"""
新组件单元测试 — AgentLoop重构后的专门组件

覆盖：
- StateManager: 状态管理
- AgentErrorHandler: 错误处理
- ProgressTracker: 进度跟踪
- ResultBuilder: 结果构建
- TaskOrchestrator: 任务编排（路由决策部分）
"""

import asyncio
import unittest
from unittest.mock import Mock, MagicMock, patch

from opc_manager.state_manager import StateManager
from opc_manager.error_handler_component import AgentErrorHandler, ValidationResult
from opc_manager.progress_tracker import ProgressTracker
from opc_manager.result_builder import ResultBuilder
from opc_manager.task_orchestrator import TaskOrchestrator, RouteDecision
from opc_manager.agent_context import AgentContext, AgentState
from opc_manager.task_engine_v3 import TaskType, TaskResult
from opc_manager.progress_emitter import ProgressEmitter, EventType


class TestStateManager(unittest.TestCase):
    """StateManager状态管理器测试"""

    def setUp(self):
        """每个测试前创建新的StateManager实例"""
        self.manager = StateManager(max_context_history=10)

    def test_create_context_generates_task_id(self):
        """测试创建上下文时生成task_id"""
        context = self.manager.create_context("test input")

        self.assertIsInstance(context, AgentContext)
        self.assertTrue(context.task_id.startswith("agent_task_"))
        self.assertEqual(context.user_input, "test input")
        self.assertIsNotNone(context.session_id)

    def test_create_context_with_session_id(self):
        """测试使用指定session_id创建上下文"""
        context = self.manager.create_context("test", session_id="custom-session")

        self.assertEqual(context.session_id, "custom-session")

    def test_create_context_strips_input(self):
        """测试输入文本被strip处理"""
        context = self.manager.create_context("  test input  ")

        self.assertEqual(context.user_input, "test input")

    def test_set_state_records_history(self):
        """测试状态变更被记录到历史"""
        context = self.manager.create_context("test")
        self.manager.set_state(context, AgentState.PLANNING)
        self.manager.set_state(context, AgentState.EXECUTING)

        history = self.manager.get_state_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["old_state"], AgentState.IDLE.value)
        self.assertEqual(history[0]["new_state"], AgentState.PLANNING.value)
        self.assertEqual(history[1]["old_state"], AgentState.PLANNING.value)
        self.assertEqual(history[1]["new_state"], AgentState.EXECUTING.value)

    def test_get_context_returns_none_for_unknown(self):
        """测试获取不存在的上下文返回None"""
        result = self.manager.get_context("nonexistent")
        self.assertIsNone(result)

    def test_get_state_returns_none_for_unknown(self):
        """测试获取不存在的状态返回None"""
        result = self.manager.get_state("nonexistent")
        self.assertIsNone(result)

    def test_get_state_history_filtered_by_task_id(self):
        """测试按task_id过滤状态历史"""
        context1 = self.manager.create_context("test1")
        context2 = self.manager.create_context("test2")

        self.manager.set_state(context1, AgentState.PLANNING)
        self.manager.set_state(context2, AgentState.EXECUTING)

        history1 = self.manager.get_state_history(context1.task_id)
        history2 = self.manager.get_state_history(context2.task_id)

        self.assertEqual(len(history1), 1)
        self.assertEqual(history1[0]["task_id"], context1.task_id)
        self.assertEqual(len(history2), 1)
        self.assertEqual(history2[0]["task_id"], context2.task_id)

    def test_state_listener_notification(self):
        """测试状态监听器被通知"""
        listener = Mock()
        self.manager.add_state_listener(listener)

        context = self.manager.create_context("test")
        self.manager.set_state(context, AgentState.PLANNING)

        listener.on_state_changed.assert_called_once_with(
            context.task_id, AgentState.IDLE, AgentState.PLANNING
        )

    def test_remove_state_listener(self):
        """测试移除状态监听器"""
        listener = Mock()
        self.manager.add_state_listener(listener)
        self.manager.remove_state_listener(listener)

        context = self.manager.create_context("test")
        self.manager.set_state(context, AgentState.PLANNING)

        listener.on_state_changed.assert_not_called()

    def test_contexts_property_shares_storage(self):
        """测试contexts属性共享存储"""
        context = self.manager.create_context("test")
        self.assertIn(context.task_id, self.manager.contexts)


