# 阶段 1 实施计划 - 基础架构 + P0 功能

**时间**: 2026-04-07 至 2026-04-21（2 周）  
**目标**: 完成基础架构和 P0 功能开发  
**交付物**: 可用的通知中心和对话中心 MVP

---

## 一、Week 1: 基础架构（Day 1-5）

### Day 1: 数据库 Schema 设计

#### 任务 1.1: 设计数据库表结构
**负责人**: 架构师  
**预计时间**: 4 小时  
**输出**: SQL 迁移脚本

```sql
-- 1. 对话表
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- active/archived/deleted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    metadata TEXT,  -- JSON 格式存储元数据
    INDEX idx_user_status (user_id, status),
    INDEX idx_last_message (user_id, last_message_at DESC)
);

-- 2. 消息表
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user/executive/system/task
    message_type TEXT NOT NULL,  -- text/plan/task/search/result
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON 格式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_conversation (conversation_id, created_at DESC),
    INDEX idx_unread (conversation_id, read) WHERE read = FALSE
);

-- 3. 通知表
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- task/confirmation/system/finance/hr
    priority TEXT NOT NULL,  -- urgent/important/normal/info
    title TEXT NOT NULL,
    content TEXT,
    related_object_type TEXT,  -- task/agent/plan
    related_object_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_unread (user_id, is_read) WHERE is_read = FALSE,
    INDEX idx_user_created (user_id, created_at DESC)
);

-- 4. 任务 - 对话关联表
CREATE TABLE IF NOT EXISTS task_conversation_links (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    link_type TEXT NOT NULL,  -- created_from/referenced_in/updated_by
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_link (task_id, conversation_id, link_type),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    INDEX idx_task (task_id),
    INDEX idx_conversation (conversation_id)
);
```

#### 任务 1.2: 编写迁移脚本
**负责人**: 后端开发  
**预计时间**: 2 小时  
**输出**: `migrations/001_add_conversation_notification.sql`

```sql
-- 迁移脚本：添加对话和通知相关表
-- 版本：001
-- 日期：2026-04-07

BEGIN TRANSACTION;

-- 创建 conversations 表
CREATE TABLE IF NOT EXISTS conversations (...);

-- 创建 messages 表
CREATE TABLE IF NOT EXISTS messages (...);

-- 创建 notifications 表
CREATE TABLE IF NOT EXISTS notifications (...);

-- 创建 task_conversation_links 表
CREATE TABLE IF NOT EXISTS task_conversation_links (...);

-- 迁移现有任务数据到 conversations 表
INSERT INTO conversations (id, title, user_id, status, created_at, last_message_at, message_count)
SELECT 
    'conv_' || SUBSTR(task_id, 6) as conversation_id,
    task_name as title,
    'default_user' as user_id,
    CASE 
        WHEN status = 'completed' THEN 'archived'
        ELSE 'active'
    END as status,
    datetime(created_at, 'unixepoch') as created_at,
    datetime(updated_at, 'unixepoch') as last_message_at,
    2 as message_count  -- 初始消息：用户 + 系统
FROM tasks
WHERE task_id LIKE 'task-%';

-- 为现有任务创建初始消息
INSERT INTO messages (id, conversation_id, role, message_type, content, created_at)
SELECT 
    'msg_init_' || SUBSTR(task_id, 6),
    'conv_' || SUBSTR(task_id, 6),
    'system' as role,
    'task' as message_type,
    json_object(
        'task_id', task_id,
        'task_name', task_name,
        'status', status
    ) as content,
    datetime(created_at, 'unixepoch') as created_at
FROM tasks
WHERE task_id LIKE 'task-%';

COMMIT;
```

---

### Day 2: ConversationManager 实现

#### 任务 2.1: 实现 ConversationManager
**负责人**: 后端开发  
**预计时间**: 6 小时  
**输出**: `opc_manager/conversation_manager.py`

