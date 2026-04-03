"""
Support & Resistance trading rules engine.

基于《炒股的智慧》支撑线/阻力线理论，
结合持仓成本，评估每个持仓标的的买卖信号。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd

from app.services.market_data import MarketData


# ─── 信号枚举 ────────────────────────────────────────────────────────────────

class Signal(Enum):
    BUY      = "买入信号"
    SELL     = "卖出信号"
    SELL_HALF = "建议卖出一半"
    STOP_LOSS = "止损信号"
    WATCH     = "关注（无操作）"
    SAFE      = "安全（无信号）"


# ─── 关键价位 ────────────────────────────────────────────────────────────────

@dataclass
class KeyLevels:
    """支撑/阻力关键价位"""
    ticker: str
    name: str
    current_price: float
    cost_price: float         # 持仓成本价

    # 均线（辅助判断趋势）
    ma20: Optional[float] = None
    ma50: Optional[float] = None
    ma250: Optional[float] = None

    # 支撑/阻力
    resistance_now: Optional[float] = None   # 最近阻力位
    support_now: Optional[float] = None       # 最近支撑位
    support_near: Optional[float] = None      # 次级支撑

    # 止损位
    stop_loss_8pct: float = 0.0   # 成本 × 0.92
    stop_loss_15pct: float = 0.0  # 成本 × 0.85

    # 止盈移动止损
    profit_high: float = 0.0      # 持仓期最高价
    trailing_stop: float = 0.0    # 移动止盈线（最高价×0.85）
    cost_plus_5pct: float = 0.0  # 成本+5%，用于涨幅≥20%后保护利润

    # 基本面/技术面判断
    trend: str = "neutral"         # "up" / "down" / "neutral"
    distance_to_resistance_pct: float = 0.0
    distance_to_support_pct: float = 0.0

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "name": self.name,
            "current_price": self.current_price,
            "cost_price": self.cost_price,
            "ma20": round(self.ma20, 3) if self.ma20 else None,
            "ma50": round(self.ma50, 3) if self.ma50 else None,
            "ma250": round(self.ma250, 3) if self.ma250 else None,
            "resistance_now": round(self.resistance_now, 3) if self.resistance_now else None,
            "support_now": round(self.support_now, 3) if self.support_now else None,
            "support_near": round(self.support_near, 3) if self.support_near else None,
            "stop_loss_8pct": round(self.stop_loss_8pct, 3) if self.stop_loss_8pct else None,
            "stop_loss_15pct": round(self.stop_loss_15pct, 3) if self.stop_loss_15pct else None,
            "profit_high": round(self.profit_high, 3) if self.profit_high else None,
            "trailing_stop": round(self.trailing_stop, 3) if self.trailing_stop else None,
            "cost_plus_5pct": round(self.cost_plus_5pct, 3) if self.cost_plus_5pct else None,
            "trend": self.trend,
            "distance_to_resistance_pct": round(self.distance_to_resistance_pct, 1),
            "distance_to_support_pct": round(self.distance_to_support_pct, 1),
        }


# ─── 规则结果 ────────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id: str
    name: str
    severity: str            # "critical" / "major" / "minor"
    signal: Signal
    ticker: str
    message: str
    price_action: Optional[str] = None  # 具体价格建议

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "signal": self.signal.value,
            "ticker": self.ticker,
            "message": self.message,
            "price_action": self.price_action,
        }


# ─── 支撑/阻力计算 ────────────────────────────────────────────────────────────

def _find_swing_points(df: pd.DataFrame, lookback: int = 60) -> tuple[list[float], list[float]]:
    """
    用简单的高低波段法找支撑/阻力区。
    返回 (highs, lows) — 近 N 日内显著的波段高点和低点。
    """
    if len(df) < 10:
        return [], []

    recent = df.tail(lookback).copy()
    highs, lows = [], []

    for i in range(1, len(recent) - 1):
        row = recent.iloc[i]
        prev_row = recent.iloc[i - 1]
        next_row = recent.iloc[i + 1]
        # 波段高点
        if float(row["high"]) >= float(prev_row["high"]) and float(row["high"]) >= float(next_row["high"]):
            highs.append(float(row["high"]))
        # 波段低点
        if float(row["low"]) <= float(prev_row["low"]) and float(row["low"]) <= float(next_row["low"]):
            lows.append(float(row["low"]))
    return highs, lows


def _cluster_levels(levels: list[float], tolerance: float = 0.03) -> list[float]:
    """
    将相近的价位聚类，取每个类的中位数作为关键价位。
    tolerance: 聚类容差（3%）
    """
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters = []
    current = [sorted_levels[0]]
    for price in sorted_levels[1:]:
        if price <= current[-1] * (1 + tolerance):
            current.append(price)
        else:
            clusters.append(current)
            current = [price]
    clusters.append(current)
    return [sum(c) / len(c) for c in clusters]


def _nearest_level(price: float, levels: list[float], direction: str = "above") -> Optional[float]:
    """找最近的上方或下方价位"""
    if not levels:
        return None
    sorted_levels = sorted(levels)
    if direction == "above":
        candidates = [x for x in sorted_levels if x > price + 0.001]
        return min(candidates) if candidates else None
    else:
        candidates = [x for x in sorted_levels if x < price - 0.001]
        return max(candidates) if candidates else None


# ─── 单标的规则评估 ──────────────────────────────────────────────────────────

def evaluate_ticker(
    ticker: str,
    name: str,
    cost_price: float,
    quantity: int,
    holding_days: int = 0,
    peak_profit_price: Optional[float] = None,
) -> tuple[KeyLevels, list[RuleResult]]:
    """
    评估单个持仓标的。
    holding_days: 持有天数（从成本价算起）
    peak_profit_price: 持仓期内最高收盘价（用于移动止盈追踪）
    """
    results: list[RuleResult] = []

    # ── 1. 获取历史数据 ─────────────────────────────────────────
    df = MarketData.get_ma(ticker, period=20, days=250)
    if df.empty:
        return KeyLevels(ticker, name, 0, cost_price), results

    close = float(df.iloc[-1]["close"])
    high = float(df["high"].max())
    low = float(df["low"].min())

    # ── 2. 计算均线 ─────────────────────────────────────────────
    ma20 = float(df["ma20"].iloc[-1]) if not pd.isna(df["ma20"].iloc[-1]) else None
    ma50 = df["close"].rolling(50).mean().iloc[-1]
    ma50 = float(ma50) if not pd.isna(ma50) else None
    ma250_val = df["close"].rolling(250).mean().iloc[-1]
    ma250 = float(ma250_val) if not pd.isna(ma250_val) else None

    # ── 3. 计算支撑/阻力 ─────────────────────────────────────────
    highs_60, lows_60 = _find_swing_points(df, lookback=60)
    highs_20, lows_20 = _find_swing_points(df, lookback=20)

    # 用60日波段高低点计算阻力/支撑区
    all_highs = _cluster_levels(highs_60)
    all_lows = _cluster_levels(lows_60)

    resistance_now = _nearest_level(close, all_highs, direction="above")
    support_now = _nearest_level(close, all_lows, direction="below")
    support_near = _nearest_level(close, all_lows, direction="above")  # 最近的次级支撑（在价格上方）

    # 趋势判断：看收盘是否在 MA20/MA50 之上
    if ma20 and close > ma20:
        trend = "up"
    elif ma20 and close < ma20:
        trend = "down"
    else:
        trend = "neutral"

    # ── 4. 止损价位 ─────────────────────────────────────────────
    stop_loss_8pct = round(cost_price * 0.92, 3)
    stop_loss_15pct = round(cost_price * 0.85, 3)

    # ── 5. 止盈追踪 ─────────────────────────────────────────────
    profit_high = peak_profit_price if peak_profit_price else close
    if close > profit_high:
        profit_high = close
    trailing_stop = round(profit_high * 0.85, 3)  # 从最高价回撤15%触发止盈

    # 成本+5%（用于涨幅≥20%后的利润保护）
    cost_plus_5pct = round(cost_price * 1.05, 3)

    # ── 6. 距离计算 ─────────────────────────────────────────────
    dist_to_res = ((resistance_now - close) / close * 100) if resistance_now else 0
    dist_to_sup = ((close - support_now) / close * 100) if support_now else 0

    levels = KeyLevels(
        ticker=ticker,
        name=name,
        current_price=close,
        cost_price=cost_price,
        ma20=ma20,
        ma50=ma50,
        ma250=ma250,
        resistance_now=resistance_now,
        support_now=support_now,
        support_near=support_near,
        stop_loss_8pct=stop_loss_8pct,
        stop_loss_15pct=stop_loss_15pct,
        profit_high=profit_high,
        trailing_stop=trailing_stop,
        cost_plus_5pct=cost_plus_5pct,
        trend=trend,
        distance_to_resistance_pct=dist_to_res,
        distance_to_support_pct=dist_to_sup,
    )

    # ── 7. 规则评估 ─────────────────────────────────────────────
    position_ratio = close / cost_price  # 涨幅比例

    # ── R-SR01：支撑线保护 ──────────────────────────────────────
    if support_now and close <= support_now * 1.02:
        results.append(RuleResult(
            rule_id="SR-01",
            name="支撑线保护（跌破警告）",
            severity="critical",
            signal=Signal.SELL if close < support_now else Signal.WATCH,
            ticker=ticker,
            message=f"现价 {close:.3f} 正在接近支撑位 {support_now:.3f}，"
                    f"（历史波段低点区）",
            price_action=f"若跌破 {support_now:.3f}，建议减仓50%或清仓" if close < support_now else f"支撑位 {support_now:.3f}，保持观察",
        ))

    # ── R-SR02：阻力线突破买入 ──────────────────────────────────
    if resistance_now:
        dist = (close - resistance_now) / resistance_now * 100
        if dist >= -3:  # 在阻力位3%以内
            results.append(RuleResult(
                rule_id="SR-02",
                name="阻力线突破（关注买入机会）",
                severity="major",
                signal=Signal.WATCH,
                ticker=ticker,
                message=f"现价 {close:.3f} 接近阻力位 {resistance_now:.3f}，"
                        f"突破后有望开启升势（突破 {resistance_now:.3f} 确认买入信号）",
                price_action=f"突破 {resistance_now:.3f} 可少量买入，止损设在本支撑 {support_now:.3f} 以下",
            ))

    # ── R-SR03：均线趋势保护 ────────────────────────────────────
    if ma20 and close < ma20:
        results.append(RuleResult(
            rule_id="SR-03",
            name="跌破20日均线（减仓警告）",
            severity="major",
            signal=Signal.SELL_HALF,
            ticker=ticker,
            message=f"现价 {close:.3f} 跌破20日均线 {ma20:.3f}，上升趋势可能结束",
            price_action=f"建议减仓50%；若继续跌破60日均线（{f'{ma50:.3f}' if ma50 else 'N/A'}）则清仓",
        ))
    elif ma20 and close > ma20:
        results.append(RuleResult(
            rule_id="SR-03",
            name="站稳20日均线（安全持有）",
            severity="minor",
            signal=Signal.SAFE,
            ticker=ticker,
            message=f"现价 {close:.3f} 在20日均线 {ma20:.3f} 之上，趋势向上",
            price_action=None,
        ))

    # ── R-SR04：8% 强制止损 ────────────────────────────────────
    if position_ratio <= 0.92:  # 亏损 ≥ 8%
        results.append(RuleResult(
            rule_id="SR-04",
            name="⚠️ 强制止损线（-8%）",
            severity="critical",
            signal=Signal.STOP_LOSS,
            ticker=ticker,
            message=f"持仓亏损 {((position_ratio - 1) * 100):.1f}%，已触及 8% 止损线！"
                    f"（成本价 {cost_price:.3f}，止损价 {stop_loss_8pct:.3f}）",
            price_action=f"立即减仓50%，禁止加仓摊薄成本！",
        ))

    # ── R-SR05：15% 深度止损 ────────────────────────────────────
    if position_ratio <= 0.85:  # 亏损 ≥ 15%
        results.append(RuleResult(
            rule_id="SR-05",
            name="⚠️ 深度止损线（-15%）",
            severity="critical",
            signal=Signal.STOP_LOSS,
            ticker=ticker,
            message=f"持仓亏损 {((position_ratio - 1) * 100):.1f}%，已触及 15% 清仓红线！"
                    f"（成本价 {cost_price:.3f}，止损价 {stop_loss_15pct:.3f}）",
            price_action="无条件立即清仓，不侥幸、不等待、不补仓！",
        ))

    # ── R-SR06：移动止盈（从最高价回撤15%）─────────────────────
    if profit_high > cost_price * 1.05 and trailing_stop > cost_price:
        if close <= trailing_stop:
            results.append(RuleResult(
                rule_id="SR-06",
                name="移动止盈触发（最高价回撤≥15%）",
                severity="critical",
                signal=Signal.SELL,
                ticker=ticker,
                message=f"持仓最高价 {profit_high:.3f}，回撤15%触发止盈线 {trailing_stop:.3f}！"
                        f"当前价 {close:.3f}，已触及！",
                price_action=f"立即止盈卖出！",
            ))
        elif close <= profit_high * 0.92:  # 接近回撤10%
            results.append(RuleResult(
                rule_id="SR-06",
                name="⚠️ 移动止盈预警（接近回撤15%）",
                severity="major",
                signal=Signal.SELL_HALF,
                ticker=ticker,
                message=f"从最高价 {profit_high:.3f} 回撤超过10%（现价 {close:.3f}），"
                        f"注意保护利润，止盈线 {trailing_stop:.3f}",
                price_action=f"建议减仓50%，跌破 {trailing_stop:.3f} 则清仓",
            ))

    # ── R-SR07：成本+5% 保护（涨幅≥20%后）─────────────────────
    if position_ratio >= 1.20:
        # 已经涨了20%以上，检查是否回撤到成本+5%
        if close < cost_plus_5pct:
            results.append(RuleResult(
                rule_id="SR-07",
                name="利润保护触发（成本+5%守护线）",
                severity="critical",
                signal=Signal.SELL_HALF,
                ticker=ticker,
                message=f"股价从高位 {profit_high:.3f} 回落，现价 {close:.3f} 跌破成本+5%（{cost_plus_5pct:.3f}）！"
                        f"利润已大量回吐，建议锁定部分利润",
                price_action="减半仓；继续跌破成本价则全部清仓",
            ))

    # ── R-SR08：250日均线（长线牛熊分界）────────────────────────
    if ma250:
        if close < ma250:
            results.append(RuleResult(
                rule_id="SR-08",
                name="跌破250日均线（熊市信号）",
                severity="critical",
                signal=Signal.SELL if (support_now and close < support_now) else Signal.WATCH,
                ticker=ticker,
                message=f"现价 {close:.3f} 在250日均线 {ma250:.3f} 之下，长线趋势向空",
                price_action="建议减仓，耐心等待重新站上均线",
            ))
        elif close > ma250:
            results.append(RuleResult(
                rule_id="SR-08",
                name="站在250日均线之上（长线安全）",
                severity="minor",
                signal=Signal.SAFE,
                ticker=ticker,
                message=f"现价 {close:.3f} 在250日均线 {ma250:.3f} 之上，长线趋势向上",
                price_action=None,
            ))

    return levels, results
