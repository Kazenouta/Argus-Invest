"""
共享工具函数。
"""
import os
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_minimax_key() -> str:
    """从环境变量或 settings 读取 MiniMax API key，结果缓存避免重复读。"""
    return os.environ.get("MINIMAX_API_KEY", "").strip() or settings.MINIMAX_API_KEY.strip()
