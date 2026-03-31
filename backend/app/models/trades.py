"""
Trade / adjustment records models.
"""
import datetime as dt
from typing import Optional
from pydantic import BaseModel, Field


class TradeRecord(BaseModel):
    """调仓记录"""
    id: Optional[int] = None
    date: dt.date = Field(description="交易日期")
    ticker: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    action: str = Field(description="操作类型：buy / sell / adjust")
    quantity: int = Field(description="交易数量")
    price: float = Field(description="成交价格")
    amount: float = Field(description="成交金额")
    reason: str = Field(description="调仓逻辑（必填）", default="")
    thinking_id: Optional[int] = Field(default=None, description="关联的盘中思考ID")
    created_at: dt.datetime = Field(default_factory=dt.datetime.now)
    updated_at: Optional[dt.datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2026-03-31",
                "ticker": "SZ000001",
                "name": "平安银行",
                "action": "buy",
                "quantity": 500,
                "price": 13.20,
                "amount": 6600.0,
                "reason": "5日线上穿10日线，成交量放大，符合建仓条件",
                "thinking_id": None
            }
        }


class TradeWithPosition(BaseModel):
    """带有持仓前后状态的调仓记录"""
    trade: TradeRecord
    position_before: float = Field(description="操作前持仓（股）")
    position_after: float = Field(description="操作后持仓（股）")
    cost_before: Optional[float] = Field(default=None, description="操作前成本")
    cost_after: Optional[float] = Field(default=None, description="操作后成本")
