"""Comprehensive tests for Smart Suggestions System

Tests cover:
- Rule engine for all 4 suggestion categories (follow_up, related, improvement, exploration)
- Confidence calculation and ranking
- Suggestion deduplication and limiting
- Edge cases (empty history, no feedback, all features used)
- Context building from session state
- Action type handling
- Boundary conditions
"""

import pytest
from unittest.mock import patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frontend.components.smart_suggestions import (
    Suggestion,
    generate_suggestions,
    _generate_follow_up_suggestions,
    _generate_related_suggestions,
    _generate_improvement_suggestions,
    _generate_exploration_suggestions,
    build_context_from_session,
    TASK_TYPE_FOLLOW_UP_MAP,
    COMPLEMENTARY_TASKS,
)


class TestSuggestionDataStructure:
    """Test Suggestion dataclass structure and validation"""

    def test_suggestion_creation_with_all_fields(self):
        """Test creating a Suggestion with all required fields"""
        sug = Suggestion(
            id="test_1",
            title="测试建议",
            description="这是一个测试描述",
            icon="🧪",
            action_type="quick_task",
            action_payload={"prompt": "测试"},
            confidence=0.85,
            category="follow_up",
        )
        assert sug.id == "test_1"
        assert sug.title == "测试建议"
        assert sug.confidence == 0.85
        assert sug.category == "follow_up"

    def test_suggestion_confidence_range_valid(self):
        """Test that confidence is within valid range [0, 1]"""
        sug = Suggestion(
            id="valid_conf",
            title="Valid",
            description="Test",
            icon="✅",
            action_type="quick_task",
            action_payload={},
            confidence=0.5,
            category="follow_up",
        )
        assert 0 <= sug.confidence <= 1

    def test_action_types_are_valid(self):
        """Test that only allowed action types are used"""
        valid_types = {"quick_task", "navigate_tab", "open_settings"}
        for task_type, suggestions in TASK_TYPE_FOLLOW_UP_MAP.items():
            for s in suggestions:
                assert (
                    s.action_type in valid_types
                ), f"Invalid action type {s.action_type} for {s.id}"

    def test_categories_are_valid(self):
        """Test that only allowed categories are used"""
        valid_cats = {"follow_up", "related", "improvement", "exploration"}
        for task_type, suggestions in TASK_TYPE_FOLLOW_UP_MAP.items():
            for s in suggestions:
                assert (
                    s.category in valid_cats
                ), f"Invalid category {s.category} for {s.id}"


class TestFollowUpSuggestions:
    """Test follow-up suggestion generation based on task type"""

    def test_content_generation_followups(self):
        """Test content generation tasks get export/share suggestions"""
        context = {"last_task_type": "content_generation"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) > 0
        titles = [s.title for s in suggestions]
        assert any("导出" in t or "PDF" in t for t in titles)

    def test_data_analysis_followups(self):
        """Test data analysis tasks get deep-dive/report suggestions"""
        context = {"last_task_type": "data_analysis"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) > 0
        titles = [s.title for s in suggestions]
        assert any("分析" in t or "报告" in t or "对比" in t for t in titles)

    def test_info_collection_followups(self):
        """Test info collection tasks get plan/template suggestions"""
        context = {"last_task_type": "info_collection"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) > 0
        assert all(s.category == "follow_up" for s in suggestions)

    def test_business_operation_followups(self):
        """Test business operation tasks get report/expense/followup suggestions"""
        context = {"last_task_type": "business_operation"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) > 0
        has_navigate = any(s.action_type == "navigate_tab" for s in suggestions)
        assert has_navigate, "Business operations should have navigate_tab actions"

    def test_scenario_based_followups(self):
        """Test scenario-based tasks get review/rerun suggestions"""
        context = {"last_task_type": "scenario_based"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) >= 2

    def test_general_chat_followups(self):
        """Test general chat gets basic start-task suggestion"""
        context = {"last_task_type": "general_chat"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) >= 1

    def test_unknown_task_type_returns_empty(self):
        """Test unknown task type returns empty list"""
        context = {"last_task_type": "unknown_type_xyz"}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) == 0

    def test_empty_task_type_returns_empty(self):
        """Test empty task type returns empty list"""
        context = {"last_task_type": ""}
        suggestions = _generate_follow_up_suggestions(context)
        assert len(suggestions) == 0


