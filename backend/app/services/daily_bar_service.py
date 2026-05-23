"""
日线行情数据服务。

使用 AkShare 逐只拉取全A股日线历史数据（2020至今），并发加速。
存入 Parquet 按年分区，DuckDB 查询。
支持增量同步：传入 last_date，本地已有数据时只拉取其之后的交易日。
"""
import os
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from app.config import settings
from app.services.data_storage import DataStorage

logger = logging.getLogger(__name__)

# 日线数据存放根目录
DAILY_BARS_DIR: Path = settings.DATA_DIR / "market" / "daily"
DAILY_BARS_DIR.mkdir(parents=True, exist_ok=True)

_PROXY_ENVS = ("http_proxy", "https_proxy", "all_proxy")


def _proxy() -> Optional[str]:
    return os.environ.get("http_proxy") or os.environ.get("all_proxy") or None


def _clear_proxy() -> None:
    for k in _PROXY_ENVS:
        os.environ.pop(k, None)


def _set_proxy() -> None:
    p = _proxy()
    if p:
        os.environ["http_proxy"] = p
        os.environ["https_proxy"] = p


def _parquet_path(year: int) -> Path:
    return DAILY_BARS_DIR / f"daily_bars_{year}.parquet"


def _fetch_stock_list() -> list[tuple[str, str]]:
    """获取全A股代码列表，返回 [(code, name), ...]。"""
    import akshare as ak
    _clear_proxy()
    try:
        df = ak.stock_info_a_code_name()
        return [(str(r["code"]).zfill(6), str(r["name"])) for _, r in df.iterrows()]
    except Exception as e:
        logger.warning(f"[DailyBar] 获取股票列表失败: {e}")
        return []


