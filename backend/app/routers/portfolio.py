"""
Portfolio API router.
"""
from __future__ import annotations
import io
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
import pandas as pd
import openpyxl
from zipfile import BadZipFile  # openpyxl uses zipfile.BadZipFile internally

from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


@router.get("/", response_model=list[PortfolioRecord])
def list_portfolio(as_of_date: Optional[date] = Query(None)):
    """获取持仓列表（可选指定日期）"""
    df = DataStorage.read_portfolio(as_of_date)
    return df.to_dict(orient="records")


@router.post("/")
def upload_portfolio(records: list[PortfolioRecord]):
    """上传持仓数据（覆盖）"""
    if not records:
        raise HTTPException(status_code=400, detail="持仓记录不能为空")
    df = pd.DataFrame([r.model_dump() for r in records])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    DataStorage.write_portfolio(df)
    return {"status": "ok", "count": len(records)}


@router.post("/upload-xlsx")
def upload_portfolio_xlsx(
    date_str: str = Query(..., description="持仓日期，格式 YYYY-MM-DD"),
    file: UploadFile = File(..., description="持仓 xlsx 文件"),
):
    """
    解析券商格式持仓 Excel（如同花顺/东方财富导出格式），自动提取持仓数据。

    典型格式（Sheet1）：
      行1-7  ：账户头信息（资金账号/总资产等）
      行8    ：列标题（证券代码/证券名称/拥股数量/最新价/盈亏成本/浮动盈亏/盈亏比例/市场/仓位）
      行9-20 ：持仓明细
      行21+  ：合计行（跳过）

    字段映射：
      quantity       ← 拥股数量（列2）
      cost_price     ← 盈亏成本（列5，即保本价格）
      current_price  ← 最新价（列4）
      market_value   ← 证券市值（列6）
      float_profit   ← 浮动盈亏（列8）
      float_ratio    ← 盈亏比例（列9，带%）
      position_ratio ← 仓位（列19，带%）
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    try:
        contents = file.file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) < 10:
            raise HTTPException(status_code=400, detail="Excel 数据行不足")

        # ── 1. 定位表头行 ─────────────────────────────────────
        HEADER_KEYWORDS = ["证券代码", "股票代码", "代码", "ticker"]
        header_row_idx = None
        for i, row in enumerate(rows):
            if row and any(cell is not None for cell in row):
                first_cells = [str(c).strip() for c in row[:5] if c is not None]
                if any(kw in " ".join(first_cells) for kw in HEADER_KEYWORDS):
                    header_row_idx = i
                    headers = [str(c).strip() if c is not None else "" for c in row]
                    break

        if header_row_idx is None:
            raise HTTPException(status_code=400, detail="未找到表头行（需包含「证券代码」列）")

        data_rows = rows[header_row_idx + 1:]

        # ── 2. 列索引映射（容错匹配）──────────────────────────
        def col_idx(keywords: list[str]) -> int:
            for j, h in enumerate(headers):
                if any(kw in str(h) for kw in keywords):
                    return j
            return -1

        # 必填列
        col_code   = col_idx(["证券代码", "股票代码", "代码"])
        col_name   = col_idx(["证券名称", "股票名称", "名称"])
        col_qty    = col_idx(["拥股数量", "持股数量", "股票数量", "数量"])
        col_price  = col_idx(["最新价", "当前价", "现价", "价格", "price"])
        col_cost   = col_idx(["盈亏成本", "参考保本价", "成本价", "cost"])  # 盈亏成本 = 保本价
        col_mv     = col_idx(["证券市值", "市值", "market_value"])
        col_fp     = col_idx(["浮动盈亏", "盈亏金额"])
        col_fpr    = col_idx(["盈亏比例", "盈亏比例%"])
        col_ratio  = col_idx(["仓位", "仓位占比", "position", "ratio"])
        col_market = col_idx(["市场"])

        required = [("证券代码", col_code), ("证券名称", col_name),
                    ("拥股数量", col_qty), ("最新价", col_price),
                    ("盈亏成本", col_cost), ("浮动盈亏", col_fp)]
        missing = [name for name, idx in required if idx < 0]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"缺少必需列：{', '.join(missing)}，请确认 Excel 表头包含这些列"
            )

        # ── 3. 解析每一行 ────────────────────────────────────
        def parse_pct(v: str | float | None) -> float:
            """解析百分比字符串，如 '1.22%' → 1.22"""
            if v is None or v == "--" or v == "":
                return 0.0
            s = str(v).strip().replace("%", "").replace(" ", "")
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        def parse_num(v: str | float | None, default: float = 0.0) -> float:
            if v is None or v == "" or v == "--":
                return default
            try:
                return float(str(v).strip().replace(",", ""))
            except (ValueError, TypeError):
                return default

        records: list[PortfolioRecord] = []
        portfolio_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        parsed_tickers: set[str] = set()

        for row in data_rows:
            if not row or len(row) < 5:
                continue
            cells = list(row)

            # 证券代码：清理 tab 空格，补齐 6 位，加上市场前缀 SZ/SH/HK
            raw_code = str(cells[col_code]).replace("\t", "").replace(" ", "").strip()
            if not raw_code or raw_code in ("", "None"):
                continue  # 跳过合计行
            code6 = raw_code.zfill(6) if raw_code.isdigit() else raw_code
            # 根据市场字段补前缀
            market_raw = str(cells[col_market]).strip() if col_market >= 0 and col_market < len(cells) and cells[col_market] else ""
            if "深" in market_raw or "SZ" in market_raw.upper():
                ticker = "SZ" + code6
            elif "沪" in market_raw or "SH" in market_raw.upper():
                ticker = "SH" + code6
            elif "港" in market_raw:
                ticker = "HK" + code6
            else:
                ticker = code6
            if ticker in parsed_tickers:
                continue
            parsed_tickers.add(ticker)

            name = str(cells[col_name]).strip() if col_name < len(cells) and cells[col_name] else ""

            # 拥股数量
            qty_raw = cells[col_qty] if col_qty < len(cells) else None
            try:
                qty = int(float(str(qty_raw).strip().replace(",", "")))
            except (ValueError, TypeError):
                qty = 0
            if qty <= 0:
                continue  # 持仓为 0 跳过

            # 最新价
            price = parse_num(cells[col_price] if col_price < len(cells) else None)
            # 成本价（盈亏成本 = 保本价，即卖出不亏的价格）
            cost = parse_num(cells[col_cost] if col_cost < len(cells) else None)
            # 市值（证券市值优先，否则用数量×现价推算）
            mv_raw = cells[col_mv] if col_mv < len(cells) else None
            mv = parse_num(mv_raw, default=qty * price) if mv_raw != "--" else qty * price
            # 浮动盈亏
            float_profit = parse_num(cells[col_fp] if col_fp < len(cells) else None)
            # 盈亏比例：直接读原始文件（券商已算好），避免自行计算时 cost≈0 导致溢出
            float_ratio = parse_pct(cells[col_fpr] if col_fpr < len(cells) else None)
            # 仓位占比（带%）
            position_ratio = parse_pct(cells[col_ratio] if col_ratio < len(cells) else None)
            # 市场
            market = str(cells[col_market]).strip() if col_market >= 0 and col_market < len(cells) and cells[col_market] else ""

            records.append(PortfolioRecord(
                ticker=ticker,
                name=name,
                quantity=qty,
                cost_price=round(cost, 3),
                current_price=round(price, 3),
                market_value=round(mv, 2),
                float_profit=round(float_profit, 2),
                float_profit_ratio=round(float_ratio, 2),
                position_ratio=round(position_ratio, 2),
                date=portfolio_date,
            ))

        if not records:
            raise HTTPException(status_code=400, detail="未能从文件中解析出有效持仓记录，请检查文件内容")

        # ── 4. 写入存储（追加：同日期覆盖，不同日期追加）──────────
        df = pd.DataFrame([r.model_dump() for r in records])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        DataStorage.write_portfolio(df)

        return {
            "status": "ok",
            "date": date_str,
            "count": len(records),
            "preview": [
                {"ticker": r.ticker, "name": r.name, "qty": r.quantity,
                 "cost": r.cost_price, "price": r.current_price,
                 "float_profit": r.float_profit, "position_ratio": r.position_ratio}
                for r in records[:5]
            ],
        }

    except BadZipFile:
        raise HTTPException(status_code=400, detail="文件格式错误，请上传有效的 .xlsx 文件")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.get("/snapshot", response_model=PortfolioSnapshot)
def portfolio_snapshot(as_of_date: Optional[date] = Query(None)):
    """获取持仓快照汇总"""
    df = DataStorage.read_portfolio(as_of_date)
    if df.empty:
        raise HTTPException(status_code=404, detail="暂无持仓数据")
    total_mv = df["market_value"].sum()
    total_cost = (df["quantity"] * df["cost_price"]).sum()
    total_float = df["float_profit"].sum()
    float_ratio = (total_float / total_cost * 100) if total_cost else 0
    cash_ratio = 100 - df["position_ratio"].sum()
    return PortfolioSnapshot(
        date=as_of_date or date.today(),
        total_market_value=total_mv,
        total_cost=total_cost,
        total_float_profit=total_float,
        float_profit_ratio=round(float_ratio, 2),
        cash_ratio=round(cash_ratio, 2),
        position_ratio=round(100 - cash_ratio, 2),
        position_count=len(df),
        positions=df.to_dict(orient="records")
    )
