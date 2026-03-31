"""
Intraday thinking record models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ThinkingRecord(BaseModel):
    """盘中思考记录"""
    id: Optional[int] = None
    thinking_time: datetime = Field(description="思考时间")
    ticker: Optional[str] = Field(default=None, description="关联股票代码（可选）")
    ticker_name: Optional[str] = Field(default=None, description="股票名称")
    content: str = Field(description="思考内容")
    action: Optional[str] = Field(default=None, description="关联操作，如 '买入XXX'")
    source: str = Field(default="manual", description="来源：manual / voice")
    trade_id: Optional[int] = Field(default=None, description="关联调仓记录ID")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "thinking_time": "2026-03-31T10:30:00",
                "ticker": "SZ000001",
                "ticker_name": "平安银行",
                "content": "5日线上穿10日线，成交量放大，大盘氛围偏多，可以考虑建仓",
                "action": "买入平安银行500股",
                "source": "manual",
                "trade_id": None
            }
        }
