"""Unit tests for LLMBackendManager (ADR-005).

Test dimensions (DevSquad Testing Iron Rules):
- Happy ≥50% — successful calls, cache hits, healthy backends
- Error ≥15% — connection errors, 5xx, 4xx, 429, all-failed
- Boundary ≥10% — priority ordering, unhealthy skipping, recovery
- Performance ≥5% — concurrent calls thread safety
- Integration ≥10% — from_env factory, cache integration, full fallback chain

Testing approach:
- Real httpx library with httpx.MockTransport (NOT mock objects) for HTTP
- Real LLMCache with tempfile SQLite DB
- No skipped tests
"""

import asyncio
import os
import tempfile
import threading
import time
import unittest
from typing import List

import httpx

from opc_manager.llm_backend_manager import (
    LLMAllBackendsFailedError,
    LLMBackendConfig,
    LLMBackendError,
    LLMBackendManager,
    LLMBackendTimeoutError,
    LLMBackendUnhealthyError,
    BackendHealth,
)
from opc_manager.llm_cache import LLMCache
from opc_manager.llm_service import LLMProvider, LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ollama_cfg(
    base_url: str = "http://localhost:11434",
    model: str = "llama3",
    priority: int = 0,
    timeout: int = 5,
) -> LLMBackendConfig:
    return LLMBackendConfig(
        name="ollama",
        base_url=base_url,
        model=model,
        priority=priority,
        timeout=timeout,
    )


def _moka_cfg(
    base_url: str = "https://gateway.promiselink.cn/api/v1/pro/relay/llm",
    model: str = "moka/claude-sonnet-4-6",
    priority: int = 1,
    timeout: int = 5,
) -> LLMBackendConfig:
    return LLMBackendConfig(
        name="moka",
        base_url=base_url,
        model=model,
        priority=priority,
        timeout=timeout,
        extra_headers={"X-AI-Call": "true"},
    )


def _openai_cfg(
    base_url: str = "https://api.openai.com/v1",
    model: str = "gpt-4o-mini",
    priority: int = 2,
    timeout: int = 5,
    api_key: str = "sk-test-key-12345",
) -> LLMBackendConfig:
    return LLMBackendConfig(
        name="openai",
        base_url=base_url,
        model=model,
        priority=priority,
        timeout=timeout,
        api_key=api_key,
    )


def _ollama_response(content: str = "hello from ollama") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "response": content,
            "prompt_eval_count": 5,
            "eval_count": 10,
            "total_duration": 1_500_000,
        },
    )


def _openai_response(content: str = "hello from openai") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {"message": {"role": "assistant", "content": content}}
            ],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 10,
                "total_tokens": 15,
            },
        },
    )


