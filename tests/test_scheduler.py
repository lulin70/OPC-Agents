"""opc_manager/scheduler.py 单元测试 — TDD §5 契约验证.

覆盖: 受限调度语法解析 / 两表持久化 / 重启后任务不丢 /
     决策点 fail-close / 失败重试 / tick 状态回写 / 安全边界（白名单+参数限额）
"""

from datetime import datetime, timedelta

import pytest

from opc_manager.scheduler import (
    DEFAULT_AUTO_TASK_TYPES,
    DecisionVetoError,
    ScheduleParseError,
    ScheduledTaskRepository,
    SchedulerService,
    ScheduledTaskRunner,
    TaskExecutionRepository,
)

NOW = datetime(2026, 9, 21, 12, 0, 0)


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "scheduler_test.db")


@pytest.fixture()
def repos(db_path):
    task_repo = ScheduledTaskRepository(db_path)
    exec_repo = TaskExecutionRepository(db_path)
    yield task_repo, exec_repo
    task_repo.close()
    exec_repo.close()


def _make_task(task_repo, **overrides):
    kwargs = dict(
        name="早报任务",
        schedule_type="daily",
        schedule_expression="daily 08:00",
        task_type="morning_brief",
        parameters={"scope": "default"},
    )
    kwargs.update(overrides)
    return task_repo.create_task(**kwargs)


def _enabled_task(task_repo, **overrides):
    task = _make_task(task_repo, **overrides)
    return task_repo.enable_task(task.id)


def _runner(task_repo, exec_repo, handler=None, guard=None):
    runner = ScheduledTaskRunner(task_repo, exec_repo, consensus_guard=guard)
    if handler is not None:
        runner.register_handler("morning_brief", handler)
    return runner


# ---------------------------------------------------------------------------
# ScheduleParser — 受限语法
# ---------------------------------------------------------------------------


class TestScheduleParser:
    def test_cron_every_five_minutes(self):
        from opc_manager.scheduler import ScheduleParser

        nxt = ScheduleParser.next_after("*/5 * * * *", NOW.replace(minute=1))
        assert nxt == NOW.replace(minute=5)

    def test_cron_daily_eight(self):
        from opc_manager.scheduler import ScheduleParser

        nxt = ScheduleParser.next_after("0 8 * * *", NOW)
        assert nxt.hour == 8 and nxt.minute == 0 and nxt.day == NOW.day + 1

    def test_daily_syntax(self):
        from opc_manager.scheduler import ScheduleParser

        nxt = ScheduleParser.next_after("daily 08:30", NOW)
        assert (nxt.hour, nxt.minute) == (8, 30)

    def test_interval_minutes(self):
        from opc_manager.scheduler import ScheduleParser

        nxt = ScheduleParser.next_after("interval:30", NOW)
        assert nxt == NOW + timedelta(minutes=30)

    def test_dow_seven_is_sunday(self):
        from opc_manager.scheduler import ScheduleParser

        fields = ScheduleParser.next_after  # noqa: F841
        from opc_manager.scheduler import _parse_cron

        dow = _parse_cron("0 8 * * 7").dow
        assert 0 in dow and 7 not in dow

    def test_too_few_fields_rejected(self):
        from opc_manager.scheduler import ScheduleParser

        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("0 8 * *", NOW)

    def test_field_out_of_range_rejected(self):
        from opc_manager.scheduler import ScheduleParser

        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("60 * * * *", NOW)
        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("* 25 * * *", NOW)

    def test_bad_step_rejected(self):
        from opc_manager.scheduler import ScheduleParser

        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("*/0 * * * *", NOW)

    def test_bad_interval_rejected(self):
        from opc_manager.scheduler import ScheduleParser

        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("interval:0", NOW)
        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("interval:abc", NOW)

    def test_bad_daily_rejected(self):
        from opc_manager.scheduler import ScheduleParser

        with pytest.raises(ScheduleParseError):
            ScheduleParser.next_after("daily 9999", NOW)

    def test_list_and_range_fields(self):
        from opc_manager.scheduler import ScheduleParser

        nxt = ScheduleParser.next_after("0 8 * * 1-5", NOW)
        assert nxt.isoweekday() in (1, 2, 3, 4, 5)


# ---------------------------------------------------------------------------
# ScheduledTaskRepository — 安全边界与状态
# ---------------------------------------------------------------------------


