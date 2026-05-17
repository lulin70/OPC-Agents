#!/bin/bash
# OPC-Agents 一键安装脚本
# 适用于 macOS/Linux 系统

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  OPC-Agents 一键安装脚本"
echo "========================================"
echo ""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "📋 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "   当前 Python 版本：$python_version"

major_version=$(echo $python_version | cut -d'.' -f1)
minor_version=$(echo $python_version | cut -d'.' -f2)

if [[ "$major_version" -lt 3 ]] || [[ "$major_version" -eq 3 && "$minor_version" -lt 9 ]]; then
    echo -e "${RED}❌ 错误：需要 Python 3.9 或更高版本${NC}"
    echo "   请访问 https://www.python.org/downloads/ 下载安装"
    exit 1
fi

echo -e "${GREEN}✓ Python 版本符合要求${NC}"
echo ""

echo "📦 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
else
    echo -e "${YELLOW}⚠ 虚拟环境已存在，跳过${NC}"
fi
echo ""

echo "🔌 激活虚拟环境..."
source venv/bin/activate
echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
echo ""

echo "⬆️  升级 pip..."
pip install --upgrade pip
echo -e "${GREEN}✓ pip 升级完成${NC}"
echo ""

echo "📥 安装 Python 依赖包..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo -e "${GREEN}✓ 依赖包安装完成${NC}"
else
    echo -e "${RED}❌ 错误：找不到 requirements.txt${NC}"
    exit 1
fi
echo ""

echo "⚙️  创建配置文件..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ 配置文件 .env 创建成功${NC}"
        echo -e "${YELLOW}⚠  请编辑 .env 配置 API 密钥${NC}"
    else
        cat > .env << 'EOF'
# OPC-Agents 配置文件
# 版本: 0.2.0

# === LLM API 配置（至少配置一个）===
# 推荐：MOKA AI（支持 Claude Sonnet 4）
MOKA_API_KEY=
MOKA_API_BASE=https://api.moka-ai.com/v1
MOKA_MODEL=moka/claude-sonnet-4-6

# 备选：智谱 GLM
# GLM_API_KEY=

# 备选：OpenAI
# OPENAI_API_KEY=
# OPENAI_API_BASE=https://api.openai.com/v1

# 备选：Ollama本地模型（无需API Key，使用OpenAI兼容端点）
# OLLAMA_ENABLED=true
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3
EOF
        echo -e "${GREEN}✓ 默认配置文件 .env 创建成功${NC}"
        echo -e "${YELLOW}⚠  请编辑 .env 配置 API 密钥${NC}"
    fi
else
    echo -e "${YELLOW}⚠  配置文件 .env 已存在，跳过${NC}"
fi
echo ""

echo "📁 创建数据目录..."
mkdir -p deliverables
mkdir -p data
mkdir -p data/schedules
mkdir -p data/completions
mkdir -p data/context
mkdir -p data/checkpoints
mkdir -p data/loop_progress
mkdir -p data/consensus_logs
mkdir -p data/marketplace
mkdir -p data/feedback
mkdir -p plugins
mkdir -p data/workflows
mkdir -p logs
echo -e "${GREEN}✓ 数据目录创建完成${NC}"
echo ""

echo "========================================"
echo -e "${GREEN}✅ 安装完成！${NC}"
echo "========================================"
echo ""
echo "📝 下一步操作："
echo ""
echo "1. 配置 API 密钥（可选，不配置也能用模板模式）："
echo "   vim .env"
echo ""
echo "2. 启动服务："
echo "   ./start.sh"
echo ""
echo "3. 访问系统："
echo "   http://localhost:8501"
echo ""
echo "========================================"
echo ""

if [ -t 0 ]; then
    read -p "是否现在启动服务？(y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🚀 启动 OPC-Agents..."
        streamlit run frontend/app.py
    fi
else
    echo "💡 非交互模式，请手动运行: ./start.sh"
fi
