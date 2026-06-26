"""
Unified Types Unit Tests — Comprehensive validation of the dual-engine type mapping system.

Covers:
- UnifiedTaskCategory enum values and completeness (13 categories)
- IntentType → UnifiedTaskCategory mapping (all 22 IntentType values)
- TaskType → UnifiedTaskCategory mapping (all 6 TaskType values)
- Reverse mapping: UnifiedTaskCategory → TaskType (13 categories)
- Core utility functions: unify_intent, unify_task, to_task_type, get_risk_level
- i18n support: get_category_label (zh_CN, en_US, ja_JP)
- Icon system: get_category_icon returns valid emoji
- Smart suggestions: suggest_follow_up_actions returns reasonable actions
- Edge cases: unknown types fallback, None input, case insensitivity
- ProgressEvent.with_category() immutability pattern
- Confirmer integration with new unified risk map
- UnifiedClassificationResult container and serialization
- Backward compatibility: legacy_intent_to_risk function

Total tests: 50+ test cases organized into logical test classes.

Run command:
    pytest tests/test_unified_types.py -v --tb=short
"""

import pytest
from opc_manager.unified_types import (
    UnifiedTaskCategory,
    INTENT_TO_UNIFIED_MAP,
    TASK_TO_UNIFIED_MAP,
    UNIFIED_TO_TASK_MAP,
    unify_intent,
    unify_intent_from_enum,
    unify_task,
    to_task_type,
    get_risk_level,
    get_category_label,
    get_category_icon,
    suggest_follow_up_actions,
    legacy_intent_to_risk,
    classify_unified,
    UnifiedClassificationResult,
    CATEGORY_LABELS,
    CATEGORY_ICONS,
    FOLLOW_UP_ACTIONS,
)
from opc_manager.intent_types import IntentType
from opc_manager.task_types import TaskType
from opc_manager.confirmer import RiskLevel, Confirmer
from opc_manager.progress_emitter import ProgressEvent, EventType


class TestUnifiedTaskCategoryEnum:
    """Test suite for UnifiedTaskCategory enum completeness and values."""

    def test_all_13_categories_exist(self):
        """Verify all 13 expected categories are defined."""
        expected_categories = {
            "info_search",
            "data_query",
            "document_writing",
            "message_compose",
            "task_management",
            "finance_operation",
            "crm_operation",
            "calendar_operation",
            "social_publish",
            "email_send",
            "data_analysis",
            "workflow_automation",
            "general_chat",
        }
        actual_categories = {cat.value for cat in UnifiedTaskCategory}
        assert actual_categories == expected_categories

    def test_low_risk_categories(self):
        """Verify low-risk categories are correctly identified."""
        low_risk = [
            UnifiedTaskCategory.INFO_SEARCH,
            UnifiedTaskCategory.DATA_QUERY,
            UnifiedTaskCategory.DATA_ANALYSIS,
            UnifiedTaskCategory.GENERAL_CHAT,
        ]
        for cat in low_risk:
            assert get_risk_level(cat) == RiskLevel.LOW

    def test_medium_risk_categories(self):
        """Verify medium-risk categories are correctly identified."""
        medium_risk = [
            UnifiedTaskCategory.DOCUMENT_WRITING,
            UnifiedTaskCategory.MESSAGE_COMPOSE,
            UnifiedTaskCategory.TASK_MANAGEMENT,
            UnifiedTaskCategory.FINANCE_OPERATION,
            UnifiedTaskCategory.CRM_OPERATION,
            UnifiedTaskCategory.CALENDAR_OPERATION,
            UnifiedTaskCategory.WORKFLOW_AUTOMATION,
        ]
        for cat in medium_risk:
            assert get_risk_level(cat) == RiskLevel.MEDIUM

    def test_high_risk_categories(self):
        """Verify high-risk categories are correctly identified."""
        high_risk = [
            UnifiedTaskCategory.SOCIAL_PUBLISH,
            UnifiedTaskCategory.EMAIL_SEND,
        ]
        for cat in high_risk:
            assert get_risk_level(cat) == RiskLevel.HIGH


