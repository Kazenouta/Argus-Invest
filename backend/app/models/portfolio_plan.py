"""
Stock trading plan models.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class StockPlan(BaseModel):
    """个股交易计划"""
    id: Optional[int] = None
    ticker: str = Field(description="股票代码")
    ticker_name: str = Field(description="股票名称")
    plan_date: date = Field(default_factory=date.today, description="计划日期")
    plan: str = Field(description="交易计划内容")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "SH601899",
                "ticker_name": "紫金矿业",
                "plan_date": "2026-04-03",
                "plan": "若股价跌破30日线，减仓50%；若突破60日线，加仓两手",
            }
        }
