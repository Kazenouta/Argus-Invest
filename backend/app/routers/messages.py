"""
Messages API router.
"""
from fastapi import APIRouter, Query
from app.models.message import MessageListResponse
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/messages", tags=["Messages"])


def _to_native(obj):
    """将 numpy/pandas 类型递归转换为 Python 原生类型"""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(item) for item in obj]
    return obj


@router.get("/", response_model=MessageListResponse)
def list_messages(limit: int = Query(default=100, le=500)):
    """获取消息列表"""
    df = DataStorage.read_messages(limit=limit)
    if df.empty:
        return MessageListResponse(total=0, unread=0, messages=[])
    unread = int((~df["is_read"]).sum()) if "is_read" in df.columns else 0
    messages = [_to_native(row.to_dict()) for _, row in df.iterrows()]
    return MessageListResponse(total=len(messages), unread=unread, messages=messages)


@router.get("/unread-count")
def unread_count():
    """获取未读消息数量（供 Header 角标使用）"""
    return {"unread": DataStorage.unread_count()}


@router.put("/{message_id}/read")
def mark_read(message_id: int):
    """标记单条消息为已读"""
    success = DataStorage.mark_message_read(message_id)
    if not success:
        return {"status": "not_found"}
    return {"status": "ok"}


@router.put("/read-all")
def mark_all_read():
    """全部标记已读"""
    updated = DataStorage.mark_all_messages_read()
    return {"status": "ok", "updated": updated}
