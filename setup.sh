#!/bin/bash
# ============================================================
# 接口代码生成平台 - Linux/Mac 安装脚本
# ============================================================

set -e

echo "============================================================"
echo "接口代码生成平台 - 自动安装"
echo "============================================================"
echo ""

# 检查 Python 版本
echo "检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ 错误: 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ 找到 Python $PYTHON_VERSION"

# 创建虚拟环境
echo ""
echo "创建虚拟环境..."
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo "✓ 虚拟环境创建成功"
else
    echo "✓ 虚拟环境已存在"
fi

# 激活虚拟环境
echo ""
echo "激活虚拟环境..."
source venv/bin/activate
echo "✓ 虚拟环境已激活"

# 安装依赖
echo ""
echo "安装 Python 依赖..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✓ 依赖安装完成"

# 创建必要目录
echo ""
echo "创建必要目录..."
mkdir -p data output
echo "✓ 目录创建完成"

# 初始化数据库
echo ""
echo "初始化数据库..."
$PYTHON seed_data/init_db.py

echo ""
echo "============================================================"
echo "✓ 安装完成！"
echo "============================================================"
echo ""
echo "启动服务:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "或者使用 Docker:"
echo "  docker-compose up -d"
echo ""
echo "访问地址: http://localhost:5001"
echo "默认账户: admin / admin123"
echo "============================================================"
