"""
Trades API router.
"""
import io
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from zipfile import BadZipFile
import pandas as pd
import openpyxl

from app.models.trades import TradeRecord
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/trades", tags=["Trades"])


@router.get("/")
def list_trades(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    ticker: Optional[str] = Query(None),
):
    """查询调仓记录"""
    df = DataStorage.read_trades(start_date, end_date, ticker)
    return df.to_dict(orient="records")


@router.post("/")
def add_trade(trade: TradeRecord):
    """追加一条调仓记录"""
    record = trade.model_dump()
    new_id = DataStorage.append_trade(record)
    return {"status": "ok", "id": new_id}


@router.post("/upload-xlsx")
def upload_trades_xlsx(
    file: UploadFile = File(..., description="当日成交 xlsx 文件"),
):
    """
    解析券商格式当日成交 Excel，批量追加调仓记录。

    格式（Sheet1）：
      行6   ：表头（流水号/证券代码/证券名称/成交类型/方向/成交状态/
               成交数量/成交价格/成交金额/成交时间/股东代码/委托数量/委托价格）
      行7+  ：成交明细

    映射规则：
      direction → action：证券买入→buy，证券卖出→sell，增强限价卖出→sell，撤单→adjust
      status → 成交/撤单：撤单记录 amount=0 不入库
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    try:
        contents = file.file.read()
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if len(rows) < 7:
            raise HTTPException(status_code=400, detail="文件数据行不足")

        # 定位表头行（第6行，index=5）
        header_row_idx = None
        for i, row in enumerate(rows):
            if row and str(row[0]).strip() in ("流水号", "委托号", "成交编号"):
                header_row_idx = i
                headers = [str(c).strip() if c else "" for c in row]
                break

        if header_row_idx is None:
            raise HTTPException(status_code=400, detail="未找到表头行（需以「流水号」开头）")

        data_rows = rows[header_row_idx + 1:]

        # 列索引
        def col(keyword: str) -> int:
            for j, h in enumerate(headers):
                if keyword in h:
                    return j
            return -1

        ci_serial = col("流水号")
        ci_code   = col("证券代码")
        ci_name   = col("证券名称")
        ci_dir    = col("方向")
        ci_status = col("成交状态")
        ci_qty    = col("成交数量")
        ci_price  = col("成交价格")
        ci_amount = col("成交金额")
        ci_time   = col("成交时间")
        ci_account = col("股东代码")

        missing = []
        for label, idx in [("证券代码", ci_code), ("证券名称", ci_name),
                           ("方向", ci_dir), ("成交状态", ci_status),
                           ("成交数量", ci_qty), ("成交价格", ci_price),
                           ("成交时间", ci_time)]:
            if idx < 0:
                missing.append(label)
        if missing:
            raise HTTPException(status_code=400, detail=f"缺少列：{', '.join(missing)}")

        def parse_num(v, default=0.0):
            if v is None or str(v).strip() in ("", "None"):
                return default
            try:
                return float(str(v).strip().replace(",", ""))
            except (ValueError, TypeError):
                return default

        def direction_to_action(direction: str) -> Optional[str]:
            d = str(direction).strip()
            if "买入" in d:
                return "buy"
            elif "卖出" in d:
                return "sell"
            return None

        # ── 先收集所有有效成交，再按 (date, ticker, action) 合并 ───
        raw_records: list[dict] = []

        for row in data_rows:
            if not row or len(row) < 5:
                continue
            cells = list(row)

            raw_code = str(cells[ci_code]).replace("\t", "").replace(" ", "").strip()
            if not raw_code or raw_code in ("", "None"):
                continue

            code6 = raw_code.zfill(6) if raw_code.isdigit() else raw_code
            account = str(cells[ci_account]).replace("\t", "").strip() if ci_account >= 0 and ci_account < len(cells) else ""
            if "深" in account or "SZ" in account.upper():
                ticker = "SZ" + code6
            elif "沪" in account or "SH" in account.upper():
                ticker = "SH" + code6
            elif "港" in account:
                ticker = "HK" + code6
            else:
                ticker = code6

            # 成交状态：撤单跳过
            status = str(cells[ci_status]).strip() if ci_status >= 0 and ci_status < len(cells) else ""
            if "撤单" in status:
                continue

            # 方向 → action
            direction = str(cells[ci_dir]).strip() if ci_dir >= 0 and ci_dir < len(cells) else ""
            action = direction_to_action(direction)
            if action is None:
                continue

            qty = int(parse_num(cells[ci_qty] if ci_qty < len(cells) else None))
            price = parse_num(cells[ci_price] if ci_price < len(cells) else None)
            amount = parse_num(cells[ci_amount] if ci_amount < len(cells) else None, default=qty * price)

            if qty <= 0:
                continue

            # 成交时间 → date
            time_str = str(cells[ci_time]).strip() if ci_time >= 0 and ci_time < len(cells) else ""
            try:
                trade_date = datetime.strptime(time_str[:19], "%Y-%m-%d %H:%M:%S").date()
            except (ValueError, TypeError):
                try:
                    trade_date = datetime.strptime(time_str[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    trade_date = date.today()

            name = str(cells[ci_name]).strip() if ci_name >= 0 and ci_name < len(cells) else ""

            raw_records.append({
                "date": trade_date, "ticker": ticker, "name": name,
                "action": action, "quantity": qty,
                "price": price, "amount": amount,
            })

        if not raw_records:
            raise HTTPException(status_code=400, detail="未解析出有效成交记录（可能全为撤单）")

        # ── 按 (date, ticker, action) 合并：数量/金额累加，加权平均价格 ─
        merged: dict[tuple, dict] = {}
        for r in raw_records:
            key = (r["date"], r["ticker"], r["action"])
            if key not in merged:
                merged[key] = {**r}
            else:
                m = merged[key]
                # 加权平均价格
                total_amount = m["amount"] + r["amount"]
                total_qty    = m["quantity"] + r["quantity"]
                m["price"]   = round(total_amount / total_qty, 3) if total_qty > 0 else 0
                m["quantity"] = total_qty
                m["amount"]  = round(total_amount, 2)

        records: list[TradeRecord] = []
        for key, r in merged.items():
            records.append(TradeRecord(
                date=r["date"], ticker=r["ticker"], name=r["name"],
                action=r["action"], quantity=r["quantity"],
                price=r["price"], amount=r["amount"],
                reason="", created_at=datetime.now(),
            ))

        # 按日期+标的排序
        records.sort(key=lambda r: (r.date, r.ticker, r.action))

        # ── 按日期分组：同日期覆盖，不同日期追加 ─────────────────
        uploaded_dates = set(r.date for r in records)
        existing_df = DataStorage.read_trades()
        dates_to_replace = [d for d in uploaded_dates if d in existing_df["date"].values]
        if dates_to_replace:
            existing_df = existing_df[~existing_df["date"].isin(dates_to_replace)]

        # 生成新记录的 ID（取现有最大 ID + 1，递进分配）
        max_id = int(existing_df["id"].max()) if not existing_df.empty and "id" in existing_df.columns and existing_df["id"].notna().any() else 0
        for i, rec in enumerate(records):
            rec.id = max_id + i + 1
            rec.updated_at = datetime.now()

        merged_df = existing_df if not existing_df.empty else pd.DataFrame()
        new_records_df = pd.DataFrame([r.model_dump() for r in records])
        final_df = pd.concat([merged_df, new_records_df], ignore_index=True) if not merged_df.empty else new_records_df
        final_df.to_parquet(DataStorage.trades_path(), index=False)

        return {
            "status": "ok",
            "count": len(records),
            "dates_replaced": [str(d) for d in dates_to_replace],
            "preview": [
                {"ticker": r.ticker, "name": r.name, "action": r.action,
                 "qty": r.quantity, "price": r.price, "amount": r.amount, "date": str(r.date)}
                for r in records[:5]
            ],
        }

    except BadZipFile:
        raise HTTPException(status_code=400, detail="文件格式错误，请上传有效的 .xlsx 文件")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.delete("/{trade_id}")
def delete_trade(trade_id: int):
    """删除指定调仓记录"""
    df = DataStorage.read_trades()
    if df.empty:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    if "id" not in df.columns or trade_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    df = df[df["id"] != trade_id]
    df.to_parquet(DataStorage.trades_path(), index=False)
    return {"status": "ok"}


@router.put("/{trade_id}")
def update_trade(trade_id: int, trade: TradeRecord):
    """更新指定调仓记录（目前主要用于修改 reason 逻辑字段）"""
    df = DataStorage.read_trades()
    if df.empty or "id" not in df.columns or trade_id not in df["id"].values:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    idx = df[df["id"] == trade_id].index
    if idx.empty:
        raise HTTPException(status_code=404, detail="调仓记录不存在")
    record = trade.model_dump()
    for col, val in record.items():
        if col not in ("id",):
            df.loc[idx[0], col] = val
    df.to_parquet(DataStorage.trades_path(), index=False)
    return {"status": "ok", "id": trade_id}