class TestAgentErrorHandler(unittest.TestCase):
    """AgentErrorHandler错误处理器测试"""

    def test_validate_input_valid(self):
        """测试有效输入验证"""
        result = AgentErrorHandler.validate_input("hello world")
        self.assertTrue(result.is_valid)
        self.assertIsNone(result.error)

    def test_validate_input_empty(self):
        """测试空输入验证"""
        result = AgentErrorHandler.validate_input("")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "用户输入不能为空")

    def test_validate_input_whitespace_only(self):
        """测试纯空白输入验证"""
        result = AgentErrorHandler.validate_input("   ")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "用户输入不能为空")

    def test_validate_input_too_long(self):
        """测试超长输入验证"""
        long_input = "a" * 10001
        result = AgentErrorHandler.validate_input(long_input)
        self.assertFalse(result.is_valid)
        self.assertIn("超过最大长度限制", result.error)

    def test_build_error_result(self):
        """测试构建错误结果"""
        result = AgentErrorHandler.build_error_result("test error")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "test error")
        self.assertEqual(result.task_type, TaskType.GENERAL_CHAT)

    def test_build_validation_error_result(self):
        """测试构建验证错误结果"""
        result = AgentErrorHandler.build_validation_error_result("validation failed")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "validation failed")
        self.assertEqual(result.content, "")

    def test_build_confirmation_needed_result(self):
        """测试构建需要确认的结果"""
        result = AgentErrorHandler.build_confirmation_needed_result("please confirm")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "需要用户确认后才能执行")
        self.assertTrue(result.metadata["needs_confirmation"])
        self.assertEqual(result.metadata["confirmation_message"], "please confirm")

    def test_handle_execution_exception(self):
        """测试处理执行异常"""
        error = ValueError("test exception")
        result = AgentErrorHandler.handle_execution_exception(error, "task_123")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "test exception")


class TestProgressTracker(unittest.TestCase):
    """ProgressTracker进度跟踪器测试"""

    def setUp(self):
        self.emitter = Mock(spec=ProgressEmitter)
        self.tracker = ProgressTracker(self.emitter)

    def test_emit_plan_start(self):
        """测试发射规划开始事件"""
        self.tracker.emit_plan_start("session_1")

        self.emitter.emit.assert_called_once()
        event = self.emitter.emit.call_args[0][0]
        self.assertEqual(event.event_type, EventType.PLAN_START)
        self.assertEqual(event.session_id, "session_1")

    def test_emit_complete(self):
        """测试发射完成事件"""
        self.tracker.emit_complete("session_1")

        self.emitter.emit.assert_called_once()
        event = self.emitter.emit.call_args[0][0]
        self.assertEqual(event.event_type, EventType.COMPLETE)
        self.assertEqual(event.progress_pct, 100)

    def test_emit_error_with_detail(self):
        """测试发射错误事件带详情"""
        self.tracker.emit_error("session_1", "error msg", {"code": 500})

        self.emitter.emit.assert_called_once()
        event = self.emitter.emit.call_args[0][0]
        self.assertEqual(event.event_type, EventType.ERROR)
        self.assertEqual(event.detail, {"code": 500})

    def test_emit_with_none_emitter(self):
        """测试emitter为None时不报错"""
        tracker = ProgressTracker(None)
        # 应该静默处理，不抛异常
        tracker.emit_plan_start("session_1")
        tracker.emit_complete("session_1")
        tracker.emit_error("session_1", "error")

    def test_emitter_property(self):
        """测试emitter属性"""
        self.assertEqual(self.tracker.emitter, self.emitter)


class TestResultBuilder(unittest.TestCase):
    """ResultBuilder结果构建器测试"""

    def setUp(self):
        self.session_manager = Mock()
        self.builder = ResultBuilder(self.session_manager)

    def test_build_result_cancelled(self):
        """测试构建取消结果"""
        context = AgentContext(task_id="test", user_input="test")
        result = self.builder.build_result(context, cancelled=True)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "任务已取消")

    def test_build_result_empty_results(self):
        """测试构建空结果"""
        context = AgentContext(task_id="test", user_input="test")
        result = self.builder.build_result(context)

        self.assertTrue(result.success)
        self.assertEqual(result.content, "已收到您的消息，我会尽力帮助您。")

    def test_build_result_with_data(self):
        """测试构建带数据的结果"""
        context = AgentContext(task_id="test", user_input="test")
        context.execution_results = [
            {
                "success": True,
                "data": {"content": "test content", "sources": ["src1"]},
                "execution_time": 1.5,
            }
        ]

        result = self.builder.build_result(context)

        self.assertTrue(result.success)
        self.assertEqual(result.content, "test content")
        self.assertEqual(result.sources, ["src1"])
        self.assertEqual(result.execution_time_ms, 1500)

    def test_build_result_with_failed_step(self):
        """测试构建有失败步骤的结果"""
        context = AgentContext(task_id="test", user_input="test")
        context.execution_results = [
            {"success": True, "data": {"content": "ok"}, "execution_time": 1.0},
            {"success": False, "data": None, "error": "failed", "execution_time": 0.5},
        ]

        result = self.builder.build_result(context)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "执行失败")

    def test_build_greeting_result(self):
        """测试构建问候结果"""
        result = self.builder.build_greeting_result("hello!", 0.95)

        self.assertTrue(result.success)
        self.assertEqual(result.content, "hello!")
        self.assertEqual(result.metadata["route"], "greeting")
        self.assertEqual(result.metadata["confidence"], 0.95)

    def test_build_loop_error_result(self):
        """测试构建循环错误结果"""
        loop_result = {"success": False, "error": "loop error"}
        result = self.builder.build_loop_error_result(loop_result)

        self.assertFalse(result.success)
        self.assertEqual(result.content, "loop error")
        self.assertEqual(result.error, "loop error")

    def test_build_overall_result(self):
        """测试构建总体结果摘要"""
        context = AgentContext(task_id="test", user_input="test")
        context.execution_results = [
            {"success": True, "data": {}, "execution_time": 1.0},
            {"success": False, "data": None, "execution_time": 0.5},
        ]

        overall = self.builder.build_overall_result(context)

        self.assertFalse(overall["success"])
        self.assertEqual(overall["data"]["total_steps"], 2)
        self.assertEqual(overall["data"]["completed_steps"], 1)
        self.assertEqual(overall["data"]["total_time"], 1.5)

    def test_record_session_turn_called(self):
        """测试会话历史记录被调用"""
        context = AgentContext(
            task_id="test", user_input="test", session_id="session_1"
        )
        context.execution_results = [
            {"success": True, "data": {"content": "response"}, "execution_time": 1.0}
        ]

        self.builder.build_result(context)

        self.session_manager.add_turn.assert_called_once()

    def test_record_session_turn_not_called_without_session(self):
        """测试无session_id时不记录会话历史"""
        context = AgentContext(task_id="test", user_input="test")
        context.execution_results = [
            {"success": True, "data": {"content": "response"}, "execution_time": 1.0}
        ]

        self.builder.build_result(context)

        self.session_manager.add_turn.assert_not_called()