def _make_cache() -> LLMCache:
    """Create a real LLMCache backed by a temp SQLite file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return LLMCache(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMBackendManagerHappyPath(unittest.TestCase):
    """Happy-path tests — successful calls and cache hits."""

    def setUp(self) -> None:
        self._tempfiles: List[str] = []

    def tearDown(self) -> None:
        for p in self._tempfiles:
            try:
                os.remove(p)
            except OSError:
                pass

    def test_call_ollama_success_happy_path(self):
        """Verify: When Ollama is healthy and returns 200, call() returns its response.

        Scenario: Single Ollama backend configured; MockTransport returns 200
        with valid Ollama JSON.
        Expected: Response content matches, provider == OLLAMA.
        """
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return _ollama_response("local-ollama-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        # Act
        response = manager.call("hello")

        # Assert
        self.assertEqual(response.content, "local-ollama-reply")
        self.assertEqual(response.provider, LLMProvider.OLLAMA)
        self.assertEqual(response.model, "llama3")
        self.assertGreaterEqual(response.usage["total_tokens"], 0)
        self.assertGreaterEqual(response.latency_ms, 0)

    def test_call_moka_success_happy_path(self):
        """Verify: Moka backend returns parsed OpenAI-compatible response."""
        def handler(request: httpx.Request) -> httpx.Response:
            return _openai_response("moka-reply")

        manager = LLMBackendManager(
            [_moka_cfg()],
            transport=httpx.MockTransport(handler),
        )
        response = manager.call("hi")
        self.assertEqual(response.content, "moka-reply")
        self.assertEqual(response.provider, LLMProvider.MOKA)

    def test_call_openai_success_happy_path(self):
        """Verify: OpenAI backend returns parsed response."""
        def handler(request: httpx.Request) -> httpx.Response:
            return _openai_response("openai-reply")

        manager = LLMBackendManager(
            [_openai_cfg()],
            transport=httpx.MockTransport(handler),
        )
        response = manager.call("hi")
        self.assertEqual(response.content, "openai-reply")
        self.assertEqual(response.provider, LLMProvider.OPENAI)

    def test_call_with_cache_hit_skips_backend(self):
        """Verify: On cache hit, the backend HTTP endpoint is NOT called.

        Scenario: Cache is pre-populated with a known response for the prompt;
        the MockTransport handler raises if invoked (proving no HTTP call made).
        Expected: Response content equals cached content; no exception raised.
        """
        # Arrange — real cache with temp DB
        cache = _make_cache()
        self._tempfiles.append(cache._db_path)
        cache.put(
            model="llama3",
            temperature=0.3,
            max_tokens=500,
            system_prompt="",
            user_prompt="cached-prompt",
            response="cached-response",
            provider="ollama",
        )

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("Backend should not be called on cache hit")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            cache=cache,
            transport=httpx.MockTransport(handler),
        )

        # Act
        response = manager.call("cached-prompt")

        # Assert
        self.assertEqual(response.content, "cached-response")
        self.assertEqual(response.latency_ms, 0.0)
        cache.close()

    def test_call_with_cache_miss_writes_to_cache(self):
        """Verify: On cache miss, the successful response is written to cache.

        Scenario: Empty cache; backend returns 200; second call with same prompt
        should hit the cache (handler not invoked on second call would prove it,
        but here we simply verify cache content directly).
        Expected: After first call, cache.get() returns the response content.
        """
        cache = _make_cache()
        self._tempfiles.append(cache._db_path)

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return _ollama_response("persisted-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            cache=cache,
            transport=httpx.MockTransport(handler),
        )

        # Act — first call: cache miss, backend called, response cached
        first = manager.call("prompt-to-cache")
        self.assertEqual(first.content, "persisted-reply")
        self.assertEqual(call_count["n"], 1)

        # Second call: cache hit, backend NOT called
        second = manager.call("prompt-to-cache")
        self.assertEqual(second.content, "persisted-reply")
        self.assertEqual(call_count["n"], 1, "Backend should not be called on second call")

        # Verify cache contains the entry
        cached = cache.get(
            model="llama3", temperature=0.3, max_tokens=500,
            system_prompt="", user_prompt="prompt-to-cache",
        )
        self.assertEqual(cached, "persisted-reply")
        cache.close()

    def test_async_acall_happy_path(self):
        """Verify: Async acall() returns the same response as sync call()."""
        def handler(request: httpx.Request) -> httpx.Response:
            return _ollama_response("async-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = asyncio.run(manager.acall("hello-async"))
        self.assertEqual(response.content, "async-reply")
        self.assertEqual(response.provider, LLMProvider.OLLAMA)

    def test_health_check_all_healthy(self):
        """Verify: health_check() returns healthy=True for all reachable backends."""
        def handler(request: httpx.Request) -> httpx.Response:
            # Probes use GET for ollama (/api/tags) and HEAD for others.
            return httpx.Response(200)

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        result = manager.health_check()
        self.assertIsInstance(result, dict)
        self.assertTrue(result["ollama"].healthy)
        self.assertTrue(result["moka"].healthy)
        self.assertIsNotNone(result["ollama"].last_check)
        self.assertEqual(result["ollama"].consecutive_failures, 0)

    def test_get_backends_status_returns_all(self):
        """Verify: get_backends_status() returns a dict for every backend."""
        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg(), _openai_cfg()],
        )
        statuses = manager.get_backends_status()
        self.assertEqual(len(statuses), 3)
        names = [s["name"] for s in statuses]
        self.assertIn("ollama", names)
        self.assertIn("moka", names)
        self.assertIn("openai", names)
        # Sorted by priority
        self.assertEqual(names, ["ollama", "moka", "openai"])
        # Each status has the expected fields
        for s in statuses:
            self.assertIn("base_url", s)
            self.assertIn("priority", s)
            self.assertIn("enabled", s)
            self.assertIn("healthy", s)
            self.assertIn("consecutive_failures", s)

    def test_priority_order_ollama_first(self):
        """Verify: Backends are tried in priority order (lower priority first)."""
        # Reverse insertion order; priority should still sort ollama first.
        manager = LLMBackendManager(
            [_openai_cfg(priority=2), _moka_cfg(priority=1), _ollama_cfg(priority=0)],
        )
        statuses = manager.get_backends_status()
        self.assertEqual(statuses[0]["name"], "ollama")
        self.assertEqual(statuses[1]["name"], "moka")
        self.assertEqual(statuses[2]["name"], "openai")


class TestLLMBackendManagerFallback(unittest.TestCase):
    """Fallback chain tests — error-triggered backend switching."""

    def test_call_ollama_connection_refused_fallback_to_moka(self):
        """Verify: When Ollama connection is refused, fallback to Moka.

        Scenario: Ollama URL triggers httpx.ConnectError; Moka returns 200.
        Expected: Response provider == MOKA; ollama health consecutive_failures == 1.
        """
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            if "localhost:11434" in str(request.url):
                raise httpx.ConnectError("connection refused")
            return _openai_response("moka-fallback-reply")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        # Act
        response = manager.call("hello")

        # Assert
        self.assertEqual(response.content, "moka-fallback-reply")
        self.assertEqual(response.provider, LLMProvider.MOKA)
        # Ollama should have one failure recorded
        self.assertEqual(manager._health["ollama"].consecutive_failures, 1)
        # Moka should be healthy (success)
        self.assertEqual(manager._health["moka"].consecutive_failures, 0)

    def test_call_moka_5xx_fallback_to_openai(self):
        """Verify: When Moka returns 5xx, fallback to OpenAI."""
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "gateway.promiselink" in url:
                return httpx.Response(503, text="service unavailable")
            if "api.openai.com" in url:
                return _openai_response("openai-fallback-reply")
            # Ollama: also fail so we test moka→openai chain directly
            raise httpx.ConnectError("ollama down")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg(), _openai_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = manager.call("hello")
        self.assertEqual(response.content, "openai-fallback-reply")
        self.assertEqual(response.provider, LLMProvider.OPENAI)

    def test_call_all_backends_fail_raises_LLMAllBackendsFailedError(self):
        """Verify: When all backends fail with fallback-eligible errors,
        LLMAllBackendsFailedError is raised."""
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("all down")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(LLMAllBackendsFailedError) as ctx:
            manager.call("hello")
        self.assertIn("All LLM backends failed", str(ctx.exception))

    def test_call_4xx_no_fallback_raises(self):
        """Verify: HTTP 4xx (except 429) does NOT trigger fallback; raises immediately.

        Scenario: Ollama returns 400 Bad Request; Moka would also return 200
        but should never be called.
        Expected: LLMBackendError raised with status_code=400; Moka never invoked.
        """
        called_urls: List[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            return httpx.Response(400, text="Bad Request")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(LLMBackendError) as ctx:
            manager.call("hello")

        self.assertEqual(ctx.exception.status_code, 400)
        # Only ollama was called — no fallback to moka
        self.assertEqual(len(called_urls), 1)
        self.assertIn("localhost:11434", called_urls[0])
        # Moka's health should be untouched
        self.assertEqual(manager._health["moka"].consecutive_failures, 0)

    def test_call_429_fallback_to_next_backend(self):
        """Verify: HTTP 429 (rate limit) triggers fallback to next backend."""
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "localhost:11434" in url:
                return httpx.Response(429, text="rate limited")
            return _openai_response("moka-after-429")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = manager.call("hello")
        self.assertEqual(response.content, "moka-after-429")
        self.assertEqual(response.provider, LLMProvider.MOKA)
        self.assertEqual(manager._health["ollama"].consecutive_failures, 1)

    def test_unhealthy_backend_skipped_in_call(self):
        """Verify: A backend marked unhealthy is skipped during call()."""
        # Arrange — handler simulates moka returning success, ollama never called
        ollama_calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "localhost:11434" in url:
                ollama_calls["n"] += 1
                return httpx.Response(500, text="ollama broken")
            return _openai_response("moka-success")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )
        # Manually mark ollama unhealthy with future probe time
        manager._health["ollama"].healthy = False
        manager._health["ollama"].consecutive_failures = 3
        manager._next_probe_ts["ollama"] = time.time() + 999  # far future

        # Act
        response = manager.call("hello")

        # Assert
        self.assertEqual(response.content, "moka-success")
        self.assertEqual(ollama_calls["n"], 0, "Unhealthy ollama should be skipped")
        # Moka remains the responder
        self.assertEqual(manager._health["moka"].consecutive_failures, 0)

    def test_moka_backend_includes_x_ai_call_header(self):
        """Verify: Moka backend requests carry the X-AI-Call: true header.

        This is a HARD_CONSTRAINT (§2.4) — gateway billing depends on it.
        """
        captured_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return _openai_response("moka-ok")

        manager = LLMBackendManager(
            [_moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        manager.call("hi")
        self.assertIn("x-ai-call", captured_headers)
        self.assertEqual(captured_headers["x-ai-call"], "true")


class TestLLMBackendManagerHealth(unittest.TestCase):
    """Health check and circuit breaker tests."""

    def test_health_check_marks_unhealthy_after_3_failures(self):
        """Verify: 3 consecutive failures mark a backend unhealthy."""
        manager = LLMBackendManager([_ollama_cfg()])

        # Act — record 3 failures
        for _ in range(3):
            manager._record_health(
                "ollama", success=False, latency_ms=0, error="conn refused"
            )

        # Assert
        self.assertFalse(manager._health["ollama"].healthy)
        self.assertEqual(manager._health["ollama"].consecutive_failures, 3)
        self.assertEqual(manager._health["ollama"].last_error, "conn refused")
        # next_probe_ts should be set ~5 min in the future
        self.assertGreater(manager._next_probe_ts["ollama"], time.time())

    def test_health_check_recovery_after_5min(self):
        """Verify: Unhealthy backend becomes retriable after 5-min cooldown.

        Scenario: Mark unhealthy, advance next_probe_ts into the past,
        record a success — health should be restored.
        Expected: healthy == True, consecutive_failures == 0.
        """
        manager = LLMBackendManager([_ollama_cfg()])

        # Mark unhealthy
        for _ in range(3):
            manager._record_health(
                "ollama", success=False, latency_ms=0, error="down"
            )
        self.assertFalse(manager._health["ollama"].healthy)

        # Simulate 5 min passing — move next_probe_ts into past
        manager._next_probe_ts["ollama"] = time.time() - 1
        self.assertTrue(manager._is_backend_healthy(_ollama_cfg()))

        # Record a success — should clear unhealthy state
        manager._record_health("ollama", success=True, latency_ms=42)
        self.assertTrue(manager._health["ollama"].healthy)
        self.assertEqual(manager._health["ollama"].consecutive_failures, 0)
        self.assertAlmostEqual(manager._health["ollama"].avg_latency_ms, 42.0)

    def test_health_check_below_threshold_stays_healthy(self):
        """Verify: Fewer than 3 failures does NOT mark unhealthy (boundary)."""
        manager = LLMBackendManager([_ollama_cfg()])

        manager._record_health("ollama", success=False, latency_ms=0, error="e1")
        manager._record_health("ollama", success=False, latency_ms=0, error="e2")

        self.assertTrue(manager._health["ollama"].healthy)
        self.assertEqual(manager._health["ollama"].consecutive_failures, 2)

    def test_health_check_success_resets_failures(self):
        """Verify: A success resets the consecutive failure counter."""
        manager = LLMBackendManager([_ollama_cfg()])

        manager._record_health("ollama", success=False, latency_ms=0, error="e1")
        manager._record_health("ollama", success=False, latency_ms=0, error="e2")
        manager._record_health("ollama", success=True, latency_ms=10)

        self.assertEqual(manager._health["ollama"].consecutive_failures, 0)
        self.assertTrue(manager._health["ollama"].healthy)

    def test_health_check_marks_unhealthy_on_5xx_probe(self):
        """Verify: Probe returning 5xx marks backend unhealthy (after threshold)."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="gateway down")

        manager = LLMBackendManager(
            [_moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        # Run probe 3 times to cross the threshold
        for _ in range(3):
            manager.health_check()

        self.assertFalse(manager._health["moka"].healthy)

    def test_background_health_check_runs_periodically(self):
        """Verify: Background thread executes health_check at the interval.

        Uses a short interval patch to avoid waiting 60s in unit tests.
        """
        probe_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            probe_count["n"] += 1
            return httpx.Response(200)

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )
        # Shorten interval for test
        original = LLMBackendManager.HEALTH_CHECK_INTERVAL_SEC
        LLMBackendManager.HEALTH_CHECK_INTERVAL_SEC = 0.2
        try:
            manager.start_background_health_check()
            time.sleep(0.7)  # ~3 cycles
        finally:
            LLMBackendManager.HEALTH_CHECK_INTERVAL_SEC = original
            manager.close()

        # At least one probe cycle should have executed
        self.assertGreater(probe_count["n"], 0)

    def test_close_stops_background_thread(self):
        """Verify: close() stops the background health check thread."""
        manager = LLMBackendManager([_ollama_cfg()])
        manager.start_background_health_check()
        self.assertIsNotNone(manager._health_check_thread)
        self.assertTrue(manager._health_check_thread.is_alive())

        manager.close()
        self.assertFalse(manager._health_check_thread.is_alive())


class TestLLMBackendManagerShouldFallback(unittest.TestCase):
    """_should_fallback() decision matrix tests."""

    def test_should_fallback_connection_error_true(self):
        manager = LLMBackendManager([_ollama_cfg()])
        self.assertTrue(manager._should_fallback(ConnectionError("refused")))

    def test_should_fallback_timeout_true(self):
        manager = LLMBackendManager([_ollama_cfg()])
        self.assertTrue(manager._should_fallback(TimeoutError("timed out")))
        self.assertTrue(manager._should_fallback(asyncio.TimeoutError()))

    def test_should_fallback_llm_backend_timeout_error_true(self):
        manager = LLMBackendManager([_ollama_cfg()])
        self.assertTrue(manager._should_fallback(LLMBackendTimeoutError("slow")))

    def test_should_fallback_5xx_true(self):
        manager = LLMBackendManager([_ollama_cfg()])
        for code in (500, 502, 503, 504):
            err = LLMBackendError(f"HTTP {code}", status_code=code)
            self.assertTrue(manager._should_fallback(err), f"code={code}")

    def test_should_fallback_4xx_false(self):
        manager = LLMBackendManager([_ollama_cfg()])
        for code in (400, 401, 403, 404, 422):
            err = LLMBackendError(f"HTTP {code}", status_code=code)
            self.assertFalse(manager._should_fallback(err), f"code={code}")

    def test_should_fallback_429_true(self):
        manager = LLMBackendManager([_ollama_cfg()])
        err = LLMBackendError("HTTP 429", status_code=429)
        self.assertTrue(manager._should_fallback(err))

    def test_should_fallback_all_backends_failed_false(self):
        """Verify: LLMAllBackendsFailedError is terminal — no further fallback."""
        manager = LLMBackendManager([_ollama_cfg()])
        err = LLMAllBackendsFailedError("terminal")
        self.assertFalse(manager._should_fallback(err))

    def test_should_fallback_http_client_exception_true(self):
        """Verify: http.client.HTTPException triggers fallback."""
        import http.client

        manager = LLMBackendManager([_ollama_cfg()])
        self.assertTrue(manager._should_fallback(http.client.HTTPException("bad")))


class TestLLMBackendManagerCache(unittest.TestCase):
    """Cache integration tests."""

    def setUp(self) -> None:
        self._tempfiles: List[str] = []

    def tearDown(self) -> None:
        for p in self._tempfiles:
            try:
                os.remove(p)
            except OSError:
                pass

    def test_cache_key_deterministic(self):
        """Verify: Same prompt+kwargs always produces the same SHA256 cache key."""
        manager = LLMBackendManager([_ollama_cfg()])

        prompt = "deterministic-prompt"
        kwargs = {"temperature": 0.3, "max_tokens": 500, "system_prompt": "sys"}

        key1 = manager._compute_cache_key(prompt, **kwargs)
        key2 = manager._compute_cache_key(prompt, **kwargs)

        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 64)  # SHA256 hex digest length

    def test_cache_key_changes_with_prompt(self):
        """Verify: Different prompts yield different cache keys (boundary)."""
        manager = LLMBackendManager([_ollama_cfg()])
        k1 = manager._compute_cache_key("prompt-a")
        k2 = manager._compute_cache_key("prompt-b")
        self.assertNotEqual(k1, k2)

    def test_cache_key_changes_with_temperature(self):
        """Verify: Different temperatures yield different cache keys (boundary)."""
        manager = LLMBackendManager([_ollama_cfg()])
        k1 = manager._compute_cache_key("p", temperature=0.3)
        k2 = manager._compute_cache_key("p", temperature=0.7)
        self.assertNotEqual(k1, k2)

    def test_cache_put_skipped_when_none(self):
        """Verify: When cache is None, _cache_put is a no-op (boundary)."""
        manager = LLMBackendManager([_ollama_cfg()], cache=None)
        # Should not raise
        manager._cache_put(
            "p",
            LLMResponse(
                content="x", provider=LLMProvider.OLLAMA, model="llama3",
                usage={}, latency_ms=1.0,
            ),
        )

    def test_cache_get_returns_none_when_no_cache(self):
        """Verify: When cache is None, _cache_get returns None (boundary)."""
        manager = LLMBackendManager([_ollama_cfg()], cache=None)
        self.assertIsNone(manager._cache_get("any-prompt"))


