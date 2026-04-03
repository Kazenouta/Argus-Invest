"""
Market data service using Tencent Finance API (web.ifzq.gtimg.cn).
稳定可靠，支持 A 股历史行情。
"""
import json
import re
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests


class MarketData:
    """
    通过腾讯财经接口获取 A 股历史 OHLCV 数据。

    格式：["日期", "开盘", "收盘", "最高", "最低", "成交量"]
    返回 DataFrame 按日期升序排列。
    """

    _session = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.headers.update({
                "Referer": "https://finance.qq.com",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            })
            cls._session.proxies = {
                "http": "http://127.0.0.1:7890",
                "https": "http://127.0.0.1:7890",
            }
        return cls._session

    @classmethod
    def _ticker_to_market(cls, ticker: str) -> str:
        """ticker 格式: SH600096 / SZ000776 / SH515220 → sh600096"""
        prefix = ticker[:2].lower()
        code = ticker[2:].lower()
        return f"{prefix}{code}"

    @classmethod
    def get_hist(
        cls,
        ticker: str,
        days: int = 120,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        获取最近 N 个交易日的历史 OHLCV（前复权）。

        Returns DataFrame with columns:
          date, open, high, low, close, volume
        """
        if end_date is None:
            end_date = date.today()

        market_code = cls._ticker_to_market(ticker)
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?_var=kline_dayqfq&param={market_code},day,,,{days},qfq"
        )

        try:
            resp = cls._get_session().get(url, timeout=10)
            resp.raise_for_status()
            text = resp.text
            # 去掉 js 变量声明
            json_str = re.sub(r"^[^=]+=", "", text.strip())
            data = json.loads(json_str)
        except Exception:
            return pd.DataFrame()

        try:
            qfq_key = list(data["data"][market_code].keys())[0]
            raw_rows = data["data"][market_code][qfq_key]
        except (KeyError, IndexError):
            return pd.DataFrame()

        records = []
        for row in raw_rows:
            if len(row) < 6:
                continue
            try:
                records.append({
                    "date":   row[0],
                    "open":   float(row[1]),
                    "close":  float(row[2]),
                    "high":   float(row[3]),
                    "low":    float(row[4]),
                    "volume": float(row[5]),
                })
            except (ValueError, TypeError):
                continue

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.sort_values("date").reset_index(drop=True)

        # 只取 end_date 之前的数据
        if end_date:
            df = df[df["date"] <= end_date]

        return df

    @classmethod
    def latest_price(cls, ticker: str) -> Optional[float]:
        """获取最新收盘价"""
        df = cls.get_hist(ticker, days=5)
        if df.empty:
            return None
        return float(df.iloc[-1]["close"])

    @classmethod
    def get_ma(cls, ticker: str, period: int = 20, days: int = 120) -> pd.DataFrame:
        """返回带均线的 OHLCV DataFrame"""
        df = cls.get_hist(ticker, days=days + period)  # 多取一些确保均线准确
        if df.empty:
            return df
        df[f"ma{period}"] = df["close"].rolling(window=period).mean()
        return df.tail(days)  # 只返回最近 N 日

    @classmethod
    def get_realtime(cls, tickers: list[str]) -> dict[str, dict]:
        """
        批量获取实时行情（当日开盘价/最新价/最高/最低）。
        返回 {"SH600096": {"name": ..., "current": 32.67, "open": ..., "high": ..., "low": ...}}
        """
        if not tickers:
            return {}
        market_codes = [cls._ticker_to_market(t) for t in tickers]
        url = f"https://hq.sinajs.cn/list={','.join(market_codes)}"
        try:
            resp = cls._get_session().get(url, timeout=10)
            resp.raise_for_status()
            resp.encoding = "gbk"
            text = resp.text
        except Exception:
            return {}

        result = {}
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if not line.strip() or i >= len(tickers):
                continue
            ticker = tickers[i]
            m = re.search(r'"([^"]*)"', line)
            if not m:
                continue
            fields = m.group(1).split(",")
            if len(fields) < 10:
                continue
            try:
                result[ticker] = {
                    "name":     fields[0],
                    "open":     float(fields[1]) if fields[1] else 0,
                    "close":    float(fields[2]) if fields[2] else 0,   # 昨收
                    "current":  float(fields[3]) if fields[3] else 0,   # 当前/最新
                    "high":     float(fields[4]) if fields[4] else 0,
                    "low":      float(fields[5]) if fields[5] else 0,
                    "date":     fields[30] if len(fields) > 30 else "",
                    "time":     fields[31] if len(fields) > 31 else "",
                }
            except (ValueError, IndexError):
                continue
        return result
