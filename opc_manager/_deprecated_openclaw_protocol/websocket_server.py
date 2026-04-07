"""
OpenClaw WebSocket 服务器（增强版）

模拟 OpenClaw 网关 API，支持配对流程和设备认证
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
import uuid
from datetime import datetime

from .pairing_manager import pairing_manager
from .qr_generator import qr_generator

logger = logging.getLogger(__name__)


class OpenClawProtocolHandler:
    """
    OpenClaw 协议处理器（增强版 - 支持配对）
    
    功能:
    - 处理 WebSocket 连接
    - 处理配对请求
    - 处理设备认证
    - 处理消息收发
    """
    
    def __init__(self):
        """初始化协议处理器"""
        # 已连接的客户端：connection_id -> client_info
        self.connected_clients: Dict[str, dict] = {}
        
        # 可选认证 Token
        self.auth_token: Optional[str] = None
        
        # 后台任务（在 WebSocket 服务器启动时启动）
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("OpenClawProtocolHandler initialized")
    
    async def start(self):
        """启动后台任务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("OpenClawProtocolHandler started")
    
    async def stop(self):
        """停止后台任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("OpenClawProtocolHandler stopped")
    
    async def _cleanup_loop(self):
        """定期清理过期配对请求"""
        while True:
            await asyncio.sleep(300)  # 每 5 分钟清理一次
            try:
                expired_count = pairing_manager.cleanup_expired()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired pairings")
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def handle_connect(self, websocket: WebSocket, params: dict) -> dict:
        """
        处理连接握手
        
        Args:
            websocket: WebSocket 连接
            params: 连接参数
            
        Returns:
            dict: 响应消息
        """
        device_id = params.get('device', {}).get('id', str(uuid.uuid4()))
        device_info = params.get('device', {})
        
        # 验证 Token（如果设置了）
        if self.auth_token:
            auth = params.get('auth', {})
            if auth.get('token') != self.auth_token:
                logger.warning(f"Authentication failed for device {device_id}")
                return {
                    'type': 'res',
                    'id': 'connect_001',
                    'ok': False,
                    'error': {'message': 'Authentication failed'}
                }
        
        # 检查设备是否已批准
        if not pairing_manager.is_device_approved(device_id):
            # 未批准，进入配对流程
            logger.info(f"Unapproved device attempting connection: {device_id}")
            return await self._initiate_pairing(websocket, device_id, device_info)
        
        # 已批准，正常连接
        connection_id = str(uuid.uuid4())
        self.connected_clients[connection_id] = {
            'websocket': websocket,
            'device': device_info,
            'device_id': device_id,
            'role': params.get('role'),
            'capabilities': params.get('capabilities', []),
            'approved': True,
            'connected_at': datetime.now()
        }
        
        logger.info(
            f"Approved device connected: {device_id} "
            f"(connection_id={connection_id})"
        )
        
        return {
            'type': 'res',
            'id': 'connect_001',
            'ok': True,
            'result': {
                'status': 'connected',
                'gateway': 'OPC-Agents',
                'version': '1.0.0',
                'device_id': device_id,
                'connection_id': connection_id
            }
        }
    
    async def _initiate_pairing(
        self, 
        websocket: WebSocket, 
        device_id: str,
        device_info: dict
    ) -> dict:
        """
        发起配对流程
        
        Args:
            websocket: WebSocket 连接
            device_id: 设备 ID
            device_info: 设备信息
            
        Returns:
            dict: 配对响应（包含二维码）
        """
        try:
            # 创建配对请求
            pairing_code = pairing_manager.create_pairing_request(
                channel='wechat',
                device_id=device_id,
                device_info=device_info
            )
            
            # 生成 WebSocket URL
            host = websocket.client.host if websocket.client else 'localhost'
            ws_url = f"ws://{host}:18789/ws/openclaw"
            
            # 生成二维码
            base64_qr = qr_generator.generate_pairing_qr(
                pairing_code=pairing_code,
                websocket_url=ws_url,
                device_id=device_id
            )
            
            # 生成 ASCII 二维码（用于终端）
            ascii_qr = qr_generator.generate_ascii_qr(pairing_code)
            
            logger.info(
                f"Created pairing request: {pairing_code} "
                f"(device={device_id})"
            )
            
            # 返回配对信息（包含二维码）
            return {
                'type': 'res',
                'id': 'connect_001',
                'ok': True,
                'result': {
                    'status': 'pairing_required',
                    'pairing_code': pairing_code,
                    'qr_code': base64_qr,
                    'ascii_qr': ascii_qr,
                    'expires_in': 3600,  # 1 小时
                    'instructions': {
                        'zh': '请使用微信扫码绑定',
                        'en': 'Please scan QR code with WeChat to bind'
                    },
                    'next_steps': [
                        '1. 访问 Web 界面查看二维码',
                        '2. 使用微信"扫一扫"扫描',
                        '3. 点击确认绑定',
                        '4. 重新连接完成绑定'
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to create pairing request: {e}")
            return {
                'type': 'res',
                'id': 'connect_001',
                'ok': False,
                'error': {
                    'message': f'Failed to create pairing request: {str(e)}'
                }
            }
    
    async def handle_pairing_approve(self, params: dict) -> dict:
        """
        处理配对批准
        
        Args:
            params: 批准参数（包含 pairing_code）
            
        Returns:
            dict: 批准结果
        """
        pairing_code = params.get('code')
        
        if not pairing_code:
            return {
                'type': 'res',
                'ok': False,
                'error': {'message': 'Missing pairing code'}
            }
        
        # 批准配对
        device_info = pairing_manager.approve_pairing(pairing_code)
        
        if device_info:
            device_id = device_info.get('device_id', 'unknown')
            logger.info(f"Pairing approved: {device_id} (code={pairing_code})")
            
            return {
                'type': 'res',
                'ok': True,
                'result': {
                    'status': 'approved',
                    'device_id': device_id,
                    'message': 'Pairing approved successfully'
                }
            }
        else:
            return {
                'type': 'res',
                'ok': False,
                'error': {
                    'message': 'Invalid or expired pairing code'
                }
            }
    
    async def handle_pairing_list(self, params: dict) -> dict:
        """
        处理配对列表查询
        
        Args:
            params: 查询参数（包含 channel）
            
        Returns:
            dict: 配对列表
        """
        channel = params.get('channel', 'wechat')
        pending = pairing_manager.list_pending(channel)
        
        return {
            'type': 'res',
            'ok': True,
            'result': {
                'pending_pairings': pending,
                'count': len(pending),
                'channel': channel
            }
        }
    
    async def handle_pairing_revoke(self, params: dict) -> dict:
        """
        处理配对撤销
        
        Args:
            params: 撤销参数（包含 device_id）
            
        Returns:
            dict: 撤销结果
        """
        device_id = params.get('device_id')
        
        if not device_id:
            return {
                'type': 'res',
                'ok': False,
                'error': {'message': 'Missing device_id'}
            }
        
        # 撤销设备
        success = pairing_manager.revoke_device(device_id)
        
        if success:
            logger.info(f"Device revoked: {device_id}")
            
            # 关闭该设备的连接
            for conn_id, client in list(self.connected_clients.items()):
                if client.get('device_id') == device_id:
                    try:
                        await client['websocket'].close()
                        logger.info(f"Closed connection for revoked device: {conn_id}")
                    except Exception as e:
                        logger.error(f"Error closing connection: {e}")
            
            return {
                'type': 'res',
                'ok': True,
                'result': {
                    'status': 'revoked',
                    'device_id': device_id
                }
            }
        else:
            return {
                'type': 'res',
                'ok': False,
                'error': {'message': 'Device not found'}
            }
    
    async def handle_message_receive(self, params: dict) -> dict:
        """
        处理接收到的消息
        
        Args:
            params: 消息参数
            
        Returns:
            dict: 处理结果
        """
        channel = params.get('channel', 'wechat')
        from_user = params.get('from')
        content = params.get('content', {})
        
        logger.info(f"Received message from {from_user}: {content}")
        
        # 调用 OPC-Agents 消息处理器
        try:
            # 导入 OPC Manager (需要在 app.py 中传递进来)
            from opc_manager.communication_manager import conversation_manager
            
            # 创建或获取对话
            conv_id = f"wechat_{from_user}"
            
            # 将微信消息添加到对话
            if conversation_manager:
                await conversation_manager.add_message(
                    conversation_id=conv_id,
                    message_type='user',
                    content=content.get('text', ''),
                    metadata={
                        'channel': channel,
                        'from_user': from_user,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                
                # 触发 AI 响应
                response = await conversation_manager.generate_response(
                    conversation_id=conv_id
                )
                
                logger.info(f"AI response generated: {response.get('content', '')[:100]}")
                
                # 将响应推送回微信
                if response.get('content'):
                    await self._send_to_wechat(from_user, response['content'])
                
                return {
                    'type': 'res',
                    'ok': True,
                    'result': {
                        'status': 'processed',
                        'message': 'Message processed successfully',
                        'ai_response': response.get('content', '')
                    }
                }
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            return {
                'type': 'res',
                'ok': False,
                'error': {
                    'message': f'Failed to process message: {str(e)}'
                }
            }
        
        # 降级处理：返回自动响应
        return {
            'type': 'res',
            'ok': True,
            'result': {
                'status': 'received',
                'message': '消息已收到，正在处理中...'
            }
        }
    
    async def _send_to_wechat(self, user_id: str, message: str):
        """
        发送消息到微信
        
        Args:
            user_id: 用户 ID
            message: 消息内容
        """
        # TODO: 实现微信消息推送
        logger.info(f"Sending to WeChat {user_id}: {message}")
        # 这里需要调用微信 API 发送消息
    
    async def handle_health(self) -> dict:
        """
        处理健康检查
        
        Returns:
            dict: 健康状态
        """
        stats = pairing_manager.get_stats()
        
        return {
            'type': 'res',
            'ok': True,
            'result': {
                'status': 'healthy',
                'gateway': 'OPC-Agents',
                'version': '1.0.0',
                'pairing_stats': stats,
                'connected_clients': len(self.connected_clients)
            }
        }
    
    async def handle_request(self, websocket: WebSocket, request: dict) -> dict:
        """
        处理请求
        
        Args:
            websocket: WebSocket 连接
            request: 请求消息
            
        Returns:
            dict: 响应消息
        """
        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')
        
        logger.debug(f"Handling request: method={method}, id={request_id}")
        
        # 路由到对应处理方法
        if method == 'pairing.approve':
            result = await self.handle_pairing_approve(params)
        elif method == 'pairing.list':
            result = await self.handle_pairing_list(params)
        elif method == 'pairing.revoke':
            result = await self.handle_pairing_revoke(params)
        elif method == 'message.receive':
            result = await self.handle_message_receive(params)
        elif method == 'health':
            result = await self.handle_health()
        else:
            result = {
                'type': 'res',
                'id': request_id,
                'ok': False,
                'error': {'message': f'Unknown method: {method}'}
            }
        
        return result
    
    async def send_message_to_device(
        self, 
        device_id: str, 
        message: dict
    ) -> int:
        """
        发送消息到指定设备
        
        Args:
            device_id: 设备 ID
            message: 消息内容
            
        Returns:
            int: 成功发送的连接数
        """
        success_count = 0
        
        for connection_id, client in self.connected_clients.items():
            if client.get('device_id') == device_id:
                try:
                    await client['websocket'].send_json(message)
                    success_count += 1
                    logger.debug(
                        f"Sent message to device {device_id} "
                        f"(connection={connection_id})"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send to device {device_id}: {e}"
                    )
        
        return success_count


class OpenClawWebSocketServer:
    """
    OpenClaw WebSocket 服务器
    
    处理 WebSocket 连接和协议解析
    """
    
    def __init__(self):
        """初始化 WebSocket 服务器"""
        self.handler = OpenClawProtocolHandler()
        logger.info("OpenClawWebSocketServer initialized")
    
    async def handle_websocket(self, websocket: WebSocket):
        """
        处理 WebSocket 连接
        
        Args:
            websocket: WebSocket 连接
        """
        await websocket.accept()
        logger.info(f"WebSocket connection accepted: {websocket.client}")
        
        try:
            while True:
                # 接收消息
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {data[:100]}")
                    await websocket.send_json({
                        'type': 'res',
                        'ok': False,
                        'error': {'message': 'Invalid JSON format'}
                    })
                    continue
                
                logger.debug(f"Received message: {json.dumps(message, indent=2)}")
                
                # 第一条消息必须是 connect
                if message.get('type') == 'connect':
                    response = await self.handler.handle_connect(
                        websocket, 
                        message.get('params', {})
                    )
                elif message.get('type') == 'req':
                    response = await self.handler.handle_request(websocket, message)
                else:
                    response = {
                        'type': 'res',
                        'ok': False,
                        'error': {
                            'message': 'Invalid message type. First message must be "connect"'
                        }
                    }
                
                # 发送响应
                await websocket.send_json(response)
                logger.debug(f"Sent response: {json.dumps(response, indent=2)}")
                
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
        finally:
            # 清理连接
            logger.info("WebSocket connection closed")


# 全局单例
websocket_server = OpenClawWebSocketServer()
