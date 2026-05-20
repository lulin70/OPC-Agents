#!/usr/bin/env python3
"""Multilingual Input Test Suite

Covers Chinese (zh), English (en), and Japanese (jp) input processing:
- InputValidator: sanitization and validation for all three languages
- IntentClassifier: intent recognition for all three languages
- TaskRequest: Pydantic validation for all three languages
- TaskEngineV3.execute(): end-to-end processing for all three languages
"""

import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.task_engine_v3 import (
    InputValidator,
    IntentClassifier,
    TaskEngineV3,
    TaskType,
    TaskResult,
)
from opc_manager.validators import TaskRequest
from opc_manager.llm_content import LLMEnhancedContentGenerator

MOCK_SEARCH_RESULTS = [
    {
        "title": "AI Market Research",
        "href": "https://example.com/1",
        "body": "Latest AI market trends and analysis...",
    },
    {
        "title": "Marketing Plan Guide",
        "href": "https://example.com/2",
        "body": "How to create an effective marketing plan...",
    },
    {
        "title": "SWOT Analysis Framework",
        "href": "https://example.com/3",
        "body": "Business SWOT analysis methodology...",
    },
]

MOCK_SOURCES = [
    {"title": r.get("title", ""), "url": r.get("href", "")}
    for r in MOCK_SEARCH_RESULTS
    if r.get("href")
]

MOCK_LLM_RESPONSE = (
    "# Analysis Report\n\n"
    "## Key Findings\n- Market size: 50 billion CNY with 25% YoY growth\n"
    "- Top 3 competitors hold 40% market share\n"
    "- Customer acquisition cost: 150 CNY per user\n\n"
    "## Recommendations\n1. Focus on content marketing for organic growth\n"
    "2. Launch referral program with 20% discount incentive\n"
    "3. Target enterprise segment for higher LTV\n"
)


class TestInputValidatorMultilingual(unittest.TestCase):
    """InputValidator multilingual support tests"""

    def test_chinese_input_passes(self):
        text, err = InputValidator.sanitize("帮我收集2024年AI行业最新趋势报告")
        self.assertIsNone(err)
        self.assertIn("AI", text)

    def test_english_input_passes(self):
        text, err = InputValidator.sanitize(
            "Collect the latest AI industry trends for 2024"
        )
        self.assertIsNone(err)
        self.assertIn("AI", text)

    def test_japanese_input_passes(self):
        text, err = InputValidator.sanitize("2024年のAI業界最新トレンドを収集して")
        self.assertIsNone(err)
        self.assertIn("AI", text)

    def test_mixed_chinese_english_input(self):
        text, err = InputValidator.sanitize("帮我research一下AI Agent的市场趋势")
        self.assertIsNone(err)
        self.assertIn("research", text)

    def test_mixed_japanese_english_input(self):
        text, err = InputValidator.sanitize("AIエージェントのmarket trendsを分析して")
        self.assertIsNone(err)
        self.assertIn("AI", text)

    def test_chinese_long_input_truncated(self):
        long_input = "测试内容" * 500
        sanitized, err = InputValidator.sanitize(long_input)
        self.assertIsNone(err)
        self.assertLessEqual(len(sanitized), 2000)

    def test_english_long_input_truncated(self):
        long_input = "test content " * 500
        sanitized, err = InputValidator.sanitize(long_input)
        self.assertIsNone(err)
        self.assertLessEqual(len(sanitized), 2000)

    def test_japanese_long_input_truncated(self):
        long_input = "テスト内容" * 500
        sanitized, err = InputValidator.sanitize(long_input)
        self.assertIsNone(err)
        self.assertLessEqual(len(sanitized), 2000)

    def test_chinese_control_chars_stripped(self):
        text, err = InputValidator.sanitize("正常\x00文本\x1f内容")
        self.assertIsNone(err)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x1f", text)
        self.assertIn("正常", text)

    def test_english_control_chars_stripped(self):
        text, err = InputValidator.sanitize("normal\x00text\x1fcontent")
        self.assertIsNone(err)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x1f", text)
        self.assertIn("normal", text)

    def test_japanese_control_chars_stripped(self):
        text, err = InputValidator.sanitize("正常\x00テキスト\x1f内容")
        self.assertIsNone(err)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x1f", text)

    def test_chinese_html_stripped(self):
        text, err = InputValidator.sanitize("<script>alert('xss')</script>正常内容")
        self.assertIsNone(err)
        self.assertNotIn("<script>", text)
        self.assertIn("正常内容", text)

    def test_english_html_stripped(self):
        text, err = InputValidator.sanitize(
            "<script>alert('xss')</script>normal content"
        )
        self.assertIsNone(err)
        self.assertNotIn("<script>", text)
        self.assertIn("normal content", text)

    def test_japanese_html_stripped(self):
        text, err = InputValidator.sanitize(
            "<script>alert('xss')</script>正常コンテンツ"
        )
        self.assertIsNone(err)
        self.assertNotIn("<script>", text)


