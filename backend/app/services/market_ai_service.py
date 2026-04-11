"""
Market AI overview service.

方案：AkShare 抓取真实数据 → MiniMax M2.7 合成结构化 JSON
（系统错误时自动重试，最多重试 3 次）
"""
import os
import re
import json
import asyncio
from datetime import datetime
from typing import Any, Optional

import httpx


# ── MiniMax M2.7 配置 ───────────────────────────────────────────────────────

_MINIMAX_KEY: Optional[str] = None
_BASE_URL = "https://api.minimaxi.com/anthropic"
_MAX_RETRIES = 3


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
    """用 AkShare + Tushare 抓取真实市场数据（有超时保护，线程方式实现）"""
    import threading
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
    _error_msg = []
    _sh_daily = [None]  # 用list包装以便在内部赋值后外部可读取
    _prev_date = [None]

    def _get_prev_trading_date(trade_date_str: str, pro_api) -> str:
        """Tushare日期格式：YYYYMMDD，找前一交易日"""
        import datetime
        d = datetime.date(int(trade_date_str[:4]), int(trade_date_str[4:6]), int(trade_date_str[6:8]))
        for _ in range(1, 8):
            d2 = d - datetime.timedelta(days=_)
            ds = d2.strftime('%Y%m%d')
            df = pro_api.daily(trade_date=ds)
            if df is not None and not df.empty:
                return ds
        return trade_date_str

    def _fetch():
        try:
            import akshare as ak
            import tushare as ts

            token = os.environ.get('TUSHARE_TOKEN', '').strip()
            if not token:
                import pathlib
                profile_path = pathlib.Path.home() / '.openclaw/agents/main/agent/auth-profiles.json'
                if profile_path.exists():
                    try:
                        data = json.loads(profile_path.read_text(encoding='utf-8'))
                        profiles = data.get('profiles', {})
                        for name in ['tushare:pro', 'tushare']:
                            if name in profiles:
                                token = profiles[name].get('key', '').strip()
                                if token:
                                    break
                    except Exception:
                        pass
            if not token:
                token = '703fd07f16a5c9e171961ad1a980d8b90793243b78b1ba6b0d92791d'
            pro_local = ts.pro_api(token)

            # 1. 成交额：Tushare pro.daily 全市场汇总（amount单位=百万元，/100=亿元）
            try:
                import datetime
                today_str = datetime.date.today().strftime('%Y%m%d')
                today_df = pro_local.daily(trade_date=today_str)
                if today_df is None or today_df.empty:
                    # 尝试用 BaoStock 找最近交易日
                    sh_d = ak.stock_zh_index_daily(symbol='sh000001').sort_values('date')
                    latest = sh_d.iloc[-1]['date'].strftime('%Y%m%d')
                    today_str = latest
                    today_df = pro_local.daily(trade_date=today_str)
                if today_df is not None and not today_df.empty:
                    # amount 单位=千元(1e3元), vol=手(100股)
                    # amount_sum千元 / 1e5 = 亿元
                    today_amount_千元 = today_df['amount'].sum()
                    result['成交额亿'] = round(today_amount_千元 / 1e5, 0)
                    # 昨日
                    prev_str = _get_prev_trading_date(today_str, pro_local)
                    _prev_date[0] = prev_str
                    prev_df = pro_local.daily(trade_date=prev_str)
                    if prev_df is not None and not prev_df.empty:
                        prev_amount_千元 = prev_df['amount'].sum()
                        result['昨日成交额亿'] = round(prev_amount_千元 / 1e5, 0)
                    # 保存 sh_daily 供后面涨跌停用
                    sh_d = ak.stock_zh_index_daily(symbol='sh000001').sort_values('date')
                    _sh_daily[0] = sh_d
                else:
                    _error_msg.append('成交额: Tushare返回空')
            except Exception as e:
                _error_msg.append(f'成交额: {e}')
                # 备用：BaoStock
                try:
                    sh_d = ak.stock_zh_index_daily(symbol='sh000001').sort_values('date')
                    sz_d = ak.stock_zh_index_daily(symbol='sz399001').sort_values('date')
                    today_sh = sh_d.iloc[-1]
                    prev_sh = sh_d.iloc[-2]
                    today_sz = sz_d.iloc[-1]
                    prev_sz = sz_d.iloc[-2]
                    cap_df = ak.macro_china_stock_market_cap().sort_values('数据日期', ascending=False)
                    row = cap_df.iloc[1]
                    sh_avg = float(row['成交金额-上海']) * 1e8 / (float(row['成交量-上海']) * 1e8) if float(row['成交量-上海']) > 0 else 14.5
                    sz_avg = float(row['成交金额-深圳']) * 1e8 / (float(row['成交量-深圳']) * 1e8) if float(row['成交量-深圳']) > 0 else 17.2
                    result['成交额亿'] = round(float(today_sh['volume']) * sh_avg / 1e8 + float(today_sz['volume']) * sz_avg / 1e8, 0)
                    result['昨日成交额亿'] = round(float(prev_sh['volume']) * sh_avg / 1e8 + float(prev_sz['volume']) * sz_avg / 1e8, 0)
                    _sh_daily[0] = sh_d
                except Exception as e2:
                    _error_msg.append(f'成交额(备用): {e2}')

            # 2. 涨跌停
            try:
                sh_d = _sh_daily[0]
                if sh_d is not None and not sh_d.empty:
                    latest_date = sh_d.iloc[-1]['date'].strftime('%Y%m%d')
                    zt_df = ak.stock_zt_pool_em(date=latest_date)
                    result['涨停家数'] = len(zt_df) if zt_df is not None and not zt_df.empty else 0
                    dt_df = ak.stock_zt_pool_dtgc_em(date=latest_date)
                    result['跌停家数'] = len(dt_df) if dt_df is not None and not dt_df.empty else 0
            except Exception as e:
                _error_msg.append(f'涨跌停: {e}')

            # 3. 融资余额
            try:
                rz_sh = ak.macro_china_market_margin_sh().sort_values("日期", ascending=False)
                rz_sz = ak.macro_china_market_margin_sz().sort_values("日期", ascending=False)
                if not rz_sh.empty and not rz_sz.empty:
                    sh_latest = float(rz_sh.iloc[0]["融资余额"]) / 1e8
                    sz_latest = float(rz_sz.iloc[0]["融资余额"]) / 1e8
                    total_latest = sh_latest + sz_latest
                    if len(rz_sh) >= 6 and len(rz_sz) >= 6:
                        prev_total = float(rz_sh.iloc[5]["融资余额"]) / 1e8 + float(rz_sz.iloc[5]["融资余额"]) / 1e8
                        result["融资余额变化"] = round((total_latest - prev_total) / prev_total * 100, 2)
                    result["融资余额亿"] = round(total_latest, 0)
            except Exception as e:
                _error_msg.append(f"融资: {e}")

            # 4. 行业资金流向
            try:
                ind_df = ak.stock_fund_flow_industry()
                if ind_df is not None and not ind_df.empty:
                    df_sorted = ind_df.sort_values("净额", ascending=False)
                    result["资金流入行业"] = [f"{r['行业']}({r['净额']:.1f}亿)" for _, r in df_sorted.head(3).iterrows()]
                    result["资金流出行业"] = [f"{r['行业']}({r['净额']:.1f}亿)" for _, r in df_sorted.tail(3).iterrows()]
            except Exception as e:
                _error_msg.append(f"资金流向: {e}")

        except Exception as e:
            _error_msg.append(str(e))

    t = threading.Thread(target=_fetch)
    t.start()
    t.join(timeout=15)  # 最多等15秒
    if t.is_alive():
        _error_msg.append("AkShare 抓取超时（15秒），部分数据未获取")

    if _error_msg:
        result["_error"] = "; ".join(_error_msg)

    return result


