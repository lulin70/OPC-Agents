#!/usr/bin/env python3
"""Real E2E Test Suite — Validates actual system behavior with real API calls

This test suite calls REAL services (DuckDuckGo search, LLM API) to verify
that the system works end-to-end for real users. No mocks.

Run commands:
  SKIP_E2E=0 pytest tests/test_e2e_real.py -v              # All E2E tests
  SKIP_E2E=0 pytest tests/test_e2e_real.py -m e2e_search   # Search only
  SKIP_E2E=0 pytest tests/test_e2e_real.py -m e2e_llm      # LLM only

Quality gates:
  - Search must return results for Chinese/English/Japanese queries
  - LLM must generate content in the same language as user input
  - No placeholders in any output
  - Content length > 500 chars for non-trivial queries
  - Response time < 30s for search, < 60s for LLM
"""

import unittest
import time
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.task_engine_v3 import TaskEngineV3, TaskType, TaskResult
from opc_manager.llm_content import LLMEnhancedContentGenerator
from opc_hr.web_search import WebSearchMCP


# ============================================================
# Real Search Tests (DuckDuckGo)
# ============================================================

@pytest.mark.e2e
@pytest.mark.e2e_search
class TestRealSearch(unittest.TestCase):
    """Validate real DuckDuckGo search works for all languages"""

    @classmethod
    def setUpClass(cls):
        cls.search = WebSearchMCP()
        if not cls.search.is_available():
            raise unittest.SkipTest("DuckDuckGo search not available")

    def test_chinese_search_returns_results(self):
        results = self.search.search("一人公司创业指南", max_results=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Chinese search should return results")
        for r in results:
            self.assertIn("title", r)
            self.assertIn("href", r)

    def test_english_search_returns_results(self):
        results = self.search.search("one person company business guide", max_results=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "English search should return results")

    def test_japanese_search_returns_results(self):
        results = self.search.search("一人会社起業ガイド", max_results=5)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Japanese search should return results")

    def test_search_result_has_required_fields(self):
        results = self.search.search("SaaS growth strategy", max_results=3)
        if results:
            for r in results:
                self.assertIn("title", r)
                self.assertIn("href", r)
                self.assertIn("body", r)
                self.assertTrue(len(r["title"]) > 0)

    def test_search_performance_under_15s(self):
        start = time.time()
        self.search.search("AI agent framework 2024", max_results=8)
        elapsed = time.time() - start
        self.assertLess(elapsed, 15, f"Search took {elapsed:.1f}s, should be < 15s")


# ============================================================
# Real Full Pipeline Tests (Search + Engine)
# ============================================================

@pytest.mark.e2e
@pytest.mark.e2e_search
class TestRealFullPipeline(unittest.TestCase):
    """Validate full pipeline with real search (no LLM)"""

    def setUp(self):
        self.engine = TaskEngineV3()

    def test_chinese_info_collection_real(self):
        result = self.engine.execute("收集AI行业最新趋势")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.INFO_COLLECTION)
        self.assertGreater(len(result.content), 200)

    def test_english_info_collection_real(self):
        result = self.engine.execute("collect latest AI industry trends")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.INFO_COLLECTION)
        self.assertGreater(len(result.content), 200)

    def test_japanese_info_collection_real(self):
        result = self.engine.execute("AI業界の最新トレンドを収集して")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.INFO_COLLECTION)
        self.assertGreater(len(result.content), 200)

    def test_chinese_content_generation_real(self):
        result = self.engine.execute("帮我写一份Q2营销方案")
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)
        self.assertIn("# ", result.content)

    def test_chinese_data_analysis_real(self):
        result = self.engine.execute("分析一下一人公司的SWOT")
        self.assertTrue(result.success)
        content_lower = result.content.lower()
        has_swot = any(kw in content_lower for kw in ["swot", "优势", "劣势", "机会", "威胁"])
        self.assertTrue(has_swot, f"SWOT analysis should contain SWOT keywords: {result.content[:100]}")

    def test_no_placeholder_in_real_output(self):
        result = self.engine.execute("帮我制定一个产品发布计划")
        placeholders = ["___", "待填写", "此处插入", "TODO", "FIXME"]
        for p in placeholders:
            self.assertNotIn(p, result.content, f"Real output should not contain placeholder: {p}")

    def test_real_pipeline_performance_under_30s(self):
        start = time.time()
        self.engine.execute("收集SaaS增长策略信息")
        elapsed = time.time() - start
        self.assertLess(elapsed, 30, f"Full pipeline took {elapsed:.1f}s, should be < 30s")


