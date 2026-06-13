#!/usr/bin/env python3
"""Re-process 12 broken PDF wiki entries for 郭磊宏观."""

import json
import os
import re
import sys
from datetime import datetime

import pymupdf

MINIMAX_API_KEY = open("/tmp/mx_key_clean.txt").read().strip()
MINIMAX_ENDPOINT = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
MODEL = "MiniMax-M2.7"

PDF_DIR = "/Users/bxz/Documents/projects/Argus-Invest/data/kv/郭磊宏观"
WIKI_DIR = "/Users/bxz/Documents/projects/Argus-Invest/wiki/郭磊宏观"
PROGRESS_FILE = "/tmp/guolei_progress.json"

# 12 broken files with their metadata
FILES_CONFIG = [
    {
        "pdf": "【广发宏观贺骁束】高频数据下的1月经济：数量篇.pdf",
        "wiki": "高频数据下的1月经济_数量篇.md",
        "created": "2026/02/02",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的2月经济：价格篇.pdf",
        "wiki": "高频数据下的2月经济_价格篇.md",
        "created": "2026/03/01",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的2月经济：数量篇.pdf",
        "wiki": "高频数据下的2月经济_数量篇.md",
        "created": "2026/03/01",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的3月经济：价格篇.pdf",
        "wiki": "高频数据下的3月经济_价格篇.md",
        "created": "2026/04/02",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的3月经济：数量篇.pdf",
        "wiki": "高频数据下的3月经济_数量篇.md",
        "created": "2026/04/02",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的4月经济：价格篇.pdf",
        "wiki": "高频数据下的4月经济_价格篇.md",
        "created": "2026/05/01",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观贺骁束】高频数据下的4月经济：数量篇.pdf",
        "wiki": "高频数据下的4月经济_数量篇.md",
        "created": "2026/05/01",
        "author": "贺骁束",
        "type": "高频数据",
    },
    {
        "pdf": "【广发宏观郭磊】3月PMI：主要亮点和短板简析.pdf",
        "wiki": "3月PMI_主要亮点和短板简析.md",
        "created": "2026/03/31",
        "author": "郭磊",
        "type": "PMI数据",
    },
    {
        "pdf": "【广发宏观郭磊】一季度经济数据：主要亮点和短板分析.pdf",
        "wiki": "一季度经济数据_主要亮点和短板分析.md",
        "created": "2026/04/16",
        "author": "郭磊",
        "type": "经济分析",
    },
    {
        "pdf": "【广发宏观郭磊】从3月BCI数据看企业端最新状况.pdf",
        "wiki": "从3月BCI数据看企业端最新状况.md",
        "created": "2026/03/26",
        "author": "郭磊",
        "type": "BCI数据",
    },
    {
        "pdf": "【广发宏观郭磊】从PMI和BCI数据看当前内需特征.pdf",
        "wiki": "从PMI和BCI数据看当前内需特征.md",
        "created": "2026/03/04",
        "author": "郭磊",
        "type": "PMI数据",
    },
    {
        "pdf": "【广发宏观郭磊】从PMI和BCI看4月经济情况.pdf",
        "wiki": "从PMI和BCI看4月经济情况.md",
        "created": "2026/04/30",
        "author": "郭磊",
        "type": "PMI数据",
    },
]


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF, focusing on 摘要 section."""
    doc = pymupdf.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    doc.close()

    # Find 摘要 section
    match = re.search(r'摘要[:：]?\s*', full_text)
    if match:
        start = match.start()
        return full_text[start : start + 1500]
    return full_text[:1500]


def call_minimax(text):
    """Call MiniMax API with extracted text."""
    import urllib.request
    import urllib.error

    prompt = f"""你是一个宏观经济分析师。请从以下文本中提取关键信息，生成结构化的摘要。

文本内容：
{text}

请以JSON格式返回，字段如下：
{{
  "abstract": "2-3句话的摘要，概括文章主要结论",
  "key_points": ["关键观点1", "关键观点2", "关键观点3", "关键观点4", "关键观点5"]
}}

要求：
- abstract为2-3句话，简洁明了
- key_points为5个关键观点，每个20-50字
- 不要包含原始数据详情，聚焦结论
- JSON外不要加markdown代码块标记
"""

    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        MINIMAX_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"]
        # Try to parse JSON
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())


def determine_stance(text):
    """Determine stance from text content."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["上行", "增长", "回升", "改善", "向好", "扩张"]):
        return "✅看多"
    if any(k in text_lower for k in ["下行", "回落", "收缩", "下降", "疲软"]):
        return "❌看空"
    return "➡️中性"


def generate_tags(config, abstract, key_points):
    """Generate tags based on content."""
    tags = [config["type"]]
    text = (abstract + " ".join(key_points)).lower()

    if "价格" in config["wiki"]:
        tags.append("价格")
    if "数量" in config["wiki"]:
        tags.append("数量")

    month_map = {"1月": "1月经济", "2月": "2月经济", "3月": "3月经济", "4月": "4月经济"}
    for m, tag in month_map.items():
        if m in config["wiki"]:
            tags.append(tag)

    if any(k in text for k in ["PMI", "采购经理", "制造业"]):
        tags.append("PMI")
    if any(k in text for k in ["BCI", "企业", "营收", "利润"]):
        tags.append("BCI")
    if any(k in text for k in ["地产", "房地产", "销售"]):
        tags.append("房地产")
    if any(k in text for k in ["出口", "外需", "航运"]):
        tags.append("出口")
    if any(k in text for k in ["工业", "生产", "发电"]):
        tags.append("工业生产")
    if any(k in text for k in ["消费", "零售", "耐用品"]):
        tags.append("消费")

    return tags[:6]


def write_wiki(config, abstract, key_points):
    """Write the wiki file."""
    stance = determine_stance(abstract + "".join(key_points))
    tags = generate_tags(config, abstract, key_points)
    today = datetime.now().strftime("%Y-%m-%d")

    content = f'''---
title: "{config["wiki"][:-3]}"
created: {config["created"]}
updated: {today}
type: {config["type"]}
author: {config["author"]}
stance: {stance}
tags: {json.dumps(tags, ensure_ascii=False)}
sources: ["广发宏观", "郭磊宏观茶座"]
confidence: high
contested: false
---

## 摘要
{abstract}

## 关键观点
'''
    for i, point in enumerate(key_points, 1):
        content += f"{i}. {point}\n"

    wiki_path = os.path.join(WIKI_DIR, config["wiki"])
    with open(wiki_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote: {wiki_path}")


def main():
    progress = load_progress()
    processed = set(progress.get("processed", []))

    for cfg in FILES_CONFIG:
        if cfg["wiki"] in processed:
            print(f"Skipping already processed: {cfg['wiki']}")
            continue

        pdf_path = os.path.join(PDF_DIR, cfg["pdf"])
        if not os.path.exists(pdf_path):
            print(f"PDF not found: {pdf_path}")
            continue

        print(f"\nProcessing: {cfg['pdf']}")

        # Extract text
        text = extract_text_from_pdf(pdf_path)
        print(f"  Extracted {len(text)} chars from PDF")

        # Call MiniMax
        result = call_minimax(text)
        abstract = result["abstract"]
        key_points = result["key_points"]
        print(f"  Got abstract: {abstract[:50]}...")

        # Write wiki
        write_wiki(cfg, abstract, key_points)

        # Update progress
        processed.add(cfg["wiki"])
        save_progress({"processed": list(processed)})
        print(f"  Updated progress, total processed: {len(processed)}/12")

    print("\nDone!")


if __name__ == "__main__":
    main()