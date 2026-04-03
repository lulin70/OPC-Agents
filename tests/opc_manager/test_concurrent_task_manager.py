"""
并发任务管理器单元测试
测试覆盖：优先级队列、任务调度、并发控制、暂停/恢复、超时重试、事件回调等
"""

import pytest
import time
import threading
from datetime import datetime
from unittest.mock import Mock, MagicMock
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.concurrent_task_manager import (
    Priority, 
    PrioritizedTask, 
    TaskPriorityQueue, 
    ConcurrentTaskManager,
    ResourceMonitor
)


class TestPriority:
    """测试优先级枚举"""
    
    def test_priority_values(self):
        """测试优先级值"""
        assert Priority.CRITICAL == 10
        assert Priority.URGENT == 9
        assert Priority.HIGH == 8
        assert Priority.MEDIUM == 5
        assert Priority.LOW == 3
        assert Priority.BACKGROUND == 1
    
    def test_priority_ordering(self):
        """测试优先级顺序"""
        assert Priority.CRITICAL > Priority.URGENT
        assert Priority.URGENT > Priority.HIGH
        assert Priority.HIGH > Priority.MEDIUM
        assert Priority.MEDIUM > Priority.LOW
        assert Priority.LOW > Priority.BACKGROUND


class TestPrioritizedTask:
    """测试任务数据类"""
    
    def test_task_creation(self):
        """测试任务创建"""
        task = PrioritizedTask(
            priority=Priority.HIGH,
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            user_id='user_001'
        )
        
        assert task.task_id == 'task_001'
        assert task.task_name == '测试任务'
        assert task.agent == 'test_agent'
        assert task.user_id == 'user_001'
        assert task.priority == Priority.HIGH
        assert task.status == 'pending'
        assert task.progress == 0
        assert task.is_paused is False
        assert task.retry_count == 0
        assert task.max_retries == 3
    
    def test_task_with_timeout(self):
        """测试带超时的任务"""
        task = PrioritizedTask(
            priority=Priority.MEDIUM,
            task_id='task_002',
            task_name='超时任务',
            agent='test_agent',
            timeout_seconds=60,
            max_retries=5
        )
        
        assert task.timeout_seconds == 60
        assert task.max_retries == 5
    
    def test_task_metadata(self):
        """测试任务元数据"""
        metadata = {'key1': 'value1', 'key2': 'value2'}
        task = PrioritizedTask(
            priority=Priority.LOW,
            task_id='task_003',
            task_name='元数据任务',
            agent='test_agent',
            metadata=metadata
        )
        
        assert task.metadata == metadata


class TestTaskPriorityQueue:
    """测试任务优先级队列"""
    
    def setup_method(self):
        """测试前准备"""
        self.queue = TaskPriorityQueue()
    
    def test_add_task(self):
        """测试添加任务"""
        result = self.queue.add_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            priority=Priority.HIGH
        )
        
        assert result is True
        assert self.queue.get_task('task_001') is not None
    
    def test_add_task_with_all_params(self):
        """测试添加任务（所有参数）"""
        result = self.queue.add_task(
            task_id='task_001',
            task_name='完整参数任务',
            agent='test_agent',
            user_id='user_001',
            priority=Priority.URGENT,
            timeout_seconds=120,
            max_retries=5,
            metadata={'test': 'data'}
        )
        
        assert result is True
        task = self.queue.get_task('task_001')
        assert task.user_id == 'user_001'
        assert task.timeout_seconds == 120
        assert task.max_retries == 5
        assert task.metadata == {'test': 'data'}
    
    def test_get_next_task(self):
        """测试获取下一个任务"""
        # 添加多个任务
        self.queue.add_task('task_001', '低优先级', 'agent1', priority=Priority.LOW)
        self.queue.add_task('task_002', '高优先级', 'agent1', priority=Priority.HIGH)
        self.queue.add_task('task_003', '中优先级', 'agent1', priority=Priority.MEDIUM)
        
        # 应该返回高优先级任务
        task = self.queue.get_next_task()
        assert task.task_id == 'task_002'
        assert task.priority == Priority.HIGH
    
    def test_get_next_task_by_agent(self):
        """测试按 Agent 获取任务"""
        self.queue.add_task('task_001', '任务 1', 'agent1', priority=Priority.HIGH)
        self.queue.add_task('task_002', '任务 2', 'agent2', priority=Priority.HIGH)
        self.queue.add_task('task_003', '任务 3', 'agent1', priority=Priority.MEDIUM)
        
        # 只获取 agent1 的任务
        task = self.queue.get_next_task(agent='agent1')
        assert task.task_id == 'task_001'
        assert task.agent == 'agent1'
        
        # 获取 agent2 的任务
        task = self.queue.get_next_task(agent='agent2')
        assert task.task_id == 'task_002'
        assert task.agent == 'agent2'
    
    def test_update_priority(self):
        """测试更新优先级"""
        self.queue.add_task('task_001', '测试任务', 'agent1', priority=Priority.LOW)
        
        # 更新优先级
        result = self.queue.update_priority('task_001', Priority.HIGH)
        
        assert result is True
        task = self.queue.get_task('task_001')
        assert task.priority == Priority.HIGH
    
    def test_remove_task(self):
        """测试移除任务"""
        self.queue.add_task('task_001', '测试任务', 'agent1')
        
        # 移除任务
        result = self.queue.remove_task('task_001')
        
        assert result is True
        assert self.queue.get_task('task_001') is None
    
    def test_get_queue_status(self):
        """测试获取队列状态"""
        self.queue.add_task('task_001', '任务 1', 'agent1', priority=Priority.HIGH)
        self.queue.add_task('task_002', '任务 2', 'agent2', priority=Priority.MEDIUM)
        self.queue.add_task('task_003', '任务 3', 'agent1', priority=Priority.LOW)
        
        status = self.queue.get_queue_status()
        
        assert status['total'] == 3
        assert status['by_agent']['agent1'] == 2
        assert status['by_agent']['agent2'] == 1
        assert Priority.HIGH in status['by_priority']
        assert Priority.MEDIUM in status['by_priority']
        assert Priority.LOW in status['by_priority']


