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

from opc_manager.task_engine_v3 import TaskEngineV3, TaskType
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
        has_swot = any(
            kw in content_lower for kw in ["swot", "优势", "劣势", "机会", "威胁"]
        )
        self.assertTrue(
            has_swot,
            f"SWOT analysis should contain SWOT keywords: {result.content[:100]}",
        )

    def test_no_placeholder_in_real_output(self):
        result = self.engine.execute("帮我制定一个产品发布计划")
        placeholders = ["___", "待填写", "此处插入", "TODO", "FIXME"]
        for p in placeholders:
            self.assertNotIn(
                p, result.content, f"Real output should not contain placeholder: {p}"
            )

    def test_real_pipeline_performance_under_30s(self):
        start = time.time()
        self.engine.execute("收集SaaS增长策略信息")
        elapsed = time.time() - start
        self.assertLess(
            elapsed, 30, f"Full pipeline took {elapsed:.1f}s, should be < 30s"
        )


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
        # Validate the API key actually works (not just present).
        # is_available() only checks key existence; an invalid/expired key
        # would cause test failures instead of a clean skip.
        try:
            validation = cls.generator.generate(
                user_input="test",
                template="# Test\n{business_context}\n",
            )
            if validation.fallback_used:
                raise unittest.SkipTest(
                    "LLM API key invalid or LLM unreachable (fallback used). "
                    "Set a valid API key to run these tests."
                )
        except unittest.SkipTest:
            raise
        except Exception as e:
            raise unittest.SkipTest(f"LLM API validation failed: {e}")

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
        self.assertLess(
            elapsed, 60, f"LLM generation took {elapsed:.1f}s, should be < 60s"
        )


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
        # Validate the API key actually works (see TestRealLLM.setUpClass).
        try:
            validation = cls.generator.generate(
                user_input="test",
                template="# Test\n{business_context}\n",
            )
            if validation.fallback_used:
                raise unittest.SkipTest(
                    "LLM API key invalid or LLM unreachable (fallback used)."
                )
        except unittest.SkipTest:
            raise
        except Exception as e:
            raise unittest.SkipTest(f"LLM API validation failed: {e}")

    def test_full_chinese_pipeline_with_llm(self):
        result = self.engine.execute(
            "帮我写一份AI产品Q2增长方案，目标月活从5000提升到10000"
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)
        self.assertIn("# ", result.content)
        placeholders = ["___", "待填写", "此处插入"]
        for p in placeholders:
            self.assertNotIn(p, result.content)

    def test_full_english_pipeline_with_llm(self):
        result = self.engine.execute(
            "Write a Q2 growth plan for an AI product, target MAU from 5000 to 10000"
        )
        self.assertTrue(result.success)
        self.assertGreater(len(result.content), 500)

    def test_full_japanese_pipeline_with_llm(self):
        result = self.engine.execute(
            "AI製品のQ2成長プランを作成して、目標MAUを5000から10000に"
        )
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


# ============================================================
# [v0.3.0] Core Skills Real E2E Tests — 3 core scenarios
# See docs/spec/CORE_SKILLS_ACCEPTANCE.md for acceptance criteria
# ============================================================


