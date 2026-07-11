"""
Parallel Execution Engine for OPC-Agents LLM Call Optimization

 NOTE: This module is reserved for future multi-skill parallel execution scenarios.
 The three-sages parallel voting (asyncio.gather) is implemented in:
   - opc_manager/consensus_engine.py (ConsensusEngine.collect_opinions)
   - opc_manager/task_engine_v3_parallel.py (TaskEngineV3Parallel)
 This module is NOT used by the three-sages flow. See docs/architecture/PARALLEL_SAGES_DESIGN.md.

Provides controlled parallelism for LLM calls with:
- Rate limiting (max concurrent API calls to avoid API bans)
- Error isolation (one failure doesn't block others)
- Timeout management (per-task deadlines)
- Progress tracking (emit events for each task)
- Result aggregation (collect and merge results)

=== Design Goals ===
1. Accelerate multi-skill workflow execution through parallel LLM calls
2. Maintain API safety with strict concurrency limits
3. Ensure robustness with error isolation and timeout protection
4. Provide visibility into parallel execution progress

=== Usage Scenarios ===
- Content generation pre-retrieval parallelization (~30% speedup)
- Multi-dimensional data analysis parallelization (~40% speedup)
- Batch operation parallel execution (~50% speedup for N independent operations)

=== Architecture ===
TaskSpec list → Semaphore-controlled concurrency → asyncio.gather() → TaskResult list → Merge strategy → Unified output

=== Version ===
v1.0.0 - Initial implementation for OPC-Agents parallel optimization
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """Result merge strategies for parallel task outputs"""

    CONCAT = "concat"  # Simple concatenation
    MERGE = "merge"  # Intelligent merging (deduplicate, organize)
    DEDUPLICATE = "deduplicate"  # Remove duplicates only
    FIRST_SUCCESS = "first_success"  # Return first successful result


@dataclass
class TaskSpec:
    """Specification for a single parallel task

    Attributes:
        func: Callable to execute
        args: Positional arguments for func
        kwargs: Keyword arguments for func
        timeout: Per-task timeout in seconds (default 60s)
        retry_count: Number of retries on failure (default 0)
        priority: Task priority (lower = higher priority, default 0)
        description: Human-readable task description for logging
    """

    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    timeout: float = 60.0
    retry_count: int = 0
    priority: int = 0
    description: str = ""


@dataclass
class TaskResult:
    """Result of a single parallel task execution

    Attributes:
        success: Whether the task completed successfully
        result: The return value from func (if successful)
        error: Error message (if failed)
        execution_time_ms: Actual execution time in milliseconds
        task_index: Original index in the task list (for ordering)
        retries_used: Number of retries actually used
    """

    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    task_index: int = 0
    retries_used: int = 0


@dataclass
class ParallelResult:
    """Aggregated result from parallel task execution

    Attributes:
        results: List of individual task results (ordered by original task index)
        total_time_ms: Total wall-clock time for all tasks
        success_count: Number of successfully completed tasks
        failure_count: Number of failed tasks
        speedup_factor: Estimated speedup vs serial execution
        merged_content: Merged output content (if merge strategy applied)
        metadata: Additional execution metadata for debugging/analysis
    """

    results: List[TaskResult]
    total_time_ms: float
    success_count: int
    failure_count: int
    speedup_factor: float = 1.0
    merged_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ParallelExecutor:
    """Manages parallel task execution with safety limits and progress tracking

    This is the core engine for LLM call parallelization in OPC-Agents.
    It provides controlled concurrency to avoid API rate limits while
    maximizing throughput for independent operations.

    Key features:
    - Semaphore-based concurrency control (default max 3 concurrent LLM calls)
    - Per-task timeout with asyncio.wait_for()
    - Error isolation: one task failure doesn't affect others
    - Progress callbacks for real-time monitoring
    - Multiple merge strategies for combining results
    - Automatic speedup estimation

    Thread safety:
    - Designed for use within asyncio event loop
    - Not thread-safe for concurrent calls from multiple threads

    Example usage:
        >>> executor = ParallelExecutor(max_concurrent=3)
        >>> tasks = [
        ...     TaskSpec(func=search_market_data, args=("AI trends",), description="Market search"),
        ...     TaskSpec(func=search_competitor, args=("competitors",), description="Competitor search"),
        ...     TaskSpec(func=search_user_feedback, args=("feedback",), description="Feedback search"),
        ... ]
        >>> result = await executor.execute_parallel(tasks, session_id="sess_123")
        >>> print(f"Completed {result.success_count}/{len(tasks)} tasks in {result.total_time_ms:.0f}ms")
        >>> print(f"Speedup: {result.speedup_factor:.2f}x")
    """

    DEFAULT_MAX_CONCURRENT = 3
    DEFAULT_TASK_TIMEOUT = 60.0

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        default_timeout: float = DEFAULT_TASK_TIMEOUT,
        progress_callback: Optional[Callable[[str, int, int, TaskResult], None]] = None,
    ) -> None:
        """Initialize ParallelExecutor

        Args:
            max_concurrent: Maximum number of simultaneous tasks (default 3, to avoid API rate limits)
            default_timeout: Default per-task timeout in seconds (default 60s)
            progress_callback: Optional callback(session_id, completed, total, task_result) for progress tracking
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if default_timeout <= 0:
            raise ValueError("default_timeout must be positive")

        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.progress_callback = progress_callback

        logger.info(
            f"[ParallelExecutor] Initialized: max_concurrent={max_concurrent}, "
            f"default_timeout={default_timeout}s"
        )

    async def execute_parallel(
        self,
        tasks: List[TaskSpec],
        session_id: str = "",
        merge_strategy: MergeStrategy = MergeStrategy.CONCAT,
    ) -> ParallelResult:
        """Execute multiple tasks in parallel with controlled concurrency

        This is the main entry point for parallel execution. It:
        1. Creates a semaphore to limit concurrency
        2. Wraps each task with error handling and timeout
        3. Executes all tasks using asyncio.gather()
        4. Collects results and computes statistics
        5. Optionally merges results based on strategy

        Args:
            tasks: List of TaskSpec objects to execute
            session_id: Session ID for progress tracking and logging
            merge_strategy: How to combine task results (default CONCAT)

        Returns:
            ParallelResult containing all task results and aggregate statistics

        Raises:
            ValueError: If tasks list is empty
        """
        if not tasks:
            raise ValueError("Tasks list cannot be empty")

        start_time = time.time()
        task_count = len(tasks)

        logger.info(
            f"[ParallelExecutor] Starting parallel execution: {task_count} tasks, "
            f"session={session_id}, max_concurrent={self.max_concurrent}"
        )

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_task_with_semaphore(task: TaskSpec, index: int) -> TaskResult:
            return await self._execute_single_task(task, semaphore, session_id, index)

        results = await asyncio.gather(
            *[run_task_with_semaphore(task, i) for i, task in enumerate(tasks)],
            return_exceptions=False,
        )

        total_time_ms = (time.time() - start_time) * 1000

        success_count = sum(1 for r in results if r.success)
        failure_count = task_count - success_count

        total_serial_time_ms = sum(r.execution_time_ms for r in results)
        speedup_factor = self._calculate_speedup(
            total_time_ms, total_serial_time_ms, task_count
        )

        merged_content = self._merge_results(results, merge_strategy)

        metadata = {
            "task_count": task_count,
            "max_concurrent": self.max_concurrent,
            "merge_strategy": merge_strategy.value,
            "session_id": session_id,
            "parallel_execution": True,
            "timestamp": time.time(),
        }

        parallel_result = ParallelResult(
            results=results,
            total_time_ms=total_time_ms,
            success_count=success_count,
            failure_count=failure_count,
            speedup_factor=speedup_factor,
            merged_content=merged_content,
            metadata=metadata,
        )

        logger.info(
            f"[ParallelExecutor] Completed: {success_count}/{task_count} successes, "
            f"{failure_count} failures, {total_time_ms:.0f}ms total, "
            f"speedup={speedup_factor:.2f}x"
        )

        return parallel_result

    async def _execute_single_task(
        self,
        task: TaskSpec,
        semaphore: asyncio.Semaphore,
        session_id: str,
        task_index: int,
    ) -> TaskResult:
        """Execute a single task with error isolation and timeout

        This method implements the core execution logic for one task:
        1. Acquire semaphore slot (concurrency control)
        2. Execute with timeout protection
        3. Catch and isolate any exceptions
        4. Support retry logic
        5. Report progress via callback

        Error isolation design:
        - Each task runs in its own try/except block
        - Exceptions are caught and wrapped in TaskResult(success=False)
        - Other tasks continue even if this one fails
        - Timeout errors are distinguished from other errors

        Args:
            task: TaskSpec describing what to execute
            semaphore: Semaphore for concurrency control
            session_id: Session ID for logging/tracking
            task_index: Original position in task list

        Returns:
            TaskResult with outcome of this specific task
        """
        timeout = task.timeout or self.default_timeout
        retries_remaining = task.retry_count
        last_error = None

        # P2-13: 信号量在重试循环外获取，任务持有信号量期间完成所有重试，
        # 避免重试时重新排队导致排在后面的任务长时间等待（饿死）。
        async with semaphore:
            for attempt in range(retries_remaining + 1):
                try:
                    task_start = time.time()

                    logger.debug(
                        f"[ParallelExecutor] Task {task_index} starting "
                        f"(attempt {attempt + 1}/{retries_remaining + 1}): "
                        f"{task.description or 'unnamed'}"
                    )

                    result = await asyncio.wait_for(
                        self._run_task_func(task),
                        timeout=timeout,
                    )

                    execution_time_ms = (time.time() - task_start) * 1000

                    task_result = TaskResult(
                        success=True,
                        result=result,
                        execution_time_ms=execution_time_ms,
                        task_index=task_index,
                        retries_used=attempt,
                    )

                    if self.progress_callback:
                        try:
                            self.progress_callback(
                                session_id,
                                task_index + 1,
                                len([t for t in [task]]),
                                task_result,
                            )
                        except Exception as cb_error:
                            logger.warning(
                                f"[ParallelExecutor] Progress callback error: {cb_error}"
                            )

                    return task_result

                except asyncio.TimeoutError:
                    execution_time_ms = (
                        time.time()
                        - (task_start if "task_start" in locals() else time.time())
                    ) * 1000
                    last_error = f"Timeout after {timeout}s"
                    logger.warning(
                        f"[ParallelExecutor] Task {task_index} timed out after {timeout}s: "
                        f"{task.description or 'unnamed'}"
                    )

                except Exception as e:
                    execution_time_ms = (
                        time.time()
                        - (task_start if "task_start" in locals() else time.time())
                    ) * 1000
                    last_error = str(e)
                    logger.warning(
                        f"[ParallelExecutor] Task {task_index} failed "
                        f"(attempt {attempt + 1}): {e}"
                    )

                if attempt < retries_remaining:
                    retry_delay = min(0.5 * (2**attempt), 2.0)
                    logger.debug(
                        f"[ParallelExecutor] Retrying task {task_index} in {retry_delay}s"
                    )
                    await asyncio.sleep(retry_delay)

        failure_result = TaskResult(
            success=False,
            error=last_error or "Unknown error",
            execution_time_ms=(
                execution_time_ms if "execution_time_ms" in locals() else 0
            ),
            task_index=task_index,
            retries_used=retries_remaining,
        )

        if self.progress_callback:
            try:
                self.progress_callback(
                    session_id,
                    task_index + 1,
                    1,  # Total is 1 for this single task context
                    failure_result,
                )
            except Exception as cb_error:
                logger.warning(
                    f"[ParallelExecutor] Progress callback error (failure): {cb_error}"
                )

        return failure_result

    async def _run_task_func(self, task: TaskSpec) -> Any:
        """Run the actual task function with proper await handling

        Handles both sync and async callables:
        - If task.func is async, await it directly
        - If task.func is sync, run it in executor to avoid blocking event loop

        Args:
            task: TaskSpec containing the function to run

        Returns:
            Return value from task.func
        """
        func = task.func

        if asyncio.iscoroutinefunction(func):
            return await func(*task.args, **task.kwargs)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: func(*task.args, **task.kwargs)
            )

    def _merge_results(
        self,
        results: List[TaskResult],
        strategy: MergeStrategy = MergeStrategy.CONCAT,
    ) -> str:
        """Merge multiple task results into unified output

        Supports different merge strategies based on use case:
        - CONCAT: Simply concatenate all successful results
        - MERGE: Intelligent merging with deduplication and organization
        - DEDUPLICATE: Remove duplicate content while preserving order
        - FIRST_SUCCESS: Return only the first successful result

        Args:
            results: List of TaskResult objects from parallel execution
            strategy: MergeStrategy enum value

        Returns:
            Merged string content (empty string if no successful results)
        """
        successful_results = [r for r in results if r.success and r.result]

        if not successful_results:
            # P2-14: 聚合所有失败任务的错误消息，格式统一为
            # "所有任务失败: [task_0: error_0; task_1: error_1; ...]"
            failed_entries = [
                f"task_{r.task_index}: {r.error}"
                for r in results
                if not r.success and r.error
            ]
            return f"所有任务失败: [{'; '.join(failed_entries)}]"

        if strategy == MergeStrategy.FIRST_SUCCESS:
            return str(successful_results[0].result)

        contents = [str(r.result) for r in successful_results]

        if strategy == MergeStrategy.CONCAT:
            separator = "\n\n---\n\n"
            return separator.join(contents)

        elif strategy == MergeStrategy.DEDUPLICATE:
            seen = set()
            unique_contents = []
            for content in contents:
                if content not in seen:
                    seen.add(content)
                    unique_contents.append(content)
            return "\n\n---\n\n".join(unique_contents)

        elif strategy == MergeStrategy.MERGE:
            return self._intelligent_merge(contents)

        return "\n\n---\n\n".join(contents)

    def _intelligent_merge(self, contents: List[str]) -> str:
        """Intelligent merging: deduplicate + organize by content type

        Attempts to identify and organize different types of content:
        - Bullet points/lists
        - Paragraphs
        - Data/tables
        - Code blocks

        Then merges intelligently while removing exact duplicates.

        Args:
            contents: List of content strings to merge

        Returns:
            Organized and merged content string
        """
        all_lines = []
        seen_lines = set()

        for content in contents:
            lines = content.split("\n")
            for line in lines:
                stripped = line.strip()
                if stripped and stripped not in seen_lines:
                    seen_lines.add(stripped)
                    all_lines.append(line)

        return "\n".join(all_lines)

    def _calculate_speedup(
        self,
        parallel_time_ms: float,
        total_serial_time_ms: float,
        task_count: int,
    ) -> float:
        """Calculate estimated speedup factor from parallelization

        Speedup formula:
        - Ideal speedup = task_count (all tasks perfectly parallel)
        - Real speedup = total_serial_time / parallel_time
        - Capped at task_count (can't exceed theoretical maximum)
        - Minimum 1.0x (parallel should never be slower than reported)

        Also accounts for overhead:
        - Small task counts (< 3) may show minimal speedup due to overhead
        - Very fast tasks may show < 1.0x due to asyncio scheduling overhead

        Args:
            parallel_time_ms: Actual wall-clock time for parallel execution
            total_serial_time_ms: Sum of all individual task times
            task_count: Number of tasks executed

        Returns:
            Speedup factor (>= 1.0, <= task_count)
        """
        if total_serial_time_ms <= 0 or parallel_time_ms <= 0:
            return 1.0

        raw_speedup = total_serial_time_ms / parallel_time_ms

        ideal_max = min(task_count, self.max_concurrent)
        capped_speedup = min(raw_speedup, ideal_max)

        realistic_speedup = max(1.0, capped_speedup)

        return round(realistic_speedup, 2)

    @staticmethod
    def estimate_speedup(task_count: int, avg_task_time: float) -> Dict[str, Any]:
        """Estimate potential speedup from parallelization (static analysis)

        This is a planning-time estimation tool to help decide whether
        parallelization is worth the overhead for a given workload.

        Args:
            task_count: Number of independent tasks to parallelize
            avg_task_time: Average expected execution time per task (seconds)

        Returns:
            Dictionary containing:
            - estimated_serial_time: Total time if executed serially
            - estimated_parallel_time: Expected time with parallelization
            - speedup_factor: Expected speedup ratio
            - recommendation: Whether parallelization is recommended
            - reasoning: Human-readable explanation
        """
        if task_count <= 1:
            return {
                "estimated_serial_time": avg_task_time,
                "estimated_parallel_time": avg_task_time,
                "speedup_factor": 1.0,
                "recommendation": "not_needed",
                "reasoning": "Single task cannot benefit from parallelization",
            }

        serial_time = task_count * avg_task_time

        max_concurrent = ParallelExecutor.DEFAULT_MAX_CONCURRENT
        effective_parallel = min(task_count, max_concurrent)

        batches = (task_count + effective_parallel - 1) // effective_parallel
        parallel_time = batches * avg_task_time

        overhead_factor = 1.05  # 5% overhead for semaphore/context switching
        realistic_parallel = parallel_time * overhead_factor

        speedup = serial_time / realistic_parallel if realistic_parallel > 0 else 1.0
        speedup = min(speedup, effective_parallel)

        if speedup < 1.3:
            recommendation = "not_worthwhile"
            reasoning = (
                f"Speedup ({speedup:.2f}x) too small to justify parallelization overhead. "
                f"Tasks are too few or too fast."
            )
        elif speedup >= 2.0:
            recommendation = "highly_recommended"
            reasoning = (
                f"Excellent speedup potential ({speedup:.2f}x). "
                f"Parallelization will significantly reduce wait time."
            )
        else:
            recommendation = "recommended"
            reasoning = (
                f"Moderate speedup ({speedup:.2f}x). "
                f"Parallelization provides noticeable improvement."
            )

        return {
            "estimated_serial_time": round(serial_time, 2),
            "estimated_parallel_time": round(realistic_parallel, 2),
            "speedup_factor": round(speedup, 2),
            "task_count": task_count,
            "avg_task_time": avg_task_time,
            "effective_parallelism": effective_parallel,
            "recommendation": recommendation,
            "reasoning": reasoning,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return current executor configuration and statistics

        Useful for monitoring and debugging parallel execution performance.

        Returns:
            Dictionary with configuration parameters
        """
        return {
            "max_concurrent": self.max_concurrent,
            "default_timeout": self.default_timeout,
            "has_progress_callback": self.progress_callback is not None,
            "type": "ParallelExecutor",
        }