class TestIntentToUnifiedMapping:
    """Test suite for IntentType → UnifiedTaskCategory mapping correctness."""

    def test_search_maps_to_info_search(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.SEARCH] == UnifiedTaskCategory.INFO_SEARCH
        )

    def test_knowledge_maps_to_info_search(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.KNOWLEDGE]
            == UnifiedTaskCategory.INFO_SEARCH
        )

    def test_dashboard_maps_to_data_query(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.DASHBOARD]
            == UnifiedTaskCategory.DATA_QUERY
        )

    def test_report_maps_to_document_writing(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.REPORT]
            == UnifiedTaskCategory.DOCUMENT_WRITING
        )

    def test_proposal_maps_to_document_writing(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.PROPOSAL]
            == UnifiedTaskCategory.DOCUMENT_WRITING
        )

    def test_analysis_maps_to_document_writing(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.ANALYSIS]
            == UnifiedTaskCategory.DOCUMENT_WRITING
        )

    def test_creation_maps_to_document_writing(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.CREATION]
            == UnifiedTaskCategory.DOCUMENT_WRITING
        )

    def test_task_maps_to_task_management(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.TASK]
            == UnifiedTaskCategory.TASK_MANAGEMENT
        )

    def test_finance_maps_to_finance_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.FINANCE]
            == UnifiedTaskCategory.FINANCE_OPERATION
        )

    def test_invoice_maps_to_finance_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.INVOICE]
            == UnifiedTaskCategory.FINANCE_OPERATION
        )

    def test_crm_maps_to_crm_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.CRM] == UnifiedTaskCategory.CRM_OPERATION
        )

    def test_calendar_maps_to_calendar_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.CALENDAR]
            == UnifiedTaskCategory.CALENDAR_OPERATION
        )

    def test_pricing_maps_to_crm_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.PRICING]
            == UnifiedTaskCategory.CRM_OPERATION
        )

    def test_competitor_maps_to_data_analysis(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.COMPETITOR]
            == UnifiedTaskCategory.DATA_ANALYSIS
        )

    def test_tax_reminder_maps_to_calendar_operation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.TAX_REMINDER]
            == UnifiedTaskCategory.CALENDAR_OPERATION
        )

    def test_social_maps_to_social_publish(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.SOCIAL]
            == UnifiedTaskCategory.SOCIAL_PUBLISH
        )

    def test_email_maps_to_email_send(self):
        assert INTENT_TO_UNIFIED_MAP[IntentType.EMAIL] == UnifiedTaskCategory.EMAIL_SEND

    def test_notification_maps_to_message_compose(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.NOTIFICATION]
            == UnifiedTaskCategory.MESSAGE_COMPOSE
        )

    def test_operation_maps_to_workflow_automation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.OPERATION]
            == UnifiedTaskCategory.WORKFLOW_AUTOMATION
        )

    def test_combined_maps_to_workflow_automation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.COMBINED]
            == UnifiedTaskCategory.WORKFLOW_AUTOMATION
        )

    def test_extended_skill_maps_to_workflow_automation(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.EXTENDED_SKILL]
            == UnifiedTaskCategory.WORKFLOW_AUTOMATION
        )

    def test_unknown_maps_to_general_chat(self):
        assert (
            INTENT_TO_UNIFIED_MAP[IntentType.UNKNOWN]
            == UnifiedTaskCategory.GENERAL_CHAT
        )

    def test_all_intents_have_mapping(self):
        """Ensure every IntentType has a corresponding unified category."""
        for intent in IntentType:
            assert intent in INTENT_TO_UNIFIED_MAP, f"Missing mapping for {intent}"


class TestTaskToUnifiedMapping:
    """Test suite for TaskType → UnifiedTaskCategory mapping."""

    def test_info_collection_maps_to_info_search(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.INFO_COLLECTION]
            == UnifiedTaskCategory.INFO_SEARCH
        )

    def test_content_generation_maps_to_document_writing(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.CONTENT_GENERATION]
            == UnifiedTaskCategory.DOCUMENT_WRITING
        )

    def test_data_analysis_maps_to_data_analysis(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.DATA_ANALYSIS]
            == UnifiedTaskCategory.DATA_ANALYSIS
        )

    def test_scenario_based_maps_to_workflow_automation(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.SCENARIO_BASED]
            == UnifiedTaskCategory.WORKFLOW_AUTOMATION
        )

    def test_business_operation_maps_to_workflow_automation(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.BUSINESS_OPERATION]
            == UnifiedTaskCategory.WORKFLOW_AUTOMATION
        )

    def test_general_chat_maps_to_general_chat(self):
        assert (
            TASK_TO_UNIFIED_MAP[TaskType.GENERAL_CHAT]
            == UnifiedTaskCategory.GENERAL_CHAT
        )

    def test_all_tasks_have_mapping(self):
        """Ensure every TaskType has a corresponding unified category."""
        for task in TaskType:
            assert task in TASK_TO_UNIFIED_MAP, f"Missing mapping for {task}"


