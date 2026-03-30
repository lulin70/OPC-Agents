import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opc_hr.agent_optimizer import AgentOptimizer
from opc_hr.skill_manager import SkillManager
from opc_hr.mcp_integration import MCPIntegration
from opc_hr.installation_manager import InstallationManager
from model_integration.model_manager import ModelManager

class IntegrationTest(unittest.TestCase):
    def setUp(self):
        """设置测试环境"""
        self.agent_optimizer = AgentOptimizer()
        self.skill_manager = SkillManager()
        self.mcp_integration = MCPIntegration()
        self.installation_manager = InstallationManager()
        self.model_manager = ModelManager()
        
        # 注册一个测试模型
        self.model_manager.register_model("test_model", "local", {"api_key": "test_key"})
        self.model_manager.set_current_model("test_model")
    
    def test_agent_skill_integration(self):
        """测试代理和技能管理的集成"""
        # 注册一个技能（即使注册失败也继续测试）
        self.skill_manager.register_skill("test_skill", "/path/to/skill")
        
        # 记录技能使用
        usage_recorded = self.skill_manager.record_skill_usage("test_skill", "test_agent", True, 1.5)
        self.assertTrue(usage_recorded)
        
        # 生成技能推荐
        recommendations = self.skill_manager.generate_skill_recommendations("test_agent")
        self.assertIsInstance(recommendations, list)
    
    def test_agent_optimizer_integration(self):
        """测试代理优化的集成"""
        # 分析代理性能
        agent_data = {"name": "test_agent", "skills": ["test_skill"]}
        analysis_result = self.agent_optimizer.analyze_performance("test_agent", agent_data)
        self.assertIsInstance(analysis_result, dict)
        
        # 生成改进计划
        improvement_plan = self.agent_optimizer.generate_improvement_plan("test_agent", analysis_result)
        self.assertIsInstance(improvement_plan, list)
        
        # 优化代理
        optimization_result = self.agent_optimizer.optimize_agent("test_agent", agent_data)
        self.assertIsInstance(optimization_result, dict)
        self.assertIn("success", optimization_result)
    
    def test_mcp_skill_integration(self):
        """测试MCP和技能管理的集成"""
        # 从MCP获取技能
        skills = self.mcp_integration.fetch_skills()
        self.assertIsInstance(skills, list)
        
        # 验证技能
        if skills:
            skill_data = skills[0]
            verification_result = self.mcp_integration.verify_skill(skill_data)
            self.assertIsInstance(verification_result, dict)
            self.assertIn("verified", verification_result)
    
    def test_model_integration(self):
        """测试模型集成"""
        # 测试模型生成
        prompt = "Hello, world!"
        generate_result = self.model_manager.generate(prompt)
        self.assertIsInstance(generate_result, str)
        
        # 测试模型聊天
        messages = [{"role": "user", "content": "Hello!"}]
        chat_result = self.model_manager.chat(messages)
        self.assertIsInstance(chat_result, str)
    
    def test_installation_integration(self):
        """测试安装管理的集成"""
        # 检查依赖
        check_result = self.installation_manager.check_dependencies()
        self.assertIsInstance(check_result, dict)
        self.assertIn("total_required", check_result)
        
        # 优化安装
        optimize_result = self.installation_manager.optimize_installation()
        self.assertIsInstance(optimize_result, dict)
        self.assertIn("success", optimize_result)

if __name__ == '__main__':
    unittest.main()