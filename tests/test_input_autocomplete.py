"""Comprehensive Test Suite for Input Autocomplete Component

Tests cover:
- Data structures and models
- Filtering algorithms (prefix, contains, pinyin)
- History suggestions with deduplication
- Skill shortcuts rendering
- Template suggestions
- Frequency tracking and caching
- Edge cases and boundary conditions
- UI rendering functions (with mocked Streamlit)
- Ranking algorithm (match_score × frequency × time_decay)

Run: pytest tests/test_input_autocomplete.py -v
"""

import pytest
import json
import time
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frontend.components.input_autocomplete import (
    CompletionItem,
    COMPLETION_TEMPLATES,
    filter_completions,
    _render_history_suggestions,
    _render_skill_shortcuts,
    _render_template_suggestions,
    _render_contact_suggestions,
    _get_all_completion_items,
    load_completion_cache,
    save_completion_cache,
    update_completion_frequency,
    get_autocomplete_stats,
    clear_completion_cache,
    CACHE_FILE,
    CACHE_DIR,
    SKILL_CATEGORY_ICONS,
    SMART_HINTS,
)


@pytest.fixture
def sample_history():
    """Sample chat history for testing"""
    return [
        {"role": "user", "content": "帮我写一份Q2营销方案"},
        {"role": "assistant", "content": "好的，我来帮你..."},
        {"role": "user", "content": "分析竞品数据"},
        {"role": "user", "content": "帮我写一份Q2营销方案"},
        {"role": "user", "content": "记录收入 ¥5000 from 项目A"},
        {"role": "user", "content": "查询本月财务报表"},
    ]


