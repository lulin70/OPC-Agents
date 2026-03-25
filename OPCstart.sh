#!/bin/bash

# OPC-Agents 启动脚本
# 功能：启动 ZeroClaw Gateway，等待配对码，启动 OPC-Agents，提供 kill gateway 的方法

echo "========================================"
echo "OPC-Agents 启动脚本"
echo "========================================"

# 切换到 OPC-Agents 目录
OPC_AGENTS_DIR="$(dirname "$0")"
cd "$OPC_AGENTS_DIR"
echo "当前目录: $(pwd)"

# 定义 ZeroClaw 目录路径
ZEROCLAW_DIR="/Users/lin/zeroclaw"

# 启动 ZeroClaw Gateway
echo "\n启动 ZeroClaw Gateway..."
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
    
    # 等待 10 秒，让用户看到匹配码
    sleep 10
    
    echo "\n========================================"
    echo "请查看 ZeroClaw Gateway 日志获取配对码:"
    echo "cat $ZEROCLAW_DIR/gateway.log"
    echo "========================================"
    
    # 提示用户输入配对码
    echo "\n请将配对码输入到 config.toml 文件中的 pairing_code 字段"
    echo "然后按 Enter 键继续..."
    read -p "按 Enter 键继续启动 OPC-Agents..."
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
echo "Web 页面网址: http://localhost:5007"
python3 web_interface.py

# 注意：由于上面的命令会阻塞，下面的代码不会执行
# 因此我们需要在另一个终端中执行 kill 命令
echo "\n========================================"
echo "如何停止 ZeroClaw Gateway:"
echo "kill $GATEWAY_PID"
echo "或使用: kill -9 $GATEWAY_PID"
echo "========================================"
