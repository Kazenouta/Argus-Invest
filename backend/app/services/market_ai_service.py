"""
Market AI overview service.

使用 AI + 网络搜索获取市场概览数据：
  1. 大盘今日总成交额 + 近期趋势描述 + 历史分位数
  2. 今日涨跌停个数 + 近期变化描述
  3. 今日融资余额 + 近期变化描述
  4. 近期散户情绪变化描述
  5. 近期资金流入最多的三个行业
  6. 近期资金流出最多的三个行业
"""
import os
import re
import json
import time
import httpx
from datetime import datetime, date, timedelta
from typing import Any


# ── 环境配置 ────────────────────────────────────────────────────────────────

def _get_minimax_key() -> str:
    """优先从 .env 读取 MiniMax API Key"""
    # 尝试从 .env 文件读取
    env_path = os.path.join(os.path.dirname(__file__), '../../.env')
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            line = line.strip()
            if line.startswith('MINIMAX_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return os.environ.get('MINIMAX_API_KEY', '')


def _get_base_url() -> str:
    env_path = os.path.join(os.path.dirname(__file__), '../../.env')
    if os.path.exists(env_path):
        for line in open(env_path, encoding='utf-8'):
            line = line.strip()
            if line.startswith('MINIMAX_API_BASE='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return os.environ.get('MINIMAX_API_BASE', 'https://api.minimax.chat/v1')


# ── Web 搜索 ────────────────────────────────────────────────────────────────

def duckduckgo_search(query: str, num_results: int = 5) -> list[str]:
    """使用 DuckDuckGo HTML 搜索，返回文本片段列表"""
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query, "kl": "zh-cn"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = httpx.get(url, params=params, headers=headers, timeout=15, follow_redirects=True)
        # 解析 <a class="result__snippet" ...>...</a>
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        clean = []
        for s in snippets[:num_results]:
            t = re.sub(r'<[^>]+>', '', s)
            t = t.replace('&nbsp;', ' ').replace('&amp;', '&').strip()
            if len(t) > 10:
                clean.append(t)
        return clean
    except Exception:
        return []


def search_market_data() -> dict[str, Any]:
    """搜索获取各项市场数据，返回原始文本供 AI 合成"""
    results = {}

    # 1. A股成交额
    try:
        resp = httpx.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18",
                "_": int(time.time() * 1000),
            },
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"},
            timeout=10,
        )
        data = resp.json()
        if data.get("data"):
            results["成交总额"] = f"今日A股总成交额约 {data['data'].get('f6', '—')} 亿元"
    except Exception:
        pass

    # 用搜索补全
    ddg_queries = {
        "成交额": "A股今日成交额 亿元 " + datetime.now().strftime("%Y-%m-%d"),
        "涨跌停": "A股今日涨跌停家数 " + datetime.now().strftime("%Y-%m-%d"),
        "融资余额": "A股融资余额 最新 " + datetime.now().strftime("%Y年%m月"),
        "散户情绪": "A股融资余额变化 散户情绪 " + datetime.now().strftime("%Y-%m"),
        "行业资金流入": "A股行业资金流入排名 主力 " + datetime.now().strftime("%Y-%m-%d"),
    }
    for key, query in ddg_queries.items():
        results[key] = duckduckgo_search(query, num_results=3)

    return results


# ── MiniMax AI 合成 ────────────────────────────────────────────────────────

async def _call_minimax(prompt: str, system: str = "") -> str:
    """调用 MiniMax chat completion（流式），返回合成文本"""
    import asyncio
    api_key = _get_minimax_key()
    base_url = _get_base_url()
    if not api_key:
        return "[错误] 未配置 MINIMAX_API_KEY，请联系管理员"

    model = "MiniMax-Text-01"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                return f"[错误] API返回 {resp.status_code}: {resp.text[:200]}"
            result = resp.json()
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[错误] {str(e)}"


SYSTEM_PROMPT = """你是一个专业的A股市场数据分析助手。你的任务是根据搜索到的市场数据，合成结构化的市场概览。

请严格遵循以下JSON格式输出，不要输出任何其他内容（只输出JSON）：

{
  "成交额": {
    "value": "数字（亿元）",
    "趋势描述": "一句话描述近期成交量趋势",
    "历史分位": "当前成交额所处历史分位数区间（如20%-30%），如果不确定写'未知'",
    "信号": "放量/缩量/持平"
  },
  "涨跌停": {
    "value": "涨停数 / 跌停数",
    "变化描述": "一句话描述近期涨跌停个数的变化趋势",
    "信号": "偏多/偏空/中性"
  },
  "融资余额": {
    "value": "数字（亿元）",
    "变化描述": "一句话描述近期融资余额变化",
    "信号": "做多情绪/去杠杆偏空/中性"
  },
  "散户情绪": {
    "描述": "一句话描述近期散户情绪变化",
    "信号": "做多情绪/去杠杆偏空/中性"
  },
  "资金流入行业": ["行业1", "行业2", "行业3"],
  "资金流出行业": ["行业1", "行业2", "行业3"],
  "综合信号": "短期市场整体信号：看多/偏多/中性/偏空/看空",
  "更新时间": "YYYY-MM-DD HH:mm"
}

注意：
- 所有描述要简洁，一句话
- 信号基于数据判断，不要臆测
- 如果某项数据确实无法获取，value写'未知'，趋势描述写'暂无数据'
- 历史分位请基于近期成交额与过去3个月对比估算
- 综合信号要综合所有6项数据判断"""


USER_PROMPT_TEMPLATE = """请根据以下搜索到的A股市场数据，合成结构化的市场概览 JSON：

搜索数据：
{search_data}

当前时间：{now}

请直接输出JSON，不要有其他文字。"""


async def synthesize_market_overview() -> dict[str, Any]:
    """搜索 + AI 合成，返回完整市场概览"""
    # Step 1: 搜索
    raw_data = search_market_data()

    # Step 2: 整理搜索结果为文本
    search_text = json.dumps(raw_data, ensure_ascii=False, indent=2)

    # Step 3: 调用 AI 合成
    user_prompt = USER_PROMPT_TEMPLATE.format(
        search_data=search_text,
        now=datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    response_text = await _call_minimax(user_prompt, system=SYSTEM_PROMPT)

    # Step 4: 解析 AI 返回的 JSON
    try:
        # 去掉 markdown 代码块
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```json?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        result = json.loads(text)

        # 补充原始搜索数据（方便调试）
        result["_raw_search"] = raw_data
        result["ai_raw"] = response_text[:500] if len(response_text) > 500 else response_text
        return result
    except json.JSONDecodeError:
        return {
            "error": "AI 返回格式解析失败",
            "ai_raw": response_text[:1000],
            "_raw_search": raw_data,
            "成交额": {"value": "未知", "趋势描述": "AI解析失败", "历史分位": "未知", "信号": "未知"},
            "涨跌停": {"value": "未知", "变化描述": "AI解析失败", "信号": "未知"},
            "融资余额": {"value": "未知", "变化描述": "AI解析失败", "信号": "未知"},
            "散户情绪": {"描述": "AI解析失败", "信号": "未知"},
            "资金流入行业": ["未知", "未知", "未知"],
            "资金流出行业": ["未知", "未知", "未知"],
            "综合信号": "未知",
            "更新时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
