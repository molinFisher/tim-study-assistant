#!/bin/bash
# Tim 学习助手 - 启动脚本
# 使用方法: bash run.sh

echo "================================================"
echo "  Tim 学习助手 v1.0"
echo "  多学科错题管理 | 智能复习 | 统计分析"
echo "================================================"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 创建必要目录
mkdir -p data uploads

# 检查端口是否被占用
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 5000 已被占用，正在释放..."
    kill $(lsof -t -i:5000) 2>/dev/null
    sleep 1
fi

# 启动应用
echo "🚀 正在启动应用..."
echo "📍 访问地址: http://localhost:5000"
echo "📍 按 Ctrl+C 停止服务"
echo ""

python3.11 app.py