# ── Step 2：M2.7 合成（带重试）─────────────────────────────────────────────

async def _call_m2_synthesize(raw: dict[str, Any], now_str: str) -> dict[str, Any]:
    api_key = _get_minimax_key()
    if not api_key:
        return _error_result("未找到 MiniMax API Key，请配置 MINIMAX_API_KEY 环境变量")

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
{f"[数据抓取警告：{err}]" if err else ""}

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
    "历史分位": "估算当前成交额所处历史分位，如'历史分位约30%'或'历史分位约80%'",
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

    last_error = ""
    for attempt in range(1, _MAX_RETRIES + 1):
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
                last_error = f"M2.7 API 返回 {resp.status_code}: {resp.text[:300]}"
                # 1033/500/502/503/529 等系统错误，重试
                if resp.status_code in (500, 502, 503, 529) or "1033" in resp.text or "overloaded" in resp.text:
                    await asyncio.sleep(5 * attempt)  # 递增等待
                    continue
                return _error_result(last_error)

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
            last_error = f"M2.7 返回格式解析失败：{raw_text[:300]}"
            # 格式解析失败不重试，直接返回错误
            return _error_result(last_error)

        except Exception as e:
            last_error = f"请求异常：{str(e)}"
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2 * attempt)
                continue
            return _error_result(last_error)

    # 所有重试均失败
    return _error_result(f"M2.7 服务不可用（已重试{_MAX_RETRIES}次）：{last_error}")


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


# ── 主入口 ───────────────────────────────────────────────────────────────

async def synthesize_market_overview() -> dict[str, Any]:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    raw = fetch_market_data()
    return await _call_m2_synthesize(raw, now_str)
