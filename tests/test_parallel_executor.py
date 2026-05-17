"""
Comprehensive Test Suite for Parallel Executor - OPC-Agents LLM Parallelization

Test coverage (35+ test cases):
1. Basic parallel execution (2-5 tasks)
2. Concurrency control (MAX_CONCURRENT=3)
3. Timeout handling
4. Error isolation (one failure doesn't block others)
5. Result merge strategies (concat/merge/deduplicate/first_success)
6. Speed estimation function
7. _should_parallelize heuristic rules
8. Edge cases (empty tasks, all failures, partial failures)
9. Progress callback integration
10. Async/sync function handling

Run with: pytest tests/test_parallel_executor.py -v
"""

import asyncio
import time
import pytest
from typing import List
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opc_manager.parallel_executor import (
    ParallelExecutor,
    TaskSpec,
    TaskResult,
    ParallelResult,
    MergeStrategy,
)


class TestParallelExecutorBasic:
    """Test basic parallel execution functionality"""
    
    @pytest.mark.asyncio
    async def test_execute_two_tasks_successfully(self):
        """Test parallel execution of 2 simple tasks"""
        executor = ParallelExecutor(max_concurrent=2)
        
        async def task_a():
            await asyncio.sleep(0.1)
            return "result_a"
        
        async def task_b():
            await asyncio.sleep(0.1)
            return "result_b"
        
        tasks = [
            TaskSpec(func=task_a, description="Task A"),
            TaskSpec(func=task_b, description="Task B"),
        ]
        
        result = await executor.execute_parallel(tasks, session_id="test_session")
        
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.results) == 2
        assert result.results[0].result == "result_a"
        assert result.results[1].result == "result_b"
        assert result.speedup_factor >= 1.0
    
    @pytest.mark.asyncio
    async def test_execute_five_tasks(self):
        """Test parallel execution of 5 tasks"""
        executor = ParallelExecutor(max_concurrent=3)
        
        results_expected = []
        
        async def make_task(idx):
            await asyncio.sleep(0.05)
            results_expected.append(f"result_{idx}")
            return f"result_{idx}"
        
        tasks = [TaskSpec(func=lambda i=i: make_task(i), description=f"Task {i}") for i in range(5)]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 5
        assert result.failure_count == 0
        assert len(result.results) == 5
    
    @pytest.mark.asyncio
    async def test_tasks_maintain_order(self):
        """Test that results maintain original task order regardless of completion order"""
        executor = ParallelExecutor(max_concurrent=3)
        
        async def slow_task():
            await asyncio.sleep(0.2)
            return "slow"
        
        async def fast_task():
            await asyncio.sleep(0.05)
            return "fast"
        
        tasks = [
            TaskSpec(func=slow_task, description="Slow"),
            TaskSpec(func=fast_task, description="Fast"),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.results[0].result == "slow"
        assert result.results[0].task_index == 0
        assert result.results[1].result == "fast"
        assert result.results[1].task_index == 1
    
    @pytest.mark.asyncio
    async def test_empty_task_list_raises_error(self):
        """Test that empty task list raises ValueError"""
        executor = ParallelExecutor()
        
        with pytest.raises(ValueError, match="Tasks list cannot be empty"):
            await executor.execute_parallel([])
    
    @pytest.mark.asyncio
    async def test_single_task_execution(self):
        """Test that single task executes correctly (edge case)"""
        executor = ParallelExecutor()
        
        async def solo_task():
            return "solo_result"
        
        tasks = [TaskSpec(func=solo_task, description="Solo")]
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.results[0].result == "solo_result"


class TestConcurrencyControl:
    """Test concurrency limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_max_concurrent_respected(self):
        """Test that max concurrent limit is respected"""
        max_concurrent = 2
        executor = ParallelExecutor(max_concurrent=max_concurrent)
        
        concurrent_count = 0
        peak_concurrent = 0
        lock = asyncio.Lock()
        
        async def tracked_task():
            nonlocal concurrent_count, peak_concurrent
            async with lock:
                concurrent_count += 1
                if concurrent_count > peak_concurrent:
                    peak_concurrent = concurrent_count
            
            await asyncio.sleep(0.1)
            
            async with lock:
                concurrent_count -= 1
            
            return "done"
        
        tasks = [TaskSpec(func=tracked_task, description=f"Task {i}") for i in range(6)]
        
        await executor.execute_parallel(tasks)
        
        assert peak_concurrent <= max_concurrent, f"Peak concurrency {peak_concurrent} exceeded limit {max_concurrent}"
    
    @pytest.mark.asyncio
    async def test_concurrency_one(self):
        """Test with max_concurrent=1 (effectively serial)"""
        executor = ParallelExecutor(max_concurrent=1)

        execution_order = []

        def make_ordered_task(idx):
            async def ordered_task():
                execution_order.append(f"start_{idx}")
                await asyncio.sleep(0.05)
                execution_order.append(f"end_{idx}")
                return idx
            return ordered_task

        tasks = [TaskSpec(func=make_ordered_task(i), description=f"Task {i}") for i in range(3)]

        await executor.execute_parallel(tasks)

        assert len(execution_order) == 6
        for i in range(3):
            start_idx = execution_order.index(f"start_{i}")
            end_idx = execution_order.index(f"end_{i}")
            if i > 0:
                prev_end_idx = execution_order.index(f"end_{i-1}")
                assert start_idx > prev_end_idx, f"Task {i} started before task {i-1} finished"


class TestTimeoutHandling:
    """Test timeout management and handling"""
    
    @pytest.mark.asyncio
    async def test_task_timeout_detected(self):
        """Test that slow tasks are timed out correctly"""
        executor = ParallelExecutor(default_timeout=0.2)
        
        async def slow_task():
            await asyncio.sleep(1.0)  # Much longer than timeout
            return "should_not_complete"
        
        tasks = [TaskSpec(func=slow_task, description="Slow task", timeout=0.2)]
        result = await executor.execute_parallel(tasks)
        
        assert result.failure_count == 1
        assert result.results[0].success is False
        assert "timeout" in result.results[0].error.lower()
    
    @pytest.mark.asyncio
    async def test_timeout_doesnt_block_other_tasks(self):
        """Test that one timed-out task doesn't affect others"""
        executor = ParallelExecutor(max_concurrent=2, default_timeout=0.2)
        
        async def slow_task():
            await asyncio.sleep(1.0)
            return "slow"
        
        async def fast_task():
            await asyncio.sleep(0.05)
            return "fast"
        
        tasks = [
            TaskSpec(func=slow_task, description="Slow", timeout=0.2),
            TaskSpec(func=fast_task, description="Fast", timeout=0.2),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.failure_count == 1
        assert result.results[1].result == "fast"
    
    @pytest.mark.asyncio
    async def test_per_task_timeout_override(self):
        """Test per-task timeout override"""
        executor = ParallelExecutor(default_timeout=5.0)
        
        async def moderate_task():
            await asyncio.sleep(0.3)
            return "completed"
        
        tasks = [
            TaskSpec(func=moderate_task, description="With short timeout", timeout=0.1),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.failure_count == 1
        assert "timeout" in result.results[0].error.lower()


class TestErrorIsolation:
    """Test error isolation between tasks"""
    
    @pytest.mark.asyncio
    async def test_one_failure_doesnt_block_others(self):
        """Test that one failing task doesn't prevent others from completing"""
        executor = ParallelExecutor(max_concurrent=3)
        
        async def failing_task():
            raise ValueError("Intentional failure")
        
        async def successful_task():
            await asyncio.sleep(0.05)
            return "success"
        
        tasks = [
            TaskSpec(func=failing_task, description="Fails"),
            TaskSpec(func=successful_task, description="Succeeds"),
            TaskSpec(func=successful_task, description="Also succeeds"),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 2
        assert result.failure_count == 1
        assert result.results[0].success is False
        assert "Intentional failure" in result.results[0].error
        assert result.results[1].result == "success"
        assert result.results[2].result == "success"
    
    @pytest.mark.asyncio
    async def test_all_tasks_fail(self):
        """Test behavior when all tasks fail"""
        executor = ParallelExecutor()
        
        async def always_fail():
            raise RuntimeError("Always fails")
        
        tasks = [
            TaskSpec(func=always_fail, description="Fail 1"),
            TaskSpec(func=always_fail, description="Fail 2"),
            TaskSpec(func=always_fail, description="Fail 3"),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 0
        assert result.failure_count == 3
        assert all(not r.success for r in result.results)
    
    @pytest.mark.asyncio
    async def test_different_exception_types(self):
        """Test handling of different exception types"""
        executor = ParallelExecutor()
        
        async def value_error():
            raise ValueError("Value error")
        
        async def key_error():
            raise KeyError("missing_key")
        
        async def type_error():
            raise TypeError("Wrong type")
        
        tasks = [
            TaskSpec(func=value_error, description="ValueError"),
            TaskSpec(func=key_error, description="KeyError"),
            TaskSpec(func=type_error, description="TypeError"),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.failure_count == 3
        assert "Value error" in result.results[0].error
        assert "missing_key" in result.results[1].error
        assert "Wrong type" in result.results[2].error


class TestMergeStrategies:
    """Test result merging strategies"""
    
    @pytest.mark.asyncio
    async def test_concat_strategy(self):
        """Test CONCAT merge strategy"""
        executor = ParallelExecutor()
        
        tasks = [
            TaskSpec(func=lambda: "content_a", description="A"),
            TaskSpec(func=lambda: "content_b", description="B"),
            TaskSpec(func=lambda: "content_c", description="C"),
        ]
        
        result = await executor.execute_parallel(tasks, merge_strategy=MergeStrategy.CONCAT)
        
        assert "content_a" in result.merged_content
        assert "content_b" in result.merged_content
        assert "content_c" in result.merged_content
        assert "---" in result.merged_content
    
    @pytest.mark.asyncio
    async def test_deduplicate_strategy(self):
        """Test DEDUPLICATE merge strategy removes duplicates"""
        executor = ParallelExecutor()
        
        duplicate_content = "same content"
        
        tasks = [
            TaskSpec(func=lambda: duplicate_content, description="A"),
            TaskSpec(func=lambda: duplicate_content, description="B"),
            TaskSpec(func=lambda: "unique content", description="C"),
        ]
        
        result = await executor.execute_parallel(tasks, merge_strategy=MergeStrategy.DEDUPLICATE)
        
        assert result.merged_content.count("same content") == 1
        assert "unique content" in result.merged_content
    
    @pytest.mark.asyncio
    async def test_first_success_strategy(self):
        """Test FIRST_SUCCESS strategy returns only first successful result"""
        executor = ParallelExecutor()
        
        tasks = [
            TaskSpec(func=lambda: "first", description="First"),
            TaskSpec(func=lambda: "second", description="Second"),
            TaskSpec(func=lambda: "third", description="Third"),
        ]
        
        result = await executor.execute_parallel(tasks, merge_strategy=MergeStrategy.FIRST_SUCCESS)
        
        assert result.merged_content == "first"
    
    @pytest.mark.asyncio
    async def test_merge_with_failures(self):
        """Test merging when some tasks failed"""
        executor = ParallelExecutor()
        
        async def fail_task():
            raise ValueError("Failed")
        
        tasks = [
            TaskSpec(func=fail_task, description="Fails"),
            TaskSpec(func=lambda: "succeeds", description="Succeeds"),
        ]
        
        result = await executor.execute_parallel(tasks, merge_strategy=MergeStrategy.CONCAT)
        
        assert "succeeds" in result.merged_content
        assert len(result.merged_content) > 0  # Should have some content even with failures


class TestSpeedEstimation:
    """Test speedup estimation functions"""
    
    def test_estimate_speedup_single_task(self):
        """Test speedup estimation for single task (no benefit)"""
        estimate = ParallelExecutor.estimate_speedup(task_count=1, avg_task_time=2.0)
        
        assert estimate["speedup_factor"] == 1.0
        assert estimate["recommendation"] == "not_needed"
        assert estimate["estimated_serial_time"] == 2.0
        assert estimate["estimated_parallel_time"] == 2.0
    
    def test_estimate_speedup_multiple_fast_tasks(self):
        """Test speedup estimation for multiple fast tasks (not worthwhile)"""
        estimate = ParallelExecutor.estimate_speedup(task_count=3, avg_task_time=0.1)
        
        assert estimate["recommendation"] in ["not_worthwhile", "recommended", "highly_recommended"]
        assert estimate["speedup_factor"] >= 1.0
    
    def test_estimate_speedup_multiple_slow_tasks(self):
        """Test speedup estimation for multiple slow tasks (highly recommended)"""
        estimate = ParallelExecutor.estimate_speedup(task_count=5, avg_task_time=5.0)
        
        assert estimate["estimated_serial_time"] == 25.0
        assert estimate["speedup_factor"] > 1.5
        assert estimate["recommendation"] in ["recommended", "highly_recommended"]
    
    def test_estimate_speedup_many_tasks(self):
        """Test speedup estimation for many tasks"""
        estimate = ParallelExecutor.estimate_speedup(task_count=10, avg_task_time=2.0)
        
        assert estimate["estimated_serial_time"] == 20.0
        assert estimate["effective_parallelism"] == 3  # DEFAULT_MAX_CONCURRENT
        assert estimate["speedup_factor"] <= 3.0  # Can't exceed max concurrent
    
    def test_speedup_calculation_in_real_execution(self):
        """Test actual speedup calculation from parallel execution"""
        executor = ParallelExecutor(max_concurrent=3)
        
        async def moderate_task():
            await asyncio.sleep(0.15)
            return "done"
        
        tasks = [TaskSpec(func=moderate_task, description=f"Task {i}") for i in range(4)]
        
        import asyncio as _asyncio
        
        async def run_test():
            result = await executor.execute_parallel(tasks)
            return result
        
        result = _asyncio.run(run_test())
        
        assert result.speedup_factor >= 1.0
        assert result.speedup_factor <= 4.0  # Theoretical max


class TestShouldParallelize:
    """Test _should_parallelize heuristic rules"""
    
    def setup_method(self):
        """Set up test fixtures"""
        from opc_manager.task_engine_v3 import TaskEngineV3
        self.engine = TaskEngineV3()
    
    def test_long_prompt_triggers_parallelization(self):
        """Test that prompts > 200 chars trigger parallelization"""
        long_prompt = "x" * 250
        assert self.engine._should_parallelize(long_prompt) is True
    
    def test_short_prompt_no_parallelization(self):
        """Test that short prompts don't trigger parallelization"""
        short_prompt = "帮我写个方案"
        assert self.engine._should_parallelize(short_prompt) is False
    
    def test_contrast_keyword_triggers(self):
        """Test that '对比' keyword triggers parallelization"""
        prompt = "对比分析一下市场趋势"
        assert self.engine._should_parallelize(prompt) is True
    
    def test_compare_keyword_english(self):
        """Test English 'compare' keyword triggers parallelization"""
        prompt = "Compare the market trends and competitor analysis"
        assert self.engine._should_parallelize(prompt) is True
    
    def test_comprehensive_keyword_triggers(self):
        """Test '综合' keyword triggers parallelization"""
        prompt = "综合分析各方面的数据"
        assert self.engine._should_parallelize(prompt) is True
    
    def test_multi_dimensional_keyword(self):
        """Test '多维' keyword triggers parallelization"""
        prompt = "从多维角度分析用户反馈"
        assert self.engine._should_parallelize(prompt) is True
    
    def test_data_analysis_type_always_parallelizes(self):
        """Test DATA_ANALYSIS task type triggers parallelization"""
        from opc_manager.task_types import TaskType
        prompt = "分析一下业务数据"
        assert self.engine._should_parallelize(prompt, TaskType.DATA_ANALYSIS) is True
    
    def test_content_generation_with_document_keywords(self):
        """Test CONTENT_GENERATION with document keywords triggers parallelization"""
        from opc_manager.task_types import TaskType
        prompt = "帮我写一份Q2营销报告"
        assert self.engine._should_parallelize(prompt, TaskType.CONTENT_GENERATION) is True
    
    def test_empty_prompt_returns_false(self):
        """Test empty prompt returns False"""
        assert self.engine._should_parallelize("") is False
        assert self.engine._should_parallelize(None) is False
    
    def test_simple_chat_no_parallelization(self):
        """Test simple chat doesn't trigger parallelization"""
        prompt = "你好"
        assert self.engine._should_parallelize(prompt) is False


class TestProgressCallback:
    """Test progress callback integration"""
    
    @pytest.mark.asyncio
    async def test_progress_callback_called_for_each_task(self):
        """Test that progress callback is called for each completed task"""
        progress_events = []
        
        def mock_callback(session_id, completed, total, task_result):
            progress_events.append({
                'session_id': session_id,
                'completed': completed,
                'total': total,
                'success': task_result.success,
            })
        
        executor = ParallelExecutor(
            max_concurrent=2,
            progress_callback=mock_callback,
        )
        
        async def simple_task():
            await asyncio.sleep(0.05)
            return "done"
        
        tasks = [TaskSpec(func=simple_task, description=f"Task {i}") for i in range(3)]
        
        await executor.execute_parallel(tasks, session_id="progress_test")
        
        assert len(progress_events) == 3
        assert all(e['session_id'] == "progress_test" for e in progress_events)
        assert all(e['success'] for e in progress_events)
    
    @pytest.mark.asyncio
    async def test_progress_callback_with_failures(self):
        """Test progress callback reports failures correctly"""
        progress_events = []
        
        def mock_callback(session_id, completed, total, task_result):
            progress_events.append(task_result.success)
        
        executor = ParallelExecutor(progress_callback=mock_callback)
        
        async def failing_task():
            raise ValueError("Fail")
        
        async def success_task():
            return "ok"
        
        tasks = [
            TaskSpec(func=failing_task, description="Fail"),
            TaskSpec(func=success_task, description="Success"),
        ]
        
        await executor.execute_parallel(tasks)
        
        assert len(progress_events) == 2
        assert progress_events[0] is False
        assert progress_events[1] is True


class TestAsyncSyncHandling:
    """Test handling of both async and sync functions"""
    
    @pytest.mark.asyncio
    async def test_async_function_handling(self):
        """Test that async functions are properly awaited"""
        executor = ParallelExecutor()
        
        async def async_func():
            await asyncio.sleep(0.05)
            return "async_result"
        
        tasks = [TaskSpec(func=async_func, description="Async")]
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.results[0].result == "async_result"
    
    @pytest.mark.asyncio
    async def test_sync_function_handling(self):
        """Test that sync functions run in executor without blocking"""
        executor = ParallelExecutor()
        
        def sync_func():
            time.sleep(0.05)  # Simulate blocking I/O
            return "sync_result"
        
        tasks = [TaskSpec(func=sync_func, description="Sync")]
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.results[0].result == "sync_result"
    
    @pytest.mark.asyncio
    async def test_mixed_async_sync_functions(self):
        """Test mixed async and sync functions in same batch"""
        executor = ParallelExecutor(max_concurrent=2)
        
        async def async_task():
            await asyncio.sleep(0.05)
            return "async"
        
        def sync_task():
            time.sleep(0.05)
            return "sync"
        
        tasks = [
            TaskSpec(func=async_task, description="Async"),
            TaskSpec(func=sync_task, description="Sync"),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 2
        assert set([r.result for r in result.results]) == {"async", "sync"}


class TestRetryMechanism:
    """Test retry logic for failed tasks"""
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test that tasks retry on failure"""
        executor = ParallelExecutor()
        
        attempt_count = 0
        
        async def flaky_task():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Temporary failure")
            return "success_after_retry"
        
        tasks = [
            TaskSpec(func=flaky_task, description="Flaky", retry_count=2),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.results[0].retries_used == 1
        assert result.results[0].result == "success_after_retry"
    
    @pytest.mark.asyncio
    async def test_exhaust_retries(self):
        """Test that task fails after exhausting retries"""
        executor = ParallelExecutor()
        
        async def always_fail():
            raise ValueError("Permanent failure")
        
        tasks = [
            TaskSpec(func=always_fail, description="Always fails", retry_count=2),
        ]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.failure_count == 1
        assert result.results[0].retries_used == 2


class TestMetadataAndStats:
    """Test metadata collection and statistics"""
    
    @pytest.mark.asyncio
    async def test_metadata_contains_parallel_info(self):
        """Test that result metadata contains parallel execution info"""
        executor = ParallelExecutor()
        
        async def simple_task():
            return "data"
        
        tasks = [TaskSpec(func=simple_task, description="Test")]
        result = await executor.execute_parallel(tasks, session_id="meta_test")
        
        assert result.metadata["parallel_execution"] is True
        assert result.metadata["task_count"] == 1
        assert result.metadata["session_id"] == "meta_test"
        assert "timestamp" in result.metadata
    
    @pytest.mark.asyncio
    async def test_execution_time_recorded(self):
        """Test that individual task execution times are recorded"""
        executor = ParallelExecutor()
        
        async def timed_task():
            await asyncio.sleep(0.1)
            return "timed"
        
        tasks = [TaskSpec(func=timed_task, description="Timed")]
        result = await executor.execute_parallel(tasks)
        
        assert result.results[0].execution_time_ms > 0
        assert result.total_time_ms > 0
        assert result.total_time_ms >= result.results[0].execution_time_ms
    
    def test_get_stats_returns_config(self):
        """Test get_stats() returns configuration info"""
        executor = ParallelExecutor(max_concurrent=5, default_timeout=30.0)
        stats = executor.get_stats()
        
        assert stats["max_concurrent"] == 5
        assert stats["default_timeout"] == 30.0
        assert stats["type"] == "ParallelExecutor"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    @pytest.mark.asyncio
    async def test_very_large_number_of_tasks(self):
        """Test with large number of tasks (stress test)"""
        executor = ParallelExecutor(max_concurrent=3)
        
        async def light_task():
            await asyncio.sleep(0.01)
            return "ok"
        
        tasks = [TaskSpec(func=light_task, description=f"Task {i}") for i in range(20)]
        
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 20
        assert result.speedup_factor > 1.0
    
    @pytest.mark.asyncio
    async def test_tasks_returning_none(self):
        """Test handling of tasks returning None"""
        executor = ParallelExecutor()
        
        async def none_task():
            return None
        
        tasks = [TaskSpec(func=none_task, description="None result")]
        result = await executor.execute_parallel(tasks)
        
        assert result.success_count == 1
        assert result.results[0].result is None
    
    @pytest.mark.asyncio
    async def test_tasks_returning_complex_objects(self):
        """Test handling of tasks returning complex objects"""
        executor = ParallelExecutor()
        
        async def dict_task():
            return {"key": "value", "nested": {"a": 1}}
        
        async def list_task():
            return [1, 2, 3, "four"]
        
        tasks = [
            TaskSpec(func=dict_task, description="Dict"),
            TaskSpec(func=list_task, description="List"),
        ]
        
        result = await executor.execute_parallel(tasks, merge_strategy=MergeStrategy.CONCAT)
        
        assert result.success_count == 2
        assert isinstance(result.results[0].result, dict)
        assert isinstance(result.results[1].result, list)
    
    @pytest.mark.asyncio
    async def test_zero_timeout_raises_error(self):
        """Test that zero timeout raises ValueError"""
        with pytest.raises(ValueError, match="default_timeout must be positive"):
            ParallelExecutor(default_timeout=0)
    
    @pytest.mark.asyncio
    async def test_negative_concurrency_raises_error(self):
        """Test that negative concurrency raises ValueError"""
        with pytest.raises(ValueError, match="max_concurrent must be at least 1"):
            ParallelExecutor(max_concurrent=-1)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
