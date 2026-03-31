"""
Portfolio API router.
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd

from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


@router.get("/", response_model=list[PortfolioRecord])
def list_portfolio(as_of_date: Optional[date] = Query(None)):
    """获取持仓列表（可选指定日期）"""
    df = DataStorage.read_portfolio(as_of_date)
    return df.to_dict(orient="records")


@router.post("/")
def upload_portfolio(records: list[PortfolioRecord]):
    """上传持仓数据（覆盖）"""
    if not records:
        raise HTTPException(status_code=400, detail="持仓记录不能为空")
    df = pd.DataFrame([r.model_dump() for r in records])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    DataStorage.write_portfolio(df)
    return {"status": "ok", "count": len(records)}


@router.get("/snapshot", response_model=PortfolioSnapshot)
def portfolio_snapshot(as_of_date: Optional[date] = Query(None)):
    """获取持仓快照汇总"""
    df = DataStorage.read_portfolio(as_of_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="暂无持仓数据")
    total_mv = df["market_value"].sum()
    total_cost = (df["quantity"] * df["cost_price"]).sum()
    total_float = df["float_profit"].sum()
    float_ratio = (total_float / total_cost * 100) if total_cost else 0
    cash_ratio = 100 - df["position_ratio"].sum()
    return PortfolioSnapshot(
        date=as_of_date or date.today(),
        total_market_value=total_mv,
        total_cost=total_cost,
        total_float_profit=total_float,
        float_profit_ratio=round(float_ratio, 2),
        cash_ratio=round(cash_ratio, 2),
        position_ratio=round(100 - cash_ratio, 2),
        position_count=len(df),
        positions=df.to_dict(orient="records")
    )
