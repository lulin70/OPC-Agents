import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_hr.mcp_integration import MCPIntegration

class TestMCPIntegration(unittest.TestCase):
    def setUp(self):
        self.mcp_integration = MCPIntegration()

    def test_verify_skill(self):
        skill_data = {"name": "test_skill", "version": "1.0.0"}
        result = self.mcp_integration.verify_skill(skill_data)
        self.assertIsInstance(result, dict)
        self.assertIn("verified", result)
        self.assertIn("security_score", result)
        self.assertIn("reliability_score", result)
        self.assertIn("code_scan", result)
        self.assertIn("trusted", result)

    def test_verify_agent(self):
        agent_data = {"name": "test_agent", "repo_full_name": "unknown/repo", "stars": 50, "forks": 10, "license": "MIT", "description": "test", "language": "Python"}
        result = self.mcp_integration._verify_resource(agent_data, "agent")
        self.assertIsInstance(result, dict)
        self.assertIn("verified", result)
        self.assertIn("security_score", result)

    def test_trusted_source(self):
        agent_data = {"name": "test", "repo_full_name": "microsoft/autogen", "stars": 100, "forks": 50, "license": "MIT", "description": "test", "language": "Python"}
        result = self.mcp_integration._verify_resource(agent_data, "agent")
        self.assertTrue(result.get("trusted", False))
        self.assertEqual(result.get("security_score"), 1.0)

    def test_import_skill_no_verify(self):
        result = self.mcp_integration.import_skill("nonexistent/repo")
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("success", False))

    def test_load_trusted_sources(self):
        trusted = self.mcp_integration._load_trusted_sources()
        self.assertIsInstance(trusted, set)
        self.assertIn("microsoft/autogen", trusted)

    def test_scan_code_safety(self):
        result = self.mcp_integration._scan_code_safety("nonexistent/repo")
        self.assertIsInstance(result, dict)
        self.assertIn("scanned", result)
        self.assertIn("risk_level", result)

if __name__ == '__main__':
    unittest.main()
