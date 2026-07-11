"""
Parallel Execution Mixin for Task Engine v3.5

Extracted from TaskEngineV3 to reduce the God Class size.
Contains parallel-execution-related methods:
- _get_parallel_executor: lazy-init ParallelExecutor instance
- _should_parallelize: heuristic decision on whether to parallelize a task
- _parallel_content_generation: parallelized content generation workflow
- _serial_content_generation: fallback serial content generation
- _parallel_data_analysis: parallelized multi-dimension data analysis
- _execute_data_analysis_serial: serial data analysis fallback

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
TaskEngineV3 inherits from this mixin, so all external callers see no change.
Cross-mixin calls (e.g. self._search, self._extract_search_query,
self._gen_real_content, self._execute_data_analysis) are resolved at runtime
via the composed TaskEngineV3 instance.
"""

import time
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Tuple, Any

from opc_manager.task_types import TaskType, TaskResult

try:
    from opc_manager.progress_emitter import ProgressEmitter, EventType, ProgressEvent

    _PROGRESS_EMITTER_AVAILABLE = True
except ImportError:
    _PROGRESS_EMITTER_AVAILABLE = False

try:
    from opc_manager.parallel_executor import (
        ParallelExecutor,
        TaskSpec,
        MergeStrategy,
    )

    _PARALLEL_EXECUTOR_AVAILABLE = True
except ImportError:
    _PARALLEL_EXECUTOR_AVAILABLE = False

logger = logging.getLogger(__name__)

# Timeout constants (seconds)
_PARALLEL_EXEC_TIMEOUT = 120
_DEFAULT_OPERATION_TIMEOUT = 60.0
_HTTP_REQUEST_TIMEOUT = 15.0

# Search result count constants
SEARCH_MAX_RESULTS_CONTENT = 5
SEARCH_MAX_RESULTS_STEP_ANALYSIS = 3


