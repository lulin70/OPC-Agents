#!/usr/bin/env python3
"""
数据访问对象（DAO）

提供数据库的CRUD操作接口。
"""

import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from .models import MessageRecord, TaskRecord, ConversationRecord, AgentRecord, DeliverableRecord


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data_storage/opc_agents.db"):
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建消息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    receiver TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'user',
                    status TEXT DEFAULT 'pending',
                    timestamp REAL NOT NULL,
                    progress INTEGER DEFAULT 0,
                    error TEXT,
                    metadata TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    progress INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    assigned_to TEXT,
                    description TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # 创建对话历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    messages TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    summary TEXT,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            ''')
            
            # 创建Agent表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    department TEXT NOT NULL,
                    role TEXT,
                    skills TEXT DEFAULT '[]',
                    performance_score REAL DEFAULT 0.0,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_in_progress INTEGER DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            ''')
            
            # 创建成果物表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deliverables (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT DEFAULT 'document',
                    content TEXT,
                    file_path TEXT,
                    version INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    created_by TEXT,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_task_id ON messages(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agents_department ON agents(department)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_deliverables_task_id ON deliverables(task_id)')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # 消息相关操作
    def save_message(self, message: MessageRecord) -> bool:
        """保存消息记录
        
        Args:
            message: 消息记录对象
            
        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO messages 
                (id, task_id, sender, receiver, content, message_type, status, timestamp, progress, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                message.id, message.task_id, message.sender, message.receiver,
                message.content, message.message_type, message.status,
                message.timestamp, message.progress, message.error, message.metadata
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"消息已保存: {message.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存消息失败: {e}")
            return False
    
    def get_message_by_id(self, message_id: str) -> Optional[MessageRecord]:
        """根据ID获取消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            消息记录对象，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return MessageRecord(
                    id=row['id'], task_id=row['task_id'], sender=row['sender'],
                    receiver=row['receiver'], content=row['content'],
                    message_type=row['message_type'], status=row['status'],
                    timestamp=row['timestamp'], progress=row['progress'],
                    error=row['error'], metadata=row['metadata']
                )
            return None
            
        except Exception as e:
            self.logger.error(f"获取消息失败: {e}")
            return None
    
    def get_messages_by_task(self, task_id: str) -> List[MessageRecord]:
        """根据任务ID获取所有消息
        
        Args:
            task_id: 任务ID
            
        Returns:
            消息记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp ASC',
                (task_id,)
            )
            rows = cursor.fetchall()
            
            conn.close()
            
            messages = []
            for row in rows:
                messages.append(MessageRecord(
                    id=row['id'], task_id=row['task_id'], sender=row['sender'],
                    receiver=row['receiver'], content=row['content'],
                    message_type=row['message_type'], status=row['status'],
                    timestamp=row['timestamp'], progress=row['progress'],
                    error=row['error'], metadata=row['metadata']
                ))
            
            return messages
            
        except Exception as e:
            self.logger.error(f"获取任务消息失败: {e}")
            return []
    
    # 任务相关操作
    def save_task(self, task: TaskRecord) -> bool:
        """保存任务记录
        
        Args:
            task: 任务记录对象
            
        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO tasks 
                (id, name, status, progress, created_at, updated_at, assigned_to, description, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.id, task.name, task.status, task.progress,
                task.created_at, task.updated_at, task.assigned_to,
                task.description, task.metadata
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"任务已保存: {task.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存任务失败: {e}")
            return False
    
    def get_task_by_id(self, task_id: str) -> Optional[TaskRecord]:
        """根据ID获取任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务记录对象，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return TaskRecord(
                    id=row['id'], name=row['name'], status=row['status'],
                    progress=row['progress'], created_at=row['created_at'],
                    updated_at=row['updated_at'], assigned_to=row['assigned_to'],
                    description=row['description'], metadata=row['metadata']
                )
            return None
            
        except Exception as e:
            self.logger.error(f"获取任务失败: {e}")
            return None
    
    def get_all_tasks(self) -> List[TaskRecord]:
        """获取所有任务
        
        Returns:
            任务记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM tasks ORDER BY updated_at DESC')
            rows = cursor.fetchall()
            
            conn.close()
            
            tasks = []
            for row in rows:
                tasks.append(TaskRecord(
                    id=row['id'], name=row['name'], status=row['status'],
                    progress=row['progress'], created_at=row['created_at'],
                    updated_at=row['updated_at'], assigned_to=row['assigned_to'],
                    description=row['description'], metadata=row['metadata']
                ))
            
            return tasks
            
        except Exception as e:
            self.logger.error(f"获取所有任务失败: {e}")
            return []
    
    # Agent相关操作
    def save_agent(self, agent: AgentRecord) -> bool:
        """保存Agent记录
        
        Args:
            agent: Agent记录对象
            
        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO agents 
                (id, name, department, role, skills, performance_score, tasks_completed, 
                 tasks_in_progress, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                agent.id, agent.name, agent.department, agent.role,
                agent.skills, agent.performance_score, agent.tasks_completed,
                agent.tasks_in_progress, agent.created_at, agent.updated_at,
                agent.metadata
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"Agent已保存: {agent.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存Agent失败: {e}")
            return False
    
    def get_agent_by_id(self, agent_id: str) -> Optional[AgentRecord]:
        """根据ID获取Agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent记录对象，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return AgentRecord(
                    id=row['id'], name=row['name'], department=row['department'],
                    role=row['role'], skills=row['skills'],
                    performance_score=row['performance_score'],
                    tasks_completed=row['tasks_completed'],
                    tasks_in_progress=row['tasks_in_progress'],
                    created_at=row['created_at'], updated_at=row['updated_at'],
                    metadata=row['metadata']
                )
            return None
            
        except Exception as e:
            self.logger.error(f"获取Agent失败: {e}")
            return None
    
    def get_agents_by_department(self, department: str) -> List[AgentRecord]:
        """根据部门获取Agent列表
        
        Args:
            department: 部门名称
            
        Returns:
            Agent记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM agents WHERE department = ? ORDER BY performance_score DESC',
                (department,)
            )
            rows = cursor.fetchall()
            
            conn.close()
            
            agents = []
            for row in rows:
                agents.append(AgentRecord(
                    id=row['id'], name=row['name'], department=row['department'],
                    role=row['role'], skills=row['skills'],
                    performance_score=row['performance_score'],
                    tasks_completed=row['tasks_completed'],
                    tasks_in_progress=row['tasks_in_progress'],
                    created_at=row['created_at'], updated_at=row['updated_at'],
                    metadata=row['metadata']
                ))
            
            return agents
            
        except Exception as e:
            self.logger.error(f"获取部门Agent失败: {e}")
            return []
    
    # 成果物相关操作
    def save_deliverable(self, deliverable: DeliverableRecord) -> bool:
        """保存成果物记录
        
        Args:
            deliverable: 成果物记录对象
            
        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO deliverables 
                (id, task_id, name, type, content, file_path, version, 
                 created_at, updated_at, created_by, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                deliverable.id, deliverable.task_id, deliverable.name,
                deliverable.type, deliverable.content, deliverable.file_path,
                deliverable.version, deliverable.created_at, deliverable.updated_at,
                deliverable.created_by, deliverable.metadata
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"成果物已保存: {deliverable.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存成果物失败: {e}")
            return False
    
    def get_deliverables_by_task(self, task_id: str) -> List[DeliverableRecord]:
        """根据任务ID获取成果物列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            成果物记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM deliverables WHERE task_id = ? ORDER BY created_at DESC',
                (task_id,)
            )
            rows = cursor.fetchall()
            
            conn.close()
            
            deliverables = []
            for row in rows:
                deliverables.append(DeliverableRecord(
                    id=row['id'], task_id=row['task_id'], name=row['name'],
                    type=row['type'], content=row['content'], file_path=row['file_path'],
                    version=row['version'], created_at=row['created_at'],
                    updated_at=row['updated_at'], created_by=row['created_by'],
                    metadata=row['metadata']
                ))
            
            return deliverables
            
        except Exception as e:
            self.logger.error(f"获取任务成果物失败: {e}")
            return []