class TestRelatedSuggestions:
    """Test related suggestions based on user history"""

    def test_related_from_history(self):
        """Test complementary tasks are suggested based on history"""
        context = {
            "last_task_type": "content_generation",
            "user_history": [
                {"task_type": "data_analysis"},
                {"task_type": "data_analysis"},
            ],
        }
        suggestions = _generate_related_suggestions(context)
        assert len(suggestions) > 0
        assert all(s.category == "related" for s in suggestions)

    def test_no_history_returns_empty(self):
        """Test empty history returns no related suggestions"""
        context = {"last_task_type": "content_generation", "user_history": []}
        suggestions = _generate_related_suggestions(context)
        assert len(suggestions) == 0

    def test_confidence_increases_with_frequency(self):
        """Test that more frequent complementary tasks get higher confidence"""
        context_low = {
            "last_task_type": "content_generation",
            "user_history": [{"task_type": "data_analysis"}],
        }
        context_high = {
            "last_task_type": "content_generation",
            "user_history": [{"task_type": "data_analysis"}] * 5,
        }
        sug_low = _generate_related_suggestions(context_low)
        sug_high = _generate_related_suggestions(context_high)
        if sug_low and sug_high:
            assert sug_high[0].confidence >= sug_low[0].confidence

    def test_no_complementary_in_history(self):
        """Test when history has no complementary task types"""
        context = {
            "last_task_type": "content_generation",
            "user_history": [
                {"task_type": "content_generation"},
                {"task_type": "content_generation"},
            ],
        }
        suggestions = _generate_related_suggestions(context)
        assert len(suggestions) == 0


class TestImprovementSuggestions:
    """Test improvement suggestions based on result quality"""

    def test_slow_execution_triggers_speed_suggestion(self):
        """Test slow execution (>10s) triggers speed improvement suggestion"""
        context = {"last_result": {"execution_time_ms": 15000}, "feedback_history": []}
        suggestions = _generate_improvement_suggestions(context)
        assert len(suggestions) > 0
        assert any("简化" in s.title or "加快" in s.title for s in suggestions)

    def test_fast_execution_no_speed_suggestion(self):
        """Test fast execution (<10s) does not trigger speed suggestion"""
        context = {"last_result": {"execution_time_ms": 5000}, "feedback_history": []}
        suggestions = _generate_improvement_suggestions(context)
        speed_sugs = [s for s in suggestions if "简化" in s.title or "加快" in s.title]
        assert len(speed_sugs) == 0

    def test_no_sources_triggers_search_suggestion(self):
        """Test zero sources triggers search optimization suggestion"""
        context = {
            "last_result": {"sources_count": 0, "execution_time_ms": 1000},
            "feedback_history": [],
        }
        suggestions = _generate_improvement_suggestions(context)
        assert any("搜索" in s.title or "优化" in s.title for s in suggestions)

    def test_with_sources_no_search_suggestion(self):
        """Test having sources does not trigger search suggestion"""
        context = {
            "last_result": {"sources_count": 5, "execution_time_ms": 1000},
            "feedback_history": [],
        }
        suggestions = _generate_improvement_suggestions(context)
        search_sugs = [s for s in suggestions if "搜索" in s.title]
        assert len(search_sugs) == 0

    def test_negative_feedback_triggers_improvement(self):
        """Test negative feedback triggers improvement suggestion"""
        context = {
            "last_result": {"execution_time_ms": 1000, "sources_count": 3},
            "feedback_history": [{"feedback": "bad"}],
        }
        suggestions = _generate_improvement_suggestions(context)
        assert any("改进" in s.title or "换个方式" in s.title for s in suggestions)

    def test_positive_feedback_no_improvement(self):
        """Test positive feedback does not trigger improvement suggestion"""
        context = {
            "last_result": {"execution_time_ms": 1000, "sources_count": 3},
            "feedback_history": [{"feedback": "good"}],
        }
        suggestions = _generate_improvement_suggestions(context)
        feedback_sugs = [s for s in suggestions if "改进" in s.title]
        assert len(feedback_sugs) == 0

    def test_multiple_issues_combined(self):
        """Test multiple issues generate multiple improvement suggestions"""
        context = {
            "last_result": {"execution_time_ms": 15000, "sources_count": 0},
            "feedback_history": [{"feedback": "bad"}, {"feedback": "bad"}],
        }
        suggestions = _generate_improvement_suggestions(context)
        assert len(suggestions) >= 2


