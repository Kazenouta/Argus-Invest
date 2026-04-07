"""
Market overview API router.
"""
from fastapi import APIRouter, BackgroundTasks
from app.services.market_overview_service import get_market_overview
from app.services.market_ai_service import synthesize_market_overview


router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/overview")
def get_overview():
    """获取市场概览（传统数据源）：成交额、涨跌停、北向资金、涨跌家数"""
    return get_market_overview()


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
    return result
