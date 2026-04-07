"""
Indicator monitor API router.
"""
from fastapi import APIRouter
from app.models.monitor import MonitorCheckResponse, MonitorStatus, MonitorEvent
from app.services.monitor_service import (
    check_portfolio_indicators,
    get_monitor_status,
    update_monitor_status,
    DEFAULT_RULES,
)


router = APIRouter(prefix="/api/monitor", tags=["Monitor"])


@router.get("/status")
def get_status() -> MonitorStatus:
    """获取监控状态（上次检查时间、事件数等）"""
    return get_monitor_status()


@router.get("/rules")
def get_rules():
    """获取当前监控规则列表"""
    return {
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "indicator": r.indicator,
                "operator": r.operator,
                "threshold": r.threshold,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in DEFAULT_RULES
        ]
    }


@router.post("/check", response_model=MonitorCheckResponse)
def check_positions() -> MonitorCheckResponse:
    """
    手动触发持仓指标检查。
    读取持仓 → 获取行情数据 → 计算指标 → 匹配规则 → 返回结果。
    """
    resp = check_portfolio_indicators()
    update_monitor_status(resp)
    return resp


@router.get("/events", response_model=list[MonitorEvent])
def get_events() -> list[MonitorEvent]:
    """
    获取最近一次检查的触发事件列表。
    （由 check_positions 的结果驱动，需要先调用 check 才会有数据）
    """
    status = get_monitor_status()
    if not status.last_checked_at:
        return []
    # 重新检查获取最新事件
    resp = check_portfolio_indicators()
    return resp.events
