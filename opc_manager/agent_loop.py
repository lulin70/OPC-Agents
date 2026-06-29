"""
执行循环 (AgentLoop) - 负责协调三贤者的完整执行流程

这是三贤者架构的核心协调器，实现 Plan→Act→Observe→Reflect 循环：
- Plan: 策略脑制定执行计划
- Act: 执行脑执行计划
- Observe: 收集执行结果
- Reflect: 反思脑评估并决定下一步

重构说明 (v0.4.0)：
AgentLoop已重构为轻量级协调器，具体职责委托给专门组件：
- StateManager: 状态管理
- AgentErrorHandler: 错误处理
- ProgressTracker: 进度跟踪
- ResultBuilder: 结果构建
- TaskOrchestrator: 任务编排

为保持向后兼容，AgentLoop保留了原有的公共接口和辅助方法。
"""

from typing import Dict, List, Optional, Any, cast
import logging
import os
import time

from .strategist_brain import StrategistBrain
from .executor_brain import ExecutorBrain
from .reflector_brain import (
    ReflectorBrain,
)
from .consensus_engine import (
    ConsensusEngine,
    Opinion,
)
from .skill_registry import SkillRegistry
from .tool_system import ToolSystem
from .session_context import SessionContextManager
from .task_engine_v3 import TaskEngineV3, TaskResult
from .correction_manager import CorrectionManager
from .agent_context import AgentContext, AgentState
from .task_lifecycle import TaskLifecycleManager, ConsensusConsultant
from .utils import EventEmitter
from .performance_monitor import get_performance_monitor
from .confirmer import Confirmer
from .progress_emitter import ProgressEmitter

# Shared constants and utilities (eliminates circular dependency)
from .constants import (
    MAX_RETRY_PER_STEP,
    MAX_CONTEXT_HISTORY,
    MAX_REFLECT_ROUNDS,
    AGENT_LOOP_TIMEOUT_SECONDS,
)
from .agent_utils import (
    context_to_dict as _context_to_dict_impl,
    extract_planned_action as _extract_planned_action_impl,
    dict_to_opinion as _dict_to_opinion_impl,
)

# 新增组件导入
from .state_manager import StateManager
from .agent_error_handler import AgentErrorHandler
from .progress_tracker import ProgressTracker
from .result_builder import ResultBuilder
from .task_orchestrator import TaskOrchestrator

logger = logging.getLogger(__name__)


