"""
LLM-Enhanced Content Generator v3.5 — P0-2 Content Intelligence Upgrade

Core problem solved:
- Generic template placeholders like "基准值待测", "提升30%", "待填写"
- User provides specific business info (AI writing assistant, MAU 5000→10000) but output completely ignores it

=== Design Decision (ADR-009) ===
Decision: RAG hybrid mode (template skeleton + LLM fill), not pure LLM or pure template
Reasons:
  1. Templates guarantee structural consistency and controllable output format
  2. LLM injects business specificity, eliminating generic filler
  3. Degrades automatically to v3.4 pure template mode, ensuring no crashes

=== Core Architecture ===
  User input + Search results
    ↓
  Step 1: _extract_business_info() → Extract product name/numbers/industry/goals
    ↓
  Step 2: _gen_skeleton() → Structural skeleton (reuse v3.4 logic)
    ↓
  Step 3: _build_context() → Search reference material summary
    ↓
  Step 4: _build_prompt() → Assemble prompt with constraints
    ↓
  Step 5: _call_llm_api() → Call GLM-4 to generate content
    ↓ [Success]
  Output: Complete targeted document (zero placeholders)
    ↓ [Failure/Timeout]
  Fallback: _fill_template() → v3.4 template + search data fill

=== Iron Rules (Must Not Be Violated) ===
1. Absolutely no placeholders (___, 待填写, 此处插入, 基准值待测)
2. Absolutely no empty frameworks (清晰定义目标, 明确边界 - such filler)
3. User-provided specific information must appear in output
4. Degraded mode must also satisfy the above three rules

=== Architecture (Mixin-based facade) ===
LLMEnhancedContentGenerator is now a facade composing two mixins (each in its own
module):
  - LLMContentPromptMixin   (opc_manager.llm_content_prompt)
    — _extract_business_info / _build_context / _build_prompt /
      _format_business_info / _enforce_structure / _clean_placeholders /
      _count_placeholders / _check_business_info_injected
  - LLMContentGenerationMixin (opc_manager.llm_content_generation)
    — _try_llm_generation / _call_llm_api / _get_llm_config /
      _get_llm_api_key / _calculate_quality_score / _quality_gate /
      _redact_secrets
This facade retains __init__, _detect_language, is_available, generate (public
entry), _fallback_to_template, check_prompt_injection — the public API is 100%
backward compatible.

Module-level constants FORBIDDEN_PATTERNS / BUSINESS_INFO_PATTERNS /
LANGUAGE_INSTRUCTIONS live in the prompt mixin (used only there);
MAX_LLM_OUTPUT_LENGTH lives in the generation mixin. FORBIDDEN_PATTERNS is
re-exported from this facade via __all__ for backward compatibility.
GenerationResult (dataclass) and _sanitize_url remain in this facade and are
defined BEFORE the mixin imports so the generation mixin can safely do
`from .llm_content import GenerationResult` without a circular-import error.

=== Version History ===
  v3.5.0: Initial version, RAG hybrid mode + degradation protection + placeholder scanning gate
"""

import re
import time
import logging
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = [
    "LLMEnhancedContentGenerator",
    "GenerationResult",
    "_sanitize_url",
    "FORBIDDEN_PATTERNS",
]

PROMPT_INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard all above",
    "you are now",
    "new instructions:",
]


def _sanitize_url(url: str) -> str:
    """Sanitize URL to prevent javascript: and non-HTTP scheme injection

    Extracted from InputValidator to avoid circular import between
    llm_content.py and task_engine_v3.py.

    Args:
        url: URL string to validate

    Returns:
        Original URL if valid http/https scheme, empty string otherwise
    """
    if not url:
        return ""
    lower = url.lower().strip()
    if lower.startswith(("javascript:", "data:", "vbscript:", "blob:")):
        return ""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", ""):
        return ""
    return url


@dataclass
class GenerationResult:
    """Content generation result container

    Design intent:
    - Unified return format so callers don't need to know if LLM or template generated
    - fallback_used flag indicates whether degraded mode was used (for monitoring and debugging)
    - quality_score provides content quality rating (for A/B test comparison)
    """

    content: str
    success: bool
    fallback_used: bool = False
    generation_mode: str = "unknown"
    llm_latency_ms: float = 0.0
    quality_score: float = 0.0
    placeholder_count: int = 0
    business_info_injected: List[str] = field(default_factory=list)
    quality_gate_passed: bool = True


