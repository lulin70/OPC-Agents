"""task_skill 模块单元测试

覆盖 create_task / complete_task / list_tasks / get_today_tasks /
parse_priority_from_text / execute_goal / undo_complete_task
"""

import os
import threading

import pytest

from opc_manager.task_skill import (
    PRIORITY_MAP,
    PRIORITY_LABELS,
    create_task,
    complete_task,
    list_tasks,
    get_today_tasks,
    parse_priority_from_text,
    execute_goal,
    undo_complete_task,
)


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    """Redirect DATA_DIR to tmp_path so tests never touch real data."""
    data_dir = str(tmp_path / "data")
    os.makedirs(data_dir, exist_ok=True)
    monkeypatch.setenv("OPC_DATA_DIR", data_dir)
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", data_dir)
    monkeypatch.setattr(dm, "DB_PATH", os.path.join(data_dir, "opc_data.db"))
    monkeypatch.setattr(dm, "BACKUP_DIR", os.path.join(data_dir, "backups"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    monkeypatch.setattr(dm, "_local", threading.local())
    dm._local.conn = None
    return data_dir


@pytest.fixture(autouse=True)
def _init_db(_isolate_data_dir):
    """Initialise the database in the isolated data dir."""
    import opc_manager.data_manager as dm

    dm.init_db()


class TestPriorityMap:
    """优先级映射常量测试"""

    def test_priority_map_contains_chinese_keywords(self):
        assert PRIORITY_MAP["紧急"] == 0
        assert PRIORITY_MAP["重要"] == 1
        assert PRIORITY_MAP["普通"] == 2
        assert PRIORITY_MAP["低"] == 3

    def test_priority_map_contains_english_keywords(self):
        assert PRIORITY_MAP["urgent"] == 0
        assert PRIORITY_MAP["important"] == 1
        assert PRIORITY_MAP["normal"] == 2
        assert PRIORITY_MAP["low"] == 3

    def test_priority_labels(self):
        assert PRIORITY_LABELS[0] == "P0紧急"
        assert PRIORITY_LABELS[1] == "P1重要"
        assert PRIORITY_LABELS[2] == "P2普通"
        assert PRIORITY_LABELS[3] == "P3低"


class TestParsePriorityFromText:
    """parse_priority_from_text 测试"""

    def test_parse_urgent_chinese(self):
        assert parse_priority_from_text("紧急处理这件事") == 0

    def test_parse_important_chinese(self):
        assert parse_priority_from_text("重要会议") == 1

    def test_parse_normal_chinese(self):
        assert parse_priority_from_text("普通任务") == 2

    def test_parse_low_chinese(self):
        assert parse_priority_from_text("低优先级") == 3

    def test_parse_urgent_english(self):
        assert parse_priority_from_text("urgent task") == 0

    def test_parse_default_returns_normal(self):
        assert parse_priority_from_text("没有优先级关键词的文本") == 2

    def test_parse_empty_string(self):
        assert parse_priority_from_text("") == 2

    def test_parse_case_insensitive(self):
        assert parse_priority_from_text("URGENT") == 0
        assert parse_priority_from_text("IMPORTANT") == 1


class TestCreateTask:
    """create_task 测试"""

    def test_create_task_success(self):
        result = create_task("写周报", description="本周工作总结", priority=1)
        assert result["success"] is True
        assert "id" in result
        assert "周报" in result["message"]
        assert "P1重要" in result["message"]

    def test_create_task_empty_title_fails(self):
        result = create_task("   ")
        assert result["success"] is False
        assert "不能为空" in result["error"]

    def test_create_task_default_priority(self):
        result = create_task("测试任务")
        assert result["success"] is True
        assert "P2普通" in result["message"]

    def test_create_task_with_due_date(self):
        result = create_task("开会", due_date="2026-07-15", priority=0)
        assert result["success"] is True
        assert "P0紧急" in result["message"]

    def test_create_task_with_tags(self):
        result = create_task("带标签的任务", tags="work,urgent")
        assert result["success"] is True


class TestListTasks:
    """list_tasks 测试"""

    def test_list_tasks_empty(self):
        result = list_tasks()
        assert result["success"] is True
        assert result["count"] == 0
        assert result["tasks"] == []

    def test_list_tasks_after_create(self):
        create_task("任务A", priority=1)
        create_task("任务B", priority=2)
        result = list_tasks(status="all")
        assert result["success"] is True
        assert result["count"] == 2

    def test_list_tasks_default_excludes_done(self):
        create_task("未完成")
        result = list_tasks()
        assert result["count"] == 1
        assert result["tasks"][0]["status"] == "pending"

    def test_list_tasks_filter_done(self):
        create_task("任务1")
        result = list_tasks(status="done")
        assert result["count"] == 0

    def test_list_tasks_all_includes_done(self):
        create_task("任务1")
        result_all = list_tasks(status="all")
        assert result_all["count"] == 1

    def test_list_tasks_priority_label_attached(self):
        create_task("紧急任务", priority=0)
        result = list_tasks(status="all")
        assert result["tasks"][0]["priority_label"] == "P0紧急"

    def test_list_tasks_with_limit(self):
        for i in range(5):
            create_task(f"任务{i}")
        result = list_tasks(status="all", limit=3)
        assert result["count"] == 3

    def test_list_tasks_priority_max_filter(self):
        create_task("紧急", priority=0)
        create_task("普通", priority=2)
        result = list_tasks(status="all", priority_max=1)
        assert result["count"] == 1
        assert result["tasks"][0]["priority"] == 0


class TestCompleteTask:
    """complete_task 测试"""

    def test_complete_task_by_id(self):
        created = create_task("要完成的任务")
        task_id = created["id"]
        result = complete_task(task_id=task_id)
        assert result["success"] is True
        assert "已完成" in result["message"]

    def test_complete_task_by_keyword(self):
        create_task("独特的任务名称")
        result = complete_task(title_keyword="独特")
        assert result["success"] is True

    def test_complete_task_no_args_fails(self):
        result = complete_task()
        assert result["success"] is False
        assert "请提供" in result["error"]

    def test_complete_task_not_found(self):
        result = complete_task(task_id="nonexistent_id")
        assert result["success"] is False
        assert "未找到" in result["error"]

    def test_complete_task_multiple_matches_fails(self):
        create_task("重复任务")
        create_task("重复任务")
        result = complete_task(title_keyword="重复任务")
        assert result["success"] is False
        assert "匹配到" in result["error"]


class TestGetTodayTasks:
    """get_today_tasks 测试"""

    def test_get_today_tasks_empty(self):
        result = get_today_tasks()
        assert result["success"] is True
        assert result["count"] == 0

    def test_get_today_tasks_includes_pending(self):
        create_task("今日待办", priority=1)
        result = get_today_tasks()
        assert result["count"] == 1
        assert result["tasks"][0]["title"] == "今日待办"

    def test_get_today_tasks_excludes_done(self):
        created = create_task("已完成任务")
        complete_task(task_id=created["id"])
        result = get_today_tasks()
        assert result["count"] == 0

    def test_get_today_tasks_with_priority_label(self):
        create_task("紧急今日", priority=0)
        result = get_today_tasks()
        assert result["tasks"][0]["priority_label"] == "P0紧急"


class TestExecuteGoal:
    """execute_goal 测试"""

    def test_execute_goal_create_task(self):
        result = execute_goal("帮我记一下明天开会")
        assert result["success"] is True
        assert "id" in result

    def test_execute_goal_complete_task(self):
        create_task("写报告")
        result = execute_goal("完成写报告")
        assert result["success"] is True

    def test_execute_goal_today_tasks(self):
        create_task("今日事项")
        result = execute_goal("今天要做什么")
        assert result["success"] is True
        assert result["count"] >= 1

    def test_execute_goal_list_tasks(self):
        create_task("列出我")
        result = execute_goal("查看待办")
        assert result["success"] is True

    def test_execute_goal_task_stats(self):
        create_task("统计任务")
        result = execute_goal("任务统计")
        assert result["success"] is True
        assert "completion_rate" in result
        assert "total" in result


class TestUndoCompleteTask:
    """undo_complete_task 测试"""

    def test_undo_by_id(self):
        created = create_task("要撤销的任务")
        complete_task(task_id=created["id"])
        result = undo_complete_task(task_id=created["id"])
        assert result["success"] is True
        assert "恢复为待办" in result["message"]

    def test_undo_by_keyword(self):
        create_task("独特撤销名")
        complete_task(title_keyword="独特撤销名")
        result = undo_complete_task(title_keyword="独特撤销名")
        assert result["success"] is True

    def test_undo_no_done_tasks_fails(self):
        result = undo_complete_task()
        assert result["success"] is False
        assert "未找到" in result["error"]

    def test_undo_latest_done(self):
        created = create_task("最新完成")
        complete_task(task_id=created["id"])
        result = undo_complete_task()
        assert result["success"] is True

    def test_undo_restores_to_pending(self):
        created = create_task("恢复测试")
        complete_task(task_id=created["id"])
        undo_complete_task(task_id=created["id"])
        today = get_today_tasks()
        titles = [t["title"] for t in today["tasks"]]
        assert "恢复测试" in titles
