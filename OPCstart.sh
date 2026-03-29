#!/bin/bash

# OPC-Agents 启动脚本
# 功能：启动 ZeroClaw Gateway，等待配对码，启动 OPC-Agents，提供 kill gateway 的方法
# 参数：--debug 启用调试模式

echo "========================================"
echo "OPC-Agents 启动脚本"
echo "========================================"

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

# 定义 ZeroClaw 目录路径
ZEROCLAW_DIR="/Users/lin/zeroclaw"

# 启动 ZeroClaw Gateway
echo "\n启动 ZeroClaw Gateway..."
lsof -ti:8080 | xargs kill -9   
if [ -d "$ZEROCLAW_DIR" ]; then
    cd "$ZEROCLAW_DIR"
    echo "进入 ZeroClaw 目录: $(pwd)"
    
    # 构建 ZeroClaw 项目
    echo "构建 ZeroClaw 项目..."
    cargo build --release
    
    # 启动 gateway，使用 nohup 后台运行，输出到 gateway.log
    echo "启动 ZeroClaw Gateway..."
    nohup ./target/release/zeroclaw gateway > gateway.log 2>&1 &
    GATEWAY_PID=$!
    echo "ZeroClaw Gateway 已启动，PID: $GATEWAY_PID"
    echo "正在等待 Gateway 启动并生成配对码..."
    
    # 等待 10 秒，让 Gateway 生成配对码
    sleep 10
    
    echo "\n========================================"
    echo "ZeroClaw Gateway 配对码:"
    # 从日志中提取配对码
    PAIRING_CODE=$(grep -A 3 "PAIRING REQUIRED" gateway.log 2>/dev/null | grep -oE "[0-9]{6}" | head -1)
    if [ -n "$PAIRING_CODE" ]; then
        echo "🔐 配对码: $PAIRING_CODE"
        echo "请将此配对码输入到 config.toml 文件中的 pairing_code 字段"
    else
        echo "未能自动提取配对码，请查看日志:"
        tail -20 gateway.log
    fi
    echo "========================================"
    
    # 提示用户输入配对码
    echo "\n按 Enter 键继续启动 OPC-Agents..."
    # 添加超时机制，5秒后自动继续
    read -t 5 -p "(5秒后自动继续) " || echo ""
    echo "继续启动 OPC-Agents..."
else
    echo "错误：ZeroClaw 目录不存在: $ZEROCLAW_DIR"
    echo "请确保 ZeroClaw 项目已克隆到正确的位置"
    exit 1
fi

# 切换回 OPC-Agents 目录
cd "$OPC_AGENTS_DIR"
echo "\n切换回 OPC-Agents 目录: $(pwd)"

# 启动 OPC-Agents Web 界面
echo "\n启动 OPC-Agents Web 界面..."
lsof -ti:5007 | xargs kill -9
echo "Web 页面网址: http://localhost:5007"

if [ "$DEBUG_MODE" = true ]; then
    echo "启用调试模式..."
    python3 -m web_interface.app --debug --gateway-pid $PAIRING_CODE
else
    python3 -m web_interface.app --gateway-pid $PAIRING_CODE
fi
