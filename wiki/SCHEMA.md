# Wiki Schema

## Domain
A股投资研究与交易复盘。

## Conventions
- 文件名: 中文 + 短横线
- 每页 YAML frontmatter
- `[[wikilinks]]` 交叉引用，每页至少 2 个出链
- 更新页面务必更新 `updated` 日期
- 新页面加入 `index.md`
- 每次操作追加 `log.md`

## Frontmatter
```yaml
---
title: 页面标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query
tags: []
sources: []
confidence: high | medium | low
contested: false
---
```

## Tag Taxonomy
- 宏观: debt-cycle, monetary-policy, inflation, geopolitics
- 行业: energy, nonferrous, chemical, new-energy, consumption
- 策略: position, stop-loss, trailing, top-signal, bottom-signal
- 行为: trading-mistake, overtrading, averaging-down, revenge-trading
- 大V: guolei, sida
- 工具: rule-reference, weekly-review
