"""
Persona Service - 扫描 ~/.hermes/skills/ 目录，加载人人格定义，对话生成。
"""
import os
import re
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import settings


# ── 配置 ─────────────────────────────────────────────────────────────────────

_MINIMAX_KEY: Optional[str] = None
_BASE_URL = "https://api.minimaxi.com/anthropic"
_MAX_RETRIES = 10
SKILLS_DIR = Path.home() / ".hermes" / "skills"


def _get_minimax_key() -> str:
    global _MINIMAX_KEY
    if _MINIMAX_KEY:
        return _MINIMAX_KEY
    key = os.environ.get("MINIMAX_API_KEY", "").strip() or settings.MINIMAX_API_KEY.strip()
    if key:
        _MINIMAX_KEY = key
    return _MINIMAX_KEY or ""


# ── 人格列表 ─────────────────────────────────────────────────────────────────

def list_personas() -> list[dict[str, Any]]:
    """扫描 ~/.hermes/skills/ 目录，返回所有人格的简要信息列表。"""
    personas = []
    if not SKILLS_DIR.exists():
        return personas

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        description = metadata.get("description", "")
        name = metadata.get("name", skill_dir.name)

        # 过滤：只保留有 description 的人格
        if not description:
            continue

        personas.append({
            "id": skill_dir.name,
            "name": name,
            "description": description,
        })

    return personas


def get_persona_detail(skill_id: str) -> Optional[dict[str, Any]]:
    """返回指定人格的完整 SKILL.md 内容，用于构造 system prompt。"""
    skill_dir = SKILLS_DIR / skill_id
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    content = skill_md.read_text(encoding="utf-8")
    metadata = _parse_frontmatter(content)

    return {
        "id": skill_id,
        "name": metadata.get("name", skill_id),
        "description": metadata.get("description", ""),
        "content": content,
        "metadata": metadata,
    }


# ── 对话生成 ─────────────────────────────────────────────────────────────────

async def chat_with_persona(
    skill_id: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """
    使用 MiniMax M2.7 API，以指定人格的 SKILL.md 为 system prompt 生成回复。

    messages 格式: [{"role": "user", "content": "..."}, ...]
    返回: {"reply": "..."} 或 {"error": "..."}
    """
    api_key = _get_minimax_key()
    if not api_key:
        return {"error": "未配置 MINIMAX_API_KEY，无法生成回复。请在 backend/.env 中设置。"}

    persona = get_persona_detail(skill_id)
    if not persona:
        return {"error": f"人格 '{skill_id}' 不存在"}

    skill_content = persona["content"]
    system_prompt = (
        f"你正在扮演 '{persona['name']}'。\n"
        f"以下是这个人格的完整定义（SKILL.md）：\n\n"
        f"{skill_content}\n\n"
        f"【重要】严格按照上述人格定义的方式回答。用他的心智模型分析问题，"
        f"用他的语气和表达风格输出。\n"
    )

    payload = {
        "model": "MiniMax-M2.7",
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        "max_tokens": 2000,
        "temperature": 0.7,
    }

    last_error = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
                resp = await client.post(
                    f"{_BASE_URL}/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                    json=payload,
                )

            if resp.status_code != 200:
                last_error = f"M2.7 API 返回 {resp.status_code}: {resp.text[:300]}"
                if resp.status_code in (500, 502, 503, 529) or "1033" in resp.text or "overloaded" in resp.text:
                    await asyncio.sleep(5 * attempt)
                    continue
                return {"error": last_error}

            result_data = resp.json()
            content_list = result_data.get("content", [])
            reply_text = ""
            if isinstance(content_list, list):
                for c in content_list:
                    if c.get("type") == "text":
                        reply_text = c["text"]
                        break

            if reply_text:
                return {"reply": reply_text}
            last_error = "M2.7 返回内容为空"
            return {"error": last_error}

        except Exception as e:
            last_error = f"请求异常：{str(e)}"
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(2 * attempt)
                continue
            return {"error": last_error}

    return {"error": f"M2.7 服务不可用（已重试{_MAX_RETRIES}次）：{last_error}"}


# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> dict[str, Any]:
    """解析 YAML frontmatter，返回 metadata dict。"""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    yaml_block = match.group(1)
    try:
        import yaml
        return yaml.safe_load(yaml_block) or {}
    except Exception:
        return {}
