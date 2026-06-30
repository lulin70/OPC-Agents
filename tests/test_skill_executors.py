"""SkillExecutorMixin 单元测试 — 覆盖技能执行层

测试覆盖范围：
1. 各执行器方法的 happy path
2. LLM 调用失败时的错误处理
3. LLM 到规则引擎的降级回退
4. 领域技能委托
5. 异步执行路径
6. 错误传播（异常不被静默吞掉）
7. 输入验证
"""

import asyncio
import json
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from opc_manager.skill_executors import SkillExecutorMixin
from opc_manager.skill_models import SkillContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mixin(
    llm_service=None,
    search_processor=None,
    tool_system=None,
) -> SkillExecutorMixin:
    """创建一个独立的 SkillExecutorMixin 实例用于测试

    Adds stub methods for methods that live on SkillRegistry (not the mixin),
    so the mixin can call self.execute_skill / self._execute_collaborative.
    """
    mixin = SkillExecutorMixin()
    mixin.llm_service = llm_service
    mixin.search_processor = search_processor
    mixin.tool_system = tool_system
    mixin._web_search = None
    mixin._content_generator = None
    mixin._collab_in_progress = False
    # Stub methods from SkillRegistry that mixin methods call via self
    mixin.execute_skill = AsyncMock(
        return_value={"success": True, "data": {"results": []}}
    )
    mixin._execute_collaborative = MagicMock(return_value=None)
    return mixin


def _run(coro):
    """运行异步协程的辅助函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_llm_service():
    """创建模拟 LLM 服务"""
    return MagicMock()


def _make_mock_search_processor():
    """创建模拟搜索处理器"""
    processor = MagicMock()
    processed = MagicMock()
    processed.results = [
        {"title": "测试结果1", "href": "https://example.com/1", "body": "内容1"},
        {"title": "测试结果2", "href": "https://example.com/2", "body": "内容2"},
    ]
    processed.fallback_used = False
    processor.process.return_value = processed
    return processor


def _make_mock_tool_system():
    """创建模拟工具系统"""
    ts = MagicMock()
    ts.call_tool = AsyncMock(return_value={"success": True, "data": "ok"})
    return ts


# ---------------------------------------------------------------------------
# Test: _execute_intent_analysis
# ---------------------------------------------------------------------------


class TestExecuteIntentAnalysis(unittest.TestCase):
    """测试意图分析执行器"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_returns_intent_dict(self):
        """返回意图分析字典"""
        result = self.mixin._execute_intent_analysis("帮我写营销方案")
        self.assertIn("intent", result)
        self.assertIn("confidence", result)
        self.assertEqual(result["intent"]["goal"], "帮我写营销方案")
        self.assertEqual(result["intent"]["type"], "analysis")

    def test_default_confidence(self):
        """默认置信度为 0.85"""
        result = self.mixin._execute_intent_analysis("测试")
        self.assertAlmostEqual(result["confidence"], 0.85)

    def test_with_context(self):
        """传入 context 不影响结果"""
        ctx = SkillContext(user_input="测试")
        result = self.mixin._execute_intent_analysis("测试", _context=ctx)
        self.assertIn("intent", result)


# ---------------------------------------------------------------------------
# Test: _execute_search
# ---------------------------------------------------------------------------


class TestExecuteSearch(unittest.TestCase):
    """测试搜索执行器"""

    def setUp(self):
        self.processor = _make_mock_search_processor()
        self.mixin = _make_mixin(search_processor=self.processor)
        # Mock web search
        self.mixin._web_search = MagicMock()
        self.mixin._web_search.is_available.return_value = True
        self.mixin._web_search.search.return_value = [
            {"title": "原始结果", "href": "https://example.com", "body": "内容"}
        ]

    def test_happy_path_with_processor(self):
        """有 search_processor 时的正常路径"""
        result = _run(self.mixin._execute_search("营销方案"))
        self.assertIn("results", result)
        self.assertIn("count", result)
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["fallback_used"])

    def test_cleans_query_special_chars(self):
        """清理查询中的特殊字符"""
        result = _run(self.mixin._execute_search("test<>&\"'query"))
        self.assertIn("results", result)

    def test_empty_query_returns_empty(self):
        """空查询返回空结果"""
        result = _run(self.mixin._execute_search("  <>&\"'  "))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)

    def test_fallback_when_processor_fails(self):
        """search_processor 异常时降级"""
        self.processor.process.side_effect = Exception("processor error")
        result = _run(self.mixin._execute_search("测试"))
        self.assertIn("results", result)

    def test_no_search_processor(self):
        """无 search_processor 时直接返回原始结果"""
        mixin = _make_mixin(search_processor=None)
        mixin._web_search = MagicMock()
        mixin._web_search.is_available.return_value = True
        mixin._web_search.search.return_value = [
            {"title": "结果", "href": "https://example.com", "body": "内容"}
        ]
        result = _run(mixin._execute_search("测试"))
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["fallback_used"])

    def test_result_field_mapping(self):
        """结果字段映射：href→url, body→snippet"""
        result = _run(self.mixin._execute_search("测试"))
        for r in result["results"]:
            self.assertIn("title", r)
            self.assertIn("url", r)
            self.assertIn("snippet", r)

    def test_max_results_parameter(self):
        """max_results 参数传递"""
        result = _run(self.mixin._execute_search("测试", max_results=3))
        self.assertIn("results", result)


