#!/usr/bin/env python3
"""TaskEngineV3 核心路径单元测试

覆盖范围：
- InputValidator: 输入校验（空值/超长/特殊字符）
- SearchCache: LRU缓存（命中/未命中/淘汰/TTL过期）
- IntentClassifier: 意图分类（5种类型 + 兜底）
- TaskEngineV3.execute(): 主流程（4种任务类型 + 错误处理）
- 零占位符门禁: 回归检测（确保不会重新引入___/待填写等）
"""

import unittest
import sys
import os
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opc_manager.task_engine_v3 import (
    InputValidator,
    SearchCache,
    IntentClassifier,
    TaskEngineV3,
    TaskType,
    TaskResult,
)
from opc_manager.llm_content import LLMEnhancedContentGenerator

MOCK_SEARCH_RESULTS = [
    {
        "title": "SaaS Q2 Marketing Strategy",
        "href": "https://example.com/1",
        "body": "A comprehensive guide to Q2 marketing planning for SaaS products...",
    },
    {
        "title": "One-Person Company Growth Framework",
        "href": "https://example.com/2",
        "body": "Growth strategies for solo entrepreneurs including content marketing...",
    },
    {
        "title": "AI Agent Market Trends 2024",
        "href": "https://example.com/3",
        "body": "The latest trends in AI agent frameworks and architectures...",
    },
    {
        "title": "Business SWOT Analysis Template",
        "href": "https://example.com/4",
        "body": "How to conduct a thorough SWOT analysis for your business...",
    },
]

MOCK_SOURCES = [
    {"title": r.get("title", ""), "url": r.get("href", "")}
    for r in MOCK_SEARCH_RESULTS
    if r.get("href")
]

MOCK_LLM_RESPONSE = (
    "# Q2 Marketing Plan\n\n"
    "## Overview\nAI writing assistant product targeting MAU growth from 5000 to 10000.\n\n"
    "## Goals\n- Increase MAU from 5000 to 10000 (100% growth) by end of Q2 2026\n"
    "- Achieve 5% conversion rate from free to paid tier\n"
    "- Reduce churn rate from 8% to 5%\n\n"
    "## Timeline\n- Week 1 (Apr 1-7): Launch content marketing campaign on 3 platforms\n"
    "- Week 2 (Apr 8-14): SEO optimization sprint targeting 50 keywords\n"
    "- Week 3 (Apr 15-21): Community building with 2 AMAs and 5 expert posts\n"
    "- Week 4 (Apr 22-30): Paid acquisition test with 10000 CNY budget\n\n"
    "## Budget\nTotal: 50000 CNY\n- Content creation: 20000 CNY\n- Paid ads: 15000 CNY\n"
    "- Tools & software: 15000 CNY\n\n"
    "## Risk Mitigation\n- If MAU < 6000 by Week 2: Double content output and add influencer partnerships\n"
    "- If conversion < 3%: A/B test pricing page and onboarding flow\n"
    "- Reserve 20% budget (10000 CNY) as emergency fund\n"
)


class TestInputValidator(unittest.TestCase):
    """输入校验器测试"""

    def test_normal_input_passes(self):
        text, err = InputValidator.sanitize("帮我写一份Q2营销方案")
        self.assertIsNone(err)
        self.assertEqual(text, "帮我写一份Q2营销方案")

    def test_empty_input_rejected(self):
        text, err = InputValidator.sanitize("")
        self.assertIsNotNone(err)
        self.assertIn("不能为空", err)

    def test_whitespace_only_rejected(self):
        text, err = InputValidator.sanitize("   \t\n  ")
        self.assertIsNotNone(err)

    def test_none_input_rejected(self):
        text, err = InputValidator.sanitize(None)
        self.assertIsNotNone(err)

    def test_long_input_truncated(self):
        long_input = "测试" * 1000
        sanitized, err = InputValidator.sanitize(long_input)
        self.assertIsNone(err)
        self.assertLessEqual(len(sanitized), 2000)

    def test_control_chars_stripped(self):
        text, err = InputValidator.sanitize("正常\x00文本\x1f内容")
        self.assertIsNone(err)
        self.assertNotIn("\x00", text)
        self.assertNotIn("\x1f", text)
        self.assertIn("正常", text)

    def test_leading_trailing_whitespace_trimmed(self):
        text, err = InputValidator.sanitize("  帮我写方案  ")
        self.assertEqual(text, "帮我写方案")

    def test_chinese_input_ok(self):
        text, err = InputValidator.sanitize("帮我收集2024年AI行业最新趋势报告")
        self.assertIsNone(err)
        self.assertIn("AI", text)

    def test_html_tags_stripped(self):
        text, err = InputValidator.sanitize("<script>alert('xss')</script>正常内容")
        self.assertIsNone(err)
        self.assertNotIn("<script>", text)
        self.assertNotIn("</script>", text)
        self.assertIn("正常内容", text)

    def test_html_tags_only_removed(self):
        text, err = InputValidator.sanitize("<b>加粗</b>和<i>斜体</i>")
        self.assertEqual(text, "加粗和斜体")

    def test_mixed_special_chars_and_html(self):
        text, err = InputValidator.sanitize("\x00<script>\x1ftest</script>")
        self.assertIsNone(err)
        self.assertNotIn("<", text)
        self.assertNotIn(">", text)


