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

# ============ 计算总摩擦成本 ============
# 佣金万分之3，印花税千分之一（仅卖出）
# 场内ETF免印花税

total_buy_amount = 0
total_sell_amount = 0
sell_with_tax = 0  # 需要缴印花税的卖出

for _, row in df.iterrows():
    amt = abs(row['成交金额'])
    if '买入' in str(row['交易类别']):
        total_buy_amount += amt
    elif '卖出' in str(row['交易类别']):
        total_sell_amount += amt
        # 判断是否需要印花税（ETF和基金免印花税）
        if 'ETF' not in str(row['证券名称']) and '基金' not in str(row['交易类别']):
            sell_with_tax += amt

commission_rate = 0.0003  # 万三佣金（双向）
stamp_tax_rate = 0.001   # 千一印花税（仅卖出）

total_commission = (total_buy_amount + total_sell_amount) * commission_rate
total_stamp_tax = sell_with_tax * stamp_tax_rate
total_friction = total_commission + total_stamp_tax

print("=" * 80)
print("一、摩擦成本总账")
print("=" * 80)
print(f"总买入金额:   {total_buy_amount:>15,.0f} 元")
print(f"总卖出金额:   {total_sell_amount:>15,.0f} 元")
print(f"印花税合计:   {total_stamp_tax:>15,.0f} 元")
print(f"佣金合计:     {total_commission:>15,.0f} 元")
print(f"总摩擦成本:   {total_friction:>15,.0f} 元")
print(f"摩擦成本率:   {(total_friction / (total_buy_amount + total_sell_amount) * 100):>14.3f}%")
print()

# ============ 按股票统计实现盈亏 ============
def calc_realized_pnl(stock_df):
    """计算每只股票的实现盈亏"""
    stock_df = stock_df.sort_values(['日期', '成交时间'])
    positions = []  # [(avg_cost, qty)]
    realized_pnl = 0
    
    for _, row in stock_df.iterrows():
        price = row['成交价格']
        qty = row['成交数量']
        amount = abs(row['成交金额'])
        
        if '买入' in str(row['交易类别']):
            # FIFO: 计算新的平均成本
            total_cost = sum(p[0] * p[1] for p in positions) + amount
            total_qty = sum(p[1] for p in positions) + qty
            avg_cost = total_cost / total_qty if total_qty > 0 else 0
            positions.append([avg_cost, qty])
        elif '卖出' in str(row['交易类别']):
            remaining_qty = qty
            cost_for_sell = 0
            for i in range(len(positions)-1, -1, -1):
                if remaining_qty <= 0:
                    break
                pos_avg, pos_qty = positions[i]
                use_qty = min(remaining_qty, pos_qty)
                cost_for_sell += use_qty * pos_avg
                positions[i][1] -= use_qty
                remaining_qty -= use_qty
                if positions[i][1] <= 0:
                    positions.pop(i)
            pnl = amount - cost_for_sell
            realized_pnl += pnl
    
    return realized_pnl

stocks = df.groupby('证券名称')
stock_pnl = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币']):
        continue
    is_etf = 'ETF' in str(name)
    buy_amt = group[group['交易类别'].str.contains('买入', na=False)]['成交金额'].abs().sum()
    sell_amt = group[group['交易类别'].str.contains('卖出', na=False)]['成交金额'].abs().sum()
    total_trades = len(group)
    realized = calc_realized_pnl(group)
    
    # 计算最大单日买入
    buys = group[group['交易类别'].str.contains('买入', na=False)]
    if len(buys) > 0:
        daily_buys = buys.groupby('日期_str').size()
        max_daily = daily_buys.max()
    else:
        max_daily = 0
    
    stock_pnl.append({
        'name': name,
        'code': group['证券代码'].iloc[0],
        'market': group['市场'].iloc[0],
        'is_etf': is_etf,
        'total_trades': total_trades,
        'buy_amount': buy_amt,
        'sell_amount': sell_amt,
        'realized_pnl': realized,
        'max_daily_buys': max_daily
    })

stock_pnl.sort(key=lambda x: x['realized_pnl'])  # 按亏损排序

print("=" * 80)
print("二、实现盈亏排名（亏损最严重的股票）")
print("=" * 80)
for s in stock_pnl[:20]:
    etf_tag = " [ETF]" if s['is_etf'] else ""
    print(f"{s['name']:12s}{etf_tag:6s}  实现盈亏:{s['realized_pnl']:>10,.0f}元  总交易:{s['total_trades']:4d}笔  最大单日:{s['max_daily_buys']:2d}次  买:{s['buy_amount']:>10,.0f} 卖:{s['sell_amount']:>10,.0f}")

# ============ 分析3: 卖出后悔模式 ============
print("\n" + "=" * 80)
print("三、卖出后悔模式（卖出后5日内买回）")
print("=" * 80)

