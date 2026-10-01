"""PromiseLink live smoke tests.

These tests are opt-in because they make real PromiseLink HTTP requests.
Run with ``PROMISELINK_LIVE_SMOKE=1`` and the three PromiseLink settings.
"""

import logging
import os
from typing import Callable, Tuple

import pytest

from opc_manager.promiselink_client import ClientResult, ClientState, PromiseLinkClient

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

_LIVE_SMOKE_ENV = "PROMISELINK_LIVE_SMOKE"


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


@pytest.fixture(scope="module")
def promiselink_live_client() -> Tuple[PromiseLinkClient, str]:
    """Create the real client only when live smoke is explicitly enabled."""
    if os.environ.get(_LIVE_SMOKE_ENV) != "1":
        pytest.skip(f"设置 {_LIVE_SMOKE_ENV}=1 才执行真实 PromiseLink smoke 测试")

    enabled = os.environ.get("PROMISELINK_ENABLED", "")
    base_url = os.environ.get("PROMISELINK_BASE_URL", "").strip()
    token = os.environ.get("PROMISELINK_TOKEN", "")
    missing = [
        name
        for name, value in (
            ("PROMISELINK_ENABLED", enabled),
            ("PROMISELINK_BASE_URL", base_url),
            ("PROMISELINK_TOKEN", token),
        )
        if not value
    ]
    if missing:
        pytest.fail("live smoke 缺少 PromiseLink 配置: " + ", ".join(missing))
    if not _is_enabled(enabled):
        pytest.fail("PROMISELINK_ENABLED 必须为 1、true 或 yes 才能执行 live smoke")

    # 不传 transport：此入口必须走真实 httpx 网络请求，而不是 MockTransport。
    client = PromiseLinkClient()
    assert client.state() is ClientState.AVAILABLE, (
        "PromiseLink 配置状态异常: " + client.state().value
    )
    return client, token


def _assert_success_or_explicit_state(name: str, result: ClientResult) -> None:
    """Keep failures actionable without including response data or credentials."""
    if result.success:
        assert (
            result.state is ClientState.AVAILABLE
        ), f"{name} 成功但 ClientState={result.state.value}"
        return

    pytest.fail(f"{name} 请求失败，ClientState={result.state.value}")


def test_promiselink_live_read_paths(
    promiselink_live_client: Tuple[PromiseLinkClient, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Validate health, dormant entities, morning brief and care reminders."""
    client, token = promiselink_live_client
    read_paths: tuple[tuple[str, Callable[[], ClientResult]], ...] = (
        ("health", client.health),
        ("dormant_entities", lambda: client.list_dormant_entities(min_days=30)),
        ("morning_brief", client.get_morning_brief),
        ("care_reminders", client.get_care_reminders),
    )

    with caplog.at_level(logging.INFO, logger="opc_manager.promiselink_client"):
        for name, read_path in read_paths:
            _assert_success_or_explicit_state(name, read_path())

    assert token not in caplog.text
