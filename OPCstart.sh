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
# 检查并清理端口 5007, 5008, 5009 上的旧进程
for port in 5007 5008 5009; do
    echo "检查端口 $port..."
    PIDS=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "发现旧进程占用端口 $port: $PIDS"
        echo "清理旧进程..."
        kill -9 $PIDS 2>/dev/null
        echo "旧进程已清理"
    else
        echo "端口 $port 未被占用"
    fi
done
echo "Web 页面网址: http://localhost:5009"

if [ "$DEBUG_MODE" = true ]; then
    echo "启用调试模式..."
    python3 -m web_interface.app --debug
else
    python3 -m web_interface.app
fi
