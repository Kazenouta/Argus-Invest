"""
Trades API router.
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from app.models.trades import TradeRecord
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/trades", tags=["Trades"])


@router.get("/")
def list_trades(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    ticker: Optional[str] = Query(None),
):
    """查询调仓记录"""
    df = DataStorage.read_trades(start_date, end_date, ticker)
    return df.to_dict(orient="records")


@router.post("/")
def add_trade(trade: TradeRecord):
    """追加一条调仓记录"""
    record = trade.model_dump()
    # ensure datetime fields are proper strings for parquet
    if isinstance(record.get("created_at"), datetime):
        record["created_at"] = record["created_at"].isoformat()
    new_id = DataStorage.append_trade(record)
    return {"status": "ok", "id": new_id}


@router.delete("/{trade_id}")
def delete_trade(trade_id: int):
    """删除指定调仓记录（软删除，改用 enabled 字段）"""
    df = DataStorage.read_trades()
    if df.empty:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    if "id" not in df.columns or trade_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    df = df[df["id"] != trade_id]
    DataStorage.write_parquet(DataStorage.trades_path(), df)
    return {"status": "ok"}