```python
#!/usr/bin/env python3
"""
Conversation Manager for OPC-Agents

负责对话的创建、查询、更新、删除，以及消息管理
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

class ConversationStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

class MessageRole(Enum):
    USER = "user"
    EXECUTIVE = "executive"
    SYSTEM = "system"
    TASK = "task"

class MessageType(Enum):
    TEXT = "text"
    PLAN = "plan"
    TASK = "task"
    SEARCH = "search"
    RESULT = "result"
    NOTIFICATION = "notification"

@dataclass
class Message:
    id: str
    conversation_id: str
    role: str
    message_type: str
    content: str
    metadata: Dict[str, Any]
    created_at: str
    read: bool = False
    
    def __post_init__(self):
        if not self.id:
            self.id = f"msg_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

@dataclass
class Conversation:
    id: str
    title: str
    user_id: str
    status: str
    created_at: str
    updated_at: str
    last_message_at: Optional[str]
    message_count: int
    related_task_ids: List[str]
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if not self.id:
            self.id = f"conv_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.related_task_ids:
            self.related_task_ids = []
        if not self.metadata:
            self.metadata = {}

class ConversationManager:
    """对话管理器"""
    
    def __init__(self, db_manager):
        """初始化对话管理器
        
        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger("OPC-Agents.ConversationManager")
    
    def create_conversation(self, user_id: str, title: str = "新对话", 
                           initial_message: str = None) -> Conversation:
        """创建新对话
        
        Args:
            user_id: 用户 ID
            title: 对话标题
            initial_message: 初始消息（可选）
            
        Returns:
            Conversation 对象
        """
        conv = Conversation(
            id=f"conv_{uuid.uuid4().hex[:12]}",
            title=title,
            user_id=user_id,
            status=ConversationStatus.ACTIVE.value,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            last_message_at=datetime.now().isoformat() if initial_message else None,
            message_count=1 if initial_message else 0,
            related_task_ids=[],
            metadata={}
        )
        
        # 持久化对话
        self._save_conversation(conv)
        
        # 添加初始消息
        if initial_message:
            self.add_message(
                conversation_id=conv.id,
                role=MessageRole.USER.value,
                message_type=MessageType.TEXT.value,
                content=initial_message
            )
        
        self.logger.info(f"创建对话：{conv.id}, 标题：{title}")
        return conv
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话详情"""
        # 实现从数据库加载对话
        pass
    
    def list_conversations(self, user_id: str, status: str = None,
                          page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """获取对话列表"""
        # 实现分页查询
        pass
    
    def add_message(self, conversation_id: str, role: str, 
                   message_type: str, content: str,
                   metadata: Dict = None) -> Message:
        """添加消息到对话"""
        msg = Message(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            conversation_id=conversation_id,
            role=role,
            message_type=message_type,
            content=content,
            metadata=metadata or {},
            created_at=datetime.now().isoformat(),
            read=False
        )
        
        # 持久化消息
        self._save_message(msg)
        
        # 更新对话的 message_count 和 last_message_at
        self._update_conversation_stats(conversation_id)
        
        return msg
    
    def get_messages(self, conversation_id: str, limit: int = 50,
                    before: str = None) -> List[Message]:
        """获取对话消息列表（分页）"""
        # 实现分页查询
        pass
    
    def link_task_to_conversation(self, task_id: str, conversation_id: str,
                                 link_type: str) -> None:
        """关联任务到对话"""
        # 实现任务 - 对话关联
        pass
    
    def archive_conversation(self, conversation_id: str) -> None:
        """归档对话"""
        # 实现归档逻辑
        pass
    
    def delete_conversation(self, conversation_id: str, soft: bool = True) -> None:
        """删除对话（支持软删除）"""
        # 实现删除逻辑
        pass
    
    def _save_conversation(self, conv: Conversation) -> None:
        """持久化对话到数据库"""
        # 实现数据库保存
        pass
    
    def _save_message(self, msg: Message) -> None:
        """持久化消息到数据库"""
        # 实现数据库保存
        pass
    
    def _update_conversation_stats(self, conversation_id: str) -> None:
        """更新对话统计信息"""
        # 更新 message_count 和 last_message_at
        pass
```

#### 任务 2.2: 单元测试
**负责人**: 测试经理  
**预计时间**: 2 小时  
**输出**: `tests/unit/test_conversation_manager.py`

```python
import pytest
from opc_manager.conversation_manager import ConversationManager, Conversation, Message

class TestConversationManager:
    """对话管理器测试"""
    
    def test_create_conversation(self, db_manager):
        """测试创建对话"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(
            user_id="user_123",
            title="测试对话",
            initial_message="你好"
        )
        
        assert conv.id.startswith("conv_")
        assert conv.title == "测试对话"
        assert conv.status == "active"
        assert conv.message_count == 1
    
    def test_add_message(self, db_manager):
        """测试添加消息"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(user_id="user_123")
        
        msg = manager.add_message(
            conversation_id=conv.id,
            role="user",
            message_type="text",
            content="测试消息"
        )
        
        assert msg.id.startswith("msg_")
        assert msg.content == "测试消息"
        assert conv.message_count == 2
    
    def test_link_task_to_conversation(self, db_manager):
        """测试关联任务到对话"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(user_id="user_123")
        
        manager.link_task_to_conversation(
            task_id="task_456",
            conversation_id=conv.id,
            link_type="created_from"
        )
        
        # 验证关联关系
        linked_conv = manager.get_conversation(conv.id)
        assert "task_456" in linked_conv.related_task_ids
```

