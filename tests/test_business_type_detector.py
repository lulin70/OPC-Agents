"""
Comprehensive unit tests for business_type_detector_v2.py

Covers:
1. Detection accuracy for each business type
2. Edge cases: ambiguous, mixed-language, short, long input
3. Rule-based detection path (keyword matching)
4. LLM fallback path
5. Confidence scoring logic
6. Default fallback
7. Caching / statistics
8. detect() return type and structure
"""

import unittest
from unittest.mock import MagicMock, AsyncMock

from opc_manager.business_types import BusinessType
from opc_manager.business_type_detector_v2 import (
    BusinessTypeDetectorV2,
    DetectionResult,
)


class TestDetectionResultDataclass(unittest.TestCase):
    """Test DetectionResult structure and defaults."""

    def test_default_fields(self):
        result = DetectionResult(
            business_type=BusinessType.CONTENT_CREATOR,
            confidence=0.9,
            method="keyword_match",
        )
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)
        self.assertEqual(result.confidence, 0.9)
        self.assertEqual(result.method, "keyword_match")
        self.assertEqual(result.matched_keywords, [])
        self.assertEqual(result.alternative_types, [])
        self.assertEqual(result.detected_patterns, [])
        self.assertEqual(result.reasoning, "")

    def test_all_fields_populated(self):
        result = DetectionResult(
            business_type=BusinessType.ECOMMERCE,
            confidence=0.75,
            method="pattern_match",
            matched_keywords=["电商", "淘宝"],
            alternative_types=[(BusinessType.CONTENT_CREATOR, 0.3)],
            detected_patterns=[r"我的.*店铺"],
            reasoning="Matched pattern",
        )
        self.assertEqual(len(result.matched_keywords), 2)
        self.assertEqual(len(result.alternative_types), 1)


class TestDetectorInit(unittest.TestCase):
    """Test detector initialization."""

    def test_default_init(self):
        detector = BusinessTypeDetectorV2()
        self.assertFalse(detector.enable_llm)
        self.assertIsNone(detector.llm_service)
        self.assertEqual(detector.default_type, BusinessType.CONTENT_CREATOR)
        self.assertEqual(detector.confidence_threshold, 0.12)

    def test_init_with_llm_enabled(self):
        mock_service = MagicMock()
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        self.assertTrue(detector.enable_llm)
        self.assertIs(detector.llm_service, mock_service)

    def test_keyword_database_has_all_business_types(self):
        detector = BusinessTypeDetectorV2()
        for bt in BusinessType:
            self.assertIn(
                bt, detector.type_keywords, f"Missing keywords for {bt.value}"
            )

    def test_pattern_database_has_all_business_types(self):
        detector = BusinessTypeDetectorV2()
        for bt in BusinessType:
            self.assertIn(bt, detector.patterns, f"Missing patterns for {bt.value}")

    def test_negation_words_initialized(self):
        detector = BusinessTypeDetectorV2()
        self.assertIn("不", detector.negation_words)
        self.assertIn("不是", detector.negation_words)
        self.assertIn("没有", detector.negation_words)

    def test_keyword_config_structure(self):
        """Each keyword config should have required sub-keys."""
        detector = BusinessTypeDetectorV2()
        required_keys = {
            "name",
            "emoji",
            "weight",
            "primary_keywords",
            "secondary_keywords",
        }
        for bt, config in detector.type_keywords.items():
            for key in required_keys:
                self.assertIn(key, config, f"Missing '{key}' in config for {bt.value}")


