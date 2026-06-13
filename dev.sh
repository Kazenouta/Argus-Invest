#!/bin/bash
# Argus-Invest 开发服务启动脚本
# 用法: bash dev.sh

set -e
cd "$(dirname "$0")"

PYTHON_BIN=/usr/bin/python3
PYTHONPATH="/Users/bxz/Library/Python/3.9/lib/python/site-packages:$(pwd)/backend"

echo "=== Argus-Invest Dev ==="

# 启动后端（不用 --reload，避免修改代码时崩溃）
echo "[backend] 启动 FastAPI on :8000 ..."
PYTHONPATH="$PYTHONPATH" $PYTHON_BIN -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "[frontend] 启动 Vite on :8888 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "后端: http://localhost:8000 (PID $BACKEND_PID)"
echo "前端: http://localhost:8888 (PID $FRONTEND_PID)"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