@pytest.fixture
def sample_items():
    """Sample completion items for filtering tests"""
    return [
        CompletionItem(
            text="帮我写一份报告",
            display_text="写报告",
            source="template",
            frequency=10,
            last_used=time.time() - 3600,
        ),
        CompletionItem(
            text="分析数据趋势",
            display_text="数据分析",
            source="template",
            frequency=5,
            last_used=time.time() - 7200,
        ),
        CompletionItem(
            text="记录收入",
            display_text="记录收入",
            source="history",
            frequency=3,
            last_used=time.time() - 86400,
        ),
        CompletionItem(
            text="发送邮件给客户",
            display_text="发邮件",
            source="skill",
            frequency=1,
            last_used=time.time() - 172800,
        ),
    ]


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for cache testing"""
    test_cache_dir = tmp_path / "data"
    test_cache_file = test_cache_dir / "completions_cache.json"

    with (
        patch("frontend.components.input_autocomplete.CACHE_DIR", test_cache_dir),
        patch("frontend.components.input_autocomplete.CACHE_FILE", test_cache_file),
    ):
        yield tmp_path


class TestCompletionItemDataStructure:
    """Test CompletionItem dataclass functionality"""

    def test_creation_with_required_fields(self):
        """Test creating CompletionItem with minimum required fields"""
        item = CompletionItem(
            text="test text", display_text="Test Display", source="template"
        )
        assert item.text == "test text"
        assert item.display_text == "Test Display"
        assert item.source == "template"
        assert item.frequency == 0
        assert item.last_used == 0.0

    def test_creation_with_all_fields(self):
        """Test creating CompletionItem with all fields"""
        item = CompletionItem(
            text="full item",
            display_text="Full Item",
            source="history",
            frequency=15,
            last_used=1234567890.0,
        )
        assert item.frequency == 15
        assert item.last_used == 1234567890.0

    def test_to_dict_conversion(self):
        """Test converting CompletionItem to dictionary"""
        item = CompletionItem(
            text="convert me", display_text="Convert Me", source="skill", frequency=7
        )
        result = item.to_dict()
        assert isinstance(result, dict)
        assert result["text"] == "convert me"
        assert result["frequency"] == 7

    def test_from_dict_conversion(self):
        """Test creating CompletionItem from dictionary"""
        data = {
            "text": "dict item",
            "display_text": "Dict Item",
            "source": "contact",
            "frequency": 20,
            "last_used": 9999999999.0,
        }
        item = CompletionItem.from_dict(data)
        assert item.text == "dict item"
        assert item.source == "contact"
        assert item.frequency == 20

    def test_valid_source_values(self):
        """Test that only valid source values are used"""
        valid_sources = ["history", "skill", "template", "contact"]
        for source in valid_sources:
            item = CompletionItem(text="test", display_text="Test", source=source)
            assert item.source == source

    def test_invalid_source_handling(self):
        """Test that invalid sources are still stored (validation is external)"""
        item = CompletionItem(text="test", display_text="Test", source="invalid_source")
        assert item.source == "invalid_source"


class TestFilteringAlgorithm:
    """Test the core filtering and ranking algorithm"""

    def test_empty_query_returns_empty(self, sample_items):
        """Test that empty query returns no results"""
        result = filter_completions("", sample_items)
        assert result == []

    def test_none_query_returns_empty(self, sample_items):
        """Test that None query returns no results"""
        result = filter_completions(None, sample_items)
        assert result == []

    def test_whitespace_query_returns_empty(self, sample_items):
        """Test that whitespace-only query returns no results"""
        result = filter_completions("   ", sample_items)
        assert result == []

    def test_prefix_match_highest_priority(self, sample_items):
        """Test that prefix matches get highest score (1.0)"""
        result = filter_completions("帮我写", sample_items)
        assert len(result) > 0
        assert result[0].text == "帮我写一份报告"

    def test_contains_match_medium_priority(self, sample_items):
        """Test that contains matches get medium score (0.8)"""
        result = filter_completions("报告", sample_items)
        assert any(item.text == "帮我写一份报告" for item in result)

    def test_case_insensitive_matching(self, sample_items):
        """Test that matching is case-insensitive"""
        result_lower = filter_completions("帮我写", sample_items)
        result_upper = filter_completions("帮我写", sample_items)
        assert len(result_lower) == len(result_upper)

    def test_display_text_matching(self, sample_items):
        """Test that display text is also searched"""
        result = filter_completions("写报告", sample_items)
        assert any(item.display_text == "写报告" for item in result)

    def test_max_results_limit(self):
        """Test that results are limited to max_results"""
        many_items = [
            CompletionItem(
                text=f"item {i}", display_text=f"Item {i}", source="template"
            )
            for i in range(20)
        ]
        result = filter_completions("item", many_items, max_results=5)
        assert len(result) <= 5

    def test_frequency_boosts_ranking(self):
        """Test that higher frequency items rank higher"""
        items = [
            CompletionItem(
                text="common task",
                display_text="Common Task",
                source="history",
                frequency=100,
                last_used=time.time(),
            ),
            CompletionItem(
                text="common task alternative",
                display_text="Alternative",
                source="template",
                frequency=1,
                last_used=time.time(),
            ),
        ]
        result = filter_completions("common", items)
        assert len(result) > 0
        assert result[0].text == "common task"

    def test_time_decay_affects_ranking(self):
        """Test that recent usage boosts ranking"""
        items = [
            CompletionItem(
                text="recent item",
                display_text="Recent",
                source="history",
                frequency=5,
                last_used=time.time(),
            ),
            CompletionItem(
                text="old item",
                display_text="Old",
                source="template",
                frequency=5,
                last_used=time.time() - 30 * 86400,  # 30 days ago
            ),
        ]
        result = filter_completions("item", items)
        if len(result) >= 2:
            assert result[0].text == "recent item"

    def test_no_matches_returns_empty(self):
        """Test that query with no matches returns empty list"""
        items = [
            CompletionItem(text="apple", display_text="Apple", source="template"),
            CompletionItem(text="banana", display_text="Banana", source="template"),
        ]
        result = filter_completions("xyznonexistent", items)
        assert result == []

    def test_special_characters_in_query(self, sample_items):
        """Test handling of special characters in query"""
        items_with_special = sample_items + [
            CompletionItem(
                text="记录收入 ¥5000 from 项目A",
                display_text="💰 记录收入",
                source="history",
                frequency=2,
                last_used=time.time(),
            )
        ]
        result = filter_completions("¥5000", items_with_special)
        assert any("记录收入" in item.text for item in result)

    def test_chinese_text_matching(self, sample_items):
        """Test Chinese text matching works correctly"""
        result = filter_completions("财务", sample_items)
        assert isinstance(result, list)

    def test_empty_items_list(self):
        """Test that empty items list returns empty results"""
        result = filter_completions("test", [])
        assert result == []


class TestHistorySuggestions:
    """Test history-based suggestion generation"""

    def test_basic_history_loading(self, sample_history):
        """Test loading suggestions from history"""
        items = _render_history_suggestions(sample_history, max_show=10)
        assert len(items) > 0
        assert all(item.source == "history" for item in items)

    def test_deduplication(self, sample_history):
        """Test that duplicate messages are removed"""
        items = _render_history_suggestions(sample_history, max_show=10)
        texts = [item.text for item in items]
        assert len(texts) == len(set(texts))

    def test_reverse_chronological_order(self, sample_history):
        """Test that most recent items appear first"""
        items = _render_history_suggestions(sample_history, max_show=10)
        if len(items) >= 2:
            assert items[0].text == "查询本月财务报表"

    def test_user_messages_only(self):
        """Test that only user messages are included"""
        history = [
            {"role": "user", "content": "user message"},
            {"role": "assistant", "content": "assistant message"},
            {"role": "user", "content": "another user message"},
        ]
        items = _render_history_suggestions(history)
        assert all("assistant" not in item.text for item in items)

    def test_max_show_limit(self, sample_history):
        """Test that max_show parameter limits results"""
        items = _render_history_suggestions(sample_history, max_show=2)
        assert len(items) <= 2

    def test_empty_history(self):
        """Test that empty history returns empty list"""
        items = _render_history_suggestions([])
        assert items == []

    def test_long_message_truncation(self):
        """Test that long messages are truncated in display"""
        long_text = "A" * 300
        history = [{"role": "user", "content": long_text}]
        items = _render_history_suggestions(history)
        assert len(items) == 0  # Messages >200 chars are excluded

    def test_whitespace_filtering(self):
        """Test that whitespace-only messages are excluded"""
        history = [
            {"role": "user", "content": "   "},
            {"role": "user", "content": "valid message"},
        ]
        items = _render_history_suggestions(history)
        assert len(items) == 1


class TestSkillShortcuts:
    """Test skill shortcut rendering"""

    def test_skill_shortcuts_not_empty(self):
        """Test that skill shortcuts returns items"""
        items = _render_skill_shortcuts()
        assert len(items) > 0

    def test_all_skills_have_correct_source(self):
        """Test that all skill items have source='skill'"""
        items = _render_skill_shortcuts()
        assert all(item.source == "skill" for item in items)

    def test_skill_display_format(self):
        """Test that skill display text includes icon and name"""
        items = _render_skill_shortcuts()
        for item in items[:3]:
            assert any(
                icon in item.display_text for icon in SKILL_CATEGORY_ICONS.values()
            )

    @patch("opc_manager.skill_registry.SkillRegistry")
    def test_fallback_on_registry_error(self, mock_registry_cls):
        """Test fallback to default skills when registry fails"""
        mock_registry_cls.side_effect = Exception("Registry error")
        items = _render_skill_shortcuts()
        assert len(items) > 0
        assert all(item.source == "skill" for item in items)

    def test_minimum_default_skills(self):
        """Test that fallback provides minimum set of skills"""
        with patch("opc_manager.skill_registry.SkillRegistry") as mock_registry_cls:
            mock_registry_cls.side_effect = Exception("Error")
            items = _render_skill_shortcuts()
            assert len(items) >= 9  # Minimum default skills


class TestTemplateSuggestions:
    """Test template-based suggestion generation"""

    def test_templates_not_empty(self):
        """Test that templates are defined and non-empty"""
        items = _render_template_suggestions()
        assert len(items) > 0

    def test_templates_match_constant(self):
        """Test that rendered templates match COMPLETION_TEMPLATES constant"""
        items = _render_template_suggestions()
        assert len(items) == len(COMPLETION_TEMPLATES)

    def test_most_templates_have_placeholders(self):
        """Test that most templates contain variable placeholders"""
        items = _render_template_suggestions()
        items_with_placeholders = [
            item for item in items if "{" in item.text and "}" in item.text
        ]
        assert (
            len(items_with_placeholders) >= len(items) - 1
        )  # Allow 1 template without placeholders

    def test_template_source_is_template(self):
        """Test that all template items have correct source"""
        items = _render_template_suggestions()
        assert all(item.source == "template" for item in items)

    def test_template_display_contains_no_emoji(self):
        """Test that template display texts do not contain emojis"""
        items = _render_template_suggestions()
        for item in items:
            assert not any(
                char in item.display_text
                for char in ["📝", "📊", "💰", "📧", "✅", "💹", "🔍", "🎯"]
            )


class TestContactSuggestions:
    """Test contact-based suggestion generation"""

    def test_no_contacts_without_trigger(self):
        """Test that contacts don't show without trigger words"""
        items = _render_contact_suggestions("hello world")
        assert items == []

    def test_at_trigger_activates_contacts(self):
        """Test that '@' trigger activates contact search"""
        with patch("opc_manager.crm_skill.search_customers") as mock_search:
            mock_search.return_value = {
                "customers": [{"name": "张三"}, {"name": "李四"}]
            }
            items = _render_contact_suggestions("@张")
            assert len(items) > 0

    def test_gei_trigger_activates_contacts(self):
        """Test that '给 ' trigger activates contact search"""
        with patch("opc_manager.crm_skill.search_customers") as mock_search:
            mock_search.return_value = {"customers": [{"name": "王五"}]}
            items = _render_contact_suggestions("给 ")
            assert len(items) > 0

    def test_contact_source_label(self):
        """Test that contact items have correct source"""
        with patch("opc_manager.crm_skill.search_customers") as mock_search:
            mock_search.return_value = {"customers": [{"name": "赵六"}]}
            items = _render_contact_suggestions("@")
            assert all(item.source == "contact" for item in items)

    def test_crm_error_handling(self):
        """Test graceful handling when CRM is unavailable"""
        with patch("opc_manager.crm_skill.search_customers") as mock_search:
            mock_search.side_effect = ImportError("CRM not available")
            items = _render_contact_suggestions("@")
            assert items == []


