# Argus-Invest 项目文档

## 项目概述
Argus-Invest 是一个量化投资研究平台，使用 FastAPI 后端 + Vue 前端架构。

## 技术栈
- **后端**: FastAPI (Python), Parquet 数据存储
- **前端**: Vue 3 + TypeScript + Vite
- **数据**: Parquet 文件存储 (`data/` 目录)
- **市场数据**: BaoStock 直连

## 项目结构
```
backend/
  app/
    main.py          - FastAPI 应用入口
    models/          - Pydantic 数据模型
    routers/         - API 路由
    services/        - 业务逻辑
data/
  rules/             - 规则数据 (parquet)
  user/              - 用户数据 (portfolio, trades)
  kv/                - Key-Value 存储 (用户研究笔记)
  market/            - 市场数据
frontend/
  src/
    api/             - API 调用层
    layout/          - 布局组件
    router/          - Vue Router 配置
    views/           - 页面组件
```

## 关键决策与背景
- 市场 AI 服务有超时保护机制
- 使用 BaoStock 直连而非第三方 API
- 数据以 Parquet 格式存储便于查询和分析
- 已删除 persona 和 quant 视图，聚焦核心功能

## 常用命令
- 启动开发服务器: `bash dev.sh`
- 后端依赖: `pip install -r backend/requirements.txt`
- 前端依赖: `cd frontend && npm install`

## 编码规范
- Python 遵循 PEP 8
- Vue 组件使用 Composition API
- API 路由使用 FastAPI 的 APIRouter
- Parquet 文件操作统一通过 service 层

## 网络代理
网络命令超时或长时间无响应时，依次尝试：
1. 本地: `export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890`
2. 备用: `export http_proxy=http://ark:CVXj8aS=9jm8B6bn5IfY@192.168.123.101:7890 https_proxy=http://ark:CVXj8aS=9jm8B6bn5IfY@192.168.123.101:7890`

## 用户偏好
- 使用中文交流
- 代码注释和 commit message 使用中文
- 优先保持代码简洁，避免过度设计
