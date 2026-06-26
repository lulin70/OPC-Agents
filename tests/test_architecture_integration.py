"""Integration tests for AgentLoop single-entry architecture.

Verifies that the unified AgentLoop→TaskEngineV3→TaskResult pipeline works correctly,
including the ExecutorBrain direct TaskEngineV3 integration (no TaskEngineAdapter).
"""

import asyncio
import unittest
from unittest.mock import patch

from opc_manager.task_engine_v3 import TaskEngineV3, TaskResult, TaskType
from opc_manager.agent_loop import AgentLoop
from opc_manager.executor_brain import ExecutorBrain


class TestExecutorBrainDirectIntegration(unittest.TestCase):
    """Test ExecutorBrain directly uses TaskEngineV3 (no adapter)."""

    def test_executor_brain_holds_task_engine(self):
        engine = TaskEngineV3()
        brain = ExecutorBrain(task_engine=engine)
        self.assertIs(brain.task_engine, engine)

    def test_executor_brain_default_task_engine(self):
        brain = ExecutorBrain()
        self.assertIsInstance(brain.task_engine, TaskEngineV3)

    @patch.object(TaskEngineV3, "execute")
    def test_executor_brain_delegates_to_task_engine(self, mock_execute):
        mock_execute.return_value = TaskResult(
            success=True,
            content="Generated content",
            task_type=TaskType.CONTENT_GENERATION,
        )
        brain = ExecutorBrain()
        # _execute_degraded is async, run it in an event loop
        result = asyncio.run(
            brain._execute_degraded(
                skill_id="content_generation",
                parameters={"query": "写一封邮件", "goal": "写一封邮件"},
                context=None,
            )
        )
        self.assertTrue(result.success)
        mock_execute.assert_called_once()


class TestAgentLoopReturnsTaskResult(unittest.TestCase):
    """Test AgentLoop.run() returns TaskResult instead of dict."""

    @patch.object(TaskEngineV3, "execute")
    def test_run_returns_task_result(self, mock_execute):
        mock_execute.return_value = TaskResult(
            success=True,
            content="Test content",
            task_type=TaskType.GENERAL_CHAT,
        )
        loop = AgentLoop(task_engine=TaskEngineV3())
        result = asyncio.run(loop.run("hello"))
        self.assertIsInstance(result, TaskResult)
        self.assertTrue(result.success)

    def test_run_empty_input_returns_task_result(self):
        loop = AgentLoop(task_engine=TaskEngineV3())
        result = asyncio.run(loop.run(""))
        self.assertIsInstance(result, TaskResult)
        self.assertFalse(result.success)

    def test_run_too_long_input_returns_task_result(self):
        loop = AgentLoop(task_engine=TaskEngineV3())
        result = asyncio.run(loop.run("x" * 10001))
        self.assertIsInstance(result, TaskResult)
        self.assertFalse(result.success)


class TestNoTaskEngineAdapterInPipeline(unittest.TestCase):
    """Verify TaskEngineAdapter is not in the call chain."""

    def test_agent_loop_no_adapter_import(self):
        """AgentLoop should not reference TaskEngineAdapter."""
        import inspect

        source = inspect.getsource(AgentLoop)
        self.assertNotIn("TaskEngineAdapter", source)
        self.assertNotIn("task_engine_adapter", source)

    def test_executor_brain_no_adapter_import(self):
        """ExecutorBrain should not reference TaskEngineAdapter."""
        import inspect

        source = inspect.getsource(ExecutorBrain)
        self.assertNotIn("TaskEngineAdapter", source)
        self.assertNotIn("task_engine_adapter", source)


if __name__ == "__main__":
    unittest.main()
