"""
User weakness profile models (v2 - 深度行为分析版).
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class WeaknessItem(BaseModel):
    """弱点条目（v2 深度分析版）"""
    id: str = Field(description="弱点ID，如 'W001'")
    name: str = Field(description="弱点名称，如 'T+0成瘾'")
    severity: str = Field(default="medium", description="严重程度：minor / moderate / major / critical")
    category: str = Field(default="", description="分类：交易行为 / 仓位管理 / 止损纪律 / 市场风险")
    description: str = Field(default="", description="详细描述")
    data_points: str = Field(default="", description="具体数据证据")
    affected_stocks: str = Field(default="", description="涉及标的")
    monetize_impact: str = Field(default="", description="金钱影响描述")
    related_weakness: str = Field(default="[]", description="关联弱点ID，JSON数组字符串")
    recommended_rules: str = Field(default="[]", description="推荐规则，JSON数组字符串")
    enabled: bool = Field(default=True, description="是否启用")
    confirmed: bool = Field(default=False, description="用户是否已确认")
    created_at: str = Field(default="", description="创建时间ISO字符串")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "W001",
                "name": "T+0成瘾（日内短线刷单）",
                "severity": "critical",
                "category": "交易行为",
                "description": "2年内942个交易日存在同一标的当日买卖...",
                "data_points": "942个交易日有T+0操作 | 东睦股份124天...",
                "affected_stocks": "东睦股份、中矿资源、赤峰黄金",
                "monetize_impact": "估算摩擦损耗超25万元",
                "related_weakness": '["W002", "W003"]',
                "recommended_rules": '["单票单日最多买卖各1次", "月交易上限30笔"]',
                "enabled": True,
                "confirmed": False,
                "created_at": "2026-04-15T00:00:00",
            }
        }


class WeaknessProfile(BaseModel):
    """弱点画像"""
    version: str = Field(default="v2_deep_analysis", description="画像版本")
    last_updated: date = Field(default_factory=date.today)
    items: list[WeaknessItem] = Field(default_factory=list)
    total_count: int = 0
    critical_count: int = 0
