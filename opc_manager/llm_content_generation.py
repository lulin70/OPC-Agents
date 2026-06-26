"""
Generation Mixin for LLMEnhancedContentGenerator

Extracted from llm_content.py to reduce the God Class size.
Contains the LLM API / quality-evaluation methods:
- _try_llm_generation: assemble prompt and attempt LLM generation (core RAG flow)
- _call_llm_api: call the LLM backend (with cache, timeout, HTTPS checks)
- _get_llm_config: discover LLM API key/base_url/model
- _get_llm_api_key: backward-compatible API key accessor
- _calculate_quality_score: score generated content (0-100)
- _quality_gate: reject low-quality output (placeholders/length/source)
- _redact_secrets: redact API keys / tokens from generated content

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
LLMEnhancedContentGenerator inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed facade
instance:
- self._build_prompt / self._enforce_structure (LLMContentPromptMixin)
- self.llm_timeout / self._llm_caller (facade — set by __init__)

GenerationResult is imported from the facade module; the facade defines it before
importing the mixins to keep the import cycle safe (see llm_content.py).
MAX_LLM_OUTPUT_LENGTH is defined locally here (used only by _call_llm_api).
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

from .utils import _llm_thread_semaphore
from .llm_content import GenerationResult

logger = logging.getLogger(__name__)

MAX_LLM_OUTPUT_LENGTH = 50000


class LLMContentGenerationMixin:
    """Mixin class containing LLM API / quality-evaluation methods for
    LLMEnhancedContentGenerator.

    Cross-mixin calls (e.g. self._build_prompt) are resolved at runtime on the
    composed facade instance via Python's MRO.
    """

    def _try_llm_generation(
        self,
        user_input: str,
        template: str,
        business_info: Dict[str, List[str]],
        context: str,
        search_results: List[Dict],
        business_type: str = None,
        is_follow_up: bool = False,
    ) -> GenerationResult:
        """Attempt LLM generation (core RAG flow)

        Assemble prompt and call LLM API.

        Args:
            user_input: User input
            template: Template skeleton
            business_info: Extracted business info
            context: Search result context
            search_results: Raw search results
            business_type: Detected business type

        Returns:
            GenerationResult: LLM generation result or failed empty result
        """
        prompt = self._build_prompt(
            user_input=user_input,
            template=template,
            business_info=business_info,
            context=context,
            business_type=business_type,
            is_follow_up=is_follow_up,
        )

        content = self._call_llm_api(prompt)

        if content and len(content.strip()) > 200:
            return GenerationResult(
                content=self._enforce_structure(content, template),
                success=True,
                generation_mode="llm_rag",
            )

        return GenerationResult(content="", success=False, generation_mode="llm_failed")

    def _call_llm_api(self, prompt: str) -> Optional[str]:
        if self._llm_caller is not None:
            try:
                return self._llm_caller(prompt)
            except Exception as e:
                logger.warning("[LLMContentGen] Injected llm_caller failed: %s", e)
                return None

        try:
            import requests

            api_key, api_base, model = self._get_llm_config()
            if not api_base:
                logger.info(
                    "[LLMContentGen] No LLM backend configured, skipping LLM call"
                )
                return None

            _temperature = 0.7
            _max_tokens = 4000
            _system_prompt = (
                "You are a professional business consultant. Respond in the "
                "same language as the user's input. CRITICAL RULES: 1) Never "
                "skip key analysis sections with excuses like 'due to time "
                "constraints' or 'for brevity'. 2) Never fabricate data — if "
                "data is unavailable, explicitly state 'data source needed' "
                "rather than making up numbers. 3) Never give hollow "
                "suggestions like 'further research recommended' — always "
                "provide at least one concrete, actionable step."
            )

            # Try LLM cache first
            from opc_manager.llm_cache import get_llm_cache

            cache = get_llm_cache()
            if cache is not None:
                cached = cache.get(
                    model, _temperature, _max_tokens, _system_prompt, prompt
                )
                if cached is not None:
                    logger.debug("[LLMContentGen] Cache hit for prompt")
                    return cached

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": _system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": _temperature,
                "max_tokens": _max_tokens,
            }

            endpoint = f"{api_base.rstrip('/')}/chat/completions"

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            if not api_base.startswith("https://"):
                logger.warning(
                    "[LLMContentGen] API base URL is not HTTPS: %s", api_base
                )

            with _llm_thread_semaphore:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.llm_timeout,
                )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if len(content) > MAX_LLM_OUTPUT_LENGTH:
                    logger.warning(
                        "[LLMContentGen] LLM output truncated: %d -> %d chars",
                        len(content),
                        MAX_LLM_OUTPUT_LENGTH,
                    )
                    content = content[:MAX_LLM_OUTPUT_LENGTH]
                logger.info(
                    f"[LLMContentGen] LLM API call succeeded ({model}), returned {len(content)} chars"
                )
                # Cache the response
                if cache is not None:
                    cache.put(
                        model,
                        _temperature,
                        _max_tokens,
                        _system_prompt,
                        prompt,
                        content,
                        provider=api_base,
                    )
                return content
            else:
                logger.warning(
                    f"[LLMContentGen] LLM API returned error: "
                    f"{response.status_code} - {response.text[:200]}"
                )
                return None

        except ImportError:
            logger.debug("[LLMContentGen] requests library not available")
            return None
        except Exception as e:
            logger.error("[LLMContentGen] LLM API call exception: %s", e)
            return None

    def _get_llm_config(self) -> Tuple[Optional[str], str, str]:
        from opc_manager.simple_llm_service import discover_llm_config

        config = discover_llm_config()
        api_key = config["api_key"] or None
        api_base = config["base_url"]
        model = config["model"]
        if api_key or api_base:
            logger.info(
                "[LLMContentGen] Using LLM config: base=%s, model=%s", api_base, model
            )
        return api_key, api_base, model

    def _get_llm_api_key(self) -> Optional[str]:
        """Get LLM API Key (backward compatible interface)"""
        key, _, _ = self._get_llm_config()
        return key

    def _calculate_quality_score(self, result: GenerationResult) -> float:
        """Calculate content quality score (0-100)

        Scoring dimensions:
        - Length score (0-25): Longer content is more likely to be rich
        - Placeholder penalty (0-25): -5 points per placeholder
        - Business info injection (0-25): More key info injected is better
        - Degradation penalty (0-25): -15 points for degraded mode
        """
        score = 50.0

        length = len(result.content)
        if length > 3000:
            score += 25
        elif length > 1500:
            score += 18
        elif length > 800:
            score += 10

        score -= min(result.placeholder_count * 5, 25)

        injection_rate = 0
        total_info_items = len(result.business_info_injected)
        if total_info_items > 0:
            injection_rate = min(total_info_items / 4.0, 1.0)
        score += injection_rate * 25

        if result.fallback_used:
            score -= 15

        return max(0, min(100, score))

    def _quality_gate(
        self,
        result: "GenerationResult",
        business_info: Dict[str, List[str]],
        has_search_results: bool = False,
    ) -> "GenerationResult":
        """Deliverable quality gate — reject low-quality output

        Gate conditions:
        1. Zero placeholders (placeholder_count == 0)
        2. Minimum length >= 300 chars
        3. At least 1 data source reference (URL or search citation)
           — Only enforced when search results were provided to the generator.
           When LLM generates from its own knowledge (no search results),
           the source requirement is relaxed since no external data was used.

        If gate fails:
        - Log warning with specific failure reason
        - Append quality notice to content
        - Does NOT retry (retry is handled by AsyncTaskExecutor)

        Args:
            result: Generation result to check
            business_info: Extracted business info for context
            has_search_results: Whether search results were provided for generation

        Returns:
            GenerationResult with quality_gate_passed flag set
        """
        failures = []

        if result.placeholder_count > 0:
            failures.append(f"placeholders={result.placeholder_count}")

        if len(result.content) < 300:
            failures.append(f"length={len(result.content)}<300")

        if has_search_results:
            has_source = bool(re.search(r"https?://\S+", result.content)) or bool(
                re.search(
                    r"来源|参考|引用|出处|source|ref", result.content, re.IGNORECASE
                )
            )
            if not has_source:
                failures.append("no_data_source")

        result.quality_gate_passed = len(failures) == 0

        if not result.quality_gate_passed:
            reason = ", ".join(failures)
            logger.warning(f"[LLMContentGen] Quality gate FAILED: {reason}")
            result.content += (
                f"\n\n---\n>  质量提示：此交付物未通过质量门禁（{reason}），"
                f"内容可能不够完整。建议通过多轮对话补充细节。"
            )

        return result

    def _redact_secrets(self, content: str) -> str:
        """Redact API keys and secrets from generated content

        Detects common API key patterns and replaces with [REDACTED].
        Prevents accidental leakage of credentials in deliverables.

        Args:
            content: Generated content to scan

        Returns:
            Content with secrets replaced by [REDACTED]
        """
        patterns = [
            (r"sk-proj-[a-zA-Z0-9]{20,}", "[REDACTED-API-KEY]"),
            (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED-API-KEY]"),
            (r"ghp_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-TOKEN]"),
            (r"gho_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-TOKEN]"),
            (r"ghs_[a-zA-Z0-9]{36}", "[REDACTED-GITHUB-TOKEN]"),
            (r"glm-[a-zA-Z0-9]{20,}", "[REDACTED-GLM-KEY]"),
            (r"moka/[a-zA-Z0-9\-]{10,}", "[REDACTED-MOKA-KEY]"),
            (r"AKIA[0-9A-Z]{16}", "[REDACTED-AWS-KEY]"),
            (r"Bearer\s+[a-zA-Z0-9\-._~+/]+=*", "[REDACTED-BEARER-TOKEN]"),
        ]
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        return content
