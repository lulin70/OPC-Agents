#!/usr/bin/env python3
"""
消息数据模型

定义消息的数据结构和状态。
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import time
import uuid


class MessageStatus(Enum):
    """消息状态枚举"""
    PENDING = "pending"  # 等待处理
    PROCESSING = "processing"  # 正在处理
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


class MessageType(Enum):
    """消息类型枚举"""
    USER = "user"  # 用户消息
    EXECUTIVE = "executive"  # 总裁办消息
    SYSTEM = "system"  # 系统消息
    TASK = "task"  # 任务消息


@dataclass
class Message:
    """消息数据类"""
    id: str = field(default_factory=lambda: f"msg_{int(time.time())}_{uuid.uuid4().hex[:8]}")
    task_id: str = ""
    sender: str = ""
    receiver: str = ""
    content: str = ""
    message_type: MessageType = MessageType.USER
    status: MessageStatus = MessageStatus.PENDING
    timestamp: float = field(default_factory=time.time)
    progress: int = 0  # 处理进度 0-100
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "message_type": self.message_type.value,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "progress": self.progress,
            "error": self.error,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息对象"""
        return cls(
            id=data.get("id", f"msg_{int(time.time())}_{uuid.uuid4().hex[:8]}"),
            task_id=data.get("task_id", ""),
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            content=data.get("content", ""),
            message_type=MessageType(data.get("message_type", "user")),
            status=MessageStatus(data.get("status", "pending")),
            timestamp=data.get("timestamp", time.time()),
            progress=data.get("progress", 0),
            error=data.get("error"),
            metadata=data.get("metadata", {})
        )


@dataclass
class MessageProgress:
    """消息处理进度"""
    message_id: str
    status: MessageStatus
    progress: int  # 0-100
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "message_id": self.message_id,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "timestamp": self.timestamp
        }
