#!/bin/bash

# 选股服务 API 启动脚本

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo "错误: 未找到 Python，请先安装 Python 3.11 或更高版本"
    exit 1
fi

# 检查依赖
if ! python -c "import fastapi" 2>/dev/null; then
    echo "正在安装依赖..."
    pip install -r requirements.txt
fi

# 设置默认参数
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
WORKERS=${WORKERS:-1}

# 启动服务
echo "启动选股服务 API..."
echo "访问地址: http://${HOST}:${PORT}"
echo "API 文档: http://${HOST}:${PORT}/docs"
echo "按 Ctrl+C 停止服务"
echo ""

if [ "$WORKERS" -gt 1 ]; then
    uvicorn api_server:app --host "$HOST" --port "$PORT" --workers "$WORKERS"
else
    python api_server.py
fi

