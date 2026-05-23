"""
日线行情数据接口。

GET  /daily-bar/?ticker=X&start=Y&end=Z&limit=N   — 查询日线
POST /daily-bar/sync        — 手动触发全量同步
GET  /daily-bar/coverage    — 各年份数据覆盖情况
GET  /daily-bar/latest-date — 本地数据最新交易日
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.daily_bar_service import (
    sync_full,
    get_daily_bars,
    get_latest_trading_date,
    get_coverage,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/daily-bar", tags=["日线行情"])


class SyncResponse(BaseModel):
    status: str
    started_at: str
    finished_at: str
    results: dict


class CoverageResponse(BaseModel):
    coverage: dict
    latest_trading_date: Optional[str]


class DailyBarsQueryResponse(BaseModel):
    ticker: str
    count: int
    start_date: Optional[str]
    end_date: Optional[str]
    data: list


@router.get("/coverage", response_model=CoverageResponse)
def coverage() -> CoverageResponse:
    """返回各年份数据覆盖情况。"""
    return CoverageResponse(
        coverage=get_coverage(),
        latest_trading_date=get_latest_trading_date(),
    )


@router.get("/latest-date")
def latest_date() -> dict:
    """返回本地数据中最近的一个交易日。"""
    latest = get_latest_trading_date()
    return {"latest_date": latest}


@router.get("/", response_model=DailyBarsQueryResponse)
def query_daily_bars(
    ticker: str = Query(..., description="股票代码，如 000001、600519"),
    start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(500, description="最多返回条数"),
) -> DailyBarsQueryResponse:
    """
    查询指定股票的日线数据。
    数据从本地 Parquet 存储中读取，无需网络请求。
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker 不能为空")

    df = get_daily_bars(ticker=ticker.strip(), start_date=start, end_date=end, limit=limit)
    if df.empty:
        return DailyBarsQueryResponse(ticker=ticker, count=0, start_date=start, end_date=end, data=[])

    return DailyBarsQueryResponse(
        ticker=ticker,
        count=len(df),
        start_date=str(df["date"].min()) if "date" in df.columns else start,
        end_date=str(df["date"].max()) if "date" in df.columns else end,
        data=df.to_dict(orient="records"),
    )


@router.post("/sync", response_model=SyncResponse)
def sync_daily_bars(
    start_year: int = Query(2020, description="同步起始年份"),
    end_year: Optional[int] = Query(None, description="同步结束年份，默认为今年"),
) -> SyncResponse:
    """
    手动触发全量日线数据同步。
    拉取从 start_year 到 end_year 的所有A股日线数据。
    注意：首次全量同步耗时较长（预计30~60分钟），建议在后台运行。
    """
    today = date.today()
    if end_year is None:
        end_year = today.year
    end_year = min(end_year, today.year)
    if start_year > end_year:
        raise HTTPException(status_code=400, detail="start_year 不能大于 end_year")

    started_at = datetime.now().isoformat()
    try:
        results = sync_full(start_year=start_year, end_year=end_year)
    except Exception as e:
        logger.exception("[DailyBar] 同步失败")
        raise HTTPException(status_code=500, detail=f"同步失败: {e}")

    finished_at = datetime.now().isoformat()
    return SyncResponse(
        status="ok",
        started_at=started_at,
        finished_at=finished_at,
        results=results,
    )