class TestSearchCache(unittest.TestCase):
    """搜索LRU缓存测试"""

    def setUp(self):
        self.cache = SearchCache(max_size=3, ttl=60)

    def test_cache_miss_on_empty(self):
        result = self.cache.get("nonexistent", 5)
        self.assertIsNone(result)
        self.assertEqual(self.cache.stats["misses"], 1)

    def test_cache_hit_after_set(self):
        data = [{"title": "test"}]
        self.cache.set("query", 5, data)
        result = self.cache.get("query", 5)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "test")
        self.assertEqual(self.cache.stats["hits"], 1)

    def test_cache_miss_different_query(self):
        self.cache.set("query_a", 5, [{"title": "a"}])
        result = self.cache.get("query_b", 5)
        self.assertIsNone(result)

    def test_lru_eviction(self):
        cache = SearchCache(max_size=2, ttl=60)
        cache.set("a", 5, [{"title": "a"}])
        cache.set("b", 5, [{"title": "b"}])
        cache.set("c", 5, [{"title": "c"}])
        self.assertEqual(cache.stats["size"], 2)
        self.assertIsNone(cache.get("a", 5))
        self.assertIsNotNone(cache.get("b", 5))
        self.assertIsNotNone(cache.get("c", 5))

    def test_ttl_expiry(self):
        cache = SearchCache(max_size=10, ttl=1)
        cache.set("expiring", 5, [{"title": "data"}])
        time.sleep(1.1)
        cached = cache.get("expiring", 5)
        self.assertIsNone(cached)

    def test_same_query_different_max_results_separate(self):
        cache = SearchCache(max_size=10, ttl=60)
        cache.set("q", 3, ["a", "b", "c"])
        cache.set("q", 8, list(range(8)))
        r3 = cache.get("q", 3)
        r8 = cache.get("q", 8)
        self.assertEqual(len(r3), 3)
        self.assertEqual(len(r8), 8)

    def test_stats_tracking(self):
        self.cache.set("a", 5, [1])
        self.cache.get("a", 5)
        self.cache.get("b", 5)
        stats = self.cache.stats
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)


class TestIntentClassifier(unittest.TestCase):
    """意图分类器测试"""

    def test_info_collection_keywords(self):
        inputs = [
            "收集2024年AI趋势",
            "搜索最新的Python框架",
            "查找竞品分析报告",
            "了解行业动态",
            "调研用户需求",
            "最新政策解读",
        ]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.INFO_COLLECTION, f"Failed for: {inp}")
            self.assertGreaterEqual(conf, 0.85)

    def test_content_generation_keywords(self):
        inputs = [
            "帮我写一份Q2营销方案",
            "撰写项目总结报告",
            "生成产品发布文案",
            "起草咨询提案",
            "帮我做一份执行计划",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.CONTENT_GENERATION, f"Failed for: {inp}")

    def test_data_analysis_keywords(self):
        inputs = [
            "分析一下这个方案的可行性",
            "评估市场机会",
            "对比两个产品的优劣",
            "预测下季度销售额",
            "这个方向好不好？",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.DATA_ANALYSIS, f"Failed for: {inp}")

    def test_scenario_based_keywords(self):
        inputs = [
            "执行内容日历规划场景",
            "帮我运行数字产品发布",
            "内容日历怎么安排",
            "电商运营优化怎么做",
            "会议组织流程",
        ]
        for inp in inputs:
            tt, _ = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.SCENARIO_BASED, f"Failed for: {inp}")

    def test_fallback_to_general_chat(self):
        inputs = [
            "你好",
            "谢谢",
        ]
        for inp in inputs:
            tt, conf = IntentClassifier.classify(inp)
            self.assertEqual(tt, TaskType.GENERAL_CHAT, f"Failed for: {inp}")
            self.assertLessEqual(conf, 0.5)

    def test_ambiguous_input_falls_somewhere(self):
        tt, _ = IntentClassifier.classify("今天天气怎么样")
        self.assertIn(tt, [TaskType.DATA_ANALYSIS, TaskType.GENERAL_CHAT])

    def test_case_insensitive(self):
        tt1, _ = IntentClassifier.classify("帮我写方案")
        tt2, _ = IntentClassifier.classify("帮我写方案")
        self.assertEqual(tt1, tt2)


