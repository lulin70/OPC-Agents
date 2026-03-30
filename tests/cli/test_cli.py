import unittest
import sys
import os
from unittest.mock import patch

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli.cli import CommandLineInterface

class TestCommandLineInterface(unittest.TestCase):
    def setUp(self):
        self.cli = CommandLineInterface()
    
    @patch('sys.argv', ['cli.py', 'system', 'info'])
    def test_system_info(self):
        """测试系统信息命令"""
        with patch('builtins.print') as mock_print:
            self.cli.run()
            # 验证print被调用，并且包含系统信息
            mock_print.assert_any_call("System information:")
            mock_print.assert_any_call("OPC-Agents Version: 1.0.0")
    
    @patch('sys.argv', ['cli.py', 'system', 'status'])
    def test_system_status(self):
        """测试系统状态命令"""
        with patch('builtins.print') as mock_print:
            self.cli.run()
            mock_print.assert_any_call("Checking system status...")
            mock_print.assert_any_call("System is running normally")
    
    @patch('sys.argv', ['cli.py', 'model', 'list'])
    def test_model_list(self):
        """测试模型列表命令"""
        with patch('builtins.print') as mock_print:
            self.cli.run()
            mock_print.assert_any_call("Listing all models...")

if __name__ == '__main__':
    unittest.main()