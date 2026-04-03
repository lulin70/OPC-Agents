"""
内容摘要技能单元测试
"""

import unittest
from opc_skills.content_summary import ContentSummarySkill


class TestContentSummarySkill(unittest.TestCase):
    """内容摘要技能测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.skill = ContentSummarySkill()
        self.test_text = """
        人工智能是 21 世纪最重要的技术革命之一。首先，人工智能在医疗领域的应用已经取得了显著成果。
        其次，在交通领域，自动驾驶技术正在快速发展。第三，人工智能在金融领域的应用也非常广泛。
        此外，AI 还在教育、零售、制造等行业发挥着重要作用。
        
        值得注意的是，人工智能的发展也带来了一些挑战。比如数据隐私问题、就业替代问题、算法偏见等。
        因此，我们需要在推动 AI 技术发展的同时，也要关注其可能带来的社会影响。
        
        总之，人工智能正在深刻改变我们的生活和工作方式。未来，随着技术的不断进步，AI 将会更加普及和智能化。
        """
    
    def test_get_schema(self):
        """测试获取 schema"""
        schema = self.skill.get_schema()
        
        # 验证 schema 结构
        self.assertIn('input', schema)
        self.assertIn('output', schema)
        
        # 验证输入 schema
        input_schema = schema['input']
        self.assertIn('operation', input_schema)
        self.assertEqual(input_schema['operation']['required'], True)
        self.assertIn('text', input_schema)
        
        # 验证操作类型
        supported_ops = ['summarize', 'outline', 'keywords', 'extract']
        self.assertEqual(input_schema['operation']['enum'], supported_ops)
    
    def test_invalid_operation(self):
        """测试无效操作"""
        result = self.skill.execute('invalid_op', self.test_text)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('supported_operations', result)
    
    def test_summarize(self):
        """测试文本摘要"""
        result = self.skill.execute('summarize', self.test_text, ratio=0.3)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('summary', result)
        self.assertIn('original_length', result)
        self.assertIn('summary_length', result)
        self.assertIn('compression_ratio', result)
        
        # 验证摘要长度
        self.assertLess(len(result['summary']), len(self.test_text))
        self.assertGreater(result['compression_ratio'], 0)
        self.assertLessEqual(result['compression_ratio'], 1)
    
    def test_outline(self):
        """测试大纲生成"""
        result = self.skill.execute('outline', self.test_text)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('outline', result)
        self.assertIn('structure', result)
        self.assertIn('main_points', result)
        self.assertIn('points_count', result)
        
        # 验证大纲包含标记
        self.assertIn('【引言】', result['outline'])
        self.assertIn('【总结】', result['outline'])
    
    def test_keywords(self):
        """测试关键词提取"""
        result = self.skill.execute('keywords', self.test_text, top_k=5)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('keywords', result)
        self.assertIn('scores', result)
        
        # 验证关键词数量
        self.assertLessEqual(len(result['keywords']), 5)
        self.assertGreater(len(result['keywords']), 0)
        
        # 验证关键词不为空
        for keyword in result['keywords']:
            self.assertIsInstance(keyword, str)
            self.assertGreater(len(keyword), 0)
    
    def test_extract(self):
        """测试关键信息提取"""
        result = self.skill.execute('extract', self.test_text)
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('key_sentences', result)
        
        # 验证关键句子
        self.assertGreater(len(result['key_sentences']), 0)
    
    def test_empty_text(self):
        """测试空文本"""
        result = self.skill.execute('summarize', '')
        
        # 空文本应该返回成功但无内容
        self.assertTrue(result['success'])
    
    def test_single_sentence(self):
        """测试单句文本"""
        single_text = "这是一个测试句子。"
        result = self.skill.execute('summarize', single_text)
        
        # 单句文本应该返回原文
        self.assertTrue(result['success'])
        self.assertEqual(result['summary'], single_text)
        self.assertEqual(result['compression_ratio'], 1.0)


class TestContentSummaryChinese(unittest.TestCase):
    """中文内容摘要测试"""
    
    def setUp(self):
        self.skill = ContentSummarySkill()
    
    def test_chinese_text_summarization(self):
        """测试中文文本摘要"""
        text = """
        中国是世界上人口最多的国家。北京是中国的首都，拥有超过 2000 万人口。
        上海是中国的经济中心，也是最大的城市之一。广州位于中国南部，是重要的商业中心。
        深圳是中国的科技中心，许多高科技公司都聚集在这里。
        """
        
        result = self.skill.execute('summarize', text, ratio=0.5)
        
        self.assertTrue(result['success'])
        self.assertIn('summary', result)
    
    def test_chinese_keywords(self):
        """测试中文关键词提取"""
        text = """
        人工智能技术正在快速发展。机器学习是人工智能的核心技术之一。
        深度学习是机器学习的重要分支。神经网络是深度学习的基础。
        """
        
        result = self.skill.execute('keywords', text, top_k=5)
        
        self.assertTrue(result['success'])
        self.assertIn('keywords', result)
        
        # 应该包含相关关键词
        keywords_text = ' '.join(result['keywords'])
        self.assertTrue(
            '智能' in keywords_text or 
            '学习' in keywords_text or 
            '技术' in keywords_text
        )


if __name__ == '__main__':
    unittest.main()
