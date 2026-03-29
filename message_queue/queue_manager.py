#!/usr/bin/env python3
"""
消息队列管理器

提供消息队列的管理、存储和检索功能。
"""

import queue
import threading
import time
from typing import Dict, List, Optional, Any
from .models import Message, MessageStatus, MessageProgress
import logging

logger = logging.getLogger(__name__)


class MessageQueue:
    """消息队列管理器"""
    
    def __init__(self, max_size: int = 1000):
        """初始化消息队列
        
        Args:
            max_size: 队列最大容量
        """
        self.queue = queue.Queue(maxsize=max_size)
        self.messages: Dict[str, Message] = {}  # 消息ID到消息对象的映射
        self.task_messages: Dict[str, List[str]] = {}  # 任务ID到消息ID列表的映射
        self.progress: Dict[str, MessageProgress] = {}  # 消息ID到进度的映射
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
    
    def add_message(self, message: Message) -> bool:
        """添加消息到队列
        
        Args:
            message: 消息对象
            
        Returns:
            是否添加成功
        """
        try:
            with self.lock:
                self.queue.put(message, block=False)
                self.messages[message.id] = message
                
                # 添加到任务消息列表
                if message.task_id not in self.task_messages:
                    self.task_messages[message.task_id] = []
                self.task_messages[message.task_id].append(message.id)
                
                # 初始化进度
                self.progress[message.id] = MessageProgress(
                    message_id=message.id,
                    status=MessageStatus.PENDING,
                    progress=0
                )
                
                self.logger.info(f"消息已添加到队列: {message.id}")
                return True
        except queue.Full:
            self.logger.error("消息队列已满")
            return False
        except Exception as e:
            self.logger.error(f"添加消息失败: {e}")
            return False
    
    def get_message(self, timeout: Optional[float] = None) -> Optional[Message]:
        """从队列获取消息
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            消息对象，如果队列为空则返回None
        """
        try:
            message = self.queue.get(block=True, timeout=timeout)
            return message
        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"获取消息失败: {e}")
            return None
    
    def update_message_status(self, message_id: str, status: MessageStatus, progress: int = None, error: str = None):
        """更新消息状态
        
        Args:
            message_id: 消息ID
            status: 新状态
            progress: 进度（可选）
            error: 错误信息（可选）
        """
        with self.lock:
            if message_id in self.messages:
                message = self.messages[message_id]
                message.status = status
                
                if progress is not None:
                    message.progress = progress
                
                if error is not None:
                    message.error = error
                
                # 更新进度
                if message_id in self.progress:
                    self.progress[message_id].status = status
                    if progress is not None:
                        self.progress[message_id].progress = progress
                
                self.logger.debug(f"消息状态已更新: {message_id} -> {status.value}")
    
    def get_message_by_id(self, message_id: str) -> Optional[Message]:
        """根据ID获取消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            消息对象，如果不存在则返回None
        """
        return self.messages.get(message_id)
    
    def get_messages_by_task(self, task_id: str) -> List[Message]:
        """根据任务ID获取所有消息
        
        Args:
            task_id: 任务ID
            
        Returns:
            消息列表
        """
        with self.lock:
            message_ids = self.task_messages.get(task_id, [])
            return [self.messages[mid] for mid in message_ids if mid in self.messages]
    
    def get_progress(self, message_id: str) -> Optional[MessageProgress]:
        """获取消息处理进度
        
        Args:
            message_id: 消息ID
            
        Returns:
            进度对象，如果不存在则返回None
        """
        return self.progress.get(message_id)
    
    def get_queue_size(self) -> int:
        """获取队列大小
        
        Returns:
            队列中的消息数量
        """
        return self.queue.qsize()
    
    def clear_completed_messages(self, max_age: int = 3600):
        """清理已完成的消息
        
        Args:
            max_age: 最大保留时间（秒）
        """
        current_time = time.time()
        with self.lock:
            messages_to_remove = []
            
            for message_id, message in self.messages.items():
                if message.status in [MessageStatus.COMPLETED, MessageStatus.FAILED]:
                    if current_time - message.timestamp > max_age:
                        messages_to_remove.append(message_id)
            
            for message_id in messages_to_remove:
                message = self.messages.pop(message_id, None)
                if message and message.task_id in self.task_messages:
                    self.task_messages[message.task_id] = [
                        mid for mid in self.task_messages[message.task_id] 
                        if mid != message_id
                    ]
                self.progress.pop(message_id, None)
            
            if messages_to_remove:
                self.logger.info(f"已清理 {len(messages_to_remove)} 条已完成的消息")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取队列统计信息
        
        Returns:
            统计信息字典
        """
        with self.lock:
            status_count = {
                MessageStatus.PENDING: 0,
                MessageStatus.PROCESSING: 0,
                MessageStatus.COMPLETED: 0,
                MessageStatus.FAILED: 0
            }
            
            for message in self.messages.values():
                status_count[message.status] += 1
            
            return {
                "total_messages": len(self.messages),
                "queue_size": self.queue.qsize(),
                "status_count": {k.value: v for k, v in status_count.items()},
                "tasks_count": len(self.task_messages)
            }
