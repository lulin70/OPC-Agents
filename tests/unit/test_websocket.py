#!/usr/bin/env python3
"""
WebSocket 集成测试脚本

测试 WebSocket 连接、消息推送等功能
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from opc_manager.websocket_manager import websocket_manager


async def test_websocket_manager():
    """测试 WebSocket 管理器基本功能"""
    print("=" * 60)
    print("WebSocket 管理器测试")
    print("=" * 60)
    
    # 启动 WebSocket 管理器
    await websocket_manager.start()
    print("✅ WebSocket 管理器已启动")
    
    # 模拟添加连接（使用 Mock 对象）
    class MockWebSocket:
        async def send_json(self, data):
            print(f"  → 发送消息：{data}")
        
        async def close(self):
            print("  → 连接已关闭")
    
    # 测试添加连接
    print("\n测试添加连接...")
    conn_id1 = await websocket_manager.add_connection(
        websocket=MockWebSocket(),
        user_id="user_123",
        channel="chat"
    )
    print(f"✅ 添加连接：{conn_id1}")
    
    conn_id2 = await websocket_manager.add_connection(
        websocket=MockWebSocket(),
        user_id="user_123",
        channel="notification"
    )
    print(f"✅ 添加连接：{conn_id2}")
    
    conn_id3 = await websocket_manager.add_connection(
        websocket=MockWebSocket(),
        user_id="user_456",
        channel="chat"
    )
    print(f"✅ 添加连接：{conn_id3}")
    
    # 测试获取连接数
    print(f"\n当前连接数：{websocket_manager.get_connection_count()}")
    print(f"user_123 的连接数：{websocket_manager.get_user_connection_count('user_123')}")
    
    # 测试发送消息
    print("\n测试发送消息...")
    test_message = {
        'type': 'test_message',
        'data': {'content': 'Hello WebSocket!'}
    }
    
    count = await websocket_manager.send_to_user("user_123", test_message)
    print(f"✅ 向 user_123 发送消息，成功 {count} 个连接")
    
    count = await websocket_manager.send_to_channel("chat", test_message)
    print(f"✅ 向 chat 频道发送消息，成功 {count} 个连接")
    
    # 测试获取统计信息
    print("\nWebSocket 统计信息:")
    stats = websocket_manager.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 测试移除连接
    print("\n测试移除连接...")
    await websocket_manager.remove_connection(conn_id3)
    print(f"✅ 移除连接：{conn_id3}")
    
    # 等待心跳检测
    print("\n等待 2 秒，观察心跳检测...")
    await asyncio.sleep(2)
    
    # 停止 WebSocket 管理器
    await websocket_manager.stop()
    print("\n✅ WebSocket 管理器已停止")
    
    print("\n" + "=" * 60)
    print("所有测试通过！✅")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(test_websocket_manager())
