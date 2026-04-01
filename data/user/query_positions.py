#!/usr/bin/env python3
"""
持仓查询工具
用法: python3 query_positions.py 2025-03-31
"""
import sys
import pyarrow.parquet as pq

DATA = "/Users/bxz/Documents/projects/Argus-Invest/data/user/"
FILE = DATA + "daily_positions_filled.parquet"

def load():
    df = pq.read_table(FILE).to_pandas()
    df['date_str'] = df['日期'].astype(str).str[:10]
    return df

def query(date_str, include_zero=False):
    """
    查询指定日期的持仓数据
    参数:
        date_str: 日期字符串，格式 'YYYY-MM-DD'
        include_zero: 是否返回零持仓记录（默认否）
    返回: list of dict
    """
    dp = load()
    r = dp[dp['date_str'] == date_str]
    if not include_zero:
        r = r[r['end_qty'] > 0]
    return r[['证券代码','证券名称','市场','end_qty','last_price',
               'buy_amount','sell_amount','buy_count','sell_count']].to_dict('records')

def available_dates(limit=None):
    """列出所有有持仓记录的日期（倒序）"""
    dp = load()
    dates = sorted(dp[dp['end_qty']>0]['date_str'].unique(), reverse=True)
    if limit:
        dates = dates[:limit]
    return dates

def show(date_str):
    """打印格式化的持仓报表"""
    records = query(date_str)
    if not records:
        print(f"无持仓数据: {date_str}")
        return
    total = sum(r['end_qty'] * (r['last_price'] or 0) for r in records)
    print(f"\n{'='*52}")
    print(f"📊 {date_str} 持仓 ({len(records)} 只)  总市值≈{total:,.0f}")
    print(f"{'代码':<8} {'名称':<10} {'持股':>7} {'价':>7} {'市场':<6}")
    print("-"*45)
    for r in sorted(records, key=lambda x: x['证券名称']):
        p = r['last_price'] if (r['last_price'] == r['last_price']) else 0
        print(f"{r['证券代码']:<8} {r['证券名称']:<10} {r['end_qty']:>7.0f} {p:>7.3f} {r['市场']:<6}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 query_positions.py <日期 YYYY-MM-DD>")
        print("\n最近有持仓的日期:")
        for d in available_dates(10):
            print(f"  {d}")
        sys.exit(1)
    show(sys.argv[1])
