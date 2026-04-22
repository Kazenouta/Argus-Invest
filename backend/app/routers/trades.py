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
from app.services.trade_analysis_service import analyze_trades


def _clear_proxy():
    import os
    for k in ['http_proxy', 'https_proxy', 'all_proxy',
              'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
        os.environ.pop(k, None)

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


def _infer_ticker(code6: str, account: str = "") -> str:
    """根据代码和股东账号推断交易所前缀"""
    # 有股东代码时优先用它判断
    if account:
        acc = account.replace("\t", "").strip().upper()
        if "深" in acc or "SZ" in acc or acc.startswith("A") and not any(x in acc for x in ["沪", "SH"]):
            return "SZ" + code6
        if "沪" in acc or "SH" in acc:
            return "SH" + code6
        if "港" in acc:
            return "HK" + code6
    # 无股东代码时，根据代码首位推断
    if code6.isdigit():
        first = code6[0]
        if first in ("5", "6", "9", "11", "13", "15"):
            return "SH" + code6
        if first in ("0", "1", "2", "3", "4", "8"):
            return "SZ" + code6
        if first == "8" and len(code6) >= 5:
            return "HK" + code6
    return code6


def _parse_num(v, default=0.0) -> float:
    if v is None or str(v).strip() in ("", "None"):
        return default
    try:
        return float(str(v).strip().replace(",", ""))
    except (ValueError, TypeError):
        return default


def _direction_to_action(direction: str) -> Optional[str]:
    d = str(direction).strip()
    if "买入" in d:
        return "buy"
    if "卖出" in d:
        return "sell"
    return None


def _ticker_from_code(raw_code: str) -> str:
    code = raw_code.replace("\t", "").replace(" ", "").strip()
    code6 = code.zfill(6) if code.isdigit() else code
    return _infer_ticker(code6)


@router.post("/upload-xlsx")
def upload_trades_xlsx(
    file: UploadFile = File(..., description="当日成交 xlsx 文件"),
):
    """
    解析券商格式当日成交 Excel，批量追加调仓记录。

    支持两种格式：
    - 旧格式（成交明细）：13列，有「流水号/方向/成交状态/成交时间/股东代码」
    - 新格式（成交汇总）：7列，有「证券代码/证券名称/买卖类别/成交类型/成交数量」，
      无成交时间和股东代码，日期从「查询日期」表头行获取
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

        # ── 检测格式：找表头行，并判断是哪一种 ──────────────────────
        header_row_idx = None
        headers = []
        format_type = None  # "detail" | "summary"

        for i, row in enumerate(rows):
            if not row:
                continue
            first = str(row[0]).strip() if row[0] else ""
            if first in ("流水号", "委托号", "成交编号"):
                header_row_idx = i
                headers = [str(c).strip() if c else "" for c in row]
                format_type = "detail"
                break
            # 新格式（汇总）：表头直接是证券代码/证券名称/买卖类别
            if first in ("证券代码",) and len(row) >= 5:
                # 进一步确认：第3列是买卖类别
                h3 = str(row[2]).strip() if len(row) > 2 else ""
                if "买卖类别" in h3 or "方向" in h3:
                    header_row_idx = i
                    headers = [str(c).strip() if c else "" for c in row]
                    format_type = "summary"
                    break

        if header_row_idx is None:
            raise HTTPException(status_code=400, detail="未找到表头行（需以「流水号」或「证券代码」开头）")

        # ── 从表头第4行（index=3）提取查询日期 ──────────────────────
        query_date = date.today()
        if len(rows) >= 4 and rows[3]:
            date_str = str(rows[3][1]).strip() if rows[3][1] else ""
            try:
                query_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        data_rows = rows[header_row_idx + 1:]

        def col(keyword: str) -> int:
            for j, h in enumerate(headers):
                if keyword in h:
                    return j
            return -1

        # ── 旧格式（成交明细）解析 ────────────────────────────────
        if format_type == "detail":
            ci_code    = col("证券代码")
            ci_name    = col("证券名称")
            ci_dir     = col("方向")
            ci_status  = col("成交状态")
            ci_qty     = col("成交数量")
            ci_price   = col("成交价格")
            ci_amount  = col("成交金额")
            ci_time    = col("成交时间")
            ci_account = col("股东代码")

            missing = [l for l, idx in [
                ("证券代码", ci_code), ("证券名称", ci_name),
                ("方向", ci_dir), ("成交数量", ci_qty),
                ("成交价格", ci_price),
            ] if idx < 0]
            if missing:
                raise HTTPException(status_code=400, detail=f"缺少列：{', '.join(missing)}")

            raw_records: list[dict] = []
            for row in data_rows:
                if not row or len(row) < 5:
                    continue
                cells = list(row)

                raw_code = str(cells[ci_code]).replace("\t", "").replace(" ", "").strip() if ci_code >= 0 and ci_code < len(cells) else ""
                if not raw_code or raw_code in ("", "None"):
                    continue

                code6 = raw_code.zfill(6) if raw_code.isdigit() else raw_code
                account = str(cells[ci_account]).replace("\t", "").strip() if ci_account >= 0 and ci_account < len(cells) else ""
                ticker = _infer_ticker(code6, account)

                status = str(cells[ci_status]).strip() if ci_status >= 0 and ci_status < len(cells) else ""
                if "撤单" in status:
                    continue

                direction = str(cells[ci_dir]).strip() if ci_dir >= 0 and ci_dir < len(cells) else ""
                action = _direction_to_action(direction)
                if action is None:
                    continue

                qty    = int(_parse_num(cells[ci_qty] if ci_qty < len(cells) else None))
                price  = _parse_num(cells[ci_price] if ci_price < len(cells) else None)
                amount = _parse_num(cells[ci_amount] if ci_amount < len(cells) else None, default=qty * price)

                if qty <= 0:
                    continue

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
                    "action": action, "quantity": qty, "price": price, "amount": amount,
                })

            if not raw_records:
                raise HTTPException(status_code=400, detail="未解析出有效成交记录（可能全为撤单）")

        # ── 新格式（成交汇总）解析 ─────────────────────────────────
        else:
            ci_code   = col("证券代码")
            ci_name   = col("证券名称")
            ci_dir    = col("买卖类别")   # 新格式用「买卖类别」而非「方向」
            ci_type   = col("成交类型")
            ci_qty    = col("成交数量")
            ci_price  = col("成交价格")
            ci_amount = col("成交金额")

            missing = [l for l, idx in [
                ("证券代码", ci_code), ("证券名称", ci_name),
                ("买卖类别", ci_dir), ("成交数量", ci_qty),
                ("成交价格", ci_price),
            ] if idx < 0]
            if missing:
                raise HTTPException(status_code=400, detail=f"缺少列：{', '.join(missing)}")

            raw_records: list[dict] = []
            for row in data_rows:
                if not row or len(row) < 5:
                    continue
                cells = list(row)

                raw_code = str(cells[ci_code]).replace("\t", "").replace(" ", "").strip() if ci_code >= 0 and ci_code < len(cells) else ""
                if not raw_code or raw_code in ("", "None"):
                    continue

                ticker = _ticker_from_code(raw_code)

                direction = str(cells[ci_dir]).strip() if ci_dir >= 0 and ci_dir < len(cells) else ""
                action = _direction_to_action(direction)
                if action is None:
                    continue

                qty    = int(_parse_num(cells[ci_qty] if ci_qty < len(cells) else None))
                price  = _parse_num(cells[ci_price] if ci_price < len(cells) else None)
                amount = _parse_num(cells[ci_amount] if ci_amount < len(cells) else None, default=qty * price)

                if qty <= 0:
                    continue

                name = str(cells[ci_name]).strip() if ci_name >= 0 and ci_name < len(cells) else ""
                raw_records.append({
                    "date": query_date, "ticker": ticker, "name": name,
                    "action": action, "quantity": qty, "price": price, "amount": amount,
                })

            if not raw_records:
                raise HTTPException(status_code=400, detail="未解析出有效成交记录")

        # ── 合并：按 (date, ticker, action) 累加数量/金额，加权均价 ─
        merged: dict[tuple, dict] = {}
        for r in raw_records:
            key = (r["date"], r["ticker"], r["action"])
            if key not in merged:
                merged[key] = {**r}
            else:
                m = merged[key]
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

        records.sort(key=lambda r: (r.date, r.ticker, r.action))

        # ── 同日期覆盖，不同日期追加 ──────────────────────────────
        uploaded_dates = set(r.date for r in records)
        existing_df = DataStorage.read_trades()
        dates_to_replace = [d for d in uploaded_dates if d in existing_df["date"].values]
        if dates_to_replace:
            existing_df = existing_df[~existing_df["date"].isin(dates_to_replace)]

        max_id = int(existing_df["id"].max()) if not existing_df.empty and "id" in existing_df.columns and existing_df["id"].notna().any() else 0
        for i, rec in enumerate(records):
            rec.id = max_id + i + 1
            rec.updated_at = datetime.now()

        merged_df = existing_df if not existing_df.empty else pd.DataFrame()
        new_records_df = pd.DataFrame([r.model_dump() for r in records])
        final_df = pd.concat([merged_df, new_records_df], ignore_index=True) if not merged_df.empty else new_records_df
        final_df.to_parquet(DataStorage.trades_path(), index=False)

        # 上传新记录后清除分析缓存（下次分析需要重新计算）
        DataStorage.clear_analysis_cache()

        return {
            "status": "ok",
            "format": format_type,
            "date": str(query_date),
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
    DataStorage.clear_analysis_cache()
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
    DataStorage.clear_analysis_cache()
    return {"status": "ok", "id": trade_id}


@router.get("/analyze")
def get_trade_analysis(
    refresh: bool = Query(False, description="强制重新分析（忽略缓存）"),
):
    """
    分析最近5个交易日内的调仓记录（买入时机、逻辑完整性、信号依据等）。
    结果自动缓存到后端，下次调用（refresh=false）直接返回缓存，秒开。
    传入 refresh=true 可强制重新计算。
    """
    # 1. 尝试从缓存加载
    if not refresh:
        cached = DataStorage.load_analysis_cache()
        if cached is not None:
            return cached

    # 2. 计算最近5个交易日区间
    from datetime import timedelta
    trading_date = DataStorage._get_latest_trading_date() if hasattr(DataStorage, '_get_latest_trading_date') else None
    if trading_date is None:
        import baostock as bs
        _clear_proxy()
        bs.login()
        sh_df = bs.query_history_k_data_plus('sh.000001',
            'date', start_date='2020-01-01', end_date='2099-12-31',
            frequency='d', adjustflag='3')
        dates = []
        while sh_df.error_code == '0' and sh_df.next():
            dates.append(sh_df.get_row_data()[0])
        bs.logout()
        dates.sort()
        trading_date = dates[-1] if dates else str(date.today())

    if isinstance(trading_date, str):
        end_dt = date.fromisoformat(trading_date)
    else:
        end_dt = trading_date

    # 往前数5个交易日
    _all_dates = []
    try:
        import baostock as bs
        _clear_proxy()
        bs.login()
        sh_df = bs.query_history_k_data_plus('sh.000001',
            'date', start_date=(end_dt - timedelta(days=30)).isoformat(),
            end_date=end_dt.isoformat(), frequency='d', adjustflag='3')
        while sh_df.error_code == '0' and sh_df.next():
            _all_dates.append(sh_df.get_row_data()[0])
        bs.logout()
    except Exception:
        pass

    if len(_all_dates) >= 5:
        start_dt = _all_dates[-5]
        end_str = _all_dates[-1]
    else:
        end_str = end_dt.isoformat()
        start_dt = (end_dt - timedelta(days=14)).isoformat()

    result = analyze_trades(start_date=date.fromisoformat(start_dt), end_date=date.fromisoformat(end_str))

    # 3. 保存缓存
    DataStorage.save_analysis_cache(result)
    return result