# ---------------------------------------------------------------------------
# Test: _do_web_search
# ---------------------------------------------------------------------------


class TestDoWebSearch(unittest.TestCase):
    """测试 Web 搜索底层方法"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_returns_empty_when_web_search_false(self):
        """_web_search 为 False 时返回空列表"""
        self.mixin._web_search = False
        result = _run(self.mixin._do_web_search("测试", 10))
        self.assertEqual(result, [])

    def test_returns_empty_when_not_available(self):
        """WebSearch 不可用时返回空列表"""
        mock_ws = MagicMock()
        mock_ws.is_available.return_value = False
        self.mixin._web_search = mock_ws
        result = _run(self.mixin._do_web_search("测试", 10))
        self.assertEqual(result, [])

    def test_returns_results_when_available(self):
        """WebSearch 可用时返回搜索结果"""
        mock_ws = MagicMock()
        mock_ws.is_available.return_value = True
        mock_ws.search.return_value = [{"title": "结果"}]
        self.mixin._web_search = mock_ws
        result = _run(self.mixin._do_web_search("测试", 5))
        self.assertEqual(len(result), 1)

    def test_returns_empty_on_exception(self):
        """搜索异常时返回空列表"""
        mock_ws = MagicMock()
        mock_ws.is_available.return_value = True
        mock_ws.search.side_effect = Exception("network error")
        self.mixin._web_search = mock_ws
        result = _run(self.mixin._do_web_search("测试", 5))
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test: _execute_analysis
# ---------------------------------------------------------------------------


class TestExecuteAnalysis(unittest.TestCase):
    """测试分析执行器"""

    def setUp(self):
        self.mixin = _make_mixin(llm_service=_make_mock_llm_service())

    def test_rule_based_fallback_when_no_llm(self):
        """无 LLM 服务时使用规则引擎降级"""
        mixin = _make_mixin(llm_service=None)
        result = _run(mixin._execute_analysis(goal="市场分析"))
        self.assertIn("analysis_result", result)
        self.assertIn("summary", result)
        self.assertIn("swot", result)

    def test_rule_based_analysis_structure(self):
        """规则引擎分析结果结构完整"""
        mixin = _make_mixin(llm_service=None)
        result = _run(mixin._execute_analysis(goal="市场分析", data=["数据1", "数据2"]))
        self.assertIn("key_findings", result)
        self.assertIn("action_items", result)
        self.assertIn("strengths", result["swot"])
        self.assertIn("weaknesses", result["swot"])
        self.assertIn("opportunities", result["swot"])
        self.assertIn("threats", result["swot"])

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_analysis_happy_path(self, mock_llm):
        """LLM 分析正常路径"""
        gen_result = MagicMock()
        gen_result.success = True
        gen_result.content = json.dumps(
            {
                "summary": "市场分析摘要",
                "key_findings": ["发现1"],
                "swot": {
                    "strengths": ["S1"],
                    "weaknesses": [],
                    "opportunities": [],
                    "threats": [],
                },
                "action_items": ["行动1"],
            }
        )
        mock_llm.return_value = gen_result

        result = _run(self.mixin._execute_analysis(goal="市场分析"))
        self.assertIn("analysis_result", result)
        self.assertEqual(result["summary"], "市场分析摘要")

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_failure_falls_back_to_rules(self, mock_llm):
        """LLM 调用失败时降级到规则引擎"""
        mock_llm.side_effect = Exception("LLM error")
        result = _run(self.mixin._execute_analysis(goal="市场分析"))
        self.assertIn("analysis_result", result)
        self.assertIn("需要更多数据", result["analysis_result"])

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_returns_none_falls_back(self, mock_llm):
        """LLM 返回 None 时降级到规则引擎"""
        mock_llm.return_value = None
        result = _run(self.mixin._execute_analysis(goal="市场分析"))
        self.assertIn("analysis_result", result)

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_returns_unsuccessful_falls_back(self, mock_llm):
        """LLM 返回 success=False 时降级到规则引擎"""
        gen_result = MagicMock()
        gen_result.success = False
        mock_llm.return_value = gen_result
        result = _run(self.mixin._execute_analysis(goal="市场分析"))
        self.assertIn("analysis_result", result)


# ---------------------------------------------------------------------------
# Test: _execute_content_generation
# ---------------------------------------------------------------------------


class TestExecuteContentGeneration(unittest.TestCase):
    """测试内容生成执行器"""

    def setUp(self):
        self.mixin = _make_mixin(llm_service=_make_mock_llm_service())

    def test_rule_based_fallback_when_no_llm(self):
        """无 LLM 服务时使用规则引擎降级"""
        mixin = _make_mixin(llm_service=None)
        result = _run(mixin._execute_content_generation(goal="营销方案"))
        self.assertIn("content", result)
        self.assertTrue(result["fallback_used"])
        self.assertAlmostEqual(result["quality_score"], 0.3)

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_content_generation_happy_path(self, mock_llm):
        """LLM 内容生成正常路径"""
        gen_result = MagicMock()
        gen_result.success = True
        gen_result.content = "# 营销方案\n\n详细内容..."
        gen_result.fallback_used = False
        gen_result.quality_score = 0.9
        mock_llm.return_value = gen_result

        result = _run(self.mixin._execute_content_generation(goal="营销方案"))
        self.assertEqual(result["content"], "# 营销方案\n\n详细内容...")
        self.assertFalse(result["fallback_used"])
        self.assertAlmostEqual(result["quality_score"], 0.9)

    @patch.object(SkillExecutorMixin, "_call_llm_generate")
    def test_llm_failure_falls_back(self, mock_llm):
        """LLM 失败时降级到规则引擎"""
        mock_llm.side_effect = Exception("LLM error")
        result = _run(self.mixin._execute_content_generation(goal="营销方案"))
        self.assertTrue(result["fallback_used"])

    def test_format_parameter_passed_through(self):
        """format 参数正确传递"""
        mixin = _make_mixin(llm_service=None)
        result = _run(mixin._execute_content_generation(goal="测试", format="html"))
        self.assertEqual(result["format"], "html")


# ---------------------------------------------------------------------------
# Test: _execute_operation
# ---------------------------------------------------------------------------


class TestExecuteOperation(unittest.TestCase):
    """测试操作执行器"""

    def setUp(self):
        self.tool_system = _make_mock_tool_system()
        self.mixin = _make_mixin(tool_system=self.tool_system)

    def test_happy_path_read_file(self):
        """read_file 操作正常路径"""
        _run(
            self.mixin._execute_operation("read_file", {"path": "/tmp/test.txt"})
        )
        self.tool_system.call_tool.assert_called_once_with(
            "file_read", {"path": "/tmp/test.txt"}
        )

    def test_happy_path_write_file(self):
        """write_file 操作正常路径"""
        _run(
            self.mixin._execute_operation(
                "write_file", {"path": "/tmp/out.txt", "content": "hi"}
            )
        )
        self.tool_system.call_tool.assert_called_once_with(
            "file_write", {"path": "/tmp/out.txt", "content": "hi"}
        )

    def test_unsupported_operation(self):
        """不支持的操作返回错误"""
        result = _run(self.mixin._execute_operation("delete_everything", {}))
        self.assertFalse(result["success"])
        self.assertIn("不支持的操作", result["error"])

    def test_tool_system_exception(self):
        """工具系统异常时返回错误"""
        self.tool_system.call_tool.side_effect = Exception("tool error")
        result = _run(
            self.mixin._execute_operation("read_file", {"path": "/tmp/test.txt"})
        )
        self.assertFalse(result["success"])
        self.assertIn("tool error", result["error"])

    def test_no_tool_system(self):
        """无工具系统时返回错误"""
        mixin = _make_mixin(tool_system=None)
        result = _run(mixin._execute_operation("read_file", {}))
        self.assertFalse(result["success"])
        self.assertIn("工具系统未初始化", result["error"])

    def test_default_parameters_empty_dict(self):
        """parameters 默认为空字典"""
        _run(self.mixin._execute_operation("read_file"))
        self.tool_system.call_tool.assert_called_once()


# ---------------------------------------------------------------------------
# Test: _execute_notification
# ---------------------------------------------------------------------------


class TestExecuteNotification(unittest.TestCase):
    """测试通知执行器"""

    def setUp(self):
        self.tool_system = _make_mock_tool_system()
        self.mixin = _make_mixin(tool_system=self.tool_system)

    def test_happy_path(self):
        """正常发送通知"""
        _run(
            self.mixin._execute_notification("测试消息", recipient="user@example.com")
        )
        self.tool_system.call_tool.assert_called_once()
        call_args = self.tool_system.call_tool.call_args
        self.assertEqual(call_args[0][0], "send_email")
        self.assertEqual(call_args[0][1]["to"], "user@example.com")
        self.assertEqual(call_args[0][1]["body"], "测试消息")

    def test_cleans_recipient_newlines(self):
        """清理收件人中的换行符（防止头部注入）"""
        _run(
            self.mixin._execute_notification(
                "消息", recipient="user@test.com\r\nBCC:evil@bad.com"
            )
        )
        call_args = self.tool_system.call_tool.call_args
        cleaned_to = call_args[0][1]["to"]
        self.assertNotIn("\r", cleaned_to)
        self.assertNotIn("\n", cleaned_to)

    def test_no_tool_system(self):
        """无工具系统时返回错误信息"""
        mixin = _make_mixin(tool_system=None)
        result = _run(mixin._execute_notification("消息", recipient="user@test.com"))
        self.assertFalse(result.get("sent", True))
        self.assertIn("error", result)

    def test_tool_system_exception(self):
        """工具系统异常时返回错误"""
        self.tool_system.call_tool.side_effect = Exception("email error")
        result = _run(
            self.mixin._execute_notification("消息", recipient="user@test.com")
        )
        self.assertFalse(result["success"])

    def test_default_subject(self):
        """默认邮件主题"""
        _run(
            self.mixin._execute_notification("消息", recipient="user@test.com")
        )
        call_args = self.tool_system.call_tool.call_args
        self.assertEqual(call_args[0][1]["subject"], "OPC-Agents 通知")


# ---------------------------------------------------------------------------
# Test: _execute_output
# ---------------------------------------------------------------------------


class TestExecuteOutput(unittest.TestCase):
    """测试输出执行器"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_happy_path(self):
        """正常输出"""
        result = self.mixin._execute_output(data={"key": "value"}, format="markdown")
        self.assertIn("output", result)
        self.assertIn("key", result["output"])
        self.assertEqual(result["format"], "markdown")

    def test_none_data_defaults_to_empty_dict(self):
        """data 为 None 时默认为空字典"""
        result = self.mixin._execute_output(data=None)
        self.assertIn("output", result)

    def test_json_formatting(self):
        """JSON 格式化输出"""
        result = self.mixin._execute_output(data={"name": "测试"})
        parsed = json.loads(result["output"].split("\n\n", 1)[1])
        self.assertEqual(parsed["name"], "测试")


