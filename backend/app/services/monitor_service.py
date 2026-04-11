"""
Indicator monitor service.

行情数据获取 + 指标计算 + 规则匹配。
使用 AkShare 获取数据。
"""
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.models.monitor import (
    MonitorRule, MonitorEvent, MonitorCheckResponse,
    IndicatorValue, MonitorStatus, MonitorRule
)
from app.services.data_storage import DataStorage


# ── 默认监控规则 ─────────────────────────────────────────────────────────────

DEFAULT_RULES: list[MonitorRule] = [
    MonitorRule(
        rule_id="MON-001",
        name="RSI 超卖提醒",
        indicator="rsi14",
        operator="<",
        threshold=30,
        description="RSI(14) < 30，超卖区域，可能存在反弹机会"
    ),
    MonitorRule(
        rule_id="MON-002",
        name="RSI 超买警告",
        indicator="rsi14",
        operator=">",
        threshold=70,
        description="RSI(14) > 70，超买区域，注意回调风险"
    ),
    MonitorRule(
        rule_id="MON-003",
        name="涨幅过大警告",
        indicator="change_pct",
        operator=">",
        threshold=5.0,
        description="单日涨幅超过 5%，注意追高风险"
    ),
    MonitorRule(
        rule_id="MON-004",
        name="跌幅过大警告",
        indicator="change_pct",
        operator="<",
        threshold=-5.0,
        description="单日跌幅超过 -5%，关注是否出现异常"
    ),
    MonitorRule(
        rule_id="MON-005",
        name="成交量突增",
        indicator="volume_ratio",
        operator=">",
        threshold=3.0,
        description="成交量超过 5 日均量的 3 倍，异动信号"
    ),
    MonitorRule(
        rule_id="MON-006",
        name="布林带下轨突破",
        indicator="boll_break_lower",
        operator="==",
        threshold=1.0,
        description="股价跌破布林带下轨，关注超跌反弹机会"
    ),
    MonitorRule(
        rule_id="MON-007",
        name="布林带上轨突破",
        indicator="boll_break_upper",
        operator="==",
        threshold=1.0,
        description="股价突破布林带上轨，强势信号但注意回调"
    ),
    MonitorRule(
        rule_id="MON-008",
        name="均线多头排列",
        indicator="ma_bull",
        operator="==",
        threshold=1.0,
        description="5日 > 20日 > 60日均线，多头排列，上升趋势"
    ),
    MonitorRule(
        rule_id="MON-009",
        name="均线空头排列",
        indicator="ma_bear",
        operator="==",
        threshold=1.0,
        description="5日 < 20日 < 60日均线，空头排列，下降趋势"
    ),
    MonitorRule(
        rule_id="MON-010",
        name="布林带中轨回落支撑",
        indicator="boll_near_middle",
        operator=">=",
        threshold=0.97,
        description="股价回落至布林带中轨97%以内，来自上方，回调支撑信号"
    ),
    MonitorRule(
        rule_id="MON-011",
        name="布林带下轨回落关注",
        indicator="boll_near_lower",
        operator=">=",
        threshold=0.97,
        description="股价回落至布林带下轨97%以内，来自上方，下轨附近关注信号"
    ),
]


# ── 行情数据获取 ─────────────────────────────────────────────────────────────

def _fetch_daily_akshare(ticker: str, days: int = 120, timeout: int = 15) -> Optional[pd.DataFrame]:
    """
    使用 AkShare 获取A股/港股日线数据，带 timeout 保护（默认15秒）。
    ticker: 股票代码，如 '000001'、'600519'、'00700'
    返回: DataFrame 或 None
    """

    def _do_fetch():
        import akshare as ak

        ticker_str = str(ticker).strip().upper()
        if ticker_str.startswith(('SH', 'SZ', 'BJ')):
            pass
        elif ticker_str.isdigit():
            code = ticker_str.zfill(6)
            if code.startswith(('6', '9')):
                ticker_str = 'SH' + code
            elif code.startswith(('0', '1', '2', '3')):
                ticker_str = 'SZ' + code
            else:
                ticker_str = 'HK' + code
        else:
            ticker_str = 'HK' + ticker_str

        if ticker_str.startswith(('SH', 'SZ', 'BJ')):
            code = ticker_str[2:].zfill(6)
            prefix_map = {'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj'}
            prefix = prefix_map.get(ticker_str[:2], 'sh')
            try:
                df = ak.stock_zh_a_daily(symbol=prefix + code, adjust='qfq')
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        'date': 'date', 'open': 'open', 'close': 'close',
                        'high': 'high', 'low': 'low', 'volume': 'volume'
                    })
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    # pct_change: 以当天close相对前一天close的变化
                    df['pct_change'] = df['close'].pct_change() * 100
                    return df.tail(days + 60)
            except Exception:
                pass
        elif ticker_str.startswith('HK'):
            code = ticker_str[2:].zfill(5)
            try:
                df = ak.stock_hk_hist(symbol=code, period="daily",
                                      start_date="20200101", end_date="20991231",
                                      adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '涨跌幅': 'pct_change'
                    })
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    return df.tail(days + 60)
            except Exception:
                pass
        return None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_do_fetch)
            return future.result(timeout=timeout)
    except FuturesTimeoutError:
        return None
    except Exception:
        return None


