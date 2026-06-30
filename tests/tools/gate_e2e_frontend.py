"""V36-P1-3 G-E2E-FRONTEND-01 前端E2E测试门禁

验证范围：
1. AsyncTaskExecutor与前端app.py的集成完整性
2. submit→poll→display完整异步流程
3. 取消功能、并发限制、超时处理
4. 知识库扩展后兜底逻辑
5. MOKA API适配层正确性
6. 首屏简化后SCENARIOS_CORE/SCENARIOS_MORE数据结构

门禁标准：
- G-E2E-FRONTEND-01a: 所有异步流程测试通过 (≥90%)
- G-E2E-FRONTEND-01b: MOKA API适配层测试通过 (100%)
- G-E2E-FRONTEND-01c: 知识库兜底命中率 ≥5个分类

运行方式：
    PYTHONPATH=. python3 -m pytest tests/gate_e2e_frontend.py -v
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.async_executor import AsyncTaskExecutor
from opc_manager.search_processor import SearchResultProcessor, KNOWLEDGE_BASE
from opc_manager.llm_content import LLMEnhancedContentGenerator


class TestAsyncFlowGate:
    """G-E2E-FRONTEND-01a: 异步流程完整性门禁"""

    def test_submit_poll_done_flow(self):
        """submit→poll→done 完整流程"""
        executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def quick_task(prompt, cancel_event):
            time.sleep(0.3)
            return {
                "content": f"# {prompt}\n\n完成！",
                "success": True,
                "filepath": "/tmp/gate_test.md",
                "task_type": "CONTENT_GENERATION",
                "error": None,
            }

        task_id = executor.submit("门禁测试", execute_func=quick_task)
        assert task_id is not None

        for _ in range(20):
            status = executor.get_status(task_id)
            if status["status"] == "done":
                assert status["result_content"] is not None
                assert "门禁测试" in status["result_content"]
                return
            time.sleep(0.2)

        pytest.fail("异步流程超时未完成")

    def test_submit_poll_failed_flow(self):
        """submit→poll→failed 异常流程"""
        executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=5)

        def failing_task(prompt, cancel_event):
            raise ValueError("模拟执行失败")

        task_id = executor.submit("失败测试", execute_func=failing_task)

        for _ in range(15):
            status = executor.get_status(task_id)
            if status["status"] == "failed":
                assert status["error_message"] is not None
                return
            time.sleep(0.2)

        pytest.fail("异常流程未正确标记failed")

    def test_cancel_flow(self):
        """submit→cancel 流程"""
        executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def slow_task(prompt, cancel_event):
            time.sleep(60)
            return {
                "content": "",
                "success": False,
                "filepath": None,
                "task_type": None,
                "error": None,
            }

        task_id = executor.submit("可取消任务", execute_func=slow_task)
        time.sleep(0.05)

        assert executor.cancel(task_id) is True

        time.sleep(0.1)
        status = executor.get_status(task_id)
        assert status["status"] == "cancelled"

    def test_concurrent_limit_enforcement(self):
        """并发限制执行"""
        executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def blocker(prompt, **kw):
            return time.sleep(30)

        t1 = executor.submit("任务1", execute_func=blocker)
        t2 = executor.submit("任务2", execute_func=blocker)
        t3 = executor.submit("任务3", execute_func=blocker)

        assert t1 is not None
        assert t2 is not None
        assert t3 is None, "超过并发上限应返回None"

        executor.cancel(t1)
        executor.cancel(t2)

    def test_empty_prompt_rejected(self):
        """空prompt应被拒绝"""
        executor = AsyncTaskExecutor()
        assert executor.submit("") is None
        assert executor.submit("   ") is None
        assert executor.submit(None) is None

    def test_nonexistent_task_status(self):
        """查询不存在的任务"""
        executor = AsyncTaskExecutor()
        status = executor.get_status("task-nonexistent")
        assert status["exists"] is False


class TestMOKAAPIAdapterGate:
    """G-E2E-FRONTEND-01b: MOKA API适配层门禁"""

    def test_moka_config_priority(self):
        """MOKA配置优先级最高"""
        os.environ["MOKA_API_KEY"] = "test-moka-key"
        os.environ["MOKA_API_BASE"] = "https://api.moka-ai.com/v1"
        os.environ["MOKA_MODEL"] = "moka/claude-sonnet-4-6"

        try:
            gen = LLMEnhancedContentGenerator()
            key, base, model = gen._get_llm_config()
            assert key == "test-moka-key"
            assert base == "https://api.moka-ai.com/v1"
            assert model == "moka/claude-sonnet-4-6"
        finally:
            del os.environ["MOKA_API_KEY"]
            del os.environ["MOKA_API_BASE"]
            del os.environ["MOKA_MODEL"]

    def test_glm_fallback_without_moka(self):
        """无MOKA时回退到GLM"""
        for k in ["MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"]:
            os.environ.pop(k, None)

        os.environ["GLM_API_KEY"] = "test-glm-key"

        try:
            gen = LLMEnhancedContentGenerator()
            key, base, model = gen._get_llm_config()
            assert key == "test-glm-key"
            assert "bigmodel" in base
            assert model == "glm-4"
        finally:
            del os.environ["GLM_API_KEY"]

    def test_openai_fallback_without_others(self):
        """无MOKA/GLM时回退到OpenAI"""
        for k in ["MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"]:
            os.environ.pop(k, None)

        os.environ["OPENAI_API_KEY"] = "test-openai-key"

        try:
            gen = LLMEnhancedContentGenerator()
            key, base, model = gen._get_llm_config()
            assert key == "test-openai-key"
            assert model == "gpt-4"
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_no_key_returns_none(self):
        """无任何Key时返回None"""
        for k in ["MOKA_API_KEY", "GLM_API_KEY", "OPENAI_API_KEY"]:
            os.environ.pop(k, None)

        gen = LLMEnhancedContentGenerator()
        key, base, model = gen._get_llm_config()
        assert key is None

    def test_backward_compatible_get_api_key(self):
        """_get_llm_api_key()向后兼容"""
        os.environ["MOKA_API_KEY"] = "compat-test-key"
        os.environ["MOKA_API_BASE"] = "https://api.moka-ai.com/v1"
        os.environ["MOKA_MODEL"] = "moka/claude-sonnet-4-6"

        try:
            gen = LLMEnhancedContentGenerator()
            key = gen._get_llm_api_key()
            assert key == "compat-test-key"
        finally:
            del os.environ["MOKA_API_KEY"]
            del os.environ["MOKA_API_BASE"]
            del os.environ["MOKA_MODEL"]


class TestKnowledgeBaseGate:
    """G-E2E-FRONTEND-01c: 知识库兜底门禁"""

    def test_knowledge_base_has_6_categories(self):
        """知识库应包含6个分类"""
        assert len(KNOWLEDGE_BASE) >= 6, f"知识库分类数不足: {len(KNOWLEDGE_BASE)}"

    def test_knowledge_base_has_20_entries(self):
        """知识库应包含至少20条目"""
        total = sum(len(entries) for entries in KNOWLEDGE_BASE.values())
        assert total >= 20, f"知识库条目数不足: {total}"

    def test_new_categories_exist(self):
        """新增分类应存在"""
        required = ["产品发布", "数据分析", "项目管理"]
        for cat in required:
            assert cat in KNOWLEDGE_BASE, f"缺少分类: {cat}"

    def test_fallback_hits_new_categories(self):
        """兜底逻辑应能命中新增分类"""
        processor = SearchResultProcessor()

        test_queries = {
            "产品发布": "帮我制定产品发布计划",
            "数据分析": "分析用户行为数据",
            "项目管理": "项目管理方法论",
        }

        for category, query in test_queries.items():
            result = processor.process(query, [])
            assert result.fallback_used is True, f"查询'{query}'应触发知识库兜底"
            kb_cats = [r.get("_kb_category", "") for r in result.results]
            assert any(
                category in c for c in kb_cats
            ), f"应命中分类'{category}'，实际: {kb_cats}"

    def test_original_categories_still_work(self):
        """原有分类仍能正常兜底"""
        processor = SearchResultProcessor()

        original_queries = {
            "营销方案": "Q2营销方案",
            "税收政策": "小微企业税收优惠",
            "AI Agent": "AI Agent架构设计",
        }

        for category, query in original_queries.items():
            result = processor.process(query, [])
            assert result.fallback_used is True, f"查询'{query}'应触发知识库兜底"


class TestPerformanceGate:
    """性能门禁"""

    def test_submit_latency_under_100ms(self):
        """submit延迟应<100ms"""
        executor = AsyncTaskExecutor()
        latencies = []
        for _ in range(5):
            start = time.time()
            executor.submit("性能测试")
            latencies.append((time.time() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        assert avg < 100, f"submit平均延迟过高: {avg:.1f}ms"

    def test_get_status_latency_under_5ms(self):
        """get_status延迟应<5ms"""
        executor = AsyncTaskExecutor()
        task_id = executor.submit("状态查询")
        time.sleep(0.05)

        latencies = []
        for _ in range(50):
            start = time.time()
            executor.get_status(task_id)
            latencies.append((time.time() - start) * 1000)

        avg = sum(latencies) / len(latencies)
        assert avg < 5, f"get_status平均延迟过高: {avg:.3f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