# ---------------------------------------------------------------------------
# Test: _call_llm_generate
# ---------------------------------------------------------------------------


class TestCallLLMGenerate(unittest.TestCase):
    """测试 LLM 生成调用"""

    def setUp(self):
        self.mixin = _make_mixin(llm_service=_make_mock_llm_service())

    @patch("opc_manager.llm_content.LLMEnhancedContentGenerator")
    def test_happy_path(self, mock_gen_cls):
        """正常 LLM 生成"""
        mock_gen = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.content = "生成的内容"
        mock_gen.generate.return_value = mock_result
        mock_gen_cls.return_value = mock_gen
        self.mixin._content_generator = None

        result = _run(self.mixin._call_llm_generate("用户输入", "模板", []))
        self.assertTrue(result.success)

    @patch("opc_manager.llm_content.LLMEnhancedContentGenerator")
    def test_lazy_init_content_generator(self, mock_gen_cls):
        """懒初始化 _content_generator"""
        mock_gen = MagicMock()
        mock_gen.generate.return_value = MagicMock(success=True, content="内容")
        mock_gen_cls.return_value = mock_gen
        self.mixin._content_generator = None

        _run(self.mixin._call_llm_generate("输入", "模板"))
        self.assertIsNotNone(self.mixin._content_generator)

    def test_import_error_returns_none(self):
        """LLMEnhancedContentGenerator 导入失败时返回 None"""
        self.mixin._content_generator = None
        with patch.dict("sys.modules", {"opc_manager.llm_content": None}):
            result = _run(self.mixin._call_llm_generate("输入", "模板"))
            self.assertIsNone(result)

    @patch("opc_manager.llm_content.LLMEnhancedContentGenerator")
    def test_exception_returns_none(self, mock_gen_cls):
        """LLM 生成异常时返回 None"""
        mock_gen = MagicMock()
        mock_gen.generate.side_effect = Exception("LLM error")
        mock_gen_cls.return_value = mock_gen
        self.mixin._content_generator = None

        result = _run(self.mixin._call_llm_generate("输入", "模板"))
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Test: _get_analysis_template
# ---------------------------------------------------------------------------