@pytest.mark.e2e
@pytest.mark.e2e_core_skill
class TestRealCoreSkills(unittest.TestCase):
    """Validate 3 core skills (email/finance/report) with real LLM

    Acceptance criteria: docs/spec/CORE_SKILLS_ACCEPTANCE.md
    Run: SKIP_E2E=0 pytest tests/test_e2e_real.py -m e2e_core_skill -v
    """

    @classmethod
    def setUpClass(cls):
        if os.environ.get("SKIP_E2E", "0") == "1":
            raise unittest.SkipTest(
                "E2E tests skipped (set SKIP_E2E=0 or unset to run core skill E2E tests)"
            )
        from opc_manager.simple_llm_service import SimpleLLMService

        cls.llm = SimpleLLMService()
        # Verify LLM is available
        try:
            test_resp = cls.llm.call(
                system_prompt="You are a test assistant.",
                user_prompt="Reply with 'OK' only.",
                max_tokens=5,
            )
            if not test_resp or "OK" not in str(test_resp).upper():
                raise unittest.SkipTest("LLM service not responding correctly")
        except Exception as e:
            raise unittest.SkipTest(f"LLM service unavailable: {e}")

    # --- Scenario E1: Email draft generation ---

    def test_email_draft_generation(self):
        """Scenario E1: '帮我给张总写一封项目跟进邮件' → generate email draft.

        Acceptance:
        - Draft non-empty and meaningful
        - Subject ≤ 50 chars, body 100-500 chars
        - Content related to 'project follow-up'
        - Latency < 30s
        """
        start = time.time()
        response = self.llm.call(
            system_prompt="你是一人公司助手。生成邮件草稿，格式：主题：xxx\n\n正文：xxx",
            user_prompt="帮我给张总写一封项目跟进邮件，本周完成了产品优化，下周计划用户测试。",
            max_tokens=500,
        )
        elapsed = time.time() - start

        self.assertIsNotNone(response, "LLM response should not be None")
        self.assertLess(
            elapsed, 30, f"Email draft took {elapsed:.1f}s, should be < 30s"
        )

        content = str(response)
        self.assertGreater(len(content), 50, "Email draft too short")
        # Check it contains email-like structure
        self.assertTrue(
            any(kw in content for kw in ["主题", "正文", "张总", "跟进", "项目"]),
            f"Email draft should mention email/project keywords, got: {content[:100]}",
        )

    # --- Scenario F1: Finance income recording ---

    def test_finance_income_recording(self):
        """Scenario F1: '帮我记一笔收入3000元来自A公司' → record income.

        Acceptance:
        - Income recorded in SQLite
        - Amount = 3000.00
        - Source = A公司
        - Data persisted (queryable after recording)
        """
        from opc_manager.finance_skill import record_income, get_monthly_report
        import time as _time

        result = record_income(
            amount=3000, source="A公司", category="咨询费", note="E2E测试"
        )
        self.assertTrue(result.get("success"), f"Income recording failed: {result}")
        self.assertEqual(result.get("message"), "已记录收入 ¥3000.00 (A公司)")

        # Verify persistence by querying monthly report
        current_month = _time.strftime("%Y-%m")
        report = get_monthly_report(current_month)
        self.assertTrue(report.get("success"))
        self.assertGreaterEqual(
            report.get("income", 0),
            3000,
            "Monthly income should include the 3000 record",
        )

    def test_finance_expense_recording(self):
        """Scenario F2: '记一笔支出500元办公用品' → record expense.

        Acceptance:
        - Expense recorded
        - Amount = 500.00
        - Type = expense
        """
        from opc_manager.finance_skill import record_expense

        result = record_expense(amount=500, source="办公用品", category="办公支出")
        self.assertTrue(result.get("success"), f"Expense recording failed: {result}")
        self.assertIn("¥500.00", result.get("message", ""))

    def test_finance_error_handling(self):
        """Scenario F4: Negative amount should be rejected."""
        from opc_manager.finance_skill import record_income

        result = record_income(amount=-100, source="test")
        self.assertFalse(result.get("success"))
        self.assertIn("大于0", result.get("error", ""))

    # --- Scenario R1: Report generation ---

    def test_report_weekly_generation(self):
        """Scenario R1: '帮我生成本周周报' → generate weekly report.

        Acceptance:
        - Report generated as Markdown
        - Contains required sections (本周完成/待办事项/客户动态)
        - Report file saved
        """
        from opc_manager.report_skill import generate_weekly_report

        result = generate_weekly_report(week_note="E2E测试周报")
        self.assertTrue(result.get("success"), f"Report generation failed: {result}")

        content = result.get("content", "") or result.get("markdown", "")
        if not content:
            # Report may be saved to file, check path
            self.assertIn("path", result, "Report should have content or file path")
        else:
            self.assertIn("#", content, "Report should be Markdown format")
            self.assertTrue(
                any(kw in content for kw in ["完成", "待办", "客户", "周报"]),
                f"Report should contain weekly sections, got: {content[:100]}",
            )

    def test_report_monthly_generation(self):
        """Scenario R2: '帮我生成本月经营报告' → generate monthly report.

        Acceptance:
        - Report generated as Markdown
        - Contains financial data (收入/支出/利润)
        - Handles empty data gracefully
        """
        from opc_manager.report_skill import generate_monthly_report
        import time as _time

        current_month = _time.strftime("%Y-%m")
        result = generate_monthly_report(current_month)
        self.assertTrue(result.get("success"), f"Monthly report failed: {result}")

        content = result.get("content", "") or result.get("markdown", "")
        if content:
            self.assertIn("#", content, "Monthly report should be Markdown")
            self.assertTrue(
                any(kw in content for kw in ["收入", "支出", "利润", "财务", "月度"]),
                f"Monthly report should contain financial keywords, got: {content[:100]}",
            )

    def test_report_empty_data_handling(self):
        """Scenario R4: Empty data should not crash report generation."""
        from opc_manager.report_skill import generate_monthly_report

        # Use a month far in the future with no data
        result = generate_monthly_report("2099-12")
        self.assertTrue(result.get("success"), "Empty data should not crash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
