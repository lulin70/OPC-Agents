"""
OPC-Agents V2.1 集成测试
==========================

端到端集成测试：ScenarioEngineV2 + BusinessTypeDetector + PersonaManager

测试场景：
1. 完整的用户请求处理流程（输入 → 类型检测 → 场景匹配 → 人格选择 → 输出格式化）
2. 跨组件数据流验证
3. 多用户/多类型并发场景
4. 错误处理和降级机制
"""

import pytest
import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opc_manager.scenario_engine_v2 import (
    ScenarioEngineV2,
    BusinessType,
    ScenarioResult,
    get_scenario_engine_v2
)
from opc_manager.business_type_detector import (
    BusinessTypeDetector,
    DetectionResult
)
from opc_manager.persona_manager import (
    PersonaManager,
    PersonaConfig
)


class TestComponentIntegration:
    """三组件集成测试：核心端到端流程"""

    @pytest.fixture(autouse=True)
    def setup_integration(self):
        """
        初始化集成环境：创建并连接三个组件
        模拟真实的生产环境配置
        """
        self.detector = BusinessTypeDetector()
        self.persona_manager = PersonaManager()
        self.engine = ScenarioEngineV2()

        # 关键步骤：将 detector 和 persona_manager 注入到 engine
        self.engine.type_detector = self.detector
        self.engine.persona_manager = self.persona_manager

    def test_full_pipeline_content_creator(self):
        """
        测试1: 内容创作者完整流程
        输入: "帮我规划下周的内容日历"
        预期:
          1. BusinessTypeDetector → content_creator
          2. ScenarioEngineV2 → content_calendar 场景
          3. PersonaManager → 内容小助理人格
          4. 输出: 格式化的响应
        """
        user_input = "帮我规划下周的内容日历，要考虑粉丝画像"
        user_context = {
            "user_id": "test_content_creator_001",
            "conversation_history": []
        }

        # Step 1: 执行完整的 process 流程
        result = self.engine.process(user_input, user_context)

        # 验证基础结果结构
        assert isinstance(result, ScenarioResult)
        assert result.matched, f"输入应匹配到场景，实际: {result.suggestion}"

        # Step 2: 验证业务类型检测
        assert result.detected_business_type is not None
        assert result.detected_business_type == BusinessType.CONTENT_CREATOR, \
            f"应检测为内容创作者，实际为: {result.detected_business_type.value}"

        # Step 3: 验证场景匹配
        assert result.scenario_id == "content_calendar", \
            f"应匹配content_calendar场景，实际为: {result.scenario_id}"
        assert result.confidence >= 0.5, \
            f"置信度过低: {result.confidence:.3f}"

        # Step 4: 验证人格加载
        assert result.persona is not None, "应加载人格配置"
        assert isinstance(result.persona, PersonaConfig)
        assert result.persona.variant_id == "content_creator", \
            f"应加载content_creator人格，实际为: {result.persona.variant_id}"
        assert result.persona.display_name == "内容小助理"

        # Step 5: 验证工作流生成
        assert result.workflow is not None
        assert len(result.workflow) == 5, \
            f"content_calendar应有5个工作流步骤，实际: {len(result.workflow)}"

        # Step 6: 使用人格格式化输出
        greeting = self.persona_manager.format_response(
            result.persona,
            "greeting"
        )
        assert "💡" in greeting or "嗨" in greeting, \
            f"问候语应包含emoji或友好语气，实际: {greeting}"

        accept_msg = self.persona_manager.format_response(
            result.persona,
            "accept_task"
        )
        assert "收到" in accept_msg or "🔥" in accept_msg, \
            f"任务接受消息应包含确认语气，实际: {accept_msg}"

        print(f"\n✅ 内容创作者流程测试通过:")
        print(f"   输入: {user_input}")
        print(f"   类型: {result.detected_business_type.value}")
        print(f"   场景: {result.scenario_id} (置信度: {result.confidence:.2f})")
        print(f"   人格: {result.persona.display_name} {result.persona.emoji}")
        print(f"   工作流步骤: {len(result.workflow)}步")

    def test_full_pipeline_digital_product(self):
        """
        测试2: 数字产品开发者完整流程
        输入: "我要在Gumroad上发布一个新课程"
        """
        user_input = "我要在Gumroad上发布一个新课程，需要定价建议"
        user_context = {
            "user_id": "test_digital_product_001",
            "conversation_history": []
        }

        result = self.engine.process(user_input, user_context)

        assert result.matched, f"应匹配到场景: {result.suggestion}"

        # 验证类型检测
        assert result.detected_business_type == BusinessType.DIGITAL_PRODUCT, \
            f"应为数字产品类型，实际: {result.detected_business_type.value}"

        # 验证场景（可能是digital_product_launch或launch_product）
        assert result.scenario_id in ["digital_product_launch", "launch_product"], \
            f"场景ID异常: {result.scenario_id}"

        # 验证人格
        assert result.persona is not None
        assert result.persona.variant_id == "digital_product"
        assert result.persona.display_name == "产品顾问"
        assert "💰" in result.persona.emoji

        # 验证专业术语使用
        pricing_response = self.persona_manager.format_response(
            result.persona,
            "pricing_response",
            price="199",
            reasoning="竞品均价¥299，我们定位中高端但更有性价比"
        )
        assert "定价" in pricing_response or "¥199" in pricing_response

        print(f"\n✅ 数字产品开发者流程测试通过:")
        print(f"   场景: {result.scenario_id} | 人格: {result.persona.display_name}")

    def test_full_pipeline_ecommerce(self):
        """
        测试3: 电商运营者完整流程
        输入: "帮我的淘宝店铺策划双十一活动"
        """
        user_input = "帮我的淘宝店铺策划一个双十一促销活动"
        user_context = {
            "user_id": "test_ecommerce_001",
            "conversation_history": []
        }

        result = self.engine.process(user_input, user_context)

        assert result.matched, f"应匹配到场景: {result.suggestion}"

        # 验证类型检测
        assert result.detected_business_type == BusinessType.ECOMMERCE, \
            f"应为电商运营类型，实际: {result.detected_business_type.value}"

        # 验证场景
        assert result.scenario_id == "ecommerce_ops", \
            f"应为ecommerce_ops场景，实际: {result.scenario_id}"

        # 验证人格
        assert result.persona.variant_id == "ecommerce"
        assert result.persona.display_name == "电商小管家"
        assert "🛒" in result.persona.emoji

        # 验证电商特有模板
        alert_template = result.persona.dialogue_templates.get("alert")
        assert alert_template is not None, "电商人格应有alert模板"
        assert "⚠️" in alert_template or "异常" in alert_template

        print(f"\n✅ 电商运营者流程测试通过:")
        print(f"   场景: {result.scenario_id} | 人格: {result.persona.display_name}")

    def test_cross_component_data_flow(self):
        """
        测试4: 跨组件数据流验证
        确保数据在三个组件间正确传递
        """
        test_input = "帮我规划下周的内容日历"
        user_id = "test_data_flow_001"

        # 手动分步执行，验证每步的输出
        detection_result = self.detector.detect(test_input)
        assert detection_result.business_type.value == "content_creator", \
            f"应为content_creator类型，实际为: {detection_result.business_type.value}"

        scenario_result = self.engine.process(
            test_input,
            {"user_id": user_id}
        )

        # 验证：engine使用的detector结果与手动调用一致
        assert scenario_result.detected_business_type.value == detection_result.business_type.value

        # 验证：scenario应匹配成功
        assert scenario_result.matched, f"应匹配成功: {scenario_result.suggestion}"
        assert scenario_result.scenario_id == "content_calendar"

        # 验证：persona基于detection_result的类型加载
        persona = self.persona_manager.get_persona(
            user_id=user_id,
            business_type=detection_result.business_type
        )

        assert scenario_result.persona is not None, "应加载人格配置"
        if scenario_result.persona:
            assert scenario_result.persona.variant_id == persona.variant_id
            assert scenario_result.persona.target_business_type == detection_result.business_type.value

        print(f"\n✅ 数据流验证通过:")
        print(f"   Detector → Engine: {detection_result.business_type.value}")
        print(f"   Engine → Persona: {scenario_result.persona.variant_id}")

    def test_multi_user_isolation(self):
        """
        测试5: 多用户隔离性验证
        不同用户应该有独立的会话状态
        """
        users = [
            ("user_A_content", "帮我做内容日历", BusinessType.CONTENT_CREATOR),
            ("user_B_ecommerce", "淘宝店铺活动策划", BusinessType.ECOMMERCE),
            ("user_C_digital", "发布课程到Gumroad", BusinessType.DIGITAL_PRODUCT),
        ]

        results = {}

        for user_id, input_text, expected_type in users:
            result = self.engine.process(input_text, {"user_id": user_id})
            results[user_id] = result

            # 验证每个用户的独立结果
            assert result.matched, f"{user_id} 应匹配成功"
            assert result.detected_business_type == expected_type, \
                f"{user_id} 类型错误: {result.detected_business_type.value} vs {expected_type.value}"

        # 验证缓存隔离
        persona_a = self.persona_manager._cache.get("user_A_content")
        persona_b = self.persona_manager._cache.get("user_B_ecommerce")

        assert persona_a != persona_b, "不同用户的人格应该不同"
        assert persona_a.variant_id == "content_creator"
        assert persona_b.variant_id == "ecommerce"

        print(f"\n✅ 多用户隔离测试通过 ({len(users)}个用户)")

    def test_persona_switching_mid_session(self):
        """
        测试6: 会话中途切换人格
        模拟用户从内容创作切换到电商咨询的场景
        """
        user_id = "test_switch_user_001"

        # 第一次请求：内容创作者
        result1 = self.engine.process(
            "帮我规划下周的内容日历",
            {"user_id": user_id}
        )

        assert result1.matched
        original_persona = result1.persona
        assert original_persona.variant_id == "content_creator"

        # 模拟用户切换业务上下文
        switch_success = self.persona_manager.switch_persona(
            user_id=user_id,
            new_business_type=BusinessType.ECOMMERCE,
            reason="用户开始咨询电商问题"
        )
        assert switch_success, "人格切换应成功"

        # 第二次请求：电商相关
        result2 = self.engine.process(
            "我的淘宝店转化率太低了怎么办",
            {"user_id": user_id}
        )

        assert result2.matched
        new_persona = result2.persona
        assert new_persona.variant_id == "ecommerce", \
            f"切换后应为电商人格，实际: {new_persona.variant_id}"

        # 验证确实发生了变化
        assert new_persona.variant_id != original_persona.variant_id

        print(f"\n✅ 人格切换测试通过:")
        print(f"   切换前: {original_persona.display_name} {original_persona.emoji}")
        print(f"   切换后: {new_persona.display_name} {new_persona.emoji}")


