"""
能力发现器完整集成测试
测试总裁办在发现能力不足时，能否主动通过人事部获取新能力
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_manager.core import OPCManager


class TestFullCapabilityDiscoveryIntegration(unittest.TestCase):
    """测试完整的能力发现集成"""
    
    def setUp(self):
        """初始化测试环境"""
        self.opc = OPCManager(debug_mode=True)
    
    def test_capability_discovery_initialized(self):
        """测试能力发现器已初始化"""
        self.assertTrue(hasattr(self.opc, 'capability_discovery'))
        self.assertIsNotNone(self.opc.capability_discovery)
        print(f"✅ 能力发现器已初始化")
    
    def test_detect_capability_gaps_method_exists(self):
        """测试 detect_capability_gaps 方法存在"""
        self.assertTrue(hasattr(self.opc, 'detect_capability_gaps'))
        self.assertTrue(callable(getattr(self.opc, 'detect_capability_gaps')))
        print(f"✅ detect_capability_gaps 方法存在")
    
    def test_install_recommended_skill_method_exists(self):
        """测试 install_recommended_skill 方法存在"""
        self.assertTrue(hasattr(self.opc, 'install_recommended_skill'))
        self.assertTrue(callable(getattr(self.opc, 'install_recommended_skill')))
        print(f"✅ install_recommended_skill 方法存在")
    
    def test_decompose_task_with_capability_check(self):
        """测试任务分解时检测能力缺口"""
        # 测试场景 1：PDF 处理任务（可能需要新技能）
        task = "分析这份 PDF 文档并提取关键信息"
        result = self.opc.decompose_task(
            task=task,
            user_request=task
        )
        
        # 验证返回结构
        self.assertIn('execution_steps', result)
        self.assertIn('capability_gaps', result)
        self.assertIn('recommendations', result)
        self.assertIn('action_required', result)
        
        print(f"✅ 任务分解包含能力检测")
        print(f"   执行步骤：{len(result['execution_steps'])} 个")
        print(f"   能力缺口：{len(result['capability_gaps'])} 个")
        print(f"   推荐：{len(result['recommendations'])} 个")
        print(f"   需要操作：{result['action_required']}")
    
    def test_full_workflow(self):
        """测试完整工作流：从需求到推荐"""
        print("\n=== 完整工作流测试 ===")
        
        # 步骤 1: 用户需求
        user_request = "我需要分析这个 Excel 文件并生成图表"
        print(f"1️⃣ 用户需求：{user_request}")
        
        # 步骤 2: 检测能力缺口
        result = self.opc.detect_capability_gaps(user_request, context="数据分析")
        
        print(f"2️⃣ 检测结果:")
        print(f"   能力缺口：{len(result['gaps'])} 个")
        for gap in result['gaps'][:3]:
            print(f"   - {gap.skill_name} (优先级：{gap.priority})")
        
        print(f"3️⃣ 推荐：{len(result['recommendations'])} 个")
        for rec in result['recommendations'][:2]:
            print(f"   - {rec['skill']['name']}")
            print(f"     理由：{rec['reason'][:60]}...")
        
        print(f"4️⃣ 需要用户操作：{result['action_required']}")
        
        # 验证返回结构
        self.assertIn('gaps', result)
        self.assertIn('recommendations', result)
        self.assertIn('action_required', result)
        
        print(f"\n✅ 完整工作流测试通过")


class TestEventBusIntegration(unittest.TestCase):
    """测试事件总线集成"""
    
    def setUp(self):
        """初始化测试环境"""
        self.opc = OPCManager(debug_mode=True)
    
    def test_capability_gap_event_subscription(self):
        """测试能力缺口事件订阅"""
        # 验证事件总线已订阅 capability_gap_detected 事件
        event_handlers = self.opc.event_bus._EventBus__event_handlers
        self.assertIn('capability_gap_detected', event_handlers)
        print(f"✅ capability_gap_detected 事件已订阅")


if __name__ == '__main__':
    # 运行测试
    print("=" * 80)
    print("能力发现器完整集成测试")
    print("=" * 80)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestFullCapabilityDiscoveryIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEventBusIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 输出总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    print(f"总测试数：{result.testsRun}")
    print(f"通过：{result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败：{len(result.failures)}")
    print(f"错误：{len(result.errors)}")
    
    if result.failures:
        print("\n失败测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\n错误测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # 退出码
    sys.exit(0 if result.wasSuccessful() else 1)
