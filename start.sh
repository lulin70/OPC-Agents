#!/bin/bash
# OPC-Agents 启动脚本

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  启动 OPC-Agents"
echo "========================================"
echo ""

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ 未检测到虚拟环境，直接使用系统 Python${NC}"
else
    echo "🔌 激活虚拟环境..."
    source venv/bin/activate
    echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
fi
echo ""

echo "🔐 检查 API 配置..."
has_key=false
if [ -f ".env" ]; then
    if grep -q "^MOKA_API_KEY=." .env 2>/dev/null && ! grep -q "^MOKA_API_KEY=$" .env 2>/dev/null; then
        echo -e "${GREEN}✓ 检测到 MOKA_API_KEY${NC}"
        has_key=true
    fi
    if grep -q "^GLM_API_KEY=.*" .env 2>/dev/null && ! grep -q "^GLM_API_KEY=$" .env 2>/dev/null; then
        echo -e "${GREEN}✓ 检测到 GLM_API_KEY${NC}"
        has_key=true
    fi
    if grep -q "^OPENAI_API_KEY=." .env 2>/dev/null && ! grep -q "^OPENAI_API_KEY=$" .env 2>/dev/null; then
        echo -e "${GREEN}✓ 检测到 OPENAI_API_KEY${NC}"
        has_key=true
    fi
fi

if [ "$has_key" = false ]; then
    echo -e "${YELLOW}⚠️  未检测到 API Key，将使用模板模式（内容质量有限）${NC}"
    echo "   配置方法：编辑 .env 文件，填入 MOKA_API_KEY"
    echo ""
fi

echo ""
echo "🚀 启动 OPC-Agents 服务..."
echo ""
echo "访问地址：http://localhost:8501"
echo "按 Ctrl+C 停止服务"
echo ""
echo "========================================"
echo ""

streamlit run frontend/app.py
