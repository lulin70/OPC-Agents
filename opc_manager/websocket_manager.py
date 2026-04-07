"""
WebSocket Manager - 实时通信核心模块

提供 WebSocket 连接管理、消息推送、心跳检测等功能
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """WebSocket 连接对象"""
    
    def __init__(self, websocket, connection_id: str, user_id: str, channel: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.user_id = user_id
        self.channel = channel  # 'chat' or 'notification'
        self.created_at = datetime.now()
        self.last_active_at = datetime.now()
        self.is_closed = False
        
    async def send(self, message: dict):
        """发送消息"""
        if self.is_closed:
            return False
        
        try:
            await self.websocket.send_json(message)
            self.last_active_at = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            await self.close()
            return False
    
    async def close(self):
        """关闭连接"""
        if not self.is_closed:
            self.is_closed = True
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(f"Error closing websocket: {e}")


class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 所有连接：connection_id -> WebSocketConnection
        self.connections: Dict[str, WebSocketConnection] = {}
        
        # 按用户分组：user_id -> Set[connection_id]
        self.user_connections: Dict[str, Set[str]] = {}
        
        # 按频道分组：channel -> Set[connection_id]
        self.channel_connections: Dict[str, Set[str]] = {}
        
        # 心跳间隔（秒）
        self.heartbeat_interval = 30
        
        # 连接超时（秒）
        self.connection_timeout = 300
        
        # 后台任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """启动 WebSocket 管理器"""
        logger.info("Starting WebSocket Manager")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
    async def stop(self):
        """停止 WebSocket 管理器"""
        logger.info("Stopping WebSocket Manager")
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for connection_id in list(self.connections.keys()):
            await self.remove_connection(connection_id)
    
    async def add_connection(self, websocket, user_id: str, channel: str) -> str:
        """添加新的 WebSocket 连接"""
        connection_id = str(uuid.uuid4())
        connection = WebSocketConnection(websocket, connection_id, user_id, channel)
        
        self.connections[connection_id] = connection
        
        # 添加到用户连接组
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        # 添加到频道连接组
        if channel not in self.channel_connections:
            self.channel_connections[channel] = set()
        self.channel_connections[channel].add(connection_id)
        
        logger.info(f"Added WebSocket connection: {connection_id} (user={user_id}, channel={channel})")
        return connection_id
    
    async def remove_connection(self, connection_id: str):
        """移除 WebSocket 连接"""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        
        # 从用户连接组移除
        if connection.user_id in self.user_connections:
            self.user_connections[connection.user_id].discard(connection_id)
            if not self.user_connections[connection.user_id]:
                del self.user_connections[connection.user_id]
        
        # 从频道连接组移除
        if connection.channel in self.channel_connections:
            self.channel_connections[connection.channel].discard(connection_id)
            if not self.channel_connections[connection.channel]:
                del self.channel_connections[connection.channel]
        
        # 关闭连接
        await connection.close()
        
        # 从连接字典移除
        del self.connections[connection_id]
        
        logger.info(f"Removed WebSocket connection: {connection_id}")
    
    async def send_to_user(self, user_id: str, message: dict) -> int:
        """向指定用户的所有连接发送消息"""
        if user_id not in self.user_connections:
            return 0
        
        success_count = 0
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.connections:
                if await self.connections[connection_id].send(message):
                    success_count += 1
        
        if success_count == 0:
            logger.warning(f"No active connections for user: {user_id}")
        
        return success_count
    
    async def send_to_channel(self, channel: str, message: dict) -> int:
        """向指定频道的的所有连接发送消息"""
        if channel not in self.channel_connections:
            return 0
        
        success_count = 0
        for connection_id in self.channel_connections[channel]:
            if connection_id in self.connections:
                if await self.connections[connection_id].send(message):
                    success_count += 1
        
        return success_count
    
    async def send_to_connection(self, connection_id: str, message: dict) -> bool:
        """向指定连接发送消息"""
        if connection_id not in self.connections:
            return False
        
        return await self.connections[connection_id].send(message)
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection_id in list(self.connections.keys()):
            await self.connections[connection_id].send(message)
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.connections)
    
    def get_user_connection_count(self, user_id: str) -> int:
        """获取用户的连接数"""
        if user_id not in self.user_connections:
            return 0
        return len(self.user_connections[user_id])
    
    async def _heartbeat_loop(self):
        """心跳检测循环"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _check_connections(self):
        """检查连接状态，清理超时连接"""
        now = datetime.now()
        timeout_connections = []
        
        for connection_id, connection in self.connections.items():
            # 检查是否超时
            if (now - connection.last_active_at).total_seconds() > self.connection_timeout:
                timeout_connections.append(connection_id)
                logger.warning(f"Connection timeout: {connection_id}")
        
        # 清理超时连接
        for connection_id in timeout_connections:
            await self.remove_connection(connection_id)
        
        if timeout_connections:
            logger.info(f"Cleaned up {len(timeout_connections)} timeout connections")
    
    def get_stats(self) -> dict:
        """获取 WebSocket 统计信息"""
        return {
            'total_connections': len(self.connections),
            'total_users': len(self.user_connections),
            'channels': {
                channel: len(connections)
                for channel, connections in self.channel_connections.items()
            }
        }


# 全局单例
websocket_manager = WebSocketManager()
