"""
OpenClaw 协议模块

提供 OpenClaw WebSocket 协议兼容实现，支持：
- WebSocket 连接管理
- 配对码生成和管理
- 二维码生成
- 设备认证
- 消息收发
"""

from .pairing_manager import pairing_manager, PairingManager
from .qr_generator import qr_generator, QRCodeGenerator
from .websocket_server import websocket_server, OpenClawWebSocketServer, OpenClawProtocolHandler

__all__ = [
    'pairing_manager',
    'PairingManager',
    'qr_generator',
    'QRCodeGenerator',
    'websocket_server',
    'OpenClawWebSocketServer',
    'OpenClawProtocolHandler',
]
