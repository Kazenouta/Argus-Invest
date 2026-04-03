"""
User weakness profile models.
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class WeaknessItem(BaseModel):
    """弱点条目"""
    id: Optional[str] = None
    weakness_type: Optional[str] = Field(default=None, description="弱点类型，如 'left_side_buy' / 'chase_rising' / 'over_position'")
    title: Optional[str] = Field(default=None, description="弱点标题，如 '下跌趋势补仓'")
    description: Optional[str] = Field(default=None, description="弱点描述")
    occurrence_count: int = Field(default=0, description="历史出现次数")
    avg_loss_ratio: float = Field(default=0.0, description="平均亏损比例（%）")
    max_loss_ratio: float = Field(default=0.0, description="最大亏损比例（%）")
    severity: str = Field(default="medium", description="严重程度：low / medium / high / critical")
    enabled: bool = Field(default=True, description="是否启用")
    confirmed: bool = Field(default=False, description="用户是否已确认")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "weakness_type": "left_side_buy",
                "title": "下跌趋势补仓",
                "description": "在股价跌破60日均线后继续补仓，历史15次操作平均亏损12%",
                "occurrence_count": 15,
                "avg_loss_ratio": -12.0,
                "max_loss_ratio": -35.0,
                "severity": "high",
                "enabled": True,
                "confirmed": True
            }
        }


class WeaknessProfile(BaseModel):
    """弱点画像"""
    version: str = Field(default="v1", description="画像版本")
    last_updated: date = Field(default_factory=date.today)
    items: list[WeaknessItem] = Field(default_factory=list)
    total_count: int = 0
    critical_count: int = 0
