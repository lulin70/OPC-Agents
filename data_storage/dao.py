#!/usr/bin/env python3
"""
数据访问对象（DAO）

提供数据库的CRUD操作接口。
"""

import sqlite3
import json
import logging
import threading
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from collections import OrderedDict
from .models import MessageRecord, TaskRecord, ConversationRecord, AgentRecord, DeliverableRecord


class ConnectionPool:
    """数据库连接池"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        """初始化连接池
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        with self.lock:
            # 尝试从连接池获取可用连接
            for conn in self.connections:
                if conn and not conn.in_transaction:
                    return conn
            
            # 如果连接池已满，等待一段时间
            if len(self.connections) >= self.max_connections:
                self.logger.warning("连接池已满，等待可用连接")
                time.sleep(0.1)
                # 再次尝试获取
                for conn in self.connections:
                    if conn and not conn.in_transaction:
                        return conn
            
            # 创建新连接
            try:
                conn = sqlite3.connect(
                    self.db_path,
                    timeout=30,  # 增加超时时间
                    check_same_thread=False  # 允许跨线程使用
                )
                conn.row_factory = sqlite3.Row
                conn.execute('PRAGMA journal_mode = WAL')  # 使用WAL模式
                conn.execute('PRAGMA synchronous = NORMAL')  # 同步模式设为NORMAL
                conn.execute('PRAGMA busy_timeout = 30000')  # 设置忙时超时
                self.connections.append(conn)
                self.logger.debug(f"创建新数据库连接，当前连接数: {len(self.connections)}")
                return conn
            except Exception as e:
                self.logger.error(f"创建数据库连接失败: {e}")
                raise
    
    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            for conn in self.connections:
                try:
                    conn.close()
                except Exception as e:
                    self.logger.error(f"关闭连接失败: {e}")
            self.connections = []


