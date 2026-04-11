"""
Trade Analysis Service
分析调仓操作的得失：买入时机、信号依据、持仓匹配等。
"""
from datetime import date, datetime, timedelta
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from app.services.data_storage import DataStorage
from app.services.monitor_service import _fetch_daily_akshare, _fetch_daily_tushare, calculate_indicators, DEFAULT_RULES, _match_single_rule

INDICATOR_COLS = [
    'ticker', 'name', 'date', 'close', 'change_pct', 'volume_ratio',
    'rsi14', 'rsi6', 'macd', 'macd_signal', 'macd_hist',
    'boll_upper', 'boll_middle', 'boll_lower',
    'ma5', 'ma20', 'ma60',
]


def _price_change_after(df: pd.DataFrame, ticker: str, trade_date: date, direction: str, days: int = 5) -> Optional[float]:
    """计算交易后N天内收盘价变化（%）。direction: buy=相对买入价涨了多少，sell=相对卖出价"""
    if df is None or df.empty:
        return None
    trade_str = str(trade_date)
    future = df[df['date'] > trade_str].head(days)
    if future.empty:
        return None
    entry_price = future.iloc[0]['close'] if direction == 'buy' else future.iloc[0]['close']
    last_price = future.iloc[-1]['close']
    if entry_price == 0:
        return None
    return round((last_price - entry_price) / entry_price * 100, 2)


def _get_signals_from_df(df: Optional[pd.DataFrame]) -> list[dict]:
    """根据预取的数据计算信号（无网络请求）"""
    if df is None or len(df) < 20:
        return []
    try:
        iv = calculate_indicators(df)
        signals = []
        for rule in DEFAULT_RULES:
            trig, sig, val, desc = _match_single_rule(iv, rule)
            if trig:
                signals.append({'indicator': rule.rule_id, 'signal': sig, 'value': round(float(val), 4), 'desc': desc})
                if len(signals) >= 3:
                    break
        return signals
    except Exception:
        return []


def _reason_quality(reason: str) -> str:
    """评估逻辑填写质量"""
    if not reason or reason.strip() in ('', '点击填写逻辑...'):
        return 'missing'
    words = reason.strip()
    if len(words) < 10:
        return 'too_short'
    return 'ok'


