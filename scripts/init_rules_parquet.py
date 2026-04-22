"""
初始化 rules.parquet：将 v2_weakness 默认规则库写入数据文件
"""
import sys
sys.path.insert(0, '/Users/bxz/Documents/projects/Argus-Invest/backend')

from pathlib import Path
from datetime import date
from app.models.rules import RuleLibrary
from app.services.data_storage import DataStorage
from app.config import settings
import pandas as pd

library = RuleLibrary.default_rules()
records = [r.model_dump() for r in library.rules]
df = pd.DataFrame(records)
df['version'] = library.version
df['last_updated'] = date.today()

output_path = settings.RULES_DIR / "rules.parquet"
output_path.parent.mkdir(parents=True, exist_ok=True)
DataStorage.write_parquet(output_path, df)

print(f"已写入 {len(df)} 条规则到 {output_path}")
print(f"版本: {library.version}")
print("\n分类统计:")
for cat, count in df.groupby('category').size().items():
    print(f"  {cat}: {count}条")