#!/bin/bash

# OPC-Agents 启动脚本
# 功能：启动 OPC-Agents Web 界面
# 参数：--debug 启用调试模式

echo "======================================="
echo "OPC-Agents 启动脚本"
echo "======================================="

# 解析命令行参数
DEBUG_MODE=false
for arg in "$@"
do
    case $arg in
        --debug)
        DEBUG_MODE=true
        shift # 移除 --debug 参数
        ;;
    esac
done

# 切换到 OPC-Agents 目录
OPC_AGENTS_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "OPC_AGENTS_DIR: $OPC_AGENTS_DIR"
cd "$OPC_AGENTS_DIR"
echo "当前目录: $(pwd)"

# 提示 ZeroClaw 作为独立系统
ZEROCLAW_DIR="/Users/lin/zeroclaw"
if [ -d "$ZEROCLAW_DIR" ]; then
    echo "\n======================================="
    echo "ZeroClaw 已作为独立系统运行"
    echo "请确保 ZeroClaw Gateway 已启动并配置"
    echo "======================================="
else
    echo "\n======================================="
    echo "ZeroClaw 目录不存在: $ZEROCLAW_DIR"
    echo "ZeroClaw 作为独立系统，需要单独安装和配置"
    echo "======================================="
fi

# 启动 OPC-Agents Web 界面
echo "\n启动 OPC-Agents Web 界面..."
lsof -ti:5007 | xargs kill -9 2>/dev/null
echo "Web 页面网址: http://localhost:5007"

if [ "$DEBUG_MODE" = true ]; then
    echo "启用调试模式..."
    python3 -m web_interface.app --debug
else
    python3 -m web_interface.app
fi