class LRUCache:
    """LRU缓存"""
    
    def __init__(self, capacity: int = 100):
        """初始化缓存
        
        Args:
            capacity: 缓存容量
        """
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回None
        """
        with self.lock:
            if key in self.cache:
                # 移到末尾表示最近使用
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        with self.lock:
            if key in self.cache:
                # 移到末尾表示最近使用
                self.cache.move_to_end(key)
            elif len(self.cache) >= self.capacity:
                # 移除最久未使用的项
                self.cache.popitem(last=False)
            self.cache[key] = value
    
    def delete(self, key: str):
        """删除缓存
        
        Args:
            key: 缓存键
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data_storage/opc_agents.db"):
        """初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.connection_pool = ConnectionPool(db_path)
        self.cache = LRUCache()
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = self.connection_pool.get_connection()
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
            
            self.logger.info(f"数据库初始化完成: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            if 'conn' in locals():
                try:
                    conn.close()
                except:
                    pass
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        Returns:
            数据库连接对象
        """
        return self.connection_pool.get_connection()
    
    def begin_transaction(self) -> sqlite3.Connection:
        """开始事务
        
        Returns:
            数据库连接对象
        """
        conn = self._get_connection()
        conn.execute('BEGIN TRANSACTION')
        return conn
    
    def commit_transaction(self, conn: sqlite3.Connection):
        """提交事务
        
        Args:
            conn: 数据库连接对象
        """
        try:
            conn.commit()
        except Exception as e:
            self.logger.error(f"提交事务失败: {e}")
            raise
    
    def rollback_transaction(self, conn: sqlite3.Connection):
        """回滚事务
        
        Args:
            conn: 数据库连接对象
        """
        try:
            conn.rollback()
        except Exception as e:
            self.logger.error(f"回滚事务失败: {e}")
            raise

    
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
            
            # 更新缓存
            self.cache.set(f"message:{message.id}", message)
            # 清除相关缓存
            self.cache.delete(f"messages:task:{message.task_id}")
            
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
        # 尝试从缓存获取
        cached_message = self.cache.get(f"message:{message_id}")
        if cached_message:
            return cached_message
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
            row = cursor.fetchone()
            
            if row:
                message = MessageRecord(
                    id=row['id'], task_id=row['task_id'], sender=row['sender'],
                    receiver=row['receiver'], content=row['content'],
                    message_type=row['message_type'], status=row['status'],
                    timestamp=row['timestamp'], progress=row['progress'],
                    error=row['error'], metadata=row['metadata']
                )
                # 存入缓存
                self.cache.set(f"message:{message_id}", message)
                return message
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
        # 尝试从缓存获取
        cached_messages = self.cache.get(f"messages:task:{task_id}")
        if cached_messages:
            return cached_messages
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM messages WHERE task_id = ? ORDER BY timestamp ASC',
                (task_id,)
            )
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                messages.append(MessageRecord(
                    id=row['id'], task_id=row['task_id'], sender=row['sender'],
                    receiver=row['receiver'], content=row['content'],
                    message_type=row['message_type'], status=row['status'],
                    timestamp=row['timestamp'], progress=row['progress'],
                    error=row['error'], metadata=row['metadata']
                ))
            
            # 存入缓存
            self.cache.set(f"messages:task:{task_id}", messages)
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
            
            # 更新缓存
            self.cache.set(f"task:{task.id}", task)
            # 清除相关缓存
            self.cache.delete("tasks:all")
            
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
        # 尝试从缓存获取
        cached_task = self.cache.get(f"task:{task_id}")
        if cached_task:
            return cached_task
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            
            if row:
                task = TaskRecord(
                    id=row['id'], name=row['name'], status=row['status'],
                    progress=row['progress'], created_at=row['created_at'],
                    updated_at=row['updated_at'], assigned_to=row['assigned_to'],
                    description=row['description'], metadata=row['metadata']
                )
                # 存入缓存
                self.cache.set(f"task:{task_id}", task)
                return task
            return None
            
        except Exception as e:
            self.logger.error(f"获取任务失败: {e}")
            return None
    
    def get_all_tasks(self) -> List[TaskRecord]:
        """获取所有任务
        
        Returns:
            任务记录列表
        """
        # 尝试从缓存获取
        cached_tasks = self.cache.get("tasks:all")
        if cached_tasks:
            return cached_tasks
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM tasks ORDER BY updated_at DESC')
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                tasks.append(TaskRecord(
                    id=row['id'], name=row['name'], status=row['status'],
                    progress=row['progress'], created_at=row['created_at'],
                    updated_at=row['updated_at'], assigned_to=row['assigned_to'],
                    description=row['description'], metadata=row['metadata']
                ))
            
            # 存入缓存
            self.cache.set("tasks:all", tasks)
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
            
            # 更新缓存
            self.cache.set(f"agent:{agent.id}", agent)
            # 清除相关缓存
            self.cache.delete(f"agents:department:{agent.department}")
            
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
        # 尝试从缓存获取
        cached_agent = self.cache.get(f"agent:{agent_id}")
        if cached_agent:
            return cached_agent
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
            row = cursor.fetchone()
            
            if row:
                agent = AgentRecord(
                    id=row['id'], name=row['name'], department=row['department'],
                    role=row['role'], skills=row['skills'],
                    performance_score=row['performance_score'],
                    tasks_completed=row['tasks_completed'],
                    tasks_in_progress=row['tasks_in_progress'],
                    created_at=row['created_at'], updated_at=row['updated_at'],
                    metadata=row['metadata']
                )
                # 存入缓存
                self.cache.set(f"agent:{agent_id}", agent)
                return agent
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
        # 尝试从缓存获取
        cached_agents = self.cache.get(f"agents:department:{department}")
        if cached_agents:
            return cached_agents
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM agents WHERE department = ? ORDER BY performance_score DESC',
                (department,)
            )
            rows = cursor.fetchall()
            
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
            
            # 存入缓存
            self.cache.set(f"agents:department:{department}", agents)
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
            
            # 更新缓存
            self.cache.set(f"deliverable:{deliverable.id}", deliverable)
            # 清除相关缓存
            self.cache.delete(f"deliverables:task:{deliverable.task_id}")
            
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
        # 尝试从缓存获取
        cached_deliverables = self.cache.get(f"deliverables:task:{task_id}")
        if cached_deliverables:
            return cached_deliverables
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM deliverables WHERE task_id = ? ORDER BY created_at DESC',
                (task_id,)
            )
            rows = cursor.fetchall()
            
            deliverables = []
            for row in rows:
                deliverables.append(DeliverableRecord(
                    id=row['id'], task_id=row['task_id'], name=row['name'],
                    type=row['type'], content=row['content'], file_path=row['file_path'],
                    version=row['version'], created_at=row['created_at'],
                    updated_at=row['updated_at'], created_by=row['created_by'],
                    metadata=row['metadata']
                ))
            
            # 存入缓存
            self.cache.set(f"deliverables:task:{task_id}", deliverables)
            return deliverables
            
        except Exception as e:
            self.logger.error(f"获取任务成果物失败: {e}")
            return []