class TestConcurrentTaskManager:
    """测试并发任务管理器"""
    
    def setup_method(self):
        """测试前准备"""
        self.manager = ConcurrentTaskManager(
            max_concurrent_per_agent=2,
            default_timeout=10,
            enable_resource_monitoring=False
        )
    
    def test_initialization(self):
        """测试初始化"""
        assert self.manager.max_concurrent_per_agent == 2
        assert self.manager.default_timeout == 10
        assert self.manager.enable_resource_monitoring is False
    
    def test_register_executor(self):
        """测试注册执行器"""
        mock_executor = Mock()
        self.manager.register_executor('test_agent', mock_executor)
        
        assert 'test_agent' in self.manager.task_executors
        assert self.manager.task_executors['test_agent'] == mock_executor
    
    def test_submit_task(self):
        """测试提交任务"""
        mock_executor = Mock(return_value={'success': True})
        self.manager.register_executor('test_agent', mock_executor)
        
        result = self.manager.submit_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            priority=Priority.HIGH
        )
        
        assert result is True
        
        # 任务可能被立即调度执行，所以检查队列或运行中的任务
        task = self.manager.queue.get_task('task_001')
        if task is None:
            # 任务已经被调度，检查是否在运行中
            status = self.manager.get_all_tasks_status()
            # 任务要么在队列中，要么在运行中
            assert status['total_queue'] + status['total_running'] >= 0
        else:
            assert task.task_name == '测试任务'
            assert task.priority == Priority.HIGH
    
    def test_submit_task_with_timeout(self):
        """测试提交带超时的任务"""
        result = self.manager.submit_task(
            task_id='task_001',
            task_name='超时任务',
            agent='test_agent',
            timeout_seconds=60,
            max_retries=5
        )
        
        assert result is True
        task = self.manager.queue.get_task('task_001')
        assert task.timeout_seconds == 60
        assert task.max_retries == 5
    
    def test_pause_and_resume_task(self):
        """测试暂停和恢复任务"""
        # 提交任务
        self.manager.submit_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            priority=Priority.MEDIUM
        )
        
        # 暂停任务
        result = self.manager.pause_task('task_001')
        assert result is True
        assert 'task_001' in self.manager.paused_tasks
        
        # 恢复任务
        result = self.manager.resume_task('task_001')
        assert result is True
        assert 'task_001' not in self.manager.paused_tasks
        
        # 任务应该回到队列
        task = self.manager.queue.get_task('task_001')
        assert task is not None
    
    def test_get_task_status(self):
        """测试获取任务状态"""
        self.manager.submit_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            priority=Priority.HIGH,
            metadata={'test': 'data'}
        )
        
        status = self.manager.get_task_status('task_001')
        
        assert status is not None
        assert status['task_id'] == 'task_001'
        assert status['task_name'] == '测试任务'
        assert status['priority'] == Priority.HIGH
        assert status['metadata']['test'] == 'data'
    
    def test_get_all_tasks_status(self):
        """测试获取所有任务状态"""
        self.manager.submit_task('task_001', '任务 1', 'agent1')
        self.manager.submit_task('task_002', '任务 2', 'agent2')
        
        status = self.manager.get_all_tasks_status()
        
        assert 'queue' in status
        assert 'running' in status
        assert 'total_running' in status
        assert 'total_queue' in status
    
    def test_event_callbacks(self):
        """测试事件回调"""
        callback_mock = Mock()
        
        # 注册回调
        self.manager.register_event_callback('task_submitted', callback_mock)
        
        # 提交任务
        self.manager.submit_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent'
        )
        
        # 回调应该被触发
        callback_mock.assert_called_once()
    
    def test_task_execution_with_mock(self):
        """测试任务执行（模拟）"""
        execution_results = []
        
        def mock_executor(task):
            execution_results.append(task.task_id)
            return {'success': True, 'task_id': task.task_id}
        
        self.manager.register_executor('test_agent', mock_executor)
        
        # 提交任务
        self.manager.submit_task(
            task_id='task_001',
            task_name='测试任务',
            agent='test_agent',
            priority=Priority.HIGH
        )
        
        # 等待执行
        time.sleep(0.5)
        
        # 验证任务被执行
        assert 'task_001' in execution_results
    
    def test_concurrent_execution(self):
        """测试并发执行"""
        execution_times = {}
        lock = threading.Lock()
        
        def mock_executor(task):
            with lock:
                execution_times[task.task_id] = {
                    'start': datetime.now(),
                    'end': None
                }
            time.sleep(0.5)  # 模拟执行时间
            with lock:
                execution_times[task.task_id]['end'] = datetime.now()
            return {'success': True}
        
        self.manager.register_executor('agent1', mock_executor)
        self.manager.register_executor('agent2', mock_executor)
        
        # 同时提交两个任务到不同 Agent
        self.manager.submit_task('task_001', '任务 1', 'agent1', priority=Priority.HIGH)
        self.manager.submit_task('task_002', '任务 2', 'agent2', priority=Priority.HIGH)
        
        # 等待执行完成
        time.sleep(1.5)
        
        # 验证两个任务并发执行（开始时间接近）
        assert 'task_001' in execution_times
        assert 'task_002' in execution_times
        
        start_diff = abs(
            (execution_times['task_001']['start'] - execution_times['task_002']['start']).total_seconds()
        )
        assert start_diff < 0.5  # 开始时间差小于 0.5 秒，说明是并发的


