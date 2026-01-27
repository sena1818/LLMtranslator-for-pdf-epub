#!/bin/bash
# 公网部署启动脚本
# 使用 ngrok 内网穿透，让朋友可以访问你的翻译系统

set -e

echo "=========================================="
echo "   AI 翻译系统 - 公网部署启动脚本"
echo "=========================================="
echo ""

# 检查 ngrok 是否安装
if ! command -v ngrok &> /dev/null; then
    echo "❌ ngrok 未安装！请先安装："
    echo ""
    echo "   brew install ngrok"
    echo ""
    echo "安装后，请访问 https://ngrok.com 注册并获取 authtoken："
    echo ""
    echo "   ngrok config add-authtoken YOUR_TOKEN_HERE"
    echo ""
    exit 1
fi

# 检查 ngrok 是否已配置
if ! ngrok config check &> /dev/null; then
    echo "❌ ngrok 未配置！请先配置 authtoken："
    echo ""
    echo "   1. 访问 https://ngrok.com 注册账号"
    echo "   2. 在 Dashboard 获取 Authtoken"
    echo "   3. 运行: ngrok config add-authtoken YOUR_TOKEN_HERE"
    echo ""
    exit 1
fi

# 切换到项目目录
cd "$(dirname "$0")"

# 检查前端构建是否存在
if [ ! -d "frontend_dist" ]; then
    echo "⚠️  前端未构建，正在构建..."
    cd frontend
    npm run build
    cd ..
    cp -r frontend/dist frontend_dist
    echo "✅ 前端构建完成"
fi

echo ""
echo "🚀 启动后端服务器 (后台运行)..."
python run_server.py &
SERVER_PID=$!

# 等待服务器启动
sleep 3

# 检查服务器是否启动成功
if ! curl -s http://localhost:8000/api/health > /dev/null; then
    echo "❌ 服务器启动失败！"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

echo "✅ 后端服务器已启动 (PID: $SERVER_PID)"
echo ""
echo "🌐 启动 ngrok 隧道..."
echo ""
echo "=========================================="
echo "  按 Ctrl+C 停止服务"
echo "=========================================="
echo ""

# 捕获退出信号，清理后台进程
cleanup() {
    echo ""
    echo "🛑 正在停止服务..."
    kill $SERVER_PID 2>/dev/null
    echo "✅ 服务已停止"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 启动 ngrok
ngrok http 8000