def _fetch_single(
    ticker: str,
    start_date: str,
    end_date: str,
    adjust: str = "qfq",
) -> Optional[pd.DataFrame]:
    """
    拉取单只股票的日线数据。
    先尝试 stock_zh_a_hist（批量接口，无需代理），失败则用 stock_zh_a_daily（逐股票接口）。
    """
    import akshare as ak

    _clear_proxy()
    code = ticker.zfill(6)

    # 判断市场前缀
    if code.startswith(("6", "9")):
        prefix = "sh"
    elif code.startswith(("4", "8")):
        prefix = "bj"
    else:
        prefix = "sz"

    sym = prefix + code

    # 方法1：stock_zh_a_hist（单股票接口，支持 start_date/end_date，不需代理）
    try:
        df = ak.stock_zh_a_hist(
            symbol=ticker,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust=adjust,
        )
        if df is not None and not df.empty:
            df = df.rename(columns={
                "日期": "date", "股票代码": "ticker", "名称": "name",
                "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
                "涨跌幅": "pct_change", "换手率": "turnover", "振幅": "amplitude",
            })
            df = df[df["ticker"].str.match(r"^\d{6}$", na=False)].copy()
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            df["market"] = "SH" if code.startswith(("6", "9")) else ("BJ" if code.startswith(("4", "8")) else "SZ")
            for c in ("open", "high", "low", "close", "volume", "amount", "pct_change", "turnover", "amplitude"):
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
            cols = ["date", "ticker", "name", "open", "high", "low", "close",
                    "volume", "amount", "pct_change", "turnover", "amplitude", "market"]
            return df[[c for c in cols if c in df.columns]].reset_index(drop=True)
    except Exception:
        pass

    # 方法2：stock_zh_a_daily（需要前缀符号，逐只拉取）
    try:
        df = ak.stock_zh_a_daily(symbol=sym, start_date=start_date, end_date=end_date, adjust=adjust)
        if df is not None and not df.empty:
            df = df.rename(columns={
                "date": "date", "open": "open", "close": "close",
                "high": "high", "low": "low", "volume": "volume",
            })
            df["ticker"] = ticker
            df["name"] = ""
            df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
            for c in ("open", "high", "low", "close", "volume"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["amount"] = 0.0
            df["pct_change"] = df["close"].pct_change().fillna(0) * 100
            df["turnover"] = 0.0
            df["amplitude"] = 0.0
            df["market"] = "SH" if code.startswith(("6", "9")) else ("BJ" if code.startswith(("4", "8")) else "SZ")
            cols = ["date", "ticker", "name", "open", "high", "low", "close",
                    "volume", "amount", "pct_change", "turnover", "amplitude", "market"]
            return df[[c for c in cols if c in df.columns]].reset_index(drop=True)
    except Exception:
        pass

    return None


def _market(t: str) -> str:
    t = str(t)
    if t.startswith(("6", "9")):
        return "SH"
    if t.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """统一 DataFrame 字段格式。"""
    if df.empty:
        return df

    df = df.rename(columns={
        "日期": "date", "股票代码": "ticker", "名称": "name",
        "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "amount",
        "涨跌幅": "pct_change", "换手率": "turnover", "振幅": "amplitude",
    })
    df = df[df["ticker"].str.match(r"^\d{6}$", na=False)].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["market"] = df["ticker"].apply(_market)
    for c in ("open", "high", "low", "close", "volume", "amount", "pct_change", "turnover", "amplitude"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    cols = ["date", "ticker", "name", "open", "high", "low", "close",
            "volume", "amount", "pct_change", "turnover", "amplitude", "market"]
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)


def _save_year(df: pd.DataFrame, year: int) -> int:
    """追加写入对应年份 Parquet，去重，返回实际新增行数。"""
    if df.empty:
        return 0
    target = _parquet_path(year)
    existing = DataStorage.read_parquet(target)
    if existing is not None and not existing.empty:
        exist_keys = set(zip(existing["date"], existing["ticker"]))
        df = df[~df.apply(lambda r: (r["date"], r["ticker"]) in exist_keys, axis=1)]
    if df.empty:
        return 0
    merged = pd.concat([existing, df], ignore_index=True) if existing is not None else df
    DataStorage.write_parquet(target, merged)
    return len(df)


def sync_full(
    start_year: int = 2020,
    end_year: Optional[int] = None,
    workers: int = 16,
    progress_callback=None,
) -> dict:
    """
    全量同步：获取全A股列表，并发拉取历史日线数据，按年存储。
    progress_callback(batch_done, total, detail) 可选，用于进度回调。
    返回 {"done": N, "failed": M, "saved": {year: rows}, "errors": [...]}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    today = date.today()
    if end_year is None:
        end_year = today.year
    end_year = min(end_year, today.year)

    logger.info(f"[DailyBar] 开始全量同步 {start_year}~{end_year}，并发数={workers}")

    # 获取全量股票列表
    stocks = _fetch_stock_list()
    if not stocks:
        logger.error("[DailyBar] 无法获取股票列表，同步终止")
        return {"done": 0, "failed": 0, "saved": {}, "errors": ["无法获取股票列表"]}

    total = len(stocks)
    logger.info(f"[DailyBar] 共 {total} 只股票，开始并发拉取")

    done = 0
    failed = 0
    errors = []
    year_saved: dict[int, int] = {}

    def fetch_one(item: tuple[str, str]) -> Optional[pd.DataFrame]:
        ticker, name = item
        try:
            # 拉取完整历史（2020~end_year）
            df = _fetch_single(ticker, f"{start_year}0101", f"{end_year}1231")
            if df is not None and not df.empty:
                df["name"] = name or df.get("name", "").iloc[0] if hasattr(df.get("name", ""), '__iter__') else name
                return _normalize_df(df) if "名称" in df.columns or "股票代码" in df.columns else df
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_one, s): s for s in stocks}
        for fut in as_completed(futures):
            ticker, _ = futures[fut]
            try:
                df = fut.result()
            except Exception as e:
                failed += 1
                errors.append(f"{ticker}: {e}")
                done += 1
                if progress_callback:
                    progress_callback(done, total, ticker, str(e))
                continue

            if df is not None and not df.empty:
                # 按年拆分保存
                df["date"] = pd.to_datetime(df["date"])
                for year, grp in df.groupby(df["date"].dt.year):
                    yr = int(year)
                    saved = _save_year(grp.assign(date=grp["date"].dt.strftime("%Y-%m-%d")), yr)
                    year_saved[yr] = year_saved.get(yr, 0) + saved
                if progress_callback:
                    progress_callback(done, total, ticker, f"OK, saved={sum(grp.shape[0] for _year, grp in df.groupby(df['date'].dt.year))}")
            else:
                failed += 1
                if progress_callback:
                    progress_callback(done, total, ticker, "no data")

            done += 1

    logger.info(f"[DailyBar] 同步完成：成功 {done - failed}/{total}，失败 {failed}，保存 {year_saved}")
    return {
        "done": done - failed,
        "failed": failed,
        "saved": {str(k): v for k, v in year_saved.items()},
        "errors": errors[:20],  # 最多记录20条
    }


def get_daily_bars(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """从本地 Parquet 查询指定股票的日线数据。"""
    today = date.today()
    start_year = int(start_date[:4]) if start_date else 2020
    end_year = min(int(end_date[:4]), today.year) if end_date else today.year

    frames = []
    for year in range(start_year, end_year + 1):
        path = _parquet_path(year)
        if not path.exists():
            continue
        df = DataStorage.read_parquet(path)
        if df is None or df.empty:
            continue
        df = df[df["ticker"] == ticker]
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if start_date:
        result = result[result["date"] >= pd.to_datetime(start_date)]
    if end_date:
        result = result[result["date"] <= pd.to_datetime(end_date)]

    return (result
            .sort_values("date", ascending=True)
            .tail(limit)
            .reset_index(drop=True))


def get_latest_date_for_ticker(ticker: str) -> Optional[str]:
    """获取本地数据中某股票最新一条行情的日期。"""
    today = date.today()
    for year in range(today.year, 2019, -1):
        path = _parquet_path(year)
        if not path.exists():
            continue
        df = DataStorage.read_parquet(path)
        if df is None or df.empty:
            continue
        ticker_df = df[df["ticker"] == ticker]
        if not ticker_df.empty:
            return str(ticker_df["date"].max())
    return None


def sync_incremental(
    ticker: str,
    last_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[Optional[pd.DataFrame], str]:
    """
    增量同步：若 last_date 存在，只拉取 last_date 之后的新交易日数据。
    返回 (新增 DataFrame, 最新交易日期)。
    """
    import akshare as ak
    _clear_proxy()

    today = date.today()
    if end_date is None:
        end_date = today.strftime("%Y-%m-%d")

    # 如果没传 last_date，从本地读取
    if not last_date:
        last_date = get_latest_date_for_ticker(ticker)
        if not last_date:
            last_date = "2020-01-01"

    # 确定起始日期（last_date 的下一个交易日）
    from datetime import timedelta
    start = (pd.to_datetime(last_date) + timedelta(days=1)).strftime("%Y-%m-%d")

    if start >= end_date:
        return pd.DataFrame(), last_date

    code = ticker.zfill(6)
    if code.startswith(("6", "9")):
        prefix = "sh"
    elif code.startswith(("4", "8")):
        prefix = "bj"
    else:
        prefix = "sz"

    df = None
    # 尝试 stock_zh_a_hist（单股票接口，支持日期范围）
    try:
        df = ak.stock_zh_a_hist(
            symbol=ticker,
            start_date=start.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
    except Exception:
        pass

    if df is None or df.empty:
        try:
            df = ak.stock_zh_a_daily(
                symbol=prefix + code,
                start_date=start,
                end_date=end_date,
                adjust="qfq",
            )
        except Exception:
            pass

    if df is None or df.empty:
        return pd.DataFrame(), last_date

    df = _normalize_df(df)
    new_rows = df[df["date"] > last_date]
    if not new_rows.empty:
        year = pd.to_datetime(new_rows["date"]).dt.year.mode()[0]
        _save_year(new_rows, int(year))

    latest = str(new_rows["date"].max()) if not new_rows.empty else last_date
    return new_rows, latest


def get_coverage() -> dict:
    """各年份数据覆盖情况。"""
    today = date.today()
    cov = {}
    for year in range(2020, today.year + 1):
        path = _parquet_path(year)
        if not path.exists():
            cov[str(year)] = {"stocks": 0, "rows": 0}
            continue
        df = DataStorage.read_parquet(path)
        cov[str(year)] = {
            "stocks": int(df["ticker"].nunique()) if df is not None and not df.empty else 0,
            "rows": int(len(df)) if df is not None else 0,
        }
    return cov


def get_latest_trading_date() -> Optional[str]:
    """全局最新交易日（任意股票）。"""
    today = date.today()
    for year in range(today.year, 2019, -1):
        path = _parquet_path(year)
        if not path.exists():
            continue
        df = DataStorage.read_parquet(path)
        if df is not None and not df.empty:
            return str(df["date"].max())
    return None