class TestExplorationSuggestions:
    """Test exploration suggestions for unused features"""

    def test_all_unused_features_suggested(self):
        """Test when no features used, all are suggested"""
        context = {"features_used": set()}
        suggestions = _generate_exploration_suggestions(context)
        assert len(suggestions) == 3
        titles = [s.title for s in suggestions]
        assert any("仪表盘" in t for t in titles)
        assert any("技能市场" in t for t in titles)
        assert any("快捷键" in t for t in titles)

    def test_dashboard_used_not_suggested(self):
        """Test dashboard already used, not suggested again"""
        context = {"features_used": {"dashboard"}}
        suggestions = _generate_exploration_suggestions(context)
        dash_sugs = [s for s in suggestions if "仪表盘" in s.title]
        assert len(dash_sugs) == 0

    def test_all_features_used_returns_empty(self):
        """Test when all features used, no exploration suggestions"""
        context = {"features_used": {"dashboard", "marketplace", "shortcuts"}}
        suggestions = _generate_exploration_suggestions(context)
        assert len(suggestions) == 0

    def test_marketplace_suggestion_has_navigate_action(self):
        """Test marketplace suggestion uses navigate_tab action"""
        context = {"features_used": set()}
        suggestions = _generate_exploration_suggestions(context)
        market_sug = [s for s in suggestions if "技能市场" in s.title]
        if market_sug:
            assert market_sug[0].action_type == "navigate_tab"


class TestGenerateSuggestionsMain:
    """Test main generate_suggestions function"""

    def test_generates_all_categories(self):
        """Test that all 4 categories can be represented"""
        context = {
            "last_task_type": "content_generation",
            "last_result": {"execution_time_ms": 15000, "sources_count": 0},
            "user_history": [
                {"task_type": "data_analysis"},
                {"task_type": "data_analysis"},
            ],
            "deliverables_count": 5,
            "feedback_history": [{"feedback": "bad"}],
            "features_used": set(),
        }
        suggestions = generate_suggestions(context)
        categories = set(s.category for s in suggestions)
        assert len(categories) >= 2

    def test_suggestions_sorted_by_confidence(self):
        """Test suggestions are sorted by confidence descending"""
        context = {
            "last_task_type": "data_analysis",
            "last_result": {},
            "user_history": [],
            "deliverables_count": 0,
            "feedback_history": [],
            "features_used": set(),
        }
        suggestions = generate_suggestions(context)
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence >= suggestions[i + 1].confidence

    def test_max_10_suggestions_limit(self):
        """Test that maximum 10 suggestions are returned"""
        context = {
            "last_task_type": "content_generation",
            "last_result": {"execution_time_ms": 20000, "sources_count": 0},
            "user_history": [
                {"task_type": "data_analysis"},
                {"task_type": "data_analysis"},
                {"task_type": "data_analysis"},
                {"task_type": "content_generation"},
                {"task_type": "info_collection"},
            ],
            "deliverables_count": 10,
            "feedback_history": [{"feedback": "bad"}] * 3,
            "features_used": set(),
        }
        suggestions = generate_suggestions(context)
        assert len(suggestions) <= 10

    def test_deduplication_of_suggestions(self):
        """Test duplicate suggestion IDs are removed"""
        context = {
            "last_task_type": "content_generation",
            "last_result": {},
            "user_history": [],
            "deliverables_count": 0,
            "feedback_history": [],
            "features_used": set(),
        }
        suggestions = generate_suggestions(context)
        ids = [s.id for s in suggestions]
        assert len(ids) == len(set(ids))

    def test_empty_context_returns_empty_or_minimal(self):
        """Test empty context doesn't crash"""
        context = {}
        suggestions = generate_suggestions(context)
        assert isinstance(suggestions, list)