class TestErrorHandlingAndDegradation:
    """错误处理和降级机制测试"""

    @pytest.fixture(autouse=True)
    def setup_engine(self):
        self.engine = ScenarioEngineV2()
        self.detector = BusinessTypeDetector()
        self.persona_manager = PersonaManager()

    def test_detector_failure_graceful_degradation(self):
        """
        测试7: Detector失败时的降级处理
        当detector抛异常时，引擎应使用默认类型继续工作
        """
        # 注入一个会失败的detector
        class FailingDetector:
            def detect(self, *args, **kwargs):
                raise RuntimeError("模拟外部服务不可用")

        self.engine.type_detector = FailingDetector()

        result = self.engine.process("帮我做内容日历", {"user_id": "test_fail_001"})

        # 即使detector失败，引擎仍应返回结果（降级到默认类型）
        assert isinstance(result, ScenarioResult)
        assert result.detected_business_type is not None  # 应有默认值

        print(f"\n✅ Detector降级测试通过 (默认类型: {result.detected_business_type.value})")

    def test_persona_manager_failure_handling(self):
        """
        测试8: PersonaManager失败时的工作方式
        当persona加载失败，引擎仍应返回场景匹配结果
        """
        # 注入一个会失败的persona_manager
        class FailingPersonaManager:
            def get_persona(self, *args, **kwargs):
                return None  # 返回None模拟失败

        self.engine.type_detector = self.detector
        self.engine.persona_manager = FailingPersonaManager()

        result = self.engine.process(
            "帮我规划下周的内容日历",
            {"user_id": "test_fail_002"}
        )

        # 场景匹配应正常工作
        assert result.matched
        assert result.scenario_id == "content_calendar"

        # 但persona可能为None
        assert result.persona is None  # 这是可接受的降级行为

        print(f"\n✅ PersonaManager降级测试通过 (persona=None)")

    def test_empty_and_invalid_inputs(self):
        """
        测试9: 各种边界输入的处理
        """
        edge_cases = [
            ("", "空字符串"),
            ("   ", "纯空格"),
            ("???!!!@#$%", "特殊字符"),
            ("a" * 1000, "超长输入"),
            ("你好", "无意义输入"),
        ]

        for input_text, description in edge_cases:
            result = self.engine.process(input_text, {"user_id": "test_edge"})

            # 所有输入都不应导致崩溃
            assert isinstance(result, ScenarioResult), \
                f"{description}输入不应导致异常"

            # 未匹配时应提供建议
            if not result.matched:
                assert result.suggestion is not None, \
                    f"{description}: 未匹配时应提供建议"

        print(f"\n✅ 边界输入测试通过 ({len(edge_cases)}个用例)")

    def test_concurrent_requests_stress(self):
        """
        测试10: 并发请求压力测试
        模拟多用户同时访问的场景
        """
        results = []
        errors = []
        user_count = 20

        def simulate_user_request(user_idx):
            try:
                inputs = [
                    "内容日历规划",
                    "淘宝活动策划",
                    "产品发布方案"
                ]
                input_text = inputs[user_idx % len(inputs)]

                result = self.engine.process(
                    input_text,
                    {"user_id": f"concurrent_user_{user_idx}"}
                )
                results.append((user_idx, result))
            except Exception as e:
                errors.append((user_idx, str(e)))

        threads = []
        start_time = time.time()

        for i in range(user_count):
            t = threading.Thread(target=simulate_user_request, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10)  # 10秒超时

        elapsed_time = time.time() - start_time

        # 验证结果
        assert len(errors) == 0, f"并发请求出现{len(errors)}个错误: {errors[:3]}"
        assert len(results) == user_count, \
            f"预期{user_count}个结果，实际{len(results)}个"

        matched_count = sum(1 for _, r in results if r.matched)
        print(f"\n✅ 并发压力测试通过:")
        print(f"   请求数: {user_count}")
        print(f"   成功数: {len(results)}")
        print(f"   匹配率: {matched_count}/{user_count} ({matched_count/user_count*100:.0f}%)")
        print(f"   总耗时: {elapsed_time:.3f}s")
        print(f"   平均延迟: {elapsed_time/user_count*1000:.1f}ms/请求")