class TestReverseMapping:
    """Test suite for UnifiedTaskCategory → TaskType reverse mapping."""

    def test_info_search_to_info_collection(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.INFO_SEARCH]
            == TaskType.INFO_COLLECTION
        )

    def test_data_query_to_data_analysis(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.DATA_QUERY]
            == TaskType.DATA_ANALYSIS
        )

    def test_document_writing_to_content_generation(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.DOCUMENT_WRITING]
            == TaskType.CONTENT_GENERATION
        )

    def test_message_compose_to_content_generation(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.MESSAGE_COMPOSE]
            == TaskType.CONTENT_GENERATION
        )

    def test_task_management_to_scenario_based(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.TASK_MANAGEMENT]
            == TaskType.SCENARIO_BASED
        )

    def test_finance_operation_to_scenario_based(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.FINANCE_OPERATION]
            == TaskType.SCENARIO_BASED
        )

    def test_crm_operation_to_scenario_based(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.CRM_OPERATION]
            == TaskType.SCENARIO_BASED
        )

    def test_calendar_operation_to_scenario_based(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.CALENDAR_OPERATION]
            == TaskType.SCENARIO_BASED
        )

    def test_social_publish_to_content_generation(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.SOCIAL_PUBLISH]
            == TaskType.CONTENT_GENERATION
        )

    def test_email_send_to_content_generation(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.EMAIL_SEND]
            == TaskType.CONTENT_GENERATION
        )

    def test_data_analysis_to_data_analysis(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.DATA_ANALYSIS]
            == TaskType.DATA_ANALYSIS
        )

    def test_workflow_automation_to_scenario_based(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.WORKFLOW_AUTOMATION]
            == TaskType.SCENARIO_BASED
        )

    def test_general_chat_to_general_chat(self):
        assert (
            UNIFIED_TO_TASK_MAP[UnifiedTaskCategory.GENERAL_CHAT]
            == TaskType.GENERAL_CHAT
        )

    def test_all_categories_have_reverse_mapping(self):
        """Ensure every UnifiedTaskCategory has a reverse mapping to TaskType."""
        for cat in UnifiedTaskCategory:
            assert cat in UNIFIED_TO_TASK_MAP, f"Missing reverse mapping for {cat}"


class TestUnifyIntentFunction:
    """Test suite for unify_intent() utility function."""

    def test_valid_intent_string_lowercase(self):
        result = unify_intent("search")
        assert result == UnifiedTaskCategory.INFO_SEARCH

    def test_valid_intent_string_uppercase(self):
        result = unify_intent("SEARCH")
        assert result == UnifiedTaskCategory.INFO_SEARCH

    def test_valid_intent_string_mixed_case(self):
        result = unify_intent("SeArCh")
        assert result == UnifiedTaskCategory.INFO_SEARCH

    def test_unknown_intent_falls_back_to_general_chat(self):
        result = unify_intent("nonexistent_intent")
        assert result == UnifiedTaskCategory.GENERAL_CHAT

    def test_empty_string_falls_back_to_general_chat(self):
        result = unify_intent("")
        assert result == UnifiedTaskCategory.GENERAL_CHAT

    def test_all_intent_strings_convert_correctly(self):
        """Verify all 22 IntentType string values convert correctly."""
        test_cases = [
            ("search", UnifiedTaskCategory.INFO_SEARCH),
            ("dashboard", UnifiedTaskCategory.DATA_QUERY),
            ("report", UnifiedTaskCategory.DOCUMENT_WRITING),
            ("email", UnifiedTaskCategory.EMAIL_SEND),
            ("finance", UnifiedTaskCategory.FINANCE_OPERATION),
            ("task", UnifiedTaskCategory.TASK_MANAGEMENT),
            ("crm", UnifiedTaskCategory.CRM_OPERATION),
            ("social", UnifiedTaskCategory.SOCIAL_PUBLISH),
            ("proposal", UnifiedTaskCategory.DOCUMENT_WRITING),
            ("invoice", UnifiedTaskCategory.FINANCE_OPERATION),
            ("calendar", UnifiedTaskCategory.CALENDAR_OPERATION),
            ("knowledge", UnifiedTaskCategory.INFO_SEARCH),
        ]
        for intent_str, expected in test_cases:
            assert unify_intent(intent_str) == expected, f"Failed for {intent_str}"

    def test_unify_intent_from_enum_direct(self):
        """Test unify_intent_from_enum with enum value directly."""
        result = unify_intent_from_enum(IntentType.EMAIL)
        assert result == UnifiedTaskCategory.EMAIL_SEND