# 按股票追踪买卖
def find_sell_buyback(stock_df, stock_name):
    """找出卖出后短期内又买回来的情况"""
    stock_df = stock_df.sort_values(['日期', '成交时间'])
    
    # 找所有卖出记录
    sells = stock_df[stock_df['交易类别'].str.contains('卖出', na=False)].copy()
    buys = stock_df[stock_df['交易类别'].str.contains('买入', na=False)].copy()
    
    if len(sells) == 0 or len(buys) == 0:
        return []
    
    sell_buyback = []
    for _, sell in sells.iterrows():
        sell_date = sell['日期']
        qty_sold = sell['成交数量']
        sell_price = sell['成交价格']
        
        # 5个交易日内买回
        window_buys = buys[(buys['日期'] > sell_date) & (buys['日期'] <= sell_date + pd.Timedelta(days=7))]
        
        if len(window_buys) > 0:
            total_buyback_qty = window_buys['成交数量'].sum()
            avg_buyback_price = (window_buys['成交价格'] * window_buys['成交数量']).sum() / total_buyback_qty
            buyback_pnl = (sell_price - avg_buyback_price) * min(qty_sold, total_buyback_qty)
            sell_buyback.append({
                'sell_date': sell_date.strftime('%Y%m%d'),
                'sell_price': sell_price,
                'qty_sold': qty_sold,
                'buyback_date': window_buys.iloc[0]['日期'].strftime('%Y%m%d'),
                'buyback_price': avg_buyback_price,
                'buyback_qty': total_buyback_qty,
                'days_later': (window_buys.iloc[0]['日期'] - sell_date).days,
                'pnl_estimate': buyback_pnl
            })
    
    return sell_buyback

all_sell_buyback = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币', 'ETF']):
        continue
    sb = find_sell_buyback(group, name)
    for item in sb:
        item['name'] = name
        all_sell_buyback.append(item)

print(f"卖出后5日内买回的总次数: {len(all_sell_buyback)}")

# 按标的统计
from collections import Counter
sellback_counts = Counter([item['name'] for item in all_sell_buyback])
print("\n卖出后悔次数最多的股票:")
for name, count in sellback_counts.most_common(10):
    total_pnl = sum(item['pnl_estimate'] for item in all_sell_buyback if item['name'] == name)
    print(f"  {name}: {count}次  估计损耗:{total_pnl:,.0f}元")

# ============ 分析4: T+0当日回转交易 ============
print("\n" + "=" * 80)
print("四、T+0当日回转交易（同一标的当日买卖）")
print("=" * 80)

same_day = df.groupby(['日期_str', '证券代码', '市场']).agg({
    '交易类别': list,
    '证券名称': 'first',
    '成交金额': lambda x: [(abs(v), '买入' in str(t)) for v, t in zip(x, df.loc[x.index, '交易类别'])],
    '成交价格': list,
    '成交数量': list
}).reset_index()

same_day_actions = same_day[same_day['交易类别'].apply(lambda x: '买入' in str(x) and '卖出' in str(x))]
print(f"当日既有买入又有卖出的交易日次数: {len(same_day_actions)}")

# 按股票统计
from collections import Counter
td_counts = Counter(same_day_actions['证券名称'].tolist())
print("\nT+0最频繁的标的:")
for name, count in td_counts.most_common(15):
    stock_data = df[df['证券名称'] == name]
    buys = stock_data[stock_data['交易类别'].str.contains('买入', na=False)]
    sells = stock_data[stock_data['交易类别'].str.contains('卖出', na=False)]
    buy_amt = buys['成交金额'].abs().sum()
    sell_amt = sells['成交金额'].abs().sum()
    print(f"  {name}: {count}个交易日当日买卖  买入:{buy_amt:,.0f}元  卖出:{sell_amt:,.0f}元")

# ============ 分析5: 持仓集中度分析 ============
print("\n" + "=" * 80)
print("五、持仓集中度分析")
print("=" * 80)

# 计算每只股票的累计买入金额
position_concentration = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币', 'ETF', '基金']):
        continue
    buy_amt = group[group['交易类别'].str.contains('买入', na=False)]['成交金额'].abs().sum()
    sell_amt = group[group['交易类别'].str.contains('卖出', na=False)]['成交金额'].abs().sum()
    net_buy = buy_amt - sell_amt
    position_concentration.append({
        'name': name,
        'net_buy': net_buy,
        'buy_amt': buy_amt,
        'sell_amt': sell_amt
    })

position_concentration.sort(key=lambda x: x['net_buy'], reverse=True)
total_net_buy = sum(p['net_buy'] for p in position_concentration)

print(f"总净买入金额: {total_net_buy:,.0f}元")
print("\n净买入金额最高的股票（实际仓位最重的）:")
for i, p in enumerate(position_concentration[:15]):
    pct = p['net_buy'] / total_net_buy * 100 if total_net_buy > 0 else 0
    print(f"  {i+1}. {p['name']}: 净买入{p['net_buy']:>12,.0f}元 ({pct:>5.1f}%)")