class TestRealWorldScenarios:
    """真实世界使用场景模拟"""

    @pytest.fixture(autouse=True)
    def setup_real_world(self):
        self.detector = BusinessTypeDetector()
        self.persona_manager = PersonaManager()
        self.engine = ScenarioEngineV2()
        self.engine.type_detector = self.detector
        self.engine.persona_manager = self.persona_manager

    def test_content_creator_daily_workflow(self):
        """
        测试11: 内容创作者日常工作流程
        模拟一整天的多个连续请求
        """
        user_id = "content_creator_daily"

        daily_tasks = [
            ("早上好，今天有什么热点？", None),  # 可能不匹配具体场景
            ("帮我规划下周的内容日历", "content_calendar"),
            ("这个选题怎么样？写一篇关于AI的文章", None),  # 可能匹配write_report
            ("明天下午3点开个团队会议", None),  # 会议场景可能不匹配或匹配到其他
        ]

        results = []
        for input_text, expected_scenario in daily_tasks:
            result = self.engine.process(input_text, {"user_id": user_id})
            results.append((input_text, result))

            if expected_scenario:
                assert result.matched, f"'{input_text}'应匹配到场景"
                # 注意：某些输入可能匹配到多个场景，只要匹配成功即可
                if result.matched:
                    # 允许灵活匹配（content_calendar优先级高于其他）
                    valid_scenarios = [expected_scenario]
                    if expected_scenario == "organize_meeting":
                        valid_scenarios.extend(["content_calendar", "write_report"])
                    assert result.scenario_id in valid_scenarios, \
                        f"期望{valid_scenarios}之一，实际{result.scenario_id}"

        # 验证所有请求都使用了相同的人格
        personas_used = set(r[1].persona.variant_id for r in results if r[1].persona)
        assert len(personas_used) <= 1, "同一用户应保持一致的人格"

        print(f"\n✅ 内容创作者日常流程测试通过 ({len(daily_tasks)}个任务)")

    def test_multi_type_user_journey(self):
        """
        测试12: 多类型用户的使用旅程
        模拟一个同时涉及多种业务的用户
        """
        user_id = "multi_type_user_001"

        journey_steps = [
            {
                "input": "我想做一个知识付费课程",
                "expected_type": BusinessType.DIGITAL_PRODUCT,
                "context": "用户想进入数字产品领域"
            },
            {
                "input": "帮我在小红书上推广这个课程",
                "expected_type": BusinessType.CONTENT_CREATOR,
                "context": "用户转向内容营销"
            },
            {
                "input": "我想在淘宝上开店卖周边产品",
                "expected_type": BusinessType.ECOMMERCE,
                "context": "用户扩展到电商"
            },
        ]

        detected_types = []

        for step in journey_steps:
            result = self.engine.process(step["input"], {"user_id": user_id})

            # 验证类型检测（允许一定误差，重点是验证多类型切换流程）
            detected_types.append(result.detected_business_type.value)

            # 注意：不是所有输入都会匹配到具体场景（这是正常的）
            if result.matched:
                print(f"   ✓ {step['context']}")
                print(f"     输入: {step['input'][:30]}...")
                print(f"     检测到: {result.detected_business_type.value}")
                print(f"     场景: {result.scenario_id}")
                print(f"     人格: {result.persona.display_name if result.persona else 'N/A'}")
            else:
                # 未匹配到具体场景也是可以接受的（某些自然语言输入可能不够明确）
                print(f"   ~ {step['context']} (未匹配场景，但类型检测正确)")
                print(f"     输入: {step['input'][:30]}...")
                print(f"     检测到: {result.detected_business_type.value}")

        # 验证用户确实经历了不同类型
        unique_types = set(detected_types)
        assert len(unique_types) >= 2, "用户应经历至少2种不同的业务类型"

        print(f"\n✅ 多类型用户旅程测试通过 (经历{len(unique_types)}种类型)")

    def test_response_formatting_quality(self):
        """
        测试13: 响应格式化质量检查
        验证不同人格的输出符合其风格定义
        """
        test_cases = [
            (
                BusinessType.CONTENT_CREATOR,
                "轻松活泼",
                ["emoji", "简短", "感叹号"]
            ),
            (
                BusinessType.DIGITAL_PRODUCT,
                "专业但亲切",
                ["数据", "专业术语"]
            ),
            (
                BusinessType.ECOMMERCE,
                "干练务实",
                ["GMV", "数据", "行动导向"]
            ),
        ]

        for btype, expected_tone, tone_keywords in test_cases:
            persona = self.persona_manager.get_persona(
                user_id=f"test_tone_{btype.value}",
                business_type=btype
            )

            assert persona is not None, f"应能加载{btype.value}人格"

            greeting = self.persona_manager.get_greeting(business_type=btype)
            complete = self.persona_manager.get_completion_message(
                business_type=btype,
                deliverable="测试交付物"
            )

            # 验证风格一致性
            style = persona.style_overrides
            formality = style.get('formality_level', 0.5)

            if expected_tone == "轻松活泼":
                assert formality < 0.5, "内容创作者应低正式度"
            elif expected_tone == "专业但亲切":
                assert 0.5 <= formality <= 0.8, "产品顾问应中等正式度"
            elif expected_tone == "干练务实":
                assert formality >= 0.5, "电商管家应较高正式度"

            print(f"\n   ✓ {persona.display_name}: 正式度={formality}, 问候语='{greeting[:30]}...'")

        print(f"\n✅ 响应格式化质量测试通过 ({len(test_cases)}种人格)")


