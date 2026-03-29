#!/usr/bin/env python3
"""
实时进度反馈系统

使用Server-Sent Events (SSE)实现实时进度反馈。
"""

import json
import time
import queue
import threading
from typing import Dict, Set, Optional
from flask import Response, stream_with_context
import logging

logger = logging.getLogger(__name__)


class ProgressStreamer:
    """进度流式传输器"""
    
    def __init__(self):
        """初始化进度流式传输器"""
        self.clients: Dict[str, queue.Queue] = {}  # 客户端ID到消息队列的映射
        self.task_clients: Dict[str, Set[str]] = {}  # 任务ID到客户端ID集合的映射
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def register_client(self, client_id: str, task_id: str = None) -> queue.Queue:
        """注册客户端
        
        Args:
            client_id: 客户端ID
            task_id: 任务ID（可选）
            
        Returns:
            客户端的消息队列
        """
        with self.lock:
            if client_id not in self.clients:
                self.clients[client_id] = queue.Queue(maxsize=100)
                self.logger.info(f"客户端已注册: {client_id}")
            
            # 如果指定了任务ID，添加到任务客户端映射
            if task_id:
                if task_id not in self.task_clients:
                    self.task_clients[task_id] = set()
                self.task_clients[task_id].add(client_id)
            
            return self.clients[client_id]
    
    def unregister_client(self, client_id: str):
        """注销客户端
        
        Args:
            client_id: 客户端ID
        """
        with self.lock:
            if client_id in self.clients:
                del self.clients[client_id]
                self.logger.info(f"客户端已注销: {client_id}")
            
            # 从所有任务客户端映射中移除
            for task_id, clients in self.task_clients.items():
                clients.discard(client_id)
    
    def send_progress(self, client_id: str, progress_data: dict):
        """发送进度到指定客户端
        
        Args:
            client_id: 客户端ID
            progress_data: 进度数据
        """
        with self.lock:
            if client_id in self.clients:
                try:
                    self.clients[client_id].put_nowait(progress_data)
                except queue.Full:
                    self.logger.warning(f"客户端队列已满: {client_id}")
    
    def broadcast_to_task(self, task_id: str, progress_data: dict):
        """广播进度到任务的所有客户端
        
        Args:
            task_id: 任务ID
            progress_data: 进度数据
        """
        with self.lock:
            if task_id in self.task_clients:
                for client_id in self.task_clients[task_id]:
                    self.send_progress(client_id, progress_data)
    
    def broadcast_all(self, progress_data: dict):
        """广播进度到所有客户端
        
        Args:
            progress_data: 进度数据
        """
        with self.lock:
            for client_id in self.clients:
                self.send_progress(client_id, progress_data)
    
    def generate_stream(self, client_id: str, task_id: str = None) -> Response:
        """生成SSE流
        
        Args:
            client_id: 客户端ID
            task_id: 任务ID（可选）
            
        Returns:
            Flask Response对象
        """
        def event_stream():
            """事件流生成器"""
            client_queue = self.register_client(client_id, task_id)
            
            try:
                # 发送初始连接消息
                yield f"data: {json.dumps({'type': 'connected', 'client_id': client_id})}\n\n"
                
                while True:
                    try:
                        # 等待消息，超时30秒发送心跳
                        message = client_queue.get(timeout=30)
                        yield f"data: {json.dumps(message)}\n\n"
                    except queue.Empty:
                        # 发送心跳消息
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            except GeneratorExit:
                # 客户端断开连接
                self.unregister_client(client_id)
        
        return Response(
            stream_with_context(event_stream()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )


# 全局进度流式传输器实例
progress_streamer = ProgressStreamer()


def get_progress_streamer() -> ProgressStreamer:
    """获取全局进度流式传输器实例
    
    Returns:
        ProgressStreamer实例
    """
    return progress_streamer
