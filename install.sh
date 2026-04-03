#!/bin/bash
# OPC-Agents 一键安装脚本
# 适用于 macOS/Linux 系统

set -e

echo "========================================"
echo "  OPC-Agents 一键安装脚本"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 版本
echo "📋 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "   当前 Python 版本：$python_version"

# 提取主版本和次版本
major_version=$(echo $python_version | cut -d'.' -f1)
minor_version=$(echo $python_version | cut -d'.' -f2)

if [[ "$major_version" -lt 3 ]] || [[ "$major_version" -eq 3 && "$minor_version" -lt 9 ]]; then
    echo -e "${RED}❌ 错误：需要 Python 3.9 或更高版本${NC}"
    echo "   请访问 https://www.python.org/downloads/ 下载安装"
    exit 1
fi

echo -e "${GREEN}✓ Python 版本符合要求${NC}"
echo ""

# 检查虚拟环境
echo "📦 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ 虚拟环境创建成功${NC}"
else
    echo -e "${YELLOW}⚠ 虚拟环境已存在，跳过${NC}"
fi
echo ""

# 激活虚拟环境
echo "🔌 激活虚拟环境..."
source venv/bin/activate
echo -e "${GREEN}✓ 虚拟环境已激活${NC}"
echo ""

# 升级 pip
echo "⬆️  升级 pip..."
pip install --upgrade pip
echo -e "${GREEN}✓ pip 升级完成${NC}"
echo ""

# 安装依赖
echo "📥 安装 Python 依赖包..."
if [ -f "requirements.txt" ]; then
    # 使用国内镜像加速
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo -e "${GREEN}✓ 依赖包安装完成${NC}"
else
    echo -e "${RED}❌ 错误：找不到 requirements.txt${NC}"
    exit 1
fi
echo ""

# 创建配置文件
echo "⚙️  创建配置文件..."
if [ ! -f "config.toml" ]; then
    if [ -f "config.toml.sample" ]; then
        cp config.toml.sample config.toml
        echo -e "${GREEN}✓ 配置文件创建成功${NC}"
        echo -e "${YELLOW}⚠  请编辑 config.toml 配置 API 密钥${NC}"
    else
        # 创建默认配置
        cat > config.toml << EOF
# OPC-Agents 配置文件

[api_keys]
# 智谱 AI API 密钥（必填）
GLM_API_KEY = "your_glm_api_key_here"

# 通知配置（可选）
[email]
enabled = false
smtp_server = "smtp.example.com"
smtp_port = 587
smtp_username = "your_email@example.com"
smtp_password = "your_password"

[wechat]
enabled = false
webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"

[dingtalk]
enabled = false
webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=xxx"

[notification]
# 默认通知渠道：console, email, wechat, dingtalk
default_channels = ["console"]
EOF
        echo -e "${GREEN}✓ 默认配置文件创建成功${NC}"
        echo -e "${YELLOW}⚠  请编辑 config.toml 配置 API 密钥${NC}"
    fi
else
    echo -e "${YELLOW}⚠  配置文件已存在，跳过${NC}"
fi
echo ""

# 创建数据目录
echo "📁 创建数据目录..."
mkdir -p data/skills/installed
mkdir -p data/skills/cache
mkdir -p data/logs
mkdir -p data/config
echo -e "${GREEN}✓ 数据目录创建完成${NC}"
echo ""

# 检查系统依赖
echo "🔍 检查系统依赖..."

# 检查 git
if command -v git &> /dev/null; then
    echo -e "${GREEN}✓ git 已安装${NC}"
else
    echo -e "${YELLOW}⚠ git 未安装，某些功能可能受限${NC}"
fi

echo ""

# 安装完成
echo "========================================"
echo -e "${GREEN}✅ 安装完成！${NC}"
echo "========================================"
echo ""
echo "📝 下一步操作："
echo ""
echo "1. 配置 API 密钥："
echo "   vim config.toml"
echo ""
echo "2. 启动服务："
echo "   ./start.sh"
echo ""
echo "3. 访问系统："
echo "   http://localhost:5000"
echo ""
echo "========================================"
echo ""

# 询问是否启动
read -p "是否现在启动服务？(y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 启动 OPC-Agents..."
    python web_interface/app.py
fi
