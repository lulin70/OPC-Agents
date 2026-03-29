#!/usr/bin/env python3
"""
Workflow Definitions for OPC-Agents

Defines workflow types, steps, and structures.
"""

import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class WorkflowType(Enum):
    """工作流类型"""
    SEQUENTIAL = "sequential"      # 串行执行
    PARALLEL = "parallel"          # 并行执行
    CONDITIONAL = "conditional"    # 条件分支
    LOOP = "loop"                  # 循环执行
    HYBRID = "hybrid"              # 混合模式


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class WorkflowStatus(Enum):
    """工作流状态"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    name: str
    description: str = ""
    agent: str = ""
    department: str = ""
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    timeout: int = 300
    retry_count: int = 3
    retry_delay: int = 5
    on_success: Optional[str] = None
    on_failure: Optional[str] = None
    
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "department": self.department,
            "action": self.action,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "condition": self.condition,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class WorkflowDefinition:
    """工作流定义"""
    id: str
    name: str
    description: str = ""
    workflow_type: WorkflowType = WorkflowType.SEQUENTIAL
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    triggers: List[str] = field(default_factory=list)
    timeout: int = 3600
    max_retries: int = 3
    
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def add_step(self, step: WorkflowStep):
        """添加步骤"""
        self.steps.append(step)
        self.updated_at = time.time()
    
    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """获取步骤"""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    def get_entry_steps(self) -> List[WorkflowStep]:
        """获取入口步骤（无依赖的步骤）"""
        return [s for s in self.steps if not s.dependencies]
    
    def get_dependent_steps(self, step_id: str) -> List[WorkflowStep]:
        """获取依赖于指定步骤的步骤"""
        return [s for s in self.steps if step_id in s.dependencies]
    
    def validate(self) -> List[str]:
        """验证工作流定义
        
        Returns:
            错误消息列表
        """
        errors = []
        
        # 检查步骤ID唯一性
        step_ids = [s.id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            errors.append("步骤ID不唯一")
        
        # 检查依赖是否存在
        for step in self.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    errors.append(f"步骤 {step.id} 的依赖 {dep_id} 不存在")
        
        # 检查循环依赖
        visited = set()
        path = set()
        
        def has_cycle(step_id: str) -> bool:
            if step_id in path:
                return True
            if step_id in visited:
                return False
            
            visited.add(step_id)
            path.add(step_id)
            
            step = self.get_step(step_id)
            if step:
                for dep_id in step.dependencies:
                    if has_cycle(dep_id):
                        return True
            
            path.remove(step_id)
            return False
        
        for step in self.steps:
            if has_cycle(step.id):
                errors.append(f"检测到循环依赖，涉及步骤: {step.id}")
                break
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workflow_type": self.workflow_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "triggers": self.triggers,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowDefinition':
        """从字典创建"""
        steps = [WorkflowStep(**s) for s in data.get("steps", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            workflow_type=WorkflowType(data.get("workflow_type", "sequential")),
            steps=steps,
            variables=data.get("variables", {}),
            triggers=data.get("triggers", []),
            timeout=data.get("timeout", 3600),
            max_retries=data.get("max_retries", 3),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )


# 预定义工作流模板
WORKFLOW_TEMPLATES = {
    "project_startup": {
        "name": "项目启动流程",
        "description": "新项目启动的标准流程",
        "workflow_type": WorkflowType.SEQUENTIAL,
        "steps": [
            {
                "id": "requirements",
                "name": "需求分析",
                "agent": "business_analyst",
                "department": "product",
                "action": "analyze_requirements"
            },
            {
                "id": "design",
                "name": "方案设计",
                "agent": "solution_architect",
                "department": "design",
                "action": "design_solution",
                "dependencies": ["requirements"]
            },
            {
                "id": "planning",
                "name": "项目规划",
                "agent": "project_manager",
                "department": "executive_office",
                "action": "create_project_plan",
                "dependencies": ["design"]
            },
            {
                "id": "kickoff",
                "name": "项目启动",
                "agent": "project_coordinator",
                "department": "operations",
                "action": "kickoff_project",
                "dependencies": ["planning"]
            }
        ]
    },
    "product_development": {
        "name": "产品开发流程",
        "description": "产品从设计到发布的完整流程",
        "workflow_type": WorkflowType.HYBRID,
        "steps": [
            {
                "id": "design",
                "name": "产品设计",
                "agent": "product_designer",
                "department": "design",
                "action": "design_product"
            },
            {
                "id": "frontend_dev",
                "name": "前端开发",
                "agent": "frontend_developer",
                "department": "development",
                "action": "develop_frontend",
                "dependencies": ["design"]
            },
            {
                "id": "backend_dev",
                "name": "后端开发",
                "agent": "backend_developer",
                "department": "development",
                "action": "develop_backend",
                "dependencies": ["design"]
            },
            {
                "id": "testing",
                "name": "测试验证",
                "agent": "qa_engineer",
                "department": "testing",
                "action": "test_product",
                "dependencies": ["frontend_dev", "backend_dev"]
            },
            {
                "id": "release",
                "name": "发布上线",
                "agent": "release_manager",
                "department": "operations",
                "action": "release_product",
                "dependencies": ["testing"]
            }
        ]
    },
    "marketing_campaign": {
        "name": "市场推广流程",
        "description": "产品市场推广的标准流程",
        "workflow_type": WorkflowType.SEQUENTIAL,
        "steps": [
            {
                "id": "market_research",
                "name": "市场调研",
                "agent": "market_analyst",
                "department": "marketing",
                "action": "conduct_research"
            },
            {
                "id": "strategy",
                "name": "推广策略",
                "agent": "marketing_strategist",
                "department": "marketing",
                "action": "create_strategy",
                "dependencies": ["market_research"]
            },
            {
                "id": "content_creation",
                "name": "内容创作",
                "agent": "content_creator",
                "department": "marketing",
                "action": "create_content",
                "dependencies": ["strategy"]
            },
            {
                "id": "campaign_launch",
                "name": "活动发布",
                "agent": "campaign_manager",
                "department": "marketing",
                "action": "launch_campaign",
                "dependencies": ["content_creation"]
            },
            {
                "id": "analytics",
                "name": "效果分析",
                "agent": "marketing_analyst",
                "department": "marketing",
                "action": "analyze_results",
                "dependencies": ["campaign_launch"]
            }
        ]
    }
}


def create_workflow_from_template(template_name: str, variables: Dict[str, Any] = None) -> WorkflowDefinition:
    """从模板创建工作流
    
    Args:
        template_name: 模板名称
        variables: 变量
        
    Returns:
        工作流定义
    """
    if template_name not in WORKFLOW_TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}")
    
    template = WORKFLOW_TEMPLATES[template_name]
    
    steps = []
    for step_data in template["steps"]:
        step = WorkflowStep(
            id=step_data["id"],
            name=step_data["name"],
            description=step_data.get("description", ""),
            agent=step_data.get("agent", ""),
            department=step_data.get("department", ""),
            action=step_data.get("action", ""),
            dependencies=step_data.get("dependencies", [])
        )
        steps.append(step)
    
    return WorkflowDefinition(
        id=f"{template_name}_{int(time.time())}",
        name=template["name"],
        description=template["description"],
        workflow_type=template["workflow_type"],
        steps=steps,
        variables=variables or {}
    )