class TestLLMBackendManagerFromEnv(unittest.TestCase):
    """from_env() factory tests — integration with environment variables."""

    def setUp(self) -> None:
        # Snapshot all relevant env vars
        self._keys = [
            "LLM_BACKENDS",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "MOKA_GATEWAY_URL",
            "MOKA_MODEL",
            "MOKA_GATEWAY_TOKEN",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "LLM_TIMEOUT_DEFAULT",
            "LLM_CACHE_PATH",
        ]
        self._snapshot = {k: os.environ.get(k) for k in self._keys}
        # Clear them all
        for k in self._keys:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._snapshot.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_from_env_creates_default_backends(self):
        """Verify: from_env() with no env vars creates the default 3-backend chain."""
        manager = LLMBackendManager.from_env()

        self.assertEqual(len(manager._backends), 3)
        names = [b.name for b in manager._backends]
        self.assertEqual(names, ["ollama", "moka", "openai"])

        # Verify default URLs
        ollama = next(b for b in manager._backends if b.name == "ollama")
        self.assertEqual(ollama.base_url, "http://localhost:11434")
        moka = next(b for b in manager._backends if b.name == "moka")
        self.assertEqual(
            moka.base_url,
            "https://gateway.promiselink.cn/api/v1/pro/relay/llm",
        )
        self.assertEqual(moka.extra_headers.get("X-AI-Call"), "true")
        openai = next(b for b in manager._backends if b.name == "openai")
        self.assertEqual(openai.base_url, "https://api.openai.com/v1")

        # No cache by default (LLM_CACHE_PATH not set)
        self.assertIsNone(manager._cache)

    def test_from_env_custom_backends(self):
        """Verify: LLM_BACKENDS env var controls which backends are created."""
        os.environ["LLM_BACKENDS"] = "moka,openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"

        manager = LLMBackendManager.from_env()

        self.assertEqual(len(manager._backends), 2)
        names = [b.name for b in manager._backends]
        self.assertEqual(names, ["moka", "openai"])

    def test_from_env_custom_urls(self):
        """Verify: Custom URL env vars are honored."""
        os.environ["LLM_BACKENDS"] = "ollama"
        os.environ["OLLAMA_BASE_URL"] = "http://192.168.1.50:11434"
        os.environ["OLLAMA_MODEL"] = "mistral:7b"
        os.environ["LLM_TIMEOUT_DEFAULT"] = "15"

        manager = LLMBackendManager.from_env()

        self.assertEqual(len(manager._backends), 1)
        b = manager._backends[0]
        self.assertEqual(b.base_url, "http://192.168.1.50:11434")
        self.assertEqual(b.model, "mistral:7b")
        self.assertEqual(b.timeout, 15)

    def test_from_env_moka_includes_x_ai_call_header(self):
        """Verify: Moka backend from from_env() carries the X-AI-Call header."""
        os.environ["LLM_BACKENDS"] = "moka"

        manager = LLMBackendManager.from_env()
        moka = manager._backends[0]
        self.assertEqual(moka.extra_headers.get("X-AI-Call"), "true")


