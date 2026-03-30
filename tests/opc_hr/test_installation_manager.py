import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.installation_manager import InstallationManager

class TestInstallationManager(unittest.TestCase):
    def setUp(self):
        self.installation_manager = InstallationManager()
    
    def test_install_dependencies(self):
        """测试安装依赖功能"""
        dependencies = ["requests", "flask"]
        result = self.installation_manager.install_dependencies(dependencies)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
    
    def test_check_dependencies(self):
        """测试检查依赖功能"""
        result = self.installation_manager.check_dependencies()
        self.assertIsInstance(result, dict)
        self.assertIn("total_required", result)
        self.assertIn("missing", result)
    
    def test_optimize_installation(self):
        """测试优化安装功能"""
        result = self.installation_manager.optimize_installation()
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertIn("actions", result)

if __name__ == '__main__':
    unittest.main()