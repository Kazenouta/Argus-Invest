"""
Watchlist models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WatchlistRecord(BaseModel):
    """观察池单条记录"""
    id: Optional[int] = Field(default=None, description="记录ID，新增时可不传")
    stock_code: str = Field(description="股票代码，如 SH600096")
    stock_name: str = Field(description="股票名称")
    industry: Optional[str] = Field(default="", description="主营业务")
    add_reason: Optional[str] = Field(default="", description="加入理由")
    trade_plan: Optional[str] = Field(default="", description="交易计划，含目标买入价等")
    target_buy_price: Optional[float] = Field(default=None, description="目标买入价")
    focus_points: Optional[str] = Field(default="", description="关注点")
    attention_level: str = Field(default="中", description="关注度：高/中/低")
    notes: Optional[str] = Field(default="", description="备注")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)


class WatchlistSignal(BaseModel):
    """买入信号结果"""
    stock_code: str
    stock_name: str
    target_buy_price: Optional[float]
    current_price: float
    distance_to_target_pct: float = Field(description="距目标价百分比，正数表示还有空间，负数表示已跌破")
    signal_type: str = Field(description="信号类型：buy_signal / rule_trigger / near_target")
    signal_label: str = Field(description="简短信号标签：目标买入信号 / 接近目标价 / RSI超跌信号 / 交易计划触发")
    tier: int = Field(description="信号优先级层级：1=最高(红色) / 2=次高(橙色) / 3=一般(蓝色)")
    triggered_rules: list[str] = Field(default_factory=list, description="触发的规则ID列表")
    message: str = Field(description="简化后的信号描述")


class CheckSignalsResponse(BaseModel):
    """检查信号响应"""
    status: str = "ok"
    checked_at: str
    total_watchlist: int
    signals: list[WatchlistSignal]
    messages_created: int