class TestGetAnalysisTemplate(unittest.TestCase):
    """测试分析模板获取"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_returns_template_with_swot(self):
        """返回包含 SWOT 分析的模板"""
        template = self.mixin._get_analysis_template("市场分析")
        self.assertIn("SWOT", template)
        self.assertIn("优势", template)
        self.assertIn("劣势", template)
        self.assertIn("机会", template)
        self.assertIn("威胁", template)

    def test_template_contains_topic_placeholder(self):
        """模板包含 {topic} 占位符"""
        template = self.mixin._get_analysis_template("测试")
        self.assertIn("{topic}", template)


# ---------------------------------------------------------------------------
# Test: _get_content_template
# ---------------------------------------------------------------------------


class TestGetContentTemplate(unittest.TestCase):
    """测试内容模板获取"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_plan_template_for_strategy(self):
        """方案/计划/策略关键词返回方案模板"""
        template = self.mixin._get_content_template("营销方案")
        self.assertIn("路线图", template)
        self.assertIn("验收标准", template)

    def test_report_template(self):
        """报告/总结/回顾关键词返回报告模板"""
        template = self.mixin._get_content_template("季度报告")
        self.assertIn("摘要", template)
        self.assertIn("结论", template)

    def test_default_template(self):
        """无匹配关键词时返回默认模板"""
        template = self.mixin._get_content_template("随便写点什么")
        self.assertIn("{topic}", template)

    def test_plan_keywords(self):
        """测试所有方案关键词"""
        for kw in ["方案", "计划", "策略"]:
            template = self.mixin._get_content_template(f"测试{kw}")
            self.assertIn("路线图", template, f"关键词 '{kw}' 应匹配方案模板")

    def test_report_keywords(self):
        """测试所有报告关键词"""
        for kw in ["报告", "总结", "回顾"]:
            template = self.mixin._get_content_template(f"测试{kw}")
            self.assertIn("结论", template, f"关键词 '{kw}' 应匹配报告模板")


