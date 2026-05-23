"""
Watchlist API router.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
import pandas as pd

from app.models.watchlist import WatchlistRecord, WatchlistSignal, CheckSignalsResponse
from app.services.data_storage import DataStorage

router = APIRouter(prefix="/api/watchlist", tags=["Watchlist"])


def _to_native(obj):
    """将 numpy/pandas 类型递归转换为 Python 原生类型"""
    import numpy as np
    import math
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) or np.isinf(obj) else float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(item) for item in obj]
    return obj


@router.get("/", response_model=list[WatchlistRecord])
def list_watchlist():
    """获取观察池列表"""
    df = DataStorage.read_watchlist()
    if df.empty:
        return []
    # 转换时间字段
    records = []
    for _, row in df.iterrows():
        r = _to_native(row.to_dict())
        if "created_at" in r and isinstance(r["created_at"], str):
            r["created_at"] = r["created_at"]
        if "updated_at" in r and isinstance(r["updated_at"], str):
            r["updated_at"] = r["updated_at"]
        records.append(r)
    return records


@router.post("/")
def add_watchlist(record: WatchlistRecord):
    """新增观察股票"""
    data = record.model_dump(exclude_none=True, mode="json")
    # 移除 id，由 append_watchlist 自动生成
    data.pop("id", None)
    # 优先使用前端传入的时间，否则用当前时间
    data["created_at"] = data.get("created_at") or datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()
    new_id = DataStorage.append_watchlist(data)
    return {"status": "ok", "id": new_id}


@router.put("/{record_id}")
def update_watchlist(record_id: int, patch: dict):
    """更新观察股票"""
    patch["updated_at"] = datetime.now().isoformat()
    success = DataStorage.update_watchlist(record_id, patch)
    if not success:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"status": "ok"}


@router.delete("/{record_id}")
def delete_watchlist(record_id: int):
    """删除观察股票"""
    DataStorage.delete_watchlist(record_id)
    return {"status": "ok"}


@router.post("/check-signals", response_model=CheckSignalsResponse)
def check_watchlist_signals():
    """
    检查所有观察股票的买入信号。

    触发条件：上传持仓文件并点击「检查持仓」时调用。
    逻辑：
    1. 读取所有观察股票
    2. 获取每只股票最新行情（收盘价、涨跌幅等）
    3. 结合规则库买入规则 + 个股 trade_plan 进行匹配
    4. 满足条件 → 写入消息表
    """
    from app.services.market_data import MarketData

    df = DataStorage.read_watchlist()
    if df.empty:
        return CheckSignalsResponse(
            status="ok",
            checked_at=datetime.now().isoformat(),
            total_watchlist=0,
            signals=[],
            messages_created=0,
        )

    signals: list[WatchlistSignal] = []
    messages_created = 0

    for _, row in df.iterrows():
        stock_code = str(row.get("stock_code", ""))
        stock_name = str(row.get("stock_name", stock_code))
        target_buy_price = float(row["target_buy_price"]) if row.get("target_buy_price") else None
        trade_plan = str(row.get("trade_plan", ""))
        attention_level = str(row.get("attention_level", "中"))

        # 获取最新行情
        try:
            market_data = MarketData.get_realtime([stock_code])
            if stock_code in market_data:
                current_price = float(market_data[stock_code].get("current", 0))
            else:
                # fallback：尝试获取最新收盘价
                current_price = MarketData.latest_price(stock_code) or 0.0
        except Exception:
            current_price = 0.0

        if current_price <= 0:
            continue

        # ── RSI(6) 计算 ───────────────────────────────────────────────────────
        rsi6_value: float | None = None
        try:
            from app.services.monitor_service import calculate_indicators
            hist_df = MarketData.get_hist(stock_code, days=80)
            if hist_df is not None and len(hist_df) >= 30:
                indicators = calculate_indicators(hist_df)
                if indicators:
                    rsi6_value = indicators.rsi6
        except Exception:
            rsi6_value = None

        # 计算距目标价百分比
        if target_buy_price and target_buy_price > 0:
            distance_to_target_pct = (current_price - target_buy_price) / target_buy_price * 100
        else:
            distance_to_target_pct = 0.0

        # 判断信号类型（按优先级取最高的一个，其余作为次要信号附在消息中）
        signal_type: str | None = None
        primary_signal_label = ""
        all_triggered_rules: list[str] = []
        message_parts: list[str] = []

        # 信号1：当前价格 <= 目标买入价（买入信号，最优先）
        if target_buy_price and current_price <= target_buy_price:
            signal_type = "buy_signal"
            primary_signal_label = "目标买入信号"
            message_parts.append(
                f"当前价 {current_price:.3f} ≤ 目标买入价 {target_buy_price:.3f}，触发买入信号！"
            )
            all_triggered_rules.append("WL-BUY-001")

        # 信号2：当前价格接近目标买入价（在5%以内）
        elif target_buy_price and 0 < distance_to_target_pct <= 5:
            signal_type = "near_target"
            primary_signal_label = "接近目标价"
            message_parts.append(
                f"当前价 {current_price:.3f} 距离目标买入价 {target_buy_price:.3f} 仅 {distance_to_target_pct:.1f}%，可密切关注"
            )
            all_triggered_rules.append("WL-BUY-002")

        # 信号3：关注度高 + 有明确交易计划 + 价格触发
        elif attention_level == "高" and trade_plan and current_price > 0:
            import re
            price_match = re.findall(r"[<>]?\s*(\d+\.?\d*)", trade_plan)
            if price_match and not signal_type:
                plan_prices = [float(p) for p in price_match]
                if any(current_price <= p for p in plan_prices):
                    signal_type = "buy_signal"
                    primary_signal_label = "交易计划触发"
                    message_parts.append(f"符合交易计划条件（{trade_plan}）")
                    all_triggered_rules.append("WL-BUY-003")

        # 信号4：RSI(6) 超跌信号（所有观察池股票默认都适合 RSI）
        if rsi6_value is not None and rsi6_value < 20:
            if signal_type is None:
                # 无更高优先级信号，顶替为买入信号
                signal_type = "buy_signal"
                primary_signal_label = "RSI超跌信号"
                message_parts.append(
                    f"RSI(6)={rsi6_value:.1f}，短期超跌，关注反弹机会！"
                )
                all_triggered_rules.append("WL-BUY-RSI")
            else:
                # 已触发更高优先级信号，附注 RSI 情况
                message_parts.append(
                    f"（附：RSI(6)={rsi6_value:.1f}）"
                )
                all_triggered_rules.append("WL-BUY-RSI")

        # 生成信号
        if signal_type:
            # tier: 1=最高(红色) 2=次高(橙色) 3=一般(蓝色)
            tier = 1 if signal_type == "buy_signal" else 3 if signal_type == "near_target" else 2

            # 简化 message：去掉冗余的价格重复和规则ID
            brief_msg = message_parts[0] if message_parts else f"关注 {stock_name}({stock_code})"
            # 保留 RSI 附注（有用）
            rsi_note = next((p for p in message_parts if "RSI" in p), "")
            if rsi_note and rsi_note not in brief_msg:
                brief_msg += f"，{rsi_note}"

            signals.append(WatchlistSignal(
                stock_code=stock_code,
                stock_name=stock_name,
                target_buy_price=target_buy_price,
                current_price=current_price,
                distance_to_target_pct=round(distance_to_target_pct, 2),
                signal_type=signal_type,
                signal_label=primary_signal_label,
                tier=tier,
                triggered_rules=all_triggered_rules,
                message=brief_msg,
            ))

            # 写入消息表
            msg_content = f"【{signal_type.replace('_', ' ')}】{stock_name}({stock_code})：{brief_msg}"
            DataStorage.append_message({
                "created_at": datetime.now().isoformat(),
                "msg_type": "buy_signal" if signal_type == "buy_signal" else "rule_trigger",
                "content": msg_content,
                "stock_code": stock_code,
                "is_read": False,
            })
            messages_created += 1

    checked_at = datetime.now().isoformat()
    result = CheckSignalsResponse(
        status="ok",
        checked_at=checked_at,
        total_watchlist=len(df),
        signals=signals,
        messages_created=messages_created,
    )

    # 持久化结果
    DataStorage.save_watchlist_check(
        checked_at=checked_at,
        total_watchlist=len(df),
        signals_data=[s.model_dump() for s in signals],
        messages_created=messages_created,
    )

    return result


@router.get("/check-signals/last")
def get_last_watchlist_check():
    """获取最近一次检查信号的结果（用于页面加载时展示）"""
    result = DataStorage.read_watchlist_check()
    if result is None:
        return {"has_result": False}
    return {"has_result": True, **result}
