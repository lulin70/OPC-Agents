# OPC-Agents 多任务并发管理方案

**版本**: 1.0.0  
**创建日期**: 2026-04-03  
**目标**: 支持用户多个任务同时执行，合理分配资源

---

## 一、用户场景分析

### 典型场景

您作为 OPC 公司唯一员工，同时运行多个任务：

```
场景：周一上午 9:00
├─ 任务 1: [定时] 市场分析 Agent - 每天早上 8 点执行
│   内容：搜索竞品动态，生成分析报告
│   预计时长：30 分钟
│   优先级：中 (5)
│
├─ 任务 2: [定时] 消息监控 Agent - 持续运行
│   内容：监控邮件、微信、钉钉新消息
│   预计时长：持续
│   优先级：高 (8)
│
├─ 任务 3: [即时] 产品方案讨论 - 用户正在思考
│   内容：与三贤者讨论新产品方案
│   预计时长：15 分钟
│   优先级：高 (9)
│
└─ 任务 4: [后台] 数据备份 Agent - 每小时执行
    内容：备份重要数据到云存储
    预计时长：5 分钟
    优先级：低 (3)
```

### 关键需求

1. **并发执行**: 不同 Agent 的任务可以同时运行
2. **优先级调度**: 紧急任务优先处理
3. **资源隔离**: 避免任务间相互影响
4. **进度可见**: 实时查看所有任务进度
5. **动态调整**: 用户可以随时调整优先级或暂停任务

---

## 二、系统架构设计

### 2.1 任务队列模型

```
┌─────────────────────────────────────────────────┐
│              用户提交任务                         │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│          任务调度器 (Task Scheduler)             │
│  - 接收任务                                      │
│  - 分配优先级                                    │
│  - 选择执行 Agent                                │
└───────────────┬─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────┐
│         多队列管理系统 (Multi-Queue)             │
│                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ 高优先级队列 │  │ 中优先级队列 │  │ 低优先级 │ │
│  │ (P8-P10)    │  │ (P4-P7)     │  │ (P1-P3)  │ │
│  │             │  │             │  │          │ │
│  │ - 产品讨论  │  │ - 市场分析  │  │ - 数据备份│ │
│  │ - 紧急任务  │  │ - 常规任务  │  │ - 后台任务│ │
│  └──────┬──────┘  └──────┬──────┘  └────┬─────┘ │
│         │                │               │       │
└─────────┼────────────────┼───────────────┼───────┘
          │                │               │
          ▼                ▼               ▼
┌─────────────────────────────────────────────────┐
│         Agent 执行池 (Agent Worker Pool)        │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Agent 1  │ │ Agent 2  │ │ Agent 3  │ ...    │
│  │ 三贤者   │ │ 市场部   │ │ 监控部   │        │
│  │ (运行中) │ │ (运行中) │ │ (运行中) │        │
│  └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────┘
```

### 2.2 并发控制策略

#### 策略 1: 按 Agent 类型并发
```python
# 不同 Agent 可以并发执行
concurrent_tasks = {
    'three_sages': ['task_001'],      # 三贤者：产品讨论
    'market_dept': ['task_002'],      # 市场部：市场分析
    'monitor_dept': ['task_003'],     # 监控部：消息监控
    'it_dept': ['task_004'],          # IT 部：数据备份
}

# 同一 Agent 串行执行（避免资源冲突）
# 例如：三贤者同时只能处理一个任务
```

#### 策略 2: 资源限制
```python
# 系统级并发限制
MAX_CONCURRENT_TASKS = 10  # 最多 10 个任务同时运行
MAX_CPU_PER_TASK = 50%     # 每个任务最多使用 50% CPU
MAX_MEMORY_PER_TASK = 2GB  # 每个任务最多使用 2GB 内存
```

#### 策略 3: 优先级抢占
```python
# 高优先级任务可以抢占低优先级任务的资源
if new_task.priority >= 9 and current_running < max_concurrent:
    # 暂停一个低优先级任务
    lowest_task = get_lowest_priority_running_task()
    pause_task(lowest_task)
    
    # 启动高优先级任务
    start_task(new_task)
```

---

## 三、实现方案

### 3.1 任务优先级队列

