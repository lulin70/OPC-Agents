"""Local morning-brief aggregation and scheduler wiring tests."""

from unittest.mock import Mock

import pytest

from opc_manager.settings import MorningBriefSettings
import opc_manager.morning_brief as morning_brief


@pytest.fixture
def isolated_morning_brief_scheduler(monkeypatch, tmp_path):
    """Isolate and close the process-local scheduler and SQLite repositories."""
    if morning_brief._RUNTIME is not None:
        morning_brief._RUNTIME.stop()
    if morning_brief._REPOSITORIES is not None:
        for repository in morning_brief._REPOSITORIES:
            repository.close()
    monkeypatch.setattr(
        morning_brief, "_SCHEDULER_DB_PATH", str(tmp_path / "scheduler.db")
    )
    monkeypatch.setattr(morning_brief, "_RUNTIME", None)
    monkeypatch.setattr(morning_brief, "_REPOSITORIES", None)

    yield

    if morning_brief._RUNTIME is not None:
        morning_brief._RUNTIME.stop()
    if morning_brief._REPOSITORIES is not None:
        for repository in morning_brief._REPOSITORIES:
            repository.close()
    morning_brief._RUNTIME = None
    morning_brief._REPOSITORIES = None


def test_render_morning_brief_markdown_contains_operator_sections():
    markdown = morning_brief.render_morning_brief_markdown(
        {
            "generated_at": "2026-09-30T08:00:00",
            "finance": {"monthly": {"income": 1000, "expense": 250, "profit": 750}},
            "crm": {
                "stats": {"total": 2},
                "silent": {
                    "count": 1,
                    "customers": [{"name": "张三", "company": "示例公司"}],
                },
            },
            "tasks": {"by_status": {"pending": 3}},
            "audit_log": [],
            "errors": [],
        }
    )

    assert "# 经营早报" in markdown
    assert "本月利润：¥750.00" in markdown
    assert "示例公司" in markdown
    assert "pending：3 个" in markdown


def test_build_morning_brief_email_draft_requires_recipient_and_body():
    assert morning_brief.build_morning_brief_email_draft("# brief", "") == {
        "success": False,
        "error": "早报邮件缺少收件人邮箱",
    }
    assert morning_brief.build_morning_brief_email_draft("", "owner@example.com") == {
        "success": False,
        "error": "早报邮件正文不能为空",
    }


def test_deliver_morning_brief_email_requires_confirmation(monkeypatch):
    send_email = Mock()
    monkeypatch.setattr("opc_manager.email_skill.send_email", send_email)
    result = morning_brief.deliver_morning_brief_email(
        {"recipient": "owner@example.com", "subject": "早报", "body": "正文"}
    )
    assert result == {"success": False, "error": "发送早报邮件前必须确认"}
    send_email.assert_not_called()


def test_deliver_morning_brief_email_sends_only_after_confirmation(monkeypatch):
    send_email = Mock(return_value={"success": True, "id": "email-1"})
    monkeypatch.setattr("opc_manager.email_skill.send_email", send_email)
    result = morning_brief.deliver_morning_brief_email(
        {"recipient": "owner@example.com", "subject": "早报", "body": "正文"},
        confirmed=True,
    )
    assert result["success"] is True
    send_email.assert_called_once_with("owner@example.com", "早报", "正文")


