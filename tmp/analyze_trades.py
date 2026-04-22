import pandas as pd
import numpy as np

df = pd.read_excel('docs/成交记录/20260401-历史成交.xlsx', skiprows=4)
df.columns = ['日期', '成交时间', '交易类别', '证券代码', '证券名称', '成交价格', '成交数量', '证券余额', '成交金额', '股东代码', '市场']
df = df.dropna(subset=['日期', '证券名称'])
df = df[df['交易类别'].notna()]
df['日期'] = pd.to_datetime(df['日期'].astype(str), errors='coerce')
df = df[df['日期'].notna()]
df['成交价格'] = pd.to_numeric(df['成交价格'], errors='coerce')
df['成交数量'] = pd.to_numeric(df['成交数量'], errors='coerce')
df['成交金额'] = pd.to_numeric(df['成交金额'], errors='coerce')
df['日期_str'] = df['日期'].dt.strftime('%Y%m%d')
df['年月'] = df['日期'].dt.to_period('M')

# 按股票分组，构建累计持仓和平均成本
def analyze_stock(stock_df, stock_name):
    stock_df = stock_df.sort_values(['日期', '成交时间'])
    positions = []  # (price, qty)
    trades = []
    
    for _, row in stock_df.iterrows():
        action = 'buy' if '买入' in str(row['交易类别']) else 'sell'
        price = row['成交价格']
        qty = row['成交数量']
        date = row['日期']
        amount = abs(row['成交金额'])
        
        if action == 'buy':
            trades.append({'date': date, 'action': 'buy', 'price': price, 'qty': qty, 'amount': amount})
            # 计算新平均成本
            total_cost = sum(p[0] * p[1] for p in positions) + amount
            total_qty = sum(p[1] for p in positions) + qty
            avg_cost = total_cost / total_qty if total_qty > 0 else 0
            positions.append([avg_cost, qty])
        else:
            trades.append({'date': date, 'action': 'sell', 'price': price, 'qty': qty, 'amount': amount})
            remaining_qty = qty
            realized_pnl = 0
            for i in range(len(positions)-1, -1, -1):
                if remaining_qty <= 0:
                    break
                pos_avg, pos_qty = positions[i]
                use_qty = min(remaining_qty, pos_qty)
                realized_pnl += use_qty * (price - pos_avg)
                positions[i][1] -= use_qty
                remaining_qty -= use_qty
            trades[-1]['realized_pnl'] = realized_pnl
    
    remaining = sum(p[1] for p in positions)
    avg_cost = sum(p[0] * p[1] for p in positions) / remaining if remaining > 0 else 0
    
    # 当日买卖次数
    buy_days = stock_df[stock_df['交易类别'].str.contains('买入', na=False)].groupby('日期_str').size()
    max_daily_buys = buy_days.max() if len(buy_days) > 0 else 0
    
    return {
        'name': stock_name,
        'code': stock_df['证券代码'].iloc[0],
        'market': stock_df['市场'].iloc[0],
        'total_trades': len(stock_df),
        'buy_count': len(stock_df[stock_df['交易类别'].str.contains('买入', na=False)]),
        'sell_count': len(stock_df[stock_df['交易类别'].str.contains('卖出', na=False)]),
        'remaining': remaining,
        'avg_cost': avg_cost,
        'max_daily_buys': max_daily_buys,
        'trades': trades
    }

stocks = df.groupby('证券名称')
results = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币', 'ETF', '基金']):
        continue
    r = analyze_stock(group, name)
    results.append(r)

results.sort(key=lambda x: x['total_trades'], reverse=True)

print("=" * 80)
print("一、交易最频繁的问题股票（Top 15）")
print("=" * 80)
for r in results[:15]:
    print(f"\n{r['name']} ({r['code']}, {r['market']})")
    print(f"  总交易{r['total_trades']}次 | 买入{r['buy_count']}次 | 卖出{r['sell_count']}次")
    print(f"  剩余持仓:{r['remaining']:.0f}股 | 平均成本:{r['avg_cost']:.2f}元 | 最大单日买入:{r['max_daily_buys']}次")

# ============ 分析2: 当日买卖（冲动型交易） ============
print("\n" + "=" * 80)
print("二、当日买卖模式（冲动交易信号）")
print("=" * 80)

# 找到当日既有买入又有卖出的情况
same_day = df.groupby(['日期_str', '证券代码']).agg({
    '交易类别': list,
    '证券名称': 'first',
    '成交金额': lambda x: list(x)
}).reset_index()

same_day_buysell = same_day[same_day['交易类别'].apply(lambda x: '买入' in str(x) and '卖出' in str(x))]
print(f"当日既有买入又有卖出的交易日次数: {len(same_day_buysell)}")

# ============ 分析3: 连续下跌后加仓 ============
print("\n" + "=" * 80)
print("三、连续下跌后加仓（越跌越买陷阱）")
print("=" * 80)

