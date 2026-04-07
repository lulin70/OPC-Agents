#!/usr/bin/env python3
"""
Conversation Manager for OPC-Agents

Responsible for conversation lifecycle management:
- Create, read, update, delete conversations
- Add and retrieve messages
- Link tasks to conversations
- Archive and delete conversations
"""

import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum


class ConversationStatus(Enum):
    """Conversation status"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MessageRole(Enum):
    """Message role"""
    USER = "user"
    EXECUTIVE = "executive"
    SYSTEM = "system"
    TASK = "task"


class MessageType(Enum):
    """Message type"""
    TEXT = "text"
    PLAN = "plan"
    TASK = "task"
    SEARCH = "search"
    RESULT = "result"
    NOTIFICATION = "notification"


@dataclass
class Message:
    """Message data structure"""
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
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class Conversation:
    """Conversation data structure"""
    id: str
    title: str
    user_id: str
    status: str
    created_at: str
    updated_at: str
    last_message_at: Optional[str]
    message_count: int
    related_task_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = f"conv_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
        if self.related_task_ids is None:
            self.related_task_ids = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        """Create from dictionary"""
        return cls(**data)


class ConversationManager:
    """
    Conversation Manager
    
    Manages conversations and messages for OPC-Agents system.
    Provides CRUD operations for conversations and messages,
    and handles task-conversation linking.
    """
    
    def __init__(self, db_manager):
        """
        Initialize Conversation Manager
        
        Args:
            db_manager: Database manager with get_connection() method
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger("OPC-Agents.ConversationManager")
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Ensure required tables exist"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('conversations', 'messages', 'task_conversation_links')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            if len(tables) < 3:
                self.logger.warning("Required tables not found. Please run migration first.")
    
    def create_conversation(self, user_id: str, title: str = "新对话", 
                           initial_message: str = None,
                           metadata: Dict = None) -> Conversation:
        """
        Create a new conversation
        
        Args:
            user_id: User ID
            title: Conversation title
            initial_message: Initial message content (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Conversation object
        """
        now = datetime.now().isoformat()
        
        conv = Conversation(
            id=f"conv_{uuid.uuid4().hex[:12]}",
            title=title,
            user_id=user_id,
            status=ConversationStatus.ACTIVE.value,
            created_at=now,
            updated_at=now,
            last_message_at=now if initial_message else None,
            message_count=1 if initial_message else 0,
            related_task_ids=[],
            metadata=metadata or {}
        )
        
        # Persist conversation
        self._save_conversation(conv)
        
        # Add initial message
        if initial_message:
            self.add_message(
                conversation_id=conv.id,
                role=MessageRole.USER.value,
                message_type=MessageType.TEXT.value,
                content=initial_message
            )
        
        self.logger.info(f"Created conversation: {conv.id}, title: {title}")
        return conv
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Get conversation by ID
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Conversation object or None
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, user_id, status, created_at, updated_at,
                       last_message_at, message_count, metadata
                FROM conversations
                WHERE id = ?
            """, (conversation_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Get related task IDs
            cursor.execute("""
                SELECT task_id FROM task_conversation_links
                WHERE conversation_id = ?
            """, (conversation_id,))
            related_task_ids = [r[0] for r in cursor.fetchall()]
            
            conv = Conversation(
                id=row[0],
                title=row[1],
                user_id=row[2],
                status=row[3],
                created_at=row[4],
                updated_at=row[5],
                last_message_at=row[6],
                message_count=row[7],
                related_task_ids=related_task_ids,
                metadata=json.loads(row[8]) if row[8] else {}
            )
            
            return conv
    
    def list_conversations(self, user_id: str, status: str = None,
                          page: int = 1, limit: int = 20,
                          search: str = None) -> Dict[str, Any]:
        """
        List conversations with pagination
        
        Args:
            user_id: User ID
            status: Filter by status (optional)
            page: Page number (1-indexed)
            limit: Items per page
            search: Search keyword (optional)
            
        Returns:
            Dictionary with items, total, page, limit
        """
        offset = (page - 1) * limit
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query
            base_query = """
                SELECT id, title, status, last_message_at, message_count
                FROM conversations
                WHERE user_id = ?
            """
            params = [user_id]
            
            if status:
                base_query += " AND status = ?"
                params.append(status)
            
            if search:
                base_query += " AND (title LIKE ? OR id LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])
            
            # Get total count
            count_query = base_query.replace("SELECT id, title, status, last_message_at, message_count", 
                                            "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get items
            base_query += " ORDER BY last_message_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(base_query, params)
            
            rows = cursor.fetchall()
            items = []
            for row in rows:
                items.append({
                    "id": row[0],
                    "title": row[1],
                    "status": row[2],
                    "last_message_at": row[3],
                    "message_count": row[4]
                })
            
            return {
                "items": items,
                "total": total,
                "page": page,
                "limit": limit
            }
    
    def add_message(self, conversation_id: str, role: str, 
                   message_type: str, content: str,
                   metadata: Dict = None) -> Message:
        """
        Add a message to conversation
        
        Args:
            conversation_id: Conversation ID
            role: Message role (user/executive/system/task)
            message_type: Message type (text/plan/task/search/result)
            content: Message content
            metadata: Additional metadata (optional)
            
        Returns:
            Message object
        """
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
        
        # Persist message
        self._save_message(msg)
        
        # Update conversation stats
        self._update_conversation_stats(conversation_id)
        
        return msg
    
    def get_messages(self, conversation_id: str, limit: int = 50,
                    before: str = None) -> List[Message]:
        """
        Get messages for a conversation (paginated)
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages
            before: Get messages before this timestamp (optional)
            
        Returns:
            List of Message objects
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT id, conversation_id, role, message_type, content, 
                       metadata, created_at, read
                FROM messages
                WHERE conversation_id = ?
            """
            params = [conversation_id]
            
            if before:
                query += " AND created_at < ?"
                params.append(before)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                msg = Message(
                    id=row[0],
                    conversation_id=row[1],
                    role=row[2],
                    message_type=row[3],
                    content=row[4],
                    metadata=json.loads(row[5]) if row[5] else {},
                    created_at=row[6],
                    read=bool(row[7])
                )
                messages.append(msg)
            
            # Return in ascending order
            messages.reverse()
            return messages
    
    def link_task_to_conversation(self, task_id: str, conversation_id: str,
                                 link_type: str) -> None:
        """
        Link a task to a conversation
        
        Args:
            task_id: Task ID
            conversation_id: Conversation ID
            link_type: Type of link (created_from/referenced_in/updated_by)
        """
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert link
            cursor.execute("""
                INSERT OR IGNORE INTO task_conversation_links 
                (id, task_id, conversation_id, link_type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"link_{uuid.uuid4().hex[:12]}",
                task_id,
                conversation_id,
                link_type,
                datetime.now().isoformat()
            ))
            
            # Update conversation's related_task_ids
            conv = self.get_conversation(conversation_id)
            if conv and task_id not in conv.related_task_ids:
                conv.related_task_ids.append(task_id)
                conv.updated_at = datetime.now().isoformat()
                self._save_conversation(conv)
        
        self.logger.info(f"Linked task {task_id} to conversation {conversation_id} ({link_type})")
    
    def archive_conversation(self, conversation_id: str) -> None:
        """
        Archive a conversation
        
        Args:
            conversation_id: Conversation ID
        """
        self._update_conversation_status(conversation_id, ConversationStatus.ARCHIVED.value)
        self.logger.info(f"Archived conversation: {conversation_id}")
    
    def delete_conversation(self, conversation_id: str, soft: bool = True) -> None:
        """
        Delete a conversation
        
        Args:
            conversation_id: Conversation ID
            soft: If True, mark as deleted; if False, permanently delete
        """
        if soft:
            self._update_conversation_status(conversation_id, ConversationStatus.DELETED.value)
            self.logger.info(f"Soft deleted conversation: {conversation_id}")
        else:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
                conn.commit()
            self.logger.info(f"Permanently deleted conversation: {conversation_id}")
    
    def _save_conversation(self, conv: Conversation) -> None:
        """Persist conversation to database"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO conversations 
                (id, title, user_id, status, created_at, updated_at, 
                 last_message_at, message_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conv.id,
                conv.title,
                conv.user_id,
                conv.status,
                conv.created_at,
                conv.updated_at,
                conv.last_message_at,
                conv.message_count,
                json.dumps(conv.metadata) if conv.metadata else None
            ))
            
            conn.commit()
    
    def _save_message(self, msg: Message) -> None:
        """Persist message to database"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO messages 
                (id, conversation_id, role, message_type, content, metadata, created_at, read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                msg.id,
                msg.conversation_id,
                msg.role,
                msg.message_type,
                msg.content,
                json.dumps(msg.metadata) if msg.metadata else None,
                msg.created_at,
                msg.read
            ))
            
            conn.commit()
    
    def _update_conversation_stats(self, conversation_id: str) -> None:
        """Update conversation message count and last message time"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get message count
            cursor.execute("""
                SELECT COUNT(*) FROM messages WHERE conversation_id = ?
            """, (conversation_id,))
            message_count = cursor.fetchone()[0]
            
            # Get last message time
            cursor.execute("""
                SELECT MAX(created_at) FROM messages WHERE conversation_id = ?
            """, (conversation_id,))
            last_message_at = cursor.fetchone()[0]
            
            # Update conversation
            cursor.execute("""
                UPDATE conversations 
                SET message_count = ?, last_message_at = ?, updated_at = ?
                WHERE id = ?
            """, (message_count, last_message_at, datetime.now().isoformat(), conversation_id))
            
            conn.commit()
    
    def _update_conversation_status(self, conversation_id: str, status: str) -> None:
        """Update conversation status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE conversations 
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, datetime.now().isoformat(), conversation_id))
            conn.commit()
