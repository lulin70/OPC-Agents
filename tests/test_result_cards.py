"""result_cards 模块单元测试

覆盖所有核心函数：
- render_result_card(): 5种task_type渲染
- _render_card_header(): 头部组件
- _render_metadata_bar(): 元数据栏
- _render_action_buttons(): 操作按钮
- _render_content_preview(): 内容预览/截断
- _extract_data_insights(): 数据洞察提取
- get_task_type_label(): 标签获取
- validate_deliverable_record(): 记录验证
"""

import unittest
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontend.components.result_cards import (
    TASK_TYPE_CONFIG,
    render_result_card,
    _render_card_header,
    _render_metadata_bar,
    _render_action_buttons,
    _render_content_preview,
    _extract_data_insights,
    get_task_type_label,
    validate_deliverable_record,
)


class TestTaskTypeConfig(unittest.TestCase):
    """TASK_TYPE_CONFIG配置完整性测试"""

    def test_all_required_types_exist(self):
        """TC-001: 所有必需的task_type都存在"""
        required_types = [
            "content_generation",
            "data_analysis",
            "info_collection",
            "scenario_based",
            "general_chat",
        ]
        for task_type in required_types:
            self.assertIn(task_type, TASK_TYPE_CONFIG)

    def test_config_has_required_keys(self):
        """TC-002: 每个config都包含必要字段"""
        required_keys = ["icon", "title", "gradient_start", "gradient_end", "bg_color"]
        for task_type, config in TASK_TYPE_CONFIG.items():
            for key in required_keys:
                self.assertIn(key, config, f"{task_type}缺少{key}字段")

    def test_gradient_colors_are_valid_hex(self):
        """TC-003: 渐变色为有效的HEX格式"""
        hex_pattern = r"^#[0-9A-Fa-f]{6}$"
        for config in TASK_TYPE_CONFIG.values():
            self.assertRegex(config["gradient_start"], hex_pattern)
            self.assertRegex(config["gradient_end"], hex_pattern)