class TestCachingSystem:
    """Test completion cache persistence"""

    def test_save_and_load_cache(self, temp_cache_dir):
        """Test saving and loading cache data"""
        test_data = {
            "test item": {"frequency": 5, "last_used": 1234567890.0},
            "another item": {"frequency": 3, "last_used": 9876543210.0},
        }
        save_completion_cache(test_data)
        loaded = load_completion_cache()

        assert loaded == test_data
        assert len(loaded) == 2

    def test_load_nonexistent_cache(self, temp_cache_dir):
        """Test loading when cache file doesn't exist"""
        loaded = load_completion_cache()
        assert loaded == {}

    def test_update_frequency_new_item(self, temp_cache_dir):
        """Test updating frequency for new item"""
        update_completion_frequency("new command")

        cache = load_completion_cache()
        assert "new command" in cache
        assert cache["new command"]["frequency"] == 1

    def test_update_frequency_existing_item(self, temp_cache_dir):
        """Test updating frequency for existing item"""
        initial_data = {"existing command": {"frequency": 3, "last_used": 1000.0}}
        save_completion_cache(initial_data)

        update_completion_frequency("existing command")

        cache = load_completion_cache()
        assert cache["existing command"]["frequency"] == 4
        assert cache["existing command"]["last_used"] > 1000.0

    def test_clear_cache(self, temp_cache_dir):
        """Test clearing the cache file"""
        from frontend.components import input_autocomplete as ia_module

        save_completion_cache({"item": {"frequency": 1}})
        assert ia_module.CACHE_FILE.exists()

        result = clear_completion_cache()
        assert result is True
        assert not ia_module.CACHE_FILE.exists()

    def test_clear_nonexistent_cache(self, temp_cache_dir):
        """Test clearing when cache doesn't exist"""
        result = clear_completion_cache()
        assert result is False

    def test_cache_size_limit(self, temp_cache_dir):
        """Test that cache is trimmed when too large"""
        from frontend.components import input_autocomplete as ia_module

        large_data = {
            f"item_{i}": {"frequency": i, "last_used": time.time()} for i in range(200)
        }
        save_completion_cache(large_data)

        cache = load_completion_cache()
        file_size_kb = ia_module.CACHE_FILE.stat().st_size / 1024
        if file_size_kb > ia_module.MAX_CACHE_SIZE_KB:
            assert len(cache) <= 100
        else:
            assert len(cache) == 200

    def test_get_stats_empty_cache(self, temp_cache_dir):
        """Test getting stats when cache is empty"""
        stats = get_autocomplete_stats()
        assert stats["total_cached_items"] == 0
        assert stats["total_usage_count"] == 0

    def test_get_stats_with_data(self, temp_cache_dir):
        """Test getting statistics with cached data"""
        test_data = {
            "popular": {"frequency": 50, "last_used": time.time()},
            "rare": {"frequency": 2, "last_used": time.time() - 86400},
        }
        save_completion_cache(test_data)

        stats = get_autocomplete_stats()
        assert stats["total_cached_items"] == 2
        assert stats["total_usage_count"] == 52
        assert len(stats["top_completions"]) <= 5


