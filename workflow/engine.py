#!/usr/bin/env python3
"""
Workflow Engine for OPC-Agents

Core workflow orchestration engine.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from queue import Queue
import uuid

from .definitions import (
    WorkflowDefinition, WorkflowStep, WorkflowStatus, StepStatus,
    WorkflowType, create_workflow_from_template
)


@dataclass
class WorkflowContext:
    """工作流执行上下文"""
    workflow_id: str
    variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_variable(self, key: str, value: Any):
        """设置变量"""
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取变量"""
        return self.variables.get(key, default)
    
    def set_step_result(self, step_id: str, result: Any):
        """设置步骤结果"""
        self.step_results[step_id] = result
    
    def get_step_result(self, step_id: str) -> Any:
        """获取步骤结果"""
        return self.step_results.get(step_id)
    
    def log(self, level: str, message: str, details: Dict[str, Any] = None):
        """记录日志"""
        entry = {
            "timestamp": time.time(),
            "level": level,
            "message": message,
            "details": details or {}
        }
        self.execution_log.append(entry)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "variables": self.variables,
            "step_results": self.step_results,
            "execution_log": self.execution_log
        }


class WorkflowEngine:
    """工作流引擎
    
    负责工作流的创建、执行、监控和管理。
    """
    
    def __init__(self, opc_manager=None):
        """初始化工作流引擎
        
        Args:
            opc_manager: OPCManager实例
        """
        self.opc_manager = opc_manager
        self.logger = logging.getLogger("OPC-Agents.WorkflowEngine")
        
        # 工作流存储
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._contexts: Dict[str, WorkflowContext] = {}
        self._statuses: Dict[str, WorkflowStatus] = {}
        
        # 执行队列
        self._execution_queue: Queue = Queue()
        self._executor_thread = None
        self._is_running = False
        
        # 回调函数
        self.on_workflow_start: Optional[Callable] = None
        self.on_workflow_complete: Optional[Callable] = None
        self.on_step_start: Optional[Callable] = None
        self.on_step_complete: Optional[Callable] = None
        self.on_step_failed: Optional[Callable] = None
        
        self.logger.info("WorkflowEngine initialized")
    
    def create_workflow(self, name: str, description: str = "",
                       workflow_type: WorkflowType = WorkflowType.SEQUENTIAL,
                       steps: List[Dict[str, Any]] = None,
                       variables: Dict[str, Any] = None) -> WorkflowDefinition:
        """创建新工作流
        
        Args:
            name: 工作流名称
            description: 描述
            workflow_type: 工作流类型
            steps: 步骤列表
            variables: 变量
            
        Returns:
            工作流定义
        """
        workflow_id = f"wf_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        workflow = WorkflowDefinition(
            id=workflow_id,
            name=name,
            description=description,
            workflow_type=workflow_type,
            variables=variables or {}
        )
        
        if steps:
            for i, step_data in enumerate(steps):
                step = WorkflowStep(
                    id=step_data.get("id", f"step_{i+1}"),
                    name=step_data.get("name", f"步骤{i+1}"),
                    description=step_data.get("description", ""),
                    agent=step_data.get("agent", ""),
                    department=step_data.get("department", ""),
                    action=step_data.get("action", ""),
                    parameters=step_data.get("parameters", {}),
                    dependencies=step_data.get("dependencies", [])
                )
                workflow.add_step(step)
        
        # 验证工作流
        errors = workflow.validate()
        if errors:
            raise ValueError(f"工作流验证失败: {errors}")
        
        self._workflows[workflow_id] = workflow
        self._statuses[workflow_id] = WorkflowStatus.CREATED
        
        self.logger.info(f"Created workflow: {workflow_id} - {name}")
        return workflow
    
    def create_from_template(self, template_name: str, 
                            variables: Dict[str, Any] = None) -> WorkflowDefinition:
        """从模板创建工作流
        
        Args:
            template_name: 模板名称
            variables: 变量
            
        Returns:
            工作流定义
        """
        workflow = create_workflow_from_template(template_name, variables)
        self._workflows[workflow.id] = workflow
        self._statuses[workflow.id] = WorkflowStatus.CREATED
        
        self.logger.info(f"Created workflow from template: {workflow.id}")
        return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取工作流"""
        return self._workflows.get(workflow_id)
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """获取工作流状态"""
        return self._statuses.get(workflow_id)
    
    def get_context(self, workflow_id: str) -> Optional[WorkflowContext]:
        """获取执行上下文"""
        return self._contexts.get(workflow_id)
    
    def list_workflows(self, status: WorkflowStatus = None) -> List[WorkflowDefinition]:
        """列出工作流
        
        Args:
            status: 过滤状态（可选）
            
        Returns:
            工作流列表
        """
        if status:
            return [wf for wf_id, wf in self._workflows.items() 
                   if self._statuses.get(wf_id) == status]
        return list(self._workflows.values())
    
    def start(self):
        """启动工作流引擎"""
        if self._is_running:
            return
        
        self._is_running = True
        self._executor_thread = threading.Thread(target=self._execution_loop, daemon=True)
        self._executor_thread.start()
        self.logger.info("WorkflowEngine started")
    
    def stop(self):
        """停止工作流引擎"""
        self._is_running = False
        if self._executor_thread:
            self._executor_thread.join(timeout=5)
        self.logger.info("WorkflowEngine stopped")
    
    def execute(self, workflow_id: str) -> bool:
        """执行工作流
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            是否成功启动
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            self.logger.error(f"Workflow not found: {workflow_id}")
            return False
        
        # 创建执行上下文
        context = WorkflowContext(
            workflow_id=workflow_id,
            variables=workflow.variables.copy()
        )
        self._contexts[workflow_id] = context
        
        # 更新状态
        self._statuses[workflow_id] = WorkflowStatus.RUNNING
        
        # 加入执行队列
        self._execution_queue.put((workflow_id, time.time()))
        
        self.logger.info(f"Workflow execution started: {workflow_id}")
        
        if self.on_workflow_start:
            self.on_workflow_start(workflow_id, workflow)
        
        return True
    
    def _execution_loop(self):
        """执行循环"""
        while self._is_running:
            try:
                # 获取待执行的工作流
                try:
                    workflow_id, start_time = self._execution_queue.get(timeout=1)
                except:
                    continue
                
                workflow = self._workflows.get(workflow_id)
                context = self._contexts.get(workflow_id)
                
                if not workflow or not context:
                    continue
                
                # 执行工作流
                try:
                    success = self._execute_workflow(workflow, context)
                    
                    if success:
                        self._statuses[workflow_id] = WorkflowStatus.COMPLETED
                        self.logger.info(f"Workflow completed: {workflow_id}")
                        
                        if self.on_workflow_complete:
                            self.on_workflow_complete(workflow_id, workflow, True)
                    else:
                        self._statuses[workflow_id] = WorkflowStatus.FAILED
                        self.logger.error(f"Workflow failed: {workflow_id}")
                        
                        if self.on_workflow_complete:
                            self.on_workflow_complete(workflow_id, workflow, False)
                    
                except Exception as e:
                    self.logger.error(f"Workflow execution error: {e}")
                    self._statuses[workflow_id] = WorkflowStatus.FAILED
                    
                    if self.on_workflow_complete:
                        self.on_workflow_complete(workflow_id, workflow, False)
                
            except Exception as e:
                self.logger.error(f"Execution loop error: {e}")
    
    def _execute_workflow(self, workflow: WorkflowDefinition, 
                         context: WorkflowContext) -> bool:
        """执行工作流
        
        Args:
            workflow: 工作流定义
            context: 执行上下文
            
        Returns:
            是否成功
        """
        context.log("info", f"开始执行工作流: {workflow.name}")
        
        # 重置所有步骤状态
        for step in workflow.steps:
            step.status = StepStatus.PENDING
            step.result = None
            step.error = None
        
        if workflow.workflow_type == WorkflowType.SEQUENTIAL:
            return self._execute_sequential(workflow, context)
        elif workflow.workflow_type == WorkflowType.PARALLEL:
            return self._execute_parallel(workflow, context)
        elif workflow.workflow_type == WorkflowType.HYBRID:
            return self._execute_hybrid(workflow, context)
        else:
            return self._execute_sequential(workflow, context)
    
    def _execute_sequential(self, workflow: WorkflowDefinition,
                           context: WorkflowContext) -> bool:
        """串行执行"""
        for step in workflow.steps:
            if not self._execute_step(step, workflow, context):
                return False
        return True
    
    def _execute_parallel(self, workflow: WorkflowDefinition,
                         context: WorkflowContext) -> bool:
        """并行执行"""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(workflow.steps)) as executor:
            futures = {}
            for step in workflow.steps:
                future = executor.submit(self._execute_step, step, workflow, context)
                futures[future] = step
            
            for future in concurrent.futures.as_completed(futures):
                step = futures[future]
                try:
                    if not future.result():
                        return False
                except Exception as e:
                    self.logger.error(f"Step {step.id} failed: {e}")
                    return False
        
        return True
    
    def _execute_hybrid(self, workflow: WorkflowDefinition,
                       context: WorkflowContext) -> bool:
        """混合执行（考虑依赖关系）"""
        completed_steps = set()
        pending_steps = list(workflow.steps)
        
        while pending_steps:
            # 找出可以执行的步骤
            ready_steps = [
                s for s in pending_steps
                if all(dep in completed_steps for dep in s.dependencies)
            ]
            
            if not ready_steps:
                # 检查是否有失败的步骤导致死锁
                failed_steps = [s for s in pending_steps if s.status == StepStatus.FAILED]
                if failed_steps:
                    context.log("error", f"工作流因步骤失败而终止")
                    return False
                break
            
            # 执行就绪步骤
            for step in ready_steps:
                if not self._execute_step(step, workflow, context):
                    return False
                completed_steps.add(step.id)
                pending_steps.remove(step)
        
        return True
    
    def _execute_step(self, step: WorkflowStep, workflow: WorkflowDefinition,
                     context: WorkflowContext) -> bool:
        """执行单个步骤"""
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        
        context.log("info", f"开始执行步骤: {step.name}")
        
        if self.on_step_start:
            self.on_step_start(workflow.id, step)
        
        try:
            # 执行步骤动作
            result = self._perform_step_action(step, context)
            
            step.result = result
            step.status = StepStatus.COMPLETED
            step.completed_at = time.time()
            
            context.set_step_result(step.id, result)
            context.log("info", f"步骤完成: {step.name}")
            
            if self.on_step_complete:
                self.on_step_complete(workflow.id, step, result)
            
            return True
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = time.time()
            
            context.log("error", f"步骤失败: {step.name} - {e}")
            
            if self.on_step_failed:
                self.on_step_failed(workflow.id, step, str(e))
            
            return False
    
    def _perform_step_action(self, step: WorkflowStep, 
                            context: WorkflowContext) -> Any:
        """执行步骤动作"""
        if not self.opc_manager:
            # 模拟执行
            self.logger.warning(f"No OPCManager, simulating step: {step.id}")
            time.sleep(0.5)
            return {"simulated": True, "step": step.id}
        
        # 通过通信管理器发送任务给Agent
        if step.agent:
            result = self.opc_manager.communication_manager.send_message(
                sender="workflow_engine",
                receiver=step.agent,
                message_type="workflow_step",
                content=f"执行工作流步骤: {step.name}\n动作: {step.action}",
                context={
                    "workflow_id": context.workflow_id,
                    "step_id": step.id,
                    "parameters": step.parameters
                }
            )
            return result
        
        return {"executed": True, "step": step.id}
    
    def pause(self, workflow_id: str) -> bool:
        """暂停工作流"""
        if self._statuses.get(workflow_id) == WorkflowStatus.RUNNING:
            self._statuses[workflow_id] = WorkflowStatus.PAUSED
            self.logger.info(f"Workflow paused: {workflow_id}")
            return True
        return False
    
    def resume(self, workflow_id: str) -> bool:
        """恢复工作流"""
        if self._statuses.get(workflow_id) == WorkflowStatus.PAUSED:
            self._statuses[workflow_id] = WorkflowStatus.RUNNING
            self._execution_queue.put((workflow_id, time.time()))
            self.logger.info(f"Workflow resumed: {workflow_id}")
            return True
        return False
    
    def cancel(self, workflow_id: str) -> bool:
        """取消工作流"""
        if workflow_id in self._statuses:
            self._statuses[workflow_id] = WorkflowStatus.CANCELLED
            self.logger.info(f"Workflow cancelled: {workflow_id}")
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        status_counts = {}
        for status in WorkflowStatus:
            status_counts[status.value] = sum(
                1 for s in self._statuses.values() if s == status
            )
        
        return {
            "total_workflows": len(self._workflows),
            "status_counts": status_counts,
            "is_running": self._is_running
        }
