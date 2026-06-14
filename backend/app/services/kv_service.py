"""
大V观点服务 — 本地 PDF 文件 + AI 提炼关键信息

数据流：
  PDF 文件（用户手动保存到 data/kv/{account}/）→ pypdf 全文提取 →
  MiniMax AI 提炼（核心观点/关键数据/情绪/逻辑）→ Parquet 存储 → API 返回

大V配置：
  郭磊宏观茶座 (guolei) → data/kv/郭磊宏观/
"""
import os
import re
import json
import time
import asyncio
import datetime as dt
from typing import Any, Optional
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings
from app.utils import get_minimax_key


# ── 大V配置 ──────────────────────────────────────────────────────────────────

class KvAccount:
    def __init__(self, name: str, display_name: str, pdf_dir: str):
        self.name = name
        self.display_name = display_name
        self.pdf_dir = pdf_dir   # PDF 文件所在目录


KV_ACCOUNTS: dict[str, KvAccount] = {
    "guolei": KvAccount(
        name="guolei",
        display_name="郭磊宏观",
        pdf_dir="郭磊宏观",
    ),
}

KV_DATA_DIR = settings.DATA_DIR / "kv"
KV_PARQUET_NAME = "articles.parquet"


# ── MiniMax API ──────────────────────────────────────────────────────────────

_BASE_URL = settings.AI_API_BASE
_AI_MODEL = settings.AI_MODEL


def _get_minimax_key() -> str:
    """兼容旧调用：复用 utils.get_minimax_key"""
    return get_minimax_key()


# ── PDF 提取 ─────────────────────────────────────────────────────────────────