def _fetch_daily_tushare(ticker: str, days: int = 120, timeout: int = 15) -> Optional[pd.DataFrame]:
    """
    使用 Tushare 获取A股日线数据（作为 AkShare 失败时的备选）。
    ticker: 'SH600096', 'SZ000807' 等
    """
    from app.config import settings
    token = getattr(settings, 'TUSHARE_TOKEN', None) or None
    if not token:
        return None

    def _do_fetch():
        import tushare as ts

        ticker_str = str(ticker).strip().upper()
        # 解析成 tushare 格式: 600519.SH, 000807.SZ
        if ticker_str.startswith(('SH', 'SZ', 'BJ')):
            code = ticker_str[2:].zfill(6)
            prefix = {'SH': '.SH', 'SZ': '.SZ', 'BJ': '.BJ'}.get(ticker_str[:2], '.SH')
            ts_code = code + prefix
        elif ticker_str.isdigit():
            code = ticker_str.zfill(6)
            if code.startswith(('6', '9', '5', '11', '13', '15')):
                ts_code = code + '.SH'
            else:
                ts_code = code + '.SZ'
        else:
            return None

        try:
            pro = ts.pro_api(token)
            # Tushare 默认返回最近交易日，限制数量即可
            df = pro.daily(ts_code=ts_code, start_date='20200101', end_date='20991231')
            if df is None or df.empty:
                return None

            df = df.rename(columns={
                'trade_date': 'date', 'open': 'open', 'high': 'high',
                'low': 'low', 'close': 'close', 'vol': 'volume'
            })
            # Tushare 日期是 YYYYMMDD 字符串
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            # vol 单位是万股，转成股
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce') * 10000
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df['pct_change'] = pd.to_numeric(df.get('pct_chg'), errors='coerce')
            # 按日期升序排列（ oldest first ）
            df = df.sort_values('date').reset_index(drop=True)
            return df.tail(days + 60)
        except Exception:
            return None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_do_fetch)
            return future.result(timeout=timeout)
    except FuturesTimeoutError:
        return None
    except Exception:
        return None


# ── 指标计算 ──────────────────────────────────────────────────────────────────

def _calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """计算 RSI"""
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calculate_bollinger(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0):
    """计算布林带"""
    df = df.copy()
    df['boll_middle'] = df['close'].rolling(window=period).mean()
    df['boll_std'] = df['close'].rolling(window=period).std()
    df['boll_upper'] = df['boll_middle'] + std_mult * df['boll_std']
    df['boll_lower'] = df['boll_middle'] - std_mult * df['boll_std']
    return df