class TestPatternDetection(unittest.TestCase):
    """Test the pattern matching detection path."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_content_creator_pattern(self):
        result = self.detector.detect("帮我写一篇关于AI的文章")
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)
        self.assertGreaterEqual(result.confidence, 0.8)
        self.assertEqual(result.method, "pattern_match")

    def test_digital_product_pattern(self):
        result = self.detector.detect("我要在Gumroad上发布一个新课程")
        self.assertEqual(result.business_type, BusinessType.DIGITAL_PRODUCT)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_ai_tool_builder_pattern(self):
        result = self.detector.detect("我的工具的AI模型需要优化性能提升")
        self.assertEqual(result.business_type, BusinessType.AI_TOOL_BUILDER)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_consultant_pattern(self):
        result = self.detector.detect("给客户写一份SWOT分析方案")
        self.assertEqual(result.business_type, BusinessType.CONSULTANT)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_ecommerce_pattern(self):
        result = self.detector.detect("我的淘宝店铺运营优化")
        self.assertEqual(result.business_type, BusinessType.ECOMMERCE)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_creative_work_pattern(self):
        result = self.detector.detect("帮我设计一个logo")
        self.assertEqual(result.business_type, BusinessType.CREATIVE_WORK)
        self.assertGreaterEqual(result.confidence, 0.8)

    def test_pattern_confidence_capped_at_095(self):
        result = self.detector._detect_by_pattern("帮我写一篇关于AI的文章")
        if result:
            self.assertLessEqual(result.confidence, 0.95)

    def test_no_pattern_returns_none(self):
        result = self.detector._detect_by_pattern("今天天气不错")
        self.assertIsNone(result)


class TestKeywordDetection(unittest.TestCase):
    """Test the keyword matching detection path."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_content_creator_keywords(self):
        result = self.detector.detect("我的小红书账号涨粉技巧")
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)

    def test_digital_product_keywords(self):
        result = self.detector.detect("知识付费课程定价策略")
        self.assertEqual(result.business_type, BusinessType.DIGITAL_PRODUCT)

    def test_ai_tool_keywords(self):
        result = self.detector.detect("GPT API集成开发部署")
        self.assertEqual(result.business_type, BusinessType.AI_TOOL_BUILDER)

    def test_consultant_keywords(self):
        result = self.detector.detect("咨询项目提案方法论框架")
        self.assertEqual(result.business_type, BusinessType.CONSULTANT)

    def test_ecommerce_keywords(self):
        result = self.detector.detect("电商店铺GMV转化率优化")
        self.assertEqual(result.business_type, BusinessType.ECOMMERCE)

    def test_creative_work_keywords(self):
        result = self.detector.detect("Figma设计作品集插画")
        self.assertEqual(result.business_type, BusinessType.CREATIVE_WORK)

    def test_keyword_result_has_matched_keywords(self):
        result = self.detector._detect_by_keywords("电商店铺GMV转化率优化")
        self.assertIsInstance(result.matched_keywords, list)
        self.assertGreater(len(result.matched_keywords), 0)

    def test_keyword_result_has_alternative_types(self):
        result = self.detector._detect_by_keywords("电商店铺GMV转化率优化")
        self.assertIsInstance(result.alternative_types, list)

    def test_keyword_confidence_is_rounded(self):
        result = self.detector._detect_by_keywords("电商")
        # confidence should be rounded to 3 decimal places
        self.assertEqual(result.confidence, round(result.confidence, 3))


class TestNegationDetection(unittest.TestCase):
    """Test negation detection and adjustment."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_contains_negation_true(self):
        self.assertTrue(self.detector._contains_negation("我不想做电商"))
        self.assertTrue(self.detector._contains_negation("没有内容"))
        self.assertTrue(self.detector._contains_negation("别做这个"))

    def test_contains_negation_false(self):
        self.assertFalse(self.detector._contains_negation("我想做电商"))
        self.assertFalse(self.detector._contains_negation("内容创作"))

    def test_negation_reduces_confidence(self):
        """Test negation penalty directly via _adjust_for_negation."""
        original = DetectionResult(
            business_type=BusinessType.ECOMMERCE,
            confidence=0.6,
            method="keyword_match",
        )
        adjusted = self.detector._adjust_for_negation(original, "不做电商")
        self.assertLess(adjusted.confidence, original.confidence)

    def test_negation_penalty_minimum_confidence(self):
        """After negation adjustment, confidence should not go below 0.1."""
        result = self.detector._adjust_for_negation(
            DetectionResult(
                business_type=BusinessType.ECOMMERCE,
                confidence=0.2,
                method="keyword_match",
            ),
            "不做电商",
        )
        self.assertGreaterEqual(result.confidence, 0.1)

    def test_adjust_for_negation_modifies_method(self):
        result = self.detector._adjust_for_negation(
            DetectionResult(
                business_type=BusinessType.ECOMMERCE,
                confidence=0.5,
                method="keyword_match",
            ),
            "不做电商",
        )
        self.assertIn("negation", result.method)


class TestContextAnalysis(unittest.TestCase):
    """Test context-aware detection with conversation history."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_context_boost_with_consistent_history(self):
        history = [
            {"user": "我的小红书涨粉技巧"},
            {"user": "内容创作选题规划"},
            {"user": "抖音爆款视频分析"},
        ]
        result = self.detector.detect("帮我规划下周内容", history=history)
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)

    def test_context_boost_applied_when_history_exists(self):
        history = [
            {"user": "电商店铺运营"},
            {"user": "淘宝双十一促销"},
            {"user": "GMV转化率优化"},
        ]
        result_no_history = self.detector.detect("帮我处理订单")
        result_with_history = self.detector.detect("帮我处理订单", history=history)
        # With consistent history, confidence should be boosted
        self.assertGreaterEqual(
            result_with_history.confidence, result_no_history.confidence
        )

    def test_context_ignored_when_history_too_short(self):
        """History with fewer than 3 items should not trigger context analysis."""
        short_history = [{"user": "电商运营"}]
        result = self.detector.detect("帮我处理订单", history=short_history)
        # Should still work, just without context boost
        self.assertIsNotNone(result)

    def test_context_uses_various_message_keys(self):
        """Context analysis should handle 'input' and 'message' keys too."""
        history = [
            {"input": "电商店铺运营"},
            {"input": "淘宝双十一促销"},
            {"input": "GMV转化率优化"},
        ]
        result = self.detector.detect("帮我处理订单", history=history)
        self.assertIsNotNone(result)


