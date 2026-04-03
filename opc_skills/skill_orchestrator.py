"""
技能编排引擎
实现多个技能的组合编排和协同工作
"""

import json
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from enum import Enum


class SkillStatus(Enum):
    """技能执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowNode:
    """工作流节点"""
    
    def __init__(self, node_id: str, skill_name: str, 
                 parameters: Optional[Dict] = None,
                 condition: Optional[str] = None):
        self.node_id = node_id
        self.skill_name = skill_name
        self.parameters = parameters or {}
        self.condition = condition  # 执行条件
        self.status = SkillStatus.PENDING
        self.result = None
        self.error = None
        self.start_time = None
        self.end_time = None
        self.dependencies = []  # 依赖的节点 ID
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'node_id': self.node_id,
            'skill_name': self.skill_name,
            'parameters': self.parameters,
            'condition': self.condition,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'dependencies': self.dependencies
        }


class Workflow:
    """工作流定义"""
    
    def __init__(self, workflow_id: str, name: str, description: str = ""):
        self.workflow_id = workflow_id
        self.name = name
        self.description = description
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: Dict[str, List[str]] = {}  # node_id -> [next_node_ids]
        self.start_node: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.version = "1.0.0"
    
    def add_node(self, node: WorkflowNode):
        """添加节点"""
        self.nodes[node.node_id] = node
        
        # 如果没有起始节点，设置为起始节点
        if not self.start_node and not node.dependencies:
            self.start_node = node.node_id
    
    def add_edge(self, from_node: str, to_node: str):
        """添加边（定义节点间的执行顺序）"""
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)
        
        # 更新依赖关系
        if to_node in self.nodes:
            self.nodes[to_node].dependencies.append(from_node)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'workflow_id': self.workflow_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'nodes': {nid: node.to_dict() for nid, node in self.nodes.items()},
            'edges': self.edges,
            'start_node': self.start_node,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class WorkflowEngine:
    """工作流执行引擎"""
    
    def __init__(self, skill_registry=None):
        self.skill_registry = skill_registry
        self.workflows: Dict[str, Workflow] = {}
        self.execution_history = []
    
    def register_workflow(self, workflow: Workflow):
        """注册工作流"""
        self.workflows[workflow.workflow_id] = workflow
    
    def execute_workflow(self, workflow_id: str, 
                        context: Optional[Dict] = None) -> Dict:
        """执行工作流"""
        if workflow_id not in self.workflows:
            return {
                'success': False,
                'error': f'工作流不存在：{workflow_id}'
            }
        
        workflow = self.workflows[workflow_id]
        context = context or {}
        
        # 初始化执行上下文
        execution_context = {
            'workflow_id': workflow_id,
            'start_time': datetime.now().isoformat(),
            'status': 'running',
            'nodes': {},
            'variables': context,
            'output': {}
        }
        
        try:
            # 从起始节点开始执行
            current_node_id = workflow.start_node
            visited = set()
            
            while current_node_id:
                if current_node_id in visited:
                    break
                
                visited.add(current_node_id)
                node = workflow.nodes[current_node_id]
                
                # 检查依赖是否完成
                if not self._check_dependencies(node, execution_context):
                    execution_context['nodes'][current_node_id] = {
                        'status': 'skipped',
                        'reason': 'dependencies_not_met'
                    }
                    current_node_id = self._get_next_node(workflow, current_node_id)
                    continue
                
                # 检查执行条件
                if node.condition and not self._evaluate_condition(node.condition, context):
                    execution_context['nodes'][current_node_id] = {
                        'status': 'skipped',
                        'reason': 'condition_not_met'
                    }
                    current_node_id = self._get_next_node(workflow, current_node_id)
                    continue
                
                # 执行节点
                result = self._execute_node(node, execution_context)
                execution_context['nodes'][current_node_id] = result
                
                # 更新上下文
                if result['status'] == 'completed' and result.get('output'):
                    context.update(result['output'])
                
                # 获取下一个节点
                current_node_id = self._get_next_node(workflow, current_node_id)
            
            execution_context['status'] = 'completed'
            execution_context['end_time'] = datetime.now().isoformat()
            
            # 记录执行历史
            self.execution_history.append(execution_context)
            
            return {
                'success': True,
                'workflow_id': workflow_id,
                'status': 'completed',
                'execution_context': execution_context
            }
            
        except Exception as e:
            execution_context['status'] = 'failed'
            execution_context['error'] = str(e)
            execution_context['end_time'] = datetime.now().isoformat()
            
            self.execution_history.append(execution_context)
            
            return {
                'success': False,
                'error': str(e),
                'execution_context': execution_context
            }
    
    def _check_dependencies(self, node: WorkflowNode, 
                           context: Dict) -> bool:
        """检查依赖是否满足"""
        for dep_id in node.dependencies:
            if dep_id not in context['nodes']:
                return False
            
            dep_status = context['nodes'][dep_id].get('status')
            if dep_status not in ['completed']:
                return False
        
        return True
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """评估执行条件"""
        # 简单的条件评估，实际应该用更安全的表达式解析器
        try:
            # 将上下文变量注入到条件表达式中
            return eval(condition, {"__builtins__": {}}, context)
        except Exception:
            return False
    
    def _execute_node(self, node: WorkflowNode, context: Dict) -> Dict:
        """执行节点"""
        node.start_time = datetime.now().isoformat()
        
        # 解析参数（支持从上下文获取）
        resolved_params = self._resolve_parameters(node.parameters, context)
        
        # 调用技能
        if self.skill_registry:
            skill = self.skill_registry.get_skill(node.skill_name)
            if skill:
                result = skill.execute(**resolved_params)
                node.result = result
                node.status = SkillStatus.COMPLETED if result.get('success') else SkillStatus.FAILED
            else:
                node.status = SkillStatus.FAILED
                node.error = f'技能不存在：{node.skill_name}'
        else:
            # 模拟执行
            node.result = {'success': True, 'message': '模拟执行'}
            node.status = SkillStatus.COMPLETED
        
        node.end_time = datetime.now().isoformat()
        
        return {
            'node_id': node.node_id,
            'skill_name': node.skill_name,
            'status': node.status.value,
            'result': node.result,
            'error': node.error,
            'start_time': node.start_time,
            'end_time': node.end_time,
            'output': node.result if node.result else {}
        }
    
    def _resolve_parameters(self, parameters: Dict, context: Dict) -> Dict:
        """解析参数（支持从上下文获取变量）"""
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                # 从上下文获取变量
                var_name = value[2:-1]
                resolved[key] = context['variables'].get(var_name, value)
            else:
                resolved[key] = value
        return resolved
    
    def _get_next_node(self, workflow: Workflow, current_node_id: str) -> Optional[str]:
        """获取下一个节点"""
        if current_node_id in workflow.edges:
            next_nodes = workflow.edges[current_node_id]
            return next_nodes[0] if next_nodes else None
        return None


class SkillOrchestrator:
    """技能编排器"""
    
    def __init__(self, skill_registry=None):
        self.skill_registry = skill_registry
        self.engine = WorkflowEngine(skill_registry)
        self._register_builtin_workflows()
    
    def _register_builtin_workflows(self):
        """注册内置工作流"""
        
        # 工作流 1: 文档处理 + 内容摘要
        workflow1 = Workflow(
            workflow_id='doc_summary_workflow',
            name='文档摘要工作流',
            description='读取文档并生成摘要'
        )
        
        workflow1.add_node(WorkflowNode(
            node_id='read_doc',
            skill_name='document_processor',
            parameters={
                'operation': 'read_pdf',
                'file_path': '${file_path}'
            }
        ))
        
        workflow1.add_node(WorkflowNode(
            node_id='generate_summary',
            skill_name='content_summary',
            parameters={
                'operation': 'summarize',
                'text': '${read_doc.result.content}'
            }
        ))
        
        workflow1.add_edge('read_doc', 'generate_summary')
        self.engine.register_workflow(workflow1)
        
        # 工作流 2: 网页搜索 + 内容摘要
        workflow2 = Workflow(
            workflow_id='search_summary_workflow',
            name='搜索摘要工作流',
            description='搜索网络并生成摘要'
        )
        
        workflow2.add_node(WorkflowNode(
            node_id='web_search',
            skill_name='web_search',
            parameters={
                'query': '${query}',
                'engine': 'baidu'
            }
        ))
        
        workflow2.add_node(WorkflowNode(
            node_id='content_summary',
            skill_name='content_summary',
            parameters={
                'operation': 'summarize',
                'text': '${web_search.result.content}'
            }
        ))
        
        workflow2.add_edge('web_search', 'content_summary')
        self.engine.register_workflow(workflow2)
        
        # 工作流 3: 安全扫描 + 报告生成
        workflow3 = Workflow(
            workflow_id='security_scan_workflow',
            name='安全扫描工作流',
            description='代码扫描并生成报告'
        )
        
        workflow3.add_node(WorkflowNode(
            node_id='scan_code',
            skill_name='security_scanner',
            parameters={
                'operation': 'scan_code',
                'code': '${code}',
                'language': '${language}'
            }
        ))
        
        workflow3.add_node(WorkflowNode(
            node_id='generate_report',
            skill_name='content_summary',
            parameters={
                'operation': 'extract_key_info',
                'text': '${scan_code.result}'
            },
            condition='scan_code.result.get("issues_count", 0) > 0'
        ))
        
        workflow3.add_edge('scan_code', 'generate_report')
        self.engine.register_workflow(workflow3)
    
    def execute_workflow(self, workflow_id: str, **kwargs) -> Dict:
        """执行工作流"""
        return self.engine.execute_workflow(workflow_id, kwargs)
    
    def create_custom_workflow(self, workflow_id: str, name: str,
                              nodes: List[Dict], edges: List[tuple]) -> Dict:
        """创建自定义工作流"""
        workflow = Workflow(workflow_id, name)
        
        # 添加节点
        for node_data in nodes:
            node = WorkflowNode(
                node_id=node_data['node_id'],
                skill_name=node_data['skill_name'],
                parameters=node_data.get('parameters'),
                condition=node_data.get('condition')
            )
            workflow.add_node(node)
        
        # 添加边
        for from_node, to_node in edges:
            workflow.add_edge(from_node, to_node)
        
        self.engine.register_workflow(workflow)
        
        return {
            'success': True,
            'workflow_id': workflow_id,
            'message': f'工作流 {name} 创建成功'
        }
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        return [wf.to_dict() for wf in self.engine.workflows.values()]
    
    def get_workflow_info(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流信息"""
        if workflow_id in self.engine.workflows:
            return self.engine.workflows[workflow_id].to_dict()
        return None


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("技能编排引擎测试")
    print("=" * 60)
    
    # 创建编排器
    orchestrator = SkillOrchestrator()
    
    # 列出内置工作流
    print("\n[内置工作流]")
    workflows = orchestrator.list_workflows()
    for wf in workflows:
        print(f"- {wf['name']} ({wf['workflow_id']})")
        print(f"  描述：{wf['description']}")
        print(f"  节点数：{len(wf['nodes'])}")
    
    # 测试文档摘要工作流
    print("\n[测试] 文档摘要工作流")
    result = orchestrator.execute_workflow(
        'doc_summary_workflow',
        file_path='/path/to/document.pdf'
    )
    print(f"执行状态：{result.get('status')}")
    print(f"结果：{result.get('success')}")
    
    # 创建自定义工作流
    print("\n[测试] 创建自定义工作流")
    result = orchestrator.create_custom_workflow(
        workflow_id='custom_workflow_1',
        name='自定义工作流 1',
        nodes=[
            {
                'node_id': 'step1',
                'skill_name': 'web_search',
                'parameters': {'query': 'test'}
            },
            {
                'node_id': 'step2',
                'skill_name': 'content_summary',
                'parameters': {'operation': 'summarize'}
            }
        ],
        edges=[('step1', 'step2')]
    )
    print(f"创建结果：{result}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