# ---------------------------------------------------------------------------
# Test: _parse_analysis_result
# ---------------------------------------------------------------------------


class TestParseAnalysisResult(unittest.TestCase):
    """测试分析结果解析"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_parse_json_content(self):
        """解析 JSON 格式的分析结果"""
        content = json.dumps(
            {
                "summary": "摘要",
                "key_findings": ["发现1"],
                "swot": {
                    "strengths": ["S1"],
                    "weaknesses": ["W1"],
                    "opportunities": ["O1"],
                    "threats": ["T1"],
                },
                "action_items": ["行动1"],
            }
        )
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertEqual(result["summary"], "摘要")
        self.assertEqual(result["key_findings"], ["发现1"])

    def test_parse_json_with_code_block(self):
        """解析带 ```json 代码块的 JSON"""
        content = (
            '```json\n{"summary": "摘要", "key_findings": [], "swot": '
            '{"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}, '
            '"action_items": []}\n```'
        )
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertEqual(result["summary"], "摘要")

    def test_parse_markdown_content(self):
        """解析 Markdown 格式的分析结果"""
        content = (
            "# 分析报告\n\n"
            "## 摘要\n\n这是摘要内容\n\n"
            "## 关键发现\n\n- 发现1\n- 发现2\n\n"
            "## 优势\n\n- 优势1\n\n"
            "## 劣势\n\n- 劣势1\n\n"
            "## 机会\n\n- 机会1\n\n"
            "## 威胁\n\n- 威胁1\n\n"
            "## 行动清单\n\n- 行动1\n"
        )
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertIn("摘要内容", result["summary"])
        self.assertGreater(len(result["key_findings"]), 0)
        self.assertGreater(len(result["swot"]["strengths"]), 0)

    def test_parse_invalid_json_falls_back(self):
        """无效 JSON 时回退到 Markdown 解析"""
        content = "这不是 JSON 也不是 Markdown"
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertIn("analysis_result", result)
        self.assertEqual(result["summary"], "")

    def test_parse_preserves_original_content(self):
        """解析结果保留原始内容"""
        content = "原始内容"
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertEqual(result["analysis_result"], content)

    def test_parse_swot_english_keywords(self):
        """解析英文 SWOT 关键词"""
        content = (
            "## strengths\n\n- S1\n\n"
            "## weaknesses\n\n- W1\n\n"
            "## opportunities\n\n- O1\n\n"
            "## threats\n\n- T1\n"
        )
        result = self.mixin._parse_analysis_result(content, "测试")
        self.assertGreater(len(result["swot"]["strengths"]), 0)
        self.assertGreater(len(result["swot"]["weaknesses"]), 0)