# GenerationResult is defined ABOVE so the mixin modules can safely do
# `from .llm_content import GenerationResult` without triggering a
# circular-import error at load time. FORBIDDEN_PATTERNS is re-exported from
# the prompt mixin (added to __all__ above) to preserve backward-compatible
# import sites.
from .llm_content_prompt import (  # noqa: E402
    LLMContentPromptMixin,
    FORBIDDEN_PATTERNS,
)
from .llm_content_generation import LLMContentGenerationMixin  # noqa: E402


class LLMEnhancedContentGenerator(LLMContentPromptMixin, LLMContentGenerationMixin):
    """LLM-Enhanced Content Generator — RAG hybrid mode solves content generalization issue

    Core capabilities:
    1. Business info extraction: Extract product name/numbers/target metrics from user input
    2. RAG hybrid generation: Template skeleton ensures structure + LLM injects business specificity
    3. Placeholder iron rule: Multi-layer filtering ensures zero placeholder output
    4. Graceful degradation: Auto-switch to v3.4 template mode when LLM unavailable
    5. Quality scoring: Output quality can be quantitatively evaluated

    Usage example:
        >>> generator = LLMEnhancedContentGenerator()
        >>> result = generator.generate(
        ...     user_input="帮我制定Q2增长方案，产品是AI写作助手，月活5000想提升到10000",
        ...     template="# Q2方案\\n\\n## 项目概览\\n{business_context}\\n",
        ...     search_results=[{'title': 'SaaS增长策略', 'snippet': '从5000到10000...'}],
        ... )
        >>> print(result.content)
        >>> print(f"Used fallback: {result.fallback_used}")

    Thread safety:
    - Stateless design (each generate() call is independent)
    - Does not depend on external mutable state
    - Safe for multi-threaded environments (e.g. AsyncTaskExecutor background thread)

    Facade composing two behavior mixins (Prompt / Generation). Cross-mixin
    calls (e.g. self._build_prompt, self._calculate_quality_score) are
    resolved at runtime on this facade instance via Python's MRO.
    """

    def __init__(
        self,
        llm_timeout: int = 30,
        max_content_length: int = 15000,
        min_fallback_length: int = 800,
        llm_caller: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self.llm_timeout = llm_timeout
        self.max_content_length = max_content_length
        self.min_fallback_length = min_fallback_length
        self._llm_caller = llm_caller

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect the dominant language of input text

        Returns:
            "zh" for Chinese, "jp" for Japanese, "en" for English (default)
        """
        jp_kana = len(re.findall(r"[\u3040-\u309F\u30A0-\u30FF]", text))
        zh_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        en_chars = len(re.findall(r"[a-zA-Z]", text))

        if jp_kana >= 2:
            return "jp"
        if zh_chars > en_chars and zh_chars >= 2:
            return "zh"
        return "en"

    def is_available(self) -> bool:
        """Check if LLM service is available

        Returns:
            bool: True means at least one LLM backend is available (API Key configured)
        """
        try:
            api_key = self._get_llm_api_key()
            return api_key is not None and len(api_key) > 0
        except Exception as e:
            logger.warning("[LLMContentGen] Availability check failed: %s", e)
            return False

    def generate(
        self,
        user_input: str,
        template: str,
        search_results: Optional[List[Dict]] = None,
        business_type: Optional[str] = None,
        is_follow_up: bool = False,
        **kwargs,
    ) -> GenerationResult:
        """Main entry: RAG hybrid mode content generation

        Execution flow:
        1. Extract user business info (product name, numbers, goals)
        2. Build search result context
        3. Attempt LLM generation (with timeout and exception protection)
        4. If LLM succeeds → quality check → return
        5. If LLM fails → degrade to template fill → quality check → return

        Args:
            user_input: User's original input (contains business background info)
            template: Document template skeleton (Markdown format, may contain {variable} placeholders)
            search_results: Search result list (each element contains title/snippet/href)
            business_type: Detected business type (affects role positioning and output style)
            **kwargs: Additional parameters (passed to _fill_template or _call_llm_api)

        Returns:
            GenerationResult: Contains content/success/fallback_used etc. fields
        """
        start_time = time.time()

        # [SECURITY] Prompt injection detection (non-blocking, audit log only)
        self.check_prompt_injection(user_input)

        template = template.replace("{topic}", user_input)
        business_info = self._extract_business_info(user_input)
        context = self._build_context(search_results or [])

        try:
            result = self._try_llm_generation(
                user_input=user_input,
                template=template,
                business_info=business_info,
                context=context,
                search_results=search_results or [],
                business_type=business_type,
                is_follow_up=is_follow_up,
            )

            if result.success:
                latency_ms = (time.time() - start_time) * 1000
                result.llm_latency_ms = latency_ms
                result.placeholder_count = self._count_placeholders(result.content)
                result.business_info_injected = self._check_business_info_injected(
                    result.content, business_info
                )
                result.quality_score = self._calculate_quality_score(result)

                if result.placeholder_count > 0:
                    logger.warning(
                        f"[LLMContentGen] LLM output contains {result.placeholder_count} placeholders, "
                        f"attempting cleanup..."
                    )
                    result.content = self._clean_placeholders(result.content)
                    result.placeholder_count = self._count_placeholders(result.content)

                result.content = self._redact_secrets(result.content)
                result = self._quality_gate(
                    result, business_info, has_search_results=bool(search_results)
                )

                logger.info(
                    f"[LLMContentGen] LLM generation succeeded: "
                    f"{len(result.content)} chars, "
                    f"latency {latency_ms:.0f}ms, "
                    f"quality score {result.quality_score:.1f}"
                )
                return result

        except Exception as e:
            logger.error("[LLMContentGen] LLM generation exception: %s", e)

        fallback_result = self._fallback_to_template(
            user_input=user_input,
            template=template,
            business_info=business_info,
            context=context,
            search_results=search_results or [],
        )

        fallback_result.fallback_used = True
        fallback_result.generation_mode = "template_v34"
        fallback_result.llm_latency_ms = (time.time() - start_time) * 1000
        fallback_result.placeholder_count = self._count_placeholders(
            fallback_result.content
        )
        fallback_result.business_info_injected = self._check_business_info_injected(
            fallback_result.content, business_info
        )
        fallback_result.quality_score = self._calculate_quality_score(fallback_result)

        fallback_result.content = self._redact_secrets(fallback_result.content)
        fallback_result = self._quality_gate(
            fallback_result, business_info, has_search_results=bool(search_results)
        )

        logger.info(
            f"[LLMContentGen] Using degraded (template) mode: "
            f"{len(fallback_result.content)} chars, "
            f"quality score {fallback_result.quality_score:.1f}"
        )

        return fallback_result

    def _fallback_to_template(
        self,
        user_input: str,
        template: str,
        business_info: Dict[str, List[str]],
        context: str,
        search_results: List[Dict],
    ) -> GenerationResult:
        """Degrade to v3.4 template fill mode

        When LLM is unavailable, use pure rule engine to fill template:
        1. Replace variables in template with search result data
        2. Inject user business info
        3. Execute placeholder scan and cleanup
        4. Ensure output meets minimum quality standards

        Args:
            user_input: User input
            template: Template skeleton
            business_info: Business info
            context: Search context
            search_results: Search results

        Returns:
            GenerationResult: Template-generated result
        """
        content = template

        content = content.replace(
            "{business_context}", self._format_business_info(business_info)
        )
        content = content.replace("{search_context}", context)
        content = content.replace("{user_query}", user_input)
        content = content.replace(
            "{goals}",
            ", ".join(business_info["targets"]) or "Based on user requirements",
        )
        content = content.replace("{topic}", user_input)

        if search_results:
            refs_section = "\n\n## 参考资料\n"
            for i, sr in enumerate(search_results[:5], 1):
                title = sr.get("title", "")
                url = sr.get("href", sr.get("url", ""))
                safe_url = _sanitize_url(url)
                if safe_url:
                    refs_section += f"{i}. [{title}]({safe_url})\n"
                else:
                    refs_section += f"{i}. {title}\n"
            content += refs_section

        content = self._clean_placeholders(content)

        if len(content) < self.min_fallback_length:
            content += (
                f"\n\n---\n*Note: This document was generated by OPC-Agents v3.5 template engine. "
                f"Original user request: {user_input}\n"
            )

        success = (
            len(content) >= self.min_fallback_length
            and self._count_placeholders(content) == 0
        )

        return GenerationResult(
            content=content,
            success=success,
            generation_mode="template_v34",
        )

    @staticmethod
    def check_prompt_injection(text: str) -> List[str]:
        """Check for common prompt injection patterns and log warnings.

        Does NOT block content — only logs detected patterns for awareness.

        Args:
            text: Input text to check

        Returns:
            List of detected injection pattern strings (empty if none found)
        """
        detected = []
        text_lower = text.lower()
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern in text_lower:
                detected.append(pattern)
                logger.warning(
                    "[LLMContentGen] Prompt injection pattern detected: '%s'",
                    pattern,
                )
        return detected
