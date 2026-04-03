"""
任务并发管理器
支持多 Agent 并发执行，优先级调度，资源隔离
"""

import threading
import time
import heapq
import traceback
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import IntEnum
from dataclasses import dataclass, field
import logging
import weakref


class Priority(IntEnum):
    """任务优先级"""
    CRITICAL = 10    # 紧急故障
    URGENT = 9       # 用户正在等待
    HIGH = 8         # 重要业务
    MEDIUM = 5       # 常规任务
    LOW = 3          # 后台任务
    BACKGROUND = 1   # 可延迟任务


@dataclass(order=True)
class PrioritizedTask:
    """带优先级的任务"""
    # 用于排序的字段（负优先级，这样高优先级的任务先出队）
    sort_key: tuple = field(init=False)
    
    # 实际字段
    priority: int = field(compare=False)
    task_id: str = field(compare=False)
    task_name: str = field(compare=False)
    agent: str = field(compare=False)
    user_id: str = field(compare=False, default='default')
    created_at: float = field(compare=False, default_factory=lambda: datetime.now().timestamp())
    status: str = field(compare=False, default='pending')
    start_time: Optional[datetime] = field(compare=False, default=None)
    end_time: Optional[datetime] = field(compare=False, default=None)
    result: Optional[Dict] = field(compare=False, default=None)
    error: Optional[str] = field(compare=False, default=None)
    
    # 新增字段
    timeout_seconds: Optional[int] = field(compare=False, default=None)  # 超时时间（秒）
    retry_count: int = field(compare=False, default=0)  # 重试次数
    max_retries: int = field(compare=False, default=3)  # 最大重试次数
    retry_delay: int = field(compare=False, default=2)  # 重试延迟（秒）
    is_paused: bool = field(compare=False, default=False)  # 是否暂停
    paused_at: Optional[datetime] = field(compare=False, default=None)  # 暂停时间
    progress: int = field(compare=False, default=0)  # 进度百分比 (0-100)
    progress_description: str = field(compare=False, default='')  # 进度描述
    metadata: Dict = field(compare=False, default_factory=dict)  # 元数据
    
    def __post_init__(self):
        # 创建排序键：(-priority, created_at)，这样高优先级和早创建的任务先出队
        object.__setattr__(self, 'sort_key', (-self.priority, self.created_at))


