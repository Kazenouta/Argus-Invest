"""
Weakness profile API router (v2 - 深度行为分析版).
"""
from datetime import date
from fastapi import APIRouter, HTTPException
from typing import Optional
import pandas as pd

from app.models.weakness import WeaknessProfile, WeaknessItem
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/weakness", tags=["Weakness"])


def _row_to_item(row: dict) -> WeaknessItem:
    """将 parquet 行映射到 WeaknessItem（兼容新旧字段）"""
    return WeaknessItem(
        id=str(row.get('id', '')),
        name=str(row.get('name', row.get('title', ''))),
        severity=str(row.get('severity', 'medium')),
        category=str(row.get('category', '')),
        description=str(row.get('description', '')),
        data_points=str(row.get('data_points', '')),
        affected_stocks=str(row.get('affected_stocks', '')),
        monetize_impact=str(row.get('monetize_impact', '')),
        related_weakness=str(row.get('related_weakness', '[]')),
        recommended_rules=str(row.get('recommended_rules', '[]')),
        enabled=bool(row.get('enabled', True)),
        confirmed=bool(row.get('confirmed', False)),
        created_at=str(row.get('created_at', '')),
    )


@router.get("/", response_model=WeaknessProfile)
def get_weakness_profile():
    """获取弱点画像"""
    df = DataStorage.read_weakness_profile()
    if df.empty:
        return WeaknessProfile()

    items = [_row_to_item(row) for row in df.to_dict(orient="records")]
    critical_count = len([i for i in items if i.severity == "critical"])

    return WeaknessProfile(
        version=str(df.iloc[0].get('version', 'v2')) if 'version' in df.columns else 'v2_deep_analysis',
        last_updated=df.iloc[0].get('last_updated', date.today()) if 'last_updated' in df.columns else date.today(),
        items=items,
        total_count=len(items),
        critical_count=critical_count,
    )


@router.post("/")
def save_weakness_profile(profile: WeaknessProfile):
    """保存/更新弱点画像（覆盖）"""
    if not profile.items:
        DataStorage.write_weakness_profile(pd.DataFrame())
        return {"status": "ok", "count": 0}

    records = []
    for item in profile.items:
        item_dict = {
            'id': item.id,
            'name': item.name,
            'severity': item.severity,
            'category': item.category,
            'description': item.description,
            'data_points': item.data_points,
            'affected_stocks': item.affected_stocks,
            'monetize_impact': item.monetize_impact,
            'related_weakness': item.related_weakness,
            'recommended_rules': item.recommended_rules,
            'enabled': item.enabled,
            'confirmed': item.confirmed,
            'created_at': item.created_at,
        }
        records.append(item_dict)

    df = pd.DataFrame(records)
    df['last_updated'] = date.today()
    df['version'] = profile.version
    DataStorage.write_weakness_profile(df)
    return {"status": "ok", "count": len(records)}


@router.put("/{item_id}/confirm")
def confirm_weakness_item(item_id: str, confirmed: bool = True):
    """确认/取消确认单个弱点条目"""
    df = DataStorage.read_weakness_profile()
    if df.empty or 'id' not in df.columns or item_id not in df['id'].values:
        raise HTTPException(status_code=404, detail="弱点条目不存在")
    df.loc[df['id'] == item_id, 'confirmed'] = confirmed
    DataStorage.write_weakness_profile(df)
    return {"status": "ok", "confirmed": confirmed}
