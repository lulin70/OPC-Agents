#!/usr/bin/env python3
"""
数据存储模型

定义消息、任务、对话历史等数据的数据库模型。
"""

import sqlite3
import json
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class MessageRecord:
    """消息记录数据类"""
    id: str
    task_id: str
    sender: str
    receiver: str
    content: str
    message_type: str = "user"
    status: str = "pending"
    timestamp: float = field(default_factory=time.time)
    progress: int = 0
    error: Optional[str] = None
    metadata: str = "{}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageRecord':
        """从字典创建对象"""
        return cls(**data)


@dataclass
class TaskRecord:
    """任务记录数据类"""
    id: str
    name: str
    status: str = "pending"
    progress: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    assigned_to: str = ""
    description: str = ""
    metadata: str = "{}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskRecord':
        """从字典创建对象"""
        return cls(**data)


@dataclass
class ConversationRecord:
    """对话记录数据类"""
    id: str
    task_id: str
    messages: str = "[]"  # JSON格式的消息ID列表
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    summary: str = ""
    metadata: str = "{}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationRecord':
        """从字典创建对象"""
        return cls(**data)


@dataclass
class AgentRecord:
    """Agent记录数据类"""
    id: str
    name: str
    department: str
    role: str = ""
    skills: str = "[]"  # JSON格式的技能列表
    performance_score: float = 0.0
    tasks_completed: int = 0
    tasks_in_progress: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: str = "{}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentRecord':
        """从字典创建对象"""
        return cls(**data)


@dataclass
class DeliverableRecord:
    """成果物记录数据类"""
    id: str
    task_id: str
    name: str
    type: str = "document"  # document, report, code, data, etc.
    content: str = ""
    file_path: str = ""
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = ""
    metadata: str = "{}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeliverableRecord':
        """从字典创建对象"""
        return cls(**data)
