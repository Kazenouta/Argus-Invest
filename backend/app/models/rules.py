"""
Profit-taking and portfolio rules models.
"""
from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class RuleBase(BaseModel):
    """规则基础模型"""
    rule_id: str = Field(description="规则ID，如 'PT-001'")
    category: str = Field(description="规则分类：position / top_signal / trailing /突发事件")
    title: str = Field(description="规则名称")
    description: str = Field(description="规则描述")
    params: dict[str, Any] = Field(default_factory=dict, description="规则参数")
    risk_level: str = Field(default="medium", description="风险等级：low / medium / high / critical")
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class PositionRule(RuleBase):
    """仓位管理规则"""
    category: str = "position"


class TopSignalRule(RuleBase):
    """顶部信号规则"""
    category: str = "top_signal"


class TrailingRule(RuleBase):
    """移动止盈规则"""
    category: str = "trailing"


class SuddenNewsRule(RuleBase):
    """突发利空规则"""
    category: str = "sudden_news"


class RuleLibrary(BaseModel):
    """规则库"""
    version: str = Field(default="v1")
    last_updated: date = Field(default_factory=date.today)
    rules: list[RuleBase] = Field(default_factory=list)

    @classmethod
    def default_rules(cls) -> "RuleLibrary":
        """生成默认规则库（基于止盈篇四策略）"""
        return cls(
            version="v1",
            rules=[
                # 仓位管理规则
                RuleBase(
                    rule_id="POS-001",
                    category="position",
                    title="单票仓位上限",
                    description="单个标的仓位不超过25%，超过即触发减仓警告",
                    params={"max_position_ratio": 25.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-002",
                    category="position",
                    title="总仓位上限",
                    description="总仓位不超过90%，现金不低于10%",
                    params={"max_total_ratio": 90.0, "min_cash_ratio": 10.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-003",
                    category="position",
                    title="持仓数量控制",
                    description="持仓数量控制在5-8只",
                    params={"min_count": 5, "max_count": 8},
                    risk_level="medium"
                ),
                # 顶部指标规则
                RuleBase(
                    rule_id="TOP-001",
                    category="top_signal",
                    title="历史高位区域",
                    description="股价进入历史高位（前10%分位数），进入高度警惕",
                    params={"percentile": 10.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="TOP-002",
                    category="top_signal",
                    title="成交量异常暴增",
                    description="成交量/换手率暴增2-3倍以上，天量见天价",
                    params={"volume_multiplier": 2.5, "min_multiplier": 2.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="TOP-003",
                    category="top_signal",
                    title="技术指标顶背离",
                    description="RSI/MACD形成顶背离，趋势逆转信号",
                    params={"indicators": ["RSI", "MACD"]},
                    risk_level="medium"
                ),
                # 移动止盈规则
                RuleBase(
                    rule_id="TRL-001",
                    category="trailing",
                    title="成本线保护法",
                    description="股价上涨20%后，止盈线移动至成本价+5%",
                    params={"profit_threshold": 20.0, "trailing_offset": 5.0},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="TRL-002",
                    category="trailing",
                    title="20日均线防守",
                    description="激进版，跌破20日均线减仓一半",
                    params={"ma_type": "MA20", "sell_ratio": 0.5},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="TRL-003",
                    category="trailing",
                    title="60日均线防守",
                    description="稳健版，跌破60日均线清仓",
                    params={"ma_type": "MA60", "sell_ratio": 1.0},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="TRL-004",
                    category="trailing",
                    title="最高点回撤法",
                    description="从最高点回撤15%触发止盈",
                    params={"drawback_ratio": 15.0},
                    risk_level="medium"
                ),
                # 突发利空规则
                RuleBase(
                    rule_id="SUD-001",
                    category="sudden_news",
                    title="突发重大利空",
                    description="持仓股突发重大利空，无条件减半仓",
                    params={"emergency_sell_ratio": 0.5},
                    risk_level="critical"
                ),
            ]
        )
