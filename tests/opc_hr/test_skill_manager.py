import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.skill_manager import SkillManager

class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.skill_manager = SkillManager()
    
    def test_register_skill(self):
        """测试注册技能功能"""
        skill_name = "test_skill"
        skill_path = "/path/to/skill"
        result = self.skill_manager.register_skill(skill_name, skill_path)
        self.assertIsInstance(result, bool)
    
    def test_record_skill_usage(self):
        """测试记录技能使用功能"""
        skill_name = "test_skill"
        agent_id = "test_agent"
        success = True
        duration = 1.5
        result = self.skill_manager.record_skill_usage(skill_name, agent_id, success, duration)
        self.assertIsInstance(result, bool)
    
    def test_generate_skill_recommendations(self):
        """测试生成技能推荐功能"""
        agent_name = "test_agent"
        result = self.skill_manager.generate_skill_recommendations(agent_name)
        self.assertIsInstance(result, list)
        # 确保返回的是技能推荐列表
        for recommendation in result:
            self.assertIsInstance(recommendation, dict)
            self.assertIn("skill_name", recommendation)
            self.assertIn("priority", recommendation)

if __name__ == '__main__':
    unittest.main()