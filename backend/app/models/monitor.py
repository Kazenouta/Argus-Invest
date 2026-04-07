"""
Indicator monitoring data models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class IndicatorType(str):
    """指标类型枚举（用字符串代替 Enum，保持简单）"""
    PRICE_CHANGE = "price_change"        # 涨跌幅超限
    VOLUME_SPIKE = "volume_spike"         # 成交量突增
    RSI_OVERBOUGHT = "rsi_overbought"     # RSI 超买
    RSI_OVERSOLD = "rsi_oversold"        # RSI 超卖
    MACD_CROSS = "macd_cross"            # MACD 金叉/死叉
    BOLL_BREAK_UPPER = "boll_break_upper" # 布林带上轨突破
    BOLL_BREAK_LOWER = "boll_break_lower" # 布林带下轨突破
    MA_ALIGNMENT_BULL = "ma_bull"         # 均线多头排列
    MA_ALIGNMENT_BEAR = "ma_bear"        # 均线空头排列
    PRICE_HISTORY_HIGH = "price_history_high"  # 价格创历史新高
    PRICE_HISTORY_LOW = "price_history_low"   # 价格创历史新低


class MonitorRule(BaseModel):
    """监控规则定义"""
    rule_id: str = Field(description="规则ID")
    name: str = Field(description="规则名称，如 'RSI超卖提醒'")
    indicator: str = Field(description="指标类型")
    operator: str = Field(description="比较操作符：>, <, >=, <=, cross_up, cross_down")
    threshold: float = Field(description="阈值")
    enabled: bool = Field(default=True)
    description: str = Field(default="", description="规则描述")


class IndicatorValue(BaseModel):
    """单个标的的指标值"""
    ticker: str
    name: str
    date: str
    close: float = Field(description="收盘价")
    change_pct: float = Field(description="涨跌幅%")
    volume_ratio: float = Field(description="量比（今日量/5日均量）")
    rsi6: Optional[float] = Field(default=None, description="RSI(6)")
    rsi14: Optional[float] = Field(default=None, description="RSI(14)")
    macd: Optional[float] = Field(default=None, description="MACD 值")
    macd_signal: Optional[float] = Field(default=None, description="MACD Signal")
    macd_hist: Optional[float] = Field(default=None, description="MACD 柱")
    boll_upper: Optional[float] = Field(default=None, description="布林带上轨")
    boll_middle: Optional[float] = Field(default=None, description="布林带中轨")
    boll_lower: Optional[float] = Field(default=None, description="布林带下轨")
    ma5: Optional[float] = Field(default=None, description="5日均线")
    ma20: Optional[float] = Field(default=None, description="20日均线")
    ma60: Optional[float] = Field(default=None, description="60日均线")


class MonitorEvent(BaseModel):
    """触发的事件"""
    ticker: str
    name: str
    indicator: str = Field(description="指标类型")
    signal: str = Field(description="信号方向：买入, 卖出, 警告, 关注")
    value: float = Field(description="触发时的指标值")
    threshold_desc: str = Field(description="阈值描述，如 'RSI(14) < 30'")
    message: str = Field(description="展示给用户的描述信息")
    triggered_at: datetime = Field(default_factory=datetime.now)


class MonitorCheckResponse(BaseModel):
    """检查持仓后的返回"""
    status: str = "ok"
    checked_at: datetime = Field(default_factory=datetime.now)
    total_positions: int = Field(description="持仓标的数量")
    total_events: int = Field(description="触发的事件数量")
    events: list[MonitorEvent] = Field(default_factory=list, description="触发的事件列表")
    indicators: list[IndicatorValue] = Field(default_factory=list, description="所有标的的指标值")


class MonitorStatus(BaseModel):
    """监控状态"""
    last_checked_at: Optional[datetime] = None
    last_event_count: int = 0
    last_position_count: int = 0