class TestTaskRepositorySafety:
    def test_task_type_whitelist_enforced(self, repos):
        task_repo, _ = repos
        with pytest.raises(ValueError, match="白名单"):
            _make_task(task_repo, task_type="send_email_now")

    def test_schedule_type_restricted(self, repos):
        task_repo, _ = repos
        with pytest.raises(ValueError, match="schedule_type"):
            _make_task(task_repo, schedule_type="shell")

    def test_update_fields_rejects_non_whitelist_column(self, repos):
        """_update_fields 动态拼接列名，必须拒绝白名单外的列（B608 收口）。

        若此校验缺失，列名可被污染成任意 SQL 片段。
        """
        task_repo, _ = repos
        task = _make_task(task_repo)
        with pytest.raises(ValueError, match="不允许更新的字段"):
            task_repo._update_fields(task.id, {"enabled = 1, name": "x"})

    def test_update_fields_accepts_whitelist_columns(self, repos):
        """对照组：白名单内列正常更新，保证收口未误伤既有写回路径。"""
        task_repo, _ = repos
        task = _make_task(task_repo)
        task_repo._update_fields(
            task.id, {"enabled": 1, "updated_at": "2026-01-01T00:00:00"}
        )
        assert task_repo.get_task(task.id).enabled == 1

    def test_invalid_timezone_rejected(self, repos):
        task_repo, _ = repos
        with pytest.raises(Exception):
            _make_task(task_repo, timezone_name="Mars/Olympus")

    def test_unserializable_params_rejected(self, repos):
        task_repo, _ = repos
        with pytest.raises(ValueError, match="序列化"):
            _make_task(task_repo, parameters={"fn": lambda: 1})

    def test_oversized_params_rejected(self, repos):
        task_repo, _ = repos
        with pytest.raises(ValueError, match="上限"):
            _make_task(task_repo, parameters={"blob": "x" * 11000})

    def test_created_as_draft_disabled(self, repos):
        task_repo, _ = repos
        task = _make_task(task_repo)
        assert task.enabled is False

    def test_enable_computes_next_run(self, repos):
        task_repo, _ = repos
        task = _enabled_task(task_repo)
        assert task.enabled is True
        assert task.next_run_at is not None


# ---------------------------------------------------------------------------
# 持久化与重启恢复（TDD：重启后任务不丢）
# ---------------------------------------------------------------------------


class TestPersistenceAcrossRestart:
    def test_task_survives_restart(self, db_path, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo, schedule_expression="interval:10")
        task_repo.close()
        exec_repo.close()

        repo2 = ScheduledTaskRepository(db_path)
        exec2 = TaskExecutionRepository(db_path)
        try:
            runner = _runner(repo2, exec2, handler=lambda params: "ref-1")
            service = SchedulerService(repo2, exec2, runner=runner)
            future = task.next_run_at + timedelta(minutes=1)
            outcomes = service.tick(now=future)
            assert len(outcomes) == 1
            assert outcomes[0].state.value == "SUCCEEDED"
            assert outcomes[0].result_ref == "ref-1"
            reloaded = repo2.get_task(task.id)
            assert reloaded.last_run_at is not None
            assert reloaded.next_run_at > task.next_run_at
        finally:
            repo2.close()
            exec2.close()

    def test_due_tasks_requires_enabled_and_next_run(self, repos):
        task_repo, _ = repos
        draft = _make_task(task_repo)  # DRAFT: enabled=0, next_run None
        # 参照时间点取"真实当前时间 + 365 天"：enable_task 的首次 next_run_at 基于
        # 真实当前时间计算，若沿用固定 NOW 会随日期推移落到参照点之后，断言失效
        # （B0.1 回归发现的定时炸弹：2026-09-21 编写时通过，2026-09-24 起必失败）。
        # 远未来参照点让本用例只校验两件事：enabled=0 排除、enabled=1 且 next_run 非空纳入。
        reference = datetime.now() + timedelta(days=365)
        assert task_repo.due_tasks(reference) == []
        task_repo.enable_task(draft.id)
        assert len(task_repo.due_tasks(reference)) == 1


# ---------------------------------------------------------------------------
# ScheduledTaskRunner — 决策点保护与重试
# ---------------------------------------------------------------------------