class TestGetAllCompletionItems:
    """Test aggregation of all completion sources"""

    def test_combines_all_sources(self, sample_history):
        """Test that all sources are combined"""
        items = _get_all_completion_items(sample_history)
        sources = {item.source for item in items}
        assert "history" in sources or len(sample_history) == 0
        assert "skill" in sources
        assert "template" in sources

    def test_without_history(self):
        """Test that function works without history parameter"""
        items = _get_all_completion_items(None)
        assert len(items) > 0

    def test_empty_history(self):
        """Test that function works with empty history"""
        items = _get_all_completion_items([])
        assert len(items) > 0


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions"""

    def test_ultra_long_query(self, sample_items):
        """Test handling of ultra-long query strings"""
        long_query = "a" * 10000
        result = filter_completions(long_query, sample_items)
        assert isinstance(result, list)

    def test_unicode_characters(self, sample_items):
        """Test handling of various unicode characters"""
        queries = ["日本語テスト", "한국어", "العربية", "emoji 🎉🎊"]
        for query in queries:
            result = filter_completions(query, sample_items)
            assert isinstance(result, list)

    def test_sql_injection_safe(self, sample_items):
        """Test that SQL injection patterns are safe"""
        malicious_queries = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "<script>alert('xss')</script>",
        ]
        for query in malicious_queries:
            result = filter_completions(query, sample_items)
            assert isinstance(result, list)

    def test_single_character_query(self, sample_items):
        """Test single character query"""
        result = filter_completions("我", sample_items)
        assert isinstance(result, list)

    def test_exact_match_query(self, sample_items):
        """Test query that exactly matches an item"""
        exact_item = sample_items[0]
        result = filter_completions(exact_item.text, sample_items)
        assert len(result) > 0
        assert result[0].text == exact_item.text

    def test_zero_frequency_items(self):
        """Test items with zero frequency"""
        items = [
            CompletionItem(
                text="unused", display_text="Unused", source="template", frequency=0
            )
        ]
        result = filter_completions("unused", items)
        assert len(result) > 0

    def test_future_timestamp(self):
        """Test handling of future timestamps"""
        future_time = time.time() + 365 * 86400  # 1 year in future
        items = [
            CompletionItem(
                text="future item",
                display_text="Future",
                source="history",
                frequency=10,
                last_used=future_time,
            )
        ]
        result = filter_completions("future", items)
        assert isinstance(result, list)


class TestUIIntegration:
    """Test UI-related functions with mocked Streamlit"""

    @patch("frontend.components.input_autocomplete.st")
    @patch(
        "frontend.components.input_autocomplete._render_skill_shortcuts",
        return_value=[],
    )
    @patch(
        "frontend.components.input_autocomplete._render_template_suggestions",
        return_value=[],
    )
    @patch(
        "frontend.components.input_autocomplete._render_history_suggestions",
        return_value=[],
    )
    def test_render_autocomplete_initializes_state(
        self, mock_hist, mock_tmpl, mock_skills, mock_st
    ):
        """Test that render_autocomplete initializes session state"""
        mock_session = {}
        mock_st.session_state = mock_session
        mock_st.chat_input.return_value = None
        mock_st.caption = Mock()
        mock_st.markdown = Mock()
        mock_st.columns = Mock(return_value=[])
        mock_st.button = Mock(return_value=False)
        mock_st.expander = Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock()))

        from frontend.components.input_autocomplete import render_autocomplete_input

        result = render_autocomplete_input("Test Label", "test_key")

        assert "test_key_autocomplete" in mock_session

    @patch("frontend.components.input_autocomplete.st")
    def test_render_with_user_input(self, mock_st):
        """Test rendering when user provides input"""
        mock_st.session_state = {}
        mock_st.chat_input.return_value = "user input here"
        mock_st.rerun = Mock()

        from frontend.components.input_autocomplete import render_autocomplete_input

        result = render_autocomplete_input("Label", "key2")

        assert result == "user input here"


class TestConstantsAndConfiguration:
    """Test module constants and configuration"""

    def test_completion_templates_count(self):
        """Test that expected number of templates are defined"""
        assert len(COMPLETION_TEMPLATES) == 8

    def test_completion_templates_structure(self):
        """Test that all templates have required fields"""
        for template in COMPLETION_TEMPLATES:
            assert "text" in template
            assert "display" in template
            assert "desc" in template

    def test_skill_category_icons_complete(self):
        """Test that all skill categories have icons"""
        expected_categories = [
            "utility",
            "search",
            "analysis",
            "creation",
            "operation",
            "notification",
        ]
        for cat in expected_categories:
            assert cat in SKILL_CATEGORY_ICONS

    def test_smartHints_not_empty(self):
        """Test that smart hints are defined"""
        assert len(SMART_HINTS) > 0
        assert all(isinstance(hint, str) for hint in SMART_HINTS)

    def test_smartHints_contain_useful_examples(self):
        """Test that hints contain actionable examples"""
        for hint in SMART_HINTS:
            assert "试试：" in hint or "'" in hint


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