---

### Day 3: NotificationManager 实现

#### 任务 3.1: 实现 NotificationManager
**负责人**: 后端开发  
**预计时间**: 6 小时  
**输出**: `opc_manager/notification_manager.py`

```python
#!/usr/bin/env python3
"""
Notification Manager for OPC-Agents

负责通知的创建、查询、标记已读等
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class NotificationType(Enum):
    TASK = "task"
    CONFIRMATION = "confirmation"
    SYSTEM = "system"
    FINANCE = "finance"
    HR = "hr"

class NotificationPriority(Enum):
    URGENT = "urgent"      # 🔴 紧急
    IMPORTANT = "important"  # 🟡 重要
    NORMAL = "normal"      # 🟢 普通
    INFO = "info"          # 🔵 信息

@dataclass
class Notification:
    id: str
    user_id: str
    type: str
    priority: str
    title: str
    content: str
    related_object_type: Optional[str]
    related_object_id: Optional[str]
    is_read: bool
    created_at: str
    read_at: Optional[str]
    
    def __post_init__(self):
        if not self.id:
            self.id = f"notif_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

class NotificationManager:
    """通知管理器"""
    
    def __init__(self, db_manager, event_bus=None):
        """初始化通知管理器
        
        Args:
            db_manager: 数据库管理器
            event_bus: 事件总线（用于推送通知）
        """
        self.db_manager = db_manager
        self.event_bus = event_bus
        self.logger = logging.getLogger("OPC-Agents.NotificationManager")
        
        # 订阅事件，自动创建通知
        if event_bus:
            self._subscribe_to_events()
    
    def create_notification(self, user_id: str, type: str, priority: str,
                           title: str, content: str = None,
                           related_object_type: str = None,
                           related_object_id: str = None) -> Notification:
        """创建通知
        
        Args:
            user_id: 用户 ID
            type: 通知类型
            priority: 优先级
            title: 通知标题
            content: 通知内容
            related_object_type: 关联对象类型
            related_object_id: 关联对象 ID
            
        Returns:
            Notification 对象
        """
        notif = Notification(
            id=f"notif_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            type=type,
            priority=priority,
            title=title,
            content=content or "",
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            is_read=False,
            created_at=datetime.now().isoformat(),
            read_at=None
        )
        
        # 持久化通知
        self._save_notification(notif)
        
        # 推送通知（如果有事件总线）
        if self.event_bus:
            self.event_bus.publish('notification.created', asdict(notif))
        
        self.logger.info(f"创建通知：{notif.id}, 类型：{type}, 优先级：{priority}")
        return notif
    
    def get_notifications(self, user_id: str, unread_only: bool = False,
                         page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """获取通知列表
        
        Args:
            user_id: 用户 ID
            unread_only: 仅未读
            page: 页码
            limit: 每页数量
            
        Returns:
            {
                "items": [...],
                "total": 100,
                "unread_count": 5
            }
        """
        # 实现查询逻辑
        pass
    
    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """标记通知为已读
        
        Args:
            notification_id: 通知 ID
            user_id: 用户 ID
            
        Returns:
            bool: 是否成功
        """
        # 实现标记已读
        pass
    
    def mark_all_as_read(self, user_id: str, before: str = None) -> int:
        """批量标记已读
        
        Args:
            user_id: 用户 ID
            before: 标记此时间之前的通知
            
        Returns:
            int: 标记的数量
        """
        # 实现批量标记
        pass
    
    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """删除通知"""
        # 实现删除逻辑
        pass
    
    def get_unread_count(self, user_id: str) -> int:
        """获取未读数量"""
        # 实现查询
        pass
    
    def _save_notification(self, notif: Notification) -> None:
        """持久化通知到数据库"""
        # 实现数据库保存
        pass
    
    def _subscribe_to_events(self) -> None:
        """订阅事件，自动创建通知"""
        # 任务完成事件
        self.event_bus.subscribe('task.completed', self._on_task_completed)
        # 任务失败事件
        self.event_bus.subscribe('task.failed', self._on_task_failed)
        # 计划待确认事件
        self.event_bus.subscribe('plan.pending_confirmation', self._on_plan_pending)
    
    def _on_task_completed(self, event_data: Dict) -> None:
        """任务完成事件处理"""
        task_info = event_data.get('task', {})
        self.create_notification(
            user_id=event_data.get('user_id', 'default_user'),
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="任务完成",
            content=f"任务 {task_info.get('task_name', '')} 已完成",
            related_object_type='task',
            related_object_id=task_info.get('task_id')
        )
    
    def _on_task_failed(self, event_data: Dict) -> None:
        """任务失败事件处理"""
        task_info = event_data.get('task', {})
        self.create_notification(
            user_id=event_data.get('user_id', 'default_user'),
            type=NotificationType.TASK.value,
            priority=NotificationPriority.URGENT.value,
            title="任务失败",
            content=f"任务 {task_info.get('task_name', '')} 执行失败：{task_info.get('error', '')}",
            related_object_type='task',
            related_object_id=task_info.get('task_id')
        )
    
    def _on_plan_pending(self, event_data: Dict) -> None:
        """计划待确认事件处理"""
        self.create_notification(
            user_id=event_data.get('user_id', 'default_user'),
            type=NotificationType.CONFIRMATION.value,
            priority=NotificationPriority.IMPORTANT.value,
            title="计划待确认",
            content=f"任务 {event_data.get('task_name', '')} 的执行计划已生成，请确认",
            related_object_type='plan',
            related_object_id=event_data.get('task_id')
        )
```