class TestProfileInference(unittest.TestCase):
    """Test user profile-based inference."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_profile_with_business_type(self):
        profile = {"business_type": "ecommerce"}
        result = self.detector._infer_from_profile(profile)
        self.assertEqual(result, BusinessType.ECOMMERCE)

    def test_profile_with_invalid_business_type(self):
        profile = {"business_type": "nonexistent_type"}
        result = self.detector._infer_from_profile(profile)
        self.assertIsNone(result)

    def test_profile_with_interests(self):
        profile = {"interests": ["电商", "淘宝", "店铺运营"]}
        result = self.detector._infer_from_profile(profile)
        # Should infer a type based on interests
        self.assertIsNotNone(result)

    def test_empty_profile_returns_none(self):
        result = self.detector._infer_from_profile({})
        self.assertIsNone(result)

    def test_none_profile_returns_none(self):
        result = self.detector._infer_from_profile(None)
        self.assertIsNone(result)

    def test_profile_inference_used_when_keyword_confidence_low(self):
        """When keyword confidence < 0.4 and profile has type, profile type is used."""
        profile = {"business_type": "consultant"}
        result = self.detector.detect("今天天气怎么样", user_profile=profile)
        # Should fall back to profile type since input is ambiguous
        self.assertEqual(result.business_type, BusinessType.CONSULTANT)


class TestLLMFallback(unittest.TestCase):
    """Test LLM-assisted detection path."""

    def test_llm_disabled_by_default(self):
        detector = BusinessTypeDetectorV2()
        result = detector._detect_by_llm("ambiguous input")
        self.assertIsNone(result)

    def test_llm_returns_none_when_no_service(self):
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=None)
        result = detector._detect_by_llm("ambiguous input")
        self.assertIsNone(result)

    def test_llm_detection_with_mock_service(self):
        mock_service = MagicMock()
        mock_service.detect_business_type_by_llm = AsyncMock(
            return_value={
                "business_type": "ecommerce",
                "confidence": 0.85,
                "reasoning": "User mentions shop operations",
            }
        )
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        result = detector._detect_by_llm("我的店铺运营")
        self.assertIsNotNone(result)
        self.assertEqual(result.business_type, BusinessType.ECOMMERCE)
        self.assertEqual(result.method, "llm_assisted")

    def test_llm_detection_unknown_type_returns_none(self):
        mock_service = MagicMock()
        mock_service.detect_business_type_by_llm = AsyncMock(
            return_value={"business_type": "unknown", "confidence": 0.5}
        )
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        result = detector._detect_by_llm("ambiguous input")
        self.assertIsNone(result)

    def test_llm_detection_exception_returns_none(self):
        mock_service = MagicMock()
        mock_service.detect_business_type_by_llm = AsyncMock(
            side_effect=Exception("API error")
        )
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        result = detector._detect_by_llm("ambiguous input")
        self.assertIsNone(result)

    def test_llm_confidence_capped_at_099(self):
        mock_service = MagicMock()
        mock_service.detect_business_type_by_llm = AsyncMock(
            return_value={
                "business_type": "ecommerce",
                "confidence": 1.5,  # Over 1.0
                "reasoning": "test",
            }
        )
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        result = detector._detect_by_llm("我的店铺运营")
        self.assertIsNotNone(result)
        self.assertLessEqual(result.confidence, 0.99)

    def test_llm_used_in_detect_when_confidence_low(self):
        """When keyword confidence < 0.5 and LLM is enabled, LLM should be called."""
        mock_service = MagicMock()
        mock_service.detect_business_type_by_llm = AsyncMock(
            return_value={
                "business_type": "consultant",
                "confidence": 0.8,
                "reasoning": "Consulting context",
            }
        )
        detector = BusinessTypeDetectorV2(enable_llm=True, llm_service=mock_service)
        result = detector.detect("今天天气怎么样")
        # LLM result should override low-confidence keyword result
        self.assertEqual(result.business_type, BusinessType.CONSULTANT)


class TestDefaultFallback(unittest.TestCase):
    """Test default fallback when nothing matches well."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_gibberish_input_returns_default(self):
        result = self.detector.detect("asdfghjkl")
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)
        self.assertEqual(result.method, "default")
        self.assertAlmostEqual(result.confidence, 0.2)

    def test_empty_string_returns_default(self):
        result = self.detector.detect("")
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)

    def test_min_confidence_threshold_triggers_default(self):
        """When confidence is below threshold, default type is returned."""
        result = self.detector.detect("xyz")
        self.assertEqual(result.business_type, BusinessType.CONTENT_CREATOR)

    def test_default_with_profile_fallback(self):
        """When below threshold but profile exists, use profile type."""
        profile = {"business_type": "ai_tool_builder"}
        result = self.detector.detect("xyz", user_profile=profile)
        self.assertEqual(result.business_type, BusinessType.AI_TOOL_BUILDER)
        # Method could be profile_inference or profile_fallback depending on flow
        self.assertIn("profile", result.method)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases: ambiguous, mixed-language, short, long input."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_very_short_input(self):
        result = self.detector.detect("写")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, DetectionResult)

    def test_very_long_input(self):
        long_text = "电商运营 " * 500
        result = self.detector.detect(long_text)
        self.assertIsNotNone(result)
        self.assertEqual(result.business_type, BusinessType.ECOMMERCE)

    def test_mixed_language_input(self):
        result = self.detector.detect("我的Gumroad课程landing page需要优化")
        self.assertIsNotNone(result)
        # Should detect digital product due to Gumroad/landing page
        self.assertEqual(result.business_type, BusinessType.DIGITAL_PRODUCT)

    def test_ambiguous_input_multiple_types(self):
        """Input matching multiple types should still return a result."""
        result = self.detector.detect("内容创作和电商运营结合的方案")
        self.assertIsNotNone(result)
        self.assertIsInstance(result.confidence, float)

    def test_whitespace_only_input(self):
        result = self.detector.detect("   ")
        self.assertIsNotNone(result)

    def test_special_characters_input(self):
        result = self.detector.detect("!@#$%^&*()")
        self.assertIsNotNone(result)

    def test_numeric_only_input(self):
        result = self.detector.detect("12345")
        self.assertIsNotNone(result)


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence scoring logic."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_high_confidence_for_strong_match(self):
        result = self.detector.detect("我的小红书账号想涨粉，帮我规划内容日历")
        self.assertGreater(result.confidence, 0.5)

    def test_low_confidence_for_weak_match(self):
        result = self.detector.detect("今天天气怎么样")
        self.assertLess(result.confidence, 0.5)

    def test_confidence_between_0_and_1(self):
        texts = [
            "电商运营",
            "今天天气好",
            "帮我写文章",
            "GPT API开发",
            "咨询提案",
        ]
        for text in texts:
            result = self.detector.detect(text)
            self.assertGreaterEqual(result.confidence, 0.0)
            self.assertLessEqual(result.confidence, 1.0)

    def test_enhanced_score_calculation(self):
        """Test _calculate_enhanced_score returns reasonable values."""
        config = self.detector.type_keywords[BusinessType.ECOMMERCE]
        score = self.detector._calculate_enhanced_score("电商店铺GMV转化率", config)
        self.assertGreater(score, 0.0)

    def test_context_phrase_bonus(self):
        """Context phrases should add bonus to the score."""
        config = self.detector.type_keywords[BusinessType.CONTENT_CREATOR]
        score_without_context = self.detector._calculate_enhanced_score(
            "内容创作选题", config
        )
        score_with_context = self.detector._calculate_enhanced_score(
            "帮我写一篇内容创作选题", config
        )
        # "帮我写一篇" is a context phrase, should add bonus
        self.assertGreaterEqual(score_with_context, score_without_context)


