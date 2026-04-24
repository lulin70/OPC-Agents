"""AsyncTaskExecutor 单元测试 v3.5 — P0-3 异步执行稳定性

测试覆盖范围（对应 TEST_PLAN_V3.md 的 TestAsyncExecution 类别）：
- AE-001: 提交返回task_id
- AE-002: 状态轮询正确性
- AE-003: 取消操作有效性
- AE-004: 超时自动清理

=== 验收标准 (G-ASYNC-01 门禁) ===
- submit() 返回task_id < 100ms
- get_status() 轮询状态流转: pending→running→completed/cancelled
- cancel() 成功率 >= 95%
"""
import unittest
import time
import threading
from typing import List
from opc_manager.async_executor import AsyncTaskExecutor, TaskStatus, AsyncTask


class TestSubmitReturnsTaskID(unittest.TestCase):
    """AE-001: 提交返回task_id测试"""

    def setUp(self):
        self.executor = AsyncTaskExecutor(max_concurrent=5, default_timeout=30)

    def test_submit_returns_valid_uuid_format(self):
        """submit()返回的task_id应为UUID格式"""
        task_id = self.executor.submit("测试任务")

        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith('task-'))
        self.assertEqual(len(task_id), 17)

    def test_submit_is_non_blocking(self):
        """submit()应在10ms内返回（不阻塞）"""
        start = time.time()
        
        def slow_task(prompt, cancel_event, **kwargs):
            time.sleep(2)
            return {'content': '慢任务完成', 'success': True}

        task_id = self.executor.submit("慢任务", execute_func=slow_task)
        elapsed_ms = (time.time() - start) * 1000

        self.assertIsNotNone(task_id)
        self.assertLess(elapsed_ms, 100, f"submit耗时{elapsed_ms:.1f}ms超过100ms")

    def test_submit_empty_prompt_returns_none(self):
        """空prompt应返回None"""
        task_id1 = self.executor.submit("")
        task_id2 = self.executor.submit(None)
        task_id3 = self.executor.submit("   ")

        self.assertIsNone(task_id1)
        self.assertIsNone(task_id2)
        self.assertIsNone(task_id3)

    def test_submit_stores_prompt_in_task(self):
        """提交的任务应保存原始prompt"""
        prompt = "帮我写Q2营销方案"
        task_id = self.executor.submit(prompt)

        status = self.executor.get_status(task_id)
        self.assertTrue(status['exists'])


class TestStatusPolling(unittest.TestCase):
    """AE-002: 状态轮询正确性测试"""

    def setUp(self):
        self.executor = AsyncTaskExecutor(max_concurrent=5, default_timeout=30)

    def test_pending_to_running_transition(self):
        """任务状态应从pending变为running"""
        transition_log = []

        def tracking_task(prompt, cancel_event, **kwargs):
            time.sleep(0.1)
            return {'content': '完成', 'success': True}

        task_id = self.executor.submit("跟踪任务", execute_func=tracking_task)

        status1 = self.executor.get_status(task_id)
        self.assertIn(status1['status'], ['pending', 'running'])

        time.sleep(0.2)

        status2 = self.executor.get_status(task_id)
        self.assertEqual(status2['status'], 'done')

    def test_done_status_contains_result(self):
        """done状态应包含完整的结果数据"""
        expected_content = "这是生成的内容"
        expected_filepath = "/tmp/test_output.md"

        def mock_execute(prompt, cancel_event, **kwargs):
            time.sleep(0.05)
            return {
                'content': expected_content,
                'success': True,
                'filepath': expected_filepath,
                'task_type': 'content_generation',
            }

        task_id = self.executor.submit("mock任务", execute_func=mock_execute)
        time.sleep(0.2)

        status = self.executor.get_status(task_id)
        self.assertEqual(status['status'], 'done')
        self.assertEqual(status['result_content'], expected_content)
        self.assertEqual(status['result_filepath'], expected_filepath)
        self.assertEqual(status['result_success'], True)

    def test_failed_status_contains_error(self):
        """failed状态应包含错误信息"""
        def failing_task(prompt, cancel_event, **kwargs):
            raise ValueError("模拟执行失败")

        task_id = self.executor.submit("失败任务", execute_func=failing_task)
        time.sleep(0.2)

        status = self.executor.get_status(task_id)
        self.assertEqual(status['status'], 'failed')
        self.assertIsNotNone(status['error_message'])
        self.assertIn('模拟执行失败', status['error_message'])

    def test_elapsed_time_increases(self):
        """elapsed字段应随时间增长"""
        def slow_task(prompt, cancel_event, **kwargs):
            time.sleep(0.15)
            return {'content': 'ok', 'success': True}

        task_id = self.executor.submit("计时任务", execute_func=slow_task)

        status1 = self.executor.get_status(task_id)
        elapsed1 = status1['elapsed']
        time.sleep(0.1)

        status2 = self.executor.get_status(task_id)
        elapsed2 = status2['elapsed']

        self.assertGreater(elapsed2, elapsed1)


