"""
Rules API router.
"""
from datetime import date
from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np

from app.models.rules import RuleLibrary
from app.services.data_storage import DataStorage
from app.config import settings

router = APIRouter(prefix="/api/rules", tags=["Rules"])

RULES_FILE = "rules.parquet"


def _rules_path():
    return DataStorage._parquet_path(settings.RULES_DIR, RULES_FILE)


def _to_native(obj):
    """将 numpy/pandas 类型递归转换为 Python 原生类型"""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(item) for item in obj]
    # pandas Timestamp / datetime64 -> datetime.datetime
    if isinstance(obj, (np.datetime64, pd.Timestamp)):
        return pd.Timestamp(obj).to_pydatetime()
    return obj


@router.get("/", response_model=RuleLibrary)
def get_rules():
    """获取规则库"""
    path = _rules_path()
    if not path.exists() or path.stat().st_size == 0:
        # 返回默认规则库
        return RuleLibrary.default_rules()
    df = DataStorage.read_parquet(path)
    if df.empty:
        return RuleLibrary.default_rules()
    # rebuild RuleLibrary from dataframe
    from app.models.rules import RuleBase
    records = df.to_dict(orient="records")
    rules = [RuleBase(**{k: _to_native(v) for k, v in row.items()}) for row in records]
    return RuleLibrary(
        version=str(df["version"].iloc[0]) if "version" in df.columns else "v1",
        last_updated=_to_native(df["last_updated"].iloc[0]) if "last_updated" in df.columns else date.today(),
        rules=rules
    )


@router.post("/")
def save_rules(library: RuleLibrary):
    """保存/更新规则库（覆盖）"""
    if not library.rules:
        DataStorage.write_parquet(_rules_path(), pd.DataFrame())
        return {"status": "ok", "count": 0}
    records = [r.model_dump() for r in library.rules]
    df = pd.DataFrame(records)
    df["version"] = library.version
    df["last_updated"] = date.today()
    DataStorage.write_parquet(_rules_path(), df)
    return {"status": "ok", "count": len(library.rules)}


@router.post("/reset")
def reset_rules():
    """重置规则库为默认值"""
    default = RuleLibrary.default_rules()
    return save_rules(default)


@router.put("/{rule_id}")
def update_single_rule(rule_id: str, patch: dict):
    """更新单个规则的字段（如 enabled）"""
    path = _rules_path()
    if not path.exists() or path.stat().st_size == 0:
        raise HTTPException(status_code=404, detail="规则库不存在")
    df = DataStorage.read_parquet(path)
    if 'rule_id' not in df.columns or rule_id not in df['rule_id'].values:
        raise HTTPException(status_code=404, detail="规则不存在")
    for key, val in patch.items():
        if key in df.columns:
            df.loc[df['rule_id'] == rule_id, key] = val
    DataStorage.write_parquet(path, df)
    return {"status": "ok", "rule_id": rule_id, "updated": patch}


@router.get("/evaluate")
def evaluate_portfolio():
    """
    对当前持仓进行全面规则评估（支撑/阻力版）。

    返回每个持仓标的的关键价位分析 + 所有触发规则信号。
    """
    from app.services.data_storage import DataStorage
    from app.services.rules_evaluator import evaluate_ticker, RuleResult

    portfolio_df = DataStorage.read_portfolio()
    if portfolio_df.empty:
        return {"status": "ok", "positions": [], "alerts": [], "summary": {"total": 0, "with_signals": 0}}

    alerts: list[dict] = []
    positions_data: list[dict] = []

    for _, row in portfolio_df.iterrows():
        ticker = str(row["ticker"])
        name = str(row.get("name", ticker))
        cost_price = float(row["cost_price"])
        quantity = int(row["quantity"])

        levels, results = evaluate_ticker(
            ticker=ticker,
            name=name,
            cost_price=cost_price,
            quantity=quantity,
        )

        positions_data.append(levels.to_dict())
        for r in results:
            alerts.append(r.to_dict())

    # 按 severity 排序（critical → major → minor）
    severity_order = {"critical": 0, "major": 1, "minor": 2}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 9))

    return {
        "status": "ok",
        "evaluated_at": pd.Timestamp.now().isoformat(),
        "summary": {
            "total": len(positions_data),
            "with_signals": len(set(a["ticker"] for a in alerts)),
            "critical_count": sum(1 for a in alerts if a["severity"] == "critical"),
            "major_count": sum(1 for a in alerts if a["severity"] == "major"),
            "minor_count": sum(1 for a in alerts if a["severity"] == "minor"),
        },
        "positions": positions_data,
        "alerts": alerts,
    }
