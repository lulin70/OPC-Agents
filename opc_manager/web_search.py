"""
WebSearchMCP - DuckDuckGo-based web search module

Provides free web search without requiring API keys.
Falls back gracefully when network is unavailable.
"""

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

    def is_available(self) -> bool:
        """Check if search is available"""
        return self._dds is not None