```python
import heapq
import threading
from typing import Dict, List, Optional
from enum import IntEnum
from dataclasses import dataclass, field
from datetime import datetime


class Priority(IntEnum):
    """任务优先级"""
    CRITICAL = 10  # 紧急故障
    URGENT = 9     # 用户正在等待
    HIGH = 8       # 重要业务
    MEDIUM = 5     # 常规任务
    LOW = 3        # 后台任务
    BACKGROUND = 1 # 可延迟任务


@dataclass(order=True)
class PrioritizedTask:
    """带优先级的任务"""
    priority: int
    created_at: float = field(compare=False)
    task_id: str = field(compare=False)
    task_name: str = field(compare=False)
    agent: str = field(compare=False)
    status: str = field(compare=False, default='pending')
    
    def __post_init__(self):
        self.created_at = datetime.now().timestamp()


class TaskPriorityQueue:
    """任务优先级队列"""
    
    def __init__(self):
        self.queue: List[PrioritizedTask] = []
        self.lock = threading.Lock()
        self.task_map: Dict[str, PrioritizedTask] = {}
    
    def add_task(self, task_id: str, task_name: str, 
                 agent: str, priority: int = Priority.MEDIUM):
        """添加任务到队列"""
        with self.lock:
            if task_id in self.task_map:
                # 更新已有任务的优先级
                self.update_priority(task_id, priority)
                return
            
            task = PrioritizedTask(
                priority=priority,
                task_id=task_id,
                task_name=task_name,
                agent=agent
            )
            
            heapq.heappush(self.queue, task)
            self.task_map[task_id] = task
    
    def get_next_task(self, agent: str = None) -> Optional[PrioritizedTask]:
        """获取下一个要执行的任务
        
        Args:
            agent: 指定 Agent 类型，None 则获取任意任务
        
        Returns:
            任务对象，如果没有可用任务则返回 None
        """
        with self.lock:
            while self.queue:
                task = heapq.heappop(self.queue)
                
                # 如果指定了 Agent，只返回匹配的任务
                if agent is None or task.agent == agent:
                    del self.task_map[task.task_id]
                    return task
                
                # 不匹配的任务放回队列
                heapq.heappush(self.queue, task)
                
                # 避免死循环
                if len(self.queue) == 0:
                    break
            
            return None
    
    def update_priority(self, task_id: str, new_priority: int):
        """更新任务优先级"""
        with self.lock:
            if task_id not in self.task_map:
                return
            
            task = self.task_map[task_id]
            old_priority = task.priority
            task.priority = new_priority
            
            # 重新排序队列
            # 找到并移除旧任务
            for i, t in enumerate(self.queue):
                if t.task_id == task_id:
                    self.queue.pop(i)
                    break
            
            # 重新插入
            heapq.heappush(self.queue, task)
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        with self.lock:
            by_agent = {}
            by_priority = {}
            
            for task in self.queue:
                # 按 Agent 统计
                if task.agent not in by_agent:
                    by_agent[task.agent] = 0
                by_agent[task.agent] += 1
                
                # 按优先级统计
                if task.priority not in by_priority:
                    by_priority[task.priority] = 0
                by_priority[task.priority] += 1
            
            return {
                'total': len(self.queue),
                'by_agent': by_agent,
                'by_priority': by_priority
            }
```

---

### 3.2 Agent 工作池管理

```python
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Callable


class AgentWorker:
    """Agent 工作单元"""
    
    def __init__(self, worker_id: str, agent_type: str):
        self.worker_id = worker_id
        self.agent_type = agent_type
        self.current_task = None
        self.is_busy = False
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future: Optional[Future] = None
    
    def execute_task(self, task: PrioritizedTask, 
                    task_func: Callable) -> Future:
        """执行任务"""
        if self.is_busy:
            raise Exception(f"Worker {self.worker_id} is busy")
        
        self.current_task = task
        self.is_busy = True
        
        # 异步执行任务
        self.future = self.executor.submit(task_func, task)
        return self.future
    
    def get_status(self) -> Dict:
        """获取 Worker 状态"""
        return {
            'worker_id': self.worker_id,
            'agent_type': self.agent_type,
            'is_busy': self.is_busy,
            'current_task': self.current_task.task_id if self.current_task else None
        }


class AgentWorkerPool:
    """Agent 工作池"""
    
    def __init__(self, max_workers_per_agent: int = 3):
        self.workers: Dict[str, List[AgentWorker]] = {}
        self.max_workers = max_workers_per_agent
        self.lock = threading.Lock()
    
    def get_or_create_worker(self, agent_type: str) -> Optional[AgentWorker]:
        """获取或创建 Worker
        
        Args:
            agent_type: Agent 类型
        
        Returns:
            Worker 实例，如果达到最大并发数则返回 None
        """
        with self.lock:
            if agent_type not in self.workers:
                self.workers[agent_type] = []
            
            # 查找空闲 Worker
            for worker in self.workers[agent_type]:
                if not worker.is_busy:
                    return worker
            
            # 创建新 Worker（如果未达到上限）
            if len(self.workers[agent_type]) < self.max_workers:
                worker_id = f"{agent_type}_{len(self.workers[agent_type])}"
                worker = AgentWorker(worker_id, agent_type)
                self.workers[agent_type].append(worker)
                return worker
            
            # 所有 Worker 都在忙
            return None
    
    def get_pool_status(self) -> Dict:
        """获取工作池状态"""
        with self.lock:
            status = {
                'total_workers': 0,
                'busy_workers': 0,
                'by_agent': {}
            }
            
            for agent_type, workers in self.workers.items():
                busy = sum(1 for w in workers if w.is_busy)
                status['total_workers'] += len(workers)
                status['busy_workers'] += busy
                status['by_agent'][agent_type] = {
                    'total': len(workers),
                    'busy': busy,
                    'idle': len(workers) - busy
                }
            
            return status
    
    def shutdown(self):
        """关闭所有 Worker"""
        with self.lock:
            for workers in self.workers.values():
                for worker in workers:
                    worker.executor.shutdown(wait=False)
            self.workers.clear()
```

