#!/usr/bin/env python3
"""
日线数据全量同步脚本（后台运行）。
用法: python3 sync_daily_bars.py [start_year] [workers]
"""
import sys, os, logging, time
from pathlib import Path

# 加载项目路径
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("PYTHONPATH", str(Path(__file__).parent))

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "daily_bar_sync.log"),
        logging.StreamHandler(),
    ],
)

from app.services.daily_bar_service import sync_full, get_coverage

def progress(done, total, ticker, note):
    pct = done / total * 100
    bar = "#" * int(pct / 2) + "-" * (50 - int(pct / 2))
    sys.stdout.write(f"\r[{bar}] {pct:.1f}% ({done}/{total}) {ticker} {note}   ")
    sys.stdout.flush()

start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16

print(f"开始全量同步 {start_year} 至今，并发数={workers}")
t0 = time.time()

result = sync_full(start_year=start_year, workers=workers, progress_callback=progress)

elapsed = time.time() - t0
print(f"\n\n同步完成！耗时 {elapsed/60:.1f} 分钟")
print(f"成功: {result['done']} 只，失败: {result['failed']} 只")
print(f"各年保存行数: {result['saved']}")
print(f"前20条错误: {result['errors'][:5]}")
print(f"\n最终覆盖情况: {get_coverage()}")