# ---------------------------------------------------------------------------
# Test: _rule_based_analysis
# ---------------------------------------------------------------------------


class TestRuleBasedAnalysis(unittest.TestCase):
    """测试规则引擎分析"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_returns_complete_structure(self):
        """返回完整的分析结构"""
        result = self.mixin._rule_based_analysis("市场分析", ["数据1", "数据2"])
        self.assertIn("analysis_result", result)
        self.assertIn("summary", result)
        self.assertIn("key_findings", result)
        self.assertIn("swot", result)
        self.assertIn("action_items", result)

    def test_includes_data_summary(self):
        """包含数据概览"""
        result = self.mixin._rule_based_analysis(
            "市场分析", ["数据1", "数据2", "数据3", "数据4", "数据5", "数据6"]
        )
        self.assertIn("数据1", result["analysis_result"])
        self.assertIn("数据5", result["analysis_result"])

    def test_empty_data(self):
        """空数据时正常返回"""
        result = self.mixin._rule_based_analysis("市场分析", [])
        self.assertIn("analysis_result", result)

    def test_none_data(self):
        """data 为 None 时正常返回"""
        result = self.mixin._rule_based_analysis("市场分析", None)
        self.assertIn("analysis_result", result)


# ---------------------------------------------------------------------------
# Test: _rule_based_content_generation
# ---------------------------------------------------------------------------


class TestRuleBasedContentGeneration(unittest.TestCase):
    """测试规则引擎内容生成"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_returns_content(self):
        """返回生成的内容"""
        result = self.mixin._rule_based_content_generation("营销方案", "markdown")
        self.assertIn("content", result)
        self.assertIn("营销方案", result["content"])
        self.assertTrue(result["fallback_used"])
        self.assertAlmostEqual(result["quality_score"], 0.3)

    def test_format_preserved(self):
        """format 参数正确传递"""
        result = self.mixin._rule_based_content_generation("测试", "html")
        self.assertEqual(result["format"], "html")


# ---------------------------------------------------------------------------
# Test: Domain skill delegation
# ---------------------------------------------------------------------------


class TestDomainSkillDelegation(unittest.TestCase):
    """测试领域技能委托

    Domain skills use local imports (e.g. `from opc_manager.email_skill import execute_goal`),
    so we patch at the module level where the import occurs.
    """

    def setUp(self):
        self.mixin = _make_mixin()

    @patch("opc_manager.email_skill.execute_goal")
    def test_execute_email_delegates(self, mock_execute):
        """邮件技能委托到 email_skill"""
        mock_execute.return_value = {"success": True, "email_sent": True}
        result = self.mixin._execute_email(
            goal="发送邮件", to="test@example.com", subject="测试", body="内容"
        )
        mock_execute.assert_called_once()
        self.assertTrue(result["success"])

    @patch("opc_manager.finance_skill.execute_goal")
    def test_execute_finance_delegates(self, mock_execute):
        """财务技能委托到 finance_skill"""
        mock_execute.return_value = {"success": True, "report": "财务报告"}
        result = self.mixin._execute_finance(goal="财务分析")
        mock_execute.assert_called_once()
        self.assertTrue(result["success"])

    @patch("opc_manager.task_skill.execute_goal")
    def test_execute_task_delegates(self, mock_execute):
        """任务技能委托到 task_skill"""
        mock_execute.return_value = {"success": True, "tasks": []}
        self.mixin._execute_task(goal="创建任务")
        mock_execute.assert_called_once()

    @patch("opc_manager.social_skill.execute_goal")
    def test_execute_social_delegates(self, mock_execute):
        """社交技能委托到 social_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_social(goal="社交媒体分析")
        mock_execute.assert_called_once()

    @patch("opc_manager.proposal_skill.execute_goal")
    def test_execute_proposal_delegates(self, mock_execute):
        """方案技能委托到 proposal_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_proposal(goal="写方案")
        mock_execute.assert_called_once()

    @patch("opc_manager.invoice_skill.execute_goal")
    def test_execute_invoice_delegates(self, mock_execute):
        """发票技能委托到 invoice_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_invoice(goal="开发票")
        mock_execute.assert_called_once()

    @patch("opc_manager.report_skill.execute_goal")
    def test_execute_report_delegates(self, mock_execute):
        """报告技能委托到 report_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_report(goal="生成报告")
        mock_execute.assert_called_once()

    @patch("opc_manager.calendar_skill.execute_goal")
    def test_execute_calendar_delegates(self, mock_execute):
        """日历技能委托到 calendar_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_calendar(goal="安排会议")
        mock_execute.assert_called_once()

    @patch("opc_manager.competitor_skill.execute_goal")
    def test_execute_competitor_delegates(self, mock_execute):
        """竞品技能委托到 competitor_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_competitor(goal="竞品分析")
        mock_execute.assert_called_once()

    @patch("opc_manager.pricing_skill.execute_goal")
    def test_execute_pricing_delegates(self, mock_execute):
        """定价技能委托到 pricing_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_pricing(goal="定价策略")
        mock_execute.assert_called_once()

    @patch("opc_manager.tax_reminder_skill.execute_goal")
    def test_execute_tax_reminder_delegates(self, mock_execute):
        """税务提醒技能委托到 tax_reminder_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_tax_reminder(goal="报税提醒")
        mock_execute.assert_called_once()

    @patch("opc_manager.dashboard_skill.execute_goal")
    def test_execute_dashboard_delegates(self, mock_execute):
        """仪表盘技能委托到 dashboard_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_dashboard(goal="查看仪表盘")
        mock_execute.assert_called_once()

    @patch("opc_manager.knowledge_skill.execute_goal")
    def test_execute_knowledge_delegates(self, mock_execute):
        """知识库技能委托到 knowledge_skill"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_knowledge(goal="搜索知识")
        mock_execute.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Error propagation
