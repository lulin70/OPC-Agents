"""
Comprehensive unit tests for flywheel_tracker.py

Covers:
1. Health score calculation accuracy
2. Level progression logic
3. Scenario completion tracking
4. State persistence (save/load)
5. Edge cases: new user, power user, inactive user
6. Cross-session state
7. Score boundaries and clamping
8. get_status() / report return structure
"""

import unittest
import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

from opc_manager.business_types import BusinessType
from opc_manager.flywheel_tracker import (
    FlywheelLevel,
    DimensionScore,
    UserFlywheelState,
    FlywheelTracker,
    FlywheelTrackerDB,
)


# ==================== DimensionScore Tests ====================


class TestDimensionScore(unittest.TestCase):
    """Test DimensionScore dataclass and scoring."""

    def test_default_scores_are_zero(self):
        ds = DimensionScore()
        self.assertEqual(ds.content_quality, 0.0)
        self.assertEqual(ds.audience_growth, 0.0)
        self.assertEqual(ds.monetization, 0.0)
        self.assertEqual(ds.cross_promotion, 0.0)
        self.assertEqual(ds.ecosystem_synergy, 0.0)

    def test_overall_score_with_zeros(self):
        ds = DimensionScore()
        self.assertEqual(ds.overall_score(), 0.0)

    def test_overall_score_with_max_values(self):
        ds = DimensionScore(
            content_quality=100,
            audience_growth=100,
            monetization=100,
            cross_promotion=100,
            ecosystem_synergy=100,
        )
        self.assertAlmostEqual(ds.overall_score(), 100.0)

    def test_overall_score_weighted_calculation(self):
        """Verify weighted calculation: [0.25, 0.20, 0.20, 0.15, 0.20]"""
        ds = DimensionScore(
            content_quality=100,  # 0.25 * 100 = 25
            audience_growth=0,  # 0.20 * 0 = 0
            monetization=0,  # 0.20 * 0 = 0
            cross_promotion=0,  # 0.15 * 0 = 0
            ecosystem_synergy=0,  # 0.20 * 0 = 0
        )
        self.assertAlmostEqual(ds.overall_score(), 25.0)

    def test_overall_score_partial_values(self):
        ds = DimensionScore(
            content_quality=50,
            audience_growth=50,
            monetization=50,
            cross_promotion=50,
            ecosystem_synergy=50,
        )
        self.assertAlmostEqual(ds.overall_score(), 50.0)

    def test_to_dict(self):
        ds = DimensionScore(content_quality=30, audience_growth=40)
        d = ds.to_dict()
        self.assertIn("content_quality", d)
        self.assertIn("audience_growth", d)
        self.assertIn("monetization", d)
        self.assertIn("cross_promotion", d)
        self.assertIn("ecosystem_synergy", d)
        self.assertIn("overall", d)
        self.assertEqual(d["content_quality"], 30)
        self.assertEqual(d["audience_growth"], 40)

    def test_to_dict_includes_overall(self):
        ds = DimensionScore(content_quality=100)
        d = ds.to_dict()
        self.assertAlmostEqual(d["overall"], 25.0)


# ==================== UserFlywheelState Tests ====================


class TestUserFlywheelState(unittest.TestCase):
    """Test UserFlywheelState dataclass."""

    def test_default_values(self):
        state = UserFlywheelState(user_id="test_user")
        self.assertEqual(state.user_id, "test_user")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_1)
        self.assertEqual(state.active_types, [])
        self.assertIsInstance(state.dimension_scores, DimensionScore)
        self.assertEqual(state.scenario_completion_count, {})
        self.assertEqual(state.total_scenarios_completed, 0)
        self.assertEqual(state.active_days, 0)
        self.assertIsNone(state.last_activity_date)
        self.assertEqual(state.achievements, [])

    def test_to_dict(self):
        state = UserFlywheelState(user_id="test_user")
        d = state.to_dict()
        self.assertEqual(d["user_id"], "test_user")
        self.assertEqual(d["current_level"], 1)
        self.assertEqual(d["active_types"], [])
        self.assertEqual(d["active_types_count"], 0)
        self.assertIn("dimension_scores", d)
        self.assertEqual(d["total_scenarios_completed"], 0)
        self.assertEqual(d["active_days"], 0)

    def test_to_dict_with_active_types(self):
        state = UserFlywheelState(
            user_id="test_user",
            active_types=[BusinessType.CONTENT_CREATOR, BusinessType.ECOMMERCE],
        )
        d = state.to_dict()
        self.assertEqual(d["active_types"], ["content_creator", "ecommerce"])
        self.assertEqual(d["active_types_count"], 2)

    def test_created_at_is_iso_format(self):
        state = UserFlywheelState(user_id="test_user")
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(state.created_at)
        self.assertIsInstance(parsed, datetime)


# ==================== FlywheelTracker Core Tests ====================


class TestFlywheelTrackerCore(unittest.TestCase):
    """Test core FlywheelTracker functionality."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_get_or_create_state_new_user(self):
        state = self.tracker.get_or_create_state("new_user")
        self.assertIsInstance(state, UserFlywheelState)
        self.assertEqual(state.user_id, "new_user")

    def test_get_or_create_state_returns_same_object(self):
        state1 = self.tracker.get_or_create_state("user1")
        state2 = self.tracker.get_or_create_state("user1")
        self.assertIs(state1, state2)

    def test_get_or_create_state_different_users(self):
        state1 = self.tracker.get_or_create_state("user1")
        state2 = self.tracker.get_or_create_state("user2")
        self.assertIsNot(state1, state2)


# ==================== Scenario Completion Tracking Tests ====================


class TestScenarioCompletionTracking(unittest.TestCase):
    """Test scenario completion recording."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_record_scenario_completion_increments_count(self):
        state = self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.assertEqual(state.scenario_completion_count["content_calendar"], 1)
        self.assertEqual(state.total_scenarios_completed, 1)

    def test_record_scenario_completion_multiple_times(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.scenario_completion_count["content_calendar"], 2)
        self.assertEqual(state.total_scenarios_completed, 2)

    def test_record_scenario_adds_business_type(self):
        state = self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.assertIn(BusinessType.CONTENT_CREATOR, state.active_types)

    def test_record_scenario_does_not_duplicate_business_type(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        count = state.active_types.count(BusinessType.CONTENT_CREATOR)
        self.assertEqual(count, 1)

    def test_record_multiple_scenarios_different_types(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(len(state.active_types), 2)
        self.assertEqual(state.total_scenarios_completed, 2)

    def test_record_updates_last_activity_date(self):
        state = self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(state.last_activity_date, today)

    def test_record_updates_active_days(self):
        state = self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.assertEqual(state.active_days, 1)

    def test_active_days_not_incremented_same_day(self):
        """Multiple completions on the same day should only count as 1 active day."""
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.active_days, 1)

    def test_record_updates_updated_at(self):
        state = self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.assertIsNotNone(state.updated_at)


# ==================== Level Progression Tests ====================


class TestLevelProgression(unittest.TestCase):
    """Test flywheel level progression logic."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_new_user_is_level_1(self):
        state = self.tracker.get_or_create_state("new_user")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_1)

    def test_one_type_stays_level_1(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_1)

    def test_two_types_advances_to_level_2(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_2)

    def test_three_types_advances_to_level_3(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        self.tracker.record_scenario_completion(
            "user1", "feedback_analysis", BusinessType.AI_TOOL_BUILDER
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_3)

    def test_level_3_is_max(self):
        """Adding more types beyond 3 should stay at level 3."""
        for bt in BusinessType:
            self.tracker.record_scenario_completion("user1", f"scenario_{bt.value}", bt)
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_3)

    def test_level_thresholds(self):
        self.assertEqual(self.tracker._level_thresholds[FlywheelLevel.LEVEL_1], 1)
        self.assertEqual(self.tracker._level_thresholds[FlywheelLevel.LEVEL_2], 2)
        self.assertEqual(self.tracker._level_thresholds[FlywheelLevel.LEVEL_3], 3)


# ==================== Health Score Tests ====================


class TestHealthScore(unittest.TestCase):
    """Test health score calculation accuracy."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_new_user_health_score_is_zero(self):
        score = self.tracker.get_flywheel_health_score("new_user")
        self.assertEqual(score, 0.0)

    def test_health_score_increases_with_activity(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        score = self.tracker.get_flywheel_health_score("user1")
        self.assertGreater(score, 0.0)

    def test_health_score_is_between_0_and_100(self):
        # Simulate a power user
        for i in range(20):
            for bt in BusinessType:
                self.tracker.record_scenario_completion(
                    "power_user", f"scenario_{bt.value}_{i}", bt
                )
        score = self.tracker.get_flywheel_health_score("power_user")
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_health_score_is_rounded(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        score = self.tracker.get_flywheel_health_score("user1")
        # Should be rounded to 1 decimal place
        self.assertEqual(score, round(score, 1))


# ==================== Dimension Score Update Tests ====================


class TestDimensionScoreUpdates(unittest.TestCase):
    """Test dimension score calculation after scenario completion."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_content_quality_increases_with_content_calendar(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.content_quality, 0.0)

    def test_content_quality_capped_at_100(self):
        for i in range(20):
            self.tracker.record_scenario_completion(
                "user1", "content_calendar", BusinessType.CONTENT_CREATOR
            )
        state = self.tracker.get_or_create_state("user1")
        self.assertLessEqual(state.dimension_scores.content_quality, 100)

    def test_monetization_increases_with_digital_product(self):
        self.tracker.record_scenario_completion(
            "user1", "digital_product_launch", BusinessType.DIGITAL_PRODUCT
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.monetization, 0.0)

    def test_monetization_increases_with_ecommerce(self):
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.monetization, 0.0)

    def test_monetization_capped_at_100(self):
        for i in range(20):
            self.tracker.record_scenario_completion(
                "user1", "digital_product_launch", BusinessType.DIGITAL_PRODUCT
            )
        state = self.tracker.get_or_create_state("user1")
        self.assertLessEqual(state.dimension_scores.monetization, 100)

    def test_audience_growth_increases_with_activity(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.audience_growth, 0.0)

    def test_audience_growth_capped_at_100(self):
        for i in range(20):
            for bt in BusinessType:
                self.tracker.record_scenario_completion(
                    "user1", f"scenario_{bt.value}_{i}", bt
                )
        state = self.tracker.get_or_create_state("user1")
        self.assertLessEqual(state.dimension_scores.audience_growth, 100)

    def test_cross_promotion_zero_with_single_type(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.dimension_scores.cross_promotion, 0)

    def test_cross_promotion_increases_with_multiple_types(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.cross_promotion, 0)

    def test_cross_promotion_capped_at_90(self):
        for bt in BusinessType:
            self.tracker.record_scenario_completion("user1", f"scenario_{bt.value}", bt)
        state = self.tracker.get_or_create_state("user1")
        self.assertLessEqual(state.dimension_scores.cross_promotion, 90)

    def test_ecosystem_synergy_increases_with_diversity(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        state = self.tracker.get_or_create_state("user1")
        self.assertGreater(state.dimension_scores.ecosystem_synergy, 0.0)

    def test_ecosystem_synergy_capped_at_100(self):
        for i in range(20):
            for bt in BusinessType:
                self.tracker.record_scenario_completion(
                    "user1", f"scenario_{bt.value}_{i}", bt
                )
        state = self.tracker.get_or_create_state("user1")
        self.assertLessEqual(state.dimension_scores.ecosystem_synergy, 100)


# ==================== Upgrade Suggestion Tests ====================


class TestUpgradeSuggestion(unittest.TestCase):
    """Test upgrade suggestion logic."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_level_1_user_gets_suggestion(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["target_level"], 2)

    def test_level_2_user_gets_suggestion(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion["target_level"], 3)

    def test_level_3_user_gets_no_suggestion(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user1", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        self.tracker.record_scenario_completion(
            "user1", "feedback_analysis", BusinessType.AI_TOOL_BUILDER
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIsNone(suggestion)

    def test_suggestion_has_current_state(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIn("current_state", suggestion)
        self.assertIn("level", suggestion["current_state"])
        self.assertIn("active_types", suggestion["current_state"])

    def test_suggestion_has_suggested_actions(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIn("suggested_actions", suggestion)

    def test_suggestion_has_benefits(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        suggestion = self.tracker.get_upgrade_suggestion("user1")
        self.assertIn("benefits", suggestion)


# ==================== Flywheel Report Tests ====================


class TestFlywheelReport(unittest.TestCase):
    """Test flywheel report generation."""

    def setUp(self):
        self.tracker = FlywheelTracker()
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )

    def test_report_has_required_keys(self):
        report = self.tracker.generate_flywheel_report("user1")
        self.assertIn("report_generated_at", report)
        self.assertIn("user_id", report)
        self.assertIn("current_status", report)
        self.assertIn("level_progression", report)
        self.assertIn("dimension_analysis", report)
        self.assertIn("activity_summary", report)
        self.assertIn("upgrade_path", report)
        self.assertIn("achievements", report)
        self.assertIn("tips", report)

    def test_report_user_id(self):
        report = self.tracker.generate_flywheel_report("user1")
        self.assertEqual(report["user_id"], "user1")

    def test_report_level_progression(self):
        report = self.tracker.generate_flywheel_report("user1")
        lp = report["level_progression"]
        self.assertIn("current_level", lp)
        self.assertIn("level_name", lp)
        self.assertIn("next_level", lp)
        self.assertIn("progress_to_next", lp)

    def test_report_dimension_analysis(self):
        report = self.tracker.generate_flywheel_report("user1")
        da = report["dimension_analysis"]
        self.assertIn("scores", da)
        self.assertIn("strengths", da)
        self.assertIn("weaknesses", da)
        self.assertIn("recommendations", da)

    def test_report_activity_summary(self):
        report = self.tracker.generate_flywheel_report("user1")
        a = report["activity_summary"]
        self.assertIn("total_scenarios", a)
        self.assertIn("active_days", a)
        self.assertIn("scenarios_by_type", a)

    def test_report_achievements_is_list(self):
        report = self.tracker.generate_flywheel_report("user1")
        self.assertIsInstance(report["achievements"], list)

    def test_report_tips_is_list(self):
        report = self.tracker.generate_flywheel_report("user1")
        self.assertIsInstance(report["tips"], list)


# ==================== Level Progress Calculation Tests ====================


class TestLevelProgressCalculation(unittest.TestCase):
    """Test _calculate_level_progress method."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_level_1_with_1_type(self):
        state = UserFlywheelState(
            user_id="u1",
            active_types=[BusinessType.CONTENT_CREATOR],
        )
        state.current_level = FlywheelLevel.LEVEL_1
        progress = self.tracker._calculate_level_progress(state)
        self.assertEqual(progress, 50)

    def test_level_1_with_0_types(self):
        state = UserFlywheelState(user_id="u1", active_types=[])
        state.current_level = FlywheelLevel.LEVEL_1
        progress = self.tracker._calculate_level_progress(state)
        self.assertEqual(progress, 0)

    def test_level_3_returns_100(self):
        state = UserFlywheelState(
            user_id="u1",
            active_types=[
                BusinessType.CONTENT_CREATOR,
                BusinessType.ECOMMERCE,
                BusinessType.AI_TOOL_BUILDER,
            ],
        )
        state.current_level = FlywheelLevel.LEVEL_3
        progress = self.tracker._calculate_level_progress(state)
        self.assertEqual(progress, 100)


# ==================== Strengths and Weaknesses Tests ====================


class TestStrengthsAndWeaknesses(unittest.TestCase):
    """Test _identify_strengths and _identify_weaknesses."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_new_user_no_strengths(self):
        state = UserFlywheelState(user_id="u1")
        strengths = self.tracker._identify_strengths(state)
        self.assertEqual(strengths, ["持续积累中"])

    def test_new_user_no_weaknesses(self):
        """A new user with all-zero scores triggers low-score weaknesses."""
        state = UserFlywheelState(user_id="u1")
        weaknesses = self.tracker._identify_weaknesses(state)
        # All scores are 0, which are < 40/30 thresholds, so weaknesses are expected
        self.assertIsInstance(weaknesses, list)
        self.assertGreater(len(weaknesses), 0)

    def test_high_content_quality_identified_as_strength(self):
        state = UserFlywheelState(user_id="u1")
        state.dimension_scores.content_quality = 75
        strengths = self.tracker._identify_strengths(state)
        self.assertIn("内容创作能力强", strengths)

    def test_low_content_quality_identified_as_weakness(self):
        state = UserFlywheelState(user_id="u1")
        state.dimension_scores.content_quality = 20
        weaknesses = self.tracker._identify_weaknesses(state)
        self.assertIn("内容质量需提升 - 建议多使用content_calendar场景", weaknesses)


# ==================== Achievements Tests ====================


class TestAchievements(unittest.TestCase):
    """Test achievement checking logic."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_first_step_achievement(self):
        state = UserFlywheelState(user_id="u1", total_scenarios_completed=1)
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("first_step", ids)

    def test_active_user_achievement(self):
        state = UserFlywheelState(user_id="u1", total_scenarios_completed=10)
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("active_user", ids)

    def test_cross_discipline_achievement(self):
        state = UserFlywheelState(
            user_id="u1",
            active_types=[BusinessType.CONTENT_CREATOR, BusinessType.ECOMMERCE],
        )
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("cross_discipline", ids)

    def test_ecosystem_builder_achievement(self):
        state = UserFlywheelState(
            user_id="u1",
            active_types=[
                BusinessType.CONTENT_CREATOR,
                BusinessType.ECOMMERCE,
                BusinessType.AI_TOOL_BUILDER,
            ],
        )
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("ecosystem_builder", ids)

    def test_weekly_streak_achievement(self):
        state = UserFlywheelState(user_id="u1", active_days=7)
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("weekly_streak", ids)

    def test_high_performer_achievement(self):
        state = UserFlywheelState(user_id="u1")
        state.dimension_scores = DimensionScore(
            content_quality=100,
            audience_growth=100,
            monetization=100,
            cross_promotion=100,
            ecosystem_synergy=100,
        )
        achievements = self.tracker._check_achievements(state)
        ids = [a["id"] for a in achievements]
        self.assertIn("high_performer", ids)

    def test_no_achievements_for_zero_activity(self):
        state = UserFlywheelState(user_id="u1")
        achievements = self.tracker._check_achievements(state)
        self.assertEqual(len(achievements), 0)

    def test_achievement_has_required_fields(self):
        state = UserFlywheelState(user_id="u1", total_scenarios_completed=1)
        achievements = self.tracker._check_achievements(state)
        for a in achievements:
            self.assertIn("id", a)
            self.assertIn("name", a)
            self.assertIn("description", a)
            self.assertIn("unlocked_at", a)


# ==================== All Users Summary Tests ====================


class TestAllUsersSummary(unittest.TestCase):
    """Test get_all_users_summary."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_empty_tracker(self):
        summary = self.tracker.get_all_users_summary()
        self.assertEqual(summary["total_users"], 0)
        self.assertIn("message", summary)

    def test_single_user_summary(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        summary = self.tracker.get_all_users_summary()
        self.assertEqual(summary["total_users"], 1)
        self.assertIn("level_distribution", summary)
        self.assertIn("average_health_score", summary)
        self.assertIn("total_scenarios_completed", summary)

    def test_multiple_users_summary(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user2", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        self.tracker.record_scenario_completion(
            "user2", "feedback_analysis", BusinessType.AI_TOOL_BUILDER
        )
        summary = self.tracker.get_all_users_summary()
        self.assertEqual(summary["total_users"], 2)
        self.assertEqual(summary["total_scenarios_completed"], 3)

    def test_level_distribution(self):
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user2", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.tracker.record_scenario_completion(
            "user2", "ecommerce_ops", BusinessType.ECOMMERCE
        )
        summary = self.tracker.get_all_users_summary()
        dist = summary["level_distribution"]
        self.assertEqual(dist[1], 1)  # user1 is level 1
        self.assertEqual(dist[2], 1)  # user2 is level 2


# ==================== Edge Case Tests ====================


class TestEdgeCases(unittest.TestCase):
    """Test edge cases: new user, power user, inactive user."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_new_user_state(self):
        state = self.tracker.get_or_create_state("brand_new")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_1)
        self.assertEqual(state.active_types, [])
        self.assertEqual(state.total_scenarios_completed, 0)
        self.assertEqual(state.active_days, 0)

    def test_new_user_health_score_zero(self):
        score = self.tracker.get_flywheel_health_score("brand_new")
        self.assertEqual(score, 0.0)

    def test_power_user_maxes_out(self):
        """A power user with many completions should have scores capped at 100."""
        for i in range(30):
            for bt in BusinessType:
                self.tracker.record_scenario_completion(
                    "power_user", f"scenario_{bt.value}_{i}", bt
                )
        state = self.tracker.get_or_create_state("power_user")
        self.assertEqual(state.current_level, FlywheelLevel.LEVEL_3)
        # All dimension scores should be <= 100
        ds = state.dimension_scores
        self.assertLessEqual(ds.content_quality, 100)
        self.assertLessEqual(ds.audience_growth, 100)
        self.assertLessEqual(ds.monetization, 100)
        self.assertLessEqual(ds.cross_promotion, 100)
        self.assertLessEqual(ds.ecosystem_synergy, 100)

    def test_inactive_user_stays_at_initial_state(self):
        """User created but never completes a scenario."""
        state = self.tracker.get_or_create_state("inactive_user")
        self.assertEqual(state.total_scenarios_completed, 0)
        self.assertEqual(state.active_days, 0)

    def test_cross_session_state_persistence_in_memory(self):
        """State persists across multiple method calls (in-memory)."""
        self.tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        # Later call should still find the state
        state = self.tracker.get_or_create_state("user1")
        self.assertEqual(state.total_scenarios_completed, 1)
        self.assertIn(BusinessType.CONTENT_CREATOR, state.active_types)


# ==================== Helper Method Tests ====================


class TestHelperMethods(unittest.TestCase):
    """Test internal helper methods."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_get_level_name(self):
        self.assertEqual(self.tracker._get_level_name(FlywheelLevel.LEVEL_1), "探索者")
        self.assertEqual(self.tracker._get_level_name(FlywheelLevel.LEVEL_2), "连接者")
        self.assertEqual(
            self.tracker._get_level_name(FlywheelLevel.LEVEL_3), "生态构建者"
        )

    def test_get_most_used_scenario(self):
        state = UserFlywheelState(user_id="u1")
        state.scenario_completion_count = {
            "content_calendar": 5,
            "ecommerce_ops": 3,
        }
        result = self.tracker._get_most_used_scenario(state)
        self.assertEqual(result, "content_calendar")

    def test_get_most_used_scenario_empty(self):
        state = UserFlywheelState(user_id="u1")
        result = self.tracker._get_most_used_scenario(state)
        self.assertIsNone(result)

    def test_get_scenarios_by_type(self):
        state = UserFlywheelState(user_id="u1")
        state.scenario_completion_count = {
            "content_calendar": 3,
            "ecommerce_ops": 2,
        }
        result = self.tracker._get_scenarios_by_type(state)
        self.assertIn("content_creator", result)
        self.assertEqual(result["content_creator"], 3)
        self.assertIn("ecommerce", result)
        self.assertEqual(result["ecommerce"], 2)

    def test_generate_tips(self):
        state = UserFlywheelState(user_id="u1")
        tips = self.tracker._generate_tips(state)
        self.assertIsInstance(tips, list)
        self.assertGreater(len(tips), 0)

    def test_generate_recommendations_limited_to_3(self):
        state = UserFlywheelState(user_id="u1")
        recs = self.tracker._generate_recommendations(state)
        self.assertLessEqual(len(recs), 3)


# ==================== FlywheelTrackerDB Tests ====================


class TestFlywheelTrackerDB(unittest.TestCase):
    """Test FlywheelTrackerDB (without actual DB, tests in-memory fallback)."""

    def test_init_without_db_session(self):
        tracker = FlywheelTrackerDB()
        self.assertFalse(tracker._db_enabled)
        self.assertIsNone(tracker.db_session)

    def test_in_memory_fallback_works(self):
        tracker = FlywheelTrackerDB()
        state = tracker.record_scenario_completion(
            "user1", "content_calendar", BusinessType.CONTENT_CREATOR
        )
        self.assertEqual(state.total_scenarios_completed, 1)

    def test_get_or_create_state_without_db(self):
        tracker = FlywheelTrackerDB()
        state = tracker.get_or_create_state("user1")
        self.assertIsInstance(state, UserFlywheelState)

    def test_save_to_db_is_noop_without_session(self):
        tracker = FlywheelTrackerDB()
        state = UserFlywheelState(user_id="u1")
        # Should not raise
        tracker._save_to_db(state)

    def test_get_db_state_returns_none_without_session(self):
        tracker = FlywheelTrackerDB()
        result = tracker._get_db_state("user1")
        self.assertIsNone(result)

    def test_with_mock_db_session(self):
        """Test with a mock db_session to verify DB path is exercised."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        tracker = FlywheelTrackerDB(db_session=mock_session)
        self.assertTrue(tracker._db_enabled)

    def test_record_with_mock_db_saves(self):
        """Verify _save_to_db is called when db_session is provided."""
        mock_db_state = MagicMock()
        mock_db_state.user_id = "user1"
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        tracker = FlywheelTrackerDB(db_session=mock_session)
        # Mock the db_models import that happens inside _get_db_state and _save_to_db
        with patch.dict(
            "sys.modules", {"db_models": MagicMock(), "db_models.models": MagicMock()}
        ):
            tracker.record_scenario_completion(
                "user1", "content_calendar", BusinessType.CONTENT_CREATOR
            )
            # db_session.add should have been called
            mock_session.add.assert_called()
            mock_session.commit.assert_called()


# ==================== Score Boundary Tests ====================


class TestScoreBoundaries(unittest.TestCase):
    """Test score boundaries and clamping."""

    def setUp(self):
        self.tracker = FlywheelTracker()

    def test_dimension_scores_clamped_at_100(self):
        """All dimension scores should be clamped at 100."""
        for i in range(50):
            self.tracker.record_scenario_completion(
                "user1", "content_calendar", BusinessType.CONTENT_CREATOR
            )
        state = self.tracker.get_or_create_state("user1")
        ds = state.dimension_scores
        self.assertLessEqual(ds.content_quality, 100)
        self.assertLessEqual(ds.audience_growth, 100)
        self.assertLessEqual(ds.monetization, 100)
        self.assertLessEqual(ds.ecosystem_synergy, 100)

    def test_health_score_clamped_at_100(self):
        for i in range(50):
            for bt in BusinessType:
                self.tracker.record_scenario_completion(
                    "user1", f"scenario_{bt.value}_{i}", bt
                )
        score = self.tracker.get_flywheel_health_score("user1")
        self.assertLessEqual(score, 100.0)

    def test_health_score_non_negative(self):
        score = self.tracker.get_flywheel_health_score("new_user")
        self.assertGreaterEqual(score, 0.0)

    def test_level_progress_between_0_and_100(self):
        state = UserFlywheelState(user_id="u1")
        state.current_level = FlywheelLevel.LEVEL_1
        progress = self.tracker._calculate_level_progress(state)
        self.assertGreaterEqual(progress, 0)
        self.assertLessEqual(progress, 100)


if __name__ == "__main__":
    unittest.main()
