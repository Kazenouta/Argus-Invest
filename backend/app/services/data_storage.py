"""
DuckDB + Parquet data storage service.

统一的数据层：所有数据通过 DuckDB 读写 Parquet 文件。
"""
import duckdb
from pathlib import Path
from typing import TypeVar, Generic, Type, Optional
from datetime import date, datetime
import pandas as pd
import threading

from app.config import settings

T = TypeVar("T")


class DataStorage:
    """
    基于 DuckDB + Parquet 的数据存储服务。
    每个表对应一个 Parquet 文件，通过 DuckDB SQL 查询。
    """

    _conn: Optional[duckdb.DuckDBPyConnection] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_conn(cls) -> duckdb.DuckDBPyConnection:
        """获取 DuckDB 连接（单例，线程安全）"""
        if cls._conn is None:
            with cls._lock:
                if cls._conn is None:  # 二次检查
                    cls._conn = duckdb.connect()
        return cls._conn

    @classmethod
    def close(cls) -> None:
        """关闭连接"""
        if cls._conn is not None:
            cls._conn.close()
            cls._conn = None

    # ── Parquet path helpers ────────────────────────────────────────────

    @staticmethod
    def _parquet_path(subdir: Path, filename: str) -> Path:
        return subdir / filename

    @classmethod
    def portfolio_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.PORTFOLIO_FILE)

    @classmethod
    def trades_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.TRADES_FILE)

    @classmethod
    def weakness_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.WEAKNESS_FILE)

    @classmethod
    def plans_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.PLAN_FILE)

    @classmethod
    def thinking_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.THINKING_FILE)

    # ── Generic read / write ────────────────────────────────────────────

    @classmethod
    def read_parquet(cls, path: Path) -> pd.DataFrame:
        """读取 Parquet 文件（文件不存在时返回空 DataFrame）

        直接用 pandas.read_parquet（底层 pyarrow），不走 DuckDB 连接，
        避免多线程并发访问导致崩溃。
        """
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)

    @classmethod
    def write_parquet(cls, path: Path, df: pd.DataFrame) -> None:
        """写入 Parquet 文件（覆盖）

        直接用 pandas.to_parquet()（底层 pyarrow）写入，
        避免通过 DuckDB 单例连接操作文件导致后台线程崩溃。
        """
        # pandas/pyarrow 写入，不走 DuckDB 连接
        df.to_parquet(path, index=False)
        # 确保落盘
        path.stat()

    @classmethod
    def append_parquet(cls, path: Path, df: pd.DataFrame) -> None:
        """追加写入 Parquet 文件"""
        if path.exists() and path.stat().st_size > 0:
            existing = cls.read_parquet(path)
            combined = pd.concat([existing, df], ignore_index=True)
        else:
            combined = df
        cls.write_parquet(path, combined)

    # ── Portfolio ───────────────────────────────────────────────────────

    @classmethod
    def read_portfolio(cls, as_of_date: Optional[date] = None) -> pd.DataFrame:
        """读取持仓数据（可选指定日期）"""
        df = cls.read_parquet(cls.portfolio_path())
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.date
        if as_of_date:
            df = df[df["date"] == as_of_date]
        return df

    @classmethod
    def write_portfolio(cls, df: pd.DataFrame) -> None:
        """写入持仓数据（追加：同日期覆盖，不同日期追加）"""
        path = cls.portfolio_path()
        existing = cls.read_parquet(path)
        if existing.empty:
            combined = df
        else:
            # 删除旧日期的记录，追加新记录（同日期覆盖）
            existing = existing[existing["date"] != df["date"].iloc[0]]
            combined = pd.concat([existing, df], ignore_index=True)
        df.to_parquet(path, index=False)

    # ── Trades ───────────────────────────────────────────────────────────

    @classmethod
    def read_trades(cls, start_date: Optional[date] = None,
                    end_date: Optional[date] = None,
                    ticker: Optional[str] = None) -> pd.DataFrame:
        """读取调仓记录（支持日期和标的过滤）"""
        df = cls.read_parquet(cls.trades_path())
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"]).dt.date
        if start_date:
            df = df[df["date"] >= start_date]
        if end_date:
            df = df[df["date"] <= end_date]
        if ticker:
            df = df[df["ticker"] == ticker]
        return df.sort_values("date", ascending=False)

    @classmethod
    def append_trade(cls, trade_record: dict) -> int:
        """追加一条调仓记录，返回自动生成的ID"""
        df = cls.read_trades()
        new_id = (df["id"].max() if not df.empty and "id" in df.columns else 0) + 1
        record = {**trade_record, "id": new_id}
        new_df = pd.DataFrame([record])
        cls.append_parquet(cls.trades_path(), new_df)
        return int(new_id)

    @classmethod
    def replace_trades_by_date(cls, records: list[dict], trade_date) -> None:
        """替换指定日期的全部调仓记录（先删后写）"""
        path = cls.trades_path()
        df = cls.read_trades()
        if not df.empty:
            df = df[df["date"] != trade_date]
        new_df = pd.DataFrame(records)
        combined = pd.concat([df, new_df], ignore_index=True) if not df.empty else new_df
        combined.to_parquet(path, index=False)

    # ── Weakness ────────────────────────────────────────────────────────

    @classmethod
    def read_weakness_profile(cls) -> pd.DataFrame:
        """读取弱点画像"""
        return cls.read_parquet(cls.weakness_path())

    @classmethod
    def write_weakness_profile(cls, df: pd.DataFrame) -> None:
        """写入弱点画像"""
        cls.write_parquet(cls.weakness_path(), df)

    # ── Portfolio Plans ─────────────────────────────────────────────────

    @classmethod
    def read_plans(cls, ticker: Optional[str] = None) -> pd.DataFrame:
        """读取个股计划，可选按 ticker 过滤，返回 plan_date 为 ISO 字符串"""
        df = cls.read_parquet(cls.plans_path())
        if df.empty:
            return df
        # plan_date stored as ISO string, return as-is
        if ticker:
            df = df[df["ticker"] == ticker]
        return df.sort_values("plan_date", ascending=False)

    @classmethod
    def append_plan(cls, plan_record: dict) -> int:
        """追加一条计划，返回自动生成的ID（plan_date/created_at 统一存为 ISO 字符串）"""
        df = cls.read_plans()
        new_id = (int(df["id"].max()) if not df.empty and "id" in df.columns and len(df) > 0 else 0) + 1
        record = {**plan_record, "id": new_id}
        for col in ("plan_date", "created_at"):
            val = record.get(col)
            if isinstance(val, (date, datetime)):
                record[col] = val.isoformat()
            elif val:
                record[col] = str(val)
        new_df = pd.DataFrame([record])
        cls.append_parquet(cls.plans_path(), new_df)
        return int(new_id)

    @classmethod
    def delete_plan(cls, plan_id: int) -> None:
        """删除指定计划"""
        df = cls.read_plans()
        if df.empty or "id" not in df.columns or plan_id not in df["id"].values:
            return
        df = df[df["id"] != plan_id]
        cls.write_parquet(cls.plans_path(), df)

    # ── Monitor Check Results ─────────────────────────────────────────────

    @classmethod
    def monitor_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, settings.MONITOR_FILE)

    @classmethod
    def save_monitor_check(cls, checked_at: datetime, total_positions: int,
                           total_events: int, events_data: list, indicators_data: list) -> None:
        """保存检查持仓的结果（覆盖写入）"""
        import json
        df = pd.DataFrame([{
            'checked_at': checked_at.isoformat(),
            'total_positions': total_positions,
            'total_events': total_events,
            'events': json.dumps(events_data, default=str),
            'indicators': json.dumps(indicators_data, default=str),
        }])
        cls.write_parquet(cls.monitor_path(), df)

    @classmethod
    def read_monitor_check(cls) -> Optional[dict]:
        """读取最近一次检查持仓的结果，不存在返回 None"""
        import json
        df = cls.read_parquet(cls.monitor_path())
        if df.empty:
            return None
        row = df.iloc[-1]
        return {
            'checked_at': row['checked_at'],
            'total_positions': int(row['total_positions']),
            'total_events': int(row['total_events']),
            'events': json.loads(row['events']),
            'indicators': json.loads(row['indicators']),
        }

    # ── Thinking ─────────────────────────────────────────────────────────

    @classmethod
    def read_thinking(cls, start_date: Optional[date] = None,
                      end_date: Optional[date] = None,
                      ticker: Optional[str] = None) -> pd.DataFrame:
        """读取盘中思考记录"""
        df = cls.read_parquet(cls.thinking_path())
        if df.empty:
            return df
        df["thinking_time"] = pd.to_datetime(df["thinking_time"])
        if start_date:
            df = df[df["thinking_time"].dt.date >= start_date]
        if end_date:
            df = df[df["thinking_time"].dt.date <= end_date]
        if ticker:
            df = df[df["ticker"] == ticker]
        return df.sort_values("thinking_time", ascending=False)

    @classmethod
    def append_thinking(cls, record: dict) -> int:
        """追加一条盘中思考记录"""
        df = cls.read_thinking()
        new_id = (df["id"].max() if not df.empty and "id" in df.columns else 0) + 1
        record_with_id = {**record, "id": new_id}
        new_df = pd.DataFrame([record_with_id])
        cls.append_parquet(cls.thinking_path(), new_df)
        return int(new_id)

    # ── Market AI Overview Cache ───────────────────────────────────────

    @classmethod
    def market_ai_cache_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, "market_ai_cache.parquet")

    @classmethod
    def save_market_ai_cache(cls, data: dict, updated_at: str) -> None:
        """保存 AI 市场概览缓存（覆盖写入）"""
        df = pd.DataFrame([{**data, "cached_at": updated_at}])
        cls.write_parquet(cls.market_ai_cache_path(), df)

    @classmethod
    def load_market_ai_cache(cls) -> Optional[dict]:
        """加载 AI 市场概览缓存，无缓存则返回 None（numpy类型转Python原生）"""
        path = cls.market_ai_cache_path()
        if not path.exists():
            return None
        df = cls.read_parquet(path)
        if df is None or df.empty:
            return None
        row = df.iloc[0].to_dict()
        row.pop("cached_at", None)

        def _to_native(obj):
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _to_native(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_to_native(x) for x in obj]
            return obj

        return _to_native(row)

    # ── Market Overview Cache (non-AI) ─────────────────────────────────

    @classmethod
    def market_overview_cache_path(cls) -> Path:
        return cls._parquet_path(settings.USER_DIR, "market_overview_cache.parquet")

    @classmethod
    def save_market_overview_cache(cls, data: dict) -> None:
        """保存普通市场概览缓存（覆盖写入）"""
        df = pd.DataFrame([data])
        cls.write_parquet(cls.market_overview_cache_path(), df)

    @classmethod
    def load_market_overview_cache(cls) -> Optional[dict]:
        """加载普通市场概览缓存，无缓存则返回 None（numpy类型转Python原生）"""
        path = cls.market_overview_cache_path()
        if not path.exists():
            return None
        df = cls.read_parquet(path)
        if df is None or df.empty:
            return None

        def _to_native(obj):
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _to_native(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_to_native(x) for x in obj]
            return obj

        return _to_native(df.iloc[0].to_dict())