# ---------------------------------------------------------------------------


class TestErrorPropagation(unittest.TestCase):
    """测试错误传播 — 异常不被静默吞掉"""

    def setUp(self):
        self.mixin = _make_mixin()

    @patch(
        "opc_manager.email_skill.execute_goal", side_effect=RuntimeError("email crash")
    )
    def test_email_error_propagates(self, mock_exec):
        """邮件技能异常应传播"""
        with self.assertRaises(RuntimeError):
            self.mixin._execute_email(goal="发送邮件")

    @patch("opc_manager.task_skill.execute_goal", side_effect=ValueError("bad input"))
    def test_task_error_propagates(self, mock_exec):
        """任务技能异常应传播"""
        with self.assertRaises(ValueError):
            self.mixin._execute_task(goal="创建任务")

    def test_operation_error_returns_dict(self):
        """操作执行器异常时返回错误字典而非抛出"""
        tool_system = MagicMock()
        tool_system.call_tool = AsyncMock(side_effect=Exception("tool crash"))
        mixin = _make_mixin(tool_system=tool_system)
        result = _run(mixin._execute_operation("read_file", {"path": "/tmp/test"}))
        self.assertFalse(result["success"])
        self.assertIn("tool crash", result["error"])

    def test_notification_error_returns_dict(self):
        """通知执行器异常时返回错误字典而非抛出"""
        tool_system = MagicMock()
        tool_system.call_tool = AsyncMock(side_effect=Exception("email crash"))
        mixin = _make_mixin(tool_system=tool_system)
        result = _run(mixin._execute_notification("消息", recipient="test@test.com"))
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# Test: Input validation
# ---------------------------------------------------------------------------