class TestBuildContextFromSession:
    """Test context building utility function"""

    @patch("frontend.components.smart_suggestions.st")
    def test_build_context_with_deliverables(self, mock_st):
        """Test context building extracts deliverable history"""
        mock_st.session_state = {
            "deliverables": [
                {"task_type": "content_generation", "created_at": "2024-01-01"},
                {"task_type": "data_analysis", "created_at": "2024-01-02"},
            ],
            "has_visited_dashboard": True,
            "shortcuts_shown": False,
        }
        context = build_context_from_session(
            last_task_type="content_generation",
            deliverables=mock_st.session_state["deliverables"],
        )
        assert context["last_task_type"] == "content_generation"
        assert len(context["user_history"]) == 2
        assert "dashboard" in context["features_used"]

    @patch("frontend.components.smart_suggestions.st")
    def test_build_context_empty_deliverables(self, mock_st):
        """Test context building with empty deliverables"""
        mock_st.session_state = {}
        context = build_context_from_session(
            last_task_type="general_chat", deliverables=[]
        )
        assert context["deliverables_count"] == 0
        assert len(context["user_history"]) == 0

    def test_build_context_default_values(self):
        """Test context building uses sensible defaults"""
        context = build_context_from_session()
        assert context["last_task_type"] == ""
        assert context["last_result"] == {}
        assert context["deliverables_count"] == 0
        assert context["feedback_history"] == []


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions"""

    def test_very_long_user_history(self):
        """Test system handles long user history gracefully"""
        context = {
            "last_task_type": "content_generation",
            "user_history": [{"task_type": "data_analysis"}] * 100,
            "features_used": set(),
        }
        suggestions = generate_suggestions(context)
        assert isinstance(suggestions, list)

    def test_special_characters_in_titles(self):
        """Test suggestions handle special characters properly"""
        sug = Suggestion(
            id="special",
            title='测试<>&"标题',
            description="描述with特殊chars",
            icon="🎯",
            action_type="quick_task",
            action_payload={},
            confidence=0.5,
            category="follow_up",
        )
        assert "<" in sug.title

    def test_zero_confidence_suggestion(self):
        """Test zero confidence suggestions are handled"""
        sug = Suggestion(
            id="zero_conf",
            title="Zero",
            description="Test",
            icon="0",
            action_type="quick_task",
            action_payload={},
            confidence=0.0,
            category="follow_up",
        )
        assert sug.confidence == 0.0

    def test_maximum_confidence_suggestion(self):
        """Test maximum confidence (1.0) suggestions are handled"""
        sug = Suggestion(
            id="max_conf",
            title="Max",
            description="Test",
            icon="💯",
            action_type="quick_task",
            action_payload={},
            confidence=1.0,
            category="follow_up",
        )
        assert sug.confidence == 1.0

    def test_all_task_types_have_followup_definitions(self):
        """Test all known task types have follow-up suggestions defined"""
        known_types = [
            "content_generation",
            "data_analysis",
            "info_collection",
            "business_operation",
            "scenario_based",
            "general_chat",
        ]
        for task_type in known_types:
            assert (
                task_type in TASK_TYPE_FOLLOW_UP_MAP
            ), f"Missing follow-up definitions for {task_type}"

    def test_complementary_tasks_coverage(self):
        """Test all task types have complementary task mappings"""
        known_types = [
            "content_generation",
            "data_analysis",
            "info_collection",
            "business_operation",
            "scenario_based",
            "general_chat",
        ]
        for task_type in known_types:
            assert (
                task_type in COMPLEMENTARY_TASKS
            ), f"Missing complementary mapping for {task_type}"
            assert len(COMPLEMENTARY_TASKS[task_type]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
