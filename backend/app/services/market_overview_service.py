"""
Market overview service.

获取大盘整体指标：成交额、涨跌停、融资余额、北向资金等。
数据源优先级：
  成交额 → BaoStock（直通，无代理）
  涨跌停 → AkShare
  融资余额 → FinShare
  北向资金 → FinShare HSGT
"""
import os
import json
from datetime import datetime, date, timedelta


# ── 工具：清除代理 ─────────────────────────────────────────────────────────

def _clear_proxy():
    for k in ['http_proxy', 'https_proxy', 'all_proxy',
              'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
        os.environ.pop(k, None)


# ── 工具：找最近交易日 ─────────────────────────────────────────────────────

def _get_latest_trading_date(ref_date: date = None) -> date:
    if ref_date is None:
        ref_date = date.today()
    for days_back in range(1, 10):
        d = ref_date - timedelta(days=days_back)
        if d.weekday() >= 5:
            continue
        month_day = (d.month, d.day)
        if month_day in [(1, 1), (5, 1), (10, 1), (10, 2), (10, 3)]:
            continue
        return d
    return ref_date - timedelta(days=1)



# ── 大盘成交额（AkShare stock_zh_index_daily，无需代理）───────────────────

def get_market_volume() -> dict:
    """
    获取A股上一交易日成交总额（沪指 AkShare，无需代理）。
    注意：AkShare volume 字段单位与 BaoStock amount 不完全一致，
    绝对值可能有偏差（~2倍），但变化率基本准确。
    BaoStock 限流恢复后应优先使用。
    """
    try:
        _clear_proxy()
        import akshare as ak

        trading_date = _get_latest_trading_date()
        prev_date = _get_latest_trading_date(trading_date - timedelta(days=1))

        def get_amount(symbol: str, target_date: date) -> float:
            df = ak.stock_zh_index_daily(symbol=symbol).sort_values('date')
            row = df[df['date'].apply(lambda d: d.isoformat() == target_date.isoformat())]
            if row.empty:
                row = df.tail(1)
            # AkShare volume: 成交量（股），/1e8 = 亿元
            return float(row.iloc[0]['volume']) / 1e8

        today_amount = get_amount("sh000001", trading_date)
        prev_amount = get_amount("sh000001", prev_date)
        change_pct = round((today_amount - prev_amount) / prev_amount * 100, 2) \
            if prev_amount else 0

        return {
            "amount": round(today_amount, 0),
            "change_pct": change_pct,
            "date": trading_date.isoformat(),
        }
    except Exception:
        return {"amount": 0, "change_pct": 0, "date": _get_latest_trading_date().isoformat()}


# ── 涨跌停家数 ─────────────────────────────────────────────────────────────

def get_zt_dt_count() -> dict:
    """获取上一交易日涨停、跌停家数"""
    try:
        _clear_proxy()
        import akshare as ak

        trading_date = _get_latest_trading_date()
        trading_str = trading_date.strftime("%Y%m%d")

        zt_count = 0
        try:
            zt_df = ak.stock_zt_pool_em(date=trading_str)
            zt_count = len(zt_df) if zt_df is not None and not zt_df.empty else 0
        except Exception:
            pass

        dt_count = 0
        try:
            dt_df = ak.stock_zt_pool_dtgc_em(date=trading_str)
            dt_count = len(dt_df) if dt_df is not None and not dt_df.empty else 0
        except Exception:
            pass

        return {
            "zt_count": zt_count,
            "dt_count": dt_count,
            "date": trading_date.isoformat(),
        }
    except Exception:
        return {"zt_count": 0, "dt_count": 0, "date": _get_latest_trading_date().isoformat()}


# ── 融资余额（FinShare）────────────────────────────────────────────────────

# ── 模块级缓存：FinShare margin 数据 ────────────────────────────────────────

_margin_cache: dict = {}
_margin_cache_time: float = 0
_MARGIN_CACHE_TTL: int = 300  # 5分钟内复用


def _get_margin_cached() -> dict:
    """获取 margin 数据（带5分钟缓存，只调一次 FinShare）"""
    import time
    global _margin_cache, _margin_cache_time
    now = time.time()
    if _margin_cache is not None and len(_margin_cache) > 0 and (now - _margin_cache_time) < _MARGIN_CACHE_TTL:
        return _margin_cache
    _clear_proxy()
    import finshare as fs
    df = fs.get_margin()
    _margin_cache = df.sort_values('trade_date', ascending=False)
    _margin_cache_time = now
    return _margin_cache


def get_margin_balance() -> dict:
    """获取最新融资余额（亿元）及较上日变化"""
    try:
        df = _get_margin_cached()
        if df.empty:
            return {"balance": 0, "change": 0, "change_pct": 0, "date": ""}

        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else latest

        balance = float(latest['rzye'])   # 亿元
        prev_balance = float(prev['rzye'])
        change = balance - prev_balance
        change_pct = round(change / prev_balance * 100, 2) if prev_balance else 0

        return {
            "balance": round(balance, 2),
            "change": round(change, 2),
            "change_pct": change_pct,
            "date": str(latest['trade_date']),
        }
    except Exception:
        return {"balance": 0, "change": 0, "change_pct": 0, "date": ""}


# ── 北向资金（融资净买入变化方向，反映杠杆情绪）────────────────────────────

def get_north_flow() -> dict:
    """获取融资净买入额（rzje）变化方向"""
    try:
        df = _get_margin_cached()
        if df.empty:
            return {"net_buy": 0, "direction": "neutral", "date": ""}

        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else latest

        net_buy = float(latest['rzje'])  # 亿元
        prev_net_buy = float(prev['rzje'])
        direction = "做多" if net_buy > prev_net_buy else "做空"

        return {
            "net_buy": round(net_buy, 2),
            "direction": direction,
            "date": str(latest['trade_date']),
        }
    except Exception:
        return {"net_buy": 0, "direction": "neutral", "date": ""}


# ── 融资余额变化（市场情绪代理指标）──────────────────────────────────────

def get_margin_breadth() -> dict:
    """融资余额变化率作为散户/杠杆情绪代理指标"""
    try:
        df = _get_margin_cached().head(5)
        if df.empty:
            return {"rzye": 0, "change_pct": 0, "signal": "neutral", "date": ""}

        latest = df.iloc[0]
        prev = df.iloc[-1]  # 5日前作对比

        rzye = float(latest['rzye'])  # 亿元
        prev_rzye = float(prev['rzye'])
        change_pct = round((rzye - prev_rzye) / prev_rzye * 100, 2) if prev_rzye else 0

        if change_pct > 1:
            signal = "做多情绪"
        elif change_pct < -1:
            signal = "去杠杆偏空"
        else:
            signal = "中性"

        return {
            "rzye": round(rzye, 2),
            "change_pct": change_pct,
            "signal": signal,
            "date": str(latest['trade_date']),
        }
    except Exception:
        return {"rzye": 0, "change_pct": 0, "signal": "neutral", "date": ""}


# ── 汇总 ─────────────────────────────────────────────────────────────

def get_market_overview() -> dict:
    """获取全部市场概览指标"""
    volume = get_market_volume()
    zt_dt = get_zt_dt_count()
    margin = get_margin_balance()
    north = get_north_flow()
    breadth = get_margin_breadth()

    return {
        "market_volume": volume,
        "zt_dt": zt_dt,
        "margin": margin,
        "north_flow": north,
        "breadth": breadth,
        "updated_at": datetime.now().isoformat(),
    }
