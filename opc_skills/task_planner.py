"""
自主任务规划引擎
基于 AI 的任务分解和规划能力
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime


class TaskPlanner:
    """任务规划器"""
    
    def __init__(self, skill_orchestrator=None):
        self.skill_orchestrator = skill_orchestrator
        self.planning_templates = self._load_planning_templates()
    
    def _load_planning_templates(self) -> Dict:
        """加载规划模板"""
        return {
            'document_analysis': {
                'description': '文档分析任务',
                'steps': [
                    {'skill': 'document_processor', 'operation': 'read'},
                    {'skill': 'content_summary', 'operation': 'summarize'},
                    {'skill': 'content_summary', 'operation': 'extract_keywords'}
                ]
            },
            'research_task': {
                'description': '研究任务',
                'steps': [
                    {'skill': 'web_search', 'operation': 'search'},
                    {'skill': 'content_summary', 'operation': 'summarize'},
                    {'skill': 'content_summary', 'operation': 'extract_key_info'}
                ]
            },
            'security_audit': {
                'description': '安全审计任务',
                'steps': [
                    {'skill': 'security_scanner', 'operation': 'scan_code'},
                    {'skill': 'security_scanner', 'operation': 'analyze_permissions'},
                    {'skill': 'content_summary', 'operation': 'generate_report'}
                ]
            }
        }
    
    def plan_task(self, task_description: str, context: Optional[Dict] = None) -> Dict:
        """规划任务"""
        # 分析任务类型
        task_type = self._analyze_task_type(task_description)
        
        # 获取对应的模板
        template = self.planning_templates.get(task_type)
        if not template:
            # 使用通用模板
            template = self._generate_generic_plan(task_description)
        
        # 生成执行计划
        plan = {
            'task_description': task_description,
            'task_type': task_type,
            'steps': template['steps'],
            'context': context or {},
            'created_at': datetime.now().isoformat()
        }
        
        return plan
    
    def _analyze_task_type(self, description: str) -> str:
        """分析任务类型"""
        description_lower = description.lower()
        
        # 关键词匹配
        if any(word in description_lower for word in ['文档', 'pdf', 'word', 'excel', '文件']):
            return 'document_analysis'
        
        if any(word in description_lower for word in ['研究', '调研', '搜索', '查找']):
            return 'research_task'
        
        if any(word in description_lower for word in ['安全', '扫描', '审计', '检查']):
            return 'security_audit'
        
        return 'generic'
    
    def _generate_generic_plan(self, description: str) -> Dict:
        """生成通用计划"""
        return {
            'description': '通用任务',
            'steps': [
                {'skill': 'content_summary', 'operation': 'analyze'},
                {'skill': 'web_search', 'operation': 'search'}
            ]
        }
    
    def execute_plan(self, plan: Dict) -> Dict:
        """执行计划"""
        if not self.skill_orchestrator:
            return {
                'success': False,
                'error': '技能编排器未初始化'
            }
        
        results = []
        context = plan.get('context', {})
        
        for i, step in enumerate(plan['steps']):
            # 执行技能
            result = self._execute_step(step, context)
            results.append({
                'step': i + 1,
                'skill': step['skill'],
                'operation': step['operation'],
                'result': result
            })
            
            # 更新上下文
            if result.get('success'):
                context.update(result.get('output', {}))
        
        return {
            'success': True,
            'plan': plan,
            'results': results,
            'final_context': context
        }
    
    def _execute_step(self, step: Dict, context: Dict) -> Dict:
        """执行步骤"""
        # 这里应该调用实际的技能
        # 为了演示，返回模拟结果
        return {
            'success': True,
            'output': {
                f'{step["skill"]}_result': '模拟执行结果'
            }
        }


class IntelligentTaskManager:
    """智能任务管理器"""
    
    def __init__(self):
        self.planner = TaskPlanner()
        self.task_queue = []
        self.completed_tasks = []
        self.failed_tasks = []
    
    def submit_task(self, description: str, priority: int = 5) -> Dict:
        """提交任务"""
        # 生成任务 ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 规划任务
        plan = self.planner.plan_task(description)
        
        # 创建任务
        task = {
            'task_id': task_id,
            'description': description,
            'plan': plan,
            'priority': priority,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'result': None
        }
        
        # 添加到队列
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda x: (-x['priority'], x['created_at']))
        
        return {
            'success': True,
            'task_id': task_id,
            'message': f'任务已提交，ID: {task_id}'
        }
    
    def process_next_task(self) -> Dict:
        """处理下一个任务"""
        if not self.task_queue:
            return {
                'success': False,
                'error': '没有待处理的任务'
            }
        
        # 获取最高优先级的任务
        task = self.task_queue.pop(0)
        task['status'] = 'running'
        task['started_at'] = datetime.now().isoformat()
        
        try:
            # 执行任务
            result = self.planner.execute_plan(task['plan'])
            
            task['status'] = 'completed'
            task['completed_at'] = datetime.now().isoformat()
            task['result'] = result
            
            self.completed_tasks.append(task)
            
            return {
                'success': True,
                'task_id': task['task_id'],
                'result': result
            }
            
        except Exception as e:
            task['status'] = 'failed'
            task['completed_at'] = datetime.now().isoformat()
            task['result'] = {'error': str(e)}
            
            self.failed_tasks.append(task)
            
            return {
                'success': False,
                'task_id': task['task_id'],
                'error': str(e)
            }
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        # 在队列中查找
        for task in self.task_queue:
            if task['task_id'] == task_id:
                return task
        
        # 在已完成的任务中查找
        for task in self.completed_tasks:
            if task['task_id'] == task_id:
                return task
        
        # 在失败的任务中查找
        for task in self.failed_tasks:
            if task['task_id'] == task_id:
                return task
        
        return None
    
    def list_tasks(self, status: Optional[str] = None) -> List[Dict]:
        """列出任务"""
        all_tasks = self.task_queue + self.completed_tasks + self.failed_tasks
        
        if status:
            return [t for t in all_tasks if t['status'] == status]
        
        return all_tasks


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("自主任务规划引擎测试")
    print("=" * 60)
    
    # 创建任务管理器
    manager = IntelligentTaskManager()
    
    # 提交任务
    print("\n[测试] 提交任务")
    tasks = [
        ("分析这份 PDF 文档", 8),
        ("调研人工智能发展趋势", 5),
        ("对代码进行安全审计", 9),
        ("搜索最新的科技新闻", 3)
    ]
    
    for desc, priority in tasks:
        result = manager.submit_task(desc, priority)
        print(f"提交：{desc} - {result['message']}")
    
    # 查看任务列表
    print("\n[测试] 任务列表")
    all_tasks = manager.list_tasks()
    for task in all_tasks:
        print(f"- {task['task_id']}: {task['description']} (优先级：{task['priority']})")
    
    # 处理任务
    print("\n[测试] 处理任务")
    while manager.task_queue:
        result = manager.process_next_task()
        if result['success']:
            print(f"✓ 任务完成：{result['task_id']}")
        else:
            print(f"✗ 任务失败：{result.get('error')}")
    
    # 查看完成的任务
    print("\n[测试] 已完成任务")
    completed = manager.completed_tasks
    for task in completed:
        print(f"- {task['description']}: {task['status']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
