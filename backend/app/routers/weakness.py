"""
Weakness profile API router.
"""
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import pandas as pd

from app.models.weakness import WeaknessProfile, WeaknessItem
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/weakness", tags=["Weakness"])


@router.get("/", response_model=WeaknessProfile)
def get_weakness_profile():
    """获取弱点画像"""
    df = DataStorage.read_weakness_profile()
    if df.empty:
        # 返回默认空画像
        return WeaknessProfile()
    items = [WeaknessItem(**row) for row in df.to_dict(orient="records")]
    return WeaknessProfile(
        version=df["version"].iloc[0] if "version" in df.columns else "v1",
        last_updated=df["last_updated"].iloc[0] if "last_updated" in df.columns else date.today(),
        items=items,
        total_count=len(items),
        critical_count=len([i for i in items if i.severity == "critical"])
    )


@router.post("/")
def save_weakness_profile(profile: WeaknessProfile):
    """保存/更新弱点画像（覆盖）"""
    if not profile.items:
        # 清空弱点画像
        DataStorage.write_weakness_profile(pd.DataFrame())
        return {"status": "ok", "count": 0}
    records = [item.model_dump() for item in profile.items]
    df = pd.DataFrame(records)
    df["last_updated"] = date.today()
    df["version"] = profile.version
    DataStorage.write_weakness_profile(df)
    return {"status": "ok", "count": len(records)}


@router.put("/{item_id}/confirm")
def confirm_weakness_item(item_id: str, confirmed: bool = True):
    """确认/取消确认单个弱点条目"""
    df = DataStorage.read_weakness_profile()
    if df.empty or "id" not in df.columns or item_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="弱点条目不存在")
    df.loc[df["id"] == item_id, "confirmed"] = confirmed
    DataStorage.write_weakness_profile(df)
    return {"status": "ok", "confirmed": confirmed}