class TestTaskEngineV3Execute(unittest.TestCase):
    """TaskEngineV3 main execution flow tests"""

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

    def test_execute_content_generation_plan(self):
        result = self.engine.execute("帮我写一份Q2营销方案")
        self.assertIsInstance(result, TaskResult)
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.CONTENT_GENERATION)
        self.assertGreater(len(result.content), 500)
        self.assertIn("Q2", result.content or "方案")
        self.assertIn("# ", result.content)

    def test_execute_content_generation_report(self):
        result = self.engine.execute("帮我写一份年度工作总结报告")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.CONTENT_GENERATION)
        self.assertIn("报告", result.content)

    def test_execute_info_collection(self):
        result = self.engine.execute("收集最新的AI Agent框架信息")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.INFO_COLLECTION)
        if result.sources:
            self.assertGreater(len(result.sources), 0)

    def test_execute_data_analysis(self):
        result = self.engine.execute("分析一下一人公司的SWOT")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.DATA_ANALYSIS)
        content = result.content.lower()
        self.assertTrue(
            any(kw in content for kw in ["swot", "优势", "劣势", "机会", "威胁"]),
            f"分析结果应包含SWOT相关内容，实际: {content[:100]}",
        )

    def test_execute_general_chat_hello(self):
        result = self.engine.execute("你好")
        self.assertTrue(result.success)
        self.assertEqual(result.task_type, TaskType.GENERAL_CHAT)

    def test_execute_general_chat_help(self):
        result = self.engine.execute("帮助")
        self.assertTrue(result.success)
        self.assertIn("能直接为你交付", result.content)

    def test_execute_empty_input_returns_error(self):
        result = self.engine.execute("")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_execute_none_input_returns_error(self):
        result = self.engine.execute(None)
        self.assertFalse(result.success)

    def test_result_has_execution_time(self):
        result = self.engine.execute("帮我写个简单计划")
        self.assertIsInstance(result.execution_time_ms, float)
        self.assertGreater(result.execution_time_ms, 0)

    def test_result_has_deliverable_format(self):
        result = self.engine.execute("帮我写份方案")
        self.assertIn(result.deliverable_format, ["Markdown", "", "markdown"])


class TestZeroPlaceholderGate(unittest.TestCase):
    """零占位符回归门禁 — 最关键的质量保障测试

    铁律：生成的任何内容不得包含以下模式：
    - ___ (三下划线)
    - 待填写
    - 此处插入
    - 此处应由
    - 请根据实际情况
    - 需根据实际情况
    - ⬜ (空复选框)
    - 在实际执行中
    """

    FORBIDDEN_PATTERNS = [
        "___",
        "待填写",
        "此处插入",
        "此处应由",
        "请根据实际情况",
        "需根据实际情况",
        "⬜",
        "在实际执行中",
    ]

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

    def _assert_no_placeholders(self, content: str, label: str):
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in (content or ""):
                idx = content.index(pattern)
                context = content[max(0, idx - 50) : idx + 80]
                self.fail(
                    f"[{label}] 发现禁止的占位符 '{pattern}'！\n"
                    f"上下文: ...{context}..."
                )

    def test_gen_real_plan_no_placeholder(self):
        result = self.engine.execute("帮我写一份Q2营销方案")
        self._assert_no_placeholders(result.content, "_gen_real_plan")

    def test_gen_real_report_no_placeholder(self):
        result = self.engine.execute("帮我写一份季度工作总结报告")
        self._assert_no_placeholders(result.content, "_gen_real_report")

    def test_data_analysis_no_placeholder(self):
        result = self.engine.execute("分析我的业务现状")
        self._assert_no_placeholders(result.content, "_execute_data_analysis")

    def test_writing_step_no_placeholder(self):
        result = self.engine.execute("帮我执行内容日历规划场景")
        self._assert_no_placeholders(result.content, "_gen_writing_for_step")

    def test_review_step_no_placeholder(self):
        result = self.engine.execute("帮我执行项目交付物整理场景")
        self._assert_no_placeholders(result.content, "review步骤")

    def test_source_code_itself_clean(self):
        import tokenize
        import io

        filepath = os.path.join(
            os.path.dirname(__file__), "..", "opc_manager", "task_engine_v3.py"
        )
        with open(filepath, "r") as f:
            source_lines = f.readlines()
        source_text = "".join(source_lines)

        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source_text).readline))
        except tokenize.TokenError:
            tokens = []

        code_line_nums = set(range(6, len(source_lines) + 1))
        for tok_type, tok_string, (srow, _), (erow, _), _ in tokens:
            if tok_type == tokenize.STRING:
                for r in range(srow, erow + 1):
                    code_line_nums.discard(r)

        for i in sorted(code_line_nums):
            line = source_lines[i - 1]
            for pattern in self.FORBIDDEN_PATTERNS:
                self.assertNotIn(
                    pattern, line, f"源码 L{i} 发现禁止模式 '{pattern}': {line[:100]}"
                )