class AgentLoop:
    """三贤者架构的核心协调器。

    重构后职责：
    - 作为轻量级协调器，委托具体职责给专门组件
    - 保持对外接口不变，确保向后兼容
    - 管理组件生命周期和依赖注入

    委托的职责：
    - 状态管理 → StateManager
    - 错误处理 → AgentErrorHandler
    - 进度跟踪 → ProgressTracker
    - 结果构建 → ResultBuilder
    - 任务编排 → TaskOrchestrator
    """

    def __init__(
        self,
        strategist_brain: Optional[StrategistBrain] = None,
        executor_brain: Optional[ExecutorBrain] = None,
        reflector_brain: Optional[ReflectorBrain] = None,
        consensus_engine: Optional[ConsensusEngine] = None,
        skill_registry: Optional[SkillRegistry] = None,
        tool_system: Optional[ToolSystem] = None,
        session_manager: Optional[SessionContextManager] = None,
        task_engine=None,
        llm_service=None,
        max_reflect_rounds: int = MAX_REFLECT_ROUNDS,
        max_retry_per_step: int = MAX_RETRY_PER_STEP,
    ):
        # 初始化核心依赖
        self.task_engine = task_engine or TaskEngineV3()
        self.llm_service = llm_service
        # 先创建 skill_registry，再注入到 strategist_brain，
        # 使 LLM 规划能够动态发现注册表中的全部技能
        self.skill_registry = skill_registry or SkillRegistry()
        self.strategist_brain = strategist_brain or StrategistBrain(
            llm_service=llm_service, skill_registry=self.skill_registry
        )
        self.executor_brain = executor_brain or ExecutorBrain(
            skill_registry=self.skill_registry,
            task_engine=self.task_engine,
            llm_service=llm_service,
        )
        self.reflector_brain = reflector_brain or ReflectorBrain(
            llm_service=llm_service
        )
        self.consensus_engine = consensus_engine or ConsensusEngine()
        self.tool_system = tool_system or ToolSystem()
        self.session_manager = session_manager or SessionContextManager()
        self.event_emitter = EventEmitter()
        self.confirmer = Confirmer()
        self.progress = ProgressEmitter()

        # 初始化专门组件（重构新增）
        self._state_manager = StateManager(max_context_history=MAX_CONTEXT_HISTORY)
        self._error_handler = AgentErrorHandler()
        self._progress_tracker = ProgressTracker(self.progress)
        self._result_builder = ResultBuilder(self.session_manager)

        # 修正管理器和生命周期管理器（共享contexts）
        self._correction_manager = CorrectionManager(
            skill_registry=self.skill_registry, executor_brain=self.executor_brain
        )
        self._consensus_consultant = ConsensusConsultant(
            self.strategist_brain,
            self.reflector_brain,
            self.consensus_engine,
            executor_brain=self.executor_brain,
        )

        # 任务编排器
        self._orchestrator = TaskOrchestrator(
            strategist_brain=self.strategist_brain,
            executor_brain=self.executor_brain,
            reflector_brain=self.reflector_brain,
            consensus_consultant=self._consensus_consultant,
            correction_manager=self._correction_manager,
            result_builder=self._result_builder,
            progress_tracker=self._progress_tracker,
            max_reflect_rounds=max_reflect_rounds,
            max_retry_per_step=max_retry_per_step,
        )

        # 保持向后兼容：contexts属性指向StateManager的contexts
        self.contexts = self._state_manager.contexts
        # TaskLifecycleManager 期望 dict，但 StateManager.contexts 返回 BoundedDict
        # BoundedDict 实现 dict-like 接口，运行时兼容；使用 cast 消除类型差异
        self._lifecycle = TaskLifecycleManager(
            cast(dict, self.contexts), self.executor_brain
        )

        self.max_reflect_rounds = max_reflect_rounds
        self.max_retry_per_step = max_retry_per_step

    async def run(
        self,
        user_input: str,
        context: Optional[Dict] = None,
        session_id: Optional[str] = None,
    ) -> TaskResult:
        """执行用户任务（重构后委托给专门组件）。"""
        logger.info("AgentLoop 开始执行: %s...", user_input[:50])

        # 1. 输入验证（委托给AgentErrorHandler）
        validation_result = self._error_handler.validate_input(user_input)
        if not validation_result.is_valid:
            return self._error_handler.build_validation_error_result(
                validation_result.error or ""
            )

        _perf_start = time.time()

        # 2. 创建上下文（委托给StateManager）
        agent_context = self._state_manager.create_context(user_input, session_id)

        # 3. 意图分类和路由（委托给TaskOrchestrator）
        route_decision = self._orchestrator.determine_route(user_input)

        if route_decision.is_greeting:
            logger.info("[S2-T6] GREETING 路由，直接响应")
            return self._result_builder.build_greeting_result(
                route_decision.response, route_decision.confidence
            )

        if route_decision.is_simple:
            logger.info("[S2-T6] SIMPLE 路由，跳过关键决策点共识")
            agent_context.metadata["route_category"] = "simple"

        # 4. 准备对话历史
        conversation_history = []
        if session_id:
            history_text = self.session_manager.get_context_for_llm(max_turns=5)
            if history_text:
                conversation_history = [{"role": "history", "content": history_text}]

        try:
            # 5. 执行规划阶段
            self._state_manager.set_state(agent_context, AgentState.PLANNING)
            await self._orchestrator.execute_plan_phase(
                agent_context, conversation_history
            )

            # 6. 检查取消请求
            if agent_context.cancel_requested:
                self._state_manager.set_state(agent_context, AgentState.CANCELLED)
                self._progress_tracker.emit_cancelled(agent_context.task_id)
                return self._result_builder.build_result(agent_context, cancelled=True)

            # 7. 用户确认检查
            confirm_result = await self._check_confirmation(agent_context, user_input)
            if confirm_result is not None:
                return confirm_result

            # 8. 检查是否跳过反思
            skip_reflect = os.environ.get("OPC_SKIP_REFLECT", "false").lower() == "true"
            if skip_reflect:
                return await self._execute_skip_reflect(agent_context, _perf_start)

            # 9. 执行反思循环
            deadline = time.time() + AGENT_LOOP_TIMEOUT_SECONDS
            loop_result = await self._orchestrator.run_reflect_loop(
                agent_context, deadline=deadline
            )

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    return self._result_builder.build_result(
                        agent_context, cancelled=True
                    )
                return self._result_builder.build_loop_error_result(loop_result)

            # 10. 完成处理
            self._state_manager.set_state(agent_context, AgentState.COMPLETED)
            logger.info("AgentLoop 执行完成: %s", agent_context.task_id)

            self.event_emitter.emit(
                event_type="task_completed",
                step_id="final",
                step_name="任务完成",
                status="completed",
            )

            self._progress_tracker.emit_complete(agent_context.task_id)

            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=True)
            return self._result_builder.build_result(agent_context)

        except Exception as e:
            self._state_manager.set_state(agent_context, AgentState.FAILED)
            logger.error("AgentLoop 执行失败: %s", str(e))

            self._progress_tracker.emit_error(
                agent_context.task_id, f"执行失败: {str(e)}", {"error": str(e)}
            )

            duration_ms = (time.time() - _perf_start) * 1000
            get_performance_monitor().record("agent_loop", duration_ms, success=False)
            return self._error_handler.handle_execution_exception(
                e, agent_context.task_id
            )

    async def _check_confirmation(
        self, agent_context: AgentContext, user_input: str
    ) -> Optional[TaskResult]:
        """检查用户确认（如果需要）。

        Returns:
            TaskResult如果需要返回（确认失败），None如果继续执行
        """
        intent_type = (
            cast(Any, agent_context.intent).type.name
            if agent_context.intent
            else "UNKNOWN"
        )
        goal = cast(Any, agent_context.intent).goal if agent_context.intent else ""
        confidence = (
            getattr(agent_context.intent, "confidence", 0.85)
            if agent_context.intent
            else 0.85
        )
        confirm_result = await self.confirmer.check_confirmation(
            session_id=agent_context.session_id or "",
            intent_type=intent_type,
            goal=goal,
            confidence=confidence,
            params={"user_input": user_input[:200]},
        )
        if not confirm_result.confirmed and confirm_result.method != "no_callback":
            self._state_manager.set_state(agent_context, AgentState.CONFIRMATION_NEEDED)
            confirmation_message = (
                confirm_result.message if hasattr(confirm_result, "message") else ""
            )
            return self._error_handler.build_confirmation_needed_result(
                confirmation_message
            )
        return None

    async def _execute_skip_reflect(
        self, agent_context: AgentContext, _perf_start: float
    ) -> TaskResult:
        """执行跳过反思的快速路径。"""
        self._state_manager.set_state(agent_context, AgentState.EXECUTING)
        await self._orchestrator.execute_execute_phase(agent_context)

        has_results = bool(agent_context.execution_results)
        all_failed = has_results and all(
            not r.get("success", False) for r in agent_context.execution_results
        )

        if not has_results or all_failed:
            self._state_manager.set_state(agent_context, AgentState.FAILED)
            self._progress_tracker.emit_error(agent_context.task_id, "执行步骤全部失败")
            return self._result_builder.build_result(agent_context)

        self._state_manager.set_state(agent_context, AgentState.COMPLETED)
        self._progress_tracker.emit_complete(agent_context.task_id)
        return self._result_builder.build_result(agent_context)

    # =========================================================================
    # 向后兼容方法：保留原有的辅助方法，供TaskOrchestrator和其他组件调用
    # 这些方法委托给TaskOrchestrator，确保现有测试和调用方继续工作
    # =========================================================================

    def _is_critical_decision_point(self, context, step=None) -> bool:
        """判断当前是否为关键决策点 [向后兼容委托]"""
        return self._orchestrator._is_critical_decision_point(context, step)

    async def _parallel_consensus(self, context, decision_point: str, step=None):
        """三贤者并行投票决策 [向后兼容委托]"""
        return await self._orchestrator._parallel_consensus(
            context, decision_point, step
        )

    async def _serial_consensus_fallback(self, context, decision_point: str, step=None):
        """串行降级路径 [向后兼容委托]"""
        return await self._orchestrator._serial_consensus_fallback(
            context, decision_point, step
        )

    async def _strategist_opinion_async(self, context_dict, decision_point):
        """策略脑异步意见 [向后兼容委托]"""
        return await self._orchestrator._strategist_opinion_async(
            context_dict, decision_point
        )

    def _enrich_step_parameters(
        self, params: Dict, execution_results: List[Dict]
    ) -> Dict:
        """丰富步骤参数 [向后兼容委托]"""
        return self._orchestrator._enrich_step_parameters(params, execution_results)

    async def _execute_step_with_retry(
        self, context: AgentContext, step, enriched_params: Optional[Dict] = None
    ):
        """带重试的步骤执行 [向后兼容委托]"""
        return await self._orchestrator._execute_step_with_retry(
            context, step, enriched_params if enriched_params is not None else {}
        )

    def _generate_greeting_response(self, user_input: str) -> str:
        """生成问候响应 [向后兼容委托]"""
        return self._orchestrator._generate_greeting_response(user_input)

    def _build_overall_result(self, context: AgentContext) -> Dict[str, Any]:
        """构建总体结果 [向后兼容委托]"""
        return self._result_builder.build_overall_result(context)

    def _build_result(
        self, context: AgentContext, cancelled: bool = False
    ) -> TaskResult:
        """构建结果 [向后兼容委托]"""
        return self._result_builder.build_result(context, cancelled)

    @staticmethod
    def _context_to_dict(context) -> Dict[str, Any]:
        """将 AgentContext 转换为 dict（用于三贤者投票）[S2-T2]"""
        return _context_to_dict_impl(context)

    @staticmethod
    def _extract_planned_action(context, step=None) -> Dict[str, Any]:
        """提取计划行动信息（用于 ReflectorBrain 预判）[S2-T2]"""
        return _extract_planned_action_impl(context, step)

    @staticmethod
    def _dict_to_opinion(result: Dict, brain_type: str) -> Opinion:
        """将 Brain.express_opinion 返回的 Dict 转换为 Opinion 对象 [S2-T2]"""
        return _dict_to_opinion_impl(result, brain_type)

    # =========================================================================
    # 生命周期管理方法（委托给TaskLifecycleManager）
    # =========================================================================

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._lifecycle.get_task_status(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        return await self._lifecycle.cancel_task(task_id)

    async def pause_task(self, task_id: str) -> bool:
        return await self._lifecycle.pause_task(task_id)

    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        result = await self._lifecycle.resume_task(task_id)
        if not result.get("success"):
            return result

        # 如果恢复成功，继续反思循环
        context = self.contexts.get(task_id)
        if not context:
            return result

        result.pop("resume_step", context.current_step)
        deadline = time.time() + AGENT_LOOP_TIMEOUT_SECONDS

        try:
            loop_result = await self._orchestrator.run_reflect_loop(
                context, deadline=deadline
            )

            if loop_result is not None:
                if loop_result.get("cancelled"):
                    # resume_task 返回类型为 Dict[str, Any]，但 build_result 返回 TaskResult；
                    # 失败路径返回 dict，成功路径返回 TaskResult，保持现状以维持向后兼容
                    return self._result_builder.build_result(context, cancelled=True)  # type: ignore[return-value]
                return self._result_builder.build_loop_error_result(loop_result)  # type: ignore[return-value]

            self._state_manager.set_state(context, AgentState.COMPLETED)
            return self._result_builder.build_result(context)  # type: ignore[return-value]

        except Exception as e:
            self._state_manager.set_state(context, AgentState.FAILED)
            logger.error("恢复任务执行失败: %s", str(e))
            return {"success": False, "task_id": task_id, "error": str(e)}

    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._lifecycle.list_tasks()

    def to_dict(self) -> Dict[str, Any]:
        return self._lifecycle.to_dict()