def _calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    """计算 MACD"""
    df = df.copy()
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['macd'] = ema_fast - ema_slow
    df['macd_signal'] = df['macd'].ewm(span=signal, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    return df


def _ma_cross_status(ma5: float, ma20: float, ma60: float) -> str:
    """判断均线排列状态"""
    if not all(math.isfinite(x) for x in [ma5, ma20, ma60]):
        return "unknown"
    if ma5 > ma20 > ma60:
        return "bull"
    elif ma5 < ma20 < ma60:
        return "bear"
    return "mixed"


def calculate_indicators(df: pd.DataFrame) -> Optional[IndicatorValue]:
    """
    对一只标的计算所有监控指标，返回最新一日的指标值。
    df 需要包含 columns: date, close, high, low, open, volume, pct_change
    """
    if df is None or len(df) < 30:
        return None

    df = df.copy().sort_values('date').reset_index(drop=True)

    # 计算均线
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()

    # 计算布林带
    df = _calculate_bollinger(df)

    # 计算 MACD
    df = _calculate_macd(df)

    # 计算 RSI
    df['rsi6'] = _calculate_rsi(df['close'], 6)
    df['rsi14'] = _calculate_rsi(df['close'], 14)

    # 计算量比（今日量 / 5日均量）
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()
    df['volume_ratio'] = df['volume'] / df['vol_ma5']

    # 最近两行用于判断 MACD 金叉死叉
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else row

    # 均线状态
    ma_status = _ma_cross_status(
        float(row['ma5']) if math.isfinite(row['ma5']) else 0,
        float(row['ma20']) if math.isfinite(row['ma20']) else 0,
        float(row['ma60']) if math.isfinite(row['ma60']) else 0,
    )

    # 布林带突破
    boll_upper_break = 1.0 if (math.isfinite(row['close']) and
                                math.isfinite(row['boll_upper']) and
                                row['close'] > row['boll_upper']) else 0.0
    boll_lower_break = 1.0 if (math.isfinite(row['close']) and
                               math.isfinite(row['boll_lower']) and
                               row['close'] < row['boll_lower']) else 0.0

    # 涨跌幅
    change_pct = float(row.get('pct_change', 0.0)) if math.isfinite(row.get('pct_change', 0.0)) else 0.0

    return IndicatorValue(
        ticker="",  # 外部填充
        name="",    # 外部填充
        date=str(row['date'])[:10],
        close=float(row['close']) if math.isfinite(row['close']) else 0.0,
        change_pct=change_pct,
        volume_ratio=float(row['volume_ratio']) if math.isfinite(row.get('volume_ratio', 0)) else 1.0,
        rsi6=float(row['rsi6']) if math.isfinite(row.get('rsi6', 0)) else None,
        rsi14=float(row['rsi14']) if math.isfinite(row.get('rsi14', 0)) else None,
        macd=float(row['macd']) if math.isfinite(row.get('macd', 0)) else None,
        macd_signal=float(row['macd_signal']) if math.isfinite(row.get('macd_signal', 0)) else None,
        macd_hist=float(row['macd_hist']) if math.isfinite(row.get('macd_hist', 0)) else None,
        boll_upper=float(row['boll_upper']) if math.isfinite(row.get('boll_upper', 0)) else None,
        boll_middle=float(row['boll_middle']) if math.isfinite(row.get('boll_middle', 0)) else None,
        boll_lower=float(row['boll_lower']) if math.isfinite(row.get('boll_lower', 0)) else None,
        ma5=float(row['ma5']) if math.isfinite(row.get('ma5', 0)) else None,
        ma20=float(row['ma20']) if math.isfinite(row.get('ma20', 0)) else None,
        ma60=float(row['ma60']) if math.isfinite(row.get('ma60', 0)) else None,
    )


# ── 规则匹配 ──────────────────────────────────────────────────────────────────

def match_rules(indicators: list[IndicatorValue], rules: list[MonitorRule]) -> list[MonitorEvent]:
    """对指标列表匹配规则，返回触发的事件"""
    events: list[MonitorEvent] = []
    for iv in indicators:
        for rule in rules:
            if not rule.enabled:
                continue
            triggered, signal, value, desc = _match_single_rule(iv, rule)
            if triggered:
                events.append(MonitorEvent(
                    ticker=iv.ticker,
                    name=iv.name,
                    indicator=rule.indicator,
                    signal=signal,
                    value=value,
                    threshold_desc=desc,
                    message=f"[{rule.name}] {iv.name}({iv.ticker}): {desc}，当前值 {value:.2f}"
                ))
    return events


def _match_single_rule(iv: IndicatorValue, rule: MonitorRule):
    """匹配单条规则，返回 (触发, 信号, 值, 描述)"""
    ind = rule.indicator
    threshold = rule.threshold

    # 直接数值比较
    if ind in ('rsi14', 'rsi6', 'change_pct', 'volume_ratio'):
        val = getattr(iv, ind, None)
        if val is None or not math.isfinite(val):
            return False, "", 0, ""
        desc = f"{ind} {rule.operator} {threshold}"
        if rule.operator == ">" and val > threshold:
            return True, _signal_for(ind, val, threshold), val, desc
        elif rule.operator == "<" and val < threshold:
            return True, _signal_for(ind, val, threshold), val, desc
        elif rule.operator == ">=" and val >= threshold:
            return True, _signal_for(ind, val, threshold), val, desc
        elif rule.operator == "<=" and val <= threshold:
            return True, _signal_for(ind, val, threshold), val, desc
        return False, "", 0, ""

    # 布尔型指标（均线排列、布尔带突破）
    if ind == "ma_bull":
        # ma5 > ma20 > ma60 的判断已在 calculate_indicators 里算好
        # 这里我们重新检查
        vals = {a: getattr(iv, a, None) for a in ['ma5', 'ma20', 'ma60']}
        if all(v is not None and math.isfinite(v) for v in vals.values()):
            if vals['ma5'] > vals['ma20'] > vals['ma60']:
                return True, "买入", 1.0, "5日>20日>60日均线，多头排列"
        return False, "", 0, ""

    if ind == "ma_bear":
        vals = {a: getattr(iv, a, None) for a in ['ma5', 'ma20', 'ma60']}
        if all(v is not None and math.isfinite(v) for v in vals.values()):
            if vals['ma5'] < vals['ma20'] < vals['ma60']:
                return True, "卖出", 1.0, "5日<20日<60日均线，空头排列"
        return False, "", 0, ""

    if ind == "boll_break_upper":
        if iv.boll_upper is not None and math.isfinite(iv.boll_upper) and iv.close > iv.boll_upper:
            return True, "警告", 1.0, f"突破布林带上轨({iv.boll_upper:.2f})"
        return False, "", 0, ""

    if ind == "boll_break_lower":
        if iv.boll_lower is not None and math.isfinite(iv.boll_lower) and iv.close < iv.boll_lower:
            return True, "关注", 1.0, f"跌破布林带下轨({iv.boll_lower:.2f})"
        return False, "", 0, ""

    # 布林带中轨接近（股价从上方回落，接近中轨支撑）
    # 触发条件：股价在中轨的 97%~100% 区间内，且来自上方（收于中轨附近视为支撑区域）
    if ind == "boll_near_middle":
        if iv.boll_middle is not None and math.isfinite(iv.boll_middle) and iv.boll_middle > 0:
            ratio = iv.close / iv.boll_middle
            if 0.97 <= ratio <= 1.03:  # 在中轨 ±3% 范围内
                return True, "支撑", ratio, f"接近布林带中轨({iv.boll_middle:.2f})，乖离率{(ratio-1)*100:+.2f}%"
        return False, "", 0, ""

    # 布林带下轨接近（股价从上方回落，接近下轨关注区域）
    # 触发条件：股价在下轨的 97%~100% 区间内，且未跌破
    if ind == "boll_near_lower":
        if iv.boll_lower is not None and math.isfinite(iv.boll_lower) and iv.boll_lower > 0:
            ratio = iv.close / iv.boll_lower
            if 0.97 <= ratio < 1.0:  # 在下轨 97%~100% 区间，未跌破
                return True, "关注", ratio, f"接近布林带下轨({iv.boll_lower:.2f})，乖离率{(ratio-1)*100:+.2f}%"
        return False, "", 0, ""

    return False, "", 0, ""


def _signal_for(indicator: str, value: float, threshold: float) -> str:
    """根据指标和值返回信号"""
    if indicator in ('rsi14', 'rsi6'):
        if value < 30:
            return "买入"
        elif value > 70:
            return "警告"
    if indicator == 'change_pct':
        if value > 5:
            return "警告"
        elif value < -5:
            return "关注"
    if indicator == 'volume_ratio':
        if value > 3:
            return "异动"
    return "触发"


# ── 主流程 ───────────────────────────────────────────────────────────────────

def check_portfolio_indicators() -> MonitorCheckResponse:
    """
    读取当前持仓，对每只标的获取数据并计算指标，匹配规则。
    """
    # 读取持仓
    portfolio_df = DataStorage.read_portfolio()
    if portfolio_df.empty:
        return MonitorCheckResponse(
            status="ok",
            total_positions=0,
            total_events=0,
            events=[],
            indicators=[]
        )

    all_indicators: list[IndicatorValue] = []
    all_events: list[MonitorEvent] = []

    for _, row in portfolio_df.iterrows():
        ticker = str(row.get("ticker", "")).strip()
        name = str(row.get("name", ticker))

        if not ticker:
            continue

        # 获取数据：优先 AkShare，失败则用 Tushare
        df = _fetch_daily_akshare(ticker)
        if df is None or df.empty:
            df = _fetch_daily_tushare(ticker)
        iv = calculate_indicators(df) if df is not None else None

        if iv is None:
            # 数据获取失败，创建一个占位指标
            iv = IndicatorValue(
                ticker=ticker,
                name=name,
                date=date.today().isoformat(),
                close=float(row.get("current_price", 0)),
                change_pct=0.0,
                volume_ratio=1.0,
            )
        else:
            iv.ticker = ticker
            iv.name = name

        all_indicators.append(iv)

        # 用默认规则匹配
        events = match_rules([iv], DEFAULT_RULES)
        all_events.extend(events)

    # 按时间倒序（最新的在前）
    all_events.sort(key=lambda x: x.triggered_at, reverse=True)

    return MonitorCheckResponse(
        status="ok",
        checked_at=datetime.now(),
        total_positions=len(all_indicators),
        total_events=len(all_events),
        events=all_events,
        indicators=all_indicators,
    )


# ── 状态管理 ──────────────────────────────────────────────────────────────────

_monitor_status = MonitorStatus()


def get_monitor_status() -> MonitorStatus:
    return _monitor_status


def update_monitor_status(resp: MonitorCheckResponse):
    global _monitor_status
    _monitor_status.last_checked_at = resp.checked_at
    _monitor_status.last_event_count = resp.total_events
    _monitor_status.last_position_count = resp.total_positions
