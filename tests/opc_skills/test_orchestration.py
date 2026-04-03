"""
技能编排和任务规划单元测试
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_skills.skill_orchestrator import (
    Workflow, WorkflowNode, WorkflowEngine, SkillOrchestrator
)
from opc_skills.task_planner import TaskPlanner, IntelligentTaskManager


class TestWorkflow:
    """工作流测试"""
    
    def test_workflow_creation(self):
        """测试工作流创建"""
        workflow = Workflow(
            workflow_id='test_wf',
            name='测试工作流',
            description='用于测试'
        )
        
        assert workflow.workflow_id == 'test_wf'
        assert workflow.name == '测试工作流'
        assert workflow.description == '用于测试'
        assert workflow.version == '1.0.0'
        assert len(workflow.nodes) == 0
    
    def test_add_node(self):
        """测试添加节点"""
        workflow = Workflow('wf1', '工作流 1')
        
        node = WorkflowNode(
            node_id='step1',
            skill_name='web_search',
            parameters={'query': 'test'}
        )
        
        workflow.add_node(node)
        
        assert 'step1' in workflow.nodes
        assert workflow.nodes['step1'].skill_name == 'web_search'
        assert workflow.start_node == 'step1'
    
    def test_add_edge(self):
        """测试添加边"""
        workflow = Workflow('wf1', '工作流 1')
        
        node1 = WorkflowNode('step1', 'skill1')
        node2 = WorkflowNode('step2', 'skill2')
        
        workflow.add_node(node1)
        workflow.add_node(node2)
        workflow.add_edge('step1', 'step2')
        
        assert 'step1' in workflow.edges
        assert 'step2' in workflow.edges['step1']
        assert 'step1' in node2.dependencies
    
    def test_workflow_to_dict(self):
        """测试工作流序列化"""
        workflow = Workflow('wf1', '工作流 1')
        workflow.add_node(WorkflowNode('step1', 'skill1'))
        
        data = workflow.to_dict()
        
        assert 'workflow_id' in data
        assert 'nodes' in data
        assert 'step1' in data['nodes']


class TestWorkflowEngine:
    """工作流引擎测试"""
    
    def test_engine_creation(self):
        """测试引擎创建"""
        engine = WorkflowEngine()
        assert len(engine.workflows) == 0
    
    def test_register_workflow(self):
        """测试注册工作流"""
        engine = WorkflowEngine()
        workflow = Workflow('wf1', '工作流 1')
        
        engine.register_workflow(workflow)
        
        assert 'wf1' in engine.workflows
        assert engine.workflows['wf1'] == workflow
    
    def test_execute_workflow_success(self):
        """测试执行工作流（成功）"""
        engine = WorkflowEngine()
        workflow = Workflow('wf1', '工作流 1')
        
        workflow.add_node(WorkflowNode(
            node_id='step1',
            skill_name='test_skill',
            parameters={'key': 'value'}
        ))
        
        engine.register_workflow(workflow)
        
        result = engine.execute_workflow('wf1')
        
        assert result['success'] is True
        assert result['status'] == 'completed'
    
    def test_execute_workflow_not_found(self):
        """测试执行不存在的工作流"""
        engine = WorkflowEngine()
        
        result = engine.execute_workflow('nonexistent')
        
        assert result['success'] is False
        assert '不存在' in result['error']


class TestSkillOrchestrator:
    """技能编排器测试"""
    
    def test_orchestrator_creation(self):
        """测试编排器创建"""
        orchestrator = SkillOrchestrator()
        assert len(orchestrator.engine.workflows) > 0
    
    def test_builtin_workflows(self):
        """测试内置工作流"""
        orchestrator = SkillOrchestrator()
        workflows = orchestrator.list_workflows()
        
        assert len(workflows) >= 3  # 至少 3 个内置工作流
        
        workflow_ids = [wf['workflow_id'] for wf in workflows]
        assert 'doc_summary_workflow' in workflow_ids
        assert 'search_summary_workflow' in workflow_ids
        assert 'security_scan_workflow' in workflow_ids
    
    def test_execute_builtin_workflow(self):
        """测试执行内置工作流"""
        orchestrator = SkillOrchestrator()
        
        result = orchestrator.execute_workflow(
            'doc_summary_workflow',
            file_path='/test/path.pdf'
        )
        
        assert result['success'] is True
        assert result['workflow_id'] == 'doc_summary_workflow'
    
    def test_create_custom_workflow(self):
        """测试创建自定义工作流"""
        orchestrator = SkillOrchestrator()
        
        result = orchestrator.create_custom_workflow(
            workflow_id='custom_wf',
            name='自定义工作流',
            nodes=[
                {
                    'node_id': 'step1',
                    'skill_name': 'web_search',
                    'parameters': {'query': 'test'}
                }
            ],
            edges=[]
        )
        
        assert result['success'] is True
        assert 'custom_wf' in [wf['workflow_id'] for wf in orchestrator.list_workflows()]


class TestTaskPlanner:
    """任务规划器测试"""
    
    def test_planner_creation(self):
        """测试规划器创建"""
        planner = TaskPlanner()
        assert len(planner.planning_templates) > 0
    
    def test_plan_document_task(self):
        """测试规划文档任务"""
        planner = TaskPlanner()
        
        plan = planner.plan_task('分析这份 PDF 文档')
        
        assert plan['task_type'] == 'document_analysis'
        assert len(plan['steps']) > 0
    
    def test_plan_research_task(self):
        """测试规划研究任务"""
        planner = TaskPlanner()
        
        plan = planner.plan_task('调研人工智能发展趋势')
        
        assert plan['task_type'] == 'research_task'
        assert len(plan['steps']) > 0
    
    def test_plan_security_task(self):
        """测试规划安全任务"""
        planner = TaskPlanner()
        
        plan = planner.plan_task('对代码进行安全审计')
        
        assert plan['task_type'] == 'security_audit'
        assert len(plan['steps']) > 0
    
    def test_plan_generic_task(self):
        """测试规划通用任务"""
        planner = TaskPlanner()
        
        plan = planner.plan_task('随便一个任务')
        
        assert plan['task_type'] == 'generic'
        assert len(plan['steps']) > 0


class TestIntelligentTaskManager:
    """智能任务管理器测试"""
    
    def test_manager_creation(self):
        """测试管理器创建"""
        manager = IntelligentTaskManager()
        assert len(manager.task_queue) == 0
        assert len(manager.completed_tasks) == 0
    
    def test_submit_task(self):
        """测试提交任务"""
        manager = IntelligentTaskManager()
        
        result = manager.submit_task('测试任务', priority=5)
        
        assert result['success'] is True
        assert 'task_id' in result
        assert len(manager.task_queue) == 1
    
    def test_submit_task_with_priority(self):
        """测试按优先级提交任务"""
        manager = IntelligentTaskManager()
        
        manager.submit_task('低优先级任务', priority=1)
        manager.submit_task('高优先级任务', priority=10)
        
        # 高优先级应该排在前面
        assert manager.task_queue[0]['description'] == '高优先级任务'
        assert manager.task_queue[1]['description'] == '低优先级任务'
    
    def test_process_task(self):
        """测试处理任务"""
        manager = IntelligentTaskManager()
        
        result = manager.submit_task('测试任务')
        task_id = result['task_id']
        
        process_result = manager.process_next_task()
        
        assert process_result['success'] is True
        assert len(manager.completed_tasks) == 1
        assert manager.completed_tasks[0]['task_id'] == task_id
    
    def test_get_task_status(self):
        """测试获取任务状态"""
        manager = IntelligentTaskManager()
        
        result = manager.submit_task('测试任务')
        task_id = result['task_id']
        
        status = manager.get_task_status(task_id)
        
        assert status is not None
        assert status['task_id'] == task_id
    
    def test_list_tasks(self):
        """测试列出任务"""
        manager = IntelligentTaskManager()
        
        manager.submit_task('任务 1')
        manager.submit_task('任务 2')
        manager.process_next_task()
        
        all_tasks = manager.list_tasks()
        assert len(all_tasks) == 2
        
        pending_tasks = manager.list_tasks(status='pending')
        assert len(pending_tasks) == 1
        
        completed_tasks = manager.list_tasks(status='completed')
        assert len(completed_tasks) == 1
    
    def test_process_no_tasks(self):
        """测试处理空队列"""
        manager = IntelligentTaskManager()
        
        result = manager.process_next_task()
        
        assert result['success'] is False
        assert '没有待处理的任务' in result['error']


class TestIntegration:
    """集成测试"""
    
    def test_full_workflow_execution(self):
        """测试完整工作流执行"""
        # 创建编排器
        orchestrator = SkillOrchestrator()
        
        # 创建工作流
        workflow = Workflow('integration_wf', '集成测试工作流')
        workflow.add_node(WorkflowNode('step1', 'web_search'))
        workflow.add_node(WorkflowNode('step2', 'content_summary'))
        workflow.add_edge('step1', 'step2')
        
        orchestrator.engine.register_workflow(workflow)
        
        # 执行工作流
        result = orchestrator.execute_workflow('integration_wf')
        
        assert result['success'] is True
        assert result['status'] == 'completed'
    
    def test_task_planning_and_execution(self):
        """测试任务规划和执行"""
        manager = IntelligentTaskManager()
        
        # 提交任务
        result = manager.submit_task('分析文档')
        task_id = result['task_id']
        
        # 处理任务
        process_result = manager.process_next_task()
        
        assert process_result['success'] is True
        
        # 验证状态
        status = manager.get_task_status(task_id)
        assert status['status'] == 'completed'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