---

### 3.3 任务调度器

```python
class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self.priority_queue = TaskPriorityQueue()
        self.worker_pool = AgentWorkerPool(max_workers_per_agent=2)
        self.running_tasks: Dict[str, Dict] = {}
        self.completed_tasks = []
        self.lock = threading.Lock()
        self.scheduler_thread = None
        self.running = False
    
    def submit_task(self, task_id: str, task_name: str, 
                   agent: str, priority: int = 5,
                   task_func: Callable = None):
        """提交任务
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            agent: 执行 Agent
            priority: 优先级 (1-10)
            task_func: 任务执行函数
        """
        # 添加到优先级队列
        self.priority_queue.add_task(
            task_id=task_id,
            task_name=task_name,
            agent=agent,
            priority=priority
        )
        
        # 尝试立即调度
        self._try_schedule()
    
    def _try_schedule(self):
        """尝试调度任务"""
        with self.lock:
            # 遍历所有 Agent 类型
            for agent_type in self._get_all_agent_types():
                # 获取空闲 Worker
                worker = self.worker_pool.get_or_create_worker(agent_type)
                
                if worker is None:
                    # 没有空闲 Worker
                    continue
                
                # 从队列获取下一个任务
                task = self.priority_queue.get_next_task(agent_type)
                
                if task is None:
                    # 没有可用任务
                    continue
                
                # 启动任务
                self._start_task(worker, task)
    
    def _start_task(self, worker: AgentWorker, task: PrioritizedTask):
        """启动任务"""
        # 创建任务执行包装函数
        def execute_wrapper(t):
            try:
                # 更新任务状态
                with self.lock:
                    self.running_tasks[t.task_id] = {
                        'task': t,
                        'worker': worker,
                        'start_time': datetime.now(),
                        'status': 'running'
                    }
                
                # 执行实际任务（这里应该调用实际的任务处理函数）
                result = self._execute_task_logic(t)
                
                # 任务完成
                with self.lock:
                    self.running_tasks[t.task_id]['status'] = 'completed'
                    self.running_tasks[t.task_id]['result'] = result
                    self.completed_tasks.append(t.task_id)
                    worker.is_busy = False
                    worker.current_task = None
                
                # 调度下一个任务
                self._try_schedule()
                
                return result
                
            except Exception as e:
                # 任务失败
                with self.lock:
                    self.running_tasks[t.task_id]['status'] = 'failed'
                    self.running_tasks[t.task_id]['error'] = str(e)
                    worker.is_busy = False
                    worker.current_task = None
                
                # 调度下一个任务
                self._try_schedule()
                
                raise
        
        # 在 Worker 中执行
        worker.execute_task(task, execute_wrapper)
    
    def _execute_task_logic(self, task: PrioritizedTask):
        """执行任务逻辑（占位符）"""
        # 实际应该调用对应的 Agent 执行函数
        time.sleep(1)  # 模拟执行
        return {'success': True}
    
    def _get_all_agent_types(self) -> List[str]:
        """获取所有 Agent 类型"""
        # 实际应该从配置中获取
        return ['three_sages', 'market_dept', 'monitor_dept', 'it_dept']
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        with self.lock:
            return {
                'queue': self.priority_queue.get_queue_status(),
                'worker_pool': self.worker_pool.get_pool_status(),
                'running_tasks': {
                    task_id: {
                        'name': info['task'].task_name,
                        'agent': info['task'].agent,
                        'priority': info['task'].priority,
                        'start_time': info['start_time'].isoformat(),
                        'status': info['status']
                    }
                    for task_id, info in self.running_tasks.items()
                },
                'completed_count': len(self.completed_tasks)
            }
    
    def start(self):
        """启动调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._schedule_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
    
    def _schedule_loop(self):
        """调度循环"""
        while self.running:
            try:
                self._try_schedule()
            except Exception as e:
                self.logger.error(f"调度错误：{e}")
            
            time.sleep(0.1)  # 避免 CPU 占用过高
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self.worker_pool.shutdown()
```

