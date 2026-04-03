#!/bin/bash
# OPC-Agents 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  启动 OPC-Agents"
echo "========================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ 错误：虚拟环境不存在${NC}"
    echo "   请先运行：./install.sh"
    exit 1
fi

# 激活虚拟环境
echo "🔌 激活虚拟环境..."
source venv/bin/activate
echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
echo ""

# 检查配置文件
if [ ! -f "config.toml" ]; then
    echo -e "${RED}❌ 错误：配置文件不存在${NC}"
    echo "   请创建 config.toml 或从 config.toml.sample 复制"
    exit 1
fi

# 检查 API 密钥
echo "🔐 检查配置..."
glm_key=$(grep "^GLM_API_KEY" config.toml | cut -d'"' -f2)
if [ -z "$glm_key" ] || [ "$glm_key" == "your_glm_api_key_here" ]; then
    echo -e "${YELLOW}⚠️  警告：未配置 GLM_API_KEY${NC}"
    echo "   请编辑 config.toml 配置 API 密钥"
    read -p "是否继续？(y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo -e "${GREEN}✓ 配置检查完成${NC}"
echo ""

# 启动服务
echo "🚀 启动 OPC-Agents 服务..."
echo ""
echo "访问地址：http://localhost:5000"
echo "按 Ctrl+C 停止服务"
echo ""
echo "========================================"
echo ""

python web_interface/app.py --debug
