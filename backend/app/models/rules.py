"""
Profit-taking and portfolio rules models (v2 - 融合弱点画像版).
"""
from datetime import date, datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class RuleBase(BaseModel):
    """规则基础模型"""
    rule_id: str = Field(description="规则ID，如 'POS-001'")
    category: str = Field(description="规则分类：position / top_signal / trailing / sudden_news / trading_behavior")
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


class TradingBehaviorRule(RuleBase):
    """交易行为约束规则"""
    category: str = "trading_behavior"


class RuleLibrary(BaseModel):
    """规则库"""
    version: str = Field(default="v2_weakness")
    last_updated: date = Field(default_factory=date.today)
    rules: list[RuleBase] = Field(default_factory=list)

    @classmethod
    def default_rules(cls) -> "RuleLibrary":
        """生成默认规则库（融合弱点画像 + 止盈四策略 + 行为约束）"""
        return cls(
            version="v2_weakness",
            rules=[
                # ═══════════════════════════════════════════════
                # 仓位管理规则
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="POS-001",
                    category="position",
                    title="单票仓位上限",
                    description="单个标的仓位不超过20%（基于弱点W010：单票仓位严重失控），超过即触发减仓警告",
                    params={"max_position_ratio": 20.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-002",
                    category="position",
                    title="总仓位上限",
                    description="总仓位不超过85%，现金不低于15%",
                    params={"max_total_ratio": 85.0, "min_cash_ratio": 15.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-003",
                    category="position",
                    title="持仓数量控制",
                    description="持仓数量控制在5-8只（避免过度分散和过度集中）",
                    params={"min_count": 5, "max_count": 8},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="POS-004",
                    category="position",
                    title="超限自动锁定",
                    description="仓位超限时自动锁定该标的操作权限，需填写减仓计划后方可解锁",
                    params={"lock_on_violation": True},
                    risk_level="critical"
                ),

                # ═══════════════════════════════════════════════
                # 交易行为约束规则（W001 T+0成瘾 / W002 卖出后悔）
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="TRD-001",
                    category="trading_behavior",
                    title="月交易上限",
                    description="月交易笔数上限30笔，超出需填写3条操作理由（基于弱点W001：月均294笔，严重超高频）",
                    params={"max_monthly_trades": 30, "require_reason_over_limit": True},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="TRD-002",
                    category="trading_behavior",
                    title="单票单日交易上限",
                    description="同一标的单日最多买卖各1次（2个合约），同一标的月交易上限10次（基于弱点W001：东睦股份单票交易969次）",
                    params={"max_daily_trades_per_stock": 2, "max_monthly_per_stock": 10},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="TRD-003",
                    category="trading_behavior",
                    title="禁止东睦/中矿尾盘交易",
                    description="东睦股份、中矿资源在收盘前30分钟内禁止新建仓位（这两只上瘾最严重）",
                    params={"restricted_stocks": ["东睦股份", "中矿资源"], "restricted_time_minutes_before_close": 30},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="TRD-004",
                    category="trading_behavior",
                    title="卖出后悔禁止",
                    description="卖出后5个交易日内禁止买回同一标的，违者需填写强制理由（基于弱点W002：1866次卖出后悔）",
                    params={"sell_buyback_cooldown_days": 5, "require_reason_on_violation": True},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="TRD-005",
                    category="trading_behavior",
                    title="ETF持有期下限",
                    description="ETF最少持有5个交易日才能操作（基于弱点W004：ETF高频亏损）",
                    params={"min_etf_hold_days": 5, "max_etf_monthly_trades": 10},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="TRD-006",
                    category="trading_behavior",
                    title="大V追随仓位上限",
                    description="追随大V买的标的，单笔仓位上限5%，且需在5个交易日内复审（基于弱点W008：大V追随型交易）",
                    params={"max_kol_position_ratio": 5.0, "review_within_days": 5},
                    risk_level="major"
                ),
                RuleBase(
                    rule_id="TRD-007",
                    category="trading_behavior",
                    title="买入必须写理由",
                    description="买入任何标的前必须写出自己的3条理由，不允许只写「抄作业」（基于弱点W008）",
                    params={"min_reason_length": 20, "reject_if_copy": True},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="TRD-008",
                    category="trading_behavior",
                    title="持仓亏损时禁止T+0",
                    description="持仓整体亏损超过5%时禁止做任何形式的T（含卖出后当天买回）（基于弱点W009：伪T+0）",
                    params={"max_loss_for_tzero": 5.0, "ban_tzero_on_violation": True},
                    risk_level="major"
                ),

                # ═══════════════════════════════════════════════
                # 止盈止损规则（W005 高位加仓 / W006 止损纪律差）
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="STP-001",
                    category="trailing",
                    title="成本线保护法",
                    description="股价上涨20%后，止盈线移动至成本价+5%（基于弱点W006：盈利变亏损）",
                    params={"profit_threshold": 20.0, "trailing_offset": 5.0},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="STP-002",
                    category="trailing",
                    title="亏损8%强制减仓",
                    description="亏损8%时强制减仓50%，不讨论、不等待（基于弱点W006：长期持有大亏）",
                    params={"loss_threshold_for_half": 8.0, "sell_ratio": 0.5, "force_execution": True},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="STP-003",
                    category="trailing",
                    title="亏损15%强制清仓",
                    description="亏损15%时无条件清仓（基于弱点W006：长期持亏）",
                    params={"loss_threshold_for_exit": 15.0, "sell_ratio": 1.0, "force_execution": True},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="STP-004",
                    category="trailing",
                    title="盈利超50%强制止盈",
                    description="盈利超过50%后强制移动止盈线至成本价+10%，只下移不上移",
                    params={"profit_threshold_for_forced": 50.0, "forced_trailing_profit": 10.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="STP-005",
                    category="trailing",
                    title="连续补仓后下跌熔断",
                    description="连续3次补仓后仍下跌，继续持有需写500字检讨（基于弱点W003：越跌越买143次）",
                    params={"max_consecutive_dip_buys": 3, "require_essay_on_violation": True},
                    risk_level="critical"
                ),

                # ═══════════════════════════════════════════════
                # 仓位管理——加仓规则（W003 越跌越买 / W005 高位加仓）
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="POS-ADD-001",
                    category="position",
                    title="禁止下跌趋势加仓",
                    description="禁止在股价跌破20日线后加仓，视为趋势破坏信号（基于弱点W003：越跌越买143次）",
                    params={"banned_ma": "MA20", "banned_action": "add_position"},
                    risk_level="critical"
                ),
                RuleBase(
                    rule_id="POS-ADD-002",
                    category="position",
                    title="禁止连续下跌中加仓",
                    description="禁止在连续3日下跌中加仓（基于弱点W003）",
                    params={"consecutive_down_days": 3, "banned_action": "add_position"},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-ADD-003",
                    category="position",
                    title="单票日加仓上限",
                    description="单票单日最多加仓1次，月加仓次数上限2次（基于弱点W003：单票高频加仓）",
                    params={"max_daily_add_per_stock": 1, "max_monthly_add_per_stock": 2},
                    risk_level="major"
                ),
                RuleBase(
                    rule_id="POS-ADD-004",
                    category="position",
                    title="盈利超20%禁止加仓",
                    description="盈利超过20%后禁止加仓（改为观察是否需要减仓）（基于弱点W005：盈利后高位加仓）",
                    params={"profit_threshold_ban_add": 20.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="POS-ADD-005",
                    category="position",
                    title="历史新高禁止加仓",
                    description="股价创历史新高后禁止加仓，改为减仓窗口期（基于弱点W005：高位加仓）",
                    params={"new_high_ban": True},
                    risk_level="major"
                ),

                # ═══════════════════════════════════════════════
                # 港股规则（W007 港股高风险）
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="HK-001",
                    category="trading_behavior",
                    title="港股单笔仓位上限",
                    description="港股单笔仓位上限10%（基于弱点W007：港股天齐锂业超仓位106%）",
                    params={"max_hk_position_ratio": 10.0},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="HK-002",
                    category="trading_behavior",
                    title="港股禁止T+0",
                    description="港股禁止当日买卖（基于弱点W007）",
                    params={"hk_ban_tzero": True},
                    risk_level="high"
                ),
                RuleBase(
                    rule_id="HK-003",
                    category="trading_behavior",
                    title="港股加仓冷却期",
                    description="港股加仓间隔至少5个交易日（基于弱点W007：港股流动性风险）",
                    params={"hk_add_cooldown_days": 5},
                    risk_level="medium"
                ),

                # ═══════════════════════════════════════════════
                # 顶部指标规则
                # ═══════════════════════════════════════════════
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

                # ═══════════════════════════════════════════════
                # 移动止盈规则
                # ═══════════════════════════════════════════════
                RuleBase(
                    rule_id="TRL-001",
                    category="trailing",
                    title="20日均线防守",
                    description="激进版，跌破20日均线减仓一半",
                    params={"ma_type": "MA20", "sell_ratio": 0.5},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="TRL-002",
                    category="trailing",
                    title="60日均线防守",
                    description="稳健版，跌破60日均线清仓",
                    params={"ma_type": "MA60", "sell_ratio": 1.0},
                    risk_level="medium"
                ),
                RuleBase(
                    rule_id="TRL-003",
                    category="trailing",
                    title="最高点回撤法",
                    description="从最高点回撤15%触发止盈",
                    params={"drawback_ratio": 15.0},
                    risk_level="medium"
                ),

                # ═══════════════════════════════════════════════
                # 突发利空规则
                # ═══════════════════════════════════════════════
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