class TestLLMBackendManagerValidation(unittest.TestCase):
    """Constructor validation and edge cases."""

    def test_init_requires_at_least_one_backend(self):
        """Verify: Empty backends list raises ValueError."""
        with self.assertRaises(ValueError):
            LLMBackendManager([])

    def test_init_requires_at_least_one_enabled_backend(self):
        """Verify: All-disabled backends raises ValueError (boundary)."""
        disabled = LLMBackendConfig(
            name="ollama", base_url="http://localhost:11434", enabled=False
        )
        with self.assertRaises(ValueError):
            LLMBackendManager([disabled])

    def test_init_with_disabled_backend_filters_them_out(self):
        """Verify: Disabled backends are filtered from the active list (boundary)."""
        configs = [
            _ollama_cfg(priority=0),
            LLMBackendConfig(
                name="moka",
                base_url="https://gateway.promiselink.cn/api/v1/pro/relay/llm",
                priority=1,
                enabled=False,
                extra_headers={"X-AI-Call": "true"},
            ),
        ]
        manager = LLMBackendManager(configs)
        self.assertEqual(len(manager._backends), 1)
        self.assertEqual(manager._backends[0].name, "ollama")

    def test_backend_health_dataclass_defaults(self):
        """Verify: BackendHealth dataclass defaults are sensible."""
        h = BackendHealth(name="ollama", healthy=True)
        self.assertEqual(h.name, "ollama")
        self.assertTrue(h.healthy)
        self.assertIsNone(h.last_check)
        self.assertEqual(h.consecutive_failures, 0)
        self.assertIsNone(h.last_error)
        self.assertIsNone(h.avg_latency_ms)

    def test_llm_backend_error_carries_status_code(self):
        """Verify: LLMBackendError preserves the status_code attribute."""
        err = LLMBackendError("HTTP 503", status_code=503)
        self.assertEqual(err.status_code, 503)
        self.assertIn("503", str(err))

    def test_exception_hierarchy(self):
        """Verify: Exception inheritance hierarchy is correct."""
        self.assertTrue(issubclass(LLMAllBackendsFailedError, LLMBackendError))
        self.assertTrue(issubclass(LLMBackendTimeoutError, LLMBackendError))
        self.assertTrue(issubclass(LLMBackendUnhealthyError, LLMBackendError))
        self.assertTrue(issubclass(LLMBackendError, Exception))


