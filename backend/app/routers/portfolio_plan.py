"""
Portfolio plan (个股计划) API router.
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from app.models.portfolio_plan import StockPlan
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/portfolio/plans", tags=["PortfolioPlan"])


@router.get("/", response_model=list[StockPlan])
def list_plans(ticker: Optional[str] = Query(None)):
    """查询个股计划（支持按 ticker 过滤）"""
    df = DataStorage.read_plans(ticker)
    return df.to_dict(orient="records")


@router.get("/latest")
def latest_plans():
    """获取每个持仓的最新一条计划（用于表格展示）"""
    df = DataStorage.read_plans()
    if df.empty:
        return []
    # Get latest plan per ticker
    latest = df.sort_values("plan_date", ascending=False).groupby("ticker").first().reset_index()
    return latest.to_dict(orient="records")


@router.post("/", status_code=201)
def add_plan(plan: StockPlan):
    """新增一条个股计划"""
    data = plan.model_dump()
    # Store plan_date as ISO string (YYYY-MM-DD) for consistent parquet typing
    plan_date_val = data.get("plan_date")
    if isinstance(plan_date_val, (date, datetime)):
        data["plan_date"] = plan_date_val.isoformat()
    elif plan_date_val and not isinstance(plan_date_val, str):
        data["plan_date"] = str(plan_date_val)
    new_id = DataStorage.append_plan(data)
    return {"status": "ok", "id": new_id}


@router.delete("/{plan_id}")
def delete_plan(plan_id: int):
    """删除指定计划"""
    df = DataStorage.read_plans()
    if df.empty or "id" not in df.columns or plan_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="计划不存在")
    DataStorage.delete_plan(plan_id)
    return {"status": "ok"}
