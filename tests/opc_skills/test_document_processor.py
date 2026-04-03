"""
文档处理技能单元测试
"""

import unittest
import os
import tempfile
from opc_skills.document_processor import DocumentProcessorSkill


class TestDocumentProcessorSkill(unittest.TestCase):
    """文档处理技能测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.skill = DocumentProcessorSkill()
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
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
        self.assertIn('file_path', input_schema)
        
        # 验证操作类型
        supported_ops = ['read_pdf', 'read_word', 'read_excel', 'write_word', 'write_excel']
        self.assertEqual(input_schema['operation']['enum'], supported_ops)
    
    def test_invalid_operation(self):
        """测试无效操作"""
        result = self.skill.execute('invalid_op', 'test.txt')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('supported_operations', result)
    
    def test_write_word(self):
        """测试创建 Word 文档"""
        output_path = os.path.join(self.test_dir, 'test.docx')
        content = "这是第一段。\n\n这是第二段。"
        
        result = self.skill.execute(
            'write_word',
            output_path,
            content=content,
            title='测试文档'
        )
        
        # 验证结果
        if 'error' in result and '缺少依赖' in result['error']:
            self.skipTest(result['error'])
        
        self.assertTrue(result['success'])
        self.assertEqual(result['file_path'], output_path)
        
        # 验证文件存在
        self.assertTrue(os.path.exists(output_path))
    
    def test_write_excel(self):
        """测试创建 Excel 文件"""
        output_path = os.path.join(self.test_dir, 'test.xlsx')
        data = [
            {'姓名': '张三', '年龄': 25, '城市': '北京'},
            {'姓名': '李四', '年龄': 30, '城市': '上海'},
        ]
        
        result = self.skill.execute(
            'write_excel',
            output_path,
            data=data
        )
        
        # 验证结果
        if 'error' in result and '缺少依赖' in result['error']:
            self.skipTest(result['error'])
        
        self.assertTrue(result['success'])
        self.assertEqual(result['file_path'], output_path)
        
        # 验证文件存在
        self.assertTrue(os.path.exists(output_path))
        
        # 验证数据
        self.assertEqual(result.get('rows'), 2)
        self.assertEqual(result.get('columns'), 3)
    
    def test_read_excel(self):
        """测试读取 Excel 文件"""
        # 先创建测试文件
        output_path = os.path.join(self.test_dir, 'test_read.xlsx')
        data = [
            {'A': 1, 'B': 2, 'C': 3},
            {'A': 4, 'B': 5, 'C': 6},
        ]
        
        create_result = self.skill.execute('write_excel', output_path, data=data)
        
        if not create_result['success']:
            if 'error' in create_result and '缺少依赖' in create_result['error']:
                self.skipTest(create_result['error'])
            else:
                self.fail("创建测试文件失败")
        
        # 读取文件
        result = self.skill.execute('read_excel', output_path)
        
        # 验证结果
        if 'error' in result and '缺少依赖' in result['error']:
            self.skipTest(result['error'])
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 2)
        self.assertEqual(result['shape'], [2, 3])
        self.assertEqual(result['columns'], ['A', 'B', 'C'])


class TestDocumentProcessorPDF(unittest.TestCase):
    """PDF 处理测试（需要依赖）"""
    
    @unittest.skip("需要安装 pdfplumber")
    def test_read_pdf(self):
        """测试读取 PDF"""
        skill = DocumentProcessorSkill()
        
        # 需要一个真实的 PDF 文件
        # TODO: 添加测试 PDF 文件
        pass


if __name__ == '__main__':
    unittest.main()
