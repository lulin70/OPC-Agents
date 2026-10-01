"""CRM Streamlit 页面组件测试。"""

from unittest.mock import Mock

import frontend.page_modules._crm_page as crm_page
from opc_manager.promiselink_client import ClientState


def test_promiselink_state_card_renders_visible_reason(monkeypatch):
    client = Mock()
    client.state.return_value = ClientState.UNCONFIGURED
    metric = Mock()
    info = Mock()
    subheader = Mock()
    caption = Mock()

    monkeypatch.setattr(crm_page.st, "subheader", subheader)
    monkeypatch.setattr(crm_page.st, "metric", metric)
    monkeypatch.setattr(crm_page.st, "caption", caption)
    monkeypatch.setattr(crm_page.st, "info", info)

    crm_page._render_promiselink_status(client)

    metric.assert_called_once_with("当前状态", "未配置")
    caption.assert_called_once_with("状态码：UNCONFIGURED")
    info.assert_called_once_with("请配置 Base URL 和 Token")


def test_promiselink_state_card_covers_all_client_states():
    expected = {
        ClientState.DISABLED.value,
        ClientState.UNCONFIGURED.value,
        ClientState.AVAILABLE.value,
        ClientState.DEGRADED.value,
        ClientState.CIRCUIT_OPEN.value,
        ClientState.SCHEMA_MISMATCH.value,
    }

    assert set(crm_page._PROMISELINK_STATE_LABELS) == expected
    assert all(
        label and reason
        for label, reason in crm_page._PROMISELINK_STATE_LABELS.values()
    )


def test_morning_brief_uses_local_summary_when_promiselink_is_disabled(monkeypatch):
    client = Mock()
    client.state.return_value = ClientState.DISABLED
    button = Mock(return_value=True)
    info = Mock()
    subheader = Mock()
    monkeypatch.setattr(crm_page.st, "subheader", subheader)
    monkeypatch.setattr(crm_page.st, "button", button)
    monkeypatch.setattr(crm_page.st, "info", info)
    monkeypatch.setattr(
        crm_page,
        "get_silent_customers",
        Mock(return_value={"count": 2}),
    )

    crm_page._render_morning_brief(client)

    info.assert_called_once_with("本地早报：沉默客户 2 个；当前未连接 PromiseLink")
    client.get_morning_brief.assert_not_called()
