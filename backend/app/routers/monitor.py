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
from app.services.data_storage import DataStorage


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
    同时保存到本地，重启后仍可读取（刷新页面不丢失）。
    """
    resp = check_portfolio_indicators()
    update_monitor_status(resp)
    # 持久化保存
    DataStorage.save_monitor_check(
        checked_at=resp.checked_at,
        total_positions=resp.total_positions,
        total_events=resp.total_events,
        events_data=[e.model_dump(mode='json') for e in resp.events],
        indicators_data=[i.model_dump(mode='json') for i in resp.indicators],
    )
    return resp


@router.get("/events", response_model=list[MonitorEvent])
def get_events() -> list[MonitorEvent]:
    """
    获取最近一次检查的触发事件列表（从本地存储读取，不重新计算）。
    """
    saved = DataStorage.read_monitor_check()
    if saved is None:
        return []
    events = saved.get('events', [])
    return [MonitorEvent(**e) for e in events]


@router.get("/last-result")
def get_last_check_result():
    """
    获取最近一次检查的完整结果（从本地存储读取，不重新计算）。
    用于刷新页面后直接展示上次结果。
    """
    saved = DataStorage.read_monitor_check()
    if saved is None:
        return {"status": "no_data", "events": [], "indicators": [], "checked_at": None}
    return {
        "status": "ok",
        "checked_at": saved['checked_at'],
        "total_positions": saved['total_positions'],
        "total_events": saved['total_events'],
        "events": saved['events'],
        "indicators": saved['indicators'],
    }