class TestInputValidation(unittest.TestCase):
    """测试输入验证"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_search_empty_query(self):
        """搜索空查询返回空结果"""
        result = _run(self.mixin._execute_search(""))
        self.assertEqual(result["results"], [])
        self.assertEqual(result["count"], 0)

    def test_search_whitespace_only_query(self):
        """搜索仅含空格的查询返回空结果"""
        result = _run(self.mixin._execute_search("   "))
        self.assertEqual(result["results"], [])

    def test_search_special_chars_cleaned(self):
        """搜索查询中的特殊字符被清理"""
        result = _run(self.mixin._execute_search('<script>alert("xss")</script>'))
        self.assertIn("results", result)

    def test_output_none_data(self):
        """输出 data=None 不抛异常"""
        result = self.mixin._execute_output(data=None)
        self.assertIn("output", result)

    def test_operation_none_parameters(self):
        """操作 parameters=None 默认为空字典"""
        tool_system = _make_mock_tool_system()
        mixin = _make_mixin(tool_system=tool_system)
        _run(mixin._execute_operation("read_file", parameters=None))

    def test_notification_none_recipient(self):
        """通知 recipient=None 不抛异常"""
        tool_system = _make_mock_tool_system()
        mixin = _make_mixin(tool_system=tool_system)
        _run(mixin._execute_notification("消息", recipient=None))


# ---------------------------------------------------------------------------
# Test: Async execution paths
# ---------------------------------------------------------------------------


class TestAsyncExecutionPaths(unittest.TestCase):
    """测试异步执行路径"""

    def setUp(self):
        self.mixin = _make_mixin()

    def test_search_is_async(self):
        """_execute_search 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._execute_search))

    def test_analysis_is_async(self):
        """_execute_analysis 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._execute_analysis))

    def test_content_generation_is_async(self):
        """_execute_content_generation 是异步方法"""
        self.assertTrue(
            asyncio.iscoroutinefunction(self.mixin._execute_content_generation)
        )

    def test_operation_is_async(self):
        """_execute_operation 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._execute_operation))

    def test_notification_is_async(self):
        """_execute_notification 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._execute_notification))

    def test_do_web_search_is_async(self):
        """_do_web_search 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._do_web_search))

    def test_call_llm_generate_is_async(self):
        """_call_llm_generate 是异步方法"""
        self.assertTrue(asyncio.iscoroutinefunction(self.mixin._call_llm_generate))

    def test_intent_analysis_is_sync(self):
        """_execute_intent_analysis 是同步方法"""
        self.assertFalse(
            asyncio.iscoroutinefunction(self.mixin._execute_intent_analysis)
        )

    def test_output_is_sync(self):
        """_execute_output 是同步方法"""
        self.assertFalse(asyncio.iscoroutinefunction(self.mixin._execute_output))


# ---------------------------------------------------------------------------
# Test: _execute_crm (complex delegation)
# ---------------------------------------------------------------------------


class TestExecuteCRM(unittest.TestCase):
    """测试 CRM 技能的复杂委托逻辑"""

    def setUp(self):
        self.mixin = _make_mixin()

    @patch("opc_manager.crm_skill.execute_goal")
    def test_simple_crm_delegates(self, mock_execute):
        """简单 CRM 查询直接委托"""
        mock_execute.return_value = {"success": True, "customers": []}
        self.mixin._execute_crm(goal="查看客户列表")
        mock_execute.assert_called_once()

    @patch("opc_manager.crm_skill.get_customer")
    @patch("opc_manager.crm_skill.execute_goal")
    def test_crm_with_email_triggers_collaborative(
        self, mock_crm_exec, mock_get_customer
    ):
        """包含"发邮件"关键词时触发协作"""
        self.mixin._execute_collaborative = MagicMock(
            return_value={"success": True, "collaborative": True}
        )
        mock_get_customer.return_value = {"name": "张三", "email": "zhang@test.com"}
        self.mixin._execute_crm(goal="给张三发邮件")
        self.mixin._execute_collaborative.assert_called_once()

    @patch("opc_manager.crm_skill.execute_goal")
    def test_crm_collaborative_returns_none_falls_back(self, mock_crm_exec):
        """协作返回 None 时回退到 CRM 执行"""
        self.mixin._execute_collaborative = MagicMock(return_value=None)
        mock_crm_exec.return_value = {"success": True}
        self.mixin._execute_crm(goal="给张三发邮件")
        mock_crm_exec.assert_called_once()


# ---------------------------------------------------------------------------
# Test: _execute_finance (collaborative trigger)
# ---------------------------------------------------------------------------


class TestExecuteFinance(unittest.TestCase):
    """测试财务技能的协作触发"""

    def setUp(self):
        self.mixin = _make_mixin()

    @patch("opc_manager.finance_skill.execute_goal")
    def test_simple_finance_delegates(self, mock_execute):
        """简单财务查询直接委托"""
        mock_execute.return_value = {"success": True}
        self.mixin._execute_finance(goal="财务分析")
        mock_execute.assert_called_once()

    @patch("opc_manager.finance_skill.execute_goal")
    def test_tax_reminder_triggers_collaborative(self, mock_finance_exec):
        """报税/提醒关键词触发协作"""
        self.mixin._execute_collaborative = MagicMock(
            return_value={"success": True, "collaborative": True}
        )
        self.mixin._execute_finance(goal="报税提醒")
        self.mixin._execute_collaborative.assert_called_once()

    @patch("opc_manager.finance_skill.execute_goal")
    def test_collaborative_returns_none_falls_back(self, mock_finance_exec):
        """协作返回 None 时回退到财务执行"""
        self.mixin._execute_collaborative = MagicMock(return_value=None)
        mock_finance_exec.return_value = {"success": True}
        self.mixin._execute_finance(goal="报税提醒")
        mock_finance_exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
