import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.agent_optimizer import AgentOptimizer

class TestAgentOptimizer(unittest.TestCase):
    def setUp(self):
        self.agent_optimizer = AgentOptimizer()
    
    def test_analyze_performance(self):
        """测试代理性能分析功能"""
        agent_id = "test_agent"
        agent_data = {"name": agent_id, "skills": ["test_skill"]}
        result = self.agent_optimizer.analyze_performance(agent_id, agent_data)
        self.assertIsInstance(result, dict)
        self.assertIn("response_time", result)
        self.assertIn("accuracy", result)
    
    def test_generate_improvement_plan(self):
        """测试生成改进计划功能"""
        agent_id = "test_agent"
        analysis_result = {"response_time": 0.5, "accuracy": 0.6, "completeness": 0.5, "relevance": 0.6, "user_satisfaction": 0.5}
        result = self.agent_optimizer.generate_improvement_plan(agent_id, analysis_result)
        self.assertIsInstance(result, list)
        for plan in result:
            self.assertIsInstance(plan, dict)
            self.assertIn("area", plan)
            self.assertIn("suggestion", plan)
            self.assertIn("priority", plan)
    
    def test_optimize_agent(self):
        """测试优化代理功能"""
        agent_id = "test_agent"
        agent_data = {"name": agent_id, "skills": ["test_skill"]}
        result = self.agent_optimizer.optimize_agent(agent_id, agent_data)
        self.assertIsInstance(result, dict)
        self.assertIn("success", result)
        self.assertIn("agent_name", result)
    
    def test_optimize_all_agents(self):
        """测试优化所有代理功能"""
        agents_data = {"agent1": {"name": "agent1", "skills": ["skill1"]}, "agent2": {"name": "agent2", "skills": ["skill2"]}}
        result = self.agent_optimizer.optimize_all_agents(agents_data)
        self.assertIsInstance(result, dict)
        self.assertIn("total_agents", result)
        self.assertIn("optimized_agents", result)

if __name__ == '__main__':
    unittest.main()