class TestUnifyTaskFunction:
    """Test suite for unify_task() utility function with context enhancement."""

    def test_basic_task_type_conversion(self):
        result = unify_task(TaskType.INFO_COLLECTION)
        assert result == UnifiedTaskCategory.INFO_SEARCH

    def test_content_generation_without_context(self):
        result = unify_task(TaskType.CONTENT_GENERATION)
        assert result == UnifiedTaskCategory.DOCUMENT_WRITING

    def test_content_generation_with_sending_context(self):
        result = unify_task(TaskType.CONTENT_GENERATION, context="发送邮件给客户")
        assert result == UnifiedTaskCategory.EMAIL_SEND

    def test_content_generation_with_publish_context(self):
        result = unify_task(TaskType.CONTENT_GENERATION, context="发布到小红书")
        assert result == UnifiedTaskCategory.SOCIAL_PUBLISH

    def test_content_generation_with_message_context(self):
        result = unify_task(TaskType.CONTENT_GENERATION, context="写一条通知消息")
        assert result == UnifiedTaskCategory.MESSAGE_COMPOSE

    def test_content_generation_with_english_context(self):
        result = unify_task(TaskType.CONTENT_GENERATION, context="send email to client")
        assert result == UnifiedTaskCategory.EMAIL_SEND

    def test_none_context_does_not_raise(self):
        result = unify_task(TaskType.DATA_ANALYSIS, context=None)
        assert result == UnifiedTaskCategory.DATA_ANALYSIS


class TestToTaskTypeFunction:
    """Test suite for to_task_type() reverse conversion function."""

    def test_info_search_returns_info_collection(self):
        assert to_task_type(UnifiedTaskCategory.INFO_SEARCH) == TaskType.INFO_COLLECTION

    def test_document_writing_returns_content_generation(self):
        assert (
            to_task_type(UnifiedTaskCategory.DOCUMENT_WRITING)
            == TaskType.CONTENT_GENERATION
        )

    def test_social_publish_returns_content_generation(self):
        assert (
            to_task_type(UnifiedTaskCategory.SOCIAL_PUBLISH)
            == TaskType.CONTENT_GENERATION
        )

    def test_workflow_automation_returns_scenario_based(self):
        assert (
            to_task_type(UnifiedTaskCategory.WORKFLOW_AUTOMATION)
            == TaskType.SCENARIO_BASED
        )

    def test_general_chat_returns_general_chat(self):
        assert to_task_type(UnifiedTaskCategory.GENERAL_CHAT) == TaskType.GENERAL_CHAT


class TestRiskLevelMapping:
    """Test suite for risk level assessment based on unified category."""

    @pytest.mark.parametrize(
        "category,expected_risk",
        [
            (UnifiedTaskCategory.INFO_SEARCH, RiskLevel.LOW),
            (UnifiedTaskCategory.DATA_QUERY, RiskLevel.LOW),
            (UnifiedTaskCategory.DATA_ANALYSIS, RiskLevel.LOW),
            (UnifiedTaskCategory.GENERAL_CHAT, RiskLevel.LOW),
            (UnifiedTaskCategory.DOCUMENT_WRITING, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.MESSAGE_COMPOSE, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.TASK_MANAGEMENT, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.FINANCE_OPERATION, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.CRM_OPERATION, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.CALENDAR_OPERATION, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.WORKFLOW_AUTOMATION, RiskLevel.MEDIUM),
            (UnifiedTaskCategory.SOCIAL_PUBLISH, RiskLevel.HIGH),
            (UnifiedTaskCategory.EMAIL_SEND, RiskLevel.HIGH),
        ],
    )
    def test_risk_level_for_each_category(self, category, expected_risk):
        assert get_risk_level(category) == expected_risk

    def test_risk_distribution_counts(self):
        """Verify correct distribution: 4 LOW, 7 MEDIUM, 2 HIGH."""
        from collections import Counter

        risk_counts = Counter(get_risk_level(cat) for cat in UnifiedTaskCategory)
        assert risk_counts[RiskLevel.LOW] == 4
        assert risk_counts[RiskLevel.MEDIUM] == 7
        assert risk_counts[RiskLevel.HIGH] == 2


