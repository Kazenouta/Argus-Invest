"""
Intraday thinking records API router.
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

from app.models.thinking import ThinkingRecord
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/thinking", tags=["Thinking"])


@router.get("/")
def list_thinking(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    ticker: Optional[str] = Query(None),
):
    """查询盘中思考记录"""
    df = DataStorage.read_thinking(start_date, end_date, ticker)
    return df.to_dict(orient="records")


@router.post("/")
def add_thinking(record: ThinkingRecord):
    """追加一条盘中思考记录"""
    data = record.model_dump()
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    new_id = DataStorage.append_thinking(data)
    return {"status": "ok", "id": new_id}


@router.put("/{thinking_id}")
def update_thinking(thinking_id: int, record: ThinkingRecord):
    """更新指定思考记录"""
    df = DataStorage.read_thinking()
    if df.empty or "id" not in df.columns or thinking_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="思考记录不存在")
    data = record.model_dump()
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    row_idx = df[df["id"] == thinking_id].index[0]
    for col, val in data.items():
        df.at[row_idx, col] = val
    DataStorage.write_parquet(DataStorage.thinking_path(), df)
    return {"status": "ok"}


@router.delete("/{thinking_id}")
def delete_thinking(thinking_id: int):
    """删除指定思考记录"""
    df = DataStorage.read_thinking()
    if df.empty or "id" not in df.columns or thinking_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="思考记录不存在")
    df = df[df["id"] != thinking_id]
    DataStorage.write_parquet(DataStorage.thinking_path(), df)
    return {"status": "ok"}
