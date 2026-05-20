"""
Search Result Post-Processor v3.5 — P0-1 Search Quality Fix

Core problem solved:
- User inputs "Q2 marketing plan", gets irrelevant results like "letter format", "novel writing", "SCI paper"
- DuckDuckGo Chinese search quality is poor, needs post-processing layer to improve relevance

=== Design Decision (ADR-008) ===
Decision: Build rule-based post-processing layer first, rather than switching search engines
Reasons:
  1. Zero cost (no API key needed, no payment required)
  2. Immediate effect (doesn't depend on third-party service stability)
  3. Stackable (this layer remains effective when switching engines in the future)
Degradation condition: Insufficient effect → then consider Baidu/Google/Bing multi-engine integration

=== Processing Pipeline ===
  Raw search results → Keyword extraction → Rule filtering → TF-IDF scoring → Sorted output
                                              ↓
                                        Results empty? → Knowledge base fallback

=== Performance Requirements ===
  - Single processing latency < 100ms (should not add noticeable delay)
  - Memory usage < 1MB (no caching of large intermediate results)

=== Version History ===
  v3.5.0: Initial version, implements keyword extraction/filtering/scoring/fallback four-step pipeline
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)

STOP_WORDS_CN = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "我",
    "有",
    "就",
    "不",
    "人",
    "都",
    "一",
    "一个",
    "上",
    "也",
    "很",
    "到",
    "说",
    "要",
    "去",
    "你",
    "会",
    "着",
    "没有",
    "看",
    "好",
    "自己",
    "这",
    "他",
    "她",
    "它",
    "们",
    "那",
    "什么",
    "怎么",
    "如何",
    "为什么",
    "哪",
    "哪个",
    "帮",
    "帮我",
    "请",
    "可以",
    "能够",
    "需要",
    "想要",
    "希望",
    "制定",
    "写",
    "做",
    "收集",
    "分析",
    "生成",
    "创建",
    "提供",
}

STOP_WORDS_EN = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "shall",
    "can",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "at",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "between",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "because",
}

_BUILTIN_KB_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "knowledge",
    "builtin_knowledge.json",
)


def _load_builtin_knowledge() -> Dict[str, list]:
    try:
        with open(_BUILTIN_KB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug("[SearchProcessor] Load builtin KB failed: %s", e)
        return {}


KNOWLEDGE_BASE = _load_builtin_knowledge()


@dataclass
class ProcessedResult:
    """Processed search result container

    Design intent:
    - Unified return format so callers don't need to know internal processing details
    - metadata records processing statistics for debugging and monitoring
    - fallback_used flag indicates whether knowledge base fallback was triggered
    """

    results: List[Dict]
    original_count: int = 0
    filtered_count: int = 0
    fallback_used: bool = False
    processing_time_ms: float = 0.0


_jieba_initialized = False


def _ensure_jieba():
    global _jieba_initialized
    if not _jieba_initialized:
        try:
            import jieba

            jieba.setLogLevel(logging.WARNING)
            _jieba_initialized = True
        except ImportError:
            pass


class SearchResultProcessor:
    """Search result post-processor — Improves DuckDuckGo Chinese search relevance

    Core capabilities:
    1. Keyword extraction: Remove stop words from Chinese queries, keep business keywords
    2. Rule filtering: Title/snippet must contain at least one query keyword
    3. TF-IDF scoring: Simplified scoring algorithm, title weight ×2 + snippet overlap
    4. Knowledge base fallback: Return predefined high-quality entries when all results are irrelevant

    Usage example:
        >>> processor = SearchResultProcessor()
        >>> result = processor.process("Q2营销方案", raw_search_results)
        >>> for item in result.results[:3]:
        ...     print(item['title'])

    Degradation strategy:
    - Empty results after processing → return original results (guaranteed no worse than v3.4)
    - Exception cases → log and return original results (don't interrupt main flow)
    """

    def __init__(
        self,
        min_keyword_match: int = 1,
        title_weight: float = 2.0,
        snippet_weight: float = 1.0,
        min_results: int = 3,
    ):
        """Initialize processor

        Args:
            min_keyword_match: Minimum number of keywords a result must match (default 1)
            title_weight: Title match weight (relative to snippet)
            snippet_weight: Snippet match weight
            min_results: Minimum number of results to return (supplement with KB if insufficient)
        """
        self.min_keyword_match = min_keyword_match
        self.title_weight = title_weight
        self.snippet_weight = snippet_weight
        self.min_results = min_results

    def process(self, query: str, raw_results: List[Dict]) -> ProcessedResult:
        """Three-step processing pipeline main entry point

        Processing steps:
        1. Extract keywords from query
        2. Rule-filter irrelevant results
        3. TF-IDF score and sort
        4. Check if knowledge base fallback is needed

        Args:
            query: User's original query (e.g. "帮我制定Q2营销方案")
            raw_results: Raw search result list from DuckDuckGo

        Returns:
            ProcessedResult: Contains processed result list and metadata
        """
        import time

        start_time = time.time()

        original_count = len(raw_results)

        if not raw_results:
            logger.warning(
                "[SearchResultProcessor] Input results empty, trying KB fallback"
            )
            fallback_results = self._fallback_to_knowledge_base(query)
            processing_time = (time.time() - start_time) * 1000
            return ProcessedResult(
                results=fallback_results,
                original_count=0,
                filtered_count=0,
                fallback_used=True,
                processing_time_ms=processing_time,
            )

        try:
            keywords = self._extract_keywords(query)
            logger.debug("[SearchResultProcessor] Extracted keywords: %s", keywords)

            filtered = self._filter_irrelevant(keywords, raw_results)
            logger.debug(
                f"[SearchResultProcessor] Filtered: {original_count}→{len(filtered)}"
            )

            scored = self._score_relevance(query, filtered, keywords)

            if len(scored) < self.min_results and original_count >= self.min_results:
                logger.info(
                    "[SearchResultProcessor] Insufficient relevant results, enabling KB fallback"
                )
                fallback_results = self._fallback_to_knowledge_base(query)
                scored = fallback_results + scored

            processing_time = (time.time() - start_time) * 1000

            if processing_time > 100:
                logger.warning(
                    f"[SearchResultProcessor] Processing time {processing_time:.1f}ms exceeds 100ms threshold"
                )

            return ProcessedResult(
                results=scored,
                original_count=original_count,
                filtered_count=(
                    original_count - len(scored) if scored else original_count
                ),
                fallback_used=len(scored) > 0
                and scored[0].get("href", "").startswith("#kb-"),
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.error(
                "[SearchResultProcessor] Processing exception, degrading to original results: %s",
                e,
            )
            processing_time = (time.time() - start_time) * 1000
            return ProcessedResult(
                results=raw_results,
                original_count=original_count,
                filtered_count=0,
                fallback_used=False,
                processing_time_ms=processing_time,
            )

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract core keywords from query

        Processing logic:
        1. Remove common prefixes ("帮我", "请", "能否" etc.)
        2. Tokenize (prefer jieba, fallback to regex + sliding window)
        3. Filter stop words (Chinese stop word list + English stop word list)
        4. Filter short words (Chinese length <2 or English length <2)
        5. Return deduplicated keyword list

        Args:
            query: User's original query

        Returns:
            Keyword list (lowercase English + original Chinese)
        """
        prefixes_to_remove = [
            "帮我",
            "请",
            "能否",
            "可以",
            "需要",
            "想要",
            "希望",
            "协助",
        ]
        cleaned = query
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
                break

        try:
            _ensure_jieba()
            import jieba

            jieba_tokens = list(jieba.cut(cleaned))
            keywords = []
            for token in jieba_tokens:
                token = token.strip()
                if not token:
                    continue
                if re.match(r"^[\u4e00-\u9fff]+$", token):
                    if len(token) >= 2 and token not in STOP_WORDS_CN:
                        keywords.append(token)
                elif re.match(r"^[a-zA-Z0-9]+$", token):
                    lower_token = token.lower()
                    if len(lower_token) >= 2 and lower_token not in STOP_WORDS_EN:
                        keywords.append(lower_token)

            seen = set()
            unique_keywords = []
            for kw in keywords:
                if kw not in seen:
                    seen.add(kw)
                    unique_keywords.append(kw)
            return unique_keywords
        except ImportError:
            pass

        tokens = re.split(
            r'[\s,，。！？、；：""' r"（）\[\]{}|\\/+_\-*&^%$#@!~`《》【】…—–·]",
            cleaned,
        )

        enhanced_tokens = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue

            parts = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]+", token)
            if parts:
                enhanced_tokens.extend(parts)
            else:
                enhanced_tokens.append(token)

        keywords = []
        for token in enhanced_tokens:
            if re.match(r"^[\u4e00-\u9fff]+$", token):
                if len(token) >= 2 and token not in STOP_WORDS_CN:
                    sub_tokens = self._split_chinese_words(token)
                    for st in sub_tokens:
                        if len(st) >= 2 and st not in STOP_WORDS_CN:
                            keywords.append(st)
            elif re.match(r"^[a-zA-Z0-9]+$", token):
                lower_token = token.lower()
                if len(lower_token) >= 2 and lower_token not in STOP_WORDS_EN:
                    keywords.append(lower_token)

        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    MAX_SLIDING_WINDOW_INPUT_LEN = 50

    def _split_chinese_words(self, text: str) -> List[str]:
        candidates = []
        n = min(len(text), self.MAX_SLIDING_WINDOW_INPUT_LEN)

        for length in [4, 3, 2]:
            if length > n:
                continue
            for i in range(n - length + 1):
                word = text[i : i + length]
                if word not in STOP_WORDS_CN:
                    candidates.append(word)

        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def _filter_irrelevant(
        self, keywords: List[str], results: List[Dict]
    ) -> List[Dict]:
        """Rule filtering: title/snippet must contain at least one query keyword

        Matching rules:
        1. Title or snippet (snippet/body) containing any keyword is considered relevant
        2. Matching is substring inclusion (not whole word), supports partial matching
        3. English keyword matching is case-insensitive

        Args:
            keywords: Query keyword list
            results: Raw search result list

        Returns:
            Filtered relevant result list
        """
        if not keywords:
            return results

        filtered = []
        for result in results:
            title = result.get("title", "").lower()
            snippet = result.get("snippet", "") or result.get("body", "").lower()
            combined_text = f"{title} {snippet}"

            match_count = sum(1 for kw in keywords if kw.lower() in combined_text)

            if match_count >= self.min_keyword_match:
                result["_relevance_score_raw"] = match_count
                filtered.append(result)

        has_meaningful_keywords = any(
            (
                len(kw) >= 3
                and not all(c in STOP_WORDS_CN or c in "的了是在这有个" for c in kw)
            )
            or (re.match(r"^[a-zA-Z]+$", kw) and len(kw) >= 3)
            or (
                re.match(r"[\u4e00-\u9fff]+$", kw)
                and len(kw) >= 2
                and kw not in STOP_WORDS_CN
            )
            for kw in keywords
        )

        if not filtered and results and not has_meaningful_keywords:
            return results

        return filtered

    def _score_relevance(
        self, query: str, results: List[Dict], keywords: List[str] = None
    ) -> List[Dict]:
        """Simplified TF-IDF scoring: title weight ×2 + snippet overlap

        Scoring formula:
        score = (title_matches × title_weight) + (snippet_matches × snippet_weight)

        Where:
        - title_matches: Number of keywords hit in title
        - snippet_matches: Number of keywords hit in snippet
        - Default weights: title_weight=2.0, snippet_weight=1.0

        Args:
            query: Original query (for re-extracting keywords to ensure consistency)
            results: Already filtered relevant result list
            keywords: Pre-extracted keywords (avoids redundant extraction)

        Returns:
            Result list sorted by score in descending order
        """
        if not results:
            return results

        if keywords is None:
            keywords = self._extract_keywords(query)

        scored_results = []
        for result in results:
            title = result.get("title", "")
            snippet = result.get("snippet", "") or result.get("body", "")

            title_matches = sum(1 for kw in keywords if kw.lower() in title.lower())
            snippet_matches = sum(1 for kw in keywords if kw.lower() in snippet.lower())

            score = (title_matches * self.title_weight) + (
                snippet_matches * self.snippet_weight
            )

            result["_relevance_score"] = score
            scored_results.append((score, result))

        scored_results.sort(key=lambda x: x[0], reverse=True)

        return [item[1] for item in scored_results]

    def _fallback_to_knowledge_base(self, query: str) -> List[Dict]:
        fallback_entries = []

        file_entries = self._search_file_knowledge_base(query)
        if file_entries:
            return file_entries

        CATEGORY_KEYWORDS = {
            "营销方案": ["营销", "推广", "获客", "增长", "内容日历"],
            "税收政策": ["税收", "税务", "合规", "财务", "发票"],
            "AI Agent": ["ai agent", "ai助手", "大模型", "llm", "agent"],
            "产品发布": ["发布", "上线", "定价", "launch", "mvp"],
            "数据分析": ["数据", "分析", "报表", "指标", "seo", "竞品"],
            "项目管理": ["项目", "管理", "协作", "提案", "远程"],
        }

        for category, entries in KNOWLEDGE_BASE.items():
            matched = category.lower() in query.lower()
            if not matched:
                keywords = CATEGORY_KEYWORDS.get(category, category.lower().split("、"))
                matched = any(kw in query.lower() for kw in keywords)

            if matched:
                for entry in entries:
                    entry_copy = entry.copy()
                    entry_copy["_kb_fallback"] = True
                    entry_copy["_kb_category"] = category
                    fallback_entries.append(entry_copy)
                logger.info(
                    f"[SearchResultProcessor] KB fallback matched category '{category}', "
                    f"returning {len(entries)} entries"
                )
                break

        if not fallback_entries:
            default_entry = {
                "title": f'关于"{query[:20]}"的专业资料',
                "snippet": (
                    "正在为您整理相关领域的专业资料和建议框架。"
                    "建议您提供更具体的背景信息以获得更精准的结果。"
                ),
                "href": "#kb-generic",
                "_kb_fallback": True,
                "_kb_category": "generic",
            }
            fallback_entries.append(default_entry)
            logger.info("[SearchResultProcessor] Using generic KB fallback")

        return fallback_entries

    def _search_file_knowledge_base(self, query: str) -> List[Dict]:
        kb_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "knowledge"
        )
        if not os.path.isdir(kb_dir):
            return []

        entries = []
        query_lower = query.lower()
        keywords = set(query_lower.replace("的", " ").replace("了", " ").split())
        keywords = {kw for kw in keywords if len(kw) >= 2}

        for filename in sorted(os.listdir(kb_dir)):
            if not filename.endswith((".md", ".txt", ".json")):
                continue
            filepath = os.path.join(kb_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read(2000)
            except Exception as e:
                logger.debug("[SearchProcessor] Read file failed: %s", e)
                continue

            from opc_manager.utils import sanitize_for_llm

            content = sanitize_for_llm(content, 1500)
            content_lower = content.lower()
            title = os.path.splitext(filename)[0]
            match_count = sum(1 for kw in keywords if kw in content_lower)
            title_match = sum(1 for kw in keywords if kw in title.lower())
            total_score = match_count * 2 + title_match * 3

            if match_count > 0 or title_match > 0:
                snippet = content[:200].replace("\n", " ").strip()
                entries.append(
                    {
                        "title": title,
                        "snippet": snippet,
                        "href": f"file://knowledge/{filename}",
                        "_kb_match_score": total_score,
                    }
                )

        entries.sort(key=lambda x: x.get("_kb_match_score", 0), reverse=True)
        for entry in entries:
            entry.pop("_kb_match_score", None)
        if entries:
            logger.info(
                "[SearchResultProcessor] File KB matched %s entries for '%s'",
                len(entries),
                query,
            )
        return entries[:10]
