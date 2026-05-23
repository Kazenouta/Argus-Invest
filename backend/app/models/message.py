"""
Message models.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MessageRecord(BaseModel):
    """消息记录"""
    id: Optional[int] = Field(default=None, description="消息ID")
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
    msg_type: str = Field(description="消息类型：buy_signal / rule_trigger")
    content: str = Field(description="消息内容")
    stock_code: Optional[str] = Field(default=None, description="关联股票代码")
    is_read: bool = Field(default=False, description="是否已读")


class MessageListResponse(BaseModel):
    """消息列表响应"""
    total: int
    unread: int
    messages: list[dict]
