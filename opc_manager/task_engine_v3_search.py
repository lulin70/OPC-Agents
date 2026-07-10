"""
Search Mixin for Task Engine v3.5

Extracted from TaskEngineV3 to reduce the God Class size.
Contains search-related methods:
- _search: Cached search call + SearchResultProcessor post-processing
- _extract_search_query: Extract search keywords from user input

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
TaskEngineV3 inherits from this mixin, so all external callers see no change.
Cross-mixin calls (e.g. self._search_cache, self.web_search) are resolved at
runtime via the composed TaskEngineV3 instance.
"""

import re
import logging
from typing import Any, Dict, List, Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Lazy imports under TYPE_CHECKING to avoid circular imports and runtime
    # cost. These attributes are provided at runtime by the TaskEngineV3
    # facade that composes this mixin.
    from opc_manager.search_cache import SearchCache
    from opc_manager.search_processor import SearchResultProcessor

logger = logging.getLogger(__name__)


class TaskEngineSearchMixin:
    """Mixin class containing search-related methods for TaskEngineV3.

    These methods are responsible for:
    - Encapsulating WebSearchMCP calls with SearchCache integration
    - Post-processing raw search results via SearchResultProcessor (v3.5)
    - Extracting concise search keywords from natural-language user input

    Dependencies resolved at runtime via ``self``:
    - self._search_cache (SearchCache): LRU cache for search results
    - self.web_search (WebSearchMCP): Optional web search backend
    """

    if TYPE_CHECKING:
        # Attributes provided by the TaskEngineV3 facade at runtime.
        # Declared under TYPE_CHECKING so they exist only for static
        # analysis, never at runtime (consistent with task_engine_v3_executors.py).
        _search_cache: "SearchCache"
        _search_processor: Optional["SearchResultProcessor"]
        # web_search holds a WebSearchMCP instance at runtime or None before
        # lazy init; typed as Any because WebSearchMCP is an optional dep
        # and is not guaranteed importable at static-analysis time.
        web_search: Any

    def _search(
        self, query: str, max_results: int = 8
    ) -> Tuple[List[Dict], List[Dict]]:
        """Cached search call + SearchResultProcessor post-processing (v3.5 enhanced)

        Design intent:
        - Encapsulate WebSearchMCP call details, upper layers only care about query and results
        - Automatically goes through SearchCache, same query returns cache on second call
        - [v3.5 new] Automatically calls SearchResultProcessor to improve result relevance
        - Returns dual-tuple: (raw result list, refined source list)
          Raw list contains complete fields like title/body/href
          Source list only contains title/url, for displaying reference links

        Degradation strategy:
        - web_search not initialized → Return empty list (no error)
        - Search process exception → Log and return empty list (doesn't interrupt flow)
        - [v3.5 new] SearchResultProcessor exception → Return raw search results (no worse than v3.4)

        Args:
            query: Search keywords
            max_results: Maximum number of results (also part of cache key)

        Returns:
            (results, sources): Result list and source list
        """
        cached = self._search_cache.get(query, max_results)
        if cached is not None:
            sources = [
                {"title": r.get("title", ""), "url": r.get("href", "")}
                for r in cached
                if r.get("href")
            ]
            return cached, sources

        results: List[Dict] = []
        sources = []
        if not self.web_search:
            return results, sources
        try:
            raw_results = self.web_search.search(query, max_results=max_results)

            try:
                from opc_manager.search_processor import SearchResultProcessor

                if (
                    not hasattr(self, "_search_processor")
                    or self._search_processor is None
                ):
                    self._search_processor = SearchResultProcessor()
                processor = self._search_processor
                processed = processor.process(query, raw_results)
                results = processed.results if processed.results else raw_results

                if processed.fallback_used:
                    logger.info(
                        "[TaskEngineV3] Search '%s...' used KB fallback (%s items)",
                        query[:30],
                        len(results),
                    )
                elif len(results) != len(raw_results):
                    logger.info(
                        "[TaskEngineV3] Search '%s...' after processing: %s→%s items (filtered %s irrelevant)",
                        query[:30],
                        len(raw_results),
                        results,
                        len(raw_results) - len(results),
                    )
            except Exception as proc_error:
                logger.warning(
                    "[TaskEngineV3] SearchResultProcessor failed (using raw results): %s",
                    proc_error,
                )
                results = raw_results

            self._search_cache.set(query, max_results, results)
            sources = [
                {"title": r.get("title", ""), "url": r.get("href", "")}
                for r in results
                if r.get("href")
            ]
            logger.info(
                "[TaskEngineV3] Search '%s...' returned %s results",
                query[:40],
                len(results),
            )
        except Exception as e:
            logger.error("[TaskEngineV3] Search failed: %s", e)
        return results, sources

    def _extract_search_query(self, user_input: str) -> str:
        """Extract search keywords from user input

        Design intent:
        User input is typically natural language instructions (e.g. "帮我收集最新的AI趋势"),
        but search engines need concise keywords (e.g. "AI趋势").
        This method removes common instruction prefix words via regex to extract core semantics.

        Processing rules:
        1. Remove polite prefixes like "帮我"/"请"/"能不能"/"可以吗"
        2. Remove functional verbs like "收集"/"搜索"/"查找"
        3. If extraction result is empty, fall back to original input
        """
        clean = re.sub(r"^帮我?|^请|^能不能|^可以吗", "", user_input.strip())
        clean = re.sub(
            r"^(收集|搜索|查找|了解|调研|找|帮我写|帮我做|帮我生成|帮我分析)", "", clean
        )
        return clean.strip() or user_input
