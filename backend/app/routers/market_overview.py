"""Market overview API router."""
from fastapi import APIRouter
from datetime import datetime
from app.services.market_overview_service import get_market_overview
from app.services.market_ai_service import synthesize_market_overview
from app.services.data_storage import DataStorage


router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/overview")
def get_overview():
    """获取市场概览（传统数据源）：成交额、涨跌停、北向资金、涨跌家数"""
    result = get_market_overview()
    # 有实际数据再缓存（避免失败时覆盖已有缓存）
    if result and result.get("market_volume", {}).get("amount"):
        DataStorage.save_market_overview_cache(result)
    return result


@router.get("/overview/cache")
def get_overview_cache():
    """获取缓存的市场概览，无缓存返回 None"""
    return DataStorage.load_market_overview_cache()


@router.get("/ai-overview")
async def get_ai_overview():
    """
    AI 搜索市场概览：
    1. 大盘今日总成交额 + 趋势描述 + 历史分位数
    2. 今日涨跌停个数 + 变化描述
    3. 今日融资余额 + 变化描述
    4. 散户情绪变化描述
    5. 近期资金流入最多行业 Top3
    6. 近期资金流出最多行业 Top3
    """
    result = await synthesize_market_overview()
    # 合成失败或全为"未知"时不覆盖已有缓存
    if result and not result.get("error"):
        ai_val = result.get("成交额", {}).get("value", "")
        if ai_val and ai_val != "未知":
            DataStorage.save_market_ai_cache(result, datetime.now().isoformat())
    return result


@router.get("/ai-overview/cache")
def get_ai_overview_cache():
    """获取缓存的 AI 市场概览，无缓存返回 None"""
    return DataStorage.load_market_ai_cache()