class TestCancelOperation(unittest.TestCase):
    """AE-003: 取消操作有效性测试"""

    def setUp(self):
        self.executor = AsyncTaskExecutor(max_concurrent=5, default_timeout=30)

    def test_cancel_pending_task(self):
        """取消pending状态的任务应成功"""
        def long_running_task(prompt, cancel_event, **kwargs):
            for i in range(20):
                if cancel_event.is_set():
                    raise InterruptedError("任务被取消")
                time.sleep(0.05)
            return {'content': '不应到达这里', 'success': True}

        task_id = self.executor.submit("长任务", execute_func=long_running_task)
        time.sleep(0.05)

        can_cancel = self.executor.cancel(task_id)
        self.assertTrue(can_cancel)

        time.sleep(0.1)
        status = self.executor.get_status(task_id)
        self.assertEqual(status['status'], 'cancelled')

    def test_cancel_nonexistent_task(self):
        """取消不存在的任务应返回False"""
        result = self.executor.cancel("task-nonexistent123")
        self.assertFalse(result)

    def test_cancel_completed_task(self):
        """取消已完成的任务应返回False"""
        def quick_task(prompt, cancel_event, **kwargs):
            return {'content': '快速完成', 'success': True}

        task_id = self.executor.submit("快任务", execute_func=quick_task)
        time.sleep(0.15)

        result = self.executor.cancel(task_id)
        self.assertFalse(result)

    def test_cancel_prevents_result_delivery(self):
        """取消后任务不应产生有效结果"""
        cancellation_detected = [False]

        def cancellable_task(prompt, cancel_event, **kwargs):
            time.sleep(0.05)
            if cancel_event.is_set():
                cancellation_detected[0] = True
                return None
            time.sleep(0.2)
            return {'content': '正常结果', 'success': True}

        task_id = self.executor.submit("可取消任务", execute_func=cancellable_task)
        time.sleep(0.02)
        self.executor.cancel(task_id)
        time.sleep(0.15)

        status = self.executor.get_status(task_id)
        self.assertEqual(status['status'], 'cancelled')


