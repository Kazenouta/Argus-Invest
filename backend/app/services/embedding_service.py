"""
Embedding 服务：包装 MiniMax embo-01 端点。
"""
import struct
from typing import Literal

import httpx

from app.utils import get_minimax_key

EMBEDDING_MODEL = "embo-01"
EMBEDDING_DIM = 1536
EMBEDDING_URL = "https://api.minimaxi.com/v1/embeddings"


def _pack(vec: list[float]) -> bytes:
    """1536 维 float 列表 → sqlite-vec 需要的 32 位小端字节流。"""
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def embed_texts(texts: list[str], *, kind: Literal["db", "query"] = "db") -> list[list[float]]:
    """
    调 MiniMax embo-01 拿向量。
    - kind='db'：入库用，文档侧 embedding
    - kind='query'：搜索用，查询侧 embedding（两端用不同算法，向量空间略不同）
    """
    if not texts:
        return []
    key = get_minimax_key()
    if not key:
        raise RuntimeError("MINIMAX_API_KEY 未配置")

    r = httpx.post(
        EMBEDDING_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": EMBEDDING_MODEL, "texts": texts, "type": kind},
        timeout=60.0,
    )
    r.raise_for_status()
    data = r.json()
    vectors = data.get("vectors") or []
    if not vectors:
        raise RuntimeError(f"embedding 返回空: {data}")
    if len(vectors[0]) != EMBEDDING_DIM:
        raise RuntimeError(f"embedding 维度异常: {len(vectors[0])}, 期望 {EMBEDDING_DIM}")
    return vectors


def pack_embedding(vec: list[float]) -> bytes:
    """对外暴露的 pack 工具，供 search_service 写库用。"""
    return _pack(vec)