---

## 四、用户使用界面

### 4.1 任务监控面板

```html
<!-- 任务监控面板 -->
<div class="task-monitor">
    <h2>📊 任务监控</h2>
    
    <!-- 统计卡片 -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">4</div>
            <div class="stat-label">运行中任务</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">12</div>
            <div class="stat-label">等待中任务</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">8</div>
            <div class="stat-label">今日完成</div>
        </div>
    </div>
    
    <!-- 运行中任务列表 -->
    <div class="running-tasks">
        <h3>🔄 运行中任务</h3>
        
        <div class="task-item">
            <div class="task-header">
                <span class="task-name">📈 市场分析日报</span>
                <span class="task-priority priority-medium">中优先级</span>
                <span class="task-agent">🏢 市场部</span>
            </div>
            <div class="task-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 65%"></div>
                </div>
                <span class="progress-text">65% - 正在收集竞品数据</span>
            </div>
            <div class="task-meta">
                <span>开始时间：08:00:00</span>
                <span>预计剩余：10 分钟</span>
                <button class="btn-pause">⏸ 暂停</button>
                <button class="btn-priority">⬆ 提权</button>
            </div>
        </div>
        
        <div class="task-item">
            <div class="task-header">
                <span class="task-name">📧 消息监控</span>
                <span class="task-priority priority-high">高优先级</span>
                <span class="task-agent">👁 监控部</span>
            </div>
            <div class="task-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 100%"></div>
                </div>
                <span class="progress-text">持续运行中</span>
            </div>
            <div class="task-meta">
                <span>开始时间：00:00:00</span>
                <span>已运行：9 小时</span>
                <button class="btn-pause">⏸ 暂停</button>
            </div>
        </div>
        
        <div class="task-item">
            <div class="task-header">
                <span class="task-name">💡 产品方案讨论</span>
                <span class="task-priority priority-high">高优先级</span>
                <span class="task-agent">🧙 三贤者</span>
            </div>
            <div class="task-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 30%"></div>
                </div>
                <span class="progress-text">30% - 正在分析市场需求</span>
            </div>
            <div class="task-meta">
                <span>开始时间：09:15:00</span>
                <span>预计剩余：10 分钟</span>
                <button class="btn-pause">⏸ 暂停</button>
                <button class="btn-priority">⬆ 提权</button>
            </div>
        </div>
    </div>
    
    <!-- 等待队列 -->
    <div class="waiting-queue">
        <h3>⏳ 等待队列</h3>
        <table>
            <thead>
                <tr>
                    <th>任务名称</th>
                    <th>优先级</th>
                    <th>Agent</th>
                    <th>排队位置</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>📊 数据备份</td>
                    <td><span class="priority-low">低</span></td>
                    <td>💻 IT 部</td>
                    <td>#1</td>
                    <td>
                        <button class="btn-cancel">❌ 取消</button>
                        <button class="btn-priority">⬆ 提权</button>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
```

---

### 4.2 用户操作 API

```python
# 提交新任务
@app.route('/api/task', methods=['POST'])
def submit_task():
    data = request.json
    scheduler.submit_task(
        task_id=data['task_id'],
        task_name=data['name'],
        agent=data['agent'],
        priority=data.get('priority', 5),
        task_func=execute_task
    )
    return {'success': True, 'task_id': data['task_id']}

# 调整任务优先级
@app.route('/api/task/<task_id>/priority', methods=['PUT'])
def update_task_priority(task_id):
    new_priority = request.json.get('priority')
    scheduler.priority_queue.update_priority(task_id, new_priority)
    return {'success': True}

# 暂停任务
@app.route('/api/task/<task_id>/pause', methods=['POST'])
def pause_task(task_id):
    # 实现暂停逻辑
    return {'success': True}

# 恢复任务
@app.route('/api/task/<task_id>/resume', methods=['POST'])
def resume_task(task_id):
    # 实现恢复逻辑
    return {'success': True}

# 获取任务状态
@app.route('/api/task/<task_id>/status')
def get_task_status(task_id):
    status = scheduler.get_status()
    # 返回特定任务的状态
    return status

# 获取所有任务
@app.route('/api/tasks')
def get_all_tasks():
    return scheduler.get_status()
```