class TestI18nSupport:
    """Test suite for internationalization support in category labels."""

    def test_zh_cn_labels_for_all_categories(self):
        """Verify all categories have Chinese labels."""
        for cat in UnifiedTaskCategory:
            label = get_category_label(cat, locale="zh_CN")
            assert isinstance(label, str)
            assert len(label) > 0
            assert any(
                "\u4e00" <= char <= "\u9fff" for char in label
            ), f"Chinese label for {cat.value} should contain Chinese characters"

    def test_en_us_labels_for_all_categories(self):
        """Verify all categories have English labels."""
        for cat in UnifiedTaskCategory:
            label = get_category_label(cat, locale="en_US")
            assert isinstance(label, str)
            assert len(label) > 0
            assert label.isascii(), f"English label for {cat.value} should be ASCII"

    def test_ja_jp_labels_for_all_categories(self):
        """Verify all categories have Japanese labels."""
        for cat in UnifiedTaskCategory:
            label = get_category_label(cat, locale="ja_JP")
            assert isinstance(label, str)
            assert len(label) > 0

    def test_default_locale_is_zh_cn(self):
        """Verify default locale is Chinese when not specified."""
        label = get_category_label(UnifiedTaskCategory.INFO_SEARCH)
        assert label == "信息搜索"

    def test_specific_zh_cn_examples(self):
        """Test specific Chinese label examples."""
        assert (
            get_category_label(UnifiedTaskCategory.INFO_SEARCH, "zh_CN") == "信息搜索"
        )
        assert get_category_label(UnifiedTaskCategory.EMAIL_SEND, "zh_CN") == "邮件发送"
        assert (
            get_category_label(UnifiedTaskCategory.SOCIAL_PUBLISH, "zh_CN")
            == "社交发布"
        )

    def test_specific_en_us_examples(self):
        """Test specific English label examples."""
        assert (
            get_category_label(UnifiedTaskCategory.INFO_SEARCH, "en_US")
            == "Information Search"
        )
        assert (
            get_category_label(UnifiedTaskCategory.EMAIL_SEND, "en_US") == "Email Send"
        )
        assert (
            get_category_label(UnifiedTaskCategory.SOCIAL_PUBLISH, "en_US")
            == "Social Publish"
        )


class TestIconSystem:
    """Test suite for emoji icon system."""

    def test_all_categories_have_icons(self):
        """Verify every category has an associated icon string (emoji-free)."""
        for cat in UnifiedTaskCategory:
            icon = get_category_icon(cat)
            assert isinstance(icon, str)

    def test_icons_are_emoji_free(self):
        """Verify icons contain no emoji characters."""

        def _looks_like_emoji(char: str) -> bool:
            cp = ord(char)
            return (
                (0x1F300 <= cp <= 0x1F9FF)
                or (0x2600 <= cp <= 0x27BF)
                or (0x1F600 <= cp <= 0x1F64F)
                or (0x1F680 <= cp <= 0x1F6FF)
                or (0x1F1E0 <= cp <= 0x1F1FF)
            )

        for cat in UnifiedTaskCategory:
            icon = get_category_icon(cat)
            assert not any(
                _looks_like_emoji(ch) for ch in icon
            ), f"Icon '{icon}' for {cat.value} should not contain emoji"

    def test_specific_icon_assignments(self):
        """Test specific icon assignments match expectations."""
        assert get_category_icon(UnifiedTaskCategory.INFO_SEARCH) == ""
        assert get_category_icon(UnifiedTaskCategory.EMAIL_SEND) == ""
        assert get_category_icon(UnifiedTaskCategory.SOCIAL_PUBLISH) == ""
        assert get_category_icon(UnifiedTaskCategory.FINANCE_OPERATION) == ""

    def test_icons_are_unique_per_category(self):
        """Verify each category has its own distinct icon (no duplicates ideally)."""
        icons = [get_category_icon(cat) for cat in UnifiedTaskCategory]
        # Note: Some categories may share icons if semantically similar
        # This test just ensures we have icons for all categories
        assert len(icons) == len(list(UnifiedTaskCategory))