---

### Day 4: 基础 API 开发

#### 任务 4.1: 对话 API
**负责人**: 后端开发  
**预计时间**: 4 小时  
**输出**: `web_interface/routes/chat_routes.py`

```python
#!/usr/bin/env python3
"""
Chat routes for OPC-Agents Web Interface (v2)
"""

from flask import Blueprint, jsonify, request
from opc_manager.conversation_manager import ConversationManager
import time

bp = Blueprint('chat_v2', __name__, url_prefix='/api/v2/chat')

def register_routes(manager):
    conv_manager = ConversationManager(manager.db_manager)
    
    # 创建对话
    @bp.route('', methods=['POST'])
    def create_conversation():
        data = request.json
        user_id = data.get('user_id', 'default_user')
        title = data.get('title', '新对话')
        initial_message = data.get('initial_message')
        
        conv = conv_manager.create_conversation(
            user_id=user_id,
            title=title,
            initial_message=initial_message
        )
        
        return jsonify({
            "success": True,
            "data": asdict(conv),
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 获取对话列表
    @bp.route('', methods=['GET'])
    def list_conversations():
        user_id = request.args.get('user_id', 'default_user')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search')
        
        result = conv_manager.list_conversations(
            user_id=user_id,
            status=status,
            page=page,
            limit=limit,
            search=search
        )
        
        return jsonify({
            "success": True,
            "data": result,
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 获取对话详情
    @bp.route('/<conversation_id>', methods=['GET'])
    def get_conversation(conversation_id):
        conv = conv_manager.get_conversation(conversation_id)
        
        if not conv:
            return jsonify({
                "success": False,
                "error": "Conversation not found"
            }), 404
        
        return jsonify({
            "success": True,
            "data": asdict(conv),
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 发送消息
    @bp.route('/<conversation_id>/message', methods=['POST'])
    def send_message(conversation_id):
        data = request.json
        role = data.get('role', 'user')
        message_type = data.get('type', 'text')
        content = data.get('content')
        metadata = data.get('metadata', {})
        
        if not content:
            return jsonify({
                "success": False,
                "error": "Content is required"
            }), 400
        
        msg = conv_manager.add_message(
            conversation_id=conversation_id,
            role=role,
            message_type=message_type,
            content=content,
            metadata=metadata
        )
        
        return jsonify({
            "success": True,
            "data": asdict(msg),
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    return bp
```

#### 任务 4.2: 通知 API
**负责人**: 后端开发  
**预计时间**: 3 小时  
**输出**: `web_interface/routes/notification_routes.py`

