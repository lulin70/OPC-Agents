#!/usr/bin/env python3
"""
Unit tests for ConversationManager and NotificationManager
"""

import pytest
import sqlite3
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from opc_manager.conversation_manager import (
    ConversationManager, Conversation, Message,
    ConversationStatus, MessageRole, MessageType
)
from opc_manager.notification_manager import (
    NotificationManager, Notification,
    NotificationType, NotificationPriority
)


class MockDBManager:
    """Mock database manager for testing"""
    
    def __init__(self, db_path=':memory:'):
        self.db_path = db_path
        self._conn = None
    
    def get_connection(self):
        """Get database connection"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()


@pytest.fixture
def db_manager():
    """Create in-memory database for testing"""
    manager = MockDBManager()
    
    # Create tables BEFORE initializing managers
    with manager.get_connection() as conn:
        cursor = conn.cursor()
        
        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                user_id TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        
        # Create notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                priority TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                related_object_type TEXT,
                related_object_id TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            )
        """)
        
        # Create task_conversation_links table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_conversation_links (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                link_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        
        # Create tasks table (for foreign key)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                task_name TEXT
            )
        """)
        
        conn.commit()
    
    return manager


class TestConversationManager:
    """Test ConversationManager"""
    
    def test_create_conversation(self, db_manager):
        """Test creating a conversation"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话",
            initial_message="你好"
        )
        
        assert conv.id.startswith("conv_")
        assert conv.title == "测试对话"
        assert conv.status == "active"
        assert conv.message_count == 1
        assert conv.user_id == "test_user"
    
    def test_get_conversation(self, db_manager):
        """Test getting a conversation"""
        manager = ConversationManager(db_manager)
        
        # Create conversation
        created = manager.create_conversation(
            user_id="test_user",
            title="测试对话"
        )
        
        # Retrieve conversation
        retrieved = manager.get_conversation(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == "测试对话"
        assert retrieved.status == "active"
    
    def test_list_conversations(self, db_manager):
        """Test listing conversations with pagination"""
        manager = ConversationManager(db_manager)
        
        # Create multiple conversations
        for i in range(5):
            manager.create_conversation(
                user_id="test_user",
                title=f"对话 {i+1}"
            )
        
        # List conversations
        result = manager.list_conversations(
            user_id="test_user",
            page=1,
            limit=3
        )
        
        assert result['total'] == 5
        assert len(result['items']) == 3
        assert result['page'] == 1
        assert result['limit'] == 3
    
    def test_add_message(self, db_manager):
        """Test adding a message"""
        manager = ConversationManager(db_manager)
        
        # Create conversation with initial message
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话",
            initial_message="初始消息"
        )
        
        # Verify initial message count
        assert conv.message_count == 1
        
        # Add message
        msg = manager.add_message(
            conversation_id=conv.id,
            role=MessageRole.USER.value,
            message_type=MessageType.TEXT.value,
            content="测试消息"
        )
        
        assert msg.id.startswith("msg_")
        assert msg.content == "测试消息"
        assert msg.role == "user"
        
        # Verify conversation stats updated
        updated_conv = manager.get_conversation(conv.id)
        assert updated_conv.message_count == 2
    
    def test_get_messages(self, db_manager):
        """Test getting messages"""
        manager = ConversationManager(db_manager)
        
        # Create conversation
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话",
            initial_message="第一条消息"
        )
        
        # Add more messages
        manager.add_message(
            conversation_id=conv.id,
            role="executive",
            message_type="text",
            content="第二条消息"
        )
        
        manager.add_message(
            conversation_id=conv.id,
            role="user",
            message_type="text",
            content="第三条消息"
        )
        
        # Get messages
        messages = manager.get_messages(conv.id)
        
        assert len(messages) == 3
        assert messages[0].content == "第一条消息"
        assert messages[1].content == "第二条消息"
        assert messages[2].content == "第三条消息"
    
    def test_link_task_to_conversation(self, db_manager):
        """Test linking task to conversation"""
        manager = ConversationManager(db_manager)
        
        # Create conversation
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话"
        )
        
        # Link task
        manager.link_task_to_conversation(
            task_id="task_123",
            conversation_id=conv.id,
            link_type="created_from"
        )
        
        # Verify link
        updated_conv = manager.get_conversation(conv.id)
        assert "task_123" in updated_conv.related_task_ids
    
    def test_archive_conversation(self, db_manager):
        """Test archiving a conversation"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话"
        )
        
        manager.archive_conversation(conv.id)
        
        archived_conv = manager.get_conversation(conv.id)
        assert archived_conv.status == "archived"
    
    def test_delete_conversation_soft(self, db_manager):
        """Test soft deleting a conversation"""
        manager = ConversationManager(db_manager)
        
        conv = manager.create_conversation(
            user_id="test_user",
            title="测试对话"
        )
        
        manager.delete_conversation(conv.id, soft=True)
        
        deleted_conv = manager.get_conversation(conv.id)
        assert deleted_conv.status == "deleted"


class TestNotificationManager:
    """Test NotificationManager"""
    
    def test_create_notification(self, db_manager):
        """Test creating a notification"""
        manager = NotificationManager(db_manager)
        
        notif = manager.create_notification(
            user_id="test_user",
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="测试通知",
            content="这是一个测试通知"
        )
        
        assert notif.id.startswith("notif_")
        assert notif.title == "测试通知"
        assert notif.type == "task"
        assert notif.priority == "normal"
        assert notif.is_read is False
    
    def test_get_notifications(self, db_manager):
        """Test getting notifications"""
        manager = NotificationManager(db_manager)
        
        # Create multiple notifications
        for i in range(5):
            manager.create_notification(
                user_id="test_user",
                type=NotificationType.TASK.value,
                priority=NotificationPriority.NORMAL.value,
                title=f"通知 {i+1}"
            )
        
        # Get notifications
        result = manager.get_notifications(
            user_id="test_user",
            page=1,
            limit=3
        )
        
        assert result['total'] == 5
        assert len(result['items']) == 3
        assert result['unread_count'] == 5
    
    def test_mark_as_read(self, db_manager):
        """Test marking notification as read"""
        manager = NotificationManager(db_manager)
        
        notif = manager.create_notification(
            user_id="test_user",
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="测试通知"
        )
        
        # Mark as read
        success = manager.mark_as_read(notif.id, "test_user")
        
        assert success is True
        
        # Verify
        updated_notif = manager.get_notification(notif.id)
        assert updated_notif.is_read is True
        assert updated_notif.read_at is not None
    
    def test_mark_all_as_read(self, db_manager):
        """Test marking all notifications as read"""
        manager = NotificationManager(db_manager)
        
        # Create notifications
        for i in range(5):
            manager.create_notification(
                user_id="test_user",
                type=NotificationType.TASK.value,
                priority=NotificationPriority.NORMAL.value,
                title=f"通知 {i+1}"
            )
        
        # Mark all as read
        count = manager.mark_all_as_read("test_user")
        
        assert count == 5
        
        # Verify unread count
        result = manager.get_notifications("test_user")
        assert result['unread_count'] == 0
    
    def test_get_unread_count(self, db_manager):
        """Test getting unread count"""
        manager = NotificationManager(db_manager)
        
        # Create notifications
        manager.create_notification(
            user_id="test_user",
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="通知 1"
        )
        
        manager.create_notification(
            user_id="test_user",
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="通知 2"
        )
        
        # Mark one as read
        notifs = manager.get_notifications("test_user")
        manager.mark_as_read(notifs['items'][0]['id'], "test_user")
        
        # Get unread count
        count = manager.get_unread_count("test_user")
        
        assert count == 1
    
    def test_delete_notification(self, db_manager):
        """Test deleting a notification"""
        manager = NotificationManager(db_manager)
        
        notif = manager.create_notification(
            user_id="test_user",
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="测试通知"
        )
        
        # Delete notification
        success = manager.delete_notification(notif.id, "test_user")
        
        assert success is True
        
        # Verify deletion
        deleted_notif = manager.get_notification(notif.id)
        assert deleted_notif is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
