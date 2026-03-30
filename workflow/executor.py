#!/usr/bin/env python3
"""
Workflow Executor for OPC-Agents

Executes workflow steps and handles step execution.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor

from .definitions import (
    WorkflowDefinition, WorkflowStep, WorkflowStatus, StepStatus,
    WorkflowType, WorkflowContext
)


class WorkflowExecutor:
    """工作流执行器
    
    负责执行工作流中的具体步骤。
    """
    
    def __init__(self, opc_manager=None, max_workers: int = 4):
        """初始化工作流执行器
        
        Args:
            opc_manager: OPCManager实例
            max_workers: 最大并行工作线程数
        """
        self.opc_manager = opc_manager
        self.max_workers = max_workers
        self.logger = logging.getLogger("OPC-Agents.WorkflowExecutor")
        
        # 线程池
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 执行状态
        self._active_executions: Dict[str, threading.Future] = {}
        self._lock = threading.Lock()
    
    def execute_step(self, workflow: WorkflowDefinition, step: WorkflowStep,
                    context: WorkflowContext) -> Any:
        """执行单个步骤
        
        Args:
            workflow: 工作流定义
            step: 步骤定义
            context: 执行上下文
            
        Returns:
            步骤执行结果
        """
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        
        context.log("info", f"开始执行步骤: {step.name}", {
            "step_id": step.id,
            "workflow_id": context.workflow_id
        })
        
        try:
            # 获取Agent
            agent_name = step.agent
            department = step.department
            
            # 构建执行请求
            action = step.action
            parameters = step.parameters.copy()
            
            # 如果参数中有变量引用，进行变量替换
            for key, parameters:
                if isinstance(parameters[key], str) and parameters[key].startswith("${"):
                    value = context.get_variable(key)
                    parameters[key] = value
            
            result = self._execute_action(
                agent_name=agent_name,
                department=department,
                action=action,
                parameters=parameters,
                context=context
            )
            
            # 处理结果
            if result.get("success"):
                step.status = StepStatus.COMPLETED
                step.result = result.get("result")
                step.completed_at = time.time()
                
                context.set_step_result(step.id, step.result)
                context.log("info", f"步骤完成: {step.name}", {
                    "step_id": step.id,
                    "workflow_id": context.workflow_id,
                    "duration": step.completed_at - step.started_at
                })
            else:
                step.status = StepStatus.FAILED
                step.error = result.get("error", "未知错误")
                step.completed_at = time.time()
                
                context.log("error", f"步骤失败: {step.name}: {step.error}", {
                    "step_id": step.id,
                    "workflow_id": context.workflow_id
                })
            
            return result
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.completed_at = time.time()
            
            context.log("error", f"步骤执行异常: {step.name}: {e}", {
                "step_id": step.id,
                "workflow_id": context.workflow_id
            })
        
            return result
    
    def _execute_action(self, agent_name: str, department: str, 
                         action: str, parameters: Dict[str, Any],
                         context: WorkflowContext) -> Dict[str, Any]:
        """执行动作
        
        Args:
            agent_name: Agent名称
            department: 部门名称
            action: 动作名称
            parameters: 参数
            context: 执行上下文
            
        Returns:
            执行结果
        """
        # 优先使用OPCManager调用真实模型
        if self.opc_manager:
            try:
                result = self.opc_manager.communication_manager.send_message(
                    sender="workflow_engine",
                    receiver=agent_name,
                    message_type="task",
                    content=f"请执行动作: {action}\n参数: {parameters}",
                    context={"workflow_id": context.workflow_id}
                )
                return {"success": True, "response": result.get("response", "")}
            except Exception as e:
                self.logger.error(f"OPCManager execution error: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "No OPCManager available"}
    
    def shutdown(self):
        """关闭执行器"""
        self._executor.shutdown(wait=True)
        self.logger.info("WorkflowExecutor shutdown")
