"""
Market AI overview service.

使用 MiniMax 原生联网搜索获取 A股市场概览数据：
  1. 大盘今日总成交额 + 近期趋势 + 历史分位数
  2. 今日涨跌停个数 + 近期变化
  3. 今日融资余额 + 近期变化
  4. 散户情绪变化描述
  5. 近期资金流入最多行业 Top3
  6. 近期资金流出最多行业 Top3
"""
import os
import json
from datetime import datetime
from typing import Any

import httpx


# ── 环境配置 ────────────────────────────────────────────────────────────────

def _get_minimax_key() -> str:
    return os.environ.get('MINIMAX_API_KEY', '')


def _get_base_url() -> str:
    return os.environ.get('MINIMAX_API_BASE', 'https://api.minimax.chat/v1')


# ── MiniMax 联网搜索 ────────────────────────────────────────────────────────

async def synthesize_market_overview() -> dict[str, Any]:
    """
    让 MiniMax 原生搜索最新 A股市场数据，返回结构化 JSON。
    MiniMax-Text-01 支持通过 tools 参数进行联网搜索。
    """
    api_key = _get_minimax_key()
    base_url = _get_base_url()

    if not api_key:
        return _error_result("未配置 MINIMAX_API_KEY 环境变量，请联系管理员设置")

    model = "MiniMax-Text-01"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # MiniMax 联网搜索工具定义
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "搜索互联网获取最新 A股市场数据，包括成交额、涨跌停、融资余额、行业资金流向等",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索关键词，越具体越好"
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    system_prompt = """你是一个专业的 A股市场数据分析助手。

请帮我联网搜索以下 6 项最新市场数据（搜索关键词已列出），然后综合所有搜索结果，合成结构化的 JSON 数据返回。

需要搜索的关键词：
1. A股今日成交额（今日 + 当前日期）
2. A股今日涨跌停家数（今日 + 当前日期）
3. A股最新融资余额（当前月份）
4. A股近期散户情绪（当前月份，可以用"融资余额变化 散户情绪"）
5. A股近期资金流入行业排名 Top3（近5日 + 主力资金）
6. A股近期资金流出行业排名 Top3（近5日 + 主力资金）

重要要求：
- 先用 web_search 工具逐项搜索，每项搜完再搜索下一项
- 全部搜完后综合所有结果输出 JSON
- JSON 必须包含以下全部字段，signal 只能从 [放量/缩量/持平, 偏多/偏空/中性, 做多情绪/去杠杆偏空/中性, 看多/偏多/中性/偏空/看空] 中选择
- 趋势描述和变化描述均为一到两句话，简洁准确，不要臆测
- 历史分位：结合近期成交量与过去1-3个月水平估算（如"偏低约20%分位"）
- 如果某项实在搜不到数据，value 写"未知"，描述写"暂无数据"
- 只输出 JSON，不要输出其他内容"""

    user_prompt = f"""当前时间：{now_str}

请按以下步骤操作：
Step 1：用 web_search 搜索「A股今日成交额 {now_str}」
Step 2：用 web_search 搜索「A股今日涨跌停家数 {now_str}」
Step 3：用 web_search 搜索「A股最新融资余额」
Step 4：用 web_search 搜索「A股融资余额变化 散户情绪 近期」
Step 5：用 web_search 搜索「A股行业主力资金流入排名 Top3 近5日 {now_str}」
Step 6：用 web_search 搜索「A股行业主力资金流出排名 Top3 近5日 {now_str}」

全部搜索完毕后，综合所有结果输出以下 JSON 格式（不要有任何额外文字）：
{{
  "成交额": {{
    "value": "数字亿元",
    "趋势描述": "一句话描述近期成交量趋势",
    "历史分位": "偏高/偏低/中等 分位估算",
    "信号": "放量/缩量/持平"
  }},
  "涨跌停": {{
    "value": "涨停数/跌停数",
    "变化描述": "一句话描述近期涨跌停个数变化",
    "信号": "偏多/偏空/中性"
  }},
  "融资余额": {{
    "value": "数字亿元",
    "变化描述": "一句话描述近期变化",
    "信号": "做多情绪/去杠杆偏空/中性"
  }},
  "散户情绪": {{
    "描述": "一句话描述近期散户情绪变化",
    "信号": "做多情绪/去杠杆偏空/中性"
  }},
  "资金流入行业": ["行业1", "行业2", "行业3"],
  "资金流出行业": ["行业1", "行业2", "行业3"],
  "综合信号": "看多/偏多/中性/偏空/看空",
  "更新时间": "{now_str}"
}}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": "web_search"}},
        "max_tokens": 3000,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code != 200:
            return _error_result(f"MiniMax API 返回 {resp.status_code}: {resp.text[:300]}")

        result = resp.json()

        # MiniMax 返回的 content 可能是最终 JSON 字符串
        content = result["choices"][0]["message"]["content"]

        # 尝试解析 JSON
        parsed = _parse_ai_json(content)
        if parsed:
            parsed["更新时间"] = now_str
            return parsed

        return _error_result(f"AI 返回格式解析失败，内容：{content[:500]}")

    except Exception as e:
        return _error_result(f"请求异常：{str(e)}")


def _parse_ai_json(content: str) -> dict[str, Any] | None:
    """从 AI 返回内容中提取 JSON"""
    import re

    text = content.strip()

    # 去掉 markdown 代码块
    if text.startswith("```"):
        text = re.sub(r'^```json?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    # 去掉 ``` 和首尾空白
    text = text.strip()

    # 去掉 ```json 等
    text = re.sub(r'^```\w*\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试提取 JSON 代码块内容
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None


def _error_result(reason: str) -> dict[str, Any]:
    """返回错误结果的统一格式"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        "error": reason,
        "成交额":       {"value": "未知", "趋势描述": "暂无数据", "历史分位": "未知", "信号": "未知"},
        "涨跌停":       {"value": "未知", "变化描述": "暂无数据", "信号": "未知"},
        "融资余额":     {"value": "未知", "变化描述": "暂无数据", "信号": "未知"},
        "散户情绪":     {"描述": "暂无数据", "信号": "中性"},
        "资金流入行业": ["未知", "未知", "未知"],
        "资金流出行业": ["未知", "未知", "未知"],
        "综合信号":     "未知",
        "更新时间":     now_str,
    }
