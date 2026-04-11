"""
Market overview service.

获取大盘整体指标：成交额、涨跌停、融资余额、北向资金等。
数据源：
  成交额 → BaoStock（stock_zh_index_daily，直连） + macro_china_stock_market_cap 月度系数
  涨跌停 → AkShare（eastmoney PULL，走 SOCKS5 代理）
  融资余额 → FinShare
"""
import os
import json
from datetime import datetime, date, timedelta


# ── 工具：清除代理（httpx 用）───────────────────────────────────────────────

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


def _get_latest_prev_trading_date(base_date: date) -> date:
    """以 base_date 为基准，往前找最近的上一个交易日。"""
    for days_forward in range(1, 10):
        d = base_date - timedelta(days=days_forward)
        if d.weekday() >= 5:
            continue
        month_day = (d.month, d.day)
        if month_day in [(1, 1), (5, 1), (10, 1), (10, 2), (10, 3)]:
            continue
        return d
    return base_date - timedelta(days=1)



# ── 大盘成交额（BaoStock 日线 + macro 月度系数，直连无代理）─────────────

def _get_avg_price_coefficients() -> tuple[float, float]:
    """
    从 macro_china_stock_market_cap 月度数据推导沪市/深市平均股价系数。
    返回 (沪市平均股价, 深市平均股价)，单位：元/股。
    """
    import pandas as pd
    try:
        import akshare as ak
        cap_df = ak.macro_china_stock_market_cap().sort_values('数据日期', ascending=False)
        for _, row in cap_df.iterrows():
            sh_a = row['成交金额-上海']
            sh_v = row['成交量-上海']
            if pd.notna(sh_a) and pd.notna(sh_v):
                sh_amount = float(sh_a)
                sh_volume = float(sh_v)
                sz_amount = float(row['成交金额-深圳'])
                sz_volume = float(row['成交量-深圳'])
                if sh_volume > 0 and sz_volume > 0:
                    sh_avg = sh_amount * 1e8 / (sh_volume * 1e8)
                    sz_avg = sz_amount * 1e8 / (sz_volume * 1e8)
                    return sh_avg, sz_avg
        return 14.5, 17.2
    except Exception:
        return 14.5, 17.2


def get_market_volume() -> dict:
    """
    获取A股上一交易日全市场成交总额。
    方法：Tushare pro.daily 全市场汇总（amount单位=千元，/1e5=亿元）
    备用：BaoStock + 月度均价系数（当 Tushare 不可用时）
    """
    import pandas as pd
    try:
        trading_date = _get_latest_trading_date()
        trade_str = trading_date.strftime('%Y%m%d')

        # 1. 尝试 Tushare（更准确，直取全市场日成交额）
        tushare_error = None
        try:
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
            pro = ts.pro_api(token)
            today_df = pro.daily(trade_date=trade_str)
            if today_df is not None and not today_df.empty:
                today_total = round(today_df['amount'].sum() / 1e5, 0)  # 千元→亿
                # 昨日
                prev_date = _get_latest_prev_trading_date(trading_date)
                prev_str = prev_date.strftime('%Y%m%d')
                prev_df = pro.daily(trade_date=prev_str)
                prev_total = round(prev_df['amount'].sum() / 1e5, 0) if (prev_df is not None and not prev_df.empty) else 0
                change_pct = round((today_total - prev_total) / prev_total * 100, 2) if prev_total else 0
                return {
                    'amount': today_total,
                    'change_pct': change_pct,
                    'date': trading_date.isoformat(),
                    'sh_amount': 0,
                    'sz_amount': 0,
                }
            else:
                tushare_error = 'Tushare返回空'
        except Exception as e:
            tushare_error = str(e)

        # 2. 备用：BaoStock + 月度均价系数
        _clear_proxy()
        import akshare as ak

        sh_avg_price, sz_avg_price = _get_avg_price_coefficients()

        def get_index_vol(symbol: str, target_date: date) -> tuple[float, float]:
            df = ak.stock_zh_index_daily(symbol=symbol).sort_values('date')
            mask = df['date'].apply(lambda d: d.year == target_date.year and d.month == target_date.month and d.day == target_date.day)
            row = df[mask]
            if row.empty:
                row = df.tail(2).iloc[0:1]
                if row.empty:
                    return 0.0, 0.0
            vol = float(row.iloc[0]['volume'])
            close = float(row.iloc[0]['close'])
            return vol, close

        today_sh_vol, today_sh_close = get_index_vol('sh000001', trading_date)
        today_sz_vol, today_sz_close = get_index_vol('sz399001', trading_date)
        today_sh_amount = today_sh_vol * sh_avg_price / 1e8
        today_sz_amount = today_sz_vol * sz_avg_price / 1e8
        today_total = round(today_sh_amount + today_sz_amount, 0)

        prev_date = _get_latest_prev_trading_date(trading_date)
        prev_sh_vol, _ = get_index_vol('sh000001', prev_date)
        prev_sz_vol, _ = get_index_vol('sz399001', prev_date)
        prev_total = round(prev_sh_vol * sh_avg_price / 1e8 + prev_sz_vol * sz_avg_price / 1e8, 0)
        change_pct = round((today_total - prev_total) / prev_total * 100, 2) if prev_total else 0

        return {
            'amount': today_total,
            'change_pct': change_pct,
            'date': trading_date.isoformat(),
            'sh_amount': round(today_sh_amount, 0),
            'sz_amount': round(today_sz_amount, 0),
        }
    except Exception as e:
        return {'amount': 0, 'change_pct': 0, 'date': _get_latest_trading_date().isoformat()}


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
