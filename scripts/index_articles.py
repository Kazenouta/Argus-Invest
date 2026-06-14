#!/usr/bin/env python3
"""
一次性索引脚本：把 wiki/**/*.md 和 data/kv/<作者>/articles.parquet 灌进 search.sqlite。

Usage:
    cd backend
    ../.venv/bin/python ../scripts/index_articles.py [--dry-run] [--reset]
"""
import argparse
import sys
import time
from pathlib import Path

# 让 import 能找到 app.*
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config import settings  # noqa: E402
from app.services import search_service  # noqa: E402


def index_wiki(*, reset: bool) -> int:
    """扫 wiki/<作者>/**/*.md，逐篇索引。"""
    wiki_dir = settings.PROJECT_ROOT / "wiki"
    if not wiki_dir.exists():
        print("[wiki] 目录不存在，跳过")
        return 0

    count = 0
    for author_dir in sorted(wiki_dir.iterdir()):
        if not author_dir.is_dir():
            continue
        author = author_dir.name  # 目录名作为作者标识
        for md_path in sorted(author_dir.rglob("*.md")):
            rel = str(md_path.relative_to(settings.PROJECT_ROOT))
            try:
                body = md_path.read_text(encoding="utf-8")
                # 解析 YAML frontmatter（只看前 20 行）
                title, date = "", None
                in_fm = False
                for line in body.splitlines()[:20]:
                    if line.strip() == "---":
                        if not in_fm:
                            in_fm = True
                            continue
                        break
                    if in_fm:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("created:") and not date:
                            date = line.split(":", 1)[1].strip().replace("/", "-")
                search_service.index_article(
                    author=author,
                    source="wiki",
                    title=title,
                    date=date,
                    body=body,
                    file_path=rel,
                )
                print(f"  [wiki] {rel}  ({len(body)} chars)")
                count += 1
            except Exception as e:
                print(f"  [wiki] FAILED {rel}: {e}")
    return count


def index_kv(*, reset: bool) -> int:
    """扫 data/kv/<作者>/articles.parquet，逐行索引 body_text。"""
    import pandas as pd

    kv_dir = settings.KV_DIR
    if not kv_dir.exists():
        print("[kv] 目录不存在，跳过（可能 gitignore 掉了）")
        return 0

    count = 0
    for author_dir in sorted(kv_dir.iterdir()):
        if not author_dir.is_dir():
            continue
        author = author_dir.name
        pq = author_dir / "articles.parquet"
        if not pq.exists():
            continue
        try:
            df = pd.read_parquet(pq)
        except Exception as e:
            print(f"  [kv] {pq} 读取失败: {e}")
            continue
        body_col = "body_text" if "body_text" in df.columns else None
        if not body_col:
            print(f"  [kv] {pq} 无 body_text 列，跳过")
            continue
        for _, row in df.iterrows():
            body = str(row.get(body_col, "") or "")
            if not body.strip():
                continue
            title = str(row.get("title", ""))
            date = str(row.get("published_date") or row.get("ai_发布时间") or "")[:10] or None
            rel = str(pq.relative_to(settings.PROJECT_ROOT)) + "::" + title
            try:
                search_service.index_article(
                    author=author,
                    source="kv",
                    title=title,
                    date=date,
                    body=body,
                    file_path=rel,
                )
                print(f"  [kv]   {rel}  ({len(body)} chars)")
                count += 1
            except Exception as e:
                print(f"  [kv] FAILED {rel}: {e}")
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else "")
    ap.add_argument("--dry-run", action="store_true", help="只列文件不索引")
    ap.add_argument("--reset", action="store_true", help="先清空 search.sqlite 再索引")
    args = ap.parse_args()

    if args.reset:
        db = settings.DATA_DIR / "search.sqlite"
        if db.exists():
            if args.dry_run:
                print(f"[reset] DRY: 将删除 {db}")
            else:
                db.unlink()
                print(f"[reset] 已删除 {db}")

    t0 = time.time()
    n_wiki = index_wiki(reset=args.reset) if not args.dry_run else 0
    n_kv = index_kv(reset=args.reset) if not args.dry_run else 0
    elapsed = time.time() - t0

    print()
    if args.dry_run:
        print("DRY 模式完成，未实际索引")
    else:
        s = search_service.stats()
        print(f"索引完成：{n_wiki} wiki + {n_kv} kv = {n_wiki + n_kv} 篇，耗时 {elapsed:.1f}s")
        print(f"当前总数：{s['total']} 篇")
        for row in s["by_author"]:
            print(f"  - {row['author']}: {row['n']} 篇")
    return 0


if __name__ == "__main__":
    sys.exit(main())
