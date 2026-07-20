"""LLM Backend Manager — unified multi-backend fallback scheduler.

Implements ADR-005: Ollama → Moka AI → OpenAI automatic fallback chain
with health check, circuit breaker, and cache integration.

Design references:
- docs/architecture/ADR-005-llm-backend-fallback-design.md
- HARD_CONSTRAINTS.md §2.4 (A1/A3 + 基础版 LLM 调用路径 + X-AI-Call 标头)
"""

from __future__ import annotations

import asyncio
import http.client
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from opc_manager.llm_cache import LLMCache
from opc_manager.llm_service import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMBackendError(Exception):
    """Generic LLM backend error.

    Carries an optional ``status_code`` for HTTP errors so that
    :meth:`LLMBackendManager._should_fallback` can make precise decisions
    without parsing the error message.
    """

    def __init__(self, message: str = "", status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMAllBackendsFailedError(LLMBackendError):
    """All configured backends failed — terminal fallback failure."""


class LLMBackendTimeoutError(LLMBackendError):
    """Backend call exceeded its timeout budget."""


class LLMBackendUnhealthyError(LLMBackendError):
    """Backend is marked unhealthy and was skipped."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMBackendConfig:
    """Configuration for a single LLM backend."""

    name: str  # "ollama" / "moka" / "openai"
    base_url: str
    api_key: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 30
    priority: int = 0  # lower = higher priority
    enabled: bool = True
    extra_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class BackendHealth:
    """Health status of a backend."""

    name: str
    healthy: bool
    last_check: Optional[str] = None  # ISO-8601 UTC timestamp
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    avg_latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class LLMBackendManager:
    """Unified LLM backend manager with automatic fallback.

    Implements ADR-005: Ollama → Moka AI → OpenAI fallback chain.
    Includes health check, circuit breaker, and cache integration.
    """

    HEALTH_CHECK_INTERVAL_SEC = 60
    UNHEALTHY_THRESHOLD = 3
    UNHEALTHY_RETRY_INTERVAL_SEC = 300
    HEALTH_CHECK_PROBE_TIMEOUT = 5.0
    _LATENCY_HISTORY_SIZE = 10

    _PROVIDER_MAP: Dict[str, LLMProvider] = {
        "ollama": LLMProvider.OLLAMA,
        "moka": LLMProvider.MOKA,
        "openai": LLMProvider.OPENAI,
    }

    # Default call kwargs — kept as class attrs so tests can reference them.
    DEFAULT_TEMPERATURE = 0.3
    DEFAULT_MAX_TOKENS = 500

    def __init__(
        self,
        backends: List[LLMBackendConfig],
        cache: Optional[LLMCache] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not backends:
            raise ValueError("LLMBackendManager requires at least one backend")

        enabled = [b for b in backends if b.enabled]
        if not enabled:
            raise ValueError("LLMBackendManager requires at least one enabled backend")

        # Sort by priority (lower number = higher priority = tried first).
        self._backends: List[LLMBackendConfig] = sorted(enabled, key=lambda b: b.priority)
        self._all_backends: List[LLMBackendConfig] = list(backends)

        self._cache: Optional[LLMCache] = cache
        self._transport: Optional[httpx.BaseTransport] = transport

        self._health: Dict[str, BackendHealth] = {
            b.name: BackendHealth(name=b.name, healthy=True) for b in self._backends
        }
        self._latency_history: Dict[str, List[float]] = {
            b.name: [] for b in self._backends
        }
        self._next_probe_ts: Dict[str, float] = {b.name: 0.0 for b in self._backends}

        self._lock = threading.RLock()
        self._health_check_thread: Optional[threading.Thread] = None
        self._health_check_stop = threading.Event()

    # ------------------------------------------------------------------
    # Public API — sync and async entry points
    # ------------------------------------------------------------------

    def call(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Synchronously call LLM with automatic fallback.

        Order of operations:
        1. Cache lookup — hit returns immediately.
        2. Iterate backends by priority; skip unhealthy ones (unless retry due).
        3. On success: record health, write cache, return response.
        4. On failure: record health; if ``_should_fallback`` continue, else raise.
        5. All failed → raise :class:`LLMAllBackendsFailedError`.
        """
        cached = self._cache_get(prompt, **kwargs)
        if cached is not None:
            logger.debug("[LLMBackendManager] Cache hit, skip backend call")
            return cached

        last_error: Optional[Exception] = None
        for backend in self._backends:
            if not self._is_backend_healthy(backend):
                logger.info(
                    "[LLMBackendManager] Skip unhealthy backend: %s", backend.name
                )
                continue
            try:
                response = self._try_backend(backend, prompt, **kwargs)
                self._record_health(
                    backend.name,
                    success=True,
                    latency_ms=int(response.latency_ms),
                )
                self._cache_put(prompt, response, **kwargs)
                return response
            except Exception as err:  # noqa: BLE001 — fallback decides
                last_error = err
                self._record_health(
                    backend.name,
                    success=False,
                    latency_ms=0,
                    error=str(err),
                )
                logger.warning(
                    "[LLMBackendManager] Backend %s failed: %s (fallback=%s)",
                    backend.name,
                    err,
                    self._should_fallback(err),
                )
                if not self._should_fallback(err):
                    raise
                # otherwise continue to next backend

        raise LLMAllBackendsFailedError(
            "All LLM backends failed. Last error: {}".format(last_error)
        )

    async def acall(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Asynchronously call LLM with automatic fallback.

        Reuses the synchronous :meth:`_try_backend` via :func:`asyncio.to_thread`
        so the fallback / health / cache logic is shared with :meth:`call`.
        """
        cached = self._cache_get(prompt, **kwargs)
        if cached is not None:
            logger.debug("[LLMBackendManager] Cache hit (async), skip backend call")
            return cached

        last_error: Optional[Exception] = None
        for backend in self._backends:
            if not self._is_backend_healthy(backend):
                logger.info(
                    "[LLMBackendManager] Skip unhealthy backend: %s", backend.name
                )
                continue
            try:
                response = await asyncio.to_thread(
                    self._try_backend, backend, prompt, **kwargs
                )
                self._record_health(
                    backend.name,
                    success=True,
                    latency_ms=int(response.latency_ms),
                )
                self._cache_put(prompt, response, **kwargs)
                return response
            except Exception as err:  # noqa: BLE001
                last_error = err
                self._record_health(
                    backend.name,
                    success=False,
                    latency_ms=0,
                    error=str(err),
                )
                logger.warning(
                    "[LLMBackendManager] Backend %s failed (async): %s (fallback=%s)",
                    backend.name,
                    err,
                    self._should_fallback(err),
                )
                if not self._should_fallback(err):
                    raise

        raise LLMAllBackendsFailedError(
            "All LLM backends failed. Last error: {}".format(last_error)
        )

    # ------------------------------------------------------------------
    # Backend dispatch
    # ------------------------------------------------------------------

    def _try_backend(
        self, backend: LLMBackendConfig, prompt: str, **kwargs: Any
    ) -> LLMResponse:
        """Try a single backend. Raises on failure — caller decides fallback."""
        if backend.name == "ollama":
            return self._call_ollama(backend, prompt, **kwargs)
        if backend.name == "moka":
            return self._call_openai_compatible(backend, prompt, **kwargs)
        if backend.name == "openai":
            return self._call_openai_compatible(backend, prompt, **kwargs)
        # Unknown backend name — treat as OpenAI-compatible.
        return self._call_openai_compatible(backend, prompt, **kwargs)

    def _call_ollama(
        self,
        backend: LLMBackendConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **_: Any,
    ) -> LLMResponse:
        url = f"{backend.base_url.rstrip('/')}/api/generate"
        model = backend.model or "llama3"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(temperature),
                "num_predict": int(max_tokens),
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        headers = dict(backend.extra_headers)
        start = time.time()
        try:
            with self._make_sync_client(timeout=backend.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"Ollama connection refused: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise LLMBackendTimeoutError(f"Ollama timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMBackendError(f"Ollama HTTP error: {exc}") from exc

        latency_ms = (time.time() - start) * 1000
        self._raise_for_status(resp, backend.name)

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMBackendError(
                f"Ollama returned non-JSON: {resp.text[:200]}",
                status_code=resp.status_code,
            ) from exc

        prompt_tokens = int(data.get("prompt_eval_count", 0) or 0)
        completion_tokens = int(data.get("eval_count", 0) or 0)
        return LLMResponse(
            content=data.get("response", ""),
            provider=LLMProvider.OLLAMA,
            model=model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            latency_ms=latency_ms,
            raw_response=data,
        )

    def _call_openai_compatible(
        self,
        backend: LLMBackendConfig,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        **_: Any,
    ) -> LLMResponse:
        """OpenAI-compatible chat completions — used for both Moka and OpenAI.

        Moka AI gateway expects POST directly to its ``base_url`` (which already
        includes the ``/api/v1/pro/relay/llm`` path) and requires the
        ``X-AI-Call: true`` header (configured via ``extra_headers``).
        OpenAI expects POST to ``{base_url}/chat/completions``.
        """
        # Moka's base_url is the full chat endpoint; OpenAI's needs the suffix.
        if backend.name == "moka":
            url = backend.base_url
        else:
            url = f"{backend.base_url.rstrip('/')}/chat/completions"

        model = backend.model or "gpt-4o-mini"
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": False,
        }

        headers: Dict[str, str] = dict(backend.extra_headers)
        if backend.api_key:
            headers.setdefault("Authorization", f"Bearer {backend.api_key}")
        headers.setdefault("Content-Type", "application/json")

        start = time.time()
        try:
            with self._make_sync_client(timeout=backend.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
        except httpx.ConnectError as exc:
            raise ConnectionError(f"{backend.name} connection refused: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise LLMBackendTimeoutError(f"{backend.name} timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise LLMBackendError(f"{backend.name} HTTP error: {exc}") from exc

        latency_ms = (time.time() - start) * 1000
        self._raise_for_status(resp, backend.name)

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMBackendError(
                f"{backend.name} returned non-JSON: {resp.text[:200]}",
                status_code=resp.status_code,
            ) from exc

        choices = data.get("choices") or []
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage") or {}
        provider = self._PROVIDER_MAP.get(backend.name, LLMProvider.OPENAI)
        return LLMResponse(
            content=content,
            provider=provider,
            model=model,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            },
            latency_ms=latency_ms,
            raw_response=data,
        )

    def _raise_for_status(self, resp: httpx.Response, backend_name: str) -> None:
        """Raise :class:`LLMBackendError` for 4xx/5xx responses.

        The status code is attached so :meth:`_should_fallback` can decide.
        """
        if resp.status_code < 400:
            return
        snippet = resp.text[:200] if resp.text else ""
        raise LLMBackendError(
            f"{backend_name} HTTP {resp.status_code}: {snippet}",
            status_code=resp.status_code,
        )

    def _make_sync_client(self, timeout: float) -> httpx.Client:
        kwargs: Dict[str, Any] = {"timeout": timeout}
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    # ------------------------------------------------------------------
    # Fallback decision
    # ------------------------------------------------------------------

    def _should_fallback(self, error: Exception) -> bool:
        """Decide whether to try the next backend or surface the error.

        Fallback triggers:
        - ConnectionError / ConnectionRefusedError / http.client.HTTPException
        - TimeoutError / asyncio.TimeoutError / LLMBackendTimeoutError
        - HTTP 5xx
        - HTTP 429 (rate limit)

        No fallback:
        - HTTP 4xx (except 429) — client error, retrying won't help
        - LLMAllBackendsFailedError — terminal
        """
        if isinstance(error, LLMAllBackendsFailedError):
            return False
        if isinstance(error, LLMBackendTimeoutError):
            return True
        if isinstance(error, (ConnectionError, ConnectionRefusedError)):
            return True
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
            return True
        if isinstance(error, http.client.HTTPException):
            return True
        if isinstance(error, LLMBackendError):
            sc = error.status_code
            if sc is not None:
                if sc >= 500:
                    return True
                if sc == 429:
                    return True
                if sc >= 400:
                    return False
                return True
            # No status code — inspect message for connection/timeout keywords.
            msg = str(error).lower()
            keywords = (
                "refused",
                "connection",
                "timeout",
                "timed out",
                "5xx",
                "500",
                "502",
                "503",
                "504",
                "429",
            )
            if any(k in msg for k in keywords):
                return True
            return True
        # Unknown exception — be conservative and fallback.
        return True

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    def _record_health(
        self,
        backend_name: str,
        success: bool,
        latency_ms: int,
        error: Optional[str] = None,
    ) -> None:
        """Record health outcome — 3 consecutive failures mark unhealthy."""
        with self._lock:
            health = self._health.get(backend_name)
            if health is None:
                return
            health.last_check = datetime.now(timezone.utc).isoformat()
            if success:
                health.consecutive_failures = 0
                health.healthy = True
                health.last_error = None
                history = self._latency_history.setdefault(backend_name, [])
                if latency_ms > 0:
                    history.append(float(latency_ms))
                    if len(history) > self._LATENCY_HISTORY_SIZE:
                        history.pop(0)
                if history:
                    health.avg_latency_ms = sum(history) / len(history)
                self._next_probe_ts[backend_name] = 0.0
            else:
                health.consecutive_failures += 1
                health.last_error = error
                if health.consecutive_failures >= self.UNHEALTHY_THRESHOLD:
                    health.healthy = False
                    self._next_probe_ts[backend_name] = (
                        time.time() + self.UNHEALTHY_RETRY_INTERVAL_SEC
                    )
                    logger.warning(
                        "[LLMBackendManager] Backend %s marked unhealthy "
                        "after %d consecutive failures",
                        backend_name,
                        health.consecutive_failures,
                    )

    def _is_backend_healthy(self, backend: LLMBackendConfig) -> bool:
        """Return True if backend may be tried now.

        Healthy backends are always tried. Unhealthy backends are skipped until
        their next probe timestamp has passed (5 min cooldown), at which point
        we allow a retry attempt — success will restore healthy status.
        """
        with self._lock:
            health = self._health.get(backend.name)
            if health is None:
                return True
            if health.healthy:
                return True
            next_probe = self._next_probe_ts.get(backend.name, 0.0)
            return time.time() >= next_probe

    def health_check(self) -> Dict[str, BackendHealth]:
        """Actively probe all backends; return updated health statuses."""
        for backend in self._backends:
            healthy, error, latency_ms = self._probe_backend_sync(backend)
            self._record_health(
                backend.name,
                success=healthy,
                latency_ms=latency_ms,
                error=error,
            )
        with self._lock:
            return dict(self._health)

    def _probe_backend_sync(
        self, backend: LLMBackendConfig
    ) -> Tuple[bool, Optional[str], int]:
        """Lightweight probe — GET ``/api/tags`` for Ollama, HEAD otherwise.

        Any HTTP response (even 4xx) means the server is reachable.
        Connection errors or 5xx responses mean unhealthy.
        Returns ``(healthy, error_message, latency_ms)``.
        """
        url = backend.base_url
        if backend.name == "ollama":
            url = f"{backend.base_url.rstrip('/')}/api/tags"

        headers = dict(backend.extra_headers)
        start = time.time()
        try:
            with self._make_sync_client(timeout=self.HEALTH_CHECK_PROBE_TIMEOUT) as client:
                if backend.name == "ollama":
                    resp = client.get(url, headers=headers)
                else:
                    resp = client.head(url, headers=headers)
        except httpx.ConnectError as exc:
            return False, f"connection refused: {exc}", 0
        except httpx.TimeoutException as exc:
            return False, f"timeout: {exc}", 0
        except httpx.HTTPError as exc:
            return False, f"HTTP error: {exc}", 0
        except (ConnectionError, TimeoutError, OSError) as exc:
            return False, str(exc), 0

        latency_ms = int((time.time() - start) * 1000)
        if resp.status_code >= 500:
            return False, f"HTTP {resp.status_code}", latency_ms
        return True, None, latency_ms

    def _background_health_check(self) -> None:
        """Background loop — probes every backend every 60s.

        Runs in a daemon thread; stops when :attr:`_health_check_stop` is set.
        """
        while not self._health_check_stop.wait(self.HEALTH_CHECK_INTERVAL_SEC):
            try:
                self.health_check()
            except Exception as exc:  # noqa: BLE001 — must not crash background thread
                logger.warning(
                    "[LLMBackendManager] Background health check error: %s", exc
                )

    def start_background_health_check(self) -> None:
        """Start the background health check thread (idempotent)."""
        if self._health_check_thread is not None and self._health_check_thread.is_alive():
            return
        self._health_check_stop.clear()
        self._health_check_thread = threading.Thread(
            target=self._background_health_check,
            daemon=True,
            name="llm-backend-health-check",
        )
        self._health_check_thread.start()

    def get_backends_status(self) -> List[Dict[str, Any]]:
        """Return a list of backend status dicts (sorted by priority)."""
        with self._lock:
            result: List[Dict[str, Any]] = []
            for b in self._backends:
                health = self._health.get(b.name)
                if health is None:
                    continue
                result.append(
                    {
                        "name": b.name,
                        "base_url": b.base_url,
                        "model": b.model,
                        "priority": b.priority,
                        "enabled": b.enabled,
                        "healthy": health.healthy,
                        "consecutive_failures": health.consecutive_failures,
                        "last_check": health.last_check,
                        "last_error": health.last_error,
                        "avg_latency_ms": health.avg_latency_ms,
                    }
                )
            return result

    # ------------------------------------------------------------------
    # Cache integration
    # ------------------------------------------------------------------

    def _primary_model(self) -> str:
        return self._backends[0].model or "unknown"

    def _provider_for(self, backend_name: str) -> LLMProvider:
        return self._PROVIDER_MAP.get(backend_name, LLMProvider.MOKA)

    def _cache_get(self, prompt: str, **kwargs: Any) -> Optional[LLMResponse]:
        if self._cache is None:
            return None
        model = kwargs.get("model") or self._primary_model()
        temperature = float(kwargs.get("temperature", self.DEFAULT_TEMPERATURE))
        max_tokens = int(kwargs.get("max_tokens", self.DEFAULT_MAX_TOKENS))
        system_prompt = kwargs.get("system_prompt") or ""
        try:
            content = self._cache.get(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                user_prompt=prompt,
            )
        except Exception as exc:  # noqa: BLE001 — cache failure should not break calls
            logger.warning("[LLMBackendManager] Cache get failed: %s", exc)
            return None
        if content is None:
            return None
        primary = self._backends[0]
        return LLMResponse(
            content=content,
            provider=self._provider_for(primary.name),
            model=model,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            latency_ms=0.0,
            raw_response={"cached": True},
        )

    def _cache_put(
        self, prompt: str, response: LLMResponse, **kwargs: Any
    ) -> None:
        if self._cache is None:
            return
        model = response.model or self._primary_model()
        temperature = float(kwargs.get("temperature", self.DEFAULT_TEMPERATURE))
        max_tokens = int(kwargs.get("max_tokens", self.DEFAULT_MAX_TOKENS))
        system_prompt = kwargs.get("system_prompt") or ""
        provider = response.provider.value if hasattr(response.provider, "value") else str(response.provider)
        try:
            self._cache.put(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                user_prompt=prompt,
                response=response.content,
                provider=provider,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[LLMBackendManager] Cache put failed: %s", exc)

    def _compute_cache_key(self, prompt: str, **kwargs: Any) -> str:
        """Compute the deterministic SHA256 cache key for the given call."""
        model = kwargs.get("model") or self._primary_model()
        temperature = float(kwargs.get("temperature", self.DEFAULT_TEMPERATURE))
        max_tokens = int(kwargs.get("max_tokens", self.DEFAULT_MAX_TOKENS))
        system_prompt = kwargs.get("system_prompt") or ""
        return LLMCache.compute_key(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            user_prompt=prompt,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Stop background health check and release resources.

        The thread object is retained (not nulled) so callers can introspect
        its final state via ``is_alive()`` after close.
        """
        self._health_check_stop.set()
        if self._health_check_thread is not None:
            self._health_check_thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "LLMBackendManager":
        """Build a manager from environment variables.

        Reads (with defaults):
        - ``LLM_BACKENDS`` (default ``"ollama,moka,openai"``)
        - ``OLLAMA_BASE_URL`` (default ``http://localhost:11434``)
        - ``MOKA_GATEWAY_URL`` (default ``https://gateway.promiselink.cn``)
        - ``OPENAI_BASE_URL`` (default ``https://api.openai.com/v1``)
        - ``OPENAI_API_KEY`` (optional)
        - ``LLM_TIMEOUT_DEFAULT`` (default 30)
        """
        backends_str = os.environ.get("LLM_BACKENDS", "ollama,moka,openai")
        backend_names = [n.strip() for n in backends_str.split(",") if n.strip()]

        timeout_default = int(os.environ.get("LLM_TIMEOUT_DEFAULT", "30"))

        configs: List[LLMBackendConfig] = []
        for idx, name in enumerate(backend_names):
            if name == "ollama":
                configs.append(
                    LLMBackendConfig(
                        name="ollama",
                        base_url=os.environ.get(
                            "OLLAMA_BASE_URL", "http://localhost:11434"
                        ),
                        api_key=None,
                        model=os.environ.get("OLLAMA_MODEL", "llama3"),
                        timeout=timeout_default,
                        priority=idx,
                    )
                )
            elif name == "moka":
                gateway_url = os.environ.get(
                    "MOKA_GATEWAY_URL", "https://gateway.promiselink.cn"
                )
                configs.append(
                    LLMBackendConfig(
                        name="moka",
                        base_url=f"{gateway_url.rstrip('/')}/api/v1/pro/relay/llm",
                        api_key=os.environ.get("MOKA_GATEWAY_TOKEN"),
                        model=os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"),
                        timeout=timeout_default,
                        priority=idx,
                        extra_headers={"X-AI-Call": "true"},
                    )
                )
            elif name == "openai":
                configs.append(
                    LLMBackendConfig(
                        name="openai",
                        base_url=os.environ.get(
                            "OPENAI_BASE_URL", "https://api.openai.com/v1"
                        ),
                        api_key=os.environ.get("OPENAI_API_KEY"),
                        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                        timeout=timeout_default,
                        priority=idx,
                    )
                )
            else:
                logger.warning(
                    "[LLMBackendManager] Unknown backend name in LLM_BACKENDS: %s",
                    name,
                )

        if not configs:
            # Fallback to default chain if env parsing yielded nothing.
            configs = cls._default_backends(timeout_default)

        cache: Optional[LLMCache] = None
        cache_path = os.environ.get("LLM_CACHE_PATH")
        if cache_path:
            try:
                cache = LLMCache(cache_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[LLMBackendManager] Cache init failed for path %s: %s",
                    cache_path,
                    exc,
                )

        return cls(configs, cache=cache)

    @staticmethod
    def _default_backends(timeout_default: int) -> List[LLMBackendConfig]:
        return [
            LLMBackendConfig(
                name="ollama",
                base_url="http://localhost:11434",
                model="llama3",
                timeout=timeout_default,
                priority=0,
            ),
            LLMBackendConfig(
                name="moka",
                base_url="https://gateway.promiselink.cn/api/v1/pro/relay/llm",
                model="moka/claude-sonnet-4-6",
                timeout=timeout_default,
                priority=1,
                extra_headers={"X-AI-Call": "true"},
            ),
            LLMBackendConfig(
                name="openai",
                base_url="https://api.openai.com/v1",
                model="gpt-4o-mini",
                timeout=timeout_default,
                priority=2,
            ),
        ]