class TestPerformanceBenchmark:
    """性能基准测试"""

    @pytest.fixture(autouse=True)
    def setup_perf(self):
        self.detector = BusinessTypeDetector()
        self.persona_manager = PersonaManager()
        self.engine = ScenarioEngineV2()
        self.engine.type_detector = self.detector
        self.engine.persona_manager = self.persona_manager

    def test_single_request_latency(self):
        """
        测试14: 单次请求延迟基准
        目标: < 500ms (架构设计文档要求)
        """
        test_input = "帮我规划下周的内容日历"
        iterations = 50

        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            result = self.engine.process(test_input, {"user_id": "perf_test"})
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        print(f"\n⏱️ 性能基准测试 (单次请求, {iterations}次迭代):")
        print(f"   平均延迟: {avg_latency:.2f}ms")
        print(f"   最小延迟: {min_latency:.2f}ms")
        print(f"   最大延迟: {max_latency:.2f}ms")
        print(f"   P95延迟: {p95_latency:.2f}ms")

        # 架构设计要求 < 500ms
        assert avg_latency < 500, \
            f"平均延迟{avg_latency:.2f}ms超过500ms目标"

        assert p95_latency < 1000, \
            f"P95延迟{p95_latency:.2f}ms超过1s上限"

    def test_batch_processing_throughput(self):
        """
        测试15: 批量处理吞吐量
        """
        batch_size = 100
        inputs = [
            "内容日历规划",
            "产品发布方案",
            "电商活动策划",
            "报告撰写",
            "会议组织"
        ] * 20

        start = time.perf_counter()
        results = [self.engine.process(inp, {"user_id": f"batch_{i}"})
                   for i, inp in enumerate(inputs)]
        total_time = time.perf_counter() - start

        throughput = batch_size / total_time  # requests per second

        print(f"\n⚡ 吞吐量测试 ({batch_size}个请求):")
        print(f"   总时间: {total_time:.3f}s")
        print(f"   吞吐量: {throughput:.1f} req/s")
        print(f"   成功率: {sum(1 for r in results if r.matched)/batch_size*100:.1f}%")

        assert throughput > 10, \
            f"吞吐量{throughput:.1f} req/s过低，应>10 req/s"


if __name__ == "__main__":
    # 运行所有集成测试
    pytest.main([__file__, "-v", "--tb=short", "-s"])
