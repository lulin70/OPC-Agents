"""task_content_generators 模块单元测试

覆盖 ContentGenerationMixin 的 5 个方法：
_try_llm_generate / _gen_real_report / _gen_real_plan /
_gen_real_content / _gen_writing_for_step
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from opc_manager.task_content_generators import ContentGenerationMixin


class _TestGenerator(ContentGenerationMixin):
    """Concrete subclass for testing the mixin."""

    def __init__(self, llm_content_gen=None, search_results=None):
        self.llm_content_gen = llm_content_gen
        self._mock_search_results = search_results or []

    def _search(self, query, max_results=8):
        return self._mock_search_results, []

    def _extract_search_query(self, user_input):
        return user_input


def _make_search_result(
    title="搜索结果", body="这是一段搜索结果内容" * 10, href="https://example.com"
):
    return {"title": title, "body": body, "href": href}


def _make_llm_result(content="LLM生成的内容" * 50, success=True, fallback_used=False):
    return SimpleNamespace(
        content=content, success=success, fallback_used=fallback_used
    )


# ---------------------------------------------------------------------------
# _try_llm_generate
# ---------------------------------------------------------------------------


class TestTryLlmGenerate:
    """_try_llm_generate 测试"""

    def test_no_llm_gen_returns_none(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is None

    def test_llm_success_returns_content(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="A" * 300))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is not None
        assert len(result) == 300

    def test_llm_short_content_returns_none(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="短内容"))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is None

    def test_llm_fallback_used_returns_none(self):
        llm = MagicMock()
        llm.generate = MagicMock(
            return_value=_make_llm_result(content="A" * 300, fallback_used=True)
        )
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is None

    def test_llm_not_success_returns_none(self):
        llm = MagicMock()
        llm.generate = MagicMock(
            return_value=_make_llm_result(content="A" * 300, success=False)
        )
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is None

    def test_llm_exception_returns_none(self):
        llm = MagicMock()
        llm.generate = MagicMock(side_effect=RuntimeError("LLM down"))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._try_llm_generate("查询", [], "report")
        assert result is None

    def test_template_map_doc_types(self):
        """All doc_type values should be accepted without error."""
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="A" * 300))
        gen = _TestGenerator(llm_content_gen=llm)
        for doc_type in ["report", "plan", "content", "analysis", "unknown"]:
            llm.generate.reset_mock()
            gen._try_llm_generate("查询", [], doc_type)
            assert llm.generate.called

    def test_title_replaces_topic_in_template(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="A" * 300))
        gen = _TestGenerator(llm_content_gen=llm)
        gen._try_llm_generate("查询", [], "report", title="自定义标题")
        call_kwargs = llm.generate.call_args
        assert "自定义标题" in call_kwargs.kwargs["template"]


# ---------------------------------------------------------------------------
# _gen_real_report
# ---------------------------------------------------------------------------


class TestGenRealReport:
    """_gen_real_report 测试"""

    def test_uses_llm_when_available(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="LLM报告" * 100))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._gen_real_report("帮我写报告", [], [])
        assert "LLM报告" in result

    def test_template_has_title(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("市场分析报告", [], [])
        assert "#  市场分析报告" in result

    def test_template_has_background_section(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", [], [])
        assert "背景与目的" in result

    def test_template_has_data_table(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", [], [])
        assert "维度" in result
        assert "效率指标" in result

    def test_template_has_action_items(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", [], [])
        assert "行动项" in result
        assert "P0" in result

    def test_with_search_results_includes_body(self):
        search = [_make_search_result(body="搜索到的关键信息" * 20)]
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", [], search)
        assert "搜索到的关键信息" in result

    def test_with_context_lines(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", ["## 上下文\n\n额外信息"], [])
        assert "额外信息" in result

    def test_topic_extraction_strips_keywords(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("帮我写AI报告", [], [])
        assert "AI" in result

    def test_with_two_search_results_includes_supplementary(self):
        search = [
            _make_search_result(body="第一结果" * 30),
            _make_search_result(body="第二结果补充信息" * 20),
        ]
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_report("报告", [], search)
        assert "第二结果补充信息" in result


# ---------------------------------------------------------------------------
# _gen_real_plan
# ---------------------------------------------------------------------------


class TestGenRealPlan:
    """_gen_real_plan 测试"""

    def test_uses_llm_when_available(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="LLM方案" * 100))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._gen_real_plan("帮我写方案", [], [])
        assert "LLM方案" in result

    def test_template_has_title(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("营销方案", [], [])
        assert "#  营销方案" in result

    def test_template_has_project_overview(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("方案", [], [])
        assert "项目概览" in result

    def test_template_has_smart_goals(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("方案", [], [])
        assert "SMART" in result
        assert "效率提升" in result

    def test_template_has_roadmap_phases(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("方案", [], [])
        assert "第一阶段" in result
        assert "第二阶段" in result
        assert "第三阶段" in result

    def test_template_has_risk_management(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("方案", [], [])
        assert "风险管理" in result
        assert "CCB" in result

    def test_template_has_acceptance_criteria(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("方案", [], [])
        assert "验收标准" in result

    def test_topic_extraction_strips_plan_keywords(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_plan("帮我写增长方案", [], [])
        assert "增长" in result


# ---------------------------------------------------------------------------
# _gen_real_content
# ---------------------------------------------------------------------------


class TestGenRealContent:
    """_gen_real_content 测试"""

    def test_uses_llm_when_available(self):
        llm = MagicMock()
        llm.generate = MagicMock(return_value=_make_llm_result(content="LLM内容" * 100))
        gen = _TestGenerator(llm_content_gen=llm)
        result = gen._gen_real_content("帮我写文章", [], [])
        assert "LLM内容" in result

    def test_template_has_title(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_content("我的文章", [], [])
        assert "#  我的文章" in result

    def test_with_search_results_lists_items(self):
        search = [
            _make_search_result(title="结果1", body="内容1" * 50),
            _make_search_result(title="结果2", body="内容2" * 50),
        ]
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_content("文章", [], search)
        assert "结果1" in result
        assert "结果2" in result

    def test_no_search_results_has_placeholder(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_content("文章", [], [])
        assert "请提供更多背景信息" in result

    def test_with_context_lines(self):
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_content("文章", ["## 前言\n前言内容"], [])
        assert "前言内容" in result

    def test_search_result_body_truncated(self):
        long_body = "A" * 1000
        search = [_make_search_result(body=long_body)]
        gen = _TestGenerator(llm_content_gen=None)
        result = gen._gen_real_content("文章", [], search)
        assert "..." in result


# ---------------------------------------------------------------------------
# _gen_writing_for_step
# ---------------------------------------------------------------------------


class TestGenWritingForStep:
    """_gen_writing_for_step 测试"""

    def test_generates_draft_with_desc(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("撰写市场分析", "帮我写市场分析")
        assert "内容草稿" in result
        assert "撰写市场分析" in result

    def test_includes_pdca_framework(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("描述", "查询")
        assert "PDCA" in result
        assert "Plan" in result
        assert "Do" in result

    def test_includes_action_items_table(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("描述", "查询")
        assert "行动项" in result
        assert "P0" in result

    def test_with_search_results_includes_reference(self):
        search = [_make_search_result(body="参考资料内容" * 20)]
        gen = _TestGenerator(llm_content_gen=None, search_results=search)
        result = gen._gen_writing_for_step("描述", "查询")
        assert "参考资料" in result
        assert "参考资料内容" in result

    def test_no_search_results_no_reference_section(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("描述", "查询")
        assert "参考资料" not in result

    def test_topic_extraction_strips_keywords(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("描述", "帮我写增长策略")
        assert "增长策略" in result

    def test_includes_summary_section(self):
        gen = _TestGenerator(llm_content_gen=None, search_results=[])
        result = gen._gen_writing_for_step("描述", "查询")
        assert "总结" in result