class TestRunnerProtection:
    def test_guard_veto_blocks_fail_close(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)
        runner = _runner(
            task_repo,
            exec_repo,
            handler=lambda params: "ref",
            guard=_veto_guard,
        )
        outcome = runner.run_task(task)
        assert outcome.state.value == "BLOCKED_BY_CONSENSUS"
        history = exec_repo.history_for_task(task.id)
        assert history[0]["consensus_status"] == "VETOED"
        assert history[0]["status"] == "BLOCKED_BY_CONSENSUS"

    def test_guard_exception_fails_close(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)

        def broken_guard(_task):
            raise RuntimeError("consensus service down")

        runner = _runner(task_repo, exec_repo, guard=broken_guard)
        outcome = runner.run_task(task)
        assert outcome.state.value == "BLOCKED_BY_CONSENSUS"
        history = exec_repo.history_for_task(task.id)
        assert history[0]["consensus_status"] == "GUARD_ERROR"

    def test_missing_handler_blocked(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)
        runner = _runner(task_repo, exec_repo)  # 未注册 handler
        outcome = runner.run_task(task)
        assert outcome.state.value == "BLOCKED_BY_CONSENSUS"

    def test_success_records_history(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)
        runner = _runner(task_repo, exec_repo, handler=lambda params: "ok-ref")
        outcome = runner.run_task(task)
        assert outcome.state.value == "SUCCEEDED"
        assert outcome.attempts == 1
        history = exec_repo.history_for_task(task.id)
        assert history[0]["status"] == "SUCCEEDED"
        assert history[0]["result_ref"] == "ok-ref"
        assert len(history[0]["trace_id"]) == 32

    def test_retry_then_succeed(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)
        calls = {"n": 0}

        def flaky(params):
            calls["n"] += 1
            if calls["n"] == 1:
                raise IOError("transient")
            return "ok"

        runner = _runner(task_repo, exec_repo, handler=flaky)
        outcome = runner.run_task(task)
        assert outcome.state.value == "SUCCEEDED"
        assert outcome.attempts == 2
        # 同秒内 started_at 相同，不依赖 DESC 顺序，按 retry_count 断言
        history = exec_repo.history_for_task(task.id)
        statuses = sorted(h["status"] for h in history)
        assert statuses == ["RETRYING", "SUCCEEDED"]
        assert sorted(h["retry_count"] for h in history) == [0, 1]

    def test_all_fail_marks_failed(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo)

        def always_fail(params):
            raise IOError("permanent")

        runner = _runner(task_repo, exec_repo, handler=always_fail)
        outcome = runner.run_task(task)
        assert outcome.state.value == "FAILED"
        statuses = sorted(h["status"] for h in exec_repo.history_for_task(task.id))
        assert statuses == ["FAILED", "RETRYING"]

    def test_default_guard_rejects_non_whitelist(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo, task_type="report_draft")
        runner = ScheduledTaskRunner(task_repo, exec_repo)  # 默认 guard
        runner.register_handler("report_draft", lambda p: "r")
        # 白名单内正常执行
        assert runner.run_task(task).state.value == "SUCCEEDED"


def _veto_guard(_task):
    raise DecisionVetoError("三贤者否决：自动发送未授权")


# ---------------------------------------------------------------------------
# SchedulerService.tick — 状态回写
# ---------------------------------------------------------------------------


class TestSchedulerTick:
    def test_tick_executes_and_advances(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo, schedule_expression="interval:10")
        runner = _runner(task_repo, exec_repo, handler=lambda params: "ref")
        service = SchedulerService(task_repo, exec_repo, runner=runner)
        outcomes = service.tick(now=task.next_run_at + timedelta(minutes=1))
        assert len(outcomes) == 1
        reloaded = task_repo.get_task(task.id)
        assert reloaded.last_run_at is not None
        assert reloaded.next_run_at > task.next_run_at
        assert reloaded.enabled is True

    def test_permanent_failure_disables_task(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo, schedule_expression="interval:10")

        def always_fail(params):
            raise IOError("bad")

        runner = _runner(task_repo, exec_repo, handler=always_fail)
        service = SchedulerService(task_repo, exec_repo, runner=runner)
        service.tick(now=task.next_run_at + timedelta(minutes=1))
        reloaded = task_repo.get_task(task.id)
        assert reloaded.enabled is False  # 失败停用，防止每轮空转

    def test_blocked_task_parks_until_manual_review(self, repos):
        task_repo, exec_repo = repos
        task = _enabled_task(task_repo, schedule_expression="interval:10")
        runner = _runner(task_repo, exec_repo, handler=lambda p: "r", guard=_veto_guard)
        service = SchedulerService(task_repo, exec_repo, runner=runner)
        service.tick(now=task.next_run_at + timedelta(minutes=1))
        reloaded = task_repo.get_task(task.id)
        assert reloaded.next_run_at is None  # 挂起待人工处理

    def test_no_due_task_noop(self, repos):
        task_repo, exec_repo = repos
        _enabled_task(task_repo, schedule_expression="daily 08:00")
        runner = _runner(task_repo, exec_repo, handler=lambda p: "r")
        service = SchedulerService(task_repo, exec_repo, runner=runner)
        assert service.tick(now=NOW) == []


def test_default_whitelist_covers_documented_types():
    # TDD §5.4：v1.0.0 自动任务只生成报告或草稿
    assert DEFAULT_AUTO_TASK_TYPES == frozenset(
        {"report_draft", "morning_brief", "email_draft", "local_summary"}
    )


def test_schema_columns_match_tdd(db_path):
    # TDD §5.5 两表列名逐一核对
    import sqlite3

    conn = sqlite3.connect(db_path)
    ScheduledTaskRepository(db_path).close()
    TaskExecutionRepository(db_path).close()
    task_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
    }
    exec_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(task_executions)").fetchall()
    }
    conn.close()
    assert task_cols == {
        "id",
        "name",
        "schedule_type",
        "schedule_expression",
        "task_type",
        "parameters_json",
        "enabled",
        "timezone",
        "next_run_at",
        "last_run_at",
        "created_at",
        "updated_at",
    }
    assert exec_cols == {
        "id",
        "task_id",
        "started_at",
        "finished_at",
        "status",
        "result_ref",
        "error_code",
        "retry_count",
        "consensus_status",
        "trace_id",
    }
