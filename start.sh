#!/bin/bash
# Argus-Invest 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "🚀 启动 Argus-Invest..."

# 启动后端
echo "📡 启动后端服务 (FastAPI)..."
cd "$BACKEND_DIR"
PYTHONPATH="$BACKEND_DIR" /Users/bxz/Library/Python/3.9/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "后端 PID: $BACKEND_PID"

# 等待后端就绪
sleep 3

# 启动前端
echo "🖥️  启动前端服务 (Vue)..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"

echo ""
echo "✅ 服务已启动："
echo "   后端 API：http://localhost:8000"
echo "   前端界面：http://localhost:5173"
echo "   API 文档：http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止所有服务';" SIGINT SIGTERM
wait
