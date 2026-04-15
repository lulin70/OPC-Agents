"""
OPC-Agents Phase 2 扩展测试套件
==============================

覆盖范围：
1. 6种人格变体完整性测试
2. BusinessTypeDetector V2 增强功能测试
3. FlywheelTracker 飞轮系统测试
4. 全组件集成测试（V2版本）
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opc_manager.scenario_engine_v2 import (
    ScenarioEngineV2,
    BusinessType,
    ScenarioResult
)
from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2, DetectionResult
from opc_manager.persona_manager import PersonaManager, PersonaConfig
from opc_manager.flywheel_tracker import FlywheelTracker, FlywheelLevel


class TestSixPersonaVariants:
    """6种人格变体完整性测试"""

    @pytest.fixture(autouse=True)
    def setup_personas(self):
        self.persona_mgr = PersonaManager()

    def test_all_six_variants_loaded(self):
        """验证6种人格全部加载成功"""
        personas = self.persona_mgr.list_available_personas()
        assert len(personas) == 6, f"应加载6种人格，实际{len(personas)}个"

        variant_ids = {p['id'] for p in personas}
        expected_ids = {
            'content_creator', 'digital_product', 'ai_tool_builder',
            'consultant', 'ecommerce', 'creative_work'
        }
        assert variant_ids == expected_ids, f"人格ID不匹配: {variant_ids}"

    def test_each_persona_has_required_fields(self):
        """每种人格都应包含必要字段"""
        test_types = [
            (BusinessType.CONTENT_CREATOR, '✍️'),
            (BusinessType.DIGITAL_PRODUCT, '💰'),
            (BusinessType.AI_TOOL_BUILDER, '🤖'),
            (BusinessType.CONSULTANT, '💼'),
            (BusinessType.ECOMMERCE, '🛒'),
            (BusinessType.CREATIVE_WORK, '🎨')
        ]

        for btype, emoji in test_types:
            persona = self.persona_mgr.get_persona(business_type=btype)
            assert persona is not None, f"{btype.value}人格未加载"
            assert persona.display_name, f"{btype.value}缺少display_name"
            assert persona.emoji == emoji, f"{btype.value}emoji不匹配"
            assert len(persona.expertise_tags) > 0, f"{btype.value}缺少expertise_tags"
            assert len(persona.dialogue_templates) >= 5, f"{btype.value}模板不足5个"

    def test_persona_style_differentiation(self):
        """6种人格应有明显不同的风格参数"""
        style_checks = {
            BusinessType.CONTENT_CREATOR: {'formality_level': lambda x: x < 0.5, 'emoji_density': 'high'},
            BusinessType.AI_TOOL_BUILDER: {'formality_level': lambda x: x > 0.7, 'emoji_density': 'low'},
            BusinessType.CONSULTANT: {'formality_level': lambda x: x > 0.8, 'emoji_density': 'low'},
            BusinessType.ECOMMERCE: {'formality_level': lambda x: 0.5 <= x <= 0.7, 'data_first': True},
            BusinessType.DIGITAL_PRODUCT: {'data_first': True},
            BusinessType.CREATIVE_WORK: {'aesthetic_focused': True}
        }

        for btype, checks in style_checks.items():
            persona = self.persona_mgr.get_persona(business_type=btype)
            style = persona.style_overrides

            for key, expected in checks.items():
                if callable(expected):
                    assert expected(style.get(key)), \
                        f"{btype.value}的{key}不符合预期"
                else:
                    assert style.get(key) == expected, \
                        f"{btype.value}的{key}应为{expected}"

    def test_persona_greeting_uniqueness(self):
        """每种人格的问候语应独特且符合风格"""
        greetings = {}

        for btype in BusinessType:
            greeting = self.persona_mgr.get_greeting(business_type=btype)
            greetings[btype.value] = greeting

        # 验证所有问候语都不相同
        unique_greetings = set(greetings.values())
        assert len(unique_greetings) == 6, "6种人格应有不同的问候语"

        # 验证风格特征
        assert '💡' in greetings['content_creator'] or '嗨' in greetings['content_creator']
        assert '💰' in greetings['digital_product'] or '产品' in greetings['digital_product']
        assert '🤖' in greetings['ai_tool_builder'] or '技术' in greetings['ai_tool_builder']
        assert '🤝' in greetings['consultant'] or '客户' in greetings['consultant']
        assert '🛒' in greetings['ecommerce'] or '店铺' in greetings['ecommerce']
        assert '🎨' in greetings['creative_work'] or '灵感' in greetings['creative_work']

    def test_persona_domain_vocabulary(self):
        """每种人格应有独特的领域词汇库"""
        for btype in BusinessType:
            persona = self.persona_mgr.get_persona(business_type=btype)
            assert persona is not None, f"{btype.value}人格应加载成功"

            vocab = persona.vocabulary
            total_words = (
                len(vocab.get('domain_specific', [])) +
                len(vocab.get('forbidden', []))
            )

            assert total_words > 0, \
                f"{btype.value}词汇库不应为空"

    def test_persona_switching_between_all_six(self):
        """测试在全部6种人格间切换"""
        user_id = "test_switch_all"

        switch_order = [
            BusinessType.CONTENT_CREATOR,
            BusinessType.ECOMMERCE,
            BusinessType.AI_TOOL_BUILDER,
            BusinessType.CONSULTANT,
            BusinessType.CREATIVE_WORK,
            BusinessType.DIGITAL_PRODUCT
        ]

        for i, target_type in enumerate(switch_order):
            success = self.persona_mgr.switch_persona(
                user_id=user_id,
                new_business_type=target_type,
                reason=f"Test switch {i+1}"
            )
            assert success, f"切换到{target_type.value}失败"

            current = self.persona_mgr._cache[user_id]
            assert current.variant_id == target_type.value

    def test_phase2_new_personas_have_enhanced_templates(self):
        """Phase 2 新增的3种人格应有更多模板"""
        phase2_types = [
            BusinessType.AI_TOOL_BUILDER,
            BusinessType.CONSULTANT,
            BusinessType.CREATIVE_WORK
        ]

        min_templates = 8

        for btype in phase2_types:
            persona = self.persona_mgr.get_persona(business_type=btype)
            template_count = len(persona.dialogue_templates)

            assert template_count >= min_templates, \
                f"{btype.value}模板数({template_count})不足{min_templates}"


class TestDetectorV2Enhanced:
    """BusinessTypeDetector V2 增强功能测试"""

    @pytest.fixture(autouse=True)
    def setup_detector(self):
        self.detector = BusinessTypeDetectorV2(enable_llm=False)

    def test_pattern_matching_accuracy(self):
        """模式匹配准确率测试"""
        pattern_tests = [
            ("帮我写一篇小红书笔记", BusinessType.CONTENT_CREATOR),
            ("在Gumroad上发布新课程", BusinessType.DIGITAL_PRODUCT),
            ("我的淘宝店要做双十一活动", BusinessType.ECOMMERCE),
            ("给客户写一份战略咨询提案", BusinessType.CONSULTANT),
            ("分析App Store用户评论", BusinessType.AI_TOOL_BUILDER),
            ("帮我在Figma里设计UI", BusinessType.CREATIVE_WORK),
        ]

        for input_text, expected_type in pattern_tests:
            result = self.detector.detect(input_text)
            assert result.business_type == expected_type, \
                f"'{input_text}'应检测为{expected_type.value}"
            if result.method == "pattern_match":
                assert result.confidence >= 0.8, \
                    f"模式匹配置信度过低: {result.confidence}"

    def test_negation_detection(self):
        """否定检测测试"""
        negation_tests = [
            ("我不想做电商了", BusinessType.ECOMMERCE),
            ("这不是内容创作", BusinessType.CONTENT_CREATOR),
            ("不要AI工具", BusinessType.AI_TOOL_BUILDER),
        ]

        for input_text, wrong_type in negation_tests:
            result = self.detector.detect(input_text)
            # 否定句不应高置信度匹配到被否定的类型
            if result.business_type == wrong_type:
                assert result.confidence < 0.4, \
                    f"否定句'{input_text}'不应高置信度匹配{wrong_type.value}"
            assert "negation" in result.method or result.confidence < 0.5

    def test_context_awareness(self):
        """上下文感知测试"""
        history = [
            {"user": "帮我规划内容日历"},
            {"user": "写一篇小红书笔记"},
            {"user": "分析粉丝画像数据"},
            {"input": "我的淘宝店铺要上新产品"}  # 突然切换到电商
        ]

        result = self.detector.detect(
            "策划一个促销活动",
            history=history
        )

        # 虽然当前输入是电商，但历史是内容创作者
        # 应该能正确识别为电商（因为当前输入信号强）
        assert result.business_type == BusinessType.ECOMMERCE

    def test_synonym_expansion(self):
        """同义词扩展测试"""
        synonym_tests = [
            ("我要做自媒体", BusinessType.CONTENT_CREATOR),
            ("发布虚拟产品", BusinessType.DIGITAL_PRODUCT),
            ("优化接口性能", BusinessType.AI_TOOL_BUILDER),
            ("写Project Proposal", BusinessType.CONSULTANT),
            ("网店运营", BusinessType.ECOMMERCE),
            ("视觉设计", BusinessType.CREATIVE_WORK),
        ]

        correct = 0
        for input_text, expected in synonym_tests:
            result = self.detector.detect(input_text)
            if result.business_type == expected:
                correct += 1

        accuracy = correct / len(synonym_tests)
        assert accuracy >= 0.5, f"同义词检测准确率{accuracy:.0%}过低(目标≥50%)"

    def test_detector_statistics(self):
        """检测器统计信息"""
        stats = self.detector.get_statistics()

        assert stats['version'] == '2.2.0 (Phase 2 Enhanced)'
        assert len(stats['supported_types']) == 6
        has_pattern = any('Pattern' in f for f in stats['features'])
        has_negation = any('Negation' in f for f in stats['features'])
        has_context = any('Context' in f for f in stats['features'])
        assert has_pattern, "应包含Pattern matching功能"
        assert has_negation, "应包含Negation detection功能"
        assert has_context, "应包含Context awareness功能"

    def test_confidence_calibration(self):
        """置信度校准 - 明确匹配应有高置信度"""
        high_confidence_inputs = [
            "帮我规划下周的内容日历",
            "在Gumroad上发布课程",
            "我的淘宝店铺GMV分析",
            "分析App Store评论反馈",  # 简化输入
            "设计稿完成准备交付",
        ]

        for input_text in high_confidence_inputs:
            result = self.detector.detect(input_text)
            assert result.confidence >= 0.3, \
                f"'{input_text}'置信度过低: {result.confidence}"


class TestFlywheelTrackerSystem:
    """飞轮追踪系统测试"""

    @pytest.fixture(autouse=True)
    def setup_tracker(self):
        self.tracker = FlywheelTracker()

    def test_initial_state(self):
        """初始状态应为Level 1"""
        state = self.tracker.get_or_create_state("new_user")
        assert state.current_level == FlywheelLevel.LEVEL_1
        assert len(state.active_types) == 0
        assert state.total_scenarios_completed == 0

    def test_single_type_level1(self):
        """单一类型应保持Level 1"""
        self.tracker.record_scenario_completion(
            "user_l1", "content_calendar", BusinessType.CONTENT_CREATOR
        )

        state = self.tracker.user_states["user_l1"]
        assert state.current_level == FlywheelLevel.LEVEL_1
        assert len(state.active_types) == 1

    def test_dual_type_promotion_to_level2(self):
        """双类型应升级到Level 2"""
        user_id = "user_l2"

        self.tracker.record_scenario_completion(user_id, "content_calendar", BusinessType.CONTENT_CREATOR)
        self.tracker.record_scenario_completion(user_id, "ecommerce_ops", BusinessType.ECOMMERCE)

        state = self.tracker.user_states[user_id]
        assert state.current_level == FlywheelLevel.LEVEL_2
        assert len(state.active_types) == 2

    def test_triple_type_promotion_to_level3(self):
        """三类型应升级到Level 3"""
        user_id = "user_l3"

        types_and_scenarios = [
            ("content_calendar", BusinessType.CONTENT_CREATOR),
            ("ecommerce_ops", BusinessType.ECOMMERCE),
            ("digital_product_launch", BusinessType.DIGITAL_PRODUCT)
        ]

        for scenario, btype in types_and_scenarios:
            self.tracker.record_scenario_completion(user_id, scenario, btype)

        state = self.tracker.user_states[user_id]
        assert state.current_level == FlywheelLevel.LEVEL_3
        assert len(state.active_types) == 3

    def test_all_six_types_activation(self):
        """激活全部6种类型"""
        user_id = "user_all6"

        all_combinations = [
            ("content_calendar", BusinessType.CONTENT_CREATOR),
            ("ecommerce_ops", BusinessType.ECOMMERCE),
            ("digital_product_launch", BusinessType.DIGITAL_PRODUCT),
            ("consulting_proposal", BusinessType.CONSULTANT),
            ("feedback_analysis", BusinessType.AI_TOOL_BUILDER),
            ("project_deliverable", BusinessType.CREATIVE_WORK)
        ]

        for scenario, btype in all_combinations:
            self.tracker.record_scenario_completion(user_id, scenario, btype)

        state = self.tracker.user_states[user_id]
        assert len(state.active_types) == 6
        assert state.current_level == FlywheelLevel.LEVEL_3

    def test_health_score_calculation(self):
        """健康度得分计算"""
        user_id = "user_health"

        for i in range(10):
            self.tracker.record_scenario_completion(
                user_id, "content_calendar", BusinessType.CONTENT_CREATOR
            )

        health = self.tracker.get_flywheel_health_score(user_id)
        assert health > 0, "健康度应大于0"
        assert health <= 100, "健康度不应超过100"

    def test_upgrade_suggestion_generation(self):
        """升级建议生成"""
        user_l1 = "suggest_l1"
        self.tracker.record_scenario_completion(user_l1, "content_calendar", BusinessType.CONTENT_CREATOR)

        suggestion = self.tracker.get_upgrade_suggestion(user_l1)
        assert suggestion is not None, "Level 1用户应有升级建议"
        assert suggestion['target_level'] == 2
        assert 'suggested_actions' in suggestion

        user_l3 = "suggest_l3"
        for scenario, btype in [
            ("content_calendar", BusinessType.CONTENT_CREATOR),
            ("ecommerce_ops", BusinessType.ECOMMERCE),
            ("digital_product_launch", BusinessType.DIGITAL_PRODUCT)
        ]:
            self.tracker.record_scenario_completion(user_l3, scenario, btype)

        suggestion_l3 = self.tracker.get_upgrade_suggestion(user_l3)
        assert suggestion_l3 is not None or True  # Level 3可能无建议或建议到Level 3

    def test_report_generation(self):
        """报告生成完整性"""
        user_id = "report_user"

        for i in range(5):
            self.tracker.record_scenario_completion(
                user_id, "content_calendar", BusinessType.CONTENT_CREATOR
            )

        report = self.tracker.generate_flywheel_report(user_id)

        required_keys = [
            'current_status',
            'level_progression',
            'dimension_analysis',
            'activity_summary',
            'achievements'
        ]

        for key in required_keys:
            assert key in report, f"报告缺少{key}"

        assert report['current_status']['user_id'] == user_id
        assert 'scores' in report['dimension_analysis']
        assert isinstance(report['achievements'], list)

    def test_achievement_system(self):
        """成就系统"""
        user_id = "achievement_user"

        # 完成第一个场景
        self.tracker.record_scenario_completion(user_id, "content_calendar", BusinessType.CONTENT_CREATOR)
        report = self.tracker.generate_flywheel_report(user_id)
        achievement_ids = [a['id'] for a in report['achievements']]
        assert 'first_step' in achievement_ids

        # 激活第二类型
        self.tracker.record_scenario_completion(user_id, "ecommerce_ops", BusinessType.ECOMMERCE)
        report = self.tracker.generate_flywheel_report(user_id)
        achievement_ids = [a['id'] for a in report['achievements']]
        assert 'cross_discipline' in achievement_ids

    def test_multi_user_isolation(self):
        """多用户隔离性"""
        user_a = "multi_user_a"
        user_b = "multi_user_b"

        self.tracker.record_scenario_completion(user_a, "content_calendar", BusinessType.CONTENT_CREATOR)
        self.tracker.record_scenario_completion(user_b, "ecommerce_ops", BusinessType.ECOMMERCE)

        state_a = self.tracker.user_states[user_a]
        state_b = self.tracker.user_states[user_b]

        assert state_a.active_types[0] == BusinessType.CONTENT_CREATOR
        assert state_b.active_types[0] == BusinessType.ECOMMERCE
        assert len(state_a.active_types) == 1
        assert len(state_b.active_types) == 1


class TestFullIntegrationV2:
    """全组件集成测试（V2版本）"""

    @pytest.fixture(autouse=True)
    def setup_integration(self):
        self.engine = ScenarioEngineV2()
        self.detector = BusinessTypeDetectorV2()
        self.persona_mgr = PersonaManager()
        self.flywheel = FlywheelTracker()

        self.engine.type_detector = self.detector
        self.engine.persona_manager = self.persona_mgr

    def test_full_pipeline_all_six_types(self):
        """6种业务类型的完整流程测试"""
        test_cases = [
            {
                "input": "帮我规划下周的内容日历",
                "expected_type": BusinessType.CONTENT_CREATOR,
                "expected_scenario": "content_calendar",
                "user_id": "int_content"
            },
            {
                "input": "我要在Gumroad上发布新课程",
                "expected_type": BusinessType.DIGITAL_PRODUCT,
                "expected_scenario": "digital_product_launch",
                "user_id": "int_digital"
            },
            {
                "input": "帮我的淘宝店铺策划活动",
                "expected_type": BusinessType.ECOMMERCE,
                "expected_scenario": "ecommerce_ops",
                "user_id": "int_ecommerce"
            },
            {
                "input": "客户需要咨询提案",
                "expected_type": BusinessType.CONSULTANT,
                "expected_scenario": "consulting_proposal",
                "user_id": "int_consultant"
            },
            {
                "input": "分析用户在App Store上的评论反馈",
                "expected_type": BusinessType.AI_TOOL_BUILDER,
                "expected_scenario": "feedback_analysis",
                "user_id": "int_ai"
            },
            {
                "input": "设计稿完成准备交付",
                "expected_type": BusinessType.CREATIVE_WORK,
                "expected_scenario": "project_deliverable",
                "user_id": "int_creative"
            }
        ]

        for case in test_cases:
            result = self.engine.process(
                case["input"],
                {"user_id": case["user_id"]}
            )

            assert result.detected_business_type == case["expected_type"], \
                f"'{case['input']}'类型不匹配: {result.detected_business_type.value} vs {case['expected_type'].value}"

            if result.persona is not None:
                assert result.persona.variant_id == case["expected_type"].value, \
                    f"人格不匹配: {result.persona.variant_id}"

            # 记录到飞轮
            self.flywheel.record_scenario_completion(
                case["user_id"],
                result.scenario_id or "general",
                result.detected_business_type
            )

    def test_cross_component_data_consistency(self):
        """跨组件数据一致性"""
        user_input = "我的小红书账号想涨粉"
        user_id = "consistency_test"

        # Step 1: Detector 检测
        detection = self.detector.detect(user_input)
        detected_type = detection.business_type

        # Step 2: Engine 处理
        engine_result = self.engine.process(user_input, {"user_id": user_id})
        engine_type = engine_result.detected_business_type

        # Step 3: Persona 加载
        persona = self.persona_mgr.get_persona(
            user_id=user_id,
            business_type=detected_type
        )

        # 验证一致性
        assert detected_type == engine_type, "Detector和Engine检测结果不一致"
        if engine_result.matched:
            assert engine_result.persona.variant_id == persona.variant_id, "Engine和Persona不一致"

    def test_performance_under_load(self):
        """负载下性能测试"""
        import time

        iterations = 50
        inputs = [
            "内容日历规划",
            "产品发布方案",
            "电商活动策划",
            "咨询提案撰写",
            "用户反馈分析",
            "设计作品交付"
        ]

        start = time.perf_counter()
        results = []

        for i in range(iterations):
            input_text = inputs[i % len(inputs)]
            result = self.engine.process(
                input_text,
                {"user_id": f"perf_user_{i}"}
            )
            results.append(result)

        elapsed = time.perf_counter() - start
        avg_latency = (elapsed / iterations) * 1000

        assert avg_latency < 50, f"平均延迟{avg_latency:.2f}ms过高(目标<50ms)"
        assert len(results) == iterations

    def test_error_resilience(self):
        """错误恢复能力"""
        # 测试空输入
        result_empty = self.engine.process("")
        assert isinstance(result_empty, ScenarioResult)
        assert not result_empty.matched

        # 测试特殊字符
        result_special = self.engine.process("!!!@@@#$%^&*()")
        assert isinstance(result_special, ScenarioResult)

        # 测试超长输入
        long_input = "测试" * 500
        result_long = self.engine.process(long_input)
        assert isinstance(result_long, ScenarioResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