class TestTaskOrchestratorRouting(unittest.TestCase):
    """TaskOrchestrator路由决策测试"""

    def setUp(self):
        """构建带mock依赖的TaskOrchestrator"""
        self.strategist = Mock()
        self.executor = Mock()
        self.reflector = Mock()
        self.consensus_consultant = Mock()
        self.correction_manager = Mock()
        self.result_builder = Mock(spec=ResultBuilder)
        self.progress_tracker = Mock(spec=ProgressTracker)

        self.orchestrator = TaskOrchestrator(
            strategist_brain=self.strategist,
            executor_brain=self.executor,
            reflector_brain=self.reflector,
            consensus_consultant=self.consensus_consultant,
            correction_manager=self.correction_manager,
            result_builder=self.result_builder,
            progress_tracker=self.progress_tracker,
        )

    def test_determine_route_greeting(self):
        """测试问候路由"""
        decision = self.orchestrator.determine_route("你好")

        self.assertTrue(decision.is_greeting)
        self.assertFalse(decision.is_simple)
        self.assertIn("OPC-Agents", decision.response)

    def test_determine_route_simple(self):
        """测试简单查询路由"""
        decision = self.orchestrator.determine_route("查看本月支出")

        self.assertFalse(decision.is_greeting)
        self.assertTrue(decision.is_simple)

    def test_determine_route_complex(self):
        """测试复杂任务路由"""
        decision = self.orchestrator.determine_route("发送邮件给张总")

        self.assertFalse(decision.is_greeting)
        self.assertFalse(decision.is_simple)

    def test_generate_greeting_response_hello(self):
        """测试问候响应生成 - 你好"""
        response = self.orchestrator._generate_greeting_response("你好")
        self.assertIn("OPC-Agents", response)

    def test_generate_greeting_response_thanks(self):
        """测试问候响应生成 - 谢谢"""
        response = self.orchestrator._generate_greeting_response("谢谢")
        self.assertIn("不客气", response)

    def test_generate_greeting_response_bye(self):
        """测试问候响应生成 - 再见"""
        response = self.orchestrator._generate_greeting_response("再见")
        self.assertIn("再见", response)

    def test_generate_greeting_response_help(self):
        """测试问候响应生成 - 帮助"""
        response = self.orchestrator._generate_greeting_response("帮助")
        self.assertIn("发送邮件", response)

    def test_generate_greeting_response_default(self):
        """测试问候响应生成 - 默认（无关键词匹配）"""
        response = self.orchestrator._generate_greeting_response("xyz123")
        self.assertEqual(response, "你好，有什么可以帮你的吗？")


class TestRouteDecision(unittest.TestCase):
    """RouteDecision数据类测试"""

    def test_default_values(self):
        """测试默认值"""
        decision = RouteDecision()
        self.assertFalse(decision.is_greeting)
        self.assertFalse(decision.is_simple)
        self.assertEqual(decision.response, "")
        self.assertEqual(decision.confidence, 0.0)

    def test_greeting_decision(self):
        """测试问候决策"""
        decision = RouteDecision(
            is_greeting=True, response="hello", confidence=0.95
        )
        self.assertTrue(decision.is_greeting)
        self.assertEqual(decision.response, "hello")
        self.assertEqual(decision.confidence, 0.95)


if __name__ == "__main__":
    unittest.main()