class TestDetectReturnType(unittest.TestCase):
    """Test detect() return type and structure."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_returns_detection_result(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result, DetectionResult)

    def test_result_has_business_type(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.business_type, BusinessType)

    def test_result_has_confidence(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.confidence, float)

    def test_result_has_method(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.method, str)

    def test_result_has_matched_keywords(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.matched_keywords, list)

    def test_result_has_alternative_types(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.alternative_types, list)

    def test_result_has_detected_patterns(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.detected_patterns, list)

    def test_result_has_reasoning(self):
        result = self.detector.detect("电商运营")
        self.assertIsInstance(result.reasoning, str)


class TestStatistics(unittest.TestCase):
    """Test detection statistics tracking."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_initial_statistics(self):
        stats = self.detector.get_statistics()
        self.assertEqual(stats["total_detections"], 0)
        self.assertIn("method_distribution", stats)
        self.assertIn("supported_types", stats)

    def test_total_detections_incremented(self):
        self.detector.detect("电商运营")
        self.detector.detect("内容创作")
        stats = self.detector.get_statistics()
        self.assertEqual(stats["total_detections"], 2)

    def test_method_distribution_recorded(self):
        self.detector.detect("帮我写一篇文章")
        stats = self.detector.get_statistics()
        self.assertIn("pattern_match", stats["method_distribution"])

    def test_statistics_has_version(self):
        stats = self.detector.get_statistics()
        self.assertIn("version", stats)
        self.assertIn("2.2.0", stats["version"])

    def test_statistics_has_features(self):
        stats = self.detector.get_statistics()
        self.assertIn("features", stats)
        self.assertIsInstance(stats["features"], list)

    def test_statistics_type_details(self):
        stats = self.detector.get_statistics()
        self.assertIn("type_details", stats)
        for bt in BusinessType:
            self.assertIn(bt.value, stats["type_details"])