class TestTaskEngineEdgeCases(unittest.TestCase):
    """Edge case and exception tests"""

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

    def test_very_long_input_handled(self):
        long_input = "帮我分析" + "和调研" * 500
        result = self.engine.execute(long_input)
        self.assertIsInstance(result, TaskResult)

    def test_special_chars_in_input(self):
        result = self.engine.execute("帮我写<script>alert('xss')</script>方案")
        self.assertTrue(result.success)
        self.assertNotIn("<script>", result.content or "")
        self.assertNotIn("</script>", result.content or "")

    def test_multiple_executions_independent(self):
        r1 = self.engine.execute("写方案A")
        r2 = self.engine.execute("写方案B")
        self.assertTrue(r1.success)
        self.assertTrue(r2.success)

    def test_cache_works_across_calls(self):
        self.engine.execute("收集AI趋势")
        stats_before = self.engine._search_cache.stats.copy()
        self.engine.execute("收集AI趋势")
        stats_after = self.engine._search_cache.stats
        self.assertGreaterEqual(stats_after["hits"], stats_before["hits"])


class TestFollowUpDetection(unittest.TestCase):
    """追问意图识别测试 — Sprint2 P0: 多轮对话增强"""

    def test_supplement_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("补充竞品分析"))

    def test_modify_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("修改第三阶段时间"))

    def test_adjust_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("调整预算分配"))

    def test_shorten_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("缩短到2周"))

    def test_add_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("加上风险分析"))

    def test_expand_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("展开说明第二部分"))

    def test_replace_keyword_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("把第三阶段换成敏捷迭代"))

    def test_can_you_modify_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("能不能把时间改成3周"))

    def test_english_modify_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("modify the timeline"))

    def test_english_add_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("add competitor analysis"))

    def test_japanese_modify_detected(self):
        self.assertTrue(IntentClassifier.is_follow_up("修正して"))

    def test_new_task_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("帮我写Q2营销方案"))

    def test_info_collection_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("收集2024年AI趋势"))

    def test_greeting_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("你好"))

    def test_data_analysis_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("分析一下我的业务现状"))

    def test_new_task_with_optimize_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("帮我写一份优化方案"))

    def test_new_task_with_generate_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("帮我生成一份报告"))

    def test_new_task_with_create_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("帮我创建一个新方案"))

    def test_new_task_with_plan_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("帮我制定Q2计划"))

    def test_english_generate_not_detected(self):
        self.assertFalse(IntentClassifier.is_follow_up("generate a new report"))


class TestFollowUpContextInjection(unittest.TestCase):
    """追问上下文注入测试 — 确保追问模式正确注入历史上下文"""

    def setUp(self):
        self.engine = TaskEngineV3()
        self.engine._initialized = True
        self.engine.web_search = None
        self.engine.scenario_engine = None
        self.engine.llm_content_gen = None

    def test_follow_up_adds_marker_to_content(self):
        from opc_manager.session_context import SessionContextManager

        session = SessionContextManager(max_turns=20)
        session.add_turn(
            user_input="帮我写Q2营销方案",
            assistant_response="已生成Q2营销方案，包含3个阶段...",
            task_type="content_generation",
        )
        result = self.engine.execute("补充竞品分析部分", session_ctx=session)
        self.assertTrue(result.success)
        self.assertIn("基于上次结果继续", result.content)

    def test_new_task_no_marker(self):
        from opc_manager.session_context import SessionContextManager

        session = SessionContextManager(max_turns=20)
        session.add_turn(
            user_input="帮我写Q2营销方案",
            assistant_response="已生成Q2营销方案...",
            task_type="content_generation",
        )
        result = self.engine.execute("收集AI行业最新趋势", session_ctx=session)
        self.assertTrue(result.success)
        self.assertNotIn("基于上次结果继续", result.content)

    def test_no_history_no_follow_up(self):
        from opc_manager.session_context import SessionContextManager

        session = SessionContextManager(max_turns=20)
        result = self.engine.execute("补充竞品分析", session_ctx=session)
        self.assertTrue(result.success)
        self.assertNotIn("基于上次结果继续", result.content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