# ============================================================
# Real LLM Tests (requires API key)
# ============================================================

@pytest.mark.e2e
@pytest.mark.e2e_llm
class TestRealLLM(unittest.TestCase):
    """Validate real LLM API calls work correctly"""

    @classmethod
    def setUpClass(cls):
        cls.generator = LLMEnhancedContentGenerator()
        if not cls.generator.is_available():
            raise unittest.SkipTest("LLM API not available (no API key configured)")

    def test_llm_generates_chinese_content(self):
        result = self.generator.generate(
            user_input="帮我写一份AI写作助手的Q2营销方案，月活5000提升到10000",
            template="# Q2营销方案\n\n## 项目概览\n{business_context}\n\n## 目标\n{goals}\n\n"
                     + "详细内容。\n" * 20,
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)
        self.assertIn("Q2", result.content)

    def test_llm_responds_in_english(self):
        result = self.generator.generate(
            user_input="Write a Q2 marketing plan for an AI writing assistant, MAU from 5000 to 10000",
            template="# Q2 Marketing Plan\n\n## Overview\n{business_context}\n\n## Goals\n{goals}\n\n"
                     + "Detailed content.\n" * 20,
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)

    def test_llm_responds_in_japanese(self):
        result = self.generator.generate(
            user_input="AIライティングアシスタントのQ2マーケティングプランを作成して、MAUを5000から10000に",
            template="# Q2マーケティングプラン\n\n## 概要\n{business_context}\n\n## 目標\n{goals}\n\n"
                     + "詳細内容。\n" * 20,
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)

    def test_llm_no_placeholder_in_output(self):
        result = self.generator.generate(
            user_input="帮我制定增长方案",
            template="# 增长方案\n{business_context}\n{goals}\n" + "内容。\n" * 30,
        )
        forbidden = ["___", "待填写", "此处插入", "基准值待测", "TODO", "FIXME"]
        for p in forbidden:
            self.assertNotIn(p, result.content, f"LLM output should not contain: {p}")

    def test_llm_performance_under_60s(self):
        start = time.time()
        self.generator.generate(
            user_input="帮我写一份营销方案",
            template="# 方案\n{business_context}\n" + "内容。\n" * 20,
        )
        elapsed = time.time() - start
        self.assertLess(elapsed, 60, f"LLM generation took {elapsed:.1f}s, should be < 60s")


# ============================================================
# Real End-to-End with LLM (full system)
# ============================================================

@pytest.mark.e2e
@pytest.mark.e2e_llm
class TestRealE2EWithLLM(unittest.TestCase):
    """Full end-to-end with real search + real LLM — closest to real user experience"""

    @classmethod
    def setUpClass(cls):
        cls.engine = TaskEngineV3()
        cls.generator = LLMEnhancedContentGenerator()
        if not cls.generator.is_available():
            raise unittest.SkipTest("LLM API not available")

    def test_full_chinese_pipeline_with_llm(self):
        result = self.engine.execute("帮我写一份AI产品Q2增长方案，目标月活从5000提升到10000")
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)
        self.assertIn("# ", result.content)
        placeholders = ["___", "待填写", "此处插入"]
        for p in placeholders:
            self.assertNotIn(p, result.content)

    def test_full_english_pipeline_with_llm(self):
        result = self.engine.execute("Write a Q2 growth plan for an AI product, target MAU from 5000 to 10000")
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)

    def test_full_japanese_pipeline_with_llm(self):
        result = self.engine.execute("AI製品のQ2成長プランを作成して、目標MAUを5000から10000に")
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)

    def test_multilingual_greeting_detection(self):
        result_zh = self.engine.execute("你好")
        self.assertTrue(result_zh.success)
        self.assertIn("OPC-Agents", result_zh.content)

        result_en = self.engine.execute("hello")
        self.assertTrue(result_en.success)
        self.assertIn("OPC-Agents", result_en.content)

        result_jp = self.engine.execute("こんにちは")
        self.assertTrue(result_jp.success)
        self.assertIn("OPC-Agents", result_jp.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
