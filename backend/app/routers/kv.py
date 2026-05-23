"""
大V观点 API router.

GET  /api/kv/accounts              — 列出所有已配置的大V账号
GET  /api/kv/{account}/articles    — 获取文章列表
POST /api/kv/{account}/refresh     — 扫描 PDF 并 AI 提炼
GET  /api/kv/{account}/timeline     — 获取关键指标时间序列（供图表用）
"""
from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.kv_service import (
    KV_ACCOUNTS,
    get_articles,
    refresh_and_summarize,
    get_indicator_timeline,
)

router = APIRouter(prefix="/api/kv", tags=["KV"])


# ── 辅助函数 ────────────────────────────────────────────────────────────────

import json as _json


def _parse_list_field(raw: Any) -> list:
    """JSON 字符串 → list，原始为 list 时直接返回。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return _json.loads(raw)
        except Exception:
            return []
    return []


# ── Schema ───────────────────────────────────────────────────────────────────

class AccountInfo(BaseModel):
    name: str
    display_name: str


class IndicatorItem(BaseModel):
    name: str
    value: str
    说明: str = ""


class ArticleItem(BaseModel):
    title: str
    published_date: str
    fetched_date: str
    body_text: str = ""
    source: str
    ai_核心观点: str
    ai_情绪倾向: str
    ai_情绪说明: str = ""
    ai_发布时间: str = ""
    ai_关键指标: list[IndicatorItem] = []
    ai_主要逻辑: str = ""
    ai_政策相关: list[str] = []
    ai_风险提示: str = ""
    ai_相关市场: list[str] = []
    ai_投资启示: str = ""


class RefreshResponse(BaseModel):
    success: bool
    account: str
    total_articles: int
    new_articles: int
    articles: list[ArticleItem]
    message: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/accounts")
def list_accounts():
    return {
        "accounts": [
            {"name": acc.name, "display_name": acc.display_name}
            for acc in KV_ACCOUNTS.values()
        ]
    }


@router.get("/{account}/articles")
def list_articles(account: str, limit: int = 50):
    if account not in KV_ACCOUNTS:
        raise HTTPException(status_code=404, detail=f"未知账号: {account}")
    records = get_articles(account, limit=limit)
    # 反序列化 JSON 字符串字段
    for r in records:
        r["ai_关键指标"] = _parse_list_field(r.get("ai_关键指标"))
        r["ai_政策相关"] = _parse_list_field(r.get("ai_政策相关"))
        r["ai_相关市场"] = _parse_list_field(r.get("ai_相关市场"))
    return {"account": account, "total": len(records), "articles": records}


@router.post("/{account}/refresh", response_model=RefreshResponse)
async def refresh_account(account: str, max_new: int = 20):
    """
    扫描 PDF 目录，通过 AI 提炼关键信息。

    - **account**: 大V内部标识符
    - **max_new**: 最多处理篇数（默认 20，设为 0 则处理全部）
    """
    if account not in KV_ACCOUNTS:
        raise HTTPException(status_code=404, detail=f"未知账号: {account}")

    if max_new == 0:
        max_new = 9999

    result = await refresh_and_summarize(account, max_new=max_new)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "刷新失败"))

    articles = [
        ArticleItem(
            title=r["title"],
            published_date=r["published_date"],
            fetched_date=r["fetched_date"],
            body_text=r.get("body_text", ""),
            source=r["source"],
            ai_核心观点=r["ai_核心观点"],
            ai_情绪倾向=r["ai_情绪倾向"],
            ai_情绪说明=r.get("ai_情绪说明", ""),
            ai_发布时间=r.get("ai_发布时间", ""),
            ai_关键指标=[
                IndicatorItem(**item) if isinstance(item, dict) else item
                for item in _parse_list_field(r.get("ai_关键指标"))
            ],
            ai_主要逻辑=r.get("ai_主要逻辑", ""),
            ai_政策相关=_parse_list_field(r.get("ai_政策相关")),
            ai_风险提示=r.get("ai_风险提示", ""),
            ai_相关市场=_parse_list_field(r.get("ai_相关市场")),
            ai_投资启示=r.get("ai_投资启示", ""),
        )
        for r in result.get("processed", [])
    ]

    return RefreshResponse(
        success=True,
        account=result["account"],
        total_articles=result["total_articles"],
        new_articles=result["new_articles"],
        articles=articles,
        message=result.get("message", ""),
    )


@router.get("/{account}/timeline")
def get_timeline(account: str):
    """
    获取所有文章的关键指标时间序列，供前端 ECharts 折线图使用。
    """
    if account not in KV_ACCOUNTS:
        raise HTTPException(status_code=404, detail=f"未知账号: {account}")
    return {"account": account, "timeline": get_indicator_timeline(account)}


@router.post("/{account}/dedup")
def dedup_articles(account: str):
    """
    去重：每个标题只保留最新一条记录（按 fetched_date 倒序）。
    AI 分析成功的优先于失败的。
    """
    if account not in KV_ACCOUNTS:
        raise HTTPException(status_code=404, detail=f"未知账号: {account}")

    from app.services.kv_service import _load_articles, _save_articles
    import pandas as pd

    df = _load_articles(account)
    if df.empty:
        return {"success": True, "before": 0, "after": 0}

    before = len(df)

    # 构造排序键：AI 成功的排前面，同状态时按 fetched_date 倒序
    is_failed = df["ai_核心观点"].astype(str).str.startswith("（AI分析失败")
    df["_sort_key"] = df["fetched_date"] + ("" if is_failed.any() else "")
    # 成功的记录排在前面（用 '2'），失败的用 '1'，这样字典序比较时成功>失败
    df["_success_priority"] = is_failed.map({True: "1", False: "2"}).astype(str)
    df["_sort_key"] = df["_success_priority"] + "_" + df["fetched_date"].astype(str)

    df_deduped = (
        df
        .sort_values("_sort_key", ascending=False)
        .drop_duplicates(subset=["title"], keep="first")
        .drop(columns=["_sort_key", "_success_priority"])
    )
    after = len(df_deduped)
    _save_articles(account, df_deduped.reset_index(drop=True))
    return {"success": True, "before": before, "after": after, "removed": before - after}