class TaskPriorityQueue:
    """任务优先级队列"""
    
    def __init__(self):
        self.queue: List[PrioritizedTask] = []
        self.lock = threading.Lock()
        self.task_map: Dict[str, PrioritizedTask] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_task(self, task_id: str, task_name: str, 
                 agent: str, user_id: str = 'default',
                 priority: int = Priority.MEDIUM,
                 timeout_seconds: Optional[int] = None,
                 max_retries: int = 3,
                 metadata: Optional[Dict] = None) -> bool:
        """添加任务到队列"""
        try:
            with self.lock:
                # 如果任务已存在，更新优先级
                if task_id in self.task_map:
                    self.update_priority(task_id, priority)
                    self.logger.info(f"更新任务优先级：{task_id} -> {priority}")
                    return True
                
                task = PrioritizedTask(
                    priority=priority,
                    task_id=task_id,
                    task_name=task_name,
                    agent=agent,
                    user_id=user_id,
                    status='pending',
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    metadata=metadata or {}
                )
                
                heapq.heappush(self.queue, task)
                self.task_map[task_id] = task
                
                self.logger.info(f"添加任务：{task_id} (优先级：{priority}, Agent: {agent})")
                return True
                
        except Exception as e:
            self.logger.error(f"添加任务失败：{e}")
            return False
    
    def get_next_task(self, agent: Optional[str] = None) -> Optional[PrioritizedTask]:
        """获取下一个要执行的任务
        
        Args:
            agent: 指定 Agent 类型，None 则获取任意任务
        
        Returns:
            任务对象，如果没有可用任务则返回 None
        """
        try:
            with self.lock:
                # 临时存储不匹配的任务
                temp_tasks = []
                result = None
                
                while self.queue:
                    task = heapq.heappop(self.queue)
                    
                    # 如果指定了 Agent，只返回匹配的任务
                    if agent is None or task.agent == agent:
                        result = task
                        del self.task_map[task.task_id]
                        break
                    else:
                        # 不匹配的任务先暂存
                        temp_tasks.append(task)
                
                # 把不匹配的任务放回队列
                for task in temp_tasks:
                    heapq.heappush(self.queue, task)
                
                return result
                
        except Exception as e:
            self.logger.error(f"获取任务失败：{e}")
            return None
    
    def update_priority(self, task_id: str, new_priority: int) -> bool:
        """更新任务优先级"""
        try:
            with self.lock:
                if task_id not in self.task_map:
                    return False
                
                task = self.task_map[task_id]
                old_priority = task.priority
                task.priority = new_priority
                
                # 重新排序队列：找到并移除旧任务
                for i, t in enumerate(self.queue):
                    if t.task_id == task_id:
                        self.queue.pop(i)
                        break
                
                # 重新插入（会自动排序）
                heapq.heappush(self.queue, task)
                
                self.logger.info(f"更新任务优先级：{task_id} ({old_priority} -> {new_priority})")
                return True
                
        except Exception as e:
            self.logger.error(f"更新优先级失败：{e}")
            return False
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            with self.lock:
                if task_id not in self.task_map:
                    return False
                
                # 从队列中移除
                for i, t in enumerate(self.queue):
                    if t.task_id == task_id:
                        self.queue.pop(i)
                        break
                
                del self.task_map[task_id]
                self.logger.info(f"移除任务：{task_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"移除任务失败：{e}")
            return False
    
    def get_task(self, task_id: str) -> Optional[PrioritizedTask]:
        """获取任务"""
        with self.lock:
            return self.task_map.get(task_id)
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        try:
            with self.lock:
                by_agent = {}
                by_priority = {}
                by_user = {}
                
                for task in self.queue:
                    # 按 Agent 统计
                    if task.agent not in by_agent:
                        by_agent[task.agent] = 0
                    by_agent[task.agent] += 1
                    
                    # 按优先级统计
                    if task.priority not in by_priority:
                        by_priority[task.priority] = 0
                    by_priority[task.priority] += 1
                    
                    # 按用户统计
                    if task.user_id not in by_user:
                        by_user[task.user_id] = 0
                    by_user[task.user_id] += 1
                
                return {
                    'total': len(self.queue),
                    'by_agent': by_agent,
                    'by_priority': by_priority,
                    'by_user': by_user
                }
                
        except Exception as e:
            self.logger.error(f"获取队列状态失败：{e}")
            return {'total': 0, 'by_agent': {}, 'by_priority': {}, 'by_user': {}}
    
    def get_all_tasks(self) -> List[PrioritizedTask]:
        """获取所有任务"""
        with self.lock:
            return list(self.queue)


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_cpu_usage(self) -> float:
        """获取 CPU 使用率"""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            return 0.0
    
    def get_memory_usage(self) -> Dict:
        """获取内存使用情况"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'percent': mem.percent
            }
        except ImportError:
            return {'total': 0, 'available': 0, 'used': 0, 'percent': 0.0}
    
    def get_process_info(self) -> Dict:
        """获取进程信息"""
        try:
            import psutil
            process = psutil.Process()
            return {
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_percent': process.memory_percent(),
                'memory_info': process.memory_info()._asdict(),
                'num_threads': process.num_threads(),
                'open_files': len(process.open_files())
            }
        except ImportError:
            return {}
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'process': self.get_process_info()
        }


class ConcurrentTaskManager:
    """并发任务管理器"""
    
    def __init__(self, max_concurrent_per_agent: int = 2, 
                 default_timeout: int = 300,  # 默认 5 分钟
                 enable_resource_monitoring: bool = True):
        """
        初始化并发任务管理器
        
        Args:
            max_concurrent_per_agent: 每个 Agent 最大并发任务数
            default_timeout: 默认任务超时时间（秒）
            enable_resource_monitoring: 是否启用资源监控
        """
        self.max_concurrent_per_agent = max_concurrent_per_agent
        self.default_timeout = default_timeout
        self.enable_resource_monitoring = enable_resource_monitoring
        
        self.queue = TaskPriorityQueue()
        
        # 运行中的任务：{agent_type: [task_ids]}
        self.running_tasks: Dict[str, List[str]] = {}
        self.running_lock = threading.Lock()
        
        # 任务执行函数注册表：{agent_type: callable}
        self.task_executors: Dict[str, Callable] = {}
        
        # 线程池
        self.executors: Dict[str, Dict] = {}  # {task_id: {'thread': Thread, 'future': Future}}
        
        # 暂停的任务
        self.paused_tasks: Dict[str, PrioritizedTask] = {}
        
        # 完成的任务历史（最近 N 个）
        self.task_history: List[PrioritizedTask] = []
        self.max_history_size = 100
        
        # 资源监控
        self.resource_monitor = ResourceMonitor() if enable_resource_monitoring else None
        
        # 事件回调
        self.event_callbacks: Dict[str, List[Callable]] = {
            'task_submitted': [],
            'task_started': [],
            'task_completed': [],
            'task_failed': [],
            'task_paused': [],
            'task_resumed': [],
            'task_timeout': []
        }
        
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.scheduler_thread = None
        
        self.logger.info(f"并发任务管理器初始化完成 (最大并发：{max_concurrent_per_agent}/Agent, 默认超时：{default_timeout}s)")
    
    def register_executor(self, agent_type: str, executor_func: Callable):
        """
        注册任务执行函数
        
        Args:
            agent_type: Agent 类型
            executor_func: 执行函数，签名：func(task: PrioritizedTask) -> Dict
        """
        self.task_executors[agent_type] = executor_func
        self.logger.info(f"注册 Agent 执行器：{agent_type}")
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """
        注册事件回调函数
        
        Args:
            event_type: 事件类型 (task_submitted, task_started, task_completed, etc.)
            callback: 回调函数，签名：func(task: PrioritizedTask)
        """
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
            self.logger.debug(f"注册事件回调：{event_type}")
        else:
            self.logger.warning(f"未知事件类型：{event_type}")
    
    def _trigger_event(self, event_type: str, task: PrioritizedTask):
        """触发事件回调"""
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(task)
                except Exception as e:
                    self.logger.error(f"事件回调执行失败：{e}")
    
    def submit_task(self, task_id: str, task_name: str, 
                   agent: str, user_id: str = 'default',
                   priority: int = Priority.MEDIUM,
                   timeout_seconds: Optional[int] = None,
                   max_retries: int = 3,
                   metadata: Optional[Dict] = None) -> bool:
        """
        提交任务
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            agent: 执行 Agent
            user_id: 用户 ID
            priority: 优先级 (1-10)
            timeout_seconds: 超时时间（秒），None 则使用默认值
            max_retries: 最大重试次数
            metadata: 元数据
        
        Returns:
            是否提交成功
        """
        # 添加到队列
        success = self.queue.add_task(
            task_id=task_id,
            task_name=task_name,
            agent=agent,
            user_id=user_id,
            priority=priority,
            timeout_seconds=timeout_seconds or self.default_timeout,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        
        if success:
            # 获取刚添加的任务
            task = self.queue.get_task(task_id)
            if task:
                # 触发事件
                self._trigger_event('task_submitted', task)
            
            # 尝试立即调度
            self._try_schedule()
        
        return success
    
    def _try_schedule(self):
        """尝试调度任务"""
        try:
            # 获取所有 Agent 类型
            all_agents = set(self.queue.get_queue_status()['by_agent'].keys())
            all_agents.update(self.task_executors.keys())
            
            for agent_type in all_agents:
                # 检查该 Agent 的并发数
                with self.running_lock:
                    running_count = len(self.running_tasks.get(agent_type, []))
                
                if running_count >= self.max_concurrent_per_agent:
                    # 达到最大并发数，跳过
                    continue
                
                # 检查是否有该 Agent 的执行器
                if agent_type not in self.task_executors:
                    self.logger.warning(f"Agent {agent_type} 没有注册执行器")
                    continue
                
                # 从队列获取下一个任务
                task = self.queue.get_next_task(agent_type)
                
                if task is None:
                    continue
                
                # 启动任务
                self._start_task(task)
                
        except Exception as e:
            self.logger.error(f"调度失败：{e}")
    
    def _start_task(self, task: PrioritizedTask):
        """启动任务"""
        try:
            # 更新任务状态
            task.status = 'running'
            task.start_time = datetime.now()
            
            # 记录运行中的任务
            with self.running_lock:
                if task.agent not in self.running_tasks:
                    self.running_tasks[task.agent] = []
                self.running_tasks[task.agent].append(task.task_id)
            
            # 触发事件
            self._trigger_event('task_started', task)
            
            # 创建执行线程
            def execute_wrapper():
                try:
                    # 检查是否被暂停
                    if task.is_paused:
                        self.logger.info(f"任务 {task.task_id} 被暂停，等待恢复")
                        while task.is_paused:
                            time.sleep(0.5)
                    
                    # 执行任务（带超时控制）
                    executor_func = self.task_executors[task.agent]
                    
                    # 创建带超时的执行包装
                    result = self._execute_with_timeout(task, executor_func)
                    
                    # 任务完成
                    task.status = 'completed'
                    task.result = result
                    task.end_time = datetime.now()
                    task.progress = 100
                    task.progress_description = '任务已完成'
                    
                    self.logger.info(f"任务完成：{task.task_id}")
                    
                    # 触发事件
                    self._trigger_event('task_completed', task)
                    
                    # 添加到历史记录
                    self._add_to_history(task)
                    
                except TimeoutError as e:
                    # 任务超时
                    task.status = 'timeout'
                    task.error = str(e)
                    task.end_time = datetime.now()
                    
                    self.logger.warning(f"任务超时：{task.task_id} - {e}")
                    
                    # 触发事件
                    self._trigger_event('task_timeout', task)
                    
                    # 尝试重试
                    self._handle_task_retry(task)
                    
                except Exception as e:
                    # 任务失败
                    task.status = 'failed'
                    task.error = str(e)
                    task.end_time = datetime.now()
                    
                    error_trace = traceback.format_exc()
                    self.logger.error(f"任务失败：{task.task_id} - {error_trace}")
                    
                    # 触发事件
                    self._trigger_event('task_failed', task)
                    
                    # 尝试重试
                    self._handle_task_retry(task)
                
                finally:
                    # 清理运行记录
                    with self.running_lock:
                        if task.agent in self.running_tasks:
                            if task.task_id in self.running_tasks[task.agent]:
                                self.running_tasks[task.agent].remove(task.task_id)
                    
                    # 调度下一个任务
                    self._try_schedule()
            
            # 启动线程
            thread = threading.Thread(target=execute_wrapper, daemon=True)
            thread.start()
            
            # 记录线程
            self.executors[task.task_id] = {
                'thread': thread,
                'start_time': task.start_time
            }
            
            self.logger.info(f"任务启动：{task.task_id} (Agent: {task.agent}, 优先级：{task.priority})")
            
        except Exception as e:
            self.logger.error(f"启动任务失败：{e}")
            task.status = 'failed'
            task.error = str(e)
    
    def _execute_with_timeout(self, task: PrioritizedTask, executor_func: Callable) -> Dict:
        """带超时控制的任务执行"""
        import concurrent.futures
        
        timeout = task.timeout_seconds or self.default_timeout
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(executor_func, task)
            try:
                result = future.result(timeout=timeout)
                return result
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"任务执行超时 ({timeout}秒)")
    
    def _handle_task_retry(self, task: PrioritizedTask):
        """处理任务重试"""
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            
            # 计算重试延迟（指数退避）
            delay = task.retry_delay * (2 ** (task.retry_count - 1))
            
            self.logger.info(f"任务将在 {delay} 秒后重试 ({task.retry_count}/{task.max_retries})")
            
            # 延迟后重新提交
            def retry_later():
                time.sleep(delay)
                
                # 重置任务状态
                task.status = 'pending'
                task.error = None
                task.start_time = None
                task.end_time = None
                
                # 重新添加到队列
                self.queue.add_task(
                    task_id=task.task_id,
                    task_name=task.task_name,
                    agent=task.agent,
                    user_id=task.user_id,
                    priority=task.priority
                )
                
                self.logger.info(f"任务重新提交：{task.task_id}")
                
                # 尝试调度
                self._try_schedule()
            
            retry_thread = threading.Thread(target=retry_later, daemon=True)
            retry_thread.start()
        else:
            self.logger.error(f"任务达到最大重试次数，不再重试：{task.task_id}")
    
    def _add_to_history(self, task: PrioritizedTask):
        """添加到任务历史"""
        self.task_history.append(task)
        
        # 保持历史记录大小
        if len(self.task_history) > self.max_history_size:
            self.task_history.pop(0)
    
    def update_task_priority(self, task_id: str, new_priority: int) -> bool:
        """更新任务优先级"""
        return self.queue.update_priority(task_id, new_priority)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        # 从队列中移除
        self.queue.remove_task(task_id)
        
        # 如果正在运行，标记为取消
        # 这里简化处理，实际应该实现线程中断
        return True
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self.queue.get_task(task_id)
        
        if not task:
            # 检查是否在运行中的任务
            with self.running_lock:
                for agent, task_ids in self.running_tasks.items():
                    if task_id in task_ids:
                        # 找到任务，标记为暂停
                        task = self.queue.get_task(task_id)
                        if task:
                            task.is_paused = True
                            task.paused_at = datetime.now()
                            self.paused_tasks[task_id] = task
                            self._trigger_event('task_paused', task)
                            self.logger.info(f"任务已暂停：{task_id}")
                            return True
            return False
        
        # 如果是等待中的任务，直接移到暂停队列
        task.is_paused = True
        task.paused_at = datetime.now()
        self.paused_tasks[task_id] = task
        self.queue.remove_task(task_id)
        self._trigger_event('task_paused', task)
        self.logger.info(f"任务已暂停：{task_id}")
        return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id not in self.paused_tasks:
            return False
        
        task = self.paused_tasks.pop(task_id)
        task.is_paused = False
        task.paused_at = None
        
        # 重新添加到队列
        self.queue.add_task(
            task_id=task.task_id,
            task_name=task.task_name,
            agent=task.agent,
            user_id=task.user_id,
            priority=task.priority
        )
        
        self._trigger_event('task_resumed', task)
        self.logger.info(f"任务已恢复：{task_id}")
        
        # 尝试立即调度
        self._try_schedule()
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.queue.get_task(task_id)
        
        if task:
            return {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'agent': task.agent,
                'user_id': task.user_id,
                'status': task.status,
                'priority': task.priority,
                'progress': task.progress,
                'progress_description': task.progress_description,
                'created_at': datetime.fromtimestamp(task.created_at).isoformat(),
                'start_time': task.start_time.isoformat() if task.start_time else None,
                'end_time': task.end_time.isoformat() if task.end_time else None,
                'result': task.result,
                'error': task.error,
                'retry_count': task.retry_count,
                'max_retries': task.max_retries,
                'is_paused': task.is_paused,
                'timeout_seconds': task.timeout_seconds,
                'metadata': task.metadata
            }
        
        # 检查是否在暂停队列
        if task_id in self.paused_tasks:
            task = self.paused_tasks[task_id]
            return {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'agent': task.agent,
                'user_id': task.user_id,
                'status': 'paused',
                'priority': task.priority,
                'progress': task.progress,
                'paused_at': task.paused_at.isoformat() if task.paused_at else None,
                'created_at': datetime.fromtimestamp(task.created_at).isoformat(),
                'metadata': task.metadata
            }
        
        # 检查是否在历史记录中
        for hist_task in self.task_history:
            if hist_task.task_id == task_id:
                return {
                    'task_id': hist_task.task_id,
                    'task_name': hist_task.task_name,
                    'agent': hist_task.agent,
                    'user_id': hist_task.user_id,
                    'status': hist_task.status,
                    'priority': hist_task.priority,
                    'progress': hist_task.progress,
                    'created_at': datetime.fromtimestamp(hist_task.created_at).isoformat(),
                    'start_time': hist_task.start_time.isoformat() if hist_task.start_time else None,
                    'end_time': hist_task.end_time.isoformat() if hist_task.end_time else None,
                    'result': hist_task.result,
                    'error': hist_task.error,
                    'retry_count': hist_task.retry_count
                }
        
        return None
    
    def get_all_tasks_status(self) -> Dict:
        """获取所有任务状态"""
        queue_status = self.queue.get_queue_status()
        
        running_status = {}
        with self.running_lock:
            for agent, task_ids in self.running_tasks.items():
                running_status[agent] = []
                for task_id in task_ids:
                    if task_id in self.executors:
                        task = self.queue.get_task(task_id)
                        if task:
                            running_status[agent].append({
                                'task_id': task_id,
                                'task_name': task.task_name,
                                'status': 'running',
                                'priority': task.priority,
                                'progress': task.progress,
                                'progress_description': task.progress_description,
                                'started_at': self.executors[task_id]['start_time'].isoformat(),
                                'retry_count': task.retry_count
                            })
        
        paused_status = []
        for task_id, task in self.paused_tasks.items():
            paused_status.append({
                'task_id': task_id,
                'task_name': task.task_name,
                'agent': task.agent,
                'priority': task.priority,
                'paused_at': task.paused_at.isoformat() if task.paused_at else None
            })
        
        history_status = []
        for task in self.task_history[-20:]:  # 最近 20 个
            history_status.append({
                'task_id': task.task_id,
                'task_name': task.task_name,
                'agent': task.agent,
                'status': task.status,
                'end_time': task.end_time.isoformat() if task.end_time else None
            })
        
        result = {
            'queue': queue_status,
            'running': running_status,
            'paused': paused_status,
            'history': history_status,
            'total_running': sum(len(tasks) for tasks in running_status.values()),
            'total_queue': queue_status['total'],
            'total_paused': len(self.paused_tasks),
            'total_history': len(self.task_history)
        }
        
        # 添加资源监控信息
        if self.resource_monitor:
            result['system_resources'] = self.resource_monitor.get_system_status()
        
        return result
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("任务调度器已启动")
    
    def _schedule_loop(self):
        """调度循环"""
        while self.running:
            try:
                self._try_schedule()
            except Exception as e:
                self.logger.error(f"调度循环错误：{e}")
            
            time.sleep(0.1)  # 避免 CPU 占用过高
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("任务调度器已停止")


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 创建任务管理器
    manager = ConcurrentTaskManager(max_concurrent_per_agent=2, default_timeout=30)
    
    # 注册执行器（模拟）
    def mock_executor(task: PrioritizedTask) -> Dict:
        print(f"执行任务：{task.task_name} (优先级：{task.priority})")
        
        # 模拟进度更新
        for i in range(0, 101, 20):
            task.progress = i
            task.progress_description = f'处理中... {i}%'
            time.sleep(0.5)
        
        return {'success': True, 'task_id': task.task_id}
    
    manager.register_executor('three_sages', mock_executor)
    manager.register_executor('market_dept', mock_executor)
    manager.register_executor('monitor_dept', mock_executor)
    
    # 注册事件回调
    def on_task_complete(task):
        print(f"[事件] 任务完成：{task.task_name}")
    
    def on_task_failed(task):
        print(f"[事件] 任务失败：{task.task_name} - {task.error}")
    
    manager.register_event_callback('task_completed', on_task_complete)
    manager.register_event_callback('task_failed', on_task_failed)
    
    # 启动调度器
    manager.start()
    
    # 提交任务
    print("\n[提交任务]")
    manager.submit_task('task_001', '产品方案讨论', 'three_sages', priority=Priority.URGENT)
    manager.submit_task('task_002', '市场分析', 'market_dept', priority=Priority.MEDIUM)
    manager.submit_task('task_003', '消息监控', 'monitor_dept', priority=Priority.HIGH)
    manager.submit_task('task_004', '数据备份', 'it_dept', priority=Priority.LOW, timeout_seconds=10)
    
    # 查看状态
    time.sleep(1)
    print("\n[任务状态]")
    status = manager.get_all_tasks_status()
    print(f"运行中：{status['total_running']}")
    print(f"队列中：{status['total_queue']}")
    
    # 调整优先级
    print("\n[调整优先级]")
    manager.update_task_priority('task_004', Priority.HIGH)
    
    # 暂停任务
    print("\n[暂停任务]")
    manager.pause_task('task_002')
    
    # 恢复任务
    print("\n[恢复任务]")
    time.sleep(2)
    manager.resume_task('task_002')
    
    # 等待完成
    time.sleep(10)
    
    # 查看历史记录
    print("\n[任务历史]")
    status = manager.get_all_tasks_status()
    for hist in status['history']:
        print(f"  - {hist['task_name']}: {hist['status']}")
    
    # 停止
    manager.stop()
