"""
Persona API Router - 人格列表 + 聊天接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.persona_service import list_personas as _list_personas, get_persona_detail, chat_with_persona


router = APIRouter(prefix="/api/persona", tags=["Persona"])


class ChatRequest(BaseModel):
    """聊天请求体。"""
    skill_id: str
    messages: list[dict[str, str]]  # [{"role": "user"|"assistant", "content": "..."}]


@router.get("/")
def list_personas_endpoint():
    """返回所有可用人格列表。"""
    return _list_personas()


@router.get("/{skill_id}")
def get_persona_endpoint(skill_id: str):
    """返回指定人格的详细信息（含完整 SKILL.md 内容）。"""
    persona = get_persona_detail(skill_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"人格 '{skill_id}' 不存在")
    return persona


@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    与指定人格对话。

    Body:
    {
      "skill_id": "munger-perspective",
      "messages": [{"role": "user", "content": "你怎么看现在的A股？"}]
    }
    """
    if not request.skill_id:
        raise HTTPException(status_code=400, detail="skill_id 不能为空")
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages 不能为空")

    result = await chat_with_persona(request.skill_id, request.messages)
    return result
