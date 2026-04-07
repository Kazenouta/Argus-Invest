"""
Market overview API router.
"""
from fastapi import APIRouter
from app.services.market_overview_service import get_market_overview


router = APIRouter(prefix="/api/market", tags=["Market"])


@router.get("/overview")
def get_overview():
    """获取市场概览：成交额、涨跌停、北向资金、涨跌家数"""
    return get_market_overview()
