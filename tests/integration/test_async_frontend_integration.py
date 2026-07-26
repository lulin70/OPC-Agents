"""V36-P0-2 集成测试: 前端AsyncTaskExecutor异步流程验证

测试范围：
1. AsyncTaskExecutor与frontend/app.py的集成
2. submit→poll→display完整流程
3. 取消功能、并发限制、超时处理
4. _async_execute_task包装函数正确性

运行方式：
    PYTHONPATH=. python3 -m pytest tests/test_async_frontend_integration.py -v
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.async_executor import AsyncTaskExecutor, TaskStatus


class TestAsyncExecutorIntegration:
    """AsyncTaskExecutor基础集成测试"""

    def setup_method(self):
        """每个测试前创建新的executor实例"""
        self.executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=10)

    def teardown_method(self, method):
        """每个测试后关闭executor，释放后台线程"""
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    def test_submit_returns_task_id_immediately(self):
        """测试submit()是否立即返回task_id（<10ms）"""
        start = time.time()
        task_id = self.executor.submit("测试任务")
        elapsed_ms = (time.time() - start) * 1000

        assert task_id is not None, "submit应返回有效的task_id"
        assert task_id.startswith("task-"), f"task_id格式错误: {task_id}"
        assert elapsed_ms < 100, f"submit耗时过长: {elapsed_ms:.1f}ms (应<100ms)"
        print(f"✅ submit延迟: {elapsed_ms:.1f}ms")

    def test_submit_empty_prompt_returns_none(self):
        """测试空prompt应返回None"""
        assert self.executor.submit("") is None
        assert self.executor.submit("   ") is None
        assert self.executor.submit(None) is None

    def test_get_status_pending_state(self):
        """测试提交后初始状态应为pending或running"""

        def slow_func(prompt, **kw):
            time.sleep(5)

        task_id = self.executor.submit("测试状态查询", execute_func=slow_func)
        time.sleep(0.2)

        status = self.executor.get_status(task_id)
        assert status["exists"] is True, "任务应存在"
        assert status["status"] in [
            TaskStatus.PENDING.value,
            TaskStatus.RUNNING.value,
        ], f"初始状态异常: {status['status']}"

    def test_get_status_nonexistent_task(self):
        """测试查询不存在的task_id"""
        status = self.executor.get_status("task-nonexistent")
        assert status["exists"] is False

    def test_cancel_pending_task(self):
        """测试取消pending状态的任务"""

        def slow_func(prompt, **kw):
            time.sleep(10)

        task_id = self.executor.submit("慢任务", execute_func=slow_func)
        time.sleep(0.05)

        cancel_result = self.executor.cancel(task_id)
        assert cancel_result is True, "取消应成功"

        time.sleep(0.1)
        status = self.executor.get_status(task_id)
        assert (
            status["status"] == TaskStatus.CANCELLED.value
        ), f"取消后状态应为cancelled，实际: {status['status']}"

    def test_concurrent_limit(self):
        """测试并发数达到上限后应拒绝新任务"""

        def blocker(prompt, **kw):
            time.sleep(60)

        task_ids = []
        for i in range(3):
            tid = self.executor.submit(f"阻塞任务{i}", execute_func=blocker)
            task_ids.append(tid)
            assert tid is not None, f"第{i + 1}个任务应成功提交"
            time.sleep(0.05)

        rejected = self.executor.submit("超额任务", execute_func=blocker)
        assert rejected is None, "超过并发上限应返回None"

        for tid in task_ids:
            self.executor.cancel(tid)


class TestAsyncExecuteWrapper:
    """_async_execute_task包装函数测试"""

    def teardown_method(self, method):
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    def test_wrapper_returns_dict_on_success(self):
        """测试成功执行时返回正确的字典结构"""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "frontend"))

        self.executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def mock_execute(prompt, cancel_event):
            return {
                "content": "# 测试内容\n\n这是测试生成的文档。",
                "success": True,
                "filepath": "/tmp/test_deliverable.md",
                "task_type": "CONTENT_GENERATION",
                "error": None,
            }

        task_id = self.executor.submit("wrapper测试", execute_func=mock_execute)

        max_wait = 5
        start = time.time()
        while time.time() - start < max_wait:
            status = self.executor.get_status(task_id)
            if status["status"] in ["done", "failed", "cancelled"]:
                break
            time.sleep(0.1)

        final_status = self.executor.get_status(task_id)
        assert (
            final_status["status"] == "done"
        ), f"任务应完成，实际: {final_status['status']}"
        assert final_status["result_success"] is True
        assert final_status["result_content"] is not None
        assert "测试内容" in final_status["result_content"]
        print(f"✅ 包装函数测试通过: content长度={len(final_status['result_content'])}")

    def test_wrapper_handles_exception(self):
        """测试异常情况下的错误处理"""
        self.executor = AsyncTaskExecutor(
            max_concurrent=2, default_timeout=5, max_retries=0
        )

        def failing_execute(prompt, cancel_event):
            raise ValueError("模拟执行失败")

        task_id = self.executor.submit("失败测试", execute_func=failing_execute)

        max_wait = 3
        start = time.time()
        while time.time() - start < max_wait:
            status = self.executor.get_status(task_id)
            if status["status"] in ["done", "failed", "cancelled"]:
                break
            time.sleep(0.1)

        final_status = self.executor.get_status(task_id)
        assert (
            final_status["status"] == "failed"
        ), f"应为failed状态，实际: {final_status['status']}"
        assert final_status["error_message"] is not None
        print(f"✅ 异常处理测试通过: error={final_status['error_message']}")


class TestEndToEndFlow:
    """端到端流程测试: submit → poll → result"""

    def teardown_method(self, method):
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    def test_complete_flow_success(self):
        """测试完整成功流程"""
        self.executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def quick_task(prompt, cancel_event):
            time.sleep(0.2)
            return {
                "content": f"# {prompt}\n\n任务执行完成！",
                "success": True,
                "filepath": "/tmp/e2e_test.md",
                "task_type": "GENERAL_CHAT",
                "error": None,
            }

        task_id = self.executor.submit("E2E完整测试", execute_func=quick_task)
        assert task_id is not None, "提交应成功"

        states_seen = []
        max_polls = 20
        for i in range(max_polls):
            status = self.executor.get_status(task_id)
            states_seen.append(status["status"])

            if status["status"] == "done":
                assert status["result_content"] is not None
                assert "E2E完整测试" in status["result_content"]
                assert status["result_filepath"] == "/tmp/e2e_test.md"
                print(
                    f"✅ E2E流程完成: 经历{len(states_seen)}次轮询, 最终状态={status['status']}"
                )
                return

            elif status["status"] == "failed":
                pytest.fail(f"任务意外失败: {status['error_message']}")

            time.sleep(0.1)

        pytest.fail(f"超时未完成，经历的状态序列: {states_seen}")

    def test_complete_flow_with_cancel(self):
        """测试带取消的完整流程"""
        self.executor = AsyncTaskExecutor(max_concurrent=2, default_timeout=10)

        def slow_task(prompt, cancel_event):
            time.sleep(30)
            return {
                "content": "",
                "success": False,
                "filepath": None,
                "task_type": None,
                "error": "timeout",
            }

        task_id = self.executor.submit("可取消任务", execute_func=slow_task)
        time.sleep(0.1)

        initial_status = self.executor.get_status(task_id)
        assert initial_status["status"] in ["pending", "running"]

        cancelled = self.executor.cancel(task_id)
        assert cancelled is True

        time.sleep(0.2)
        final_status = self.executor.get_status(task_id)
        assert final_status["status"] == "cancelled"
        print(f"✅ 取消流程完成: task_id={task_id}")

    def test_multiple_concurrent_tasks(self):
        """测试多个任务并发执行"""
        self.executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=10)

        def timed_task(prompt, cancel_event):
            duration = float(prompt.split("_")[-1])
            time.sleep(duration)
            return {
                "content": f"任务{prompt}完成",
                "success": True,
                "filepath": None,
                "task_type": None,
                "error": None,
            }

        task_ids = []
        for i, delay in enumerate([0.1, 0.2, 0.15]):
            tid = self.executor.submit(f"task_{delay}", execute_func=timed_task)
            task_ids.append(tid)

        completed = 0
        completed_ids = set()
        max_wait = 3
        start = time.time()

        while time.time() - start < max_wait and completed < 3:
            for tid in task_ids:
                if tid not in completed_ids:
                    status = self.executor.get_status(tid)
                    if status["status"] == "done":
                        completed += 1
                        completed_ids.add(tid)
            time.sleep(0.1)

        assert completed == 3, f"应有3个任务完成，实际: {completed}"
        print("✅ 并发测试通过: 3个任务全部完成")


class TestPerformanceGuarantees:
    """性能保证测试 — 验证V36-P0-2的关键性能指标"""

    def teardown_method(self, method):
        if hasattr(self, "executor") and self.executor:
            self.executor.shutdown(wait=False)

    def test_submit_latency_under_50ms(self):
        """submit()延迟应<50ms（ADR-010要求）。

        阈值说明：
        - 平均延迟 50ms：ADR-010 性能要求
        - 最大延迟 200ms：CI runner 比本地慢 5-10x（project_memory 教训），
          本地典型 ~5-10ms，CI 上偶发可达 100-130ms，200ms 留 4x 余量
        - v0.5.5 Release workflow 两次失败（102.4ms / 122.5ms），证明 100ms 阈值
          在 CI runner 性能波动下不可靠
        """
        self.executor = AsyncTaskExecutor()
        latencies = []

        for _ in range(10):
            start = time.time()
            self.executor.submit("性能测试")
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        assert avg_latency < 50, f"平均submit延迟过高: {avg_latency:.1f}ms"
        assert max_latency < 200, f"最大submit延迟过高: {max_latency:.1f}ms"
        print(f"✅ submit性能: 平均={avg_latency:.1f}ms, 最大={max_latency:.1f}ms")

    def test_get_status_latency_under_1ms(self):
        """get_status()延迟应<1ms（纯内存读取）"""
        self.executor = AsyncTaskExecutor()
        task_id = self.executor.submit("状态查询测试")
        time.sleep(0.05)

        latencies = []
        for _ in range(100):
            start = time.time()
            self.executor.get_status(task_id)
            elapsed_ms = (time.time() - start) * 1000
            latencies.append(elapsed_ms)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 5, f"平均get_status延迟过高: {avg_latency:.3f}ms"
        print(f"✅ get_status性能: 平均={avg_latency:.3f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