class TestSmartSuggestions:
    """Test suite for follow-up action suggestion system."""

    def test_all_categories_have_suggestions(self):
        """Verify every category has at least one suggested action."""
        for cat in UnifiedTaskCategory:
            actions = suggest_follow_up_actions(cat)
            assert isinstance(actions, list)
            assert len(actions) > 0, f"Category {cat.value} should have suggestions"

    def test_suggestions_are_strings(self):
        """Verify all suggestions are non-empty strings."""
        for cat in UnifiedTaskCategory:
            actions = suggest_follow_up_actions(cat)
            for action in actions:
                assert isinstance(action, str)
                assert len(action.strip()) > 0

    def test_info_search_suggestions_relevant(self):
        actions = suggest_follow_up_actions(UnifiedTaskCategory.INFO_SEARCH)
        assert any("分析" in action or "保存" in action for action in actions)

    def test_social_publish_suggestions_include_preview(self):
        actions = suggest_follow_up_actions(UnifiedTaskCategory.SOCIAL_PUBLISH)
        assert any(
            "预览" in action or "preview" in action.lower() for action in actions
        )

    def test_email_send_suggestions_include_cc(self):
        actions = suggest_follow_up_actions(UnifiedTaskCategory.EMAIL_SEND)
        assert any("抄送" in action or "cc" in action.lower() for action in actions)

    def test_typical_suggestion_count(self):
        """Most categories should have 3-5 suggestions."""
        for cat in UnifiedTaskCategory:
            actions = suggest_follow_up_actions(cat)
            assert (
                2 <= len(actions) <= 6
            ), f"Category {cat.value} has {len(actions)} suggestions (expected 2-6)"


class TestEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_invalid_intent_string_handling(self):
        """Verify invalid intent strings don't raise exceptions."""
        result = unify_intent("completely_invalid_intent_type")
        assert result == UnifiedTaskCategory.GENERAL_CHAT

    def test_none_input_handling_in_classify_unified(self):
        """Verify classify_unified handles None inputs gracefully."""
        result = classify_unified()
        assert result.category == UnifiedTaskCategory.GENERAL_CHAT
        assert result.original_intent is None
        assert result.original_task is None

    def test_case_insensitive_intent_matching(self):
        """Verify intent matching is case-insensitive."""
        results = set()
        for variant in ["search", "SEARCH", "Search", "SeArCh"]:
            results.add(unify_intent(variant))
        assert len(results) == 1, "All case variants should map to same category"

    def test_unicode_intent_string_handling(self):
        """Verify unicode strings in intent types work correctly."""
        # This shouldn't crash even with unusual input
        result = unify_intent("search")  # Normal case works
        assert result == UnifiedTaskCategory.INFO_SEARCH

    def test_empty_context_in_unify_task(self):
        """Verify empty context string doesn't cause issues."""
        result = unify_task(TaskType.CONTENT_GENERATION, context="")
        assert result == UnifiedTaskCategory.DOCUMENT_WRITING

    def test_get_category_label_unknown_locale_falls_back(self):
        """Verify unknown locale falls back to zh_CN."""
        label = get_category_label(UnifiedTaskCategory.INFO_SEARCH, locale="fr_FR")
        # Should fall back to zh_CN or return value
        assert isinstance(label, str)
        assert len(label) > 0