def test_handle_morning_brief_saves_local_draft_and_audits(monkeypatch, tmp_path):
    output = tmp_path / "morning_brief.md"
    monkeypatch.setattr(
        morning_brief,
        "collect_morning_brief_data",
        lambda **_: {
            "generated_at": "2026-09-30T08:00:00",
            "finance": {"monthly": {}, "trend": []},
            "crm": {"stats": {}, "silent": {"count": 0, "customers": []}},
            "tasks": {"items": [], "by_status": {}},
            "audit_log": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        morning_brief, "save_morning_brief_draft", lambda _: str(output)
    )

    audit_log = Mock()
    monkeypatch.setattr(morning_brief, "AuditLog", Mock(return_value=audit_log))
    result = morning_brief.handle_morning_brief({"scope": "default"})

    audit_log.log.assert_called_once()

    assert result == str(output)


def test_handle_morning_brief_never_sends_email(monkeypatch, tmp_path):
    output = tmp_path / "morning_brief.md"
    monkeypatch.setattr(
        morning_brief,
        "collect_morning_brief_data",
        lambda **_: {
            "generated_at": "2026-09-30T08:00:00",
            "finance": {"monthly": {}, "trend": []},
            "crm": {"stats": {}, "silent": {"count": 0, "customers": []}},
            "tasks": {"items": [], "by_status": {}},
            "audit_log": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        morning_brief, "save_morning_brief_draft", lambda _: str(output)
    )
    save_email_draft = Mock()
    monkeypatch.setattr(
        morning_brief, "save_morning_brief_email_draft", save_email_draft
    )
    audit_log = Mock()
    monkeypatch.setattr(morning_brief, "AuditLog", Mock(return_value=audit_log))

    result = morning_brief.handle_morning_brief(
        {"scope": "default", "recipient_email": "owner@example.com"}
    )

    assert result == str(output)
    save_email_draft.assert_called_once()


def test_ensure_morning_brief_task_creates_and_enables_task(monkeypatch, tmp_path):
    db_path = tmp_path / "scheduler.db"
    monkeypatch.setattr(morning_brief, "_SCHEDULER_DB_PATH", str(db_path))
    monkeypatch.setattr(morning_brief, "_RUNTIME", None)
    monkeypatch.setattr(morning_brief, "_REPOSITORIES", None)

    task = morning_brief.ensure_morning_brief_task()

    assert task.task_type == "morning_brief"
    assert task.enabled is True
    assert task.next_run_at is not None

    morning_brief._RUNTIME.stop()
    for repository in morning_brief._REPOSITORIES:
        repository.close()
    morning_brief._RUNTIME = None
    morning_brief._REPOSITORIES = None


def test_sync_morning_brief_task_first_creation_is_disabled(
    isolated_morning_brief_scheduler,
):
    task = morning_brief.sync_morning_brief_task(
        MorningBriefSettings(
            enabled=False,
            recipient_email="owner@example.com",
            schedule_time="08:30",
            timezone="Asia/Tokyo",
            scope="sales",
        )
    )

    assert task.task_type == "morning_brief"
    assert task.enabled is False
    assert task.next_run_at is None
    assert task.schedule_expression == "daily 08:30"
    assert task.timezone == "Asia/Tokyo"
    assert task.parameters["scope"] == "sales"
    assert task.parameters["recipient_email"] == "owner@example.com"


def test_sync_morning_brief_task_enabled_creation(
    isolated_morning_brief_scheduler,
):
    task = morning_brief.sync_morning_brief_task(
        MorningBriefSettings(enabled=True, schedule_time="08:30")
    )

    assert task.enabled is True
    assert task.next_run_at is not None


def test_sync_morning_brief_task_is_idempotent(
    isolated_morning_brief_scheduler,
):
    settings = MorningBriefSettings(enabled=True, schedule_time="08:30")
    first = morning_brief.sync_morning_brief_task(settings)
    second = morning_brief.sync_morning_brief_task(settings)

    tasks = morning_brief._REPOSITORIES[0].list_tasks()
    assert second.id == first.id
    assert len([task for task in tasks if task.task_type == "morning_brief"]) == 1


def test_sync_morning_brief_task_updates_existing_configuration(
    isolated_morning_brief_scheduler,
):
    first = morning_brief.sync_morning_brief_task(
        MorningBriefSettings(enabled=True, schedule_time="08:30")
    )
    updated = morning_brief.sync_morning_brief_task(
        MorningBriefSettings(
            enabled=True,
            recipient_email="owner@example.com",
            schedule_time="09:45",
            timezone="America/New_York",
            scope="finance",
        )
    )

    assert updated.id == first.id
    assert updated.schedule_expression == "daily 09:45"
    assert updated.timezone == "America/New_York"
    assert updated.parameters == {
        "scope": "finance",
        "delivery": "local_draft",
        "recipient_email": "owner@example.com",
    }
    assert updated.next_run_at is not None
    assert updated.next_run_at != first.next_run_at


def test_sync_morning_brief_task_disables_existing_task(
    isolated_morning_brief_scheduler,
):
    enabled = morning_brief.sync_morning_brief_task(MorningBriefSettings(enabled=True))

    disabled = morning_brief.sync_morning_brief_task(
        MorningBriefSettings(enabled=False)
    )

    assert disabled.id == enabled.id
    assert disabled.enabled is False


def test_sync_morning_brief_task_disables_duplicate_tasks_and_keeps_first(
    isolated_morning_brief_scheduler,
):
    first = morning_brief.sync_morning_brief_task(MorningBriefSettings(enabled=True))
    task_repo = morning_brief._REPOSITORIES[0]
    duplicate = task_repo.create_task(
        name="重复早报",
        schedule_type="daily",
        schedule_expression="daily 08:00",
        task_type="morning_brief",
        parameters={"scope": "duplicate"},
    )
    duplicate = task_repo.enable_task(duplicate.id)

    synced = morning_brief.sync_morning_brief_task(MorningBriefSettings(enabled=True))

    tasks = [
        task for task in task_repo.list_tasks() if task.task_type == "morning_brief"
    ]
    assert synced.id == first.id
    assert tasks[0].id == first.id
    assert tasks[0].enabled is True
    assert tasks[1].id == duplicate.id
    assert tasks[1].enabled is False
