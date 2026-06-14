#!/usr/bin/env python3
"""wiki_import.py - 把 data/kv/ 下的素材转成 wiki/ 结构化知识库。

按扩展名自动识别 .html / .pdf，调 LLM 生成摘要 markdown。

Usage:
    # HTML 素材（斯托伯的公众号文章）
    python scripts/wiki_import.py data/kv/斯托伯的天空 wiki/斯托伯的天空

    # PDF 素材（郭磊宏观）
    python scripts/wiki_import.py data/kv/郭磊宏观 wiki/郭磊宏观 --author 郭磊

    # 用 --config 给 PDF 加 per-file 元数据（覆盖 author/type/created）
    python scripts/wiki_import.py data/kv/郭磊宏观 wiki/郭磊宏观 --config scripts/configs/guolei.json
"""
import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pymupdf
from openai import OpenAI

MODEL = "MiniMax-M3"
API_BASE = "https://api.minimaxi.com/v1"
PROGRESS_FILE = Path("/tmp/wiki_import_progress.json")
STANCE_EMOJI = {"看多": "✅看多", "看空": "❌看空", "谨慎": "⚠️谨慎", "中性": "➡️中性"}


def extract_html(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    m = re.search(r'id="js_content"[^>]*>(.*)', text, re.DOTALL)
    if not m:
        return None
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1)))).strip()


def extract_pdf(path: Path) -> str:
    doc = pymupdf.open(path)
    full = "".join(p.get_text() for p in doc)
    doc.close()
    m = re.search(r"摘要[:：]?\s*", full)
    start = m.start() if m else 0
    return full[start:start + 1500]


EXTRACTORS = {".html": extract_html, ".pdf": extract_pdf}

PROMPT = """请为以下文章生成结构化摘要。严格输出 JSON（不要 markdown 包裹），字段：
  summary: 100-200 字摘要
  key_points: 3-5 个关键观点，每点 20-50 字
  stance: 看多/看空/谨慎/中性 之一
  tags: 2-5 个主题标签
  type: 周总结/投资理念/技术分析/书单/主题研究/仓位管理/经济分析/高频数据/PMI数据/BCI数据 之一

文章内容：
{text}"""


def call_llm(text: str) -> dict | None:
    client = OpenAI(api_key=os.environ["MINIMAX_API_KEY"], base_url=API_BASE)
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": PROMPT.format(text=text[:8000])}],
        temperature=0.3,
    )
    content = r.choices[0].message.content
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    m = re.search(r"\{[\s\S]*\}", content)
    return json.loads(m.group()) if m else None


def date_from_filename(name: str) -> str | None:
    m = re.search(r"(\d{4})[_-](\d{1,2})[_-](\d{1,2})", name)
    return f"{m.group(1)}/{m.group(2).zfill(2)}/{m.group(3).zfill(2)}" if m else None


def write_wiki(out_path: Path, source_name: str, data: dict, author: str | None) -> None:
    title = source_name.rsplit(".", 1)[0]
    stance = STANCE_EMOJI.get(data.get("stance", "中性"), data.get("stance", "中性"))

    fm = {
        "title": title,
        "created": date_from_filename(source_name) or datetime.now().strftime("%Y/%m/%d"),
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "type": data.get("type", "周总结"),
        "stance": stance,
        "tags": data.get("tags", []),
        "sources": [author] if author else ["未知"],
        "confidence": "high",
        "contested": "false",
    }
    body = "## 摘要\n\n" + data.get("summary", "") + "\n\n## 关键观点\n\n"
    body += "\n".join(f"{i}. {p}" for i, p in enumerate(data.get("key_points", []), 1))

    fm_str = "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v}"
        for k, v in fm.items()
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"---\n{fm_str}\n---\n\n{body}\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input_dir", type=Path, help="素材目录（.html 或 .pdf）")
    ap.add_argument("output_dir", type=Path, help="wiki 输出目录")
    ap.add_argument("--author", help="作者名（写入 frontmatter sources）")
    ap.add_argument("--config", type=Path, help="可选 JSON 配置，按文件名覆盖 author/type/created")
    ap.add_argument("--dry-run", action="store_true", help="只读 + 解析，不调 LLM")
    args = ap.parse_args()

    if "MINIMAX_API_KEY" not in os.environ and not args.dry_run:
        print("ERROR: MINIMAX_API_KEY 未设置", file=sys.stderr)
        return 1

    # author 缺省时从 input_dir 推断（取最后一级目录名）
    author = args.author or args.input_dir.name

    config: dict = {}
    if args.config:
        for item in json.loads(args.config.read_text()):
            config[item["pdf"]] = item

    progress = json.loads(PROGRESS_FILE.read_text()) if PROGRESS_FILE.exists() else {"processed": []}
    done = set(progress["processed"])

    files = sorted(f for f in args.input_dir.iterdir() if f.suffix.lower() in EXTRACTORS)
    if not files:
        print(f"ERROR: {args.input_dir} 下没有 .html 或 .pdf", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    success = failed = 0

    for i, f in enumerate(files, 1):
        if f.name in done:
            print(f"[{i}/{len(files)}] 跳过 {f.name}")
            continue
        print(f"[{i}/{len(files)}] {f.name}")

        text = EXTRACTORS[f.suffix.lower()](f)
        if not text:
            print("  无文本，跳过")
            failed += 1
            continue

        if args.dry_run:
            print(f"  DRY: 文本 {len(text)} 字符")
            success += 1
            continue

        result = call_llm(text)
        if not result:
            print("  LLM 无返回，跳过")
            failed += 1
            continue

        cfg = config.get(f.name, {})
        if "type" in cfg:
            result["type"] = cfg["type"]
        # cfg.get("author") 优先；其次用 main 顶部推断的 author（args.author or input_dir.name）
        author = cfg.get("author") or author

        out_path = args.output_dir / f"{f.stem}.md"
        write_wiki(out_path, f.name, result, author=author)
        print(f"  → {out_path}")
        success += 1

        done.add(f.name)
        progress["processed"] = list(done)
        PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2))
        time.sleep(1.3)

    print(f"\n完成: {success} 成功 / {failed} 失败 / {len(done)} 已处理总计")
    return 0


if __name__ == "__main__":
    sys.exit(main())
