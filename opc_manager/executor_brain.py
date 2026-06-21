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

from .utils import (
    BoundedDict,
    call_llm_service,
    extract_json_from_llm,
    sanitize_for_llm,
)
from .task_engine_v3 import TaskEngineV3, TaskType
from .intent_types import SKILL_TO_TASK_MAP
from .consensus_engine import Opinion, OpinionType

logger = logging.getLogger(__name__)

MAX_TASK_HISTORY = 100
COMMAND_TIMEOUT_SECONDS = 30


class ExecutionStatusType(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionResultType(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    success: bool
    data: Dict[str, Any] = None
    error: Optional[str] = None
    result_type: ExecutionResultType = ExecutionResultType.SUCCESS
    execution_time: float = 0.0

    def __post_init__(self):
        if self.data is None:
            self.data = {}


@dataclass
class ExecutionStatus:
    task_id: str
    status: ExecutionStatusType
    step_id: Optional[str] = None
    progress: float = 0.0
    message: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ExecutorBrain:

    def __init__(
        self, skill_registry=None, tool_system=None, task_engine=None, llm_service=None
    ):
        self.skill_registry = skill_registry
        self.tool_system = tool_system
        self.task_engine = task_engine or TaskEngineV3()
        self.llm_service = llm_service
        self.task_statuses: BoundedDict = BoundedDict(max_size=MAX_TASK_HISTORY)

    @staticmethod
    def _extract_user_input(parameters: Dict[str, Any]) -> str:
        """Extract user input from parameters using common key names."""
        for key in ("query", "goal", "user_input", "input", "content"):
            val = parameters.get(key)
            if val:
                return val
        return ""

    async def _run_task_engine(
        self, skill_id: str, parameters: Dict[str, Any]
    ) -> Optional[ExecutionResult]:
        """Execute via TaskEngineV3 as fallback. Returns None if no input or engine unavailable."""
        if not self.task_engine:
            return None
        try:
            # Set fallback flag to prevent circular fallback
            if hasattr(self.task_engine, "_in_fallback"):
                self.task_engine._in_fallback = True
            try:
                task_type = SKILL_TO_TASK_MAP.get(skill_id, TaskType.GENERAL_CHAT)
                user_input = self._extract_user_input(parameters)
                if not user_input:
                    return None
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self.task_engine.execute(
                        user_input=user_input,
                        session_ctx=parameters.get("session_ctx"),
                        business_type=parameters.get("business_type"),
                        task_type_hint=task_type,
                    ),
                )
            finally:
                # Always clear fallback flag
                if hasattr(self.task_engine, "_in_fallback"):
                    self.task_engine._in_fallback = False
            return ExecutionResult(
                success=result.success,
                data={
                    "content": result.content,
                    "sources": result.sources or [],
                    "task_type": (result.task_type.value if result.task_type else None),
                    "deliverable_format": result.deliverable_format,
                },
                error=result.error,
                execution_time=(
                    result.execution_time_ms / 1000.0 if result.execution_time_ms else 0
                ),
            )
        except Exception as e:
            logger.warning("TaskEngineV3降级执行失败: %s", e)
            return None

    async def execute_step(
        self,
        step_id: str,
        skill_id: str,
        parameters: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> ExecutionResult:
        logger.info("开始执行步骤: %s, 技能: %s", step_id, skill_id)

        start_time = asyncio.get_running_loop().time()

        try:
            if context and context.get("degrade"):
                result = await asyncio.wait_for(
                    self._execute_degraded(skill_id, parameters, context),
                    timeout=COMMAND_TIMEOUT_SECONDS,
                )
            else:
                result = await asyncio.wait_for(
                    self._execute_skill(skill_id, parameters, context),
                    timeout=COMMAND_TIMEOUT_SECONDS,
                )

            execution_time = asyncio.get_running_loop().time() - start_time

            if result is None:
                logger.error("步骤 %s 执行返回None", step_id)
                return ExecutionResult(
                    success=False,
                    error="执行返回空结果",
                    result_type=ExecutionResultType.FAILURE,
                    execution_time=execution_time,
                )

            if result.success:
                logger.info("步骤 %s 执行成功，耗时: %.2fs", step_id, execution_time)
                return ExecutionResult(
                    success=True,
                    data=result.data,
                    result_type=ExecutionResultType.SUCCESS,
                    execution_time=execution_time,
                )
            else:
                logger.warning("步骤 %s 执行失败: %s", step_id, result.error)
                return ExecutionResult(
                    success=False,
                    error=result.error,
                    result_type=ExecutionResultType.FAILURE,
                    execution_time=execution_time,
                )

        except asyncio.TimeoutError:
            execution_time = asyncio.get_running_loop().time() - start_time
            logger.error("步骤 %s 执行超时", step_id)
            return ExecutionResult(
                success=False,
                error="执行超时",
                result_type=ExecutionResultType.TIMEOUT,
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = asyncio.get_running_loop().time() - start_time
            logger.error("步骤 %s 执行异常: %s", step_id, str(e))
            return ExecutionResult(
                success=False,
                error=str(e),
                result_type=ExecutionResultType.FAILURE,
                execution_time=execution_time,
            )

    async def _execute_degraded(
        self, skill_id: str, parameters: Dict[str, Any], context: Optional[Dict]
    ) -> ExecutionResult:
        # Try TaskEngine first
        result = await self._run_task_engine(skill_id, parameters)
        if result is not None:
            return result

        # Then try skill registry
        if self.skill_registry:
            skill = self.skill_registry.get_skill(skill_id)
            if skill is not None and skill.enabled:
                try:
                    if asyncio.iscoroutinefunction(skill.execute):
                        result = await skill.execute(**parameters)
                    else:
                        result = skill.execute(**parameters)
                    if isinstance(result, dict):
                        return ExecutionResult(
                            success=result.get("success", True),
                            data=result.get("data", result),
                        )
                    return ExecutionResult(success=True, data={"result": result})
                except Exception as e:
                    return ExecutionResult(
                        success=False, error=f"降级技能执行异常: {str(e)}"
                    )

        return ExecutionResult(success=False, error=f"降级模式无可用执行器: {skill_id}")

    async def _execute_skill(
        self, skill_id: str, parameters: Dict[str, Any], context: Optional[Dict]
    ) -> ExecutionResult:
        if self.skill_registry:
            skill = self.skill_registry.get_skill(skill_id)
            if skill is not None:
                if not skill.enabled:
                    # Skill disabled — try TaskEngine fallback
                    fallback = await self._run_task_engine(skill_id, parameters)
                    if fallback is not None:
                        return fallback
                    return ExecutionResult(
                        success=False, error=f"技能已禁用: {skill_id}"
                    )
                # P0-3 修复：技能冻结机制真正生效
                # frozen=True 表示完全冻结，拒绝执行；半冻结技能允许通过维护方法调用
                if getattr(skill, "frozen", False) is True:
                    logger.warning("技能已冻结（v0.3.0），拒绝执行: %s", skill_id)
                    return ExecutionResult(
                        success=False,
                        error=f"技能已冻结（v0.3.0 产品收缩决策）: {skill_id}。详见 docs/spec/SKILL_FREEZE_LIST.md",
                    )
                try:
                    if asyncio.iscoroutinefunction(skill.execute):
                        result = await skill.execute(**parameters)
                    else:
                        result = skill.execute(**parameters)

                    if isinstance(result, dict):
                        exec_result = ExecutionResult(
                            success=result.get("success", True),
                            data=result.get("data", result),
                        )
                    else:
                        exec_result = ExecutionResult(
                            success=True, data={"result": result}
                        )

                    if not exec_result.success:
                        # Skill failed — try TaskEngine fallback
                        fallback = await self._run_task_engine(skill_id, parameters)
                        if fallback is not None and fallback.success:
                            logger.info(
                                "skill_registry失败，task_engine降级成功: %s",
                                skill_id,
                            )
                            return fallback

                    return exec_result
                except Exception as e:
                    # Skill threw exception — try TaskEngine fallback
                    fallback = await self._run_task_engine(skill_id, parameters)
                    if fallback is not None and fallback.success:
                        logger.info(
                            "skill_registry异常，task_engine降级成功: %s",
                            skill_id,
                        )
                        return fallback
                    return ExecutionResult(
                        success=False, error=f"技能执行异常: {str(e)}"
                    )

        # No skill in registry — try TaskEngine directly
        fallback = await self._run_task_engine(skill_id, parameters)
        if fallback is not None:
            return fallback

        return ExecutionResult(
            success=False, error=f"技能不存在且无可用执行器: {skill_id}"
        )

    async def execute_plan(
        self, plan_id: str, steps: List[Dict], context: Optional[Dict] = None
    ) -> ExecutionResult:
        logger.info("开始执行计划: %s, 步骤数: %s", plan_id, len(steps))

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        self.task_statuses[task_id] = ExecutionStatus(
            task_id=task_id,
            status=ExecutionStatusType.RUNNING,
            progress=0.0,
            started_at=asyncio.get_running_loop().time(),
        )

        try:
            steps_copy = copy.deepcopy(steps)
            results = []
            for i, step in enumerate(steps_copy, 1):
                self.task_statuses[task_id].step_id = step.get("id")
                self.task_statuses[task_id].progress = i / len(steps_copy)
                self.task_statuses[task_id].message = (
                    f"正在执行步骤 {i}/{len(steps_copy)}: {step.get('description', '')}"
                )

                result = await self.execute_step(
                    step_id=step["id"],
                    skill_id=step["skill_id"],
                    parameters=step.get("parameters", {}),
                    context=context,
                )

                results.append(result)

                if not result.success:
                    self.task_statuses[task_id].status = ExecutionStatusType.FAILED
                    self.task_statuses[task_id].completed_at = (
                        asyncio.get_running_loop().time()
                    )
                    self.task_statuses[task_id].message = (
                        f"步骤 {step['id']} 执行失败: {result.error}"
                    )
                    return ExecutionResult(
                        success=False,
                        error=f"步骤 {step['id']} 执行失败: {result.error}",
                        data={"results": results},
                    )

            self.task_statuses[task_id].status = ExecutionStatusType.COMPLETED
            self.task_statuses[task_id].progress = 1.0
            self.task_statuses[task_id].completed_at = asyncio.get_running_loop().time()
            self.task_statuses[task_id].message = "执行完成"

            logger.info("计划 %s 执行完成", plan_id)
            return ExecutionResult(
                success=True, data={"results": results, "task_id": task_id}
            )

        except Exception as e:
            self.task_statuses[task_id].status = ExecutionStatusType.FAILED
            self.task_statuses[task_id].completed_at = asyncio.get_running_loop().time()
            self.task_statuses[task_id].message = f"执行异常: {str(e)}"
            logger.error("计划 %s 执行异常: %s", plan_id, str(e))
            return ExecutionResult(success=False, error=str(e))

    def get_execution_status(self, task_id: str) -> Optional[ExecutionStatus]:
        return self.task_statuses.get(task_id)

    async def cancel_execution(self, task_id: str) -> bool:
        if task_id not in self.task_statuses:
            return False

        status = self.task_statuses[task_id]
        if status.status in [ExecutionStatusType.RUNNING, ExecutionStatusType.PENDING]:
            status.status = ExecutionStatusType.CANCELLED
            status.completed_at = asyncio.get_running_loop().time()
            status.message = "任务已取消"
            logger.info("任务 %s 已取消", task_id)
            return True

        return False

    def express_opinion(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Opinion:
        """
        ExecutorBrain 独立LLM判断（替代retry_count规则）
        [S2-T3] 三贤者并行投票用

        P2-9 修复：统一三脑签名，decision_point 改为 Optional（默认 None，向后兼容）。

        Args:
            context: 上下文字典，可包含 retry_count / user_input / step_info /
                     execution_summary 等字段
            decision_point: 决策点字符串，如 "send_email" / "execute_operation" /
                            "data_persist"（可选，默认 None）

        Returns:
            Opinion: 执行脑意见对象，brain_type 固定为 "executor"
        """
        if not self.llm_service:
            return self._express_opinion_rulebased(context, decision_point)

        try:
            opinion = self._express_opinion_with_llm(context, decision_point)
            if opinion is not None:
                return opinion
            logger.warning("LLM执行意见生成失败，降级到规则判断")
        except Exception as e:
            logger.warning("LLM执行意见异常，降级到规则判断: %s", e)

        return self._express_opinion_rulebased(context, decision_point)

    def _express_opinion_rulebased(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Opinion:
        """基于规则的降级判断（保留与原假意见逻辑的兼容性）"""
        retry_count = int(context.get("retry_count", 0))
        # P2-10 修复：提取 retry_count 假意见规则为私有方法，消除重复实现
        opinion_data = self._generate_retry_opinion(retry_count)
        opinion_type = (
            OpinionType.AGREE
            if opinion_data["opinion_type"] == "AGREE"
            else OpinionType.DISAGREE
        )
        dp_str = decision_point if decision_point is not None else "unknown"
        reasoning = f"执行重试次数: {retry_count} (决策点: {dp_str})"
        return Opinion(
            brain_type="executor",
            opinion_type=opinion_type,
            reasoning=reasoning,
            confidence=opinion_data["confidence"],
        )

    @staticmethod
    def _generate_retry_opinion(retry_count: int) -> Dict[str, Any]:
        """根据重试次数生成假意见规则数据（P2-10 去重提取）。

        被 _express_opinion_rulebased 和 task_lifecycle._build_executor_opinion
        共用，消除两处重复的 retry_count 假意见规则。

        Args:
            retry_count: 重试次数

        Returns:
            Dict[str, Any]: 包含 opinion_type (str) 和 confidence (float) 的字典
        """
        opinion_type = "AGREE" if retry_count < 2 else "DISAGREE"
        confidence = max(0.3, 1.0 - retry_count * 0.3)
        return {
            "opinion_type": opinion_type,
            "confidence": confidence,
        }

    def _express_opinion_with_llm(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Optional[Opinion]:
        """使用 LLM 进行执行可行性判断"""
        retry_count = int(context.get("retry_count", 0))
        step_info = context.get("step_info", "")
        user_input = context.get("user_input", "")
        execution_summary = context.get("execution_summary", "")

        safe_step = sanitize_for_llm(str(step_info), 300)
        safe_input = sanitize_for_llm(str(user_input), 300)
        safe_summary = sanitize_for_llm(str(execution_summary), 300)
        dp_str = decision_point if decision_point is not None else "unknown"

        prompt = (
            "你是执行脑(ExecutorBrain)，负责评估当前执行决策点的可行性。\n\n"
            f"决策点: {dp_str}\n"
            f"重试次数: {retry_count}\n"
            f"用户输入: {safe_input}\n"
            f"当前步骤: {safe_step}\n"
            f"执行摘要: {safe_summary}\n\n"
            "请判断是否同意继续执行该决策点。返回JSON格式（不要包含其他内容）:\n"
            "{\n"
            '  "opinion_type": "AGREE 或 DISAGREE 或 CONDITIONAL",\n'
            '  "reasoning": "判断理由（一句话）",\n'
            '  "confidence": 0.0-1.0的置信度\n'
            "}\n\n"
            "判断准则:\n"
            "- AGREE: 执行可行，无风险或风险可控\n"
            "- DISAGREE: 执行不可行，存在重大风险或已多次失败\n"
            "- CONDITIONAL: 需要满足特定条件才可执行"
        )

        llm_response = call_llm_service(self.llm_service, prompt)
        if not llm_response:
            return None

        data = extract_json_from_llm(llm_response)
        if not data:
            return None

        opinion_type_str = str(data.get("opinion_type", "AGREE")).upper().strip()
        opinion_type = OpinionType.AGREE
        for ot in OpinionType:
            if ot.name == opinion_type_str:
                opinion_type = ot
                break

        reasoning = str(data.get("reasoning", f"执行脑LLM判断: {dp_str}"))
        try:
            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.7))))
        except (TypeError, ValueError):
            confidence = 0.7

        return Opinion(
            brain_type="executor",
            opinion_type=opinion_type,
            reasoning=reasoning,
            confidence=confidence,
        )

    async def express_opinion_async(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Opinion:
        """异步版本（并行投票用）"""
        return await asyncio.to_thread(self.express_opinion, context, decision_point)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "executor_brain", "task_count": len(self.task_statuses)}
