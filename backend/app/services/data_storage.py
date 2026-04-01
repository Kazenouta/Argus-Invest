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
        """写入持仓数据（覆盖）"""
        cls.write_parquet(cls.portfolio_path(), df)

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

    # ── Weakness ────────────────────────────────────────────────────────

    @classmethod
    def read_weakness_profile(cls) -> pd.DataFrame:
        """读取弱点画像"""
        return cls.read_parquet(cls.weakness_path())

    @classmethod
    def write_weakness_profile(cls, df: pd.DataFrame) -> None:
        """写入弱点画像"""
        cls.write_parquet(cls.weakness_path(), df)

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
