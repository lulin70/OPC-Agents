"""
WebSearchMCP - DuckDuckGo-based web search module

Provides free web search without requiring API keys.
Falls back gracefully when network is unavailable.

E2E 测试支持: OPC_MOCK_LLM=true 时返回 Mock 搜索结果，避免网络依赖。

可靠性（W-1）：DDGS 聚合器会间歇性抛出连接超时（实测约 1/5 概率，与查询语言无关），
瞬时抖动不应被静默降级为"零结果"。因此对失败做**有界重试**，并在重试耗尽后通过
`last_status` / `last_error` 把失败**暴露给调用方**，使其能区分"确实没搜到"与"搜索挂了"。
"""

import os
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 有界重试：初次 + 2 次重试。DDGS 超时为瞬时抖动，短退避后可显著降低"零结果"概率
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.5

# last_status 取值：调用方据此区分"确实没搜到"与"搜索挂了"
STATUS_UNSET = "UNSET"  # 尚未执行过搜索
STATUS_OK = "OK"  # 返回了结果
STATUS_EMPTY = "EMPTY"  # 搜索成功但确认零结果
STATUS_FAILED = "FAILED"  # 重试耗尽仍失败，原因见 last_error
STATUS_UNAVAILABLE = "UNAVAILABLE"  # ddgs 未安装/未初始化

# 类名关键字：命中即视为瞬时网络故障（DDGS 的 TimeoutException 并非 OSError 子类，
# 故除类型判断外还需按类名兜底）。非瞬时异常（如编程错误）不做无意义重试。
_TRANSIENT_HINTS = ("timeout", "timedout", "connection", "unavailable", "ratelimit")


def _is_transient(exc: BaseException) -> bool:
    """判断异常是否为瞬时网络故障（值得重试）。沿异常链追溯。"""
    seen: set = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError):  # 含 TimeoutError / ConnectionError
            return True
        if any(hint in type(current).__name__.lower() for hint in _TRANSIENT_HINTS):
            return True
        current = current.__cause__ or current.__context__
    return False


class WebSearchMCP:
    """DuckDuckGo-based web search provider

    Uses the duckduckgo-search library for free, API-key-free web search.
    Falls back to empty results on any failure, while recording why via
    `last_status` / `last_error` (W-1 observability).
    """

    def __init__(self) -> None:
        self._dds = None
        self.last_status: str = STATUS_UNSET
        self.last_error: Optional[str] = None
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
            self.last_status = STATUS_OK
            self.last_error = None
            return self._generate_mock_results(query, max_results)

        if not self._dds:
            logger.debug("[WebSearchMCP] Not initialized, returning empty results")
            self.last_status = STATUS_UNAVAILABLE
            self.last_error = "ddgs/duckduckgo-search 未安装或初始化失败"
            return []

        if not query or not query.strip():
            self.last_status = STATUS_EMPTY
            self.last_error = None
            return []

        last_exc: Optional[BaseException] = None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
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
                self.last_status = STATUS_OK if results else STATUS_EMPTY
                self.last_error = None
                return results
            except Exception as e:  # noqa: BLE001 — 第三方库异常类型不稳定，统一归口
                last_exc = e
                if not _is_transient(e):
                    break  # 非瞬时故障（如编程错误），重试无意义
                if attempt < RETRY_ATTEMPTS:
                    logger.warning(
                        f"[WebSearchMCP] 第 {attempt}/{RETRY_ATTEMPTS} 次搜索失败"
                        f"（{type(e).__name__}: {e}），{RETRY_DELAY_SECONDS}s 后重试"
                    )
                    time.sleep(RETRY_DELAY_SECONDS)

        # 重试耗尽仍失败：保持返回 []（兼容既有调用方），但让失败可被识别（W-1）
        self.last_status = STATUS_FAILED
        self.last_error = f"{type(last_exc).__name__}: {last_exc}"
        logger.warning(
            f"[WebSearchMCP] Search failed for '{query[:30]}...': {last_exc}"
        )
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
                "title": f'一人公司运营指南 - 基于 "{query_preview}" 的实践',
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
