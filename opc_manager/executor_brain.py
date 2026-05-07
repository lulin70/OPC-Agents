"""
执行脑 (ExecutorBrain) - 负责技能执行和工具调用

这是三贤者架构中的贤者二，专注于微观执行：
- 执行步骤
- 调用技能和工具
- 监控执行过程
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import copy
import uuid
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


class ExecutionStatusType(Enum):
    """执行状态类型枚举"""
    PENDING = "pending"           # 待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
    TIMEOUT = "timeout"           # 超时


class ExecutionResultType(Enum):
    """执行结果类型枚举"""
    SUCCESS = "success"           # 成功
    FAILURE = "failure"           # 失败
    TIMEOUT = "timeout"           # 超时
    CANCELLED = "cancelled"       # 取消


@dataclass
class ExecutionResult:
    """执行结果对象"""
    success: bool                  # 是否成功
    data: Dict[str, Any] = None     # 返回数据
    error: Optional[str] = None     # 错误信息
    result_type: ExecutionResultType = ExecutionResultType.SUCCESS
    execution_time: float = 0.0     # 执行时间（秒）

    def __post_init__(self):
        if self.data is None:
            self.data = {}


@dataclass
class ExecutionStatus:
    """执行状态对象"""
    task_id: str                     # 任务ID
    status: ExecutionStatusType      # 状态类型
    step_id: Optional[str] = None    # 当前执行步骤ID
    progress: float = 0.0            # 进度 (0-1)
    message: str = ""                # 状态消息
    started_at: Optional[float] = None  # 开始时间
    completed_at: Optional[float] = None  # 完成时间


MAX_TASK_HISTORY = 100


class BoundedDict:
    def __init__(self, max_size: int = MAX_TASK_HISTORY):
        self._data: OrderedDict = OrderedDict()
        self.max_size = max_size

    def __setitem__(self, key, value):
        self._data[key] = value
        self._cleanup()

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __delitem__(self, key):
        del self._data[key]

    def pop(self, key, default=None):
        return self._data.pop(key, default)

    def __len__(self):
        return len(self._data)

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def _cleanup(self):
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)


class ExecutorBrain:

    def __init__(self, skill_registry=None, tool_system=None):
        self.skill_registry = skill_registry
        self.tool_system = tool_system
        self.task_statuses: BoundedDict = BoundedDict(max_size=MAX_TASK_HISTORY)
        self.execution_locks: Dict[str, asyncio.Lock] = {}

    async def execute_step(self, step_id: str, skill_id: str, 
                          parameters: Dict[str, Any], 
                          context: Optional[Dict] = None) -> ExecutionResult:
        """
        执行单个步骤
        
        Args:
            step_id: 步骤ID
            skill_id: 技能ID
            parameters: 执行参数
            context: 当前执行上下文
        
        Returns:
            ExecutionResult: 执行结果
        """
        logger.info(f"开始执行步骤: {step_id}, 技能: {skill_id}")
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await self._execute_skill(skill_id, parameters, context)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            if result.success:
                logger.info(f"步骤 {step_id} 执行成功，耗时: {execution_time:.2f}s")
                return ExecutionResult(
                    success=True,
                    data=result.data,
                    result_type=ExecutionResultType.SUCCESS,
                    execution_time=execution_time
                )
            else:
                logger.warning(f"步骤 {step_id} 执行失败: {result.error}")
                return ExecutionResult(
                    success=False,
                    error=result.error,
                    result_type=ExecutionResultType.FAILURE,
                    execution_time=execution_time
                )
        
        except asyncio.TimeoutError:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"步骤 {step_id} 执行超时")
            return ExecutionResult(
                success=False,
                error="执行超时",
                result_type=ExecutionResultType.TIMEOUT,
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"步骤 {step_id} 执行异常: {str(e)}")
            return ExecutionResult(
                success=False,
                error=str(e),
                result_type=ExecutionResultType.FAILURE,
                execution_time=execution_time
            )

    async def _execute_skill(self, skill_id: str, parameters: Dict[str, Any], 
                            context: Optional[Dict]) -> ExecutionResult:
        if self.skill_registry:
            skill = self.skill_registry.get_skill(skill_id)
            if skill is None:
                return ExecutionResult(
                    success=False,
                    error=f"技能不存在: {skill_id}"
                )
            if not skill.enabled:
                return ExecutionResult(
                    success=False,
                    error=f"技能已禁用: {skill_id}"
                )
            try:
                if asyncio.iscoroutinefunction(skill.execute):
                    result = await skill.execute(**parameters)
                else:
                    result = skill.execute(**parameters)
                
                if isinstance(result, dict):
                    return ExecutionResult(
                        success=result.get("success", True),
                        data=result.get("data", result)
                    )
                return ExecutionResult(success=True, data={"result": result})
            except Exception as e:
                return ExecutionResult(
                    success=False,
                    error=f"技能执行异常: {str(e)}"
                )
        
        return await self._execute_skill_mock(skill_id)

    async def _execute_skill_mock(self, skill_id: str) -> ExecutionResult:
        mock_results = {
            "intent_analysis": {"success": True, "data": {"analysis": "用户需求分析完成", "confidence": 0.85}},
            "search": {"success": True, "data": {"results": ["搜索结果1", "搜索结果2", "搜索结果3"], "count": 3}},
            "analysis": {"success": True, "data": {"analysis_result": "分析报告内容", "key_findings": ["发现1", "发现2"]}},
            "content_generation": {"success": True, "data": {"content": "生成的内容", "format": "markdown"}},
            "execute_operation": {"success": True, "data": {"operation_result": "操作执行成功"}},
            "send_notification": {"success": True, "data": {"notification_sent": True, "recipient": "user@example.com"}},
            "output_result": {"success": True, "data": {"output": "最终输出结果", "format": "markdown"}},
        }
        await asyncio.sleep(0.01)
        result = mock_results.get(skill_id)
        if result:
            return ExecutionResult(success=result["success"], data=result.get("data", {}))
        return ExecutionResult(success=False, error=f"未知技能: {skill_id}")

    async def execute_plan(self, plan_id: str, steps: List[Dict], 
                          context: Optional[Dict] = None) -> ExecutionResult:
        """
        执行完整计划
        
        Args:
            plan_id: 计划ID
            steps: 步骤列表
            context: 执行上下文
        
        Returns:
            ExecutionResult: 最终执行结果
        """
        logger.info(f"开始执行计划: {plan_id}, 步骤数: {len(steps)}")
        
        # 创建任务状态
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self.task_statuses[task_id] = ExecutionStatus(
            task_id=task_id,
            status=ExecutionStatusType.RUNNING,
            progress=0.0,
            started_at=asyncio.get_event_loop().time()
        )
        
        try:
            steps_copy = copy.deepcopy(steps)
            results = []
            for i, step in enumerate(steps_copy, 1):
                self.task_statuses[task_id].step_id = step.get("id")
                self.task_statuses[task_id].progress = i / len(steps_copy)
                self.task_statuses[task_id].message = f"正在执行步骤 {i}/{len(steps_copy)}: {step.get('description', '')}"
                
                result = await self.execute_step(
                    step_id=step["id"],
                    skill_id=step["skill_id"],
                    parameters=step.get("parameters", {}),
                    context=context
                )
                
                results.append(result)
                
                if not result.success:
                    retry_count = step.get("retry_count", 0)
                    if retry_count < 3:
                        step["retry_count"] = retry_count + 1
                        logger.info(f"步骤 {step['id']} 失败，重试第 {retry_count + 1} 次")
                        result = await self.execute_step(
                            step_id=step["id"],
                            skill_id=step["skill_id"],
                            parameters=step.get("parameters", {}),
                            context=context
                        )
                        results.append(result)
                
                if not result.success:
                    self.task_statuses[task_id].status = ExecutionStatusType.FAILED
                    self.task_statuses[task_id].completed_at = asyncio.get_event_loop().time()
                    self.task_statuses[task_id].message = f"步骤 {step['id']} 执行失败: {result.error}"
                    return ExecutionResult(
                        success=False,
                        error=f"步骤 {step['id']} 执行失败: {result.error}",
                        data={"results": results}
                    )
            
            # 所有步骤执行成功
            self.task_statuses[task_id].status = ExecutionStatusType.COMPLETED
            self.task_statuses[task_id].progress = 1.0
            self.task_statuses[task_id].completed_at = asyncio.get_event_loop().time()
            self.task_statuses[task_id].message = "执行完成"
            
            logger.info(f"计划 {plan_id} 执行完成")
            self._cleanup_old_tasks()
            return ExecutionResult(
                success=True,
                data={"results": results, "task_id": task_id}
            )
            
        except Exception as e:
            self.task_statuses[task_id].status = ExecutionStatusType.FAILED
            self.task_statuses[task_id].completed_at = asyncio.get_event_loop().time()
            self.task_statuses[task_id].message = f"执行异常: {str(e)}"
            logger.error(f"计划 {plan_id} 执行异常: {str(e)}")
            self._cleanup_old_tasks()
            return ExecutionResult(
                success=False,
                error=str(e)
            )

    def _cleanup_old_tasks(self) -> None:
        pass

    def get_execution_status(self, task_id: str) -> Optional[ExecutionStatus]:
        """
        获取执行状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            Optional[ExecutionStatus]: 执行状态
        """
        return self.task_statuses.get(task_id)

    async def cancel_execution(self, task_id: str) -> bool:
        """
        取消执行
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否成功取消
        """
        if task_id not in self.task_statuses:
            return False
        
        status = self.task_statuses[task_id]
        if status.status in [ExecutionStatusType.RUNNING, ExecutionStatusType.PENDING]:
            status.status = ExecutionStatusType.CANCELLED
            status.completed_at = asyncio.get_event_loop().time()
            status.message = "任务已取消"
            logger.info(f"任务 {task_id} 已取消")
            return True
        
        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        将执行脑状态转换为字典
        
        Returns:
            Dict[str, Any]: 状态字典
        """
        return {
            "type": "executor_brain",
            "task_count": len(self.task_statuses)
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典恢复执行脑状态
        
        Args:
            data: 状态字典
        """
        # 可以在这里添加状态恢复逻辑
        pass
