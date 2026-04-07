"""
Market AI overview service.

方案：AkShare 抓取东方财富真实数据 → MiniMax-M2.7 解析合成结构化 JSON

数据项：
  1. A股今日总成交额 + 趋势描述 + 历史分位数
  2. 今日涨跌停个数 + 变化描述
  3. 今日融资余额 + 变化描述
  4. 散户情绪变化描述
  5. 资金流入 Top3 行业
  6. 资金流出 Top3 行业
"""
import os
import re
import json
from datetime import datetime, date, timedelta
from typing import Any, Optional

import httpx


# ── 工具：清除代理 ─────────────────────────────────────────────────────────

def _clear_proxy():
    """清除所有代理环境变量，避免 httpx 走 SOCKS 出错"""
    for k in ["http_proxy", "https_proxy", "all_proxy",
              "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(k, None)


# ── MiniMax M2.7 配置 ───────────────────────────────────────────────────────

_MINIMAX_KEY: Optional[str] = None
_BASE_URL = "https://api.minimaxi.com/anthropic"


def _get_minimax_key() -> str:
    global _MINIMAX_KEY
    if _MINIMAX_KEY:
        return _MINIMAX_KEY
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if key:
        _MINIMAX_KEY = key
        return _MINIMAX_KEY
    import pathlib
    profile_path = pathlib.Path.home() / ".openclaw/agents/main/agent/auth-profiles.json"
    if profile_path.exists():
        try:
            data = json.loads(profile_path.read_text(encoding="utf-8"))
            profiles = data.get("profiles", {})
            for name in ["minimax:cn", "minimax"]:
                if name in profiles:
                    k = profiles[name].get("key", "").strip()
                    if k:
                        _MINIMAX_KEY = k
                        return _MINIMAX_KEY
        except Exception:
            pass
    return ""


# ── Step 1：AkShare 抓取真实数据 ────────────────────────────────────────────

def fetch_market_data() -> dict[str, Any]:
    """用 AkShare 抓取东方财富真实市场数据"""
    _clear_proxy()
    result: dict[str, Any] = {
        "成交额亿": None,
        "昨日成交额亿": None,
        "涨停家数": None,
        "跌停家数": None,
        "融资余额亿": None,
        "融资余额变化": None,
        "资金流入行业": [],
        "资金流出行业": [],
    }

    try:
        import akshare as ak

        # 1. 成交额（上证指数日线，取最新交易日）
        index_df = ak.stock_zh_index_daily(symbol="sh000001").sort_values("date")
        today_vol = float(index_df.iloc[-1]["volume"])  # 股
        yesterday_vol = float(index_df.iloc[-2]["volume"]) if len(index_df) >= 2 else today_vol
        result["成交额亿"] = round(today_vol / 1e8, 0)
        result["昨日成交额亿"] = round(yesterday_vol / 1e8, 0)

        # 2. 涨跌停家数（取最新交易日）
        latest_date = index_df.iloc[-1]["date"].strftime("%Y%m%d")
        try:
            zt_df = ak.stock_zt_pool_em(date=latest_date)
            result["涨停家数"] = len(zt_df) if zt_df is not None and not zt_df.empty else 0
        except Exception:
            result["涨停家数"] = 0
        try:
            dt_df = ak.stock_zt_pool_dtgc_em(date=latest_date)
            result["跌停家数"] = len(dt_df) if dt_df is not None and not dt_df.empty else 0
        except Exception:
            result["跌停家数"] = 0

        # 3. 融资余额（合并沪深，AkShare macro 接口）
        try:
            rz_sh = ak.macro_china_market_margin_sh().sort_values("日期", ascending=False)
            rz_sz = ak.macro_china_market_margin_sz().sort_values("日期", ascending=False)
            if not rz_sh.empty and not rz_sz.empty:
                sh_latest = float(rz_sh.iloc[0]["融资余额"]) / 1e8
                sz_latest = float(rz_sz.iloc[0]["融资余额"]) / 1e8
                total_latest = sh_latest + sz_latest
                # 取5日前（约第6行）的数据
                if len(rz_sh) >= 6 and len(rz_sz) >= 6:
                    prev_total = float(rz_sh.iloc[5]["融资余额"]) / 1e8 + float(rz_sz.iloc[5]["融资余额"]) / 1e8
                    result["融资余额变化"] = round((total_latest - prev_total) / prev_total * 100, 2)
                result["融资余额亿"] = round(total_latest, 0)
        except Exception:
            pass

        # 4. 行业资金流向（东方财富行业板块资金流）
        try:
            ind_df = ak.stock_fund_flow_industry()
            if ind_df is not None and not ind_df.empty:
                df_sorted = ind_df.sort_values("净额", ascending=False)
                inflow_rows = df_sorted.head(3)
                outflow_rows = df_sorted.tail(3)
                result["资金流入行业"] = [
                    f"{row['行业']}({row['净额']:.1f}亿)"
                    for _, row in inflow_rows.iterrows()
                ]
                result["资金流出行业"] = [
                    f"{row['行业']}({row['净额']:.1f}亿)"
                    for _, row in outflow_rows.iterrows()
                ]
        except Exception:
            pass

    except Exception as e:
        result["_error"] = str(e)

    return result


# ── Step 2：M2.7 合成结构化 JSON ──────────────────────────────────────────

async def _call_m2_synthesize(raw: dict[str, Any], now_str: str) -> dict[str, Any]:
    api_key = _get_minimax_key()
    if not api_key:
        return _error_result("未找到 MiniMax API Key")

    成交额_val = raw.get("成交额亿")
    成交额 = f"{int(成交额_val)}亿" if 成交额_val else "未知"
    昨日成交额_val = raw.get("昨日成交额亿")
    昨日成交额 = f"{int(昨日成交额_val)}亿" if 昨日成交额_val else "未知"
    涨跌停 = f"{raw.get('涨停家数', '?')}/{raw.get('跌停家数', '?')}"
    融资余额_val = raw.get("融资余额亿")
    融资余额 = f"{int(融资余额_val)}亿" if 融资余额_val else "未知"
    融资变化 = raw.get("融资余额变化", 0)
    流入 = "；".join(raw.get("资金流入行业") or ["未知"])
    流出 = "；".join(raw.get("资金流出行业") or ["未知"])
    err = raw.get("_error", "")

    user_prompt = f"""你是一个专业的 A股市场数据分析助手。以下是今日东方财富抓取的真实市场数据，请综合分析后输出结构化 JSON。

真实数据：
- 今日A股总成交额：{成交额}（昨日：{昨日成交额}）
- 涨停家数/跌停家数：{涨跌停}
- 最新融资余额：{融资余额}（较5日前变化：{融资变化}%，正数表示增加）
- 主力资金流入行业 Top3：{流入}
- 主力资金流出行业 Top3：{流出}

分析要求：
1. 对比今日和昨日成交额，判断是放量还是缩量，给出历史分位估算
2. 结合涨停>跌停还是<跌停，判断市场情绪偏多还是偏空
3. 融资余额增加通常表示散户加杠杆（做多情绪），减少表示去杠杆
4. 综合成交额、涨跌停、融资余额变化，给出综合信号

请严格按以下 JSON 格式输出（只输出 JSON，不要其他文字）：

{{
  "成交额": {{
    "value": "数字亿元",
    "趋势描述": "一句话描述今日成交量相对昨日的变化趋势",
    "历史分位": "估算当前成交额所处历史分位，如'偏低约20%分位'或'偏高约80%分位'",
    "信号": "放量/缩量/持平"
  }},
  "涨跌停": {{
    "value": "涨停数/跌停数",
    "变化描述": "一句话描述涨跌停反映的市场情绪",
    "信号": "偏多/偏空/中性"
  }},
  "融资余额": {{
    "value": "数字亿元",
    "变化描述": "一句话描述融资余额近期变化",
    "信号": "做多情绪/去杠杆偏空/中性"
  }},
  "散户情绪": {{
    "描述": "综合涨跌停和融资余额描述散户当前情绪",
    "信号": "做多情绪/去杠杆偏空/中性"
  }},
  "资金流入行业": ["行业1", "行业2", "行业3"],
  "资金流出行业": ["行业1", "行业2", "行业3"],
  "综合信号": "看多/偏多/中性/偏空/看空",
  "更新时间": "{now_str}"
}}"""

    payload = {
        "model": "MiniMax-M2.7",
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 2000,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(
                f"{_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )

        if resp.status_code != 200:
            return _error_result(f"M2.7 API 返回 {resp.status_code}: {resp.text[:300]}")

        result_data = resp.json()
        content_list = result_data.get("content", [])
        raw_text = ""
        if isinstance(content_list, list):
            for c in content_list:
                if c.get("type") == "text":
                    raw_text = c["text"]
                    break

        parsed = _parse_json(raw_text)
        if parsed:
            parsed["更新时间"] = now_str
            return parsed
        return _error_result(f"M2.7 返回格式解析失败：{raw_text[:300]}")

    except Exception as e:
        return _error_result(f"请求异常：{str(e)}")


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^```\w*\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None


def _error_result(reason: str) -> dict[str, Any]:
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


# ── 主入口 ────────────────────────────────────────────────────────────────

async def synthesize_market_overview() -> dict[str, Any]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    raw = fetch_market_data()
    return await _call_m2_synthesize(raw, now_str)
