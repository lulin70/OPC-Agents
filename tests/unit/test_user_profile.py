"""user_profile 模块单元测试

覆盖 UserProfile 类的交互记录、偏好管理、使用模式分析、技能推荐
"""

import os
import threading

import pytest

from opc_manager.user_profile import UserProfile


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
    import opc_manager.user_profile as up

    monkeypatch.setattr(up, "_data_manager", None)
    return data_dir


@pytest.fixture()
def profile(_isolate_data_dir):
    import opc_manager.data_manager as dm

    dm.init_db()
    return UserProfile()


class TestRecordInteraction:
    """record_interaction 测试"""

    def test_record_success(self, profile):
        profile.record_interaction(
            intent_type="analysis",
            goal="竞品分析",
            skill_used="search",
            result_success=True,
        )
        history = profile.get_decision_history(limit=10)
        assert len(history) == 1
        assert history[0]["intent_type"] == "analysis"
        assert history[0]["success"] is True

    def test_record_failure(self, profile):
        profile.record_interaction(
            intent_type="creation",
            goal="写文档",
            skill_used="report",
            result_success=False,
        )
        history = profile.get_decision_history()
        assert len(history) == 1
        assert history[0]["success"] is False

    def test_record_with_feedback(self, profile):
        profile.record_interaction(
            intent_type="search",
            goal="搜索资料",
            skill_used="search",
            result_success=True,
            user_feedback="很好用",
        )
        history = profile.get_decision_history()
        assert history[0]["user_feedback"] == "很好用"

    def test_record_multiple(self, profile):
        for i in range(5):
            profile.record_interaction(
                intent_type="analysis",
                goal=f"目标{i}",
                skill_used="search",
                result_success=True,
            )
        history = profile.get_decision_history()
        assert len(history) == 5


class TestGetPreferredSkills:
    """get_preferred_skills 测试"""

    def test_empty_returns_empty_list(self, profile):
        result = profile.get_preferred_skills("analysis")
        assert result == []

    def test_returns_successful_skills_ordered(self, profile):
        profile.record_interaction("analysis", "g1", "search", True)
        profile.record_interaction("analysis", "g2", "report", True)
        profile.record_interaction("analysis", "g3", "search", True)
        result = profile.get_preferred_skills("analysis")
        assert "search" in result
        assert "report" in result
        assert result.index("search") < result.index("report")

    def test_excludes_failed(self, profile):
        profile.record_interaction("analysis", "g1", "search", False)
        result = profile.get_preferred_skills("analysis")
        assert result == []

    def test_filters_by_intent_type(self, profile):
        profile.record_interaction("analysis", "g1", "search", True)
        profile.record_interaction("creation", "g2", "report", True)
        result = profile.get_preferred_skills("analysis")
        assert "search" in result
        assert "report" not in result


class TestGetUsagePatterns:
    """get_usage_patterns 测试"""

    def test_empty_patterns(self, profile):
        patterns = profile.get_usage_patterns()
        assert patterns["total_interactions"] == 0
        assert patterns["top_skills"] == []
        assert patterns["top_intents"] == []
        assert patterns["success_rate"] == 0.0

    def test_with_data(self, profile):
        profile.record_interaction("analysis", "g1", "search", True)
        profile.record_interaction("analysis", "g2", "search", True)
        profile.record_interaction("creation", "g3", "report", False)
        patterns = profile.get_usage_patterns()
        assert patterns["total_interactions"] == 3
        assert patterns["success_rate"] == round(2 / 3, 2)
        assert len(patterns["top_skills"]) == 2
        assert len(patterns["top_intents"]) == 2

    def test_peak_hours(self, profile):
        profile.record_interaction("analysis", "g1", "search", True)
        patterns = profile.get_usage_patterns()
        assert isinstance(patterns["peak_hours"], list)


class TestGetSkillRecommendations:
    """get_skill_recommendations 测试"""

    def test_empty_returns_empty(self, profile):
        recs = profile.get_skill_recommendations()
        assert recs == []

    def test_failed_intent_recommendation(self, profile):
        profile.record_interaction("analysis", "失败目标", "search", False)
        recs = profile.get_skill_recommendations()
        assert len(recs) >= 1
        assert recs[0]["type"] == "failed_intent"
        assert recs[0]["fail_count"] == 1

    def test_failed_with_successful_suggestion(self, profile):
        profile.record_interaction("analysis", "失败", "search", False)
        profile.record_interaction("analysis", "成功", "report", True)
        recs = profile.get_skill_recommendations()
        assert len(recs) >= 1
        assert "report" in recs[0]["suggestion"]

    def test_unknown_intent_recommendation(self, profile):
        profile.record_interaction("unknown", "未知意图", "none", False)
        recs = profile.get_skill_recommendations()
        unknown_recs = [r for r in recs if r["type"] == "unknown_intent"]
        assert len(unknown_recs) >= 1


class TestPreferences:
    """record_preference / get_preference 测试"""

    def test_set_and_get(self, profile):
        profile.record_preference("theme", "dark")
        assert profile.get_preference("theme") == "dark"

    def test_get_with_default(self, profile):
        assert profile.get_preference("nonexistent", "default_val") == "default_val"

    def test_get_empty_default(self, profile):
        assert profile.get_preference("nonexistent") == ""


class TestGetDecisionHistory:
    """get_decision_history 测试"""

    def test_empty_history(self, profile):
        history = profile.get_decision_history()
        assert history == []

    def test_history_with_limit(self, profile):
        for i in range(10):
            profile.record_interaction("analysis", f"目标{i}", "search", True)
        history = profile.get_decision_history(limit=5)
        assert len(history) == 5

    def test_history_ordered_by_created_at_desc(self, profile):
        profile.record_interaction("analysis", "第一", "search", True)
        profile.record_interaction("analysis", "第二", "search", True)
        history = profile.get_decision_history()
        assert len(history) == 2


class TestUpdateInteraction:
    """update_interaction 测试"""

    def test_update_success(self, profile):
        profile.record_interaction("analysis", "目标", "search", True)
        history = profile.get_decision_history()
        interaction_id = history[0]["id"]
        result = profile.update_interaction(interaction_id, success=False)
        assert result is True
        updated = profile.get_decision_history()
        assert updated[0]["success"] is False

    def test_update_nonexistent_returns_false(self, profile):
        result = profile.update_interaction("nonexistent_id", success=True)
        assert result is False

    def test_update_no_valid_fields_returns_false(self, profile):
        profile.record_interaction("analysis", "目标", "search", True)
        history = profile.get_decision_history()
        interaction_id = history[0]["id"]
        result = profile.update_interaction(interaction_id, invalid_field="value")
        assert result is False

    def test_update_multiple_fields(self, profile):
        profile.record_interaction("analysis", "目标", "search", True)
        history = profile.get_decision_history()
        interaction_id = history[0]["id"]
        result = profile.update_interaction(
            interaction_id, goal="新目标", user_feedback="更新反馈"
        )
        assert result is True
        updated = profile.get_decision_history()
        assert updated[0]["goal"] == "新目标"
        assert updated[0]["user_feedback"] == "更新反馈"
