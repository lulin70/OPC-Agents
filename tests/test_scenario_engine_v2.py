"""
场景引擎 V2 单元测试 - content_calendar 场景专项测试

基于 TEST_PLAN_V21.md 的测试策略
使用 pytest 框架
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opc_manager.scenario_engine_v2 import (
    ScenarioEngineV2,
    BusinessType,
    ScenarioConfig,
    WorkflowStep,
    ScenarioResult
)
from opc_manager.business_type_detector import (
    BusinessTypeDetector,
    DetectionResult
)


class TestContentCalendarScenario:
    """content_calendar 场景的完整测试套件"""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        """每个测试前初始化引擎"""
        self.engine = ScenarioEngineV2()
        self.detector = BusinessTypeDetector()

    def test_scenario_exists(self):
        """测试1: 验证content_calendar场景已注册"""
        scenario = self.engine.get_scenario("content_calendar")

        assert scenario is not None, "content_calendar场景应该存在"
        assert isinstance(scenario, ScenarioConfig)
        assert scenario.id == "content_calendar"
        assert scenario.name == "内容日历规划"

    def test_scenario_target_type(self):
        """测试2: 验证目标业务类型为内容创作者"""
        scenario = self.engine.get_scenario("content_calendar")

        assert len(scenario.target_business_types) == 1
        assert BusinessType.CONTENT_CREATOR in scenario.target_business_types

    def test_workflow_steps_count(self):
        """测试3: 验证工作流步骤数量（应为5步）"""
        scenario = self.engine.get_scenario("content_calendar")

        assert len(scenario.workflow_steps) == 5, \
            f"预期5个工作流步骤，实际{len(scenario.workflow_steps)}步"

    def test_workflow_step_details(self):
        """测试4: 验证工作流步骤的详细信息"""
        scenario = self.engine.get_scenario("content_calendar")
        steps = scenario.workflow_steps

        expected_steps = [
            (1, "热点扫描", "data_collection"),
            (2, "画像匹配", "analysis"),
            (3, "选题生成", "generation"),
            (4, "日历排期", "scheduling"),
            (5, "输出整理", "formatting")
        ]

        for i, (expected_id, expected_name, expected_type) in enumerate(expected_steps):
            step = steps[i]
            assert step.step_id == expected_id, f"步骤{i+1} ID不匹配"
            assert step.name == expected_name, f"步骤{i+1} 名称不匹配"
            assert step.type == expected_type, f"步骤{i+1} 类型不匹配"
            assert step.executor != "", f"步骤{i+1} 缺少执行器"

    def test_trigger_phrases_match_exact(self):
        """测试5: 精确匹配触发短语"""
        exact_matches = [
            "帮我规划下周的内容日历",
            "我想做个选题计划",
            "内容排期怎么做",
            "下周发什么内容好",
            "帮我策划内容发布计划"
        ]

        for input_text in exact_matches:
            result = self.engine.process(
                input_text,
                {"user_id": "test_user", "preferred_business_type": "content_creator"}
            )

            assert result.matched, \
                f"输入'{input_text}'应该匹配到content_calendar场景"

            if result.matched:
                assert result.scenario_id == "content_calendar", \
                    f"输入'{input_text}'应匹配到content_calendar，实际匹配到{result.scenario_id}"

    def test_trigger_phrases_partial_match(self):
        """测试6: 部分关键词匹配"""
        partial_matches = [
            "内容日历",
            "选题建议",
            "发布计划",
            "爆款选题"
        ]

        for input_text in partial_matches:
            result = self.engine.process(input_text)

            assert result.matched or result.confidence > 0, \
                f"输入'{input_text}'应该有较高的匹配置信度"

    def test_confidence_scoring_high(self):
        """测试7: 高置信度输入（>0.8）"""
        high_confidence_inputs = [
            "帮我规划下周的内容日历，要考虑粉丝画像",
            "内容创作者的选题日历怎么安排",
            "我需要一份完整的内容排期表"
        ]

        for input_text in high_confidence_inputs:
            result = self.engine.process(input_text)

            if result.matched and result.scenario_id == "content_calendar":
                assert result.confidence >= 0.8, \
                    f"输入'{input_text}'应有高置信度(>=0.8)，实际{result.confidence:.2f}"

    def test_business_type_detection_integration(self):
        """测试8: 业务类型检测与场景路由集成"""
        test_cases = [
            ("我的小红书账号想规划下周内容", "content_creator"),
            ("帮我想几个抖音选题", "content_creator"),
            ("公众号下周发什么", "content_creator"),
        ]

        for input_text, expected_type in test_cases:
            detection_result = self.detector.detect(input_text)

            assert detection_result.business_type.value == expected_type, \
                f"输入'{input_text}'应检测为{expected_type}，" \
                f"实际为{detection_result.business_type.value}"

            assert detection_result.confidence > 0.15, \
                f"输入'{input_text}'的检测置信度过低: {detection_result.confidence:.3f}"

    def test_deliverable_template_structure(self):
        """测试9: 验证交付物模板结构"""
        scenario = self.engine.get_scenario("content_calendar")
        template = scenario.deliverable_template

        assert template.name == "周内容日历"
        assert len(template.sections) == 4
        assert "选题清单" in template.sections
        assert "发布时间表" in template.sections
        assert "素材准备清单" in template.sections
        assert "效果预估" in template.sections

    def test_output_specifications(self):
        """测试10: 验证各步骤的输出规范"""
        scenario = self.engine.get_scenario("content_calendar")
        steps = scenario.workflow_steps

        output_specs = {
            1: ("热点话题库", "JSON"),
            2: ("筛选后选题池", "List"),
            3: ("选题清单", "Table"),
            4: ("内容日历", "Calendar/Excel"),
            5: ("最终交付物", "Multi-format")
        }

        for step in steps:
            expected_name, expected_format = output_specs[step.step_id]
            assert step.output_spec is not None, \
                f"步骤{step.step_id}缺少输出规范"
            assert step.output_spec.name == expected_name, \
                f"步骤{step.step_id}输出名称应为{expected_name}"
            assert expected_format in step.output_spec.format, \
                f"步骤{step.step_id}输出格式应包含{expected_format}"

    def test_dependency_chain_valid(self):
        """测试11: 验证工作流依赖链有效性"""
        scenario = self.engine.get_scenario("content_calendar")
        steps = scenario.workflow_steps

        step_map = {step.step_id: step for step in steps}

        for step in steps:
            for dep_id in step.dependencies:
                assert dep_id in step_map, \
                    f"步骤{step.step_id}依赖了不存在的步骤{dep_id}"
                assert dep_id < step.step_id, \
                    f"步骤{step.step_id}不能依赖后续步骤{dep_id}"

        assert steps[0].dependencies == [], \
            "第一步不应有依赖"

    def test_scenario_not_matching_other_types(self):
        """测试12: 非目标业务类型不应高置信匹配"""
        other_type_inputs = [
            ("我要在淘宝上做个活动", BusinessType.ECOMMERCE),
            ("发布一个新课程到Gumroad", BusinessType.DIGITAL_PRODUCT),
            ("分析App Store用户评论", BusinessType.AI_TOOL_BUILDER),
        ]

        for input_text, wrong_type in other_type_inputs:
            context = {
                "user_id": "test_user",
                "preferred_business_type": wrong_type.value
            }
            result = self.engine.process(input_text, context)

            if result.matched:
                assert result.scenario_id != "content_calendar", \
                    f"{wrong_type.value}类型的输入'{input_text}'不应匹配content_calendar"

    def test_edge_case_empty_input(self):
        """测试13: 边界情况 - 空输入"""
        result = self.engine.process("")

        assert not result.matched, "空输入不应匹配任何场景"
        assert result.suggestion is not None, "未匹配时应提供建议"

    def test_edge_case_very_long_input(self):
        """测试14: 边界情况 - 超长输入"""
        long_input = "内容日历" * 100

        result = self.engine.process(long_input)

        assert isinstance(result, ScenarioResult), "超长输入应正常返回结果"

    def test_special_characters_handling(self):
        """测试15: 特殊字符处理"""
        special_inputs = [
            "帮我规划下周的内容日历！@#$%",
            "内容日历？选题《》【】",
            "Hello! 帮我做content calendar 📅"
        ]

        for input_text in special_inputs:
            try:
                result = self.engine.process(input_text)
                assert isinstance(result, ScenarioResult)
            except Exception as e:
                pytest.fail(f"特殊字符输入导致异常: {e}")

    def test_multiple_candidates_returned(self):
        """测试16: 返回多个候选场景"""
        result = self.engine.process(
            "帮我规划下周的内容日历",
            {"user_id": "test_user"}
        )

        if result.matched:
            assert hasattr(result, 'candidates'), "结果应包含候选列表"
            assert isinstance(result.candidates, list), "候选列表应为list类型"
            assert len(result.candidates) <= 3, "候选数不应超过3个"

            if result.candidates:
                first_candidate = result.candidates[0]
                assert 'scenario_id' in first_candidate
                assert 'confidence' in first_candidate

    def test_result_to_dict_conversion(self):
        """测试17: ScenarioResult.to_dict() 方法"""
        result = self.engine.process(
            "帮我做内容日历",
            {"user_id": "test_user_001"}
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert 'matched' in result_dict
        assert 'confidence' in result_dict

        if result.matched:
            assert 'scenario_id' in result_dict
            assert 'workflow' in result_dict
            assert isinstance(result_dict['workflow'], list)
        else:
            assert 'suggestion' in result_dict

    def test_list_scenarios_filter_by_type(self):
        """测试18: 按业务类型过滤场景列表"""
        content_scenarios = self.engine.list_scenarios(
            business_type=BusinessType.CONTENT_CREATOR
        )

        assert len(content_scenarios) > 0, "内容创作者应有可用场景"

        scenario_ids = [s['id'] for s in content_scenarios]
        assert 'content_calendar' in scenario_ids, \
            "过滤结果应包含content_calendar"

        for scenario in content_scenarios:
            assert 'content_creator' in scenario['target_business_types'], \
                f"场景{scenario['id']}不属于内容创作者类型"

    def test_engine_statistics(self):
        """测试19: 引擎统计信息"""
        stats = self.engine.get_statistics()

        assert 'total_scenarios' in stats
        assert stats['total_scenarios'] == 9, \
            f"总场景数应为9，实际{stats['total_scenarios']}"

        assert 'business_types_supported' in stats
        assert len(stats['business_types_supported']) == 6, \
            "应支持6种业务类型"

        assert 'version' in stats
        assert stats['version'] == '2.1.0'

    def test_concurrent_processing_safety(self):
        """测试20: 并发处理安全性（基础验证）"""
        import threading
        results = []
        errors = []

        def process_input(input_text):
            try:
                result = self.engine.process(input_text)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        test_inputs = [
            "内容日历规划",
            "选题建议",
            "发布计划",
            "下周内容安排"
        ]

        for input_text in test_inputs:
            t = threading.Thread(target=process_input, args=(input_text,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"并发处理出现错误: {errors}"
        assert len(results) == 4, f"并发处理结果数应为4，实际{len(results)}"


class TestBusinessTypeDetectorForContent:
    """针对内容创作类型的业务检测器专项测试"""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        self.detector = BusinessTypeDetector()

    def test_content_creator_keywords_detection(self):
        """检测内容创作者特征关键词"""
        content_inputs = [
            ("粉丝画像分析", ["粉丝"]),
            ("爆款选题推荐", ["爆款", "选题"]),
            ("完播率和互动率", ["完播率", "互动率"]),
            ("小红书涨粉技巧", ["小红书", "涨粉"]),
            ("多平台内容分发", ["平台", "内容"]),
        ]

        for input_text, expected_keywords in content_inputs:
            result = self.detector.detect(input_text)

            assert result.business_type.value == "content_creator", \
                f"'{input_text}'应被识别为内容创作者，实际为{result.business_type.value}"

            for kw in expected_keywords:
                assert kw in result.matched_keywords, \
                    f"应命中关键词'{kw}'，实际命中: {result.matched_keywords}"

    def test_confidence_score_distribution(self):
        """验证置信度分数分布合理性"""
        test_cases = [
            ("你好", 0.0, 0.25),
            ("内容", 0.15, 0.5),
            ("内容日历", 0.2, 0.5),
            ("帮我规划下周的内容日历，考虑粉丝画像", 0.5, 1.0),
        ]

        for input_text, min_score, max_score in test_cases:
            result = self.detector.detect(input_text)

            assert min_score <= result.confidence <= max_score, \
                f"'{input_text}'置信度{result.confidence:.3f}不在[{min_score}, {max_score}]范围内"

    def test_alternative_types_provided(self):
        """验证备选类型列表"""
        result = self.detector.detect("帮我写报告")

        assert hasattr(result, 'alternative_types')
        assert isinstance(result.alternative_types, list)

        if result.alternative_types:
            for alt_type, alt_score in result.alternative_types:
                assert isinstance(alt_type, BusinessType)
                assert 0 <= alt_score <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