def check_dip_buying(stock_df, stock_name):
    """检查是否有连续下跌后加仓的行为"""
    buys = stock_df[stock_df['交易类别'].str.contains('买入', na=False)].copy()
    if len(buys) < 3:
        return None
    buys = buys.sort_values('日期')
    buys['price'] = buys['成交价格'].values
    buys['date'] = buys['日期'].values
    
    dip_patterns = []
    for i in range(1, len(buys)-1):
        prev_price = buys.iloc[i-1]['price']
        curr_price = buys.iloc[i]['price']
        next_price = buys.iloc[i+1]['price']
        
        # 如果买入时价格比上次低，且下次买入价格更低 = 越买越跌
        if curr_price < prev_price and next_price < curr_price:
            dip_patterns.append({
                'date1': buys.iloc[i-1]['日期_str'],
                'price1': prev_price,
                'date2': buys.iloc[i]['日期_str'],
                'price2': curr_price,
                'date3': buys.iloc[i+1]['日期_str'],
                'price3': next_price,
            })
    return dip_patterns if dip_patterns else None

for r in results[:10]:
    stock_df = df[df['证券名称'] == r['name']]
    dips = check_dip_buying(stock_df, r['name'])
    if dips:
        print(f"\n{r['name']}: 发现{len(dips)}次越跌越买模式")
        for d in dips[:3]:
            print(f"  {d['date1']}({d['price1']:.2f}) → {d['date2']}({d['price2']:.2f}) → {d['date3']}({d['price3']:.2f})")

# ============ 分析4: 盈利后高位加仓 ============
print("\n" + "=" * 80)
print("四、盈利后高位加仓（贪心陷阱）")
print("=" * 80)

def check_riding_winners(stock_df, stock_name):
    """检查是否在盈利后继续加仓"""
    buys = stock_df[stock_df['交易类别'].str.contains('买入', na=False)].copy()
    if len(buys) < 2:
        return None
    buys = buys.sort_values('日期')
    
    # 计算每个买入点的历史最高价
    winners = []
    for i in range(1, len(buys)):
        prev_price = buys.iloc[i-1]['成交价格']
        curr_price = buys.iloc[i]['成交价格']
        # 当前买入价比上次高 10% 以上
        if curr_price > prev_price * 1.10:
            winners.append({
                'date1': buys.iloc[i-1]['日期_str'],
                'price1': prev_price,
                'date2': buys.iloc[i]['日期_str'],
                'price2': curr_price,
                'gain_pct': (curr_price - prev_price) / prev_price * 100
            })
    return winners if winners else None

for r in results[:10]:
    stock_df = df[df['证券名称'] == r['name']]
    winners = check_riding_winners(stock_df, r['name'])
    if winners:
        print(f"\n{r['name']}: 发现{len(winners)}次高位加仓")
        for w in winners[:3]:
            print(f"  {w['date1']}({w['price1']:.2f}) → {w['date2']}({w['price2']:.2f}) 涨幅+{w['gain_pct']:.0f}%")

# ============ 分析5: 月度交易频率 ============
print("\n" + "=" * 80)
print("五、月度交易频率分析")
print("=" * 80)
monthly = df.groupby('年月').size()
print(f"月均交易笔数: {monthly.mean():.1f}")
print(f"最高: {monthly.max()}笔 ({monthly.idxmax()})")
print(f"最低: {monthly.min()}笔 ({monthly.idxmin()})")
print("\n各月交易笔数:")
for period, count in monthly.items():
    bar = '█' * (count // 20)
    print(f"  {period}: {count:4d} {bar}")

# ============ 分析6: ETF高频 ============
print("\n" + "=" * 80)
print("六、ETF高频交易")
print("=" * 80)
etf_df = df[df['证券名称'].str.contains('ETF', na=False)]
etf_trades = etf_df.groupby('证券名称').size().sort_values(ascending=False)
print(etf_trades.to_string())

print("\n" + "=" * 80)
print("七、止损纪律分析")
print("=" * 80)
# 找到卖出时亏损超过5%的情况
sell_with_loss = df[(df['交易类别'].str.contains('卖出', na=False))].copy()
print(f"总卖出笔数: {len(sell_with_loss)}")

# 按股票统计持有天数
def calc_holding_periods(stock_df):
    """计算每次卖出的持有天数"""
    holding_days = []
    buy_records = []
    for _, row in stock_df.iterrows():
        if '买入' in str(row['交易类别']):
            buy_records.append({'date': row['日期'], 'price': row['成交价格'], 'qty': row['成交数量']})
        elif '卖出' in str(row['交易类别']):
            qty = row['成交数量']
            for buy in buy_records[:]:
                if buy['qty'] <= 0:
                    continue
                use_qty = min(qty, buy['qty'])
                days = (row['日期'] - buy['date']).days
                holding_days.append({'days': days, 'buy_price': buy['price'], 'sell_price': row['成交价格'], 'pnl_pct': (row['成交价格'] - buy['price']) / buy['price'] * 100})
                buy['qty'] -= use_qty
                qty -= use_qty
                if buy['qty'] <= 0:
                    buy_records.remove(buy)
                if qty <= 0:
                    break
    return holding_days

long_hold_with_loss = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币', 'ETF', '基金']):
        continue
    holdings = calc_holding_periods(group)
    for h in holdings:
        if h['days'] > 20 and h['pnl_pct'] < -10:
            long_hold_with_loss.append({**h, 'name': name})

if long_hold_with_loss:
    long_hold_with_loss.sort(key=lambda x: x['days'], reverse=True)
    print(f"\n持有超过20天且亏损超10%的情况: {len(long_hold_with_loss)}次")
    for item in long_hold_with_loss[:10]:
        print(f"  {item['name']}: 持有{item['days']}天 | 买{item['buy_price']:.2f}→卖{item['sell_price']:.2f} 亏损{item['pnl_pct']:.1f}%")