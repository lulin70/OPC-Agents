#!/usr/bin/env python3
"""
Task Executor for OPC-Agents

Executes tasks by coordinating agents, tracking progress, and generating deliverables.
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
import uuid


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(order=True)
class PrioritizedTask:
    """优先级任务包装器"""
    priority: int
    task_id: str = field(compare=False)
    task_data: Dict[str, Any] = field(compare=False)


class TaskExecutor:
    """任务执行引擎
    
    负责从任务队列获取任务，分配给Agent执行，跟踪进度，生成成果物。
    """
    
    def __init__(self, opc_manager, max_workers: int = 5, 
                 progress_streamer=None, db_manager=None):
        """初始化任务执行器
        
        Args:
            opc_manager: OPCManager实例
            max_workers: 最大并行任务数
            progress_streamer: 进度流式传输器
            db_manager: 数据库管理器
        """
        self.opc_manager = opc_manager
        self.max_workers = max_workers
        self.progress_streamer = progress_streamer
        self.db_manager = db_manager
        
        self.logger = logging.getLogger("OPC-Agents.TaskExecutor")
        
        # 任务队列
        self.task_queue = PriorityQueue()
        self.running_tasks: Dict[str, threading.Thread] = {}
        self.task_results: Dict[str, Any] = {}
        
        # 执行状态
        self.is_running = False
        self.executor_thread = None
        
        # 任务超时设置（秒）
        self.task_timeout = 300  # 5分钟
        
        # 回调函数
        self.on_task_complete: Optional[Callable] = None
        self.on_task_failed: Optional[Callable] = None
        self.on_progress_update: Optional[Callable] = None
        
        self.logger.info(f"TaskExecutor initialized with {max_workers} workers")
    
    def start(self):
        """启动任务执行器"""
        if self.is_running:
            self.logger.warning("TaskExecutor is already running")
            return
        
        self.is_running = True
        self.executor_thread = threading.Thread(target=self._execution_loop, daemon=True)
        self.executor_thread.start()
        self.logger.info("TaskExecutor started")
    
    def stop(self):
        """停止任务执行器"""
        self.is_running = False
        if self.executor_thread:
            self.executor_thread.join(timeout=5)
        self.logger.info("TaskExecutor stopped")
    
    def submit_task(self, task_id: str, task_data: Dict[str, Any], 
                    priority: TaskPriority = TaskPriority.MEDIUM) -> bool:
        """提交任务到执行队列
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            priority: 任务优先级
            
        Returns:
            是否成功提交
        """
        prioritized_task = PrioritizedTask(
            priority=priority.value,
            task_id=task_id,
            task_data=task_data
        )
        
        self.task_queue.put(prioritized_task)
        self._broadcast_progress(task_id, TaskState.QUEUED, 0, "任务已加入队列")
        self.logger.info(f"Task {task_id} submitted with priority {priority.name}")
        return True
    
    def _execution_loop(self):
        """执行循环"""
        while self.is_running:
            try:
                # 检查是否有空闲的工作线程
                self._cleanup_finished_tasks()
                
                if len(self.running_tasks) >= self.max_workers:
                    time.sleep(0.5)
                    continue
                
                # 尝试获取任务
                try:
                    prioritized_task = self.task_queue.get(timeout=1)
                except:
                    continue
                
                task_id = prioritized_task.task_id
                task_data = prioritized_task.task_data
                
                # 启动任务执行线程
                thread = threading.Thread(
                    target=self._execute_task,
                    args=(task_id, task_data),
                    daemon=True
                )
                self.running_tasks[task_id] = thread
                thread.start()
                
            except Exception as e:
                self.logger.error(f"Error in execution loop: {e}")
                time.sleep(1)
    
    def _execute_task(self, task_id: str, task_data: Dict[str, Any]):
        """执行单个任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
        """
        start_time = time.time()
        
        try:
            self._broadcast_progress(task_id, TaskState.RUNNING, 0, "开始执行任务")
            
            # 获取任务信息
            task_name = task_data.get("task_name", "")
            agent_name = task_data.get("agent", "")
            department = task_data.get("department", "")
            
            self.logger.info(f"Executing task {task_id}: {task_name}")
            
            # 阶段1: 任务分析
            self._broadcast_progress(task_id, TaskState.RUNNING, 10, "分析任务需求")
            analysis_result = self._analyze_task(task_data)
            time.sleep(0.5)  # 模拟处理时间
            
            # 阶段2: 分配Agent（如果未指定）
            if not agent_name:
                self._broadcast_progress(task_id, TaskState.RUNNING, 20, "寻找合适的Agent")
                best_agent = self.opc_manager.task_manager.find_best_agent_for_task(task_name)
                agent_name = best_agent.get("agent_name", "general_assistant")
                department = best_agent.get("department", "")
            
            # 阶段3: 发送任务给Agent
            self._broadcast_progress(task_id, TaskState.RUNNING, 30, f"分配给Agent: {agent_name}")
            self.opc_manager.task_manager.assign_task_to_agent(task_id, agent_name, department)
            
            # 阶段4: Agent执行任务
            self._broadcast_progress(task_id, TaskState.RUNNING, 40, "Agent开始处理")
            execution_result = self._agent_execute(task_id, task_data, agent_name)
            
            # 阶段5: 生成中间结果
            self._broadcast_progress(task_id, TaskState.RUNNING, 70, "生成执行结果")
            
            # 阶段6: 生成成果物
            self._broadcast_progress(task_id, TaskState.RUNNING, 85, "生成成果物")
            deliverable_result = self.opc_manager.task_manager.complete_task_with_deliverable(
                task_id=task_id,
                result=execution_result,
                description=f"任务由 {agent_name} 完成"
            )
            
            # 阶段7: 完成
            self._broadcast_progress(task_id, TaskState.COMPLETED, 100, "任务完成")
            
            # 记录结果
            self.task_results[task_id] = {
                "status": "completed",
                "agent": agent_name,
                "department": department,
                "result": execution_result,
                "deliverable": deliverable_result.get("deliverable"),
                "execution_time": time.time() - start_time
            }
            
            # 回调
            if self.on_task_complete:
                self.on_task_complete(task_id, self.task_results[task_id])
            
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            self.logger.error(f"Task {task_id} failed: {e}")
            self._broadcast_progress(task_id, TaskState.FAILED, 0, f"任务失败: {str(e)}")
            
            self.task_results[task_id] = {
                "status": "failed",
                "error": str(e),
                "execution_time": time.time() - start_time
            }
            
            if self.on_task_failed:
                self.on_task_failed(task_id, str(e))
    
    def _analyze_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析任务需求
        
        Args:
            task_data: 任务数据
            
        Returns:
            分析结果
        """
        task_name = task_data.get("task_name", "")
        description = task_data.get("description", "")
        
        # 确定任务类型
        task_type = "general"
        if "分析" in task_name or "analysis" in task_name.lower():
            task_type = "analysis"
        elif "设计" in task_name or "design" in task_name.lower():
            task_type = "design"
        elif "开发" in task_name or "develop" in task_name.lower():
            task_type = "development"
        elif "测试" in task_name or "test" in task_name.lower():
            task_type = "testing"
        
        return {
            "task_type": task_type,
            "complexity": "medium",
            "estimated_time": 60,
            "required_skills": []
        }
    
    def _agent_execute(self, task_id: str, task_data: Dict[str, Any], 
                       agent_name: str) -> Dict[str, Any]:
        """Agent执行任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            agent_name: Agent名称
            
        Returns:
            执行结果
        """
        task_name = task_data.get("task_name", "")
        description = task_data.get("description", "")
        
        # 更新进度
        self._broadcast_progress(task_id, TaskState.RUNNING, 50, "Agent正在处理任务")
        
        # 通过通信管理器发送任务给Agent
        try:
            result = self.opc_manager.communication_manager.send_message(
                sender="task_executor",
                receiver=agent_name,
                message_type="task_execution",
                content=f"请执行以下任务:\n任务名称: {task_name}\n描述: {description}",
                context={"task_id": task_id}
            )
            
            # 更新进度
            self._broadcast_progress(task_id, TaskState.RUNNING, 60, "Agent处理中")
            
            return {
                "agent_response": result.get("response", ""),
                "success": result.get("success", False)
            }
        except Exception as e:
            self.logger.warning(f"Agent execution failed: {e}, using fallback")
            return {
                "agent_response": f"任务 {task_name} 已处理",
                "success": True,
                "fallback": True
            }
    
    def _broadcast_progress(self, task_id: str, state: TaskState, 
                           progress: int, message: str):
        """广播任务进度
        
        Args:
            task_id: 任务ID
            state: 任务状态
            progress: 进度百分比
            message: 进度消息
        """
        progress_data = {
            "task_id": task_id,
            "state": state.value,
            "progress": progress,
            "message": message,
            "timestamp": time.time()
        }
        
        # 更新任务状态
        self.opc_manager.task_manager.update_task_status(
            task_id, state.value, progress
        )
        
        # 通过进度流式传输器广播
        if self.progress_streamer:
            try:
                self.progress_streamer.broadcast_progress(task_id, progress_data)
            except Exception as e:
                self.logger.warning(f"Failed to broadcast progress: {e}")
        
        # 回调
        if self.on_progress_update:
            self.on_progress_update(task_id, progress_data)
        
        self.logger.debug(f"Task {task_id}: {state.value} - {progress}% - {message}")
    
    def _cleanup_finished_tasks(self):
        """清理已完成的任务线程"""
        finished_tasks = []
        for task_id, thread in self.running_tasks.items():
            if not thread.is_alive():
                finished_tasks.append(task_id)
        
        for task_id in finished_tasks:
            del self.running_tasks[task_id]
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        if task_id in self.running_tasks:
            return {
                "status": "running",
                "thread_alive": self.running_tasks[task_id].is_alive()
            }
        elif task_id in self.task_results:
            return self.task_results[task_id]
        else:
            return None
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self.task_queue.qsize()
    
    def get_active_workers(self) -> int:
        """获取活跃工作线程数"""
        self._cleanup_finished_tasks()
        return len(self.running_tasks)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        if task_id in self.running_tasks:
            # 无法直接终止线程，标记为取消
            self._broadcast_progress(task_id, TaskState.CANCELLED, 0, "任务已取消")
            self.task_results[task_id] = {
                "status": "cancelled",
                "message": "任务被用户取消"
            }
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取执行器统计信息
        
        Returns:
            统计信息
        """
        completed = sum(1 for r in self.task_results.values() if r.get("status") == "completed")
        failed = sum(1 for r in self.task_results.values() if r.get("status") == "failed")
        cancelled = sum(1 for r in self.task_results.values() if r.get("status") == "cancelled")
        
        return {
            "is_running": self.is_running,
            "queue_size": self.get_queue_size(),
            "active_workers": self.get_active_workers(),
            "max_workers": self.max_workers,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "cancelled_tasks": cancelled,
            "total_processed": len(self.task_results)
        }


class TaskExecutorManager:
    """任务执行器管理器
    
    管理多个任务执行器，支持分布式执行。
    """
    
    def __init__(self, opc_manager):
        """初始化执行器管理器
        
        Args:
            opc_manager: OPCManager实例
        """
        self.opc_manager = opc_manager
        self.logger = logging.getLogger("OPC-Agents.TaskExecutorManager")
        
        self.executors: List[TaskExecutor] = []
        self.current_executor_index = 0
    
    def create_executor(self, max_workers: int = 5, 
                        progress_streamer=None) -> TaskExecutor:
        """创建新的任务执行器
        
        Args:
            max_workers: 最大工作线程数
            progress_streamer: 进度流式传输器
            
        Returns:
            新创建的执行器
        """
        executor = TaskExecutor(
            opc_manager=self.opc_manager,
            max_workers=max_workers,
            progress_streamer=progress_streamer,
            db_manager=self.opc_manager.db_manager
        )
        self.executors.append(executor)
        self.logger.info(f"Created new TaskExecutor with {max_workers} workers")
        return executor
    
    def start_all(self):
        """启动所有执行器"""
        for executor in self.executors:
            executor.start()
        self.logger.info(f"Started {len(self.executors)} executors")
    
    def stop_all(self):
        """停止所有执行器"""
        for executor in self.executors:
            executor.stop()
        self.logger.info("Stopped all executors")
    
    def submit_task(self, task_id: str, task_data: Dict[str, Any],
                    priority: TaskPriority = TaskPriority.MEDIUM) -> bool:
        """提交任务到执行器（轮询分配）
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            priority: 任务优先级
            
        Returns:
            是否成功提交
        """
        if not self.executors:
            self.logger.error("No executors available")
            return False
        
        # 轮询选择执行器
        executor = self.executors[self.current_executor_index]
        self.current_executor_index = (self.current_executor_index + 1) % len(self.executors)
        
        return executor.submit_task(task_id, task_data, priority)
    
    def get_aggregated_statistics(self) -> Dict[str, Any]:
        """获取聚合统计信息
        
        Returns:
            聚合统计信息
        """
        total_stats = {
            "executors_count": len(self.executors),
            "total_queue_size": 0,
            "total_active_workers": 0,
            "total_max_workers": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0
        }
        
        for executor in self.executors:
            stats = executor.get_statistics()
            total_stats["total_queue_size"] += stats["queue_size"]
            total_stats["total_active_workers"] += stats["active_workers"]
            total_stats["total_max_workers"] += stats["max_workers"]
            total_stats["total_completed"] += stats["completed_tasks"]
            total_stats["total_failed"] += stats["failed_tasks"]
            total_stats["total_cancelled"] += stats["cancelled_tasks"]
        
        return total_stats
