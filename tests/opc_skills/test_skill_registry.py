"""
技能搜索基础架构单元测试
"""

import unittest
import os
import tempfile
import shutil
from opc_skills.skill_registry import SkillRegistry, SkillSearchEngine


class TestSkillRegistry(unittest.TestCase):
    """技能注册中心测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.registry_file = os.path.join(self.test_dir, 'test_registry.json')
        self.registry = SkillRegistry({
            'registry_file': self.registry_file
        })
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_register_skill(self):
        """测试注册技能"""
        # 创建测试技能类
        class TestSkill:
            METADATA = {
                'name': 'test_skill',
                'version': '1.0.0',
                'description': '测试技能',
                'author': 'Test',
                'category': 'test',
                'tags': ['test', 'demo'],
                'permissions': [],
            }
        
        result = self.registry.register_skill(TestSkill)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['skill_name'], 'test_skill')
        
        # 验证技能已注册
        skill = self.registry.get_skill('test_skill')
        self.assertIsNotNone(skill)
        self.assertEqual(skill['name'], 'test_skill')
        self.assertEqual(skill['category'], 'test')
    
    def test_unregister_skill(self):
        """测试注销技能"""
        class TestSkill:
            METADATA = {
                'name': 'test_skill',
                'version': '1.0.0',
                'description': '测试技能',
            }
        
        # 先注册
        self.registry.register_skill(TestSkill)
        
        # 再注销
        result = self.registry.unregister_skill('test_skill')
        
        self.assertTrue(result['success'])
        
        # 验证技能已注销
        skill = self.registry.get_skill('test_skill')
        self.assertIsNone(skill)
    
    def test_list_skills(self):
        """测试列出技能"""
        # 注册多个技能
        class Skill1:
            METADATA = {'name': 'skill1', 'category': 'cat1', 'tags': ['tag1']}
        class Skill2:
            METADATA = {'name': 'skill2', 'category': 'cat2', 'tags': ['tag2']}
        class Skill3:
            METADATA = {'name': 'skill3', 'category': 'cat1', 'tags': ['tag1', 'tag2']}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        self.registry.register_skill(Skill3)
        
        # 列出所有技能
        skills = self.registry.list_skills()
        self.assertEqual(len(skills), 3)
        
        # 按分类过滤
        skills = self.registry.list_skills(category='cat1')
        self.assertEqual(len(skills), 2)
        
        # 按标签过滤
        skills = self.registry.list_skills(tags=['tag2'])
        self.assertEqual(len(skills), 2)
    
    def test_search_skills(self):
        """测试搜索技能"""
        class Skill1:
            METADATA = {'name': 'web_search', 'description': '网页搜索', 'tags': ['搜索', '网页']}
        class Skill2:
            METADATA = {'name': 'doc_processor', 'description': '文档处理', 'tags': ['文档', '处理']}
        class Skill3:
            METADATA = {'name': 'content_summary', 'description': '内容摘要', 'tags': ['摘要', '内容']}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        self.registry.register_skill(Skill3)
        
        # 搜索
        results = self.registry.search_skills('搜索')
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['name'], 'web_search')
        
        # 搜索文档
        results = self.registry.search_skills('文档')
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['name'], 'doc_processor')
    
    def test_get_categories(self):
        """测试获取分类"""
        class Skill1:
            METADATA = {'name': 'skill1', 'category': 'category_a'}
        class Skill2:
            METADATA = {'name': 'skill2', 'category': 'category_b'}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        
        categories = self.registry.get_categories()
        self.assertIn('category_a', categories)
        self.assertIn('category_b', categories)
    
    def test_get_tags(self):
        """测试获取标签"""
        class Skill1:
            METADATA = {'name': 'skill1', 'tags': ['tag1', 'tag2']}
        class Skill2:
            METADATA = {'name': 'skill2', 'tags': ['tag2', 'tag3']}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        
        tags = self.registry.get_tags()
        self.assertIn('tag1', tags)
        self.assertIn('tag2', tags)
        self.assertIn('tag3', tags)
    
    def test_update_usage(self):
        """测试更新使用计数"""
        class TestSkill:
            METADATA = {'name': 'test_skill'}
        
        self.registry.register_skill(TestSkill)
        
        # 更新使用计数
        result1 = self.registry.update_skill_usage('test_skill')
        self.assertTrue(result1['success'])
        self.assertEqual(result1['usage_count'], 1)
        
        # 再次更新
        result2 = self.registry.update_skill_usage('test_skill')
        self.assertTrue(result2['success'])
        self.assertEqual(result2['usage_count'], 2)
    
    def test_rate_skill(self):
        """测试评分技能"""
        class TestSkill:
            METADATA = {'name': 'test_skill'}
        
        self.registry.register_skill(TestSkill)
        
        # 评分
        result1 = self.registry.rate_skill('test_skill', 4.0)
        self.assertTrue(result1['success'])
        self.assertEqual(result1['rating'], 4.0)
        
        # 再次评分
        result2 = self.registry.rate_skill('test_skill', 5.0)
        self.assertTrue(result2['success'])
        self.assertAlmostEqual(result2['rating'], 4.5, places=2)
    
    def test_invalid_skill_name(self):
        """测试无效技能名称"""
        result = self.registry.get_skill('nonexistent')
        self.assertIsNone(result)
        
        result = self.registry.unregister_skill('nonexistent')
        self.assertFalse(result['success'])


class TestSkillSearchEngine(unittest.TestCase):
    """技能搜索引擎测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.test_dir = tempfile.mkdtemp()
        self.registry_file = os.path.join(self.test_dir, 'test_registry.json')
        self.registry = SkillRegistry({
            'registry_file': self.registry_file
        })
        self.search_engine = SkillSearchEngine(self.registry)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_search(self):
        """测试搜索"""
        class Skill1:
            METADATA = {'name': 'web_search', 'description': '网页搜索', 'tags': ['搜索']}
        class Skill2:
            METADATA = {'name': 'doc_processor', 'description': '文档处理', 'tags': ['文档']}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        
        result = self.search_engine.search('搜索')
        
        self.assertTrue(result['success'])
        self.assertGreater(result['total'], 0)
        self.assertIn('search_time_ms', result)
    
    def test_search_with_filters(self):
        """测试带过滤器的搜索"""
        class Skill1:
            METADATA = {'name': 'skill1', 'category': 'cat_a', 'tags': ['tag1']}
        class Skill2:
            METADATA = {'name': 'skill2', 'category': 'cat_b', 'tags': ['tag2']}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        
        # 带分类过滤
        result = self.search_engine.search('skill', filters={'category': 'cat_a'})
        self.assertEqual(result['total'], 1)
    
    def test_search_sorting(self):
        """测试搜索排序"""
        class Skill1:
            METADATA = {'name': 'skill_a', 'rating': 3.0, 'usage_count': 10}
        class Skill2:
            METADATA = {'name': 'skill_b', 'rating': 5.0, 'usage_count': 5}
        
        self.registry.register_skill(Skill1)
        self.registry.register_skill(Skill2)
        
        # 按评分排序
        result = self.search_engine.search('skill', sort_by='rating')
        self.assertEqual(result['results'][0]['name'], 'skill_b')
        
        # 按使用次数排序
        result = self.search_engine.search('skill', sort_by='usage_count')
        self.assertEqual(result['results'][0]['name'], 'skill_a')


if __name__ == '__main__':
    unittest.main()