def _extract_pdf_text(pdf_path: Path) -> str:
    """用 pypdf 提取 PDF 全文"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(str(pdf_path))
        texts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
        return "\n".join(texts)
    except Exception as e:
        print(f"[KvService] PDF extraction failed {pdf_path}: {e}")
        return ""


def _parse_filename(title: str) -> dict[str, Any]:
    """
    从文件名解析标题和发布日期。
    文件名格式：【广发宏观郭磊】3月PMI：主要亮点和短板简析.pdf
    或：郭磊宏观茶座_2026-03-31_3月PMI简析.pdf
    尽可能从中提取月份/日期信息。
    """
    # 去掉.pdf 后缀
    name = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE).strip()
    # 去掉前缀【广发宏观郭磊】等
    name = re.sub(r'^【[^】]+】', '', name).strip()

    # 尝试从内容中找日期（形如 2026年3月31日、2026-03-31）
    # 先留空，由 AI 从正文中推断
    return {"clean_title": name, "inferred_date": ""}


def _parse_date_from_body(body_text: str) -> str:
    """
    从 PDF 正文提取第一条日期，格式如 '郭磊 2026年3月26日 19:11'。
    返回 YYYY-MM-DD 或空字符串。
    PDF 可能使用 CJK Radicals Supplement 字符（⽉=U+2F49, ⽇=U+2F47）而非标准汉字。
    """
    # 只在前 5 行中查找
    lines = body_text.split('\n')[:5]
    for line in lines:
        # CJK Radicals Supplement
        m = re.search(r'(\d{4})年(\d{1,2})⽉(\d{1,2})⽇', line)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            return f"{year}-{int(month):02d}-{int(day):02d}"
        # 标准汉字 fallback
        m2 = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', line)
        if m2:
            year, month, day = m2.group(1), m2.group(2), m2.group(3)
            return f"{year}-{int(month):02d}-{int(day):02d}"
    return ""


# ── AI 提炼（基于 PDF 正文） ─────────────────────────────────────────────────

async def _ai_analyze_pdf(title: str, body_text: str) -> dict[str, Any]:
    """
    用 MiniMax M3 对 PDF 正文进行深度分析，
    提炼结构化字段，包括关键经济指标。
    """
    api_key = _get_minimax_key()
    if not api_key:
        return _empty_analysis("未配置 MINIMAX_API_KEY")

    # PDF 全文可能很长，截取前 8000 字发给 AI（足够提取关键信息）
    snippet = body_text[:8000].strip()

    user_prompt = (
        "你是一个专业的A股投资研究助手。以下是一篇郭磊宏观团队的微信公众号文章全文，"
        "请提炼出对投资有价值的结构化信息。\n\n"
        f"文章标题：{title}\n\n"
        f"正文内容：\n{snippet}\n\n"
        "请严格按以下JSON格式输出（只输出JSON，不要其他文字）：\n"
        "{\n"
        '  "核心观点": "一句话概括作者的核心判断（50字以内）",\n'
        '  "情绪倾向": "看多|中性|看空之一",\n'
        '  "情绪说明": "简要说明情绪判断依据（30字以内）",\n'
        '  "发布时间": "从文章中推断的发布日期，格式YYYY-MM-DD，若无法确定则为空字符串",\n'
        '  "关键指标": [\n'
        '    {"name": "指标名称", "value": "数值或变化", "说明": "简要说明"}],\n'
        '  "主要逻辑": "作者的主要逻辑依据（150字以内）",\n'
        '  "政策相关": ["相关政策关键词列表，若无则为空数组"],\n'
        '  "风险提示": "作者提到的风险点，或空字符串",\n'
        '  "相关市场": ["相关市场或板块，如：原油、黄金、大盘、港股、消费等"],\n'
        '  "投资启示": "对A股投资的直接启示（100字以内）"\n'
        "}\n"
    )

    payload = {
        "model": _AI_MODEL,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 1200,
        "temperature": 0.3,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
            resp = await client.post(
                f"{_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )

        if resp.status_code != 200:
            return _empty_analysis(f"M3 API 返回 {resp.status_code}: {resp.text[:100]}")

        result_data = resp.json()
        content_list = result_data.get("content", [])
        raw_text = ""
        if isinstance(content_list, list):
            for c in content_list:
                if c.get("type") == "text":
                    raw_text = c["text"]
                    break

        parsed = _parse_json(raw_text)
        if parsed:
            return parsed
        return _empty_analysis("AI 返回格式解析失败")

    except Exception as e:
        return _empty_analysis(f"请求异常: {e}")


def _parse_json(text: str) -> Optional[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^\w*\s*", "", text).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None


def _empty_analysis(reason: str) -> dict[str, Any]:
    return {
        "核心观点": f"（AI分析失败: {reason}）",
        "情绪倾向": "中性",
        "情绪说明": "",
        "发布时间": "",
        "关键指标": [],
        "主要逻辑": "",
        "政策相关": [],
        "风险提示": "",
        "相关市场": [],
        "投资启示": "",
    }


# ── Parquet 存储 ─────────────────────────────────────────────────────────────

def _get_parquet_path(account_name: str) -> Path:
    d = KV_DATA_DIR / account_name
    d.mkdir(parents=True, exist_ok=True)
    return d / KV_PARQUET_NAME


def _get_pdf_dir(account: KvAccount) -> Path:
    return KV_DATA_DIR / account.pdf_dir


_COLUMNS = [
    "title", "published_date", "fetched_date",
    "body_text", "source", "account_name",
    "ai_核心观点", "ai_情绪倾向", "ai_情绪说明",
    "ai_发布时间", "ai_关键指标", "ai_主要逻辑",
    "ai_政策相关", "ai_风险提示", "ai_相关市场",
    "ai_投资启示", "processed",
]


def _load_articles(account_name: str) -> pd.DataFrame:
    path = _get_parquet_path(account_name)
    if path.exists():
        try:
            df = pd.read_parquet(path)
            if not df.empty:
                return df
        except Exception:
            pass
    return _empty_df()


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=_COLUMNS)


def _save_articles(account_name: str, df: pd.DataFrame) -> None:
    path = _get_parquet_path(account_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


# ── 主服务逻辑 ───────────────────────────────────────────────────────────────

async def scan_and_analyze_pdf(account_name: str, pdf_path: Path, title: str) -> dict[str, Any]:
    """
    扫描单个 PDF → 提取正文 → AI 分析 → 返回记录
    """
    print(f"[KvService] Processing: {title}", flush=True)

    # 1. 提取正文
    body_text = _extract_pdf_text(pdf_path)
    if not body_text.strip():
        return {"title": title, "success": False, "error": "PDF 文字提取失败"}

    # 2. AI 分析
    ai_result = await _ai_analyze_pdf(title, body_text)

    # 3. 日期 fallback：AI 返回空时从正文自动解析
    ai_date = ai_result.get("发布时间", "").strip()
    auto_date = _parse_date_from_body(body_text)
    published_date = ai_date if ai_date else auto_date

    record = {
        "title": title,
        "published_date": published_date,
        "fetched_date": dt.date.today().isoformat(),
        "body_text": body_text,
        "source": KV_ACCOUNTS[account_name].display_name,
        "account_name": account_name,
        "ai_核心观点": ai_result.get("核心观点", ""),
        "ai_情绪倾向": ai_result.get("情绪倾向", "中性"),
        "ai_情绪说明": ai_result.get("情绪说明", ""),
        "ai_发布时间": ai_result.get("发布时间", ""),
        "ai_关键指标": json.dumps(ai_result.get("关键指标", []), ensure_ascii=False),
        "ai_主要逻辑": ai_result.get("主要逻辑", ""),
        "ai_政策相关": json.dumps(ai_result.get("政策相关", []), ensure_ascii=False),
        "ai_风险提示": ai_result.get("风险提示", ""),
        "ai_相关市场": json.dumps(ai_result.get("相关市场", []), ensure_ascii=False),
        "ai_投资启示": ai_result.get("投资启示", ""),
        "processed": True,
    }
    return {"title": title, "success": True, "record": record}


# ── 并发保护 ────────────────────────────────────────────────────────────────
_refresh_lock = asyncio.Lock()


async def refresh_and_summarize(account_name: str, max_new: int = 20) -> dict[str, Any]:
    """
    扫描 PDF 目录 → 找出未处理的 PDF → AI 分析 → 存入 Parquet → 返回结果
    asyncio.Lock 保证同一 worker 内串行化处理。
    """
    async with _refresh_lock:
        account = KV_ACCOUNTS.get(account_name)
        if not account:
            return {"success": False, "error": f"未知账号: {account_name}"}

        pdf_dir = _get_pdf_dir(account)
        if not pdf_dir.exists():
            return {"success": False, "error": f"PDF 目录不存在: {pdf_dir}"}

        pdf_files = sorted(pdf_dir.glob("*.pdf"))
        guolei_pdfs = [f for f in pdf_files if "郭磊" in f.name]
        if not guolei_pdfs:
            return {"success": False, "error": f"目录中没有郭磊的 PDF 文件: {pdf_dir}"}

        df_existing = _load_articles(account_name)
        existing_titles = set(df_existing["title"].tolist()) if not df_existing.empty else set()

        # 找出之前 AI 分析失败的文章，重新处理
        failed_titles = set()
        if not df_existing.empty:
            for _, row in df_existing.iterrows():
                ai_field = str(row.get("ai_核心观点", ""))
                if ai_field.startswith("（AI分析失败") or not ai_field.strip():
                    failed_titles.add(row["title"])

        to_process = [f for f in guolei_pdfs
                      if f.name not in existing_titles or f.name in failed_titles]
        if not to_process:
            return {
                "success": True,
                "account": account.display_name,
                "total_articles": len(pdf_files),
                "new_articles": 0,
                "processed": [],
                "message": f"所有 {len(pdf_files)} 篇 PDF 均已分析，无需更新",
            }

        if max_new and len(to_process) > max_new:
            to_process = to_process[:max_new]

        print(f"[KvService] Found {len(pdf_files)} PDFs, {len(to_process)} to process", flush=True)

        processed_records = []
        for pdf_path in to_process:
            result = await scan_and_analyze_pdf(account_name, pdf_path, pdf_path.name)
            if result.get("success"):
                processed_records.append(result["record"])
            await asyncio.sleep(4)

        if processed_records:
            df_new = pd.DataFrame(processed_records)
            df_updated = pd.concat([df_existing, df_new], ignore_index=True)
            _save_articles(account_name, df_updated)

        return {
            "success": True,
            "account": account.display_name,
            "total_articles": len(pdf_files),
            "new_articles": len(processed_records),
            "processed": processed_records,
        }


def get_articles(account_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """读取某账号所有文章，按发布日期倒序"""
    df = _load_articles(account_name)
    if df.empty:
        return []

    # 按发布时间倒序
    date_col = "ai_发布时间" if "ai_发布时间" in df.columns else "published_date"
    if date_col in df.columns:
        df = df.sort_values(date_col, ascending=False, na_position="last")
    else:
        df = df.sort_values("fetched_date", ascending=False)

    df = df.head(limit)
    records = df.to_dict(orient="records")

    # 反序列化 JSON 字段
    list_fields = ("ai_关键指标", "ai_政策相关", "ai_相关市场")
    for r in records:
        for field in list_fields:
            val = r.get(field, "")
            if isinstance(val, str):
                try:
                    r[field] = json.loads(val)
                except Exception:
                    r[field] = []
            elif not isinstance(val, list):
                r[field] = []
        # 保证字段存在
        for field in list_fields:
            if field not in r:
                r[field] = []

    return records


def get_indicator_timeline(account_name: str) -> list[dict[str, Any]]:
    """
    返回所有文章中的关键指标时间序列，供前端画折线图。
    返回格式: [{date, title, indicators: [{name, value, 说明}]}]
    """
    articles = get_articles(account_name, limit=100)
    timeline = []
    for art in articles:
        date = art.get("ai_发布时间") or art.get("published_date", "")
        if not date:
            continue
        indicators = art.get("ai_关键指标", [])
        if not isinstance(indicators, list):
            indicators = []
        timeline.append({
            "date": date,
            "title": art.get("title", ""),
            "published_date": art.get("published_date", ""),
            "indicators": indicators,
            "情绪": art.get("ai_情绪倾向", ""),
            "核心观点": art.get("ai_核心观点", ""),
        })
    return timeline