# ============ 分析6: 亏损割肉 vs 盈利止损 ============
print("\n" + "=" * 80)
print("六、止损模式分析（持有超过30天亏损卖出）")
print("=" * 80)

def analyze_holding_pnl(stock_df, stock_name):
    """分析每笔卖出的持有期和盈亏"""
    stock_df = stock_df.sort_values(['日期', '成交时间'])
    results = []
    buy_queue = []  # (date, price, qty)
    
    for _, row in stock_df.iterrows():
        action = 'buy' if '买入' in str(row['交易类别']) else 'sell'
        price = row['成交价格']
        qty = row['成交数量']
        date = row['日期']
        
        if action == 'buy':
            buy_queue.append({'date': date, 'price': price, 'qty': qty})
        else:
            remaining_qty = qty
            for buy in buy_queue[:]:
                if remaining_qty <= 0:
                    break
                if buy['qty'] <= 0:
                    continue
                use_qty = min(remaining_qty, buy['qty'])
                hold_days = (date - buy['date']).days
                pnl_pct = (price - buy['price']) / buy['price'] * 100
                results.append({
                    'name': stock_name,
                    'hold_days': hold_days,
                    'buy_price': buy['price'],
                    'sell_price': price,
                    'pnl_pct': pnl_pct,
                    'qty': use_qty
                })
                buy['qty'] -= use_qty
                remaining_qty -= use_qty
                if buy['qty'] <= 0:
                    buy_queue.remove(buy)
    
    return results

all_holding_results = []
for name, group in stocks:
    if any(keyword in str(name) for keyword in ['现金宝', '货币', 'ETF', '基金']):
        continue
    results = analyze_holding_pnl(group, name)
    all_holding_results.extend(results)

# 长期持有亏损（>30天）
long_hold_loss = [r for r in all_holding_results if r['hold_days'] > 30 and r['pnl_pct'] < -10]
print(f"持有超过30天且亏损超10%卖出: {len(long_hold_loss)}笔")

# 统计
from collections import Counter
loss_stocks = Counter([r['name'] for r in long_hold_loss])
print("\n长期持亏最严重的股票:")
for name, count in loss_stocks.most_common(10):
    stocks_loss = [r for r in long_hold_loss if r['name'] == name]
    avg_loss = sum(r['pnl_pct'] for r in stocks_loss) / len(stocks_loss)
    max_loss = min(r['pnl_pct'] for r in stocks_loss)
    total_loss_amt = sum(r['pnl_pct'] / 100 * r['buy_price'] * r['qty'] for r in stocks_loss)
    print(f"  {name}: {count}笔  平均亏损{avg_loss:.1f}%  最大亏损{max_loss:.1f}%  估计损耗:{total_loss_amt:,.0f}元")

# ============ 分析7: 亏损频率统计 ============
print("\n" + "=" * 80)
print("七、所有止损卖出统计")
print("=" * 80)

loss_sells = [r for r in all_holding_results if r['pnl_pct'] < 0]
profit_sells = [r for r in all_holding_results if r['pnl_pct'] >= 0]

print(f"总卖出笔数: {len(all_holding_results)}")
print(f"亏损卖出: {len(loss_sells)}笔 ({len(loss_sells)/len(all_holding_results)*100:.1f}%)")
print(f"盈利卖出: {len(profit_sells)}笔 ({len(profit_sells)/len(all_holding_results)*100:.1f}%)")

loss_breakdown = [
    ('亏损0-5%', len([r for r in loss_sells if -5 < r['pnl_pct'] < 0])),
    ('亏损5-10%', len([r for r in loss_sells if -10 < r['pnl_pct'] <= -5])),
    ('亏损10-20%', len([r for r in loss_sells if -20 < r['pnl_pct'] <= -10])),
    ('亏损20-50%', len([r for r in loss_sells if -50 < r['pnl_pct'] <= -20])),
    ('亏损>50%', len([r for r in loss_sells if r['pnl_pct'] <= -50])),
]
print("\n亏损分布:")
for label, count in loss_breakdown:
    print(f"  {label}: {count}笔")

profit_breakdown = [
    ('盈利0-5%', len([r for r in profit_sells if 0 <= r['pnl_pct'] < 5])),
    ('盈利5-10%', len([r for r in profit_sells if 5 <= r['pnl_pct'] < 10])),
    ('盈利10-20%', len([r for r in profit_sells if 10 <= r['pnl_pct'] < 20])),
    ('盈利20-50%', len([r for r in profit_sells if 20 <= r['pnl_pct'] < 50])),
    ('盈利>50%', len([r for r in profit_sells if r['pnl_pct'] >= 50])),
]
print("\n盈利分布:")
for label, count in profit_breakdown:
    print(f"  {label}: {count}笔")