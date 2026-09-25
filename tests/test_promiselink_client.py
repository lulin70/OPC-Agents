"""PromiseLinkClient 单元测试（TDD_V1.0.0.md §3 契约）。

覆盖：
  - §3.4 六态：DISABLED / UNCONFIGURED / AVAILABLE / DEGRADED / CIRCUIT_OPEN / SCHEMA_MISMATCH
  - §3.3 职责：Bearer 注入、指数退避、429 Retry-After、熔断、schema 最小校验、trace_id、耗时
  - §3.2 禁用路径不封装
  - SKILL_FREEZE_LIST §八：结构化可校验输出（to_dict）
  - 安全：日志与结果中不泄露明文 Token
"""

import logging

import httpx
import pytest

from opc_manager.promiselink_client import (
    CIRCUIT_FAILURE_THRESHOLD,
    ClientState,
    PromiseLinkClient,
)

TOKEN = "secret-token-abc123"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in ("PROMISELINK_ENABLED", "PROMISELINK_BASE_URL", "PROMISELINK_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def make_client(transport=None, **kwargs):
    defaults = dict(
        base_url="http://promiselink.test",
        token=TOKEN,
        enabled=True,
        backoff_base_seconds=0.0,
        transport=transport,
        sleep_fn=lambda _s: None,
    )
    defaults.update(kwargs)
    return PromiseLinkClient(**defaults)


def json_handler(routes):
    """routes: list of (method, path, status, payload_or_exc, headers)

    按请求顺序依次消耗路由；同方法+路径的路由耗尽后重放最后一条
    （支持单路由多次请求，如 is_available 内部二次 health）。
    """
    calls = []
    consumed = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        matching = [
            i
            for i, r in enumerate(routes)
            if r[0] == request.method and request.url.path.endswith(r[1])
        ]
        unconsumed = [i for i in matching if i not in consumed]
        chosen = unconsumed[0] if unconsumed else (matching[-1] if matching else None)
        if chosen is None:
            return httpx.Response(404, json={"error": "not found"})
        consumed.append(chosen)
        _, _, status, payload, headers = routes[chosen]
        if isinstance(payload, Exception):
            raise payload
        return httpx.Response(status, json=payload, headers=headers or {})

    return handler, calls


# ----------------------------------------------------------------------
# 状态机：DISABLED / UNCONFIGURED / AVAILABLE
# ----------------------------------------------------------------------


class TestStates:
    def test_default_disabled(self):
        handler, calls = json_handler([])
        client = make_client(transport=httpx.MockTransport(handler), enabled=None)
        result = client.health()
        assert result.state is ClientState.DISABLED
        assert result.success is False
        assert calls == []

    def test_unconfigured_without_base_url(self):
        client = make_client(base_url="", token=TOKEN)
        result = client.health()
        assert result.state is ClientState.UNCONFIGURED

    def test_unconfigured_without_token(self):
        client = make_client(base_url="http://promiselink.test", token="")
        result = client.health()
        assert result.state is ClientState.UNCONFIGURED

    def test_available_after_health_ok(self):
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert result.success is True
        assert result.state is ClientState.AVAILABLE
        assert result.data == {"status": "ok"}
        assert client.is_available() is True

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("PROMISELINK_TOKEN", TOKEN)
        client = make_client(token=None)
        assert client.is_configured() is True


# ----------------------------------------------------------------------
# §3.3 职责：Bearer / trace_id / 耗时 / 结构化输出
# ----------------------------------------------------------------------


class TestClientDuties:
    def test_bearer_token_injected(self):
        handler, calls = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        client.health()
        assert calls[0].headers["Authorization"] == f"Bearer {TOKEN}"

    def test_trace_id_and_duration_recorded(self):
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert len(result.trace_id) == 32
        int(result.trace_id, 16)  # 十六进制
        assert result.duration_ms >= 0

    def test_structured_output_to_dict(self):
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        d = result.to_dict()
        assert set(d.keys()) == {
            "success",
            "state",
            "data",
            "error",
            "status_code",
            "trace_id",
            "duration_ms",
        }
        assert d["state"] == "AVAILABLE"

    def test_token_never_logged(self, caplog):
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        with caplog.at_level(logging.DEBUG, logger="opc_manager.promiselink_client"):
            client.health()
            client.list_dormant_entities(min_days=30)
        assert TOKEN not in caplog.text

    def test_api_prefix_enforced(self):
        handler, calls = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        client.health()
        assert calls[0].url.path.startswith("/api/v1/")


# ----------------------------------------------------------------------
# 退避 / 429 / 重试
# ----------------------------------------------------------------------


class TestRetryAndBackoff:
    def test_exponential_backoff_on_500_then_success(self):
        routes = [
            ("GET", "/api/v1/health", 500, {"error": "boom"}, None),
            ("GET", "/api/v1/health", 500, {"error": "boom"}, None),
            ("GET", "/api/v1/health", 200, {"status": "ok"}, None),
        ]
        handler, calls = json_handler(routes)
        sleeps = []
        client = make_client(
            transport=httpx.MockTransport(handler), sleep_fn=sleeps.append
        )
        result = client.health()
        assert result.success is True
        assert len(calls) == 3
        assert len(sleeps) == 2
        assert sleeps[1] == sleeps[0] * 2  # 指数退避

    def test_429_respects_retry_after(self):
        routes = [
            ("GET", "/api/v1/health", 429, {"error": "rate"}, {"Retry-After": "0.25"}),
            ("GET", "/api/v1/health", 200, {"status": "ok"}, None),
        ]
        handler, calls = json_handler(routes)
        sleeps = []
        client = make_client(
            transport=httpx.MockTransport(handler), sleep_fn=sleeps.append
        )
        result = client.health()
        assert result.success is True
        assert sleeps == [0.25]

    def test_429_exhausted_returns_degraded(self):
        routes = [("GET", "/api/v1/health", 429, {"error": "rate"}, None)] * 5
        handler, _ = json_handler(routes)
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert result.success is False
        assert result.state is ClientState.DEGRADED
        assert result.status_code == 429

    def test_client_error_no_retry(self):
        routes = [("GET", "/api/v1/health", 404, {"error": "nf"}, None)]
        handler, calls = json_handler(routes)
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert result.state is ClientState.DEGRADED
        assert result.status_code == 404
        assert len(calls) == 1

    def test_network_error_degraded(self):
        def handler(_request):
            raise httpx.ConnectError("connection refused")

        sleeps = []
        client = make_client(
            transport=httpx.MockTransport(handler), sleep_fn=sleeps.append
        )
        result = client.health()
        assert result.success is False
        assert result.state is ClientState.DEGRADED
        assert "网络错误" in result.error
        assert len(sleeps) == client._max_retries


# ----------------------------------------------------------------------
# 熔断器
# ----------------------------------------------------------------------


class TestCircuitBreaker:
    def _failing_client(self):
        def handler(_request):
            raise httpx.ConnectError("down")

        client = make_client(transport=httpx.MockTransport(handler))
        return client

    def test_opens_after_threshold(self):
        client = self._failing_client()
        for _ in range(CIRCUIT_FAILURE_THRESHOLD):
            result = client.health()
            assert result.state is ClientState.DEGRADED
        assert client.state() is ClientState.CIRCUIT_OPEN

    def test_open_circuit_short_circuits(self):
        client = self._failing_client()
        for _ in range(CIRCUIT_FAILURE_THRESHOLD):
            client.health()

        called = []

        def probe_handler(_request):
            called.append(_request)
            return httpx.Response(200, json={"status": "ok"})

        client._transport = httpx.MockTransport(probe_handler)
        result = client.health()
        assert result.state is ClientState.CIRCUIT_OPEN
        assert result.success is False
        assert called == []

    def test_half_open_recovery(self):
        client = self._failing_client()
        for _ in range(CIRCUIT_FAILURE_THRESHOLD):
            client.health()
        assert client.state() is ClientState.CIRCUIT_OPEN

        import time as _time

        client._circuit_opened_at = _time.monotonic() - 31.0  # 超过冷却期
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client._transport = httpx.MockTransport(handler)
        result = client.health()
        assert result.success is True
        assert client.state() is ClientState.AVAILABLE
        assert client._consecutive_failures == 0


# ----------------------------------------------------------------------
# Schema 校验
# ----------------------------------------------------------------------


class TestSchemaValidation:
    def test_missing_required_key_is_schema_mismatch(self):
        handler, _ = json_handler(
            [("GET", "/api/v1/health", 200, {"unexpected": 1}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert result.state is ClientState.SCHEMA_MISMATCH
        assert result.success is False
        assert "缺少字段" in result.error

    def test_list_expectation_violation(self):
        handler, _ = json_handler(
            [("GET", "/api/v1/entities", 200, {"not": "a list"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.list_entities()
        assert result.state is ClientState.SCHEMA_MISMATCH

    def test_non_json_response(self):
        def handler(_request):
            return httpx.Response(200, text="<html>oops</html>")

        client = make_client(transport=httpx.MockTransport(handler))
        result = client.health()
        assert result.state is ClientState.SCHEMA_MISMATCH

    def test_schema_mismatch_does_not_trip_circuit(self):
        handler, _ = json_handler([("GET", "/api/v1/health", 200, {"bad": 1}, None)])
        client = make_client(transport=httpx.MockTransport(handler))
        for _ in range(CIRCUIT_FAILURE_THRESHOLD + 2):
            client.health()
        assert client.state() is ClientState.AVAILABLE


# ----------------------------------------------------------------------
# §3.2 禁用路径 + 路由参数
# ----------------------------------------------------------------------


class TestRoutesAndForbiddenPaths:
    def test_forbidden_paths_not_wrapped(self):
        forbidden = [
            "dormant_days",
            "analyze_bidirectional",
            "generate_nudge",
            "nudges",
        ]
        for name in forbidden:
            assert not hasattr(PromiseLinkClient, name)

    def test_dormant_uses_min_days_param(self):
        handler, calls = json_handler(
            [("GET", "/api/v1/entities/dormant", 200, [], None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.list_dormant_entities(min_days=30)
        assert result.success is True
        assert calls[0].url.params["min_days"] == "30"
        assert "dormant_days" not in str(calls[0].url.params)

    def test_get_entity_stage_info_path(self):
        handler, calls = json_handler(
            [("GET", "/api/v1/entities/e1/stage-info", 200, {"stage": "dormant"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.get_entity_stage_info("e1")
        assert result.success is True
        assert calls[0].url.path.endswith("/api/v1/entities/e1/stage-info")

    def test_patch_reminder_preferences(self):
        handler, calls = json_handler(
            [("PATCH", "/api/v1/reminders/preferences", 200, {"quiet_hours": 22}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.patch_reminder_preferences({"quiet_hours": 22})
        assert result.success is True
        assert calls[0].method == "PATCH"

    def test_post_event(self):
        handler, calls = json_handler(
            [("POST", "/api/v1/events", 202, {"id": "evt-1"}, None)]
        )
        client = make_client(transport=httpx.MockTransport(handler))
        result = client.post_event({"type": "meeting_note"})
        assert result.success is True
        assert calls[0].method == "POST"


# ----------------------------------------------------------------------
# DTO 映射
# ----------------------------------------------------------------------


class TestDtoMapping:
    def test_map_entity_dto(self):
        dto = PromiseLinkClient.map_entity_dto(
            {"id": "e1", "name": "张三", "updated_at": "2026-09-21T08:00:00"}
        )
        assert dto == {
            "entity_id": "e1",
            "display_name": "张三",
            "source": "promiselink",
            "last_synced_at": "2026-09-21T08:00:00",
            "raw": {"id": "e1", "name": "张三", "updated_at": "2026-09-21T08:00:00"},
        }

    def test_map_entity_dto_defaults(self):
        dto = PromiseLinkClient.map_entity_dto({})
        assert dto["entity_id"] is None
        assert dto["display_name"] == ""
        assert dto["source"] == "promiselink"


# ----------------------------------------------------------------------
# Token 来源：SecureKeyStore 兜底
# ----------------------------------------------------------------------


class TestTokenSources:
    def test_keystore_fallback(self, monkeypatch):
        class FakeStore:
            def __init__(self, *a, **k):
                pass

            def get_key(self, name):
                assert name == "PROMISELINK_TOKEN"
                return TOKEN

        import opc_manager.secure_storage as secure_storage_module

        monkeypatch.setattr(secure_storage_module, "SecureKeyStore", FakeStore)
        client = make_client(token=None)
        assert client.is_configured() is True
        handler, calls = json_handler(
            [("GET", "/api/v1/health", 200, {"status": "ok"}, None)]
        )
        client._transport = httpx.MockTransport(handler)
        result = client.health()
        assert result.success is True
        assert calls[0].headers["Authorization"] == f"Bearer {TOKEN}"
