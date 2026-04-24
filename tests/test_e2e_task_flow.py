#!/usr/bin/env python3
import unittest
import sys
import os
import time
import json
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.three_sages import ThreeSagesManager
from opc_manager.core import OPCManager
from opc_hr.mcp_integration import MCPIntegration


class TestE2EIntentClassification(unittest.TestCase):

    @unittest.skip("需要真实LLM后端才能进行意图识别，本地环境无有效模型配置")
    def test_clarify_intent_detected(self):
        ts = ThreeSagesManager()
        prompt = (
            "判断以下用户消息的意图，只回复一个词：\n"
            "如果是闲聊、问候、提问，回复「chat」\n"
            "如果需要搜索互联网获取最新信息，回复「search」\n"
            "如果是需要执行的任务、工作安排、项目需求，丏述清晰可执行，回复「task」\n"
            "如果意图不明确、信息不足、需要追问用户才能执行，回复「clarify」\n\n"
            "用户消息：帮我做个东西\n"
        )
        response = ts.call_llm_api(prompt)
        self.assertIsNotNone(response)
        self.assertIn("clarify", response.lower())

    @unittest.skip("需要真实LLM后端才能进行意图识别，本地环境无有效模型配置")
    def test_task_intent_detected(self):
        ts = ThreeSagesManager()
        prompt = (
            "判断以下用户消息的意图，只回复一个词：\n"
            "如果是闲聊、问候、提问，回复「chat」\n"
            "如果需要搜索互联网获取最新信息，回复「search」\n"
            "如果是需要执行的任务、工作安排、项目需求，丏述清晰可执行，回复「task」\n"
            "如果意图不明确、信息不足、需要追问用户才能执行，回复「clarify」\n\n"
            "用户消息：帮我写一个Python爬虫抓取新闻标题\n"
        )
        response = ts.call_llm_api(prompt)
        self.assertIsNotNone(response)
        self.assertIn("task", response.lower())


class TestE2EThreeSagesDecision(unittest.TestCase):

    def test_structured_output_parseable(self):
        ts = ThreeSagesManager()
        result = ts._parse_structured_opinion(
            '{"internal_resources": "3 agents available", "external_relations": "none needed", '
            '"risk_assessment": "low risk", "strategy": "execute directly", '
            '"action_items": ["step1", "step2"]}',
            "TestSage"
        )
        self.assertEqual(result["internal_resources"], "3 agents available")
        self.assertEqual(result["strategy"], "execute directly")
        self.assertEqual(len(result["action_items"]), 2)

    def test_text_fallback_parseable(self):
        ts = ThreeSagesManager()
        result = ts._parse_structured_opinion(
            "内部资源评估：本地有design和engineering部门可用。\n"
            "外部关系评估：无需外部资源。\n"
            "风险评估：技术风险低。\n"
            "战略建议：建议分两步执行。\n"
            "1. 设计方案\n2. 开发实现\n",
            "TestSage"
        )
        self.assertIn("内部资源", result["internal_resources"])
        self.assertIn("外部关系", result["external_relations"])
        self.assertIn("风险", result["risk_assessment"])
        self.assertGreaterEqual(len(result["action_items"]), 1)


class TestE2ETaskDecomposition(unittest.TestCase):

    def test_decompose_without_synthesis(self):
        mgr = OPCManager()
        result = mgr.decompose_task("test task")
        self.assertIn("execution_steps", result)
        self.assertIn("monitoring_plan", result)

    def test_decompose_with_synthesis_steps(self):
        mgr = OPCManager()
        synthesis = {
            "execution_steps": [
                {"step": 1, "task": "design", "department": "design", "description": "d", "deliverable": "d.md"}
            ],
            "monitoring_plan": [{"checkpoint": "c1", "trigger": "t1"}]
        }
        result = mgr.decompose_task("test", synthesis)
        self.assertEqual(len(result["execution_steps"]), 1)
        self.assertEqual(result["execution_steps"][0]["task"], "design")

    def test_generate_plan_markdown(self):
        mgr = OPCManager()
        synthesis = {"summary": "test summary", "sages": []}
        steps = [{"step": 1, "task": "t", "department": "d", "description": "desc", "deliverable": "del"}]
        plan = mgr.generate_plan_markdown("test task", synthesis, steps, [], "task-1")
        self.assertIn("test task", plan)
        self.assertIn("task-1", plan)
        self.assertIn("test summary", plan)
        self.assertIn("| 1 |", plan)


class TestE2EConfirmPlan(unittest.TestCase):

    def test_confirm_plan_missing_returns_404(self):
        mgr = OPCManager()
        pending = getattr(mgr, '_pending_plans', {})
        result = pending.get("nonexistent-task-id")
        self.assertIsNone(result)

    def test_pending_plan_stored(self):
        mgr = OPCManager()
        if not hasattr(mgr, '_pending_plans'):
            mgr._pending_plans = {}
        mgr._pending_plans["test-123"] = {
            "message": "test",
            "execution_steps": [{"step": 1, "task": "t", "department": "d"}],
            "work_dir": "/tmp/test"
        }
        self.assertIn("test-123", mgr._pending_plans)
        del mgr._pending_plans["test-123"]


class TestE2EAgentExecution(unittest.TestCase):

    def test_submit_task_exists(self):
        mgr = OPCManager()
        self.assertTrue(hasattr(mgr.task_executor, 'submit_task'))

    def test_submit_task_returns_true(self):
        mgr = OPCManager()
        result = mgr.task_executor.submit_task(
            "test-e2e-001",
            {
                "task_name": "test task",
                "description": "test description",
                "department": "engineering",
                "assigned_agent": "backend_developer",
                "context": {
                    "user_requirement": "test requirement",
                    "sages_summary": "test summary",
                    "execution_plan": [],
                    "current_step": {"description": "test step", "deliverable": "test output"},
                    "previous_outputs": [],
                    "work_dir": "/tmp/test_e2e_workspace",
                    "step_index": 0
                }
            }
        )
        self.assertTrue(result)

    def test_task_context_has_all_fields(self):
        context = {
            "user_requirement": "req",
            "sages_summary": "summary",
            "execution_plan": [],
            "current_step": {"description": "step", "deliverable": "output"},
            "previous_outputs": [],
            "work_dir": "/tmp/test",
            "step_index": 0
        }
        required_keys = ["user_requirement", "sages_summary", "execution_plan",
                        "current_step", "previous_outputs", "work_dir", "step_index"]
        for key in required_keys:
            self.assertIn(key, context)


class TestE2ESecurityAudit(unittest.TestCase):

    def test_trusted_source_skipped(self):
        mcp = MCPIntegration()
        result = mcp._verify_resource(
            {"name": "t", "repo_full_name": "microsoft/autogen", "stars": 100,
             "forks": 50, "license": "MIT", "description": "t", "language": "Python"},
            "agent"
        )
        self.assertTrue(result["trusted"])
        self.assertEqual(result["security_score"], 1.0)

    def test_untrusted_source_scanned(self):
        mcp = MCPIntegration()
        result = mcp._verify_resource(
            {"name": "t", "repo_full_name": "unknown/newrepo", "stars": 0,
             "forks": 0, "description": "", "language": ""},
            "agent"
        )
        self.assertFalse(result["trusted"])


if __name__ == '__main__':
    unittest.main()