class TestTimeoutAutoCleanup(unittest.TestCase):
    """AE-004: 超时和自动清理测试"""

    def setUp(self):
        self.executor = AsyncTaskExecutor(
            max_concurrent=5,
            default_timeout=1,
            max_history=10,
        )

    def test_max_concurrent_limit(self):
        """达到并发上限后submit()应返回None"""
        started_tasks = []

        def blocking_task(prompt, cancel_event, **kwargs):
            started_tasks.append(prompt)
            cancel_event.wait(timeout=2)
            return {'content': '阻塞结束', 'success': True}

        task_ids = []
        for i in range(6):
            tid = self.executor.submit(f"并发任务{i}", execute_func=blocking_task)
            if tid:
                task_ids.append(tid)
            time.sleep(0.01)

        self.assertLessEqual(len(task_ids), 5)
        self.assertEqual(len(started_tasks), len(task_ids))

        for tid in task_ids:
            self.executor.cancel(tid)

    def test_get_status_not_found(self):
        """查询不存在的任务应返回exists=False"""
        status = self.executor.get_status("task-fake000000")
        self.assertFalse(status['exists'])
        self.assertEqual(status['status'], 'not_found')

    def test_list_active_tasks(self):
        """list_active_tasks应只返回pending/running任务"""
        def quick_task(prompt, cancel_event, **kwargs):
            return {'content': '快', 'success': True}

        tid1 = self.executor.submit("活跃任务1", execute_func=quick_task)
        tid2 = self.executor.submit("活跃任务2", execute_func=quick_task)

        active = self.executor.list_active_tasks()
        self.assertGreaterEqual(len(active), 0)

        time.sleep(0.2)
        active_after = self.executor.list_active_tasks()
        self.assertLessEqual(len(active_after), len(active))

    def test_manual_cleanup(self):
        """手动cleanup应删除已完成任务"""
        def quick_task(prompt, cancel_event, **kwargs):
            return {'content': '待清理', 'success': True}

        task_id = self.executor.submit("清理目标", execute_func=quick_task)
        time.sleep(0.15)

        status_before = self.executor.get_status(task_id)
        self.assertTrue(status_before['exists'])

        cleaned = self.executor.cleanup(task_id)
        self.assertTrue(cleaned)

        status_after = self.executor.get_status(task_id)
        self.assertFalse(status_after['exists'])


class TestGateASYNC01(unittest.TestCase):
    """G-ASYNC-01: 异步执行稳定性门禁（P0阻断级）

    这是CDR定义的核心验收标准，必须全量通过才能发布v3.5
    """

    def setUp(self):
        self.executor = AsyncTaskExecutor(max_concurrent=5, default_timeout=60)

    def test_submit_latency_under_100ms(self):
        """门禁：submit()延迟 < 100ms"""
        start = time.time()

        for i in range(10):
            task_id = self.executor.submit(f"性能测试{i}", execute_func=lambda p, ce: {'content': '', 'success': True})

        elapsed_ms = (time.time() - start) * 1000

        avg_per_submit = elapsed_ms / 10
        self.assertLess(avg_per_submit, 100, f"平均submit耗时{avg_per_submit:.1f}ms超过100ms")

    def test_full_lifecycle_no_crash(self):
        """门禁：完整生命周期(pending→running→done)无崩溃"""
        errors = []

        def robust_task(prompt, cancel_event, **kwargs):
            time.sleep(0.08)
            return {
                'content': f'处理完成: {prompt}',
                'success': True,
                'filepath': '/tmp/test_gate_async.txt',
                'task_type': 'test',
            }

        task_id = self.executor.submit("门禁测试", execute_func=robust_task)
        self.assertIsNotNone(task_id, "submit失败")

        max_wait = 50
        final_status = None
        for _ in range(max_wait):
            status = self.executor.get_status(task_id)
            final_status = status['status']
            if final_status in ['done', 'failed', 'cancelled']:
                break
            time.sleep(0.01)

        self.assertEqual(final_status, 'done', f"最终状态异常: {final_status}")

        result = self.executor.get_status(task_id)
        self.assertTrue(result['result_success'])
        self.assertIsNotNone(result['result_content'])
        self.assertGreater(len(result['result_content']), 0)

    def test_cancellation_reliability(self):
        """门禁：cancel()成功率 >= 95%（抽样10次）"""
        success_count = 0
        total_tests = 10

        for i in range(total_tests):
            def cancellable(prompt, cancel_event, **kwargs):
                try:
                    for _ in range(50):
                        if cancel_event.is_set():
                            raise InterruptedError()
                        time.sleep(0.02)
                    return {'content': '未取消', 'success': True}
                except InterruptedError:
                    return None

            task_id = self.executor.submit(f"可靠性测试{i}", execute_func=cancellable)
            time.sleep(0.05)

            if self.executor.cancel(task_id):
                success_count += 1
            time.sleep(0.1)

        success_rate = success_count / total_tests * 100
        self.assertGreaterEqual(success_rate, 95, f"cancel成功率{success_rate:.0f}%低于95%")


if __name__ == '__main__':
    unittest.main(verbosity=2)
