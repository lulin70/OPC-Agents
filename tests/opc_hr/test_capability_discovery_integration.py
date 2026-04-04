"""
能力发现器集成测试
测试总裁办在发现能力不足时，能否主动通过人事部获取新能力
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.capability_discovery import CapabilityDiscovery, CapabilityGap
from opc_skills import SkillRegistry, ClawHubIntegration


class TestCapabilityDiscoveryIntegration(unittest.TestCase):
    """测试能力发现器集成"""
    
    def setUp(self):
        """初始化测试环境"""
        self.skill_registry = SkillRegistry()
        self.clawhub = ClawHubIntegration()
        self.capability_discovery = CapabilityDiscovery(
            skill_registry=self.skill_registry,
            clawhub=self.clawhub
        )
    
    def test_analyze_user_request(self):
        """测试分析用户需求"""
        # 测试场景 1：需要处理 PDF
        request1 = "我需要分析这份 PDF 文档的内容"
        keywords1 = self.capability_discovery.analyze_user_request(request1)
        self.assertIn('pdf', keywords1)
        self.assertIn('document', keywords1)
        
        # 测试场景 2：需要处理 Excel
        request2 = "帮我分析这个 Excel 表格的数据"
        keywords2 = self.capability_discovery.analyze_user_request(request2)
        self.assertIn('excel', keywords2)
        self.assertIn('spreadsheet', keywords2)
        self.assertIn('analyze', keywords2)
        
        # 测试场景 3：需要搜索和翻译
        request3 = "搜索最新的 AI 资讯并翻译成中文"
        keywords3 = self.capability_discovery.analyze_user_request(request3)
        self.assertIn('search', keywords3)
        self.assertIn('web', keywords3)
        self.assertIn('translate', keywords3)
        
        print(f"✅ 用户需求分析测试通过")
        print(f"   PDF 需求关键词：{keywords1}")
        print(f"   Excel 需求关键词：{keywords2}")
        print(f"   搜索翻译需求关键词：{keywords3}")
    
    def test_detect_capability_gap(self):
        """测试检测能力缺口"""
        # 模拟用户需求
        request = "我需要处理视频文件并添加字幕"
        keywords = self.capability_discovery.analyze_user_request(request)
        
        # 检测能力缺口
        gaps = self.capability_discovery.detect_capability_gap(
            required_keywords=keywords,
            context="视频处理任务"
        )
        
        # 验证检测到了缺口
        self.assertGreater(len(gaps), 0, "应该检测到能力缺口")
        
        # 验证缺口信息完整
        for gap in gaps:
            self.assertIsInstance(gap, CapabilityGap)
            self.assertIn('video', gap.skill_name.lower())
            self.assertEqual(gap.required_by, "视频处理任务")
            self.assertGreater(gap.priority, 0)
        
        print(f"✅ 能力缺口检测测试通过")
        print(f"   检测到 {len(gaps)} 个能力缺口:")
        for gap in gaps:
            print(f"   - {gap.skill_name} (优先级：{gap.priority})")
    
    def test_search_alternatives(self):
        """测试搜索替代技能"""
        # 创建一个能力缺口
        gap = CapabilityGap(
            skill_name='pdf',
            required_by='文档处理任务',
            priority=7
        )
        
        # 搜索替代技能
        candidates = self.capability_discovery.search_alternatives(gap)
        
        # 验证搜索结果
        self.assertIsInstance(candidates, list)
        
        print(f"✅ 替代技能搜索测试通过")
        print(f"   找到 {len(candidates)} 个候选技能")
        if candidates:
            print(f"   示例：{candidates[0].get('name', 'Unknown')}")
    
    def test_evaluate_candidate(self):
        """测试评估候选技能"""
        # 模拟候选技能
        candidate = {
            'name': 'PDF Processor',
            'category': 'document',
            'rating': 4.5,
            'download_count': 15000,
            'security_score': 85
        }
        
        gap = CapabilityGap(
            skill_name='pdf',
            required_by='文档处理任务',
            priority=7
        )
        
        # 评估候选
        score = self.capability_discovery._evaluate_candidate(candidate, gap)
        
        # 验证评分合理性（满分 100）
        self.assertGreater(score, 60, "高匹配度技能应该得分较高")
        self.assertLessEqual(score, 100, "评分不应超过 100")
        
        print(f"✅ 候选技能评估测试通过")
        print(f"   候选技能：{candidate['name']}")
        print(f"   综合评分：{score}")
    
    def test_recommend_to_user(self):
        """测试向用户推荐技能"""
        # 模拟候选技能和能力缺口
        candidate = {
            'name': 'PDF Processor',
            'category': 'document',
            'rating': 4.5,
            'download_count': 15000,
            'security_score': 85
        }
        
        gap = CapabilityGap(
            skill_name='pdf',
            required_by='文档处理任务',
            priority=7
        )
        
        user = {'name': 'Test User'}
        
        # 推荐技能
        result = self.capability_discovery.recommend_to_user(candidate, gap, user)
        
        # 验证推荐结果
        self.assertTrue(result['success'])
        self.assertIn('recommendation', result)
        
        recommendation = result['recommendation']
        self.assertEqual(recommendation['skill']['name'], candidate['name'])
        self.assertEqual(recommendation['priority'], gap.priority)
        self.assertIn('reason', recommendation)
        self.assertIn('benefits', recommendation)
        
        print(f"✅ 用户推荐测试通过")
        print(f"   推荐理由：{recommendation['reason']}")
        print(f"   安装好处：{recommendation['benefits']}")
    
    def test_full_workflow(self):
        """测试完整工作流：从需求分析到推荐"""
        print("\n=== 完整工作流测试 ===")
        
        # 步骤 1：用户需求
        user_request = "我需要分析这个 Excel 文件并生成图表"
        print(f"1️⃣ 用户需求：{user_request}")
        
        # 步骤 2：分析需求，提取关键词
        keywords = self.capability_discovery.analyze_user_request(user_request)
        print(f"2️⃣ 提取关键词：{keywords}")
        
        # 步骤 3：检测能力缺口
        gaps = self.capability_discovery.detect_capability_gap(keywords, user_request)
        print(f"3️⃣ 检测到 {len(gaps)} 个能力缺口:")
        for gap in gaps:
            print(f"   - {gap.skill_name} (优先级：{gap.priority})")
        
        # 步骤 4：搜索替代技能
        all_candidates = []
        for gap in gaps:
            candidates = self.capability_discovery.search_alternatives(gap)
            all_candidates.extend(candidates)
            print(f"4️⃣ 为 '{gap.skill_name}' 找到 {len(candidates)} 个候选技能")
        
        # 步骤 5：评估和选择最佳候选
        if all_candidates:
            best_gap = gaps[0] if gaps else CapabilityGap('excel', '测试', 5)
            best_candidate = self.capability_discovery.evaluate_and_test(
                all_candidates, 
                best_gap
            )
            
            if best_candidate:
                print(f"5️⃣ 选择最佳候选：{best_candidate.get('name')}")
                
                # 步骤 6：向用户推荐
                user = {'name': 'Test User'}
                result = self.capability_discovery.recommend_to_user(
                    best_candidate, 
                    best_gap, 
                    user
                )
                
                if result['success']:
                    print(f"6️⃣ ✅ 推荐成功！")
                    print(f"   推荐技能：{best_candidate['name']}")
                    print(f"   推荐理由：{result['recommendation']['reason']}")
                    print(f"   安装好处：{result['recommendation']['benefits']}")
                else:
                    print(f"6️⃣ ⚠️ 推荐失败：{result['reason']}")
            else:
                print(f"5️⃣ ⚠️ 没有合适的候选技能")
        else:
            print(f"4️⃣ ⚠️ 没有找到候选技能")
        
        print(f"\n✅ 完整工作流测试完成")


class TestIntegrationWithOPCManager(unittest.TestCase):
    """测试与 OPCManager 的集成"""
    
    def test_capability_discovery_import(self):
        """测试能力发现器可以导入"""
        try:
            from opc_hr.capability_discovery import CapabilityDiscovery
            print(f"✅ 能力发现器模块导入成功")
        except ImportError as e:
            self.fail(f"能力发现器模块导入失败：{e}")
    
    def test_hr_enhancement_has_capability_methods(self):
        """测试 HR 增强模块有能力发现相关方法"""
        from opc_hr.hr_enhancement import HREnhancement
        
        # 检查 HREnhancement 是否有相关方法
        methods = dir(HREnhancement)
        
        # 应该有技能相关方法
        self.assertIn('get_all_skills', methods)
        self.assertIn('find_matching_agents', methods)
        
        print(f"✅ HR 增强模块具备能力发现相关方法")


if __name__ == '__main__':
    # 运行测试
    print("=" * 80)
    print("能力发现器集成测试")
    print("=" * 80)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestCapabilityDiscoveryIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWithOPCManager))
    
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
