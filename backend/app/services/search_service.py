"""
跨大V 观点搜索服务：sqlite-vec 向量索引 + 元数据过滤。

数据流：articles 全文 → embo-01 1536 维向量 → sqlite-vec
查询：用户 query → embo-01 向量 → KNN + 元数据过滤 → 跨作者结果
"""
import sqlite3
import sqlite_vec
from pathlib import Path
from typing import Optional

from app.config import settings
from app.services.embedding_service import (
    embed_texts, pack_embedding, EMBEDDING_DIM,
)


# ── DB 路径（独立于 data/user/，gitignore）──────────────────────────────────
SEARCH_DB_PATH = settings.DATA_DIR / "search.sqlite"


def _connect() -> sqlite3.Connection:
    """打开数据库 + 加载 vec0 扩展。"""
    SEARCH_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SEARCH_DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """创建 articles / vec_articles / article_tags 表（首次或清空后）。"""
    with _connect() as conn:
        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                author      TEXT NOT NULL,
                source      TEXT NOT NULL,
                title       TEXT,
                date        TEXT,
                body        TEXT,
                file_path   TEXT UNIQUE,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_articles USING vec0(
                article_id  INTEGER PRIMARY KEY,
                embedding   float[{EMBEDDING_DIM}]
            );
            CREATE TABLE IF NOT EXISTS article_tags (
                article_id  INTEGER,
                tag         TEXT,
                PRIMARY KEY (article_id, tag)
            );
            CREATE INDEX IF NOT EXISTS idx_articles_author ON articles(author);
            CREATE INDEX IF NOT EXISTS idx_articles_date   ON articles(date);
            CREATE INDEX IF NOT EXISTS idx_article_tags    ON article_tags(tag);
        """)
        conn.commit()


# ── 索引接口 ────────────────────────────────────────────────────────────────

def index_article(
    *,
    author: str,
    source: str,
    title: str,
    date: Optional[str],
    body: str,
    file_path: str,
    tags: list[str] | None = None,
) -> int:
    """索引单篇文章（idempotent：同 file_path 已存在则跳过）。返回 article_id。"""
    init_db()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM articles WHERE file_path = ?", (file_path,)
        ).fetchone()
        if existing:
            return int(existing["id"])

        # 入库侧 embedding（type='db'）
        vec = embed_texts([body[:8000]], kind="db")[0]

        cur = conn.execute(
            "INSERT INTO articles (author, source, title, date, body, file_path) VALUES (?,?,?,?,?,?)",
            (author, source, title, date, body, file_path),
        )
        article_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO vec_articles (article_id, embedding) VALUES (?, ?)",
            (article_id, pack_embedding(vec)),
        )
        for tag in (tags or []):
            conn.execute(
                "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
                (article_id, tag),
            )
        conn.commit()
        return article_id


def delete_article_by_path(file_path: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT id FROM articles WHERE file_path = ?", (file_path,)).fetchone()
        if not row:
            return False
        article_id = int(row["id"])
        conn.execute("DELETE FROM vec_articles WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.commit()
        return True


def stats() -> dict:
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM articles").fetchone()["n"]
        by_author = conn.execute(
            "SELECT author, COUNT(*) AS n FROM articles GROUP BY author"
        ).fetchall()
    return {"total": n, "by_author": [dict(r) for r in by_author]}


# ── 搜索接口 ────────────────────────────────────────────────────────────────

def search_articles(
    query: str,
    *,
    authors: list[str] | None = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    k: int = 10,
) -> list[dict]:
    """
    跨作者向量搜索。
    - query: 用户搜索词
    - authors: 限定作者列表（None = 全部）
    - date_from / date_to: 日期范围 YYYY-MM-DD
    - source: 'wiki' 或 'kv'
    - k: 返回前 k 条
    """
    init_db()
    if not query.strip():
        return []

    # 查询侧 embedding（type='query'，与入库侧向量空间略不同）
    qvec = embed_texts([query], kind="query")[0]
    qvec_blob = pack_embedding(qvec)

    # KNN + 元数据过滤
    # sqlite-vec 特殊语法：必须用 `AND k = ?` 在 WHERE 子句里
    # 过取 KNN 数量（k*3），再用 SQL 过滤 author/date，最后截断到 k
    fetch_k = int(k * 3)

    # 动态拼过滤条件（避免 `?` 占位符重复导致参数计数错乱）
    conditions = ["v.embedding MATCH ?", "k = ?"]
    params: list = [qvec_blob, fetch_k]
    if authors:
        placeholders = ",".join("?" for _ in authors)
        conditions.append(f"a.author IN ({placeholders})")
        params.extend(authors)
    if date_from:
        conditions.append("a.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("a.date <= ?")
        params.append(date_to)
    if source:
        conditions.append("a.source = ?")
        params.append(source)

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT a.id, a.author, a.source, a.title, a.date, a.file_path,
               v.distance
        FROM vec_articles v
        JOIN articles a ON a.id = v.article_id
        WHERE {where_clause}
        ORDER BY v.distance
    """

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()

    # 截断到 k，并把 distance 转成相似度（0~1，越大越相似）
    results = []
    for r in rows[:k]:
        results.append({
            "id": int(r["id"]),
            "author": r["author"],
            "source": r["source"],
            "title": r["title"] or "",
            "date": r["date"] or "",
            "file_path": r["file_path"],
            "distance": float(r["distance"]),
            "similarity": max(0.0, 1.0 - float(r["distance"]) / 2.0),  # 余弦 → 简单映射
        })
    return results