class TestBuildResult(unittest.TestCase):
    """Test _build_result helper method."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_build_result_with_explicit_keywords(self):
        result = self.detector._build_result(
            BusinessType.ECOMMERCE,
            0.8,
            "keyword_match",
            "电商运营",
            matched_keywords=["电商"],
        )
        self.assertEqual(result.matched_keywords, ["电商"])

    def test_build_result_auto_extracts_keywords(self):
        result = self.detector._build_result(
            BusinessType.ECOMMERCE, 0.8, "keyword_match", "电商运营"
        )
        self.assertIsInstance(result.matched_keywords, list)

    def test_build_result_has_alternative_types(self):
        result = self.detector._build_result(
            BusinessType.ECOMMERCE, 0.8, "keyword_match", "电商运营"
        )
        self.assertIsInstance(result.alternative_types, list)

    def test_build_result_default_reasoning(self):
        result = self.detector._build_result(
            BusinessType.ECOMMERCE, 0.8, "keyword_match", "电商运营"
        )
        self.assertIn("keyword_match", result.reasoning)


class TestExtractMatchedKeywords(unittest.TestCase):
    """Test _extract_matched_keywords_enhanced method."""

    def setUp(self):
        self.detector = BusinessTypeDetectorV2()

    def test_extracts_primary_keywords(self):
        config = self.detector.type_keywords[BusinessType.ECOMMERCE]
        # _extract_matched_keywords_enhanced expects text already lowercased
        matched = self.detector._extract_matched_keywords_enhanced(
            "电商店铺gmv", config
        )
        self.assertIn("电商", matched)
        self.assertIn("店铺", matched)
        self.assertIn("GMV", matched)

    def test_extracts_synonyms(self):
        config = self.detector.type_keywords[BusinessType.ECOMMERCE]
        matched = self.detector._extract_matched_keywords_enhanced("网店运营", config)
        # "网店" is a synonym of "电商"
        self.assertTrue(len(matched) > 0)

    def test_max_12_keywords(self):
        config = self.detector.type_keywords[BusinessType.CONTENT_CREATOR]
        text = "内容 创作 写作 文章 博客 公众号 小红书 抖音 视频 直播 UP主 博主 粉丝 涨粉 爆款"
        matched = self.detector._extract_matched_keywords_enhanced(text, config)
        self.assertLessEqual(len(matched), 12)


if __name__ == "__main__":
    unittest.main()