class TestIntentClassifierMultilingual(unittest.TestCase):
    """IntentClassifier multilingual intent recognition tests"""

    def test_chinese_info_collection(self):
        inputs = [
            "收集2024年AI趋势",
            "搜索最新的Python框架",
            "查找竞品分析报告",
        ]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.INFO_COLLECTION, f"Failed for: {inp}")
            self.assertGreaterEqual(conf, 0.85)

    def test_english_info_collection(self):
        inputs = [
            "collect the latest AI trends",
            "search for competitor analysis",
            "research industry news",
            "find information about market dynamics",
            "gather data on user needs",
            "look up recent policy changes",
        ]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.INFO_COLLECTION, f"Failed for: {inp}")
            self.assertGreaterEqual(conf, 0.85)

    def test_japanese_info_collection(self):
        inputs = [
            "最新のAIトレンドを収集して",
            "競合分析を検索して",
            "業界動向を調べて",
        ]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.INFO_COLLECTION, f"Failed for: {inp}")
            self.assertGreaterEqual(conf, 0.85)

    def test_chinese_content_generation(self):
        inputs = [
            "帮我写一份Q2营销方案",
            "撰写项目总结报告",
            "生成产品发布文案",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.CONTENT_GENERATION, f"Failed for: {inp}")

    def test_english_content_generation(self):
        inputs = [
            "write a Q2 marketing plan",
            "draft a project summary report",
            "create a product launch copy",
            "help me write a business proposal",
            "generate a content calendar",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.CONTENT_GENERATION, f"Failed for: {inp}")

    def test_japanese_content_generation(self):
        inputs = [
            "Q2マーケティングプランを作成して",
            "プロジェクトまとめレポートを書いて",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.CONTENT_GENERATION, f"Failed for: {inp}")

    def test_chinese_data_analysis(self):
        inputs = [
            "分析一下这个方案的可行性",
            "评估市场机会",
            "对比两个产品的优劣",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.DATA_ANALYSIS, f"Failed for: {inp}")

    def test_english_data_analysis(self):
        inputs = [
            "analyze the feasibility of this plan",
            "evaluate market opportunities",
            "compare two products",
            "assess the risk of this investment",
            "predict next quarter sales",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.DATA_ANALYSIS, f"Failed for: {inp}")

    def test_japanese_data_analysis(self):
        inputs = [
            "この企画の可行性を分析して",
            "市場機会を評価して",
            "二つの製品を比較して",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.DATA_ANALYSIS, f"Failed for: {inp}")

    def test_chinese_scenario_based(self):
        inputs = [
            "执行内容日历规划场景",
            "帮我运行数字产品发布",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.SCENARIO_BASED, f"Failed for: {inp}")

    def test_english_scenario_based(self):
        inputs = [
            "run the content calendar scenario",
            "execute the product launch scenario",
            "content calendar planning",
            "product launch plan",
            "user feedback analysis",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.SCENARIO_BASED, f"Failed for: {inp}")

    def test_japanese_scenario_based(self):
        inputs = [
            "コンテンツカレンダーのシナリオを実行して",
            "製品ローンチのシナリオを実行して",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.SCENARIO_BASED, f"Failed for: {inp}")

    def test_chinese_general_chat(self):
        inputs = ["你好", "谢谢"]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.GENERAL_CHAT, f"Failed for: {inp}")
            self.assertLessEqual(conf, 0.5)

    def test_english_general_chat(self):
        inputs = ["hello", "thanks", "good morning"]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.GENERAL_CHAT, f"Failed for: {inp}")

    def test_japanese_general_chat(self):
        inputs = ["こんにちは", "ありがとう"]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.GENERAL_CHAT, f"Failed for: {inp}")


