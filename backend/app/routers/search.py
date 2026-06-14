"""
跨大V 观点搜索 API。
POST /api/search/articles       搜索
GET  /api/search/stats         索引统计
POST /api/search/reindex       手动重新索引（传入 article specs）
DELETE /api/search/articles     按 file_path 删一条
"""
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException

from app.services import search_service


router = APIRouter(prefix="/api/search", tags=["Search"])


class ArticleSpec(BaseModel):
    author: str
    source: str  # 'wiki' | 'kv'
    title: str
    date: Optional[str] = None
    body: str
    file_path: str
    tags: list[str] = Field(default_factory=list)


class IndexResponse(BaseModel):
    article_id: int
    file_path: str
    already_indexed: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="搜索词")
    authors: list[str] | None = Field(default=None, description="限定作者，如 ['guolei', '斯托伯的天空']")
    date_from: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    date_to: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    source: Optional[str] = Field(default=None, description="'wiki' 或 'kv'")
    k: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    id: int
    author: str
    source: str
    title: str
    date: str
    file_path: str
    distance: float
    similarity: float


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: list[SearchHit]


class StatsResponse(BaseModel):
    total: int
    by_author: list[dict]


@router.post("/articles", response_model=IndexResponse)
def index_one(article: ArticleSpec):
    """索引单篇文章（同 file_path 已存在则跳过）。"""
    try:
        article_id = search_service.index_article(
            author=article.author,
            source=article.source,
            title=article.title,
            date=article.date,
            body=article.body,
            file_path=article.file_path,
            tags=article.tags,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引失败: {e}")
    return IndexResponse(article_id=article_id, file_path=article.file_path)


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """跨作者向量搜索。"""
    try:
        hits = search_service.search_articles(
            req.query,
            authors=req.authors,
            date_from=req.date_from,
            date_to=req.date_to,
            source=req.source,
            k=req.k,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")
    return SearchResponse(
        query=req.query,
        total=len(hits),
        hits=[SearchHit(**h) for h in hits],
    )


@router.get("/stats", response_model=StatsResponse)
def stats():
    """索引统计：总数 + 各作者文章数。"""
    return StatsResponse(**search_service.stats())


@router.delete("/articles")
def delete_one(file_path: str):
    """按 file_path 删一条索引（重新索引前先调这个）。"""
    deleted = search_service.delete_article_by_path(file_path)
    if not deleted:
        raise HTTPException(status_code=404, detail="file_path 不存在")
    return {"deleted": True, "file_path": file_path}
