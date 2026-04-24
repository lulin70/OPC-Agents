import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opc_hr.agent_optimizer import AgentOptimizer
from opc_hr.skill_manager import SkillManager
from opc_hr.mcp_integration import MCPIntegration
from opc_hr.installation_manager import InstallationManager
from model_integration.model_manager import ModelManager

INTEGRATION_SKIP_REASON = "集成测试需要完整的外部服务环境（MCP服务器、Agent优化器、LLM API），本地CI环境不满足条件"


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.agent_optimizer = AgentOptimizer()
        self.skill_manager = SkillManager()
        self.mcp_integration = MCPIntegration()
        self.installation_manager = InstallationManager()
        self.model_manager = ModelManager()
        self.model_manager.register_model("test_model", "local", {"api_key": "test_key"})
        self.model_manager.set_current_model("test_model")

    @unittest.skip(INTEGRATION_SKIP_REASON)
    def test_agent_skill_integration(self):
        """测试代理和技能管理的集成"""
        self.skill_manager.register_skill("test_skill", "/path/to/skill")
        usage_recorded = self.skill_manager.record_skill_usage("test_skill", "test_agent", True, 1.5)
        self.assertTrue(usage_recorded)
        recommendations = self.skill_manager.generate_skill_recommendations("test_agent")
        self.assertIsInstance(recommendations, list)

    @unittest.skip(INTEGRATION_SKIP_REASON)
    def test_agent_optimizer_integration(self):
        """测试代理优化的集成"""
        agent_data = {"name": "test_agent", "skills": ["test_skill"]}
        analysis_result = self.agent_optimizer.analyze_performance("test_agent", agent_data)
        self.assertIsInstance(analysis_result, dict)
        improvement_plan = self.agent_optimizer.generate_improvement_plan("test_agent", analysis_result)
        self.assertIsInstance(improvement_plan, list)
        optimization_result = self.agent_optimizer.optimize_agent("test_agent", agent_data)
        self.assertIsInstance(optimization_result, dict)
        self.assertIn("success", optimization_result)

    @unittest.skip(INTEGRATION_SKIP_REASON)
    def test_mcp_skill_integration(self):
        """测试MCP和技能管理的集成"""
        skill_data = {"name": "test_skill", "version": "1.0.0"}
        verification_result = self.mcp_integration.verify_skill(skill_data)
        self.assertIsInstance(verification_result, dict)
        self.assertIn("verified", verification_result)
        self.assertIn("security_score", verification_result)
        self.assertIn("code_scan", verification_result)

    @unittest.skip("需要真实LLM API Key才能调用generate/chat，本地测试环境无有效API配置")
    def test_model_integration(self):
        """测试模型集成"""
        prompt = "Hello, world!"
        generate_result = self.model_manager.generate(prompt)
        self.assertIsInstance(generate_result, str)
        messages = [{"role": "user", "content": "Hello!"}]
        chat_result = self.model_manager.chat(messages)
        self.assertIsInstance(chat_result, str)

    @unittest.skip(INTEGRATION_SKIP_REASON)
    def test_installation_integration(self):
        """测试安装管理的集成"""
        check_result = self.installation_manager.check_dependencies()
        self.assertIsInstance(check_result, dict)
        self.assertIn("total_required", check_result)
        optimize_result = self.installation_manager.optimize_installation()
        self.assertIsInstance(optimize_result, dict)
        self.assertIn("success", optimize_result)


if __name__ == '__main__':
    unittest.main()