class TestTaskRequestMultilingual(unittest.TestCase):
    """TaskRequest Pydantic validation multilingual tests"""

    def test_chinese_task_request_valid(self):
        data = {
            "user_input": "帮我制定营销方案",
            "business_type": "digital_product",
        }
        request = TaskRequest(**data)
        self.assertEqual(request.user_input, "帮我制定营销方案")

    def test_english_task_request_valid(self):
        data = {
            "user_input": "Create a marketing plan for me",
            "business_type": "digital_product",
        }
        request = TaskRequest(**data)
        self.assertEqual(request.user_input, "Create a marketing plan for me")

    def test_japanese_task_request_valid(self):
        data = {
            "user_input": "マーケティングプランを作成して",
            "business_type": "digital_product",
        }
        request = TaskRequest(**data)
        self.assertEqual(request.user_input, "マーケティングプランを作成して")

    def test_mixed_language_task_request_valid(self):
        data = {
            "user_input": "帮我research一下AI Agent的market trends",
            "business_type": "ai_tool_builder",
        }
        request = TaskRequest(**data)
        self.assertIn("research", request.user_input)
        self.assertIn("market", request.user_input)


class TestTaskEngineMultilingual(unittest.TestCase):
    """TaskEngineV3 end-to-end multilingual processing tests"""

    def setUp(self):
        self.engine = TaskEngineV3()
        self._search_patcher = patch.object(
            TaskEngineV3, "_search", return_value=(MOCK_SEARCH_RESULTS, MOCK_SOURCES)
        )
        self._llm_patcher = patch.object(
            LLMEnhancedContentGenerator, "_call_llm_api", return_value=MOCK_LLM_RESPONSE
        )
        self._search_patcher.start()
        self._llm_patcher.start()

    def tearDown(self):
        self._search_patcher.stop()
        self._llm_patcher.stop()

    def test_chinese_execute_info_collection(self):
        result = self.engine.execute("收集AI行业最新趋势")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_english_execute_info_collection(self):
        result = self.engine.execute("collect latest AI industry trends")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_japanese_execute_info_collection(self):
        result = self.engine.execute("AI業界の最新トレンドを収集して")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_chinese_execute_content_generation(self):
        result = self.engine.execute("帮我写一份营销方案")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_english_execute_content_generation(self):
        result = self.engine.execute("write a marketing plan for me")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_japanese_execute_content_generation(self):
        result = self.engine.execute("マーケティングプランを作成して")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_chinese_execute_data_analysis(self):
        result = self.engine.execute("分析一下市场机会")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_english_execute_data_analysis(self):
        result = self.engine.execute("analyze market opportunities")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_japanese_execute_data_analysis(self):
        result = self.engine.execute("市場機会を分析して")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_chinese_execute_general_chat(self):
        result = self.engine.execute("你好")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_english_execute_general_chat(self):
        result = self.engine.execute("hello")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_japanese_execute_general_chat(self):
        result = self.engine.execute("こんにちは")
        self.assertIsInstance(result, TaskResult)
        self.assertIsNotNone(result.content)

    def test_no_placeholder_in_chinese_output(self):
        result = self.engine.execute("帮我写一份营销方案")
        placeholders = ["___", "待填写", "此处插入", "TODO"]
        for p in placeholders:
            self.assertNotIn(p, result.content, f"Found placeholder: {p}")

    def test_no_placeholder_in_english_output(self):
        result = self.engine.execute("write a marketing plan for me")
        placeholders = ["___", "待填写", "此处插入", "TODO"]
        for p in placeholders:
            self.assertNotIn(p, result.content, f"Found placeholder: {p}")

    def test_no_placeholder_in_japanese_output(self):
        result = self.engine.execute("マーケティングプランを作成して")
        placeholders = ["___", "待填写", "此处插入", "TODO"]
        for p in placeholders:
            self.assertNotIn(p, result.content, f"Found placeholder: {p}")


if __name__ == "__main__":
    unittest.main()
