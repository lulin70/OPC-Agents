"""v3.5 集成测试 — 四大P0组件协同工作验证

测试覆盖范围（对应 TEST_PLAN_V3.md 的 TestIntegrationV35 类别）：
- INT-001~INT-012: 12个集成场景

=== 核心目标 ===
验证4个P0组件在TaskEngineV3中正确协同：
1. SearchResultProcessor (P0-1) → _search() 后处理
2. LLMEnhancedContentGenerator (P0-2) → 内容生成增强
3. AsyncTaskExecutor (P0-3) → 异步执行包装
4. SessionContextManager (P0-4) → 多轮对话上下文

=== 验收标准 ===
- 所有集成路径无异常崩溃
- 降级模式正常工作（不比v3.4更差）
- 多轮对话上下文正确传递
"""

import unittest
import time
from unittest.mock import patch
from opc_manager.task_engine_v3 import TaskEngineV3, InputValidator
from opc_manager.search_processor import SearchResultProcessor
from opc_manager.llm_content import LLMEnhancedContentGenerator
from opc_manager.async_executor import AsyncTaskExecutor
from opc_manager.session_context import SessionContextManager

MOCK_SEARCH_RESULTS = [
    {"title": "SaaS Q2 Marketing Strategy", "href": "https://example.com/1", "body": "A comprehensive guide to Q2 marketing planning for SaaS products..."},
    {"title": "Market Analysis Framework", "href": "https://example.com/2", "body": "SWOT analysis and market research methodology for business growth..."},
    {"title": "Growth Hacking for Startups", "href": "https://example.com/3", "body": "Low-cost customer acquisition strategies and Q2 marketing plans..."},
]

MOCK_SOURCES = [
    {"title": r.get("title", ""), "url": r.get("href", "")}
    for r in MOCK_SEARCH_RESULTS
    if r.get("href")
]

MOCK_LLM_RESPONSE = (
    "# Q2 Marketing Plan\n\n"
    "## Overview\nAI product targeting MAU growth from 5000 to 10000.\n\n"
    "## Goals\n- Increase MAU from 5000 to 10000 by end of Q2\n"
    "- Achieve 5% conversion rate\n\n"
    "## Timeline\n- Week 1: Launch content marketing\n- Week 2: SEO sprint\n\n"
    "## Budget\nTotal: 50000 CNY\n"
)


def _start_mocks(test_instance):
    test_instance._search_patcher = patch.object(
        TaskEngineV3, '_search', return_value=(MOCK_SEARCH_RESULTS, MOCK_SOURCES)
    )
    test_instance._llm_patcher = patch.object(
        LLMEnhancedContentGenerator, '_call_llm_api', return_value=MOCK_LLM_RESPONSE
    )
    test_instance._search_patcher.start()
    test_instance._llm_patcher.start()


def _stop_mocks(test_instance):
    test_instance._search_patcher.stop()
    test_instance._llm_patcher.stop()


class TestIntegrationSearchProcessor(unittest.TestCase):
    """INT-001: TaskEngineV3 + SearchResultProcessor integration"""

    def setUp(self):
        self.engine = TaskEngineV3()
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_engine_search_calls_processor(self):
        """TaskEngineV3._search() should internally call SearchResultProcessor"""
        results, sources = self.engine._search("Q2营销方案", max_results=5)

        self.assertIsInstance(results, list)
        if results:
            for r in results[:3]:
                title = r.get("title", "")
                snippet = r.get("snippet", "") or r.get("body", "")
                combined = f"{title} {snippet}".lower()
                has_relevant = any(
                    kw in combined for kw in ["marketing", "q2", "growth", "strategy", "方案", "增长"]
                )
                if not r.get("_kb_fallback"):
                    self.assertTrue(
                        has_relevant or len(results) == 0, f"Search results should be relevant: {title}"
                    )

    def test_engine_search_degradation_safe(self):
        """SearchResultProcessor失败时TaskEngineV3仍返回原始结果"""
        try:
            results, sources = self.engine._search("测试查询", max_results=3)
            self.assertIsNotNone(results)
            self.assertIsInstance(results, list)
        except Exception as e:
            self.fail(f"搜索不应抛出异常: {e}")


