import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.mcp_integration import MCPIntegration

class TestMCPIntegration(unittest.TestCase):
    def setUp(self):
        self.mcp_integration = MCPIntegration()
    
    def test_fetch_skills(self):
        """测试从MCP获取技能功能"""
        result = self.mcp_integration.fetch_skills()
        self.assertIsInstance(result, list)
        # 确保返回的是技能列表
        for skill in result:
            self.assertIsInstance(skill, dict)
            self.assertIn("name", skill)
            self.assertIn("version", skill)
    
    def test_verify_skill(self):
        """测试验证技能功能"""
        skill_data = {"name": "test_skill", "version": "1.0.0"}
        result = self.mcp_integration.verify_skill(skill_data)
        self.assertIsInstance(result, dict)
        self.assertIn("skill_name", result)
        self.assertIn("verified", result)
    
    def test_import_skill(self):
        """测试导入技能功能"""
        skill_data = {"name": "test_skill", "version": "1.0.0", "url": "https://example.com/skill"}
        result = self.mcp_integration.import_skill(skill_data)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
    
    def test_update_skill(self):
        """测试更新技能功能"""
        skill_name = "test_skill"
        result = self.mcp_integration.update_skill(skill_name)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)

if __name__ == '__main__':
    unittest.main()