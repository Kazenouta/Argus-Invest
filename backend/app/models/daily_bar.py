"""
日线行情数据模型。
每行 = 一只股票某一天的日线bar（开盘/最高/最低/收盘/成交量/成交额/涨跌幅等）。
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class DailyBar(BaseModel):
    """
    单条日线行情记录。
    """
    date: str = Field(description="交易日期，格式 YYYY-MM-DD")
    ticker: str = Field(description="股票代码，如 000001、600519")
    name: str = Field(default="", description="股票名称")
    open: float = Field(description="开盘价")
    high: float = Field(description="最高价")
    low: float = Field(description="最低价")
    close: float = Field(description="收盘价")
    volume: float = Field(description="成交量（股）")
    amount: float = Field(default=0.0, description="成交额（元）")
    pct_change: float = Field(default=0.0, description="涨跌幅（%，当日收盘价相对前收盘的变化）")
    turnover: float = Field(default=0.0, description="换手率（%）")
    amplitude: float = Field(default=0.0, description="振幅（%）")
    market: str = Field(default="", description="市场：SH/SZ/BJ/HK")  # 便于日后按市场过滤
