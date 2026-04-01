"""
Portfolio API router.
"""
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
    上传持仓 xlsx 文件，自动解析并存储。

    期望 Excel 列（表头行后第一行开始）：
    股票代码 | 股票名称 | 持股数量 | 成本价 | 当前价 | 仓位占比%

    示例：
    SZ000001 | 平安银行 | 1000 | 12.50 | 13.20 | 22.0
    SH600519 | 贵州茅台 | 200 | 1800 | 1850 | 18.5
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    try:
        contents = file.file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        ws = wb.active

        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            raise HTTPException(status_code=400, detail="Excel 文件数据行不足（需包含表头）")

        # 尝试找表头行
        header_row_idx = None
        headers = []
        for i, row in enumerate(rows):
            if row and any(cell is not None for cell in row):
                # 取前6个非空单元格作为候选表头
                cells = [str(c).strip() if c is not None else "" for c in row[:8]]
                if any(kw in "".join(cells) for kw in ["代码", "名称", "数量", "成本", "价格", "仓位", "占比"]):
                    headers = cells
                    header_row_idx = i
                    break

        if header_row_idx is None:
            # 没找到表头，假设第1行就是数据
            headers = ["股票代码", "股票名称", "持股数量", "成本价", "当前价", "仓位占比%"]
            header_row_idx = 0
            data_rows = rows[header_row_idx:]
        else:
            data_rows = rows[header_row_idx + 1:]

        # 列索引映射
        def col_idx(keywords):
            for j, h in enumerate(headers):
                if any(kw in str(h) for kw in keywords):
                    return j
            return -1

        col_code   = col_idx(["代码", "code", "stock_code"])
        col_name   = col_idx(["名称", "name", "stock_name"])
        col_qty    = col_idx(["数量", "quantity", "持股", "持股数量"])
        col_cost   = col_idx(["成本", "cost"])
        col_price  = col_idx(["当前", "现价", "price", "current_price", "最新"])
        col_ratio  = col_idx(["仓位", "占比", "ratio", "position_ratio", "比例"])

        missing = []
        if col_code < 0:   missing.append("股票代码")
        if col_name < 0:   missing.append("股票名称")
        if col_qty < 0:    missing.append("持股数量")
        if col_cost < 0:   missing.append("成本价")
        if col_price < 0:  missing.append("当前价")
        if col_ratio < 0:  missing.append("仓位占比%")

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"缺少必需列：{', '.join(missing)}，请检查 Excel 表头"
            )

        records = []
        portfolio_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        for row in data_rows:
            if not row or all(cell is None for cell in row):
                continue
            cells = [cell for cell in row]
            try:
                ticker = str(cells[col_code]).strip().replace(" ", "")
                name   = str(cells[col_name]).strip() if col_name >= 0 and col_name < len(cells) else ""
                qty    = int(float(cells[col_qty])) if col_qty >= 0 and col_qty < len(cells) and cells[col_qty] is not None else 0
                cost   = float(cells[col_cost]) if col_cost >= 0 and col_cost < len(cells) and cells[col_cost] is not None else 0.0
                price  = float(cells[col_price]) if col_price >= 0 and col_price < len(cells) and cells[col_price] is not None else 0.0
                ratio  = float(cells[col_ratio]) if col_ratio >= 0 and col_ratio < len(cells) and cells[col_ratio] is not None else 0.0
            except (ValueError, TypeError):
                continue

            if not ticker or qty <= 0:
                continue

            market_value = round(qty * price, 2)
            float_profit = round((price - cost) * qty, 2)
            float_ratio  = round((price / cost - 1) * 100, 2) if cost > 0 else 0.0

            records.append(PortfolioRecord(
                ticker=ticker,
                name=name,
                quantity=qty,
                cost_price=round(cost, 3),
                current_price=round(price, 3),
                market_value=market_value,
                float_profit=float_profit,
                float_profit_ratio=round(float_ratio, 2),
                position_ratio=round(ratio, 2),
                date=portfolio_date,
            ))

        if not records:
            raise HTTPException(status_code=400, detail="未能从文件中解析出有效持仓记录，请检查格式")

        # 写入存储（覆盖模式）
        df = pd.DataFrame([r.model_dump() for r in records])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        DataStorage.write_portfolio(df)

        return {"status": "ok", "date": date_str, "count": len(records), "records": records[:3]}

    except BadZipFile:
        raise HTTPException(status_code=400, detail="文件格式错误，请上传有效的 .xlsx 文件")
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
