"""
网页搜索技能单元测试
"""

import unittest
from opc_skills.web_search import WebSearchSkill


class TestWebSearchSkill(unittest.TestCase):
    """网页搜索技能测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.skill = WebSearchSkill({
            'default_engine': 'duckduckgo',
            'max_results': 5,
            'timeout': 30
        })
    
    @unittest.skip("需要网络连接，可能失败")
    def test_execute_success(self):
        """测试搜索执行成功"""
        result = self.skill.execute('Python programming')
        
        # 验证返回结构
        self.assertIn('success', result)
        self.assertIn('results', result)
        
        # 如果搜索成功，验证结果格式
        if result['success']:
            self.assertIn('total', result)
            self.assertIn('query', result)
            self.assertIn('engine', result)
            self.assertIsInstance(result['results'], list)
            self.assertGreaterEqual(result['total'], 0)
            
            # 验证每个结果的格式
            for r in result['results']:
                self.assertIn('title', r)
                self.assertIn('link', r)
                self.assertIn('snippet', r)
                self.assertIn('source', r)
    
    def test_invalid_engine(self):
        """测试无效的搜索引擎"""
        result = self.skill.execute('test', engine='invalid_engine')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('available_engines', result)
    
    def test_advanced_search_site(self):
        """测试限定网站的高级搜索"""
        result = self.skill.execute(
            'AI Agent',
            advanced=True,
            site='github.com'
        )
        
        # 验证返回结构
        self.assertIn('success', result)
        self.assertIn('results', result)
    
    def test_advanced_search_exclude(self):
        """测试排除词的高级搜索"""
        result = self.skill.execute(
            'Python tutorial',
            advanced=True,
            exclude=['beginner', 'basic']
        )
        
        # 验证返回结构
        self.assertIn('success', result)
    
    def test_get_schema(self):
        """测试获取 schema"""
        schema = self.skill.get_schema()
        
        # 验证 schema 结构
        self.assertIn('input', schema)
        self.assertIn('output', schema)
        
        # 验证输入 schema
        input_schema = schema['input']
        self.assertIn('query', input_schema)
        self.assertEqual(input_schema['query']['required'], True)
        
        # 验证输出 schema
        output_schema = schema['output']
        self.assertIn('success', output_schema)
        self.assertIn('results', output_schema)
    
    def test_deduplicate(self):
        """测试去重功能"""
        # 构造重复的结果
        results = [
            {'title': 'Result 1', 'link': 'http://example.com/1', 'snippet': 'Snippet 1'},
            {'title': 'Result 2', 'link': 'http://example.com/2', 'snippet': 'Snippet 2'},
            {'title': 'Result 1 Duplicate', 'link': 'http://example.com/1', 'snippet': 'Snippet 1 dup'},
        ]
        
        # 去重
        unique_results = self.skill._deduplicate_and_sort(results, 'test')
        
        # 验证去重结果
        self.assertEqual(len(unique_results), 2)
        
        # 验证链接唯一性
        links = [r['link'] for r in unique_results]
        self.assertEqual(len(links), len(set(links)))


class TestWebSearchSkillBaidu(unittest.TestCase):
    """百度搜索技能测试（需要网络）"""
    
    @unittest.skip("需要网络连接，可能失败")
    def test_baidu_search(self):
        """测试百度搜索"""
        skill = WebSearchSkill({
            'default_engine': 'baidu',
            'max_results': 3
        })
        
        result = skill.execute('Python 编程')
        
        # 百度搜索应该返回结果
        self.assertTrue(result['success'])
        self.assertGreater(result['total'], 0)


if __name__ == '__main__':
    unittest.main()
