#!/usr/bin/env python3
"""
OPC-Agents V2.1 快速入门示例
==========================

演示三组件串联使用：
1. BusinessTypeDetector - 业务类型检测
2. ScenarioEngineV2 - 场景匹配与工作流生成
3. PersonaManager - 人格选择与响应格式化

运行方式：
    python examples/quickstart_v21.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from opc_manager.scenario_engine_v2 import ScenarioEngineV2, get_scenario_engine_v2, BusinessType
from opc_manager.business_type_detector import BusinessTypeDetector, DetectionResult
from opc_manager.persona_manager import PersonaManager, PersonaConfig


def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_basic_usage():
    """演示1: 基本用法 - 单次请求处理"""
    print_separator("🚀 演示1: 基本用法 - 三组件串联")

    # 初始化三个组件
    print("\n[步骤1] 初始化组件...")
    detector = BusinessTypeDetector()
    persona_mgr = PersonaManager()
    engine = get_scenario_engine_v2()

    # 注入组件到引擎
    engine.type_detector = detector
    engine.persona_manager = persona_mgr

    print("  ✅ BusinessTypeDetector 已初始化")
    print("  ✅ PersonaManager 已加载3种人格变体")
    print("  ✅ ScenarioEngineV2 已就绪（9个场景）")

    # 模拟用户请求
    user_input = "帮我规划下周的内容日历，要考虑粉丝画像"
    user_context = {"user_id": "demo_user_001"}

    print(f"\n[步骤2] 处理用户请求...")
    print(f'  用户输入: "{user_input}"')

    # 执行完整流程
    result = engine.process(user_input, user_context)

    # 展示结果
    print(f"\n[步骤3] 处理结果:")
    print(f"  ✅ 匹配成功: {result.matched}")
    if result.matched:
        print(f"  📌 场景ID: {result.scenario_id}")
        print(f"  🎯 场景名称: {result.scenario_config.name}")
        print(f"  🎨 业务类型: {result.detected_business_type.value}")
        print(f"  📊 置信度: {result.confidence:.2f}")

        if result.persona:
            print(f"  🤖 人格: {result.persona.display_name} {result.persona.emoji}")
            print(f"     正式度: {result.persona.style_overrides.get('formality_level')}")

        if result.workflow:
            print(f"  📋 工作流步骤 ({len(result.workflow)}步):")
            for step in result.workflow[:3]:  # 只显示前3步
                print(f"     {step['step_id']}. {step['name']} ({step['estimated_duration']})")
            if len(result.workflow) > 3:
                print(f"     ... 还有{len(result.workflow)-3}步")

        # 使用人格格式化响应
        greeting = persona_mgr.format_response(result.persona, "greeting")
        accept_msg = persona_mgr.format_response(
            result.persona,
            "accept_task"
        )
        complete_msg = persona_mgr.format_response(
            result.persona,
            "complete",
            deliverable="周内容日历"
        )

        print(f"\n  💬 人格化响应示例:")
        print(f"     问候语: {greeting}")
        print(f"     接受任务: {accept_msg}")
        print(f"     完成通知: {complete_msg}")


def demo_multi_type_users():
    """演示2: 多类型用户场景"""
    print_separator("👥 演示2: 多业务类型用户场景")

    detector = BusinessTypeDetector()
    persona_mgr = PersonaManager()
    engine = get_scenario_engine_v2()
    engine.type_detector = detector
    engine.persona_manager = persona_mgr

    # 不同类型的用户请求
    test_cases = [
        {
            "user": "小美 (内容创作者)",
            "input": "我的小红书账号想涨粉，帮忙规划内容",
            "expected_type": "content_creator",
            "emoji": "✍️"
        },
        {
            "user": "老张 (数字产品开发者)",
            "input": "我要在Gumroad上发布一个新课程",
            "expected_type": "digital_product",
            "emoji": "💰"
        },
        {
            "user": "王哥 (电商运营者)",
            "input": "帮我的淘宝店铺策划双十一活动",
            "expected_type": "ecommerce",
            "emoji": "🛒"
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'─' * 50}")
        print(f"  👤 用户{i}: {case['user']}")
        print(f'  💬 输入: "{case["input"]}"')
        print(f"  {case['emoji']} 预期类型: {case['expected_type']}")

        result = engine.process(case["input"], {"user_id": f"demo_{i}"})

        if result.matched:
            type_match = "✅" if result.detected_business_type.value == case["expected_type"] else "⚠️"
            print(f"  {type_match} 检测到: {result.detected_business_type.value}")
            print(f"  🎯 匹配场景: {result.scenario_id}")
            if result.persona:
                print(f"  🤖 人格回复: {persona_mgr.get_greeting(business_type=result.detected_business_type)}")
        else:
            print("  ❌ 未匹配到具体场景")


def demo_persona_switching():
    """演示3: 人格切换机制"""
    print_separator("🔄 演示3: 人格动态切换")

    persona_mgr = PersonaManager()

    user_id = "demo_switch_user"

    # 初始状态：内容创作者
    print(f"\n[初始状态] 用户: {user_id}")
    persona1 = persona_mgr.get_persona(
        user_id=user_id,
        business_type=BusinessType.CONTENT_CREATOR
    )
    print(f"  当前人格: {persona1.display_name} {persona1.emoji}")
    print(f"  问候语: {persona_mgr.get_greeting(business_type=BusinessType.CONTENT_CREATOR)}")

    # 切换到电商运营
    print(f"\n[切换事件] 用户开始咨询电商问题...")
    switch_success = persona_mgr.switch_persona(
        user_id=user_id,
        new_business_type=BusinessType.ECOMMERCE,
        reason="用户转向电商运营咨询"
    )

    if switch_success:
        persona2 = persona_mgr._cache.get(user_id)
        print(f"  ✅ 切换成功!")
        print(f"  新人格: {persona2.display_name} {persona2.emoji}")
        print(f"  新问候语: {persona_mgr.get_greeting(business_type=BusinessType.ECOMMERCE)}")

        # 对比两种人格的风格差异
        print(f"\n[风格对比]")
        print(f"  内容创作者风格: 正式度={persona1.style_overrides.get('formality_level')}, emoji密度={persona1.style_overrides.get('emoji_density')}")
        print(f"  电商运营者风格:   正式度={persona2.style_overrides.get('formality_level')}, emoji密度={persona2.style_overrides.get('emoji_density')}")


def demo_detection_details():
    """演示4: 类型检测详情"""
    print_separator("🔍 演示4: 业务类型检测详情")

    detector = BusinessTypeDetector()

    test_inputs = [
        "帮我规划下周的内容日历",
        "我要发布一个新的AI工具",
        "帮我的淘宝店铺做个活动",
        "客户需要一份战略咨询提案",
        "我在Gumroad上有个课程要上架",
        "设计稿完成了，准备交付给客户"
    ]

    for input_text in test_inputs:
        result = detector.detect(input_text)

        print(f'\n输入: "{input_text[:40]}..."')
        print(f'  → 类型: {result.business_type.value:20s} | 置信度: {result.confidence:.3f} | 方法: {result.method}')
        if result.matched_keywords:
            print(f'  → 关键词: {", ".join(result.matched_keywords[:5])}')


def demo_engine_statistics():
    """演示5: 引擎统计信息"""
    print_separator("📊 演示5: 引擎统计信息")

    engine = ScenarioEngineV2()
    stats = engine.get_statistics()

    print(f"\n版本信息:")
    print(f"  版本号: {stats['version']}")
    print(f"  总场景数: {stats['total_scenarios']}")
    print(f"  支持的业务类型数: {len(stats['business_types_supported'])}")

    print(f"\n各类型场景分布:")
    for bt, count in stats['scenarios_per_type'].items():
        print(f"  {bt}: {count}个场景")

    print(f"\n所有场景列表:")
    scenarios = engine.list_scenarios()
    for s in scenarios:
        types_str = ', '.join(s['target_business_types'][:3])
        if len(s['target_business_types']) > 3:
            types_str += f"... (+{len(s['target_business_types'])-3})"
        print(f"  [{s['id']:25s}] {s['name']:15s} | 类型: {types_str} | 步骤: {s['steps_count']}")


def main():
    """主函数：运行所有演示"""
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + "  OPC-Agents V2.1 快速入门演示".center(66) + "║")
    print("║" + "  Phase 1 MVP - 三组件串联示例".center(66) + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        demo_basic_usage()
        demo_multi_type_users()
        demo_persona_switching()
        demo_detection_details()
        demo_engine_statistics()

        print("\n" + "=" * 70)
        print("  🎉 所有演示完成！")
        print("=" * 70)
        print("\n下一步建议:")
        print("  1. 运行测试: python -m pytest tests/test_scenario_engine_v2.py -v")
        print("  2. 查看文档: docs/architect/ARCHITECTURE_DESIGN_V21.md")
        print("  3. 自定义配置: 编辑 config/persona_variants.yaml")
        print("\n")

    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