```python
#!/usr/bin/env python3
"""
Notification routes for OPC-Agents Web Interface (v2)
"""

from flask import Blueprint, jsonify, request
from opc_manager.notification_manager import NotificationManager
import time

bp = Blueprint('notifications_v2', __name__, url_prefix='/api/v2/notifications')

def register_routes(manager):
    notif_manager = NotificationManager(manager.db_manager, manager.event_bus)
    
    # 获取通知列表
    @bp.route('', methods=['GET'])
    def get_notifications():
        user_id = request.args.get('user_id', 'default_user')
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        result = notif_manager.get_notifications(
            user_id=user_id,
            unread_only=unread_only,
            page=page,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result,
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 获取未读数量
    @bp.route('/unread-count', methods=['GET'])
    def get_unread_count():
        user_id = request.args.get('user_id', 'default_user')
        count = notif_manager.get_unread_count(user_id)
        
        return jsonify({
            "success": True,
            "data": {"unread_count": count},
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 标记已读
    @bp.route('/<notification_id>/read', methods=['PUT'])
    def mark_as_read(notification_id):
        user_id = request.args.get('user_id', 'default_user')
        success = notif_manager.mark_as_read(notification_id, user_id)
        
        return jsonify({
            "success": success,
            "data": {"marked": success},
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 批量标记已读
    @bp.route('/read-all', methods=['PUT'])
    def mark_all_as_read():
        user_id = request.args.get('user_id', 'default_user')
        before = request.args.get('before')
        
        count = notif_manager.mark_all_as_read(user_id, before)
        
        return jsonify({
            "success": True,
            "data": {"marked_count": count},
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    # 删除通知
    @bp.route('/<notification_id>', methods=['DELETE'])
    def delete_notification(notification_id):
        user_id = request.args.get('user_id', 'default_user')
        success = notif_manager.delete_notification(notification_id, user_id)
        
        return jsonify({
            "success": success,
            "meta": {
                "timestamp": time.time(),
                "request_id": f"req_{int(time.time())}"
            }
        })
    
    return bp
```

---

### Day 5: 集成测试与文档

#### 任务 5.1: API 集成测试
**负责人**: 测试经理  
**预计时间**: 4 小时  
**输出**: `tests/integration/test_chat_notification_api.py`

```python
import pytest
from flask import Flask

class TestChatNotificationAPI:
    """对话和通知 API 集成测试"""
    
    def test_create_conversation(self, app, client):
        """测试创建对话"""
        response = client.post('/api/v2/chat', json={
            "user_id": "test_user",
            "title": "测试对话",
            "initial_message": "你好"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['title'] == "测试对话"
    
    def test_send_message(self, app, client):
        """测试发送消息"""
        # 先创建对话
        conv_response = client.post('/api/v2/chat', json={
            "user_id": "test_user",
            "title": "测试对话"
        })
        conv_id = conv_response.get_json()['data']['id']
        
        # 发送消息
        response = client.post(f'/api/v2/chat/{conv_id}/message', json={
            "role": "user",
            "type": "text",
            "content": "测试消息"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['content'] == "测试消息"
    
    def test_get_notifications(self, app, client):
        """测试获取通知列表"""
        response = client.get('/api/v2/notifications?user_id=test_user')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'items' in data['data']
        assert 'unread_count' in data['data']
    
    def test_mark_notification_as_read(self, app, client):
        """测试标记通知已读"""
        # 先创建通知
        notif_response = client.post('/api/v2/notifications', json={
            "user_id": "test_user",
            "type": "task",
            "priority": "normal",
            "title": "测试通知"
        })
        notif_id = notif_response.get_json()['data']['id']
        
        # 标记已读
        response = client.put(f'/api/v2/notifications/{notif_id}/read?user_id=test_user')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
```

#### 任务 5.2: API 文档
**负责人**: 架构师  
**预计时间**: 3 小时  
**输出**: `docs/api_v2_spec.md`

```markdown
# OPC-Agents API v2 规范

## 对话 API

### POST /api/v2/chat
创建新对话

**Request**:
```json
{
  "user_id": "user_123",
  "title": "新对话",
  "initial_message": "你好"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "conv_abc123",
    "title": "新对话",
    "status": "active",
    "message_count": 1
  },
  "meta": {
    "timestamp": 1712476800,
    "request_id": "req_123"
  }
}
```

## 通知 API

### GET /api/v2/notifications
获取通知列表

**Query Parameters**:
- `user_id` (string): 用户 ID
- `unread_only` (boolean): 仅未读
- `page` (integer): 页码
- `limit` (integer): 每页数量

**Response**:
```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "unread_count": 5
  }
}
```
```

---

## 二、Week 2: P0 功能开发（Day 6-10）

### Day 6-7: 通知中心前端

### Day 8-9: 对话中心前端

### Day 10: 对话 - 任务一体化 + 集成测试

（详细实施计划略，参照 Week 1 格式）

---

## 三、验收标准

### 功能验收
- ✅ 通知铃铛显示未读数
- ✅ 点击铃铛显示通知列表
- ✅ 独立对话中心页面可用
- ✅ 对话中嵌入任务卡片
- ✅ 任务进度实时更新

### 性能验收
- ✅ 页面加载时间 < 2 秒
- ✅ API 响应时间 P95 < 200ms
- ✅ 消息推送延迟 < 2 秒

### 质量验收
- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试通过率 100%
- ✅ 无 Critical/Major Bug

---

**创建时间**: 2026-04-07  
**负责人**: 架构师  
**审核人**: 产品经理
