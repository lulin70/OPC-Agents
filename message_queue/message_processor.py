#!/usr/bin/env python3
"""
消息处理器

提供异步消息处理、AI调用和进度跟踪功能。
"""

import threading
import time
import logging
from typing import Optional, Callable
from .models import Message, MessageStatus, MessageProgress
from .queue_manager import MessageQueue


class MessageProcessor:
    """消息处理器"""
    
    def __init__(self, message_queue: MessageQueue, ai_client=None, progress_streamer=None):
        """初始化消息处理器
        
        Args:
            message_queue: 消息队列实例
            ai_client: AI客户端（ZeroClawIntegration实例）
            progress_streamer: 进度流式传输器实例
        """
        self.message_queue = message_queue
        self.ai_client = ai_client
        self.progress_streamer = progress_streamer
        self.running = False
        self.worker_thread = None
        self.logger = logging.getLogger(__name__)
        
        # 进度回调函数
        self.progress_callbacks: list = []
        
        # 处理步骤定义
        self.processing_steps = [
            {"name": "接收消息", "weight": 10},
            {"name": "分析意图", "weight": 20},
            {"name": "调用AI服务", "weight": 50},
            {"name": "生成响应", "weight": 15},
            {"name": "完成处理", "weight": 5}
        ]
    
    def add_progress_callback(self, callback: Callable[[MessageProgress], None]):
        """添加进度回调函数
        
        Args:
            callback: 回调函数，接收MessageProgress参数
        """
        self.progress_callbacks.append(callback)
    
    def _notify_progress(self, progress: MessageProgress):
        """通知进度更新
        
        Args:
            progress: 进度对象
        """
        for callback in self.progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                self.logger.error(f"进度回调失败: {e}")
    
    def _calculate_progress(self, step_index: int) -> int:
        """计算处理进度
        
        Args:
            step_index: 当前步骤索引
            
        Returns:
            进度百分比（0-100）
        """
        total_weight = sum(step["weight"] for step in self.processing_steps)
        completed_weight = sum(
            self.processing_steps[i]["weight"] 
            for i in range(step_index)
        )
        return int((completed_weight / total_weight) * 100)
    
    def process_message(self, message: Message) -> Optional[str]:
        """处理单条消息
        
        Args:
            message: 消息对象
            
        Returns:
            处理结果，如果失败则返回None
        """
        try:
            # 步骤1: 接收消息
            self._update_progress(message.id, 0, "接收消息", len(self.processing_steps), 0)
            self.message_queue.update_message_status(message.id, MessageStatus.PROCESSING, 0)
            
            # 步骤2: 分析意图
            self._update_progress(message.id, 1, "分析意图", len(self.processing_steps), 1)
            intent = self._analyze_intent(message.content)
            time.sleep(0.1)  # 模拟处理时间
            
            # 步骤3: 调用AI服务
            self._update_progress(message.id, 2, "调用AI服务", len(self.processing_steps), 2)
            response = self._call_ai_service(message.content, intent)
            
            if not response:
                raise Exception("AI服务调用失败")
            
            # 步骤4: 生成响应
            self._update_progress(message.id, 3, "生成响应", len(self.processing_steps), 3)
            processed_response = self._process_response(response)
            time.sleep(0.1)  # 模拟处理时间
            
            # 步骤5: 完成处理
            self._update_progress(message.id, 4, "完成处理", len(self.processing_steps), 4)
            self.message_queue.update_message_status(message.id, MessageStatus.COMPLETED, 100)
            
            self.logger.info(f"消息处理完成: {message.id}")
            return processed_response
            
        except Exception as e:
            self.logger.error(f"消息处理失败: {message.id}, 错误: {e}")
            self.message_queue.update_message_status(
                message.id, 
                MessageStatus.FAILED, 
                error=str(e)
            )
            return None
    
    def _update_progress(self, message_id: str, step_index: int, step_name: str, total_steps: int, completed_steps: int):
        """更新处理进度
        
        Args:
            message_id: 消息ID
            step_index: 步骤索引
            step_name: 步骤名称
            total_steps: 总步骤数
            completed_steps: 已完成步骤数
        """
        progress_value = self._calculate_progress(step_index)
        
        progress = MessageProgress(
            message_id=message_id,
            status=MessageStatus.PROCESSING,
            progress=progress_value,
            current_step=step_name,
            total_steps=total_steps,
            completed_steps=completed_steps
        )
        
        self.message_queue.progress[message_id] = progress
        self._notify_progress(progress)
        
        # 通过SSE发送实时进度更新
        if self.progress_streamer:
            message = self.message_queue.get_message_by_id(message_id)
            if message:
                progress_data = {
                    "type": "progress",
                    "message_id": message_id,
                    "task_id": message.task_id,
                    "progress": progress_value,
                    "current_step": step_name,
                    "total_steps": total_steps,
                    "completed_steps": completed_steps,
                    "status": "processing"
                }
                self.progress_streamer.broadcast_to_task(message.task_id, progress_data)
    
    def _analyze_intent(self, content: str) -> str:
        """分析消息意图
        
        Args:
            content: 消息内容
            
        Returns:
            意图类型
        """
        # 简单的意图识别
        if "计划" in content or "规划" in content:
            return "planning"
        elif "分析" in content or "报告" in content:
            return "analysis"
        elif "设计" in content or "方案" in content:
            return "design"
        else:
            return "general"
    
    def _call_ai_service(self, content: str, intent: str) -> Optional[str]:
        """调用AI服务
        
        Args:
            content: 消息内容
            intent: 意图类型
            
        Returns:
            AI响应，如果失败则返回None
        """
        try:
            if self.ai_client:
                # 构建提示词
                prompt = f"用户消息: {content}\n意图: {intent}\n请根据你的角色给出响应。"
                
                # 调用AI服务
                response = self.ai_client.call_llm(prompt)
                return response
            else:
                # 如果没有AI客户端，返回默认响应
                return f"收到您的消息，正在处理中...（意图: {intent}）"
        except Exception as e:
            self.logger.error(f"AI服务调用失败: {e}")
            return None
    
    def _process_response(self, response: str) -> str:
        """处理AI响应
        
        Args:
            response: AI原始响应
            
        Returns:
            处理后的响应
        """
        # 简单的响应处理
        if isinstance(response, str):
            # 尝试解析JSON格式的响应
            try:
                import json
                response_data = json.loads(response)
                if "response" in response_data:
                    return response_data["response"]
                elif "content" in response_data:
                    return response_data["content"]
            except:
                pass
            
            return response
        else:
            return str(response)
    
    def start(self):
        """启动消息处理器"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        self.logger.info("消息处理器已启动")
    
    def stop(self):
        """停止消息处理器"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.logger.info("消息处理器已停止")
    
    def _worker_loop(self):
        """工作线程循环"""
        while self.running:
            try:
                # 从队列获取消息
                message = self.message_queue.get_message(timeout=1.0)
                
                if message:
                    self.logger.info(f"开始处理消息: {message.id}")
                    self.process_message(message)
                
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}")
                time.sleep(1)
