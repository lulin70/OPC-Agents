import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from model_integration.model_manager import ModelManager

class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.model_manager = ModelManager()
        # 注册一个测试模型
        self.model_manager.register_model("test_model", "local", {"api_key": "test_key", "base_url": "https://api.example.com"})
    
    def test_register_model(self):
        """测试注册模型功能"""
        model_name = "test_model_2"
        model_type = "local"
        config = {"api_key": "test_key", "base_url": "https://api.example.com"}
        # 测试方法是否能正常调用，不关心返回值
        try:
            self.model_manager.register_model(model_name, model_type, config)
            # 如果没有抛出异常，测试通过
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"注册模型失败: {e}")
    
    def test_set_current_model(self):
        """测试设置当前模型功能"""
        model_name = "test_model"
        # 测试方法是否能正常调用，不关心返回值
        try:
            self.model_manager.set_current_model(model_name)
            # 如果没有抛出异常，测试通过
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"设置当前模型失败: {e}")
    
    def test_generate(self):
        """测试生成文本功能"""
        # 先设置当前模型
        self.model_manager.set_current_model("test_model")
        prompt = "Hello, world!"
        result = self.model_manager.generate(prompt)
        self.assertIsInstance(result, str)
    
    def test_chat(self):
        """测试聊天功能"""
        # 先设置当前模型
        self.model_manager.set_current_model("test_model")
        messages = [{"role": "user", "content": "Hello!"}]
        result = self.model_manager.chat(messages)
        self.assertIsInstance(result, str)
    
    def test_list_models(self):
        """测试列出所有模型功能"""
        result = self.model_manager.list_models()
        self.assertIsInstance(result, list)

if __name__ == '__main__':
    unittest.main()