"""
Portfolio data models.
"""
import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PortfolioRecord(BaseModel):
    """持仓记录"""
    id: Optional[int] = None
    ticker: str = Field(description="股票代码，如 'SZ000001'")
    name: str = Field(description="股票名称")
    quantity: int = Field(description="持股数量")
    cost_price: float = Field(description="成本价")
    current_price: float = Field(description="当前价")
    market_value: float = Field(description="市值")
    float_profit: float = Field(description="浮盈/亏金额")
    float_profit_ratio: float = Field(description="浮盈/亏比例（%）")
    position_ratio: float = Field(description="仓位占比（%）")
    date: datetime.date = Field(default_factory=datetime.date.today, description="记录日期")

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "SZ000001",
                "name": "平安银行",
                "quantity": 1000,
                "cost_price": 12.50,
                "current_price": 13.20,
                "market_value": 13200.0,
                "float_profit": 700.0,
                "float_profit_ratio": 5.60,
                "position_ratio": 22.0,
                "date": "2026-03-31"
            }
        }


class PortfolioSnapshot(BaseModel):
    """持仓快照汇总"""
    date: datetime.date
    total_market_value: float
    total_cost: float
    total_float_profit: float
    float_profit_ratio: float
    cash_ratio: float
    position_ratio: float
    position_count: int
    positions: list[PortfolioRecord]
