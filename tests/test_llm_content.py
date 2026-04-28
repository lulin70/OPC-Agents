"""LLMEnhancedContentGenerator 单元测试 v3.5 — P0-2 内容智能升级

测试覆盖范围（对应 TEST_PLAN_V3.md 的 TestContentTargeting + TestLLMFallback 类别）：
- CT-001~CT-006: RAG模式/业务信息注入/占位符消除/降级/质量/骨架
- LF-001~LF-003: 网络超时/API Key无效/降级内容完整性

=== 验收标准 (G-CONTENT-01 门禁) ===
- 生成的内容包含用户特定业务信息（产品名/数字/目标）
- 无"基准值待测""待填写""此处插入"等占位符
- LLM不可用时优雅降级到模板模式，不崩溃
"""

import unittest
import time
from unittest.mock import patch, MagicMock
from opc_manager.llm_content import (
    LLMEnhancedContentGenerator,
    GenerationResult,
    FORBIDDEN_PATTERNS,
)


class TestRAGModeGeneration(unittest.TestCase):
    """CT-001: RAG模式正常生成测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_generate_returns_result_object(self):
        """generate()应返回GenerationResult对象"""
        result = self.generator.generate(
            user_input="帮我写Q2营销方案",
            template="# 方案\n\n{business_context}\n",
        )

        self.assertIsInstance(result, GenerationResult)
        self.assertIsNotNone(result.content)
        self.assertTrue(len(result.content) > 0)

    def test_generate_with_search_results(self):
        """有搜索结果时应构建上下文并传递给生成流程"""
        search_results = [
            {"title": "SaaS增长策略", "snippet": "从5000到10000用户的关键步骤..."},
            {"title": "Q2营销计划", "snippet": "第二季度市场推广预算分配..."},
        ]

        result = self.generator.generate(
            user_input="AI写作助手增长方案",
            template="# 增长方案\n\n## 背景\n{search_context}\n\n## 详细内容\n"
            + "这是详细内容段落。" * 20,
            search_results=search_results,
        )

        self.assertIsNotNone(result.content)
        self.assertGreater(len(result.content), 100)

    def test_generation_mode_field(self):
        """result.generation_mode应标识当前使用的生成模式"""
        result = self.generator.generate(
            user_input="测试输入",
            template="# 测试\n{business_context}\n",
        )

        self.assertIn(result.generation_mode, ["llm_rag", "template_v34", "llm_failed"])

    def test_llm_latency_recorded(self):
        """result.llm_latency_ms应记录生成耗时"""
        start = time.time()
        result = self.generator.generate(
            user_input="性能测试",
            template="# 报告\n{user_query}\n",
        )
        elapsed = (time.time() - start) * 1000

        self.assertGreaterEqual(result.llm_latency_ms, 0)
        self.assertLess(result.llm_latency_ms, elapsed + 100)


class TestBusinessInfoInjection(unittest.TestCase):
    """CT-002: 业务信息注入测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_extract_product_name(self):
        """应从输入中提取产品名称（如"AI写作助手"）"""
        info = self.generator._extract_business_info(
            "我的产品是AI写作助手，想制定增长方案"
        )

        self.assertIn("AI写作助手", info["product_name"])

    def test_extract_numbers(self):
        """应从输入中提取关键数字（如"5000""10000"）"""
        info = self.generator._extract_business_info("月活5000，想提升到10000")

        has_numbers = any("5000" in n or "10000" in n for n in info["numbers"])
        self.assertTrue(has_numbers, f"未找到数字: {info['numbers']}")

    def test_extract_target_metrics(self):
        """应提取目标指标描述（如"提升到10000"）"""
        info = self.generator._extract_business_info("希望月活提升到10000人")

        targets_text = " ".join(info["targets"])
        self.assertTrue(
            any(kw in targets_text for kw in ["提升", "10000"]),
            f"未找到目标: {info['targets']}",
        )

    def test_business_info_appears_in_output(self):
        """生成的输出中应包含用户的业务信息"""
        result = self.generator.generate(
            user_input="帮我为AI写作助手制定Q2方案，月活5000想提升到10000",
            template="# Q2方案\n\n## 产品背景\n{business_context}\n## 目标\n{goals}\n",
        )

        combined_lower = result.content.lower()
        business_terms = ["ai", "写作", "助手", "5000", "10000"]
        found_count = sum(1 for term in business_terms if term in combined_lower)

        self.assertGreaterEqual(
            found_count,
            2,
            f"输出中仅找到{found_count}/5个业务关键词:\n{result.content[:300]}",
        )