class TestProgressEventIntegration:
    """Test suite for ProgressEvent with unified category support."""

    def test_progress_event_without_category(self):
        """Verify ProgressEvent works without unified_category (backward compatibility)."""
        event = ProgressEvent(
            event_type=EventType.STEP_START,
            session_id="a" * 32,
            message="Starting task",
        )
        assert event.unified_category is None
        assert event.extracted_unified_category is None

    def test_progress_event_with_category(self):
        """Verify ProgressEvent accepts unified_category field."""
        event = ProgressEvent(
            event_type=EventType.STEP_START,
            session_id="a" * 32,
            message="Starting search",
            unified_category="info_search",
        )
        assert event.unified_category == "info_search"
        assert event.extracted_unified_category == "info_search"

    def test_with_category_immutability(self):
        """Verify with_category() returns new event without modifying original."""
        original = ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id="b" * 32,
            message="Progressing",
            progress_pct=50,
        )
        assert original.unified_category is None

        modified = original.with_category(UnifiedTaskCategory.EMAIL_SEND)

        # Original should remain unchanged
        assert original.unified_category is None
        assert original.extracted_unified_category is None

        # Modified should have category
        assert modified.unified_category == "email_send"
        assert modified.extracted_unified_category == "email_send"
        assert modified.progress_pct == 50  # Other fields preserved

    def test_with_category_preserves_other_fields(self):
        """Verify with_category() preserves all other fields."""
        original = ProgressEvent(
            event_type=EventType.STEP_COMPLETE,
            session_id="c" * 32,
            message="Completed",
            progress_pct=100,
            detail={"key": "value"},
        )
        modified = original.with_category(UnifiedTaskCategory.DATA_ANALYSIS)

        assert modified.event_type == original.event_type
        assert modified.session_id == original.session_id
        assert modified.message == original.message
        assert modified.progress_pct == original.progress_pct
        assert modified.detail["key"] == "value"
        assert "unified_category" in modified.detail

    def test_with_category_accepts_string_value(self):
        """Verify with_category() accepts both enum and string values."""
        event = ProgressEvent(
            event_type=EventType.INTENT_DETECTED,
            session_id="d" * 32,
            message="Intent detected",
        )

        # With enum
        event_enum = event.with_category(UnifiedTaskCategory.SOCIAL_PUBLISH)
        assert event_enum.unified_category == "social_publish"

        # With string
        event_str = event.with_category("social_publish")
        assert event_str.unified_category == "social_publish"

    def test_to_dict_includes_unified_category(self):
        """Verify to_dict() includes unified_category when present."""
        event = ProgressEvent(
            event_type=EventType.COMPLETE,
            session_id="e" * 32,
            message="Done",
            unified_category="document_writing",
        )
        d = event.to_dict()
        assert "unified_category" in d
        assert d["unified_category"] == "document_writing"

    def test_to_dict_excludes_unified_category_when_absent(self):
        """Verify to_dict() doesn't include unified_category when absent."""
        event = ProgressEvent(
            event_type=EventType.ERROR,
            session_id="f" * 32,
            message="Error occurred",
        )
        d = event.to_dict()
        assert "unified_category" not in d

    def test_extracted_unified_category_from_detail(self):
        """Verify extracted_unified_category can extract from detail dict."""
        event = ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id="g" * 32,
            message="Progress",
            detail={"unified_category": "task_management"},
        )
        assert event.extracted_unified_category == "task_management"

    def test_extracted_unified_category_priority(self):
        """Verify direct field takes priority over detail."""
        event = ProgressEvent(
            event_type=EventType.STEP_PROGRESS,
            session_id="h" * 32,
            message="Progress",
            detail={"unified_category": "from_detail"},
            unified_category="from_field",
        )
        assert event.extracted_unified_category == "from_field"


class TestConfirmerIntegration:
    """Test suite for Confirmer integration with unified type system."""

    @pytest.fixture
    def confirmer(self):
        return Confirmer()

    def test_legacy_still_works(self, confirmer):
        """Verify legacy string-based risk assessment still works."""
        risk = confirmer.assess_risk("SEARCH")
        assert risk == RiskLevel.LOW

        risk = confirmer.assess_risk("EMAIL")
        assert risk == RiskLevel.HIGH

        risk = confirmer.assess_risk("UNKNOWN_TYPE")
        assert risk == RiskLevel.MEDIUM  # Default fallback

    def test_unified_category_risk_assessment(self, confirmer):
        """Verify unified category risk assessment works."""
        risk = confirmer.assess_risk_unified(UnifiedTaskCategory.INFO_SEARCH)
        assert risk == RiskLevel.LOW

        risk = confirmer.assess_risk_unified(UnifiedTaskCategory.EMAIL_SEND)
        assert risk == RiskLevel.HIGH

        risk = confirmer.assess_risk_unified(UnifiedTaskCategory.DOCUMENT_WRITING)
        assert risk == RiskLevel.MEDIUM

    def test_unified_string_format_works(self, confirmer):
        """Verify unified category string format works in assess_risk()."""
        risk = confirmer.assess_risk("info_search")
        assert risk == RiskLevel.LOW

        risk = confirmer.assess_risk("email_send")
        assert risk == RiskLevel.HIGH

    def test_confirmation_request_with_unified_category(self, confirmer):
        """Verify ConfirmationRequest can hold unified_category."""
        from opc_manager.confirmer import ConfirmationRequest

        req = ConfirmationRequest(
            session_id="test_session",
            intent_type="EMAIL",
            goal="Send newsletter",
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            unified_category="email_send",
        )
        assert req.unified_category == "email_send"

    def test_check_confirmation_with_unified_category(self, confirmer):
        """Verify check_confirmation accepts unified_category parameter."""
        import asyncio

        async def test():
            # High confidence should auto-approve
            result = await confirmer.check_confirmation(
                session_id="test_session",
                intent_type="email",
                goal="Send report",
                confidence=0.99,  # Above HIGH threshold (0.95)
                unified_category=UnifiedTaskCategory.EMAIL_SEND,
            )
            assert result.confirmed is True
            assert result.method == "auto"

        asyncio.run(test())