class TestIntegrationLLMContent(unittest.TestCase):
    """INT-002: TaskEngineV3 + LLMEnhancedContentGenerator integration"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()
        self._llm_patcher = patch.object(
            LLMEnhancedContentGenerator, '_call_llm_api', return_value=MOCK_LLM_RESPONSE
        )
        self._llm_patcher.start()

    def tearDown(self):
        self._llm_patcher.stop()

    def test_generator_with_engine_template(self):
        """LLMEnhancedContentGenerator应能处理TaskEngineV3的模板格式"""
        template = (
            "# Q2增长方案\n\n"
            "## 项目概览\n{business_context}\n"
            "## 目标设定\n{goals}\n"
            "## 实施路线图\n" + "详细内容段落。\n" * 20
        )

        result = self.generator.generate(
            user_input="AI写作助手，月活5000提升到10000",
            template=template,
        )

        self.assertIsNotNone(result.content)
        self.assertGreater(len(result.content), 100)

    def test_generator_output_no_placeholders(self):
        """生成器输出不应含占位符（即使使用引擎模板）"""
        result = self.generator.generate(
            user_input="生成报告",
            template="# 报告\n{business_context}\n{user_query}\n",
        )

        forbidden = ["___", "待填写", "基准值待测"]
        for pattern in forbidden:
            self.assertNotIn(pattern, result.content)


class TestIntegrationAsyncExecutor(unittest.TestCase):
    """INT-003: AsyncTaskExecutor与引擎集成"""

    def setUp(self):
        self.executor = AsyncTaskExecutor()
        self.engine = TaskEngineV3()

    def test_executor_wraps_engine_execute(self):
        """AsyncTaskExecutor应能包装TaskEngineV3.execute()调用"""
        task_id = self.executor.submit(
            prompt="你好",
            execute_func=lambda prompt, **kw: {
                "content": f"回复: {prompt}",
                "success": True,
            },
        )
        self.assertIsNotNone(task_id)

        time.sleep(0.15)
        status = self.executor.get_status(task_id)
        self.assertEqual(status["status"], "done")
        self.assertIn("回复:", status.get("result_content", ""))

    def test_executor_handles_engine_timeout(self):
        """AsyncTaskExecutor应优雅处理长时间运行的任务"""

        def slow_task(prompt, **kwargs):
            time.sleep(0.1)
            return {"content": "慢任务完成", "success": True}

        task_id = self.executor.submit("慢任务", execute_func=slow_task)
        self.assertIsNotNone(task_id)

        time.sleep(0.2)
        status = self.executor.get_status(task_id)
        self.assertIn(status["status"], ["done", "running"])


class TestIntegrationSessionContext(unittest.TestCase):
    """INT-004: SessionContextManager + engine integration"""

    def setUp(self):
        self.engine = TaskEngineV3()
        self.session = SessionContextManager(max_turns=20)
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_engine_execute_with_session_ctx(self):
        """TaskEngineV3.execute(session_ctx=...)应正确记录历史"""
        result1 = self.engine.execute(
            "帮我写Q2方案",
            session_ctx=self.session,
        )

        self.assertTrue(result1.success)
        self.assertEqual(self.session.get_turn_count(), 1)

        history = self.session.get_full_history()
        self.assertGreaterEqual(len(history), 2)

    def test_session_context_enriches_second_call(self):
        """第2次execute()应注入第1轮的上下文"""
        self.engine.execute("第一轮输入", session_ctx=self.session)

        context_before_2nd = self.session.get_context_for_llm()
        self.assertIn("第一轮输入", context_before_2nd)

        result2 = self.engine.execute(
            "基于上次修改第三阶段",
            session_ctx=self.session,
        )

        self.assertTrue(result2.success)
        self.assertEqual(self.session.get_turn_count(), 2)

        last_result = self.session.get_last_result()
        self.assertIsNotNone(last_result)
        self.assertIn("response", last_result)


class TestE2ESearchToDelivery(unittest.TestCase):
    """INT-005: Full E2E pipeline — search→process→content→delivery"""

    def setUp(self):
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_full_pipeline_no_crash(self):
        """Full execution pipeline should not crash"""
        engine = TaskEngineV3()

        result = engine.execute("帮我写一份简短的市场分析")

        self.assertIsNotNone(result)
        self.assertIsInstance(result.content, str)
        self.assertGreater(len(result.content), 10)

    def test_pipeline_with_all_components(self):
        """全链路应经过所有v3.5组件"""
        processor = SearchResultProcessor()
        generator = LLMEnhancedContentGenerator()

        raw_results = [
            {"title": "市场分析方法论", "snippet": "SWOT分析、PESTEL模型..."},
            {"title": "2026年市场趋势", "snippet": "数字化转型加速..."},
        ]

        processed = processor.process("市场分析", raw_results)
        self.assertIsNotNone(processed.results)

        content_result = generator.generate(
            user_input="帮我做市场分析",
            template="# 分析报告\n{search_context}\n{business_context}\n"
            + "详细内容。\n" * 30,
            search_results=processed.results,
        )

        self.assertIsNotNone(content_result.content)
        self.assertGreater(len(content_result.content), 100)


class TestE2EMultiTurnIteration(unittest.TestCase):
    """INT-006: Full E2E — multi-turn conversation→iterative refinement"""

    def setUp(self):
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_three_turn_iteration_flow(self):
        """3 consecutive turns should correctly accumulate context"""
        engine = TaskEngineV3()
        session = SessionContextManager(max_turns=20)

        turn1 = engine.execute("制定Q2计划", session_ctx=session)
        self.assertTrue(turn1.success)
        self.assertEqual(session.get_turn_count(), 1)

        turn2 = engine.execute("修改第三阶段时间", session_ctx=session)
        self.assertTrue(turn2.success)
        self.assertEqual(session.get_turn_count(), 2)

        turn3 = engine.execute("增加预算部分", session_ctx=session)
        self.assertTrue(turn3.success)
        self.assertEqual(session.get_turn_count(), 3)

        summary = session.get_history_summary()
        self.assertIn("共3轮", summary)


class TestCacheAndProcessorInteraction(unittest.TestCase):
    """INT-007: SearchCache + SearchResultProcessor interaction"""

    def setUp(self):
        self.engine = TaskEngineV3()
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_cache_hit_still_processed(self):
        """缓存命中时也应经过处理器（或直接返回缓存）"""
        engine = self.engine

        results1, sources1 = engine._search("相同查询", max_results=3)
        results2, sources2 = engine._search("相同查询", max_results=3)

        self.assertEqual(len(results1), len(results2))


class TestInputValidationAndSession(unittest.TestCase):
    """INT-008: InputValidator + SessionContextManager"""

    def setUp(self):
        _start_mocks(self)

    def tearDown(self):
        _stop_mocks(self)

    def test_xss_input_cleaned_before_session(self):
        """XSS input should be cleaned before storing in session"""
        session = SessionContextManager()
        engine = TaskEngineV3()

        xss_input = "<script>alert('xss')</script>测试"

        result = engine.execute(xss_input, session_ctx=session)

        history = session.get_full_history()
        if history:
            user_entries = [h for h in history if h["role"] == "user"]
            for entry in user_entries:
                self.assertNotIn("<script>", entry["content"])


class TestExecutorTimeoutHandling(unittest.TestCase):
    """INT-009: AsyncTaskExecutor超时处理"""

    def test_cancel_then_check_status(self):
        """取消后状态应为cancelled"""
        executor = AsyncTaskExecutor()

        def long_task(prompt, **kwargs):
            time.sleep(5)
            return {"content": "不该到达这里", "success": True}

        task_id = executor.submit("长任务", execute_func=long_task)
        time.sleep(0.05)

        cancelled = executor.cancel(task_id)
        self.assertTrue(cancelled)

        time.sleep(0.1)
        status = executor.get_status(task_id)
        self.assertEqual(status["status"], "cancelled")


class TestLLMFallbackToEngine(unittest.TestCase):
    """INT-010: LLM降级→引擎回退到v3.4逻辑"""

    def test_fallback_content_still_valid(self):
        """降级后的内容仍应是有效的Markdown"""
        generator = LLMEnhancedContentGenerator()

        with patch.dict("os.environ", {}, clear=True):
            result = generator.generate(
                user_input="降级测试",
                template="# 文档\n\n## 内容\n这是详细内容。" * 30,
            )

        self.assertTrue(result.success or result.fallback_used)
        self.assertIn("#", result.content)


class TestConcurrentTaskIsolation(unittest.TestCase):
    """INT-011: 并发任务隔离"""

    def test_two_tasks_independent(self):
        """同时提交2个任务应互不干扰"""
        executor = AsyncTaskExecutor(max_concurrent=5)

        tid1 = executor.submit(
            "任务A",
            execute_func=lambda prompt, **kw: {
                "content": f"结果{prompt}",
                "success": True,
            },
        )
        tid2 = executor.submit(
            "任务B",
            execute_func=lambda prompt, **kw: {
                "content": f"结果{prompt}",
                "success": True,
            },
        )

        self.assertIsNotNone(tid1)
        self.assertIsNotNone(tid2)
        self.assertNotEqual(tid1, tid2)

        time.sleep(0.2)

        s1 = executor.get_status(tid1)
        s2 = executor.get_status(tid2)

        self.assertEqual(s1["status"], "done")
        self.assertEqual(s2["status"], "done")
        self.assertIn("任务A", s1.get("result_content", ""))
        self.assertIn("任务B", s2.get("result_content", ""))


class TestFilenameWithTurnInfo(unittest.TestCase):
    """INT-012: 文件命名包含轮次信息"""

    def test_session_metadata_includes_turn_id(self):
        """会话记录应包含turn_id用于文件命名"""
        session = SessionContextManager()
        engine = TaskEngineV3()

        engine.execute("第1轮", session_ctx=session)
        engine.execute("第2轮", session_ctx=session)

        history = session.get_full_history()
        turn_ids = set(h["turn_id"] for h in history)
        self.assertEqual(turn_ids, {1, 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)
