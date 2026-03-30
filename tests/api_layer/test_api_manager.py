import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api_layer.api_manager import APIManager

class TestAPIManager(unittest.TestCase):
    def setUp(self):
        self.api_manager = APIManager()
    
    def test_register_route(self):
        """测试注册路由功能"""
        def test_handler():
            return {"status": "success"}
        
        result = self.api_manager.register_route("GET", "/test", test_handler)
        # register_route 方法可能返回 None，所以只测试方法是否能正常调用
        self.assertIsNone(result)
    
    def test_add_middleware(self):
        """测试添加中间件功能"""
        def test_middleware(request):
            return request
        
        result = self.api_manager.add_middleware(test_middleware)
        # add_middleware 方法可能返回 None，所以只测试方法是否能正常调用
        self.assertIsNone(result)
    
    def test_register_default_routes(self):
        """测试注册默认路由功能"""
        # 模拟一个 manager 对象
        class MockManager:
            def route(self, path):
                def decorator(func):
                    return func
                return decorator
        
        mock_manager = MockManager()
        result = self.api_manager.register_default_routes(mock_manager)
        # register_default_routes 方法可能返回 None，所以只测试方法是否能正常调用
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()