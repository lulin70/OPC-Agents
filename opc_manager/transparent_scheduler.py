"""
调度透明化模块

实现类似 Trae/DeepSeek 的思考过程展示：
- 意图理解
- 任务分解
- 依赖关系
- 调度计划
- 预计时间
- 资源评估
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json


@dataclass
class TaskIntent:
    """任务意图"""
    main_task: str  # 主任务
    sub_tasks: List[str] = field(default_factory=list)  # 副任务
    urgency: str = "normal"  # urgent/normal/low
    importance: str = "normal"  # high/normal/low
    
    def to_dict(self) -> Dict:
        return {
            'main_task': self.main_task,
            'sub_tasks': self.sub_tasks,
            'urgency': self.urgency,
            'importance': self.importance
        }


@dataclass
class DecomposedTask:
    """分解后的任务"""
    id: str
    name: str
    agent: str
    priority: str  # HIGH/MEDIUM/LOW
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务 ID
    estimated_duration: int = 5  # 预计时长（分钟）
    status: str = "pending"  # pending/running/completed/failed
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'agent': self.agent,
            'priority': self.priority,
            'dependencies': self.dependencies,
            'estimated_duration': self.estimated_duration,
            'status': self.status
        }


@dataclass
class SchedulingPlan:
    """调度计划"""
    task_id: str
    task_name: str
    agent: str
    start_time: datetime
    end_time: datetime
    status: str  # running/waiting/completed
    
    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'agent': self.agent,
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'status': self.status
        }


@dataclass
class ResourceAssessment:
    """资源评估"""
    cpu_current: int = 30  # 当前 CPU 使用率 %
    cpu_peak: int = 60  # 预计峰值 %
    memory_current: int = 2  # 当前内存 GB
    memory_available: int = 6  # 可用内存 GB
    status: str = "safe"  # safe/warning/danger
    
    def to_dict(self) -> Dict:
        return {
            'cpu': {
                'current': self.cpu_current,
                'peak': self.cpu_peak
            },
            'memory': {
                'current': self.memory_current,
                'available': self.memory_available
            },
            'status': self.status
        }


@dataclass
class ThinkingProcess:
    """思考过程"""
    intent: TaskIntent
    decomposition: List[DecomposedTask]
    dependency_graph: Dict[str, List[str]]  # {task_id: [dependent_ids]}
    scheduling_plan: List[SchedulingPlan]
    estimated_completion: datetime
    resource_assessment: ResourceAssessment
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'intent': self.intent.to_dict(),
            'decomposition': [t.to_dict() for t in self.decomposition],
            'dependency_graph': self.dependency_graph,
            'scheduling_plan': [p.to_dict() for p in self.scheduling_plan],
            'estimated_completion': self.estimated_completion.strftime('%H:%M'),
            'estimated_duration_minutes': (self.estimated_completion - datetime.now()).seconds // 60,
            'resource_assessment': self.resource_assessment.to_dict(),
            'created_at': self.created_at.isoformat()
        }
    
    def to_html(self, collapsed: bool = True) -> str:
        """生成 HTML 展示（类似 Trae/DeepSeek）"""
        state = "open" if not collapsed else ""
        
        html = f"""
<div class="thinking-process" style="font-size: 12px; color: #666; border: 1px solid #e0e0e0; border-radius: 4px; padding: 10px; margin: 10px 0;">
  <details {state} style="cursor: pointer;">
    <summary style="padding: 5px; font-weight: bold;">🤔 思考过程（点击展开/收起）</summary>
    
    <div style="margin-top: 10px;">
      <div style="margin-bottom: 15px;">
        <strong>意图理解:</strong>
        <p style="margin: 5px 0; padding-left: 10px; border-left: 2px solid #4CAF50;">
          主任务：{self.intent.main_task}（{self.intent.importance}）<br>
          副任务：{', '.join(self.intent.sub_tasks) if self.intent.sub_tasks else '无'}（{self.intent.urgency}）
        </p>
      </div>
      
      <div style="margin-bottom: 15px;">
        <strong>任务分解:</strong>
        <ol style="margin: 5px 0; padding-left: 20px;">
"""
        
        for task in self.decomposition:
            deps = f" → 依赖：{', '.join(task.dependencies)}" if task.dependencies else ""
            html += f"""
          <li style="margin: 5px 0;">
            <strong>{task.name}</strong>（{task.agent}）- {task.priority}{deps}
          </li>
"""
        
        html += """
        </ol>
      </div>
      
      <div style="margin-bottom: 15px;">
        <strong>调度计划:</strong>
        <table style="width: 100%; border-collapse: collapse; margin: 5px 0;">
          <thead>
            <tr style="background: #f5f5f5;">
              <th style="border: 1px solid #ddd; padding: 5px;">时间</th>
              <th style="border: 1px solid #ddd; padding: 5px;">任务</th>
              <th style="border: 1px solid #ddd; padding: 5px;">Agent</th>
              <th style="border: 1px solid #ddd; padding: 5px;">状态</th>
            </tr>
          </thead>
          <tbody>
"""
        
        for plan in self.scheduling_plan:
            status_emoji = {
                'running': '🔄',
                'waiting': '⏳',
                'completed': '✅',
                'failed': '❌'
            }.get(plan.status, '❓')
            
            html += f"""
            <tr>
              <td style="border: 1px solid #ddd; padding: 5px;">{plan.start_time} - {plan.end_time}</td>
              <td style="border: 1px solid #ddd; padding: 5px;">{plan.task_name}</td>
              <td style="border: 1px solid #ddd; padding: 5px;">{plan.agent}</td>
              <td style="border: 1px solid #ddd; padding: 5px;">{status_emoji} {plan.status}</td>
            </tr>
"""
        
        html += f"""
          </tbody>
        </table>
      </div>
      
      <div style="margin-bottom: 15px;">
        <strong>预计完成时间:</strong> 
        <span style="color: #4CAF50; font-weight: bold;">{self.estimated_completion.strftime('%H:%M')}</span>
        （约 {self.to_dict()['estimated_duration_minutes']} 分钟）
      </div>
      
      <div style="margin-bottom: 15px;">
        <strong>资源评估:</strong>
        <p style="margin: 5px 0; padding-left: 10px; border-left: 2px solid {'#4CAF50' if self.resource_assessment.status == 'safe' else '#FF9800'};">
          CPU: 当前 {self.resource_assessment.cpu_current}%，预计峰值 {self.resource_assessment.cpu_peak}% 
          ({'安全' if self.resource_assessment.status == 'safe' else '警告'})<br>
          内存：当前 {self.resource_assessment.memory_current}GB，可用 {self.resource_assessment.memory_available}GB（充足）
        </p>
      </div>
    </div>
  </details>
</div>
"""
        return html
    
    def to_markdown(self) -> str:
        """生成 Markdown 格式"""
        md = f"""
### 🤔 思考过程

**意图理解:**
- 主任务：{self.intent.main_task}（{self.intent.importance}）
- 副任务：{', '.join(self.intent.sub_tasks) if self.intent.sub_tasks else '无'}（{self.intent.urgency}）

**任务分解:**
"""
        
        for i, task in enumerate(self.decomposition, 1):
            deps = f" → 依赖：{', '.join(task.dependencies)}" if task.dependencies else ""
            md += f"\n{i}. **{task.name}**（{task.agent}）- {task.priority}{deps}"
        
        md += "\n\n**调度计划:**\n"
        md += "| 时间 | 任务 | Agent | 状态 |\n"
        md += "|------|------|-------|------|\n"
        
        for plan in self.scheduling_plan:
            status_emoji = {
                'running': '🔄',
                'waiting': '⏳',
                'completed': '✅',
                'failed': '❌'
            }.get(plan.status, '❓')
            md += f"| {plan.start_time}-{plan.end_time} | {plan.task_name} | {plan.agent} | {status_emoji} {plan.status} |\n"
        
        md += f"""
**预计完成时间:** {self.estimated_completion.strftime('%H:%M')}（约 {self.to_dict()['estimated_duration_minutes']} 分钟）