class TestRenderResultCard(unittest.TestCase):
    """render_result_card()主函数测试"""

    @patch("frontend.components.result_cards.st")
    def test_render_with_content_generation(self, mock_st):
        """TC-004: CONTENT_GENERATION类型卡片渲染"""
        content = "# 测试报告\n\n这是测试内容"
        record = {
            "filename": "test.md",
            "filepath": "/tmp/test.md",
            "prompt": "测试任务",
            "task_type": "content_generation",
            "created_at": "2024-01-01 12:00:00",
            "size_kb": 5.2,
            "meta": {"execution_time_ms": 2300, "sources_count": 3},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            render_result_card(content, "content_generation", record, temp_path)
            mock_st.markdown.assert_called()
            mock_st.container.assert_called()
        finally:
            os.unlink(temp_path)

    @patch("frontend.components.result_cards.st")
    def test_render_with_data_analysis(self, mock_st):
        """TC-005: DATA_ANALYSIS类型卡片渲染"""
        content = "分析结果显示增长率为25.5%"
        record = {
            "meta": {"sources_count": 5},
        }
        render_result_card(content, "data_analysis", record, None)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_render_with_info_collection(self, mock_st):
        """TC-006: INFO_COLLECTION类型卡片渲染"""
        content = "收集到以下信息..."
        render_result_card(content, "info_collection", {}, None)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_render_with_scenario_based(self, mock_st):
        """TC-007: SCENARIO_BASED类型卡片渲染"""
        content = "场景执行结果..."
        render_result_card(content, "scenario_based", {}, None)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_render_with_general_chat(self, mock_st):
        """TC-008: GENERAL_CHAT类型卡片渲染（无下载按钮）"""
        content = "对话内容..."
        with patch.object(
            sys.modules["frontend.components.result_cards"].st, "container"
        ):
            render_result_card(content, "general_chat", {}, None)

    @patch("frontend.components.result_cards.st")
    def test_render_empty_content_shows_warning(self, mock_st):
        """TC-009: 空内容显示警告"""
        render_result_card("", "general_chat", {}, None)
        mock_st.warning.assert_called_once()

    @patch("frontend.components.result_cards.st")
    def test_render_none_task_type_defaults_to_general(self, mock_st):
        """TC-010: None task_type默认使用general_chat配置"""
        content = "测试内容"
        render_result_card(content, None, {}, None)
        mock_st.markdown.assert_called()


class TestRenderCardHeader(unittest.TestCase):
    """_render_card_header()头部组件测试"""

    @patch("frontend.components.result_cards.st")
    def test_header_includes_icon_and_title(self, mock_st):
        """TC-011: 头部包含图标和标题"""
        config = TASK_TYPE_CONFIG["content_generation"]
        _render_card_header("content_generation", config)
        mock_st.markdown.assert_called_once()
        call_args = mock_st.markdown.call_args[0][0]
        self.assertIn(config["icon"], call_args)
        self.assertIn(config["title"], call_args)

    @patch("frontend.components.result_cards.st")
    def test_header_includes_timestamp(self, mock_st):
        """TC-012: 头部包含时间戳"""
        config = TASK_TYPE_CONFIG["data_analysis"]
        _render_card_header("data_analysis", config)
        call_args = mock_st.markdown.call_args[0][0]
        self.assertNotIn("🕐", call_args)
        self.assertIn("2026-", call_args)


class TestRenderMetadataBar(unittest.TestCase):
    """_render_metadata_bar()元数据栏测试"""

    @patch("frontend.components.result_cards.st")
    def test_metadata_with_execution_time(self, mock_st):
        """TC-013: 显示执行时间"""
        metadata = {"execution_time_ms": 2300}
        _render_metadata_bar(metadata, {})
        mock_st.columns.assert_called()
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_metadata_with_sources_count(self, mock_st):
        """TC-014: 显示来源数量"""
        metadata = {"sources_count": 5}
        _render_metadata_bar(metadata, {})
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_metadata_with_file_size(self, mock_st):
        """TC-015: 显示文件大小"""
        record = {"size_kb": 10.5}
        _render_metadata_bar({}, record)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_metadata_with_agent_loop(self, mock_st):
        """TC-016: 显示AI增强模式标识"""
        metadata = {"agent_loop": True}
        _render_metadata_bar(metadata, {})
        call_args_list = mock_st.markdown.call_args_list
        self.assertTrue(any("AI增强" in str(call) for call in call_args_list))

    @patch("frontend.components.result_cards.st")
    def test_empty_metadata_no_render(self, mock_st):
        """TC-017: 空元数据不渲染"""
        _render_metadata_bar({}, {})
        mock_st.columns.assert_not_called()


class TestRenderActionButtons(unittest.TestCase):
    """_render_action_buttons()操作按钮测试"""

    @patch("frontend.components.result_cards.st")
    def test_download_button_for_existing_file(self, mock_st):
        """TC-018: 文件存在时显示下载按钮"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            _render_action_buttons(temp_path, "test content", ["pdf"])
            mock_st.download_button.assert_called()
        finally:
            os.unlink(temp_path)

    @patch("frontend.components.result_cards.st")
    def test_disabled_button_for_missing_file(self, mock_st):
        """TC-019: 文件不存在时禁用下载按钮"""
        _render_action_buttons("/nonexistent/path.md", "content", [])
        button_calls = [
            call for call in mock_st.button.call_args_list if "下载" in str(call)
        ]
        self.assertGreater(len(button_calls), 0)
        call_kwargs = (
            button_calls[0].kwargs if hasattr(button_calls[0], "kwargs") else {}
        )
        self.assertTrue(
            call_kwargs.get("disabled", False) or "disabled" in str(button_calls[0])
        )

    @patch("frontend.components.result_cards.st")
    def test_copy_button_present(self, mock_st):
        """TC-020: 复制按钮始终存在"""
        _render_action_buttons("/tmp/test.md", "content", ["pdf"])
        copy_calls = [
            call for call in mock_st.button.call_args_list if "复制" in str(call)
        ]
        self.assertGreater(len(copy_calls), 0)

    @patch("frontend.components.result_cards.st")
    def test_export_format_buttons(self, mock_st):
        """TC-021: 导出格式按钮正确生成"""
        formats = ["pdf", "docx", "xlsx"]
        _render_action_buttons("/tmp/test.md", "content", formats)
        format_labels = ["PDF", "Word", "Excel"]
        for label in format_labels:
            calls = [str(call) for call in mock_st.button.call_args_list]
            self.assertTrue(any(label in call for call in calls))


class TestRenderContentPreview(unittest.TestCase):
    """_render_content_preview()内容预览测试"""

    @patch("frontend.components.result_cards.st")
    def test_short_content_fully_displayed(self, mock_st):
        """TC-022: 短内容完整显示（不截断）"""
        short_content = "这是短内容" * 5
        _render_content_preview(short_content, max_chars=200)
        mock_st.markdown.assert_called_once_with(short_content)

    @patch("frontend.components.result_cards.st")
    def test_long_content_truncated(self, mock_st):
        """TC-023: 长内容截断显示"""
        long_content = "这是一段很长的内容。" * 50
        mock_st.session_state = {}
        _render_content_preview(long_content, max_chars=200)
        call_args_list = mock_st.markdown.call_args_list
        self.assertGreater(len(call_args_list), 0, "应该至少调用一次st.markdown")
        found_truncated = False
        for call in call_args_list:
            call_content = str(call[0][0]) if call[0] and len(call[0]) > 0 else ""
            if "..." in call_content and len(call_content) < len(long_content):
                found_truncated = True
                break
        self.assertTrue(
            found_truncated,
            f"应该在调用中找到截断的内容，实际调用数: {len(call_args_list)}",
        )

    @patch("frontend.components.result_cards.st")
    def test_expand_toggle_for_long_content(self, mock_st):
        """TC-024: 长内容显示展开按钮"""
        long_content = "x" * 300
        _render_content_preview(long_content, max_chars=200)
        button_calls = [str(call) for call in mock_st.button.call_args_list]
        self.assertTrue(
            any("展开" in call or "expand" in call.lower() for call in button_calls)
        )


class TestExtractDataInsights(unittest.TestCase):
    """_extract_data_insights()数据洞察提取测试"""

    def test_extract_percentages(self):
        """TC-025: 提取百分比数据"""
        content = "增长率达到25.5%，下降3.2%"
        insights = _extract_data_insights(content)
        percentage_found = any("百分比" in insight for insight in insights)
        self.assertTrue(percentage_found)
        self.assertIn("25.5%", str(insights))

    def test_extract_monetary_values(self):
        """TC-026: 提取金额数据"""
        content = "项目总预算100万元，收入5000元"
        insights = _extract_data_insights(content)
        monetary_found = any("金额" in insight for insight in insights)
        self.assertTrue(monetary_found)

    def test_extract_dates(self):
        """TC-027: 提取日期数据"""
        content = "报告日期2024-01-15，截止2024/12/31"
        insights = _extract_data_insights(content)
        date_found = any("日期" in insight for insight in insights)
        self.assertTrue(date_found)

    def test_extract_trend_words(self):
        """TC-028: 提取趋势关键词"""
        content = "数据显示明显增长，但部分指标出现下滑"
        insights = _extract_data_insights(content)
        trend_found = any("趋势" in insight for insight in insights)
        self.assertTrue(trend_found)
        self.assertTrue(
            any(
                "增长" in str(insight) or "下滑" in str(insight) for insight in insights
            )
        )

    def test_no_data_returns_empty(self):
        """TC-029: 无数据时返回空列表"""
        content = "这是一段普通文本，没有数字或数据"
        insights = _extract_data_insights(content)
        self.assertEqual(insights, [])


class TestGetTaskTypeLabel(unittest.TestCase):
    """get_task_type_label()标签获取测试"""

    def test_content_generation_label(self):
        """TC-030: 内容生成标签正确"""
        label = get_task_type_label("content_generation")
        self.assertNotIn("✍", label)
        self.assertIn("内容生成", label)

    def test_data_analysis_label(self):
        """TC-031: 数据分析标签正确"""
        label = get_task_type_label("data_analysis")
        self.assertNotIn("📊", label)
        self.assertIn("数据分析", label)

    def test_unknown_type_fallback(self):
        """TC-032: 未知类型使用默认标签"""
        label = get_task_type_label("unknown_type")
        self.assertIn("unknown_type", label)


class TestValidateDeliverableRecord(unittest.TestCase):
    """validate_deliverable_record()记录验证测试"""

    def test_valid_record(self):
        """TC-033: 有效记录通过验证"""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            record = {
                "filename": "test.md",
                "filepath": temp_path,
                "prompt": "测试",
                "task_type": "content_generation",
                "created_at": "2024-01-01",
            }
            is_valid, error = validate_deliverable_record(record)
            self.assertTrue(is_valid)
            self.assertEqual(error, "")
        finally:
            os.unlink(temp_path)

    def test_missing_required_field(self):
        """TC-034: 缺少必要字段返回错误"""
        record = {
            "filename": "test.md",
            "prompt": "测试",
        }
        is_valid, error = validate_deliverable_record(record)
        self.assertFalse(is_valid)
        self.assertIn("缺少", error)

    def test_nonexistent_file(self):
        """TC-035: 文件不存在返回错误"""
        record = {
            "filename": "test.md",
            "filepath": "/nonexistent/file.md",
            "prompt": "测试",
            "task_type": "content_generation",
            "created_at": "2024-01-01",
        }
        is_valid, error = validate_deliverable_record(record)
        self.assertFalse(is_valid)
        self.assertIn("不存在", error)

    def test_empty_task_type(self):
        """TC-036: 空task_type返回错误"""
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            temp_path = f.name

        try:
            record = {
                "filename": "test.md",
                "filepath": temp_path,
                "prompt": "测试",
                "task_type": "",
                "created_at": "2024-01-01",
            }
            is_valid, error = validate_deliverable_record(record)
            self.assertFalse(is_valid)
            self.assertIn("不能为空", error)
        finally:
            os.unlink(temp_path)


class TestEdgeCases(unittest.TestCase):
    """边界情况和异常处理测试"""

    @patch("frontend.components.result_cards.st")
    def test_unicode_content_handling(self, mock_st):
        """TC-037: Unicode内容正常处理"""
        content = "中文内容 🎉 日本語 한국어 العربية"
        render_result_card(content, "general_chat", {}, None)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_very_long_content(self, mock_st):
        """TC-038: 超长内容处理"""
        content = "测试内容。" * 1000
        render_result_card(content, "content_generation", {}, None)
        mock_st.markdown.assert_called()

    @patch("frontend.components.result_cards.st")
    def test_markdown_content_preserved(self, mock_st):
        """TC-039: Markdown格式保留"""
        content = "# 标题\n\n**粗体** *斜体* `代码`\n- 列表项1\n- 列表项2"
        render_result_card(content, "content_generation", {}, None)
        mock_st.markdown.assert_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
