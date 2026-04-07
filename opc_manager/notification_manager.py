#!/usr/bin/env python3
"""
Notification Manager for OPC-Agents

Responsible for notification lifecycle management:
- Create, read, update, delete notifications
- Mark notifications as read/unread
- Batch operations
- Event-driven notification creation
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


class NotificationType(Enum):
    """Notification type"""
    TASK = "task"
    CONFIRMATION = "confirmation"
    SYSTEM = "system"
    FINANCE = "finance"
    HR = "hr"


class NotificationPriority(Enum):
    """Notification priority"""
    URGENT = "urgent"      # 🔴 紧急
    IMPORTANT = "important"  # 🟡 重要
    NORMAL = "normal"      # 🟢 普通
    INFO = "info"          # 🔵 信息


@dataclass
class Notification:
    """Notification data structure"""
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
    read_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = f"notif_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Notification':
        """Create from dictionary"""
        return cls(**data)


class NotificationManager:
    """
    Notification Manager
    
    Manages notifications for OPC-Agents system.
    Provides CRUD operations and event-driven notification creation.
    """
    
    def __init__(self, db_manager, event_bus=None):
        """
        Initialize Notification Manager
        
        Args:
            db_manager: Database manager with get_connection() method
            event_bus: Event bus for subscribing to events (optional)
        """
        self.db_manager = db_manager
        self.event_bus = event_bus
        self.logger = logging.getLogger("OPC-Agents.NotificationManager")
        
        if event_bus:
            self._subscribe_to_events()
        
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Ensure required tables exist"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name = 'notifications'
            """)
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                self.logger.warning("Notifications table not found. Please run migration first.")
    
    def create_notification(self, user_id: str, type: str, priority: str,
                           title: str, content: str = None,
                           related_object_type: str = None,
                           related_object_id: str = None) -> Notification:
        """
        Create a new notification
        
        Args:
            user_id: User ID
            type: Notification type (task/confirmation/system/finance/hr)
            priority: Priority (urgent/important/normal/info)
            title: Notification title
            content: Notification content (optional)
            related_object_type: Related object type (task/agent/plan)
            related_object_id: Related object ID
            
        Returns:
            Notification object
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
        
        # Persist notification
        self._save_notification(notif)
        
        # Push notification via event bus
        if self.event_bus:
            self.event_bus.publish('notification.created', notif.to_dict())
        
        self.logger.info(f"Created notification: {notif.id}, type: {type}, priority: {priority}")
        return notif
    
    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """
        Get notification by ID
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Notification object or None
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, type, priority, title, content,
                       related_object_type, related_object_id, is_read,
                       created_at, read_at
                FROM notifications
                WHERE id = ?
            """, (notification_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return Notification(
                id=row[0],
                user_id=row[1],
                type=row[2],
                priority=row[3],
                title=row[4],
                content=row[5],
                related_object_type=row[6],
                related_object_id=row[7],
                is_read=bool(row[8]),
                created_at=row[9],
                read_at=row[10]
            )
    
    def get_notifications(self, user_id: str, unread_only: bool = False,
                         page: int = 1, limit: int = 20,
                         type_filter: str = None,
                         priority_filter: str = None) -> Dict[str, Any]:
        """
        Get notifications with pagination
        
        Args:
            user_id: User ID
            unread_only: Only unread notifications
            page: Page number (1-indexed)
            limit: Items per page
            type_filter: Filter by type (optional)
            priority_filter: Filter by priority (optional)
            
        Returns:
            Dictionary with items, total, unread_count, page, limit
        """
        offset = (page - 1) * limit
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query
            base_query = """
                SELECT id, title, type, priority, is_read, created_at, related_object_type
                FROM notifications
                WHERE user_id = ?
            """
            params = [user_id]
            
            if unread_only:
                base_query += " AND is_read = FALSE"
            
            if type_filter:
                base_query += " AND type = ?"
                params.append(type_filter)
            
            if priority_filter:
                base_query += " AND priority = ?"
                params.append(priority_filter)
            
            # Get total count
            count_query = base_query.replace(
                "SELECT id, title, type, priority, is_read, created_at, related_object_type",
                "SELECT COUNT(*)"
            )
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get items
            base_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(base_query, params)
            
            rows = cursor.fetchall()
            items = []
            for row in rows:
                items.append({
                    "id": row[0],
                    "title": row[1],
                    "type": row[2],
                    "priority": row[3],
                    "is_read": bool(row[4]),
                    "created_at": row[5],
                    "related_object_type": row[6]
                })
            
            # Get unread count
            cursor.execute("""
                SELECT COUNT(*) FROM notifications
                WHERE user_id = ? AND is_read = FALSE
            """, (user_id,))
            unread_count = cursor.fetchone()[0]
            
            return {
                "items": items,
                "total": total,
                "unread_count": unread_count,
                "page": page,
                "limit": limit
            }
    
    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark notification as read
        
        Args:
            notification_id: Notification ID
            user_id: User ID
            
        Returns:
            bool: True if successful, False if notification not found
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if notification exists and belongs to user
            cursor.execute("""
                SELECT id FROM notifications
                WHERE id = ? AND user_id = ?
            """, (notification_id, user_id))
            
            if not cursor.fetchone():
                return False
            
            # Mark as read
            cursor.execute("""
                UPDATE notifications
                SET is_read = TRUE, read_at = ?
                WHERE id = ? AND user_id = ?
            """, (datetime.now().isoformat(), notification_id, user_id))
            
            conn.commit()
            self.logger.info(f"Marked notification {notification_id} as read")
            return True
    
    def mark_all_as_read(self, user_id: str, before: str = None) -> int:
        """
        Mark all notifications as read
        
        Args:
            user_id: User ID
            before: Mark notifications before this timestamp (optional)
            
        Returns:
            int: Number of notifications marked
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                UPDATE notifications
                SET is_read = TRUE, read_at = ?
                WHERE user_id = ? AND is_read = FALSE
            """
            params = [datetime.now().isoformat(), user_id]
            
            if before:
                query += " AND created_at < ?"
                params.append(before)
            
            cursor.execute(query, params)
            marked_count = cursor.rowcount
            conn.commit()
            
            self.logger.info(f"Marked {marked_count} notifications as read for user {user_id}")
            return marked_count
    
    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Delete notification
        
        Args:
            notification_id: Notification ID
            user_id: User ID
            
        Returns:
            bool: True if successful, False if notification not found
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM notifications
                WHERE id = ? AND user_id = ?
            """, (notification_id, user_id))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            
            if deleted:
                self.logger.info(f"Deleted notification {notification_id}")
            return deleted
    
    def get_unread_count(self, user_id: str) -> int:
        """
        Get unread notification count
        
        Args:
            user_id: User ID
            
        Returns:
            int: Unread count
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM notifications
                WHERE user_id = ? AND is_read = FALSE
            """, (user_id,))
            
            count = cursor.fetchone()[0]
            return count
    
    def _save_notification(self, notif: Notification) -> None:
        """Persist notification to database"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO notifications 
                (id, user_id, type, priority, title, content,
                 related_object_type, related_object_id, is_read, created_at, read_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                notif.id,
                notif.user_id,
                notif.type,
                notif.priority,
                notif.title,
                notif.content,
                notif.related_object_type,
                notif.related_object_id,
                notif.is_read,
                notif.created_at,
                notif.read_at
            ))
            
            conn.commit()
    
    def _subscribe_to_events(self) -> None:
        """Subscribe to events for automatic notification creation"""
        if not self.event_bus:
            return
        
        # Task completed event
        self.event_bus.subscribe('task.completed', self._on_task_completed)
        
        # Task failed event
        self.event_bus.subscribe('task.failed', self._on_task_failed)
        
        # Plan pending confirmation event
        self.event_bus.subscribe('plan.pending_confirmation', self._on_plan_pending)
    
    def _on_task_completed(self, event_data: Dict) -> None:
        """Handle task completed event"""
        task_info = event_data.get('task', {})
        user_id = event_data.get('user_id', 'default_user')
        
        self.create_notification(
            user_id=user_id,
            type=NotificationType.TASK.value,
            priority=NotificationPriority.NORMAL.value,
            title="任务完成",
            content=f"任务 {task_info.get('task_name', '')} 已完成",
            related_object_type='task',
            related_object_id=task_info.get('task_id')
        )
    
    def _on_task_failed(self, event_data: Dict) -> None:
        """Handle task failed event"""
        task_info = event_data.get('task', {})
        user_id = event_data.get('user_id', 'default_user')
        
        self.create_notification(
            user_id=user_id,
            type=NotificationType.TASK.value,
            priority=NotificationPriority.URGENT.value,
            title="任务失败",
            content=f"任务 {task_info.get('task_name', '')} 执行失败：{task_info.get('error', '')}",
            related_object_type='task',
            related_object_id=task_info.get('task_id')
        )
    
    def _on_plan_pending(self, event_data: Dict) -> None:
        """Handle plan pending confirmation event"""
        user_id = event_data.get('user_id', 'default_user')
        task_name = event_data.get('task_name', '')
        
        self.create_notification(
            user_id=user_id,
            type=NotificationType.CONFIRMATION.value,
            priority=NotificationPriority.IMPORTANT.value,
            title="计划待确认",
            content=f"任务 {task_name} 的执行计划已生成，请确认",
            related_object_type='plan',
            related_object_id=event_data.get('task_id')
        )
