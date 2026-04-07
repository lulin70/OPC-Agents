"""
WebSocket 路由 - 处理 WebSocket 连接和消息

提供聊天和通知的 WebSocket 端点
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse
import logging
from typing import Optional
import asyncio

from opc_manager.websocket_manager import websocket_manager
from opc_manager.auth import get_current_user  # 假设有认证模块

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/api/ws/chat/{chat_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    chat_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    聊天 WebSocket 端点
    
    用于实时接收聊天消息
    """
    await websocket.accept()
    
    user_id = current_user['id']
    connection_id = await websocket_manager.add_connection(
        websocket=websocket,
        user_id=user_id,
        channel='chat'
    )
    
    logger.info(f"Chat WebSocket connected: {connection_id} (chat_id={chat_id}, user={user_id})")
    
    try:
        # 发送连接成功消息
        await websocket.send_json({
            'type': 'connected',
            'connection_id': connection_id,
            'chat_id': chat_id
        })
        
        # 保持连接，接收客户端消息（如心跳）
        while True:
            try:
                # 接收客户端消息（可选，用于心跳等）
                data = await websocket.receive_json()
                logger.debug(f"Received message from {connection_id}: {data}")
                
                # 处理客户端消息
                if data.get('type') == 'ping':
                    await websocket.send_json({'type': 'pong'})
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break
    
    finally:
        # 清理连接
        await websocket_manager.remove_connection(connection_id)
        logger.info(f"Chat WebSocket disconnected: {connection_id}")


@router.websocket("/api/ws/notifications")
async def notification_websocket_endpoint(
    websocket: WebSocket,
    current_user: dict = Depends(get_current_user)
):
    """
    通知 WebSocket 端点
    
    用于实时接收通知
    """
    await websocket.accept()
    
    user_id = current_user['id']
    connection_id = await websocket_manager.add_connection(
        websocket=websocket,
        user_id=user_id,
        channel='notification'
    )
    
    logger.info(f"Notification WebSocket connected: {connection_id} (user={user_id})")
    
    try:
        # 发送连接成功消息
        await websocket.send_json({
            'type': 'connected',
            'connection_id': connection_id
        })
        
        # 保持连接
        while True:
            try:
                data = await websocket.receive_json()
                logger.debug(f"Received message from {connection_id}: {data}")
                
                # 处理心跳
                if data.get('type') == 'ping':
                    await websocket.send_json({'type': 'pong'})
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break
    
    finally:
        await websocket_manager.remove_connection(connection_id)
        logger.info(f"Notification WebSocket disconnected: {connection_id}")


@router.get("/api/ws/stats")
async def get_websocket_stats():
    """获取 WebSocket 统计信息"""
    return websocket_manager.get_stats()


@router.post("/api/ws/broadcast")
async def broadcast_message(
    message: dict,
    channel: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    广播消息
    
    - channel: 指定频道（'chat' 或 'notification'）
    - user_id: 指定用户
    - 都不指定则广播到所有连接
    """
    if user_id:
        # 发送给指定用户
        count = await websocket_manager.send_to_user(user_id, message)
        return {'success': True, 'sent_to': count, 'target': f'user_{user_id}'}
    
    elif channel:
        # 发送给指定频道
        count = await websocket_manager.send_to_channel(channel, message)
        return {'success': True, 'sent_to': count, 'target': f'channel_{channel}'}
    
    else:
        # 广播到所有连接
        await websocket_manager.broadcast(message)
        return {'success': True, 'sent_to': 'all'}


# 辅助函数：推送消息
async def push_new_message(user_id: str, message_data: dict):
    """推送新消息到指定用户"""
    message = {
        'type': 'new_message',
        'data': message_data,
        'timestamp': message_data.get('created_at')
    }
    
    count = await websocket_manager.send_to_user(user_id, message)
    logger.info(f"Pushed new message to {count} connections for user {user_id}")
    return count


async def push_notification(user_id: str, notification_data: dict):
    """推送通知到指定用户"""
    message = {
        'type': 'new_notification',
        'data': notification_data,
        'timestamp': notification_data.get('created_at')
    }
    
    count = await websocket_manager.send_to_user(user_id, message)
    logger.info(f"Pushed notification to {count} connections for user {user_id}")
    return count


async def push_task_update(user_id: str, task_data: dict):
    """推送任务更新到指定用户"""
    message = {
        'type': 'task_update',
        'data': task_data,
        'timestamp': task_data.get('updated_at')
    }
    
    count = await websocket_manager.send_to_user(user_id, message)
    logger.info(f"Pushed task update to {count} connections for user {user_id}")
    return count