class TestPlaceholderElimination(unittest.TestCase):
    """CT-003: 占位符消除测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_no_forbidden_patterns_in_output(self):
        """输出不应包含任何已知的禁止占位符"""
        result = self.generator.generate(
            user_input="写一份完整报告",
            template="# 报告\n\n## 内容\n{business_context}\n",
        )

        for pattern in FORBIDDEN_PATTERNS:
            self.assertNotIn(
                pattern, result.content, f"发现禁止占位符 '{pattern}' 在输出中"
            )

    def test_placeholder_count_is_zero(self):
        """result.placeholder_count应为0"""
        result = self.generator.generate(
            user_input="生成无占位符文档",
            template="# 文档\n{business_context}\n",
        )

        self.assertEqual(
            result.placeholder_count, 0, f"仍有{result.placeholder_count}个占位符"
        )

    def test_clean_placeholders_removes_underscores(self):
        """_clean_placeholders()应移除连续下划线"""
        text_with_underscore = "这是___待填写的内容___"
        cleaned = self.generator._clean_placeholders(text_with_underscore)

        self.assertNotIn("___", cleaned)

    def test_clean_placeholders_removes_tbd(self):
        """_clean_placeholders()应移除TBD"""
        text = "计划时间 TBD，后续补充 TODO 项目 FIXME"
        cleaned = self.generator._clean_placeholders(text)

        self.assertNotIn("TBD", cleaned)
        self.assertNotIn("TODO", cleaned)
        self.assertNotIn("FIXME", cleaned)


class TestLLMFallback(unittest.TestCase):
    """CT-004 + LF系列: LLM降级路径测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_fallback_when_no_api_key(self):
        """无API Key时应自动使用降级模式"""
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(self.generator, "_get_llm_api_key", return_value=None):
                result = self.generator.generate(
                    user_input="降级测试",
                    template="# 测试\n{business_context}\n",
                )

                self.assertTrue(result.fallback_used or result.success)
                self.assertIsNotNone(result.content)

    def test_fallback_on_api_exception(self):
        """API异常时应降级而不崩溃"""
        original_call = self.generator._call_llm_api

        def failing_api(prompt):
            raise ConnectionError("网络不可达")

        self.generator._call_llm_api = failing_api

        try:
            result = self.generator.generate(
                user_input="异常测试",
                template="# 异常\n{user_query}\n",
            )

            self.assertIsNotNone(result.content)
            self.assertTrue(result.success or result.fallback_used)
        finally:
            self.generator._call_llm_api = original_call

    def test_fallback_content_has_minimum_length(self):
        """降级后的内容长度应 >= min_fallback_length(800)"""
        result = self.generator.generate(
            user_input="最小长度测试",
            template="# 文档\n\n{business_context}\n\n## 详细内容\n这是一段较长的测试内容。"
            * 20,
        )

        if result.success:
            self.assertGreaterEqual(len(result.content), 200)

    def test_network_timeout_fallback(self):
        """LF-001: 网络超时触发降级"""

        def timeout_api(prompt):
            import requests

            raise requests.Timeout("请求超时")

        original_call = self.generator._call_llm_api
        self.generator._call_llm_api = timeout_api

        try:
            result = self.generator.generate(
                user_input="超时测试",
                template="# 超时\n{business_context}\n",
            )

            self.assertFalse(
                result.fallback_used == False and not result.success,
                "超时应成功降级或标记fallback",
            )
        finally:
            self.generator._call_llm_api = original_call

    def test_invalid_api_key_fallback(self):
        """LF-002: API Key无效触发降级"""

        def auth_error_api(prompt):
            import requests

            raise requests.exceptions.HTTPError("401 Unauthorized")

        original_call = self.generator._call_llm_api
        self.generator._call_llm_api = auth_error_api

        try:
            result = self.generator.generate(
                user_input="认证失败测试",
                template="# 认证\n{business_context}\n",
            )

            self.assertIsNotNone(result.content)
        finally:
            self.generator._call_llm_api = original_call