---

## 五、资源配置建议

### 5.1 并发限制

```python
# 系统配置
CONFIG = {
    # 最大并发任务数
    'max_concurrent_tasks': 10,
    
    # 每个 Agent 的最大 Worker 数
    'max_workers_per_agent': 2,
    
    # 资源限制
    'max_cpu_per_task': 0.5,      # 50% CPU
    'max_memory_per_task': 2048,  # 2GB 内存
    
    # 优先级配置
    'priority_levels': {
        'critical': 10,
        'urgent': 9,
        'high': 8,
        'medium': 5,
        'low': 3,
        'background': 1
    }
}
```

### 5.2 超时和重试

```python
# 任务超时配置
TIMEOUT_CONFIG = {
    'default_timeout': 300,        # 默认 5 分钟
    'long_task_timeout': 1800,     # 长任务 30 分钟
    'infinite_timeout': -1,        # 持续运行任务（如监控）
}

# 重试配置
RETRY_CONFIG = {
    'max_retries': 3,
    'retry_delay': 2,              # 秒
    'exponential_backoff': True    # 指数退避
}
```

---

## 六、监控和告警

### 6.1 监控指标

```python
# Prometheus 指标
from prometheus_client import Counter, Histogram, Gauge

# 任务指标
TASK_SUBMITTED = Counter('tasks_submitted_total', 'Total tasks submitted')
TASK_COMPLETED = Counter('tasks_completed_total', 'Total tasks completed')
TASK_FAILED = Counter('tasks_failed_total', 'Total tasks failed')
TASK_DURATION = Histogram('task_duration_seconds', 'Task duration')

# 队列指标
QUEUE_SIZE = Gauge('task_queue_size', 'Current queue size')
QUEUE_WAIT_TIME = Histogram('task_queue_wait_seconds', 'Task wait time in queue')

# Worker 指标
WORKER_BUSY = Gauge('worker_busy_count', 'Number of busy workers')
WORKER_IDLE = Gauge('worker_idle_count', 'Number of idle workers')
```

### 6.2 告警规则

```yaml
# Prometheus 告警规则
groups:
  - name: task_alerts
    rules:
      - alert: HighQueueSize
        expr: task_queue_size > 50
        for: 5m
        annotations:
          summary: "任务队列积压过多"
          description: "队列中有 {{ $value }} 个任务等待执行"
      
      - alert: TaskFailureRate
        expr: rate(tasks_failed_total[5m]) / rate(tasks_submitted_total[5m]) > 0.2
        for: 5m
        annotations:
          summary: "任务失败率过高"
          description: "任务失败率达到 {{ $value | humanizePercentage }}"
      
      - alert: LongRunningTask
        expr: task_duration_seconds > 1800
        annotations:
          summary: "任务执行时间过长"
          description: "任务已运行超过 30 分钟"
```

---

## 七、总结

### 核心优势

1. **真正的并发执行**: 不同 Agent 的任务可以同时运行
2. **智能优先级调度**: 紧急任务优先，支持动态调整
3. **资源隔离**: 避免任务间相互影响
4. **可视化监控**: 实时查看所有任务进度
5. **灵活配置**: 支持自定义并发数、超时、重试等

### 用户价值

- ✅ **解放用户**: 可以同时运行多个任务，无需等待
- ✅ **灵活控制**: 随时调整优先级、暂停/恢复任务
- ✅ **透明可见**: 清楚知道每个任务的执行状态
- ✅ **资源优化**: 合理分配系统资源，避免过载

### 实施建议

1. **第一阶段** (1 周): 实现基础任务队列和调度器
2. **第二阶段** (1 周): 实现 Worker 池和并发控制
3. **第三阶段** (1 周): 实现监控面板和告警
4. **第四阶段** (1 周): 用户测试和优化

---

**文档维护**: OPC-Agents 架构团队  
**最后更新**: 2026-04-03
