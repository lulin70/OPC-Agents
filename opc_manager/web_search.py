"""
WebSearchMCP - DuckDuckGo-based web search module

Provides free web search without requiring API keys.
Falls back gracefully when network is unavailable.

E2E 测试支持: OPC_MOCK_LLM=true 时返回 Mock 搜索结果，避免网络依赖。
"""

import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class WebSearchMCP:
    """DuckDuckGo-based web search provider

    Uses the duckduckgo-search library for free, API-key-free web search.
    Falls back to empty results on any failure.
    """

    def __init__(self) -> None:
        self._dds = None
        try:
            # 优先使用新包名 ddgs
            try:
                from ddgs import DDGS
            except ImportError:
                # 兼容旧包名 duckduckgo_search
                from duckduckgo_search import DDGS  # type: ignore[assignment,no-redef]

            self._dds = DDGS()
            logger.info("[WebSearchMCP] DuckDuckGo search initialized")
        except ImportError:
            logger.warning(
                "[WebSearchMCP] ddgs/duckduckgo-search not installed, search unavailable. "
                "Install with: pip install duckduckgo-search"
            )
        except Exception as e:
            logger.warning(f"[WebSearchMCP] Initialization failed: {e}")

    def search(self, query: str, max_results: int = 8) -> List[Dict[str, str]]:
        """Search the web using DuckDuckGo

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of dicts with keys: title, href, body
        """
        # E2E 测试支持: OPC_MOCK_LLM=true 时返回 Mock 搜索结果，避免网络超时
        # 从用户角度：测试环境网络不稳定会导致搜索超时，进而整个任务失败，
        # 用户看不到成果物。Mock 搜索结果让搜索步骤"成功"，后续 Mock LLM 生成成果物。
        if os.environ.get("OPC_MOCK_LLM", "").lower() == "true":
            logger.info(
                "[WebSearchMCP] OPC_MOCK_LLM=true, returning mock search results"
            )
            return self._generate_mock_results(query, max_results)

        if not self._dds:
            logger.debug("[WebSearchMCP] Not initialized, returning empty results")
            return []

        if not query or not query.strip():
            return []

        try:
            results = []
            raw = self._dds.text(query, max_results=max_results)
            for item in raw:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "href": item.get("href", ""),
                        "body": item.get("body", ""),
                    }
                )
            logger.info(
                f"[WebSearchMCP] Search '{query[:30]}...' returned {len(results)} results"
            )
            return results
        except Exception as e:
            logger.warning(f"[WebSearchMCP] Search failed for '{query[:30]}...': {e}")
            return []

    def _generate_mock_results(
        self, query: str, max_results: int
    ) -> List[Dict[str, str]]:
        """生成 Mock 搜索结果（仅用于 E2E 测试，OPC_MOCK_LLM=true 时调用）.

        返回与查询相关的预设搜索结果，让搜索步骤成功完成，
        后续 LLM 调用能基于这些结果生成成果物。
        """
        query_preview = query[:50] if query else ""
        base_results = [
            {
                "title": f"一人公司运营指南 - 基于 \"{query_preview}\" 的实践",
                "href": "https://example.com/opc-agents/guide-2026",
                "body": (
                    "本文介绍了一人公司的运营实践，包括任务自动化、"
                    "智能分析和可视化报告等核心功能。"
                    "产品致力于解决独立创业者的效率痛点。"
                ),
            },
            {
                "title": "产品介绍文案最佳实践与模板",
                "href": "https://example.com/opc-agents/templates-2026",
                "body": (
                    "产品介绍文案应聚焦核心价值主张，明确目标用户，"
                    "突出竞争优势。参考来源：用户访谈记录 2026Q2。"
                ),
            },
            {
                "title": "AI 辅助内容生成工具对比分析",
                "href": "https://example.com/opc-agents/comparison-2026",
                "body": (
                    "对比主流 AI 内容生成工具的功能特性，"
                    "包括任务分解、质量检查和数据可视化能力。"
                ),
            },
        ]
        # 按 max_results 截断（至少返回 2 条，让搜索步骤判定为成功）
        return base_results[: max(2, min(max_results, len(base_results)))]

    def is_available(self) -> bool:
        """Check if search is available"""
        if os.environ.get("OPC_MOCK_LLM", "").lower() == "true":
            return True
        return self._dds is not None