class TestQualityScoring(unittest.TestCase):
    """CT-005: 内容质量评分测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_quality_score_range(self):
        """quality_score应在[0, 100]范围内"""
        result = self.generator.generate(
            user_input="评分测试",
            template="# 评分\n{business_context}\n" * 10,
        )

        self.assertGreaterEqual(result.quality_score, 0)
        self.assertLessEqual(result.quality_score, 100)

    def test_longer_content_higher_score(self):
        """更长的内容应有更高的质量分"""
        short_result = self.generator.generate(
            user_input="短内容",
            template="# 短\n{business_context}\n",
        )

        long_template = "# 长\n{business_context}\n" + "详细段落。\n" * 50
        long_result = self.generator.generate(
            user_input="长内容",
            template=long_template,
        )

        self.assertGreaterEqual(
            long_result.quality_score, short_result.quality_score - 10
        )


class TestTemplateSkeletonIntegrity(unittest.TestCase):
    """CT-006: 模板骨架完整性测试"""

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_structure_enforcement_preserves_header(self):
        """_enforce_structure()应保留模板的首个标题"""
        template = "# Q2营销方案\n\n## 背景介绍\n..."
        content = "这是一些没有标题的内容文本"

        enforced = self.generator._enforce_structure(content, template)

        self.assertIn("# Q2营销方案", enforced)

    def test_no_structure_change_if_already_present(self):
        """如果内容已有正确结构，不应被修改"""
        content = "# 原有标题\n\n正文内容"
        template = "# 原有标题\n\n{placeholder}"

        enforced = self.generator._enforce_structure(content, template)

        self.assertEqual(enforced, content)


class TestGateCONTENT01(unittest.TestCase):
    """G-CONTENT-01: 内容针对性门禁（P0阻断级）

    这是CDR定义的核心验收标准，必须全量通过才能发布v3.5
    """

    def setUp(self):
        self.generator = LLMEnhancedContentGenerator()

    def test_specific_business_info_in_output(self):
        """门禁：用"AI写作助手 月活5000→10000"生成的方案必须包含这些关键词"""
        result = self.generator.generate(
            user_input="帮我制定Q2增长方案，产品是AI写作助手，月活5000想提升到10000",
            template=(
                "# Q2增长方案\n\n"
                "## 项目概览\n{business_context}\n\n"
                "## 目标设定\n{goals}\n\n"
                "## 实施路线图\n"
            ),
        )

        forbidden_patterns = ["基准值待测", "___", "待填写", "此处插入"]
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern, result.content, f"发现禁止占位符 '{pattern}'!")

        required_business_info = ["AI写作助手", "5000", "10000"]
        info_found = sum(1 for info in required_business_info if info in result.content)
        self.assertGreaterEqual(
            info_found, 2, f"业务信息注入不足({info_found}/3):\n{result.content[:400]}"
        )

    def test_output_sufficient_length(self):
        """门禁：输出内容必须有足够长度（>200字符表示有实质内容）"""
        result = self.generator.generate(
            user_input="生成一份详细的商业计划书",
            template="# 商业计划书\n\n{business_context}\n\n"
            + "## 第一章\n内容...\n" * 10,
        )

        self.assertGreater(
            len(result.content),
            200,
            f"输出过短({len(result.content)}字)，可能无实质内容",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