def analyze_trades(start_date: Optional[date] = None, end_date: Optional[date] = None) -> dict:
    """
    分析调仓记录，返回分析报告。
    """
    # 1. 读取调仓记录
    trades_df = DataStorage.read_trades(start_date, end_date)
    if trades_df.empty:
        return {'status': 'no_data', 'summary': {}, 'details': []}

    trades_df = trades_df.sort_values('date')
    tickers = trades_df['ticker'].unique()

    # 2. 读取当前持仓
    portfolio_df = DataStorage.read_portfolio()
    current_holdings = {}
    if not portfolio_df.empty:
        for _, row in portfolio_df.iterrows():
            current_holdings[row['ticker']] = {
                'quantity': row.get('quantity'),
                'avg_cost': row.get('avg_cost'),
            }

    # 3. 预获取各标的历史数据（用于计算价格变化）
    price_changes: dict[str, dict] = {}  # (ticker, date, direction) -> pct_change

    # 4. 并发预获取所有标的历史数据（避免每条记录都请求一次）
    unique_tickers = list(set(tickers))
    ticker_dfs: dict[str, Optional[pd.DataFrame]] = {}

    def _fetch_ticker(ticker: str) -> tuple:
        try:
            df = _fetch_daily_akshare(ticker, days=60, timeout=8)
            if df is None or df.empty:
                df = _fetch_daily_tushare(ticker, days=60, timeout=8)
            return ticker, df
        except Exception:
            return ticker, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_ticker, t): t for t in unique_tickers}
        try:
            for fut in as_completed(futures, timeout=60):
                ticker, df = fut.result()
                ticker_dfs[ticker] = df
        except Exception:
            pass  # 部分失败不影响整体

    # 4. 逐条分析
    details = []
    for _, trade in trades_df.iterrows():
        ticker = trade['ticker']
        trade_date = trade['date']
        direction = trade['action']
        reason_q = _reason_quality(reason=trade.get('reason', ''))

        # 价格变化（买入后5天内价格变动）
        pc = price_changes.get((ticker, trade_date, direction))
        if pc is None:
            df = ticker_dfs.get(ticker)
            if df is not None and not df.empty:
                pc = _price_change_after(df, ticker, trade_date, direction, days=5)
            price_changes[(ticker, trade_date, direction)] = pc

        # 买入后下跌 > 5% → 差评
        # 卖出后上涨 > 5% → 踏空
        issue = None
        issue_level = None
        if direction == 'buy' and pc is not None and pc < -5:
            issue = f'买入后5天内下跌{pc}%（{-pc}%浮亏）'
            issue_level = 'error'
        elif direction == 'sell' and pc is not None and pc > 5:
            issue = f'卖出后5天内上涨{pc}%（踏空）'
            issue_level = 'warning'
        elif reason_q == 'missing':
            issue = '缺少操作逻辑'
            issue_level = 'warning'
        elif reason_q == 'too_short':
            issue = '操作逻辑过于简略'
            issue_level = 'info'

        # 当前是否在持仓中
        in_portfolio = ticker in current_holdings

        # 交易时是否有信号（复用预取数据，无额外网络请求）
        signals = _get_signals_from_df(ticker_dfs.get(ticker))
        has_signal = len(signals) > 0

        details.append({
            'id': int(trade['id']),
            'date': str(trade_date),
            'ticker': ticker,
            'name': trade.get('name', ticker),
            'action': direction,
            'price': round(float(trade['price']), 3) if trade.get('price') else None,
            'quantity': int(trade['quantity']) if trade.get('quantity') else None,
            'amount': round(float(trade['amount']), 2) if trade.get('amount') else None,
            'reason': trade.get('reason', ''),
            'reason_quality': reason_q,
            'price_change_5d': pc,
            'issue': issue,
            'issue_level': issue_level,
            'in_portfolio': in_portfolio,
            'has_signal_before': has_signal,
            'signals': signals,
        })

    # 5. 汇总统计
    total = len(details)
    buys = [d for d in details if d['action'] == 'buy']
    sells = [d for d in details if d['action'] == 'sell']
    issues = [d for d in details if d['issue'] is not None]
    no_reason = [d for d in details if d['reason_quality'] == 'missing']
    no_signal = [d for d in details if d['action'] == 'buy' and not d['has_signal_before']]

    # 买入后5天盈利比例
    buys_with_pc = [d for d in buys if d['price_change_5d'] is not None]
    buys_profit = [d for d in buys_with_pc if d['price_change_5d'] > 0]
    win_rate = round(len(buys_profit) / len(buys_with_pc) * 100, 1) if buys_with_pc else None

    avg_change = round(float(sum(d['price_change_5d'] for d in buys_with_pc) / len(buys_with_pc)), 2) if buys_with_pc else None

    # 持仓但无逻辑（买了但不知道为什么买）
    held_without_reason = [d for d in buys if not d['in_portfolio'] and d['reason_quality'] == 'missing']

    summary = {
        'total_trades': total,
        'total_buys': len(buys),
        'total_sells': len(sells),
        'win_rate_5d': win_rate,
        'avg_change_5d': avg_change,
        'total_issues': len(issues),
        'no_reason_count': len(no_reason),
        'no_signal_count': len(no_signal),
        'held_without_reason_count': len(held_without_reason),
        'issue_breakdown': {
            'bad_timing_buy': len([d for d in details if d['issue_level'] == 'error']),
            'missed_profit_sell': len([d for d in details if d['action'] == 'sell' and d['issue_level'] == 'warning']),
            'missing_logic': len(no_reason),
            'no_signal_buy': len(no_signal),
        },
    }

    return {
        'status': 'ok',
        'summary': summary,
        'details': details,
        'analyzed_at': datetime.now().isoformat(),
    }