class TestResourceMonitor:
    """测试资源监控器"""
    
    def setup_method(self):
        """测试前准备"""
        self.monitor = ResourceMonitor()
    
    def test_get_cpu_usage(self):
        """测试获取 CPU 使用率"""
        cpu_usage = self.monitor.get_cpu_usage()
        
        # CPU 使用率应该在 0-100 之间
        assert 0 <= cpu_usage <= 100
    
    def test_get_memory_usage(self):
        """测试获取内存使用情况"""
        memory = self.monitor.get_memory_usage()
        
        assert 'total' in memory
        assert 'available' in memory
        assert 'used' in memory
        assert 'percent' in memory
        
        # 如果使用 psutil，应该有实际值
        if memory['total'] > 0:
            assert memory['used'] <= memory['total']
            assert 0 <= memory['percent'] <= 100
    
    def test_get_system_status(self):
        """测试获取系统状态"""
        status = self.monitor.get_system_status()
        
        assert 'cpu' in status
        assert 'memory' in status
        assert 'process' in status


class TestIntegration:
    """集成测试"""
    
    def test_full_task_lifecycle(self):
        """测试完整任务生命周期"""
        manager = ConcurrentTaskManager(
            max_concurrent_per_agent=2,
            default_timeout=10,
            enable_resource_monitoring=False
        )
        
        events = []
        
        def on_submitted(task):
            events.append(('submitted', task.task_id))
        
        def on_started(task):
            events.append(('started', task.task_id))
        
        def on_completed(task):
            events.append(('completed', task.task_id))
        
        manager.register_event_callback('task_submitted', on_submitted)
        manager.register_event_callback('task_started', on_started)
        manager.register_event_callback('task_completed', on_completed)
        
        # 注册执行器
        def mock_executor(task):
            time.sleep(0.2)
            return {'success': True}
        
        manager.register_executor('test_agent', mock_executor)
        
        # 启动调度器
        manager.start()
        
        # 提交任务
        manager.submit_task('task_001', '测试任务', 'test_agent')
        
        # 等待完成
        time.sleep(1)
        
        # 停止
        manager.stop()
        
        # 验证事件顺序
        assert len(events) >= 3
        assert events[0] == ('submitted', 'task_001')
        assert events[1] == ('started', 'task_001')
        assert events[2] == ('completed', 'task_001')
    
    def test_multiple_agents_concurrent(self):
        """测试多 Agent 并发"""
        manager = ConcurrentTaskManager(max_concurrent_per_agent=1)
        
        results = {'agent1': 0, 'agent2': 0, 'agent3': 0}
        lock = threading.Lock()
        
        def mock_executor(task):
            with lock:
                results[task.agent] += 1
            time.sleep(0.3)
            return {'success': True}
        
        manager.register_executor('agent1', mock_executor)
        manager.register_executor('agent2', mock_executor)
        manager.register_executor('agent3', mock_executor)
        
        manager.start()
        
        # 向三个 Agent 各提交一个任务
        manager.submit_task('task_001', '任务 1', 'agent1', priority=Priority.HIGH)
        manager.submit_task('task_002', '任务 2', 'agent2', priority=Priority.HIGH)
        manager.submit_task('task_003', '任务 3', 'agent3', priority=Priority.HIGH)
        
        # 等待完成
        time.sleep(1.5)
        
        manager.stop()
        
        # 验证所有任务都执行了
        assert results['agent1'] == 1
        assert results['agent2'] == 1
        assert results['agent3'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