**资源评估:**
- CPU: 当前 {self.resource_assessment.cpu_current}%，预计峰值 {self.resource_assessment.cpu_peak}%
- 内存：当前 {self.resource_assessment.memory_current}GB，可用 {self.resource_assessment.memory_available}GB
"""
        
        return md


class TransparentScheduler:
    """透明调度器"""
    
    def __init__(self):
        self.thinking_processes: List[ThinkingProcess] = []
    
    def create_thinking_process(self, user_request: str, context: Optional[Dict] = None) -> ThinkingProcess:
        """
        创建思考过程
        
        Args:
            user_request: 用户请求
            context: 上下文信息
        
        Returns:
            ThinkingProcess: 思考过程对象
        """
        # 1. 意图理解（示例）
        intent = self._analyze_intent(user_request, context)
        
        # 2. 任务分解（示例）
        decomposition = self._decompose_tasks(intent, context)
        
        # 3. 依赖关系
        dependency_graph = self._build_dependency_graph(decomposition)
        
        # 4. 调度计划
        scheduling_plan = self._create_schedule(decomposition, dependency_graph)
        
        # 5. 预计完成时间
        estimated_completion = self._estimate_completion(scheduling_plan)
        
        # 6. 资源评估
        resource_assessment = self._assess_resources(decomposition)
        
        # 创建思考过程
        thinking = ThinkingProcess(
            intent=intent,
            decomposition=decomposition,
            dependency_graph=dependency_graph,
            scheduling_plan=scheduling_plan,
            estimated_completion=estimated_completion,
            resource_assessment=resource_assessment
        )
        
        self.thinking_processes.append(thinking)
        return thinking
    
    def _analyze_intent(self, user_request: str, context: Optional[Dict]) -> TaskIntent:
        """分析意图（简化版，实际应该用 NLP）"""
        # 示例逻辑
        if "市场" in user_request and "邮件" in user_request:
            return TaskIntent(
                main_task="市场分析",
                sub_tasks=["客户邮件回复"],
                urgency="urgent",
                importance="high"
            )
        elif "市场" in user_request:
            return TaskIntent(
                main_task="市场分析",
                urgency="normal",
                importance="normal"
            )
        else:
            return TaskIntent(
                main_task=user_request,
                urgency="normal",
                importance="normal"
            )
    
    def _decompose_tasks(self, intent: TaskIntent, context: Optional[Dict]) -> List[DecomposedTask]:
        """任务分解（简化版）"""
        tasks = []
        
        if intent.main_task == "市场分析":
            tasks.extend([
                DecomposedTask('task_1', '客户邮件回复', 'Market Dept', 'HIGH', estimated_duration=5),
                DecomposedTask('task_2', '市场数据收集', 'Web Search', 'MEDIUM', ['task_1'], estimated_duration=10),
                DecomposedTask('task_3', '市场分析报告', 'Content Summary', 'MEDIUM', ['task_2'], estimated_duration=5)
            ])
        
        return tasks
    
    def _build_dependency_graph(self, tasks: List[DecomposedTask]) -> Dict[str, List[str]]:
        """构建依赖关系图"""
        graph = {}
        for task in tasks:
            graph[task.id] = task.dependencies
        return graph
    
    def _create_schedule(self, tasks: List[DecomposedTask], dependency_graph: Dict) -> List[SchedulingPlan]:
        """创建调度计划（简化版）"""
        plans = []
        now = datetime.now()
        
        for i, task in enumerate(tasks):
            start = now + timedelta(minutes=i*5)
            end = start + timedelta(minutes=task.estimated_duration)
            
            status = 'running' if i == 0 else 'waiting'
            
            plans.append(SchedulingPlan(
                task_id=task.id,
                task_name=task.name,
                agent=task.agent,
                start_time=start,
                end_time=end,
                status=status
            ))
        
        return plans
    
    def _estimate_completion(self, plans: List[SchedulingPlan]) -> datetime:
        """估计完成时间"""
        if not plans:
            return datetime.now()
        return plans[-1].end_time
    
    def _assess_resources(self, tasks: List[DecomposedTask]) -> ResourceAssessment:
        """评估资源（简化版）"""
        # 实际应该监控系统资源
        return ResourceAssessment(
            cpu_current=30,
            cpu_peak=60,
            memory_current=2,
            memory_available=6,
            status="safe"
        )
    
    def get_latest_thinking(self) -> Optional[ThinkingProcess]:
        """获取最新的思考过程"""
        return self.thinking_processes[-1] if self.thinking_processes else None


# 使用示例
if __name__ == '__main__':
    scheduler = TransparentScheduler()
    
    print("\n=== 测试：创建思考过程 ===")
    thinking = scheduler.create_thinking_process(
        user_request="帮我分析市场，顺便回复客户邮件"
    )
    
    print("\n=== HTML 输出 ===")
    print(thinking.to_html(collapsed=False))
    
    print("\n=== Markdown 输出 ===")
    print(thinking.to_markdown())
    
    print("\n=== JSON 输出 ===")
    print(json.dumps(thinking.to_dict(), indent=2, ensure_ascii=False))