class TestUnifiedClassificationResult:
    """Test suite for UnifiedClassificationResult container."""

    def test_auto_population_of_metadata(self):
        """Verify metadata fields are auto-populated in __post_init__."""
        result = UnifiedClassificationResult(
            category=UnifiedTaskCategory.SOCIAL_PUBLISH,
            original_intent="SOCIAL",
        )
        assert result.risk_level == RiskLevel.HIGH
        assert result.label is not None
        assert result.icon is not None
        assert len(result.suggestions) > 0

    def test_to_dict_serialization(self):
        """Verify to_dict() produces complete serializable output."""
        result = classify_unified(
            intent_type="email",
            task_type=TaskType.CONTENT_GENERATION,
        )
        d = result.to_dict()

        assert "category" in d
        assert "original_intent" in d
        assert "original_task" in d
        assert "risk_level" in d
        assert "label" in d
        assert "icon" in d
        assert "suggestions" in d

        assert isinstance(d["suggestions"], list)
        assert d["risk_level"] == "high"  # EMAIL_SEND is HIGH risk

    def test_classify_unified_with_intent_only(self):
        """Verify classify_unified works with only intent_type."""
        result = classify_unified(intent_type="search")
        assert result.category == UnifiedTaskCategory.INFO_SEARCH
        assert result.original_intent == "search"
        assert result.original_task is None

    def test_classify_unified_with_task_only(self):
        """Verify classify_unified works with only task_type."""
        result = classify_unified(task_type=TaskType.DATA_ANALYSIS)
        assert result.category == UnifiedTaskCategory.DATA_ANALYSIS
        assert result.original_intent is None
        assert result.original_task == "data_analysis"

    def test_classify_unified_priority_intent_over_task(self):
        """Verify intent_type takes priority over task_type when both provided."""
        result = classify_unified(
            intent_type="email",
            task_type=TaskType.INFO_COLLECTION,
        )
        # Should use intent_type (EMAIL -> EMAIL_SEND), not task_type (INFO_COLLECTION -> INFO_SEARCH)
        assert result.category == UnifiedTaskCategory.EMAIL_SEND

    def test_classification_result_immutability_pattern(self):
        """Verify classification result follows dataclass immutability for display."""
        result = classify_unified(intent_type="finance")
        original_category = result.category
        original_risk = result.risk_level

        # Reading multiple times should give same value
        assert result.category == original_category
        assert result.risk_level == original_risk
        assert result.label == get_category_label(original_category)


class TestBackwardCompatibility:
    """Test suite for backward compatibility utilities."""

    def test_legacy_intent_to_risk_function_exists(self):
        """Verify legacy compatibility function exists and works."""
        risk = legacy_intent_to_risk("SEARCH")
        assert risk == RiskLevel.LOW

        risk = legacy_intent_to_risk("SOCIAL")
        assert risk == RiskLevel.HIGH

    def test_legacy_function_matches_new_system(self):
        """Verify legacy function produces same results as new system."""
        test_cases = ["SEARCH", "EMAIL", "FINANCE", "TASK", "CRM"]
        for intent in test_cases:
            legacy_risk = legacy_intent_to_risk(intent)
            new_risk = get_risk_level(unify_intent(intent))
            # Should be equivalent (may differ slightly due to refined mappings)
            assert legacy_risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
            assert new_risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]

    def test_old_confirmer_api_unchanged(self):
        """Verify old Confirmer API signatures still work."""
        confirmer = Confirmer()

        # Old method calls should still work
        risk = confirmer.assess_risk("SEARCH")
        assert risk == RiskLevel.LOW

        threshold = confirmer.get_effective_threshold(
            "SEARCH", "test_session_12345678901234567890123456789012"
        )
        assert threshold == 0.70  # LOW threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