class TestLLMBackendManagerPerformance(unittest.TestCase):
    """Performance and concurrency tests."""

    def test_concurrent_calls_thread_safe_performance(self):
        """Verify: Concurrent calls from multiple threads are safe and fast.

        Scenario: 10 threads each call manager.call() with the same prompt.
        Expected: All calls succeed; no exceptions; completes in < 5s.
        """
        def handler(request: httpx.Request) -> httpx.Response:
            return _ollama_response("concurrent-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        results: List[LLMResponse] = []
        errors: List[Exception] = []
        result_lock = threading.Lock()

        def worker():
            try:
                r = manager.call("concurrent-prompt")
                with result_lock:
                    results.append(r)
            except Exception as e:
                with result_lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertEqual(r.content, "concurrent-reply")
        # Performance: 10 concurrent calls should complete in < 5s
        self.assertLess(elapsed, 5.0, f"Took {elapsed:.2f}s")

    def test_concurrent_async_calls_performance(self):
        """Verify: Concurrent async acall() invocations are safe.

        Uses asyncio.gather to issue 5 parallel calls.
        """
        def handler(request: httpx.Request) -> httpx.Response:
            return _ollama_response("async-concurrent-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        async def run_all():
            tasks = [manager.acall("p") for _ in range(5)]
            return await asyncio.gather(*tasks)

        start = time.time()
        responses = asyncio.run(run_all())
        elapsed = time.time() - start

        self.assertEqual(len(responses), 5)
        for r in responses:
            self.assertEqual(r.content, "async-concurrent-reply")
        self.assertLess(elapsed, 5.0)

    def test_call_latency_recorded(self):
        """Verify: Latency is measured and recorded in health stats."""
        def handler(request: httpx.Request) -> httpx.Response:
            time.sleep(0.05)  # 50ms
            return _ollama_response("slow-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = manager.call("hi")
        self.assertGreaterEqual(response.latency_ms, 40)  # at least ~50ms
        self.assertIsNotNone(manager._health["ollama"].avg_latency_ms)
        self.assertGreaterEqual(manager._health["ollama"].avg_latency_ms, 40)


class TestLLMBackendManagerIntegration(unittest.TestCase):
    """End-to-end integration: full fallback chain, cache+backend together."""

    def setUp(self) -> None:
        self._tempfiles: List[str] = []

    def tearDown(self) -> None:
        for p in self._tempfiles:
            try:
                os.remove(p)
            except OSError:
                pass

    def test_full_fallback_chain_ollama_to_openai(self):
        """Verify: Full 3-backend chain falls through Ollama → Moka → OpenAI.

        Scenario: Ollama connection refused; Moka returns 5xx; OpenAI returns 200.
        Expected: Final response provider == OPENAI; all backends' health updated.
        """
        call_log: List[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            call_log.append(url)
            if "localhost:11434" in url:
                raise httpx.ConnectError("ollama down")
            if "gateway.promiselink" in url:
                return httpx.Response(503, text="moka 503")
            if "api.openai.com" in url:
                return _openai_response("final-openai-reply")
            return httpx.Response(404)

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg(), _openai_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = manager.call("full-chain-test")

        self.assertEqual(response.content, "final-openai-reply")
        self.assertEqual(response.provider, LLMProvider.OPENAI)
        # All 3 backends were attempted
        self.assertEqual(len(call_log), 3)
        # Health reflects the outcomes
        self.assertEqual(manager._health["ollama"].consecutive_failures, 1)
        self.assertEqual(manager._health["moka"].consecutive_failures, 1)
        self.assertEqual(manager._health["openai"].consecutive_failures, 0)

    def test_cache_hit_then_miss_after_invalidation(self):
        """Verify: After cache is cleared, the backend is called again."""
        cache = _make_cache()
        self._tempfiles.append(cache._db_path)

        backend_calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            backend_calls["n"] += 1
            return _ollama_response("integration-reply")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            cache=cache,
            transport=httpx.MockTransport(handler),
        )

        # First call: miss → backend
        r1 = manager.call("integration-prompt")
        self.assertEqual(r1.content, "integration-reply")
        self.assertEqual(backend_calls["n"], 1)

        # Second call: hit → no backend
        r2 = manager.call("integration-prompt")
        self.assertEqual(r2.content, "integration-reply")
        self.assertEqual(backend_calls["n"], 1)

        # Clear cache — next call should miss and hit backend again
        cache._conn.execute("DELETE FROM llm_cache")
        cache._conn.commit()

        r3 = manager.call("integration-prompt")
        self.assertEqual(r3.content, "integration-reply")
        self.assertEqual(backend_calls["n"], 2)

        cache.close()

    def test_manager_works_with_real_llm_response_dataclass(self):
        """Verify: Returned objects are real LLMResponse instances (not mocks)."""
        def handler(request: httpx.Request) -> httpx.Response:
            return _ollama_response("real-instance")

        manager = LLMBackendManager(
            [_ollama_cfg()],
            transport=httpx.MockTransport(handler),
        )

        response = manager.call("hi")
        self.assertIsInstance(response, LLMResponse)
        self.assertIsInstance(response.provider, LLMProvider)
        self.assertIsInstance(response.usage, dict)
        self.assertIsInstance(response.latency_ms, float)

    def test_health_check_updates_status_after_call_failure(self):
        """Verify: A failed call() updates the health status, visible via status API."""
        def handler(request: httpx.Request) -> httpx.Response:
            if "localhost:11434" in str(request.url):
                raise httpx.ConnectError("down")
            return _openai_response("moka-ok")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        manager.call("hi")

        statuses = manager.get_backends_status()
        ollama_status = next(s for s in statuses if s["name"] == "ollama")
        moka_status = next(s for s in statuses if s["name"] == "moka")

        self.assertEqual(ollama_status["consecutive_failures"], 1)
        self.assertIsNotNone(ollama_status["last_error"])
        self.assertEqual(moka_status["consecutive_failures"], 0)
        self.assertTrue(moka_status["healthy"])

    def test_repeated_failures_mark_unhealthy_then_skip(self):
        """Verify: After 3 failed calls, the 4th call skips the unhealthy backend.

        Scenario: Ollama always fails with connection error; Moka succeeds.
        Expected: After 3 calls, ollama is unhealthy; 4th call goes straight to moka.
        """
        ollama_attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "localhost:11434" in url:
                ollama_attempts["n"] += 1
                raise httpx.ConnectError("ollama dead")
            return _openai_response("moka-ok")

        manager = LLMBackendManager(
            [_ollama_cfg(), _moka_cfg()],
            transport=httpx.MockTransport(handler),
        )

        # 3 calls — each tries ollama first, fails, falls back to moka
        for i in range(3):
            r = manager.call("p")
            self.assertEqual(r.content, "moka-ok")

        self.assertEqual(ollama_attempts["n"], 3)
        self.assertFalse(manager._health["ollama"].healthy)
        self.assertEqual(manager._health["ollama"].consecutive_failures, 3)

        # 4th call — ollama should be skipped (unhealthy, future probe time)
        ollama_attempts["n"] = 0
        r = manager.call("p")
        self.assertEqual(r.content, "moka-ok")
        self.assertEqual(ollama_attempts["n"], 0, "Ollama should be skipped on 4th call")


if __name__ == "__main__":
    unittest.main()