class TaskEngineParallelMixin:
    """Mixin class containing parallel-execution methods for TaskEngineV3.

    These methods accelerate content generation and data analysis by running
    independent searches/analyses concurrently via ParallelExecutor.

    Cross-mixin dependencies resolved at runtime via ``self``:
    - self._search / self._extract_search_query (TaskEngineSearchMixin)
    - self._gen_real_content (ContentGenerationMixin)
    - self._execute_data_analysis (TaskEngineExecutorsMixin)
    - self._emit_progress (TaskEngineV3 facade)
    - self._parallel_executor (instance attribute, lazy-initialized here)
    """

    # Type declarations for cross-mixin attributes/methods (provided by the
    # TaskEngineV3 facade at runtime). Declared under TYPE_CHECKING so they
    # exist only for static analysis, never at runtime.
    if TYPE_CHECKING:
        _parallel_executor: Optional[ParallelExecutor]

        def _search(
            self, query: str, max_results: int = 8
        ) -> Tuple[List[Dict], List[Dict]]: ...

        def _extract_search_query(self, user_input: str) -> str: ...

        def _gen_real_content(
            self,
            query: str,
            context: List[str],
            search_results: List[Dict],
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
            llm_query: Optional[str] = None,
        ) -> str: ...

        def _execute_data_analysis(
            self,
            search_query: str,
            llm_query: Optional[str] = None,
            business_type: Optional[str] = None,
            is_follow_up: bool = False,
        ) -> TaskResult: ...

        def _emit_progress(
            self,
            session_id: str,
            event_type: "EventType",
            message: str,
            progress_pct: Optional[int] = None,
            detail: Optional[Dict[str, Any]] = None,
        ) -> None: ...

    def _get_parallel_executor(self) -> Optional[ParallelExecutor]:
        """Get or create ParallelExecutor instance (lazy initialization)

        Design intent:
        - ParallelExecutor only created when actually needed (saves resources)
        - Configured with safe defaults to avoid API rate limits
        - Progress callback integrated for real-time monitoring

        Returns:
            ParallelExecutor instance if available, None if parallelization disabled
        """
        if not _PARALLEL_EXECUTOR_AVAILABLE:
            return None

        if self._parallel_executor is None:

            def progress_callback(
                session_id: str, completed: int, total: int, task_result
            ):
                if _PROGRESS_EMITTER_AVAILABLE and session_id:
                    try:
                        emitter = ProgressEmitter()
                        pct = int((completed / total) * 100) if total > 0 else 0
                        event = ProgressEvent(
                            event_type=EventType.STEP_PROGRESS,
                            session_id=session_id,
                            message=f"并行任务 {completed}/{total} 完成",
                            progress_pct=pct,
                            detail={
                                "task_index": completed,
                                "success": task_result.success,
                            },
                        )
                        emitter.emit(event)
                    except Exception as e:
                        logger.warning(
                            "[TaskEngineV3] Parallel progress emit failed: %s", e
                        )

            self._parallel_executor = ParallelExecutor(
                max_concurrent=3,
                default_timeout=_DEFAULT_OPERATION_TIMEOUT,
                progress_callback=progress_callback,
            )

        return self._parallel_executor

    def _should_parallelize(
        self, prompt: str, task_type: Optional[TaskType] = None
    ) -> bool:
        """Intelligent decision: should this task be parallelized?

        Uses heuristic rules to determine if parallel execution would be beneficial.
        Balances potential speedup against overhead cost.

        Decision rules (in priority order):
        1. Prompt length > 200 chars → Complex task worth parallelizing (~30% of cases)
        2. Contains multi-dimensional keywords → Analysis needs multiple data sources
        3. Scenario workflow with multiple steps → Steps may have independent sub-tasks
        4. Data analysis type → Naturally suited for multi-dimensional parallel analysis
        5. Content generation with search → Pre-retrieval can be parallelized

        Conservative approach:
        - Default to False (backward compatible)
        - Only enable when clear benefit exists
        - Avoid parallelizing simple/fast tasks (overhead > benefit)

        Args:
            prompt: User's input prompt text
            task_type: Optional task type classification

        Returns:
            True if parallelization recommended, False otherwise
        """
        if not prompt or not prompt.strip():
            return False

        if not _PARALLEL_EXECUTOR_AVAILABLE:
            return False

        clean_prompt = prompt.strip()

        if len(clean_prompt) > 200:
            logger.debug(
                "[TaskEngineV3] Parallelize: prompt length %s > 200", len(clean_prompt)
            )
            return True

        parallel_keywords = [
            "对比",
            "比较",
            "综合",
            "多维",
            "各方面",
            "分析.*趋势",
            "分析.*数据",
            "市场.*分析",
            "竞品.*分析",
            "用户.*反馈",
            "多角度",
            "compare",
            "analyze",
            "comprehensive",
            "multi-dimensional",
        ]

        import re

        for kw in parallel_keywords:
            if re.search(kw, clean_prompt, re.IGNORECASE):
                logger.debug("[TaskEngineV3] Parallelize: matched keyword '%s'", kw)
                return True

        if task_type == TaskType.DATA_ANALYSIS:
            logger.debug("[TaskEngineV3] Parallelize: DATA_ANALYSIS task type")
            return True

        if task_type == TaskType.CONTENT_GENERATION and any(
            kw in clean_prompt for kw in ["报告", "方案", "计划", "report", "plan"]
        ):
            logger.debug(
                "[TaskEngineV3] Parallelize: CONTENT_GENERATION with document keywords"
            )
            return True

        return False

    async def _parallel_content_generation(
        self, prompt: str, session_id: str = ""
    ) -> str:
        """Parallelized content generation workflow

        Optimizes content generation by:
        1. Parallel pre-retrieval: Multiple simultaneous searches for different aspects
        2. Context merging: Combine all retrieved information
        3. Single LLM call: Generate content with rich context (avoids multiple LLM calls)

        Speedup mechanism:
        - Serial: Search1(5s) → Search2(5s) → Search3(5s) → Generate(10s) = 25s
        - Parallel: [Search1+Search2+Search3](5s) → Generate(10s) = 15s (40% faster)

        Args:
            prompt: Original user prompt for content generation
            session_id: Session ID for progress tracking

        Returns:
            Generated content string (or fallback to serial if parallel fails)
        """
        executor = self._get_parallel_executor()
        if not executor:
            logger.warning(
                "[TaskEngineV3] Parallel executor unavailable, falling back to serial"
            )
            return await self._serial_content_generation(prompt, session_id)

        base_query = self._extract_search_query(prompt)

        search_tasks = [
            TaskSpec(
                func=lambda q=base_query + " 方案 案例": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="方案案例搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
            TaskSpec(
                func=lambda q=base_query + " 最佳实践 模板": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="最佳实践搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
            TaskSpec(
                func=lambda q=base_query + " 数据 趋势": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="数据趋势搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
        ]

        try:
            if _PROGRESS_EMITTER_AVAILABLE and session_id:
                self._emit_progress(
                    session_id,
                    EventType.STEP_START,
                    f" 开始并行预检索 ({len(search_tasks)}个搜索任务)",
                    progress_pct=20,
                )

            parallel_result = await executor.execute_parallel(
                search_tasks,
                session_id=session_id,
                merge_strategy=MergeStrategy.MERGE,
            )

            if _PROGRESS_EMITTER_AVAILABLE and session_id:
                self._emit_progress(
                    session_id,
                    EventType.STEP_PROGRESS,
                    f" 并行检索完成: {parallel_result.success_count}/{len(search_tasks)} 成功 "
                    f"(提速 {parallel_result.speedup_factor:.1f}x)",
                    progress_pct=50,
                    detail={
                        "parallel_execution": True,
                        "speedup_factor": parallel_result.speedup_factor,
                        "task_count": len(search_tasks),
                    },
                )

            all_results = []
            all_sources = []

            for task_result in parallel_result.results:
                if task_result.success and task_result.result:
                    results, sources = task_result.result
                    if results:
                        all_results.extend(results)
                    if sources:
                        all_sources.extend(sources)

            context_lines = []
            if all_results:
                context_lines.append("> **并行预检索结果**（来自多个信息源）:\n")
                seen_titles = set()
                for i, r in enumerate(all_results[:6], 1):
                    title = r.get("title", "")
                    if title not in seen_titles:
                        seen_titles.add(title)
                        body = r.get("body", "") or r.get("snippet", "")
                        context_lines.append(f"{i}. **{title}**: {body[:180]}\n")
                context_lines.append("\n---\n\n")

            logger.info(
                "[TaskEngineV3] Parallel pre-retrieval collected %s results from %s searches",
                len(all_results),
                parallel_result.success_count,
            )

            content = self._gen_real_content(
                prompt, context_lines, all_results, None, llm_query=prompt
            )

            result_metadata = {
                "parallel_execution": True,
                "parallel_tasks": len(search_tasks),
                "successful_searches": parallel_result.success_count,
                "speedup_factor": parallel_result.speedup_factor,
                "total_parallel_time_ms": parallel_result.total_time_ms,
                "sources_count": len(all_sources),
            }

            if hasattr(self, "_last_metadata"):
                self._last_metadata.update(result_metadata)

            return content

        except Exception as e:
            logger.error("[TaskEngineV3] Parallel content generation failed: %s", e)
            if _PROGRESS_EMITTER_AVAILABLE and session_id:
                self._emit_progress(
                    session_id,
                    EventType.ERROR,
                    f" 并行执行失败，切换到串行模式: {str(e)[:80]}",
                )
            return await self._serial_content_generation(prompt, session_id)

    async def _serial_content_generation(
        self, prompt: str, session_id: str = ""
    ) -> str:
        """Fallback serial content generation (original behavior)

        Preserved for backward compatibility and error degradation.
        """
        results, sources = self._search(
            self._extract_search_query(prompt) + " 方案 案例 最佳实践 模板",
            max_results=SEARCH_MAX_RESULTS_CONTENT,
        )

        context_lines = []
        if results:
            context_lines.append("> 参考资料（来自网络搜索）：\n")
            for i, r in enumerate(results[:3], 1):
                context_lines.append(
                    f"{i}. **{r.get('title', '')}**: {r.get('body', '')[:200]}\n"
                )
            context_lines.append("\n---\n\n")

        content = self._gen_real_content(
            prompt, context_lines, results, None, llm_query=prompt
        )
        return content

    def _emit_parallel_progress(
        self,
        session_id: str,
        event_type: Any,
        message: str,
        progress_pct: int = 0,
        detail: Optional[Dict] = None,
    ) -> None:
        """Emit progress event if progress emitter is available and session_id is set."""
        if _PROGRESS_EMITTER_AVAILABLE and session_id:
            self._emit_progress(
                session_id,
                event_type,
                message,
                progress_pct=progress_pct,
                detail=detail or {},
            )

    def _build_analysis_tasks(self, base_query: str) -> list:
        """Build parallel analysis task list (trend / compare / risk dimensions)."""
        return [
            TaskSpec(
                func=lambda q=base_query + " 趋势 发展 历史数据": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="趋势分析搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
            TaskSpec(
                func=lambda q=base_query + " 对比 竞品 行业标杆": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="对比分析搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
            TaskSpec(
                func=lambda q=base_query + " 风险 问题 挑战": self._search(
                    q, max_results=SEARCH_MAX_RESULTS_STEP_ANALYSIS
                ),
                description="风险识别搜索",
                timeout=_HTTP_REQUEST_TIMEOUT,
            ),
        ]

    def _collect_dimension_results(self, parallel_result: Any) -> Dict[str, Any]:
        """Collect dimension results from parallel execution results."""
        dimension_results: Dict[str, Any] = {}
        dimension_names = ["趋势分析", "对比分析", "风险识别"]
        for i, task_result in enumerate(parallel_result.results):
            if not (task_result.success and task_result.result):
                continue
            results, sources = task_result.result
            dimension_key = (
                dimension_names[i] if i < len(dimension_names) else f"维度{i+1}"
            )
            dimension_results[dimension_key] = {
                "results": results,
                "sources": sources,
                "findings": (
                    [
                        f"**{r.get('title', '')}**: {r.get('body', '')[:150]}"
                        for r in results[:3]
                    ]
                    if results
                    else ["需要基于实际数据进行量化分析"]
                ),
            }
        return dimension_results

    def _format_analysis_report(
        self, prompt: str, dimension_results: Dict[str, Any]
    ) -> str:
        """Format parallel analysis results into a Markdown report."""
        lines: List[str] = []
        lines.append(f"#  「{prompt}」深度并行分析\n")
        lines.append(
            f"> 分析时间: {time.strftime('%Y-%m-%d %H:%M')} | 并行维度: {len(dimension_results)}\n\n"
        )

        for dim_name, dim_data in dimension_results.items():
            lines.append(f"## {dim_name}\n\n")
            if dim_data.get("findings"):
                for finding in dim_data["findings"]:
                    lines.append(f"- {finding}\n")
            lines.append("\n")

        lines.append("## 综合洞察\n\n")
        lines.append(
            f"基于以上 {len(dimension_results)} 个维度的并行分析，提炼以下关键洞察：\n\n"
        )

        all_findings: List[str] = []
        for dim_data in dimension_results.values():
            if dim_data.get("findings"):
                all_findings.extend(dim_data["findings"])

        unique_findings = list(set(all_findings))[:5]
        for i, finding in enumerate(unique_findings, 1):
            lines.append(f"{i}. {finding}\n")

        lines.append("\n---\n*由 OPC-Agents 并行分析引擎驱动*\n")
        return "".join(lines)

    async def _parallel_data_analysis(self, prompt: str, session_id: str = "") -> str:
        """Parallelized data analysis workflow

        Accelerates multi-dimensional analysis by running different analysis
        dimensions simultaneously instead of sequentially.

        Typical dimensions:
        - Trend analysis (历史趋势、发展方向)
        - Comparative analysis (竞品对比、行业标杆)
        - Anomaly detection (异常识别、风险点)

        Speedup mechanism:
        - Serial: Trend(8s) → Compare(8s) → Anomaly(6s) → Merge(4s) = 26s
        - Parallel: [Trend+Compare+Anomaly](8s) → Merge(4s) = 12s (54% faster)

        Args:
            prompt: Original user prompt for data analysis
            session_id: Session ID for progress tracking

        Returns:
            Analysis result string (or fallback to serial if parallel fails)
        """
        executor = self._get_parallel_executor()
        if not executor:
            logger.warning(
                "[TaskEngineV3] Parallel executor unavailable for data analysis"
            )
            return self._execute_data_analysis_serial(prompt, session_id).content

        base_query = self._extract_search_query(prompt)
        analysis_tasks = self._build_analysis_tasks(base_query)

        try:
            self._emit_parallel_progress(
                session_id,
                EventType.STEP_START,
                f" 开始并行多维度分析 ({len(analysis_tasks)}个分析维度)",
                progress_pct=20,
            )

            parallel_result = await executor.execute_parallel(
                analysis_tasks,
                session_id=session_id,
                merge_strategy=MergeStrategy.MERGE,
            )

            self._emit_parallel_progress(
                session_id,
                EventType.STEP_PROGRESS,
                f" 多维度分析完成: {parallel_result.success_count}/{len(analysis_tasks)} 维度 "
                f"(提速 {parallel_result.speedup_factor:.1f}x)",
                progress_pct=60,
                detail={
                    "parallel_execution": True,
                    "speedup_factor": parallel_result.speedup_factor,
                    "dimensions_analyzed": parallel_result.success_count,
                },
            )

            dimension_results = self._collect_dimension_results(parallel_result)
            content = self._format_analysis_report(prompt, dimension_results)

            result_metadata = {
                "parallel_execution": True,
                "analysis_dimensions": len(analysis_tasks),
                "successful_dimensions": parallel_result.success_count,
                "speedup_factor": parallel_result.speedup_factor,
                "total_analysis_time_ms": parallel_result.total_time_ms,
            }
            if hasattr(self, "_last_metadata"):
                self._last_metadata.update(result_metadata)

            logger.info(
                "[TaskEngineV3] Parallel data analysis completed: %s dimensions in %.0fms",
                parallel_result.success_count,
                parallel_result.total_time_ms,
            )

            return content

        except Exception as e:
            logger.error("[TaskEngineV3] Parallel data analysis failed: %s", e)
            self._emit_parallel_progress(
                session_id,
                EventType.ERROR,
                f" 并行分析失败，切换到串行模式: {str(e)[:80]}",
            )
            return self._execute_data_analysis_serial(prompt, session_id).content

    def _execute_data_analysis_serial(
        self, search_query: str, session_id: Optional[str] = None
    ) -> TaskResult:
        """Serial data analysis fallback (preserves original behavior)"""
        return self._execute_data_analysis(search_query)
