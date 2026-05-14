"""
v0.1.8 gamma 集成测试 — G1-G9 全任务覆盖

覆盖维度：
- Happy Path: 正常输入→预期输出
- Error Case: 非法输入/空值/越界
- Boundary: 空字符串/None/最大值
- Integration: 模块间协作场景
- Security: 权限/注入/越权
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from opc_manager.task_engine_adapter import (
    TaskEngineAdapter,
    INTENT_TO_TASK_MAP,
    SKILL_TO_TASK_MAP,
)
from opc_manager.strategist_brain import IntentType
from opc_manager.task_engine_v3 import TaskType


class TestTaskEngineAdapter(unittest.TestCase):
    """G1: TaskEngineAdapter 测试"""

    def test_intent_to_task_mapping_completeness(self):
        for intent in IntentType:
            self.assertIn(intent, INTENT_TO_TASK_MAP, f"IntentType.{intent.name} 未映射")

    def test_skill_to_task_mapping_known_skills(self):
        known_skills = ["search", "analysis", "content_generation", "execute_operation",
                        "send_notification", "intent_analysis", "output_result"]
        for skill in known_skills:
            self.assertIn(skill, SKILL_TO_TASK_MAP, f"skill_id '{skill}' 未映射")

    def test_execute_skill_unknown_defaults_to_general_chat(self):
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        adapter.task_engine.execute = MagicMock()
        adapter.task_engine.execute.return_value = MagicMock(
            success=True, content="test", task_type=TaskType.GENERAL_CHAT,
            sources=[], execution_time_ms=100, error=None,
            deliverable_format="markdown", search_results=[]
        )
        result = adapter.execute_skill("unknown_skill_xyz", {"query": "test"})
        self.assertTrue(result["success"])

    def test_execute_skill_no_input_returns_error(self):
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        result = adapter.execute_skill("search", {})
        self.assertFalse(result["success"])
        self.assertIn("No input", result["error"])

    def test_dict_to_task_result_roundtrip(self):
        from opc_manager.task_engine_adapter import TaskEngineAdapter as TEA
        from opc_manager.task_engine_v3 import TaskResult
        original = TaskResult(
            success=True, content="hello", task_type=TaskType.INFO_COLLECTION,
            sources=["src1"], execution_time_ms=1500, error=None,
            deliverable_format="markdown", search_results=[]
        )
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        data_dict = adapter._task_result_to_dict(original, "search")
        restored = TEA.dict_to_task_result(data_dict)
        self.assertEqual(restored.success, original.success)
        self.assertEqual(restored.content, original.content)
        self.assertEqual(restored.task_type, original.task_type)

    def test_execute_by_intent_mapping(self):
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        adapter.task_engine.execute = MagicMock()
        adapter.task_engine.execute.return_value = MagicMock(
            success=True, content="analysis result", task_type=TaskType.DATA_ANALYSIS,
            sources=[], execution_time_ms=200, error=None,
            deliverable_format="markdown", search_results=[]
        )
        result = adapter.execute_by_intent(IntentType.ANALYSIS, "分析竞品")
        self.assertTrue(result["success"])

    def test_execute_skill_async(self):
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        adapter.task_engine.execute = MagicMock()
        adapter.task_engine.execute.return_value = MagicMock(
            success=True, content="async result", task_type=TaskType.CONTENT_GENERATION,
            sources=[], execution_time_ms=50, error=None,
            deliverable_format="markdown", search_results=[]
        )
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                adapter.execute_skill_async("content_generation", {"query": "test"})
            )
            self.assertTrue(result["success"])
        finally:
            loop.close()

    def test_adapter_stats(self):
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        stats = adapter.get_stats()
        self.assertIn("execution_count", stats)
        self.assertIn("task_engine_initialized", stats)


class TestSkillMarketplace(unittest.TestCase):
    """G6: 技能市场API测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_marketplace_")
        from opc_manager.skill_marketplace import SkillMarketplace
        self.marketplace = SkillMarketplace(data_dir=self.tmpdir)

    def test_create_api_key(self):
        from opc_manager.skill_marketplace import PermissionLevel
        key = self.marketplace.create_api_key(
            "test_key", [PermissionLevel.READ, PermissionLevel.WRITE]
        )
        self.assertTrue(key.startswith("opc_"))

    def test_authenticate_valid_key(self):
        from opc_manager.skill_marketplace import PermissionLevel
        key = self.marketplace.create_api_key("test", [PermissionLevel.READ])
        key_info = self.marketplace.authenticate(key)
        self.assertIsNotNone(key_info)
        self.assertEqual(key_info.name, "test")

    def test_authenticate_invalid_key(self):
        result = self.marketplace.authenticate("invalid_key")
        self.assertIsNone(result)

    def test_register_skill(self):
        from opc_manager.skill_marketplace import MarketplaceSkill, PermissionLevel
        key = self.marketplace.create_api_key("admin", [PermissionLevel.WRITE])
        skill = MarketplaceSkill(
            skill_id="test_skill", name="Test Skill", description="A test skill",
            version="1.0", category="test", author="tester"
        )
        result = self.marketplace.register_skill(skill, key)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "pending")

    def test_register_skill_no_permission(self):
        from opc_manager.skill_marketplace import MarketplaceSkill, PermissionLevel
        key = self.marketplace.create_api_key("reader", [PermissionLevel.READ])
        skill = MarketplaceSkill(
            skill_id="test_skill", name="Test", description="Test",
            version="1.0", category="test", author="tester"
        )
        result = self.marketplace.register_skill(skill, key)
        self.assertFalse(result["success"])

    def test_discover_skills(self):
        from opc_manager.skill_marketplace import MarketplaceSkill, PermissionLevel, SkillStatus
        key = self.marketplace.create_api_key("admin", [PermissionLevel.WRITE])
        skill = MarketplaceSkill(
            skill_id="discover_test", name="Discoverable", description="Can be found",
            version="1.0", category="analytics", author="tester"
        )
        self.marketplace.register_skill(skill, key)
        self.marketplace.approve_skill("discover_test", key)
        results = self.marketplace.discover_skills(category="analytics")
        self.assertEqual(len(results), 1)

    def test_execute_skill_not_approved(self):
        from opc_manager.skill_marketplace import MarketplaceSkill, PermissionLevel
        key = self.marketplace.create_api_key("admin", [PermissionLevel.WRITE, PermissionLevel.EXECUTE])
        skill = MarketplaceSkill(
            skill_id="pending_skill", name="Pending", description="Not approved",
            version="1.0", category="test", author="tester"
        )
        self.marketplace.register_skill(skill, key)
        result = self.marketplace.execute_skill("pending_skill", {}, key)
        self.assertFalse(result["success"])

    def test_marketplace_stats(self):
        stats = self.marketplace.get_stats()
        self.assertIn("total_skills", stats)
        self.assertIn("total_api_keys", stats)


class TestMCPProtocol(unittest.TestCase):
    """G7: MCP协议测试"""

    def setUp(self):
        from opc_manager.mcp_protocol import MCPServer
        self.server = MCPServer()

    def test_initialize(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}
        })
        self.assertEqual(response["result"]["serverInfo"]["name"], "opc-agents")

    def test_tools_list(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
        })
        tools = response["result"]["tools"]
        self.assertGreaterEqual(len(tools), 4)

    def test_resources_list(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}
        })
        resources = response["result"]["resources"]
        self.assertGreaterEqual(len(resources), 3)

    def test_prompts_list(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}
        })
        prompts = response["result"]["prompts"]
        self.assertGreaterEqual(len(prompts), 2)

    def test_unknown_method(self):
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 5, "method": "unknown/method", "params": {}
        })
        self.assertIn("error", response)

    def test_register_custom_tool(self):
        from opc_manager.mcp_protocol import MCPTool
        self.server.register_tool(MCPTool(
            name="custom_tool", description="Custom", input_schema={"type": "object"}
        ))
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}
        })
        tool_names = [t["name"] for t in response["result"]["tools"]]
        self.assertIn("custom_tool", tool_names)

    def test_server_stats(self):
        stats = self.server.get_stats()
        self.assertIn("tools", stats)
        self.assertIn("protocol_version", stats)


class TestPluginSystem(unittest.TestCase):
    """G8: 插件系统测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_plugins_")
        from opc_manager.plugin_system import PluginManager
        self.manager = PluginManager(plugin_dir=self.tmpdir)

    def test_register_plugin(self):
        from opc_manager.plugin_system import PluginManifest
        manifest = PluginManifest(
            plugin_id="test_plugin", name="Test", version="1.0",
            description="Test plugin", author="tester", entry_point="test.py"
        )
        result = self.manager.register_plugin(manifest)
        self.assertTrue(result["success"])

    def test_register_duplicate_plugin(self):
        from opc_manager.plugin_system import PluginManifest
        manifest = PluginManifest(
            plugin_id="dup_plugin", name="Dup", version="1.0",
            description="Duplicate", author="tester", entry_point="dup.py"
        )
        self.manager.register_plugin(manifest)
        result = self.manager.register_plugin(manifest)
        self.assertFalse(result["success"])

    def test_initialize_missing_entry_point(self):
        from opc_manager.plugin_system import PluginManifest
        manifest = PluginManifest(
            plugin_id="missing_plugin", name="Missing", version="1.0",
            description="Missing entry", author="tester", entry_point="nonexistent.py"
        )
        self.manager.register_plugin(manifest)
        result = self.manager.initialize_plugin("missing_plugin")
        self.assertFalse(result["success"])

    def test_list_plugins(self):
        from opc_manager.plugin_system import PluginManifest
        manifest = PluginManifest(
            plugin_id="list_test", name="List", version="1.0",
            description="List test", author="tester", entry_point="list.py"
        )
        self.manager.register_plugin(manifest)
        plugins = self.manager.list_plugins()
        self.assertEqual(len(plugins), 1)

    def test_unload_plugin(self):
        from opc_manager.plugin_system import PluginManifest
        manifest = PluginManifest(
            plugin_id="unload_test", name="Unload", version="1.0",
            description="Unload test", author="tester", entry_point="unload.py"
        )
        self.manager.register_plugin(manifest)
        result = self.manager.unload_plugin("unload_test")
        self.assertTrue(result["success"])

    def test_sandbox_permission_check(self):
        from opc_manager.plugin_system import PluginSandbox, Permission
        sandbox = PluginSandbox(allowed_permissions=[Permission.FILESYSTEM])
        self.assertTrue(sandbox.check_permission(Permission.FILESYSTEM))
        self.assertFalse(sandbox.check_permission(Permission.NETWORK))

    def test_sandbox_access_log(self):
        from opc_manager.plugin_system import PluginSandbox, Permission
        sandbox = PluginSandbox(allowed_permissions=[])
        sandbox.log_access("test_plugin", "import", "os", False)
        log = sandbox.get_access_log()
        self.assertEqual(len(log), 1)
        self.assertFalse(log[0]["allowed"])

    def test_plugin_stats(self):
        stats = self.manager.get_stats()
        self.assertIn("total_plugins", stats)
        self.assertIn("plugin_dir", stats)


class TestSkillEditor(unittest.TestCase):
    """G9: 技能编辑器测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="test_skills_")
        from opc_manager.skill_editor import SkillEditor
        self.editor = SkillEditor(skills_dir=self.tmpdir)

    def test_create_skill(self):
        from opc_manager.skill_editor import CustomSkill, SkillParameter, ParameterType
        skill = CustomSkill(
            skill_id="test_skill", name="Test Skill", description="A test",
            input_parameters=[SkillParameter(name="topic", param_type=ParameterType.STRING, description="Topic")]
        )
        result = self.editor.create_skill(skill)
        self.assertTrue(result["success"])

    def test_create_duplicate_skill(self):
        from opc_manager.skill_editor import CustomSkill
        skill = CustomSkill(skill_id="dup", name="Dup", description="Duplicate")
        self.editor.create_skill(skill)
        result = self.editor.create_skill(skill)
        self.assertFalse(result["success"])

    def test_update_skill(self):
        from opc_manager.skill_editor import CustomSkill
        skill = CustomSkill(skill_id="update_me", name="Original", description="Original desc")
        self.editor.create_skill(skill)
        result = self.editor.update_skill("update_me", {"name": "Updated", "description": "New desc"})
        self.assertTrue(result["success"])
        updated = self.editor.get_skill("update_me")
        self.assertEqual(updated["name"], "Updated")

    def test_delete_skill(self):
        from opc_manager.skill_editor import CustomSkill
        skill = CustomSkill(skill_id="delete_me", name="Delete", description="To delete")
        self.editor.create_skill(skill)
        result = self.editor.delete_skill("delete_me")
        self.assertTrue(result["success"])
        self.assertIsNone(self.editor.get_skill("delete_me"))

    def test_preview_skill(self):
        from opc_manager.skill_editor import CustomSkill, SkillParameter, ParameterType
        skill = CustomSkill(
            skill_id="preview_test", name="Preview", description="Preview test",
            template="# {{topic}}\n\nDetails about {{topic}}.",
            input_parameters=[SkillParameter(name="topic", param_type=ParameterType.STRING)]
        )
        self.editor.create_skill(skill)
        result = self.editor.preview_skill("preview_test", {"topic": "AI"})
        self.assertTrue(result["success"])
        self.assertIn("AI", result["preview"])

    def test_test_skill_missing_params(self):
        from opc_manager.skill_editor import CustomSkill, SkillParameter, ParameterType
        skill = CustomSkill(
            skill_id="test_missing", name="Missing", description="Missing params",
            input_parameters=[SkillParameter(name="required_param", param_type=ParameterType.STRING, required=True)]
        )
        self.editor.create_skill(skill)
        result = self.editor.test_skill("test_missing", {})
        self.assertFalse(result["success"])

    def test_list_skills(self):
        from opc_manager.skill_editor import CustomSkill
        for i in range(3):
            skill = CustomSkill(skill_id=f"list_{i}", name=f"Skill {i}", description=f"Test {i}")
            self.editor.create_skill(skill)
        skills = self.editor.list_skills()
        self.assertEqual(len(skills), 3)

    def test_editor_stats(self):
        stats = self.editor.get_stats()
        self.assertIn("total_skills", stats)
        self.assertIn("skills_dir", stats)


class TestAgentLoopIntegration(unittest.TestCase):
    """G1-G5 集成测试：AgentLoop + TaskEngineAdapter + 超时 + 降级"""

    def test_agent_loop_timeout_constant(self):
        from opc_manager.agent_loop import AGENT_LOOP_TIMEOUT_SECONDS
        self.assertEqual(AGENT_LOOP_TIMEOUT_SECONDS, 60)

    def test_skip_reflect_mode(self):
        os.environ["OPC_SKIP_REFLECT"] = "true"
        try:
            from opc_manager.agent_loop import AgentLoop
            from opc_manager.task_engine_adapter import TaskEngineAdapter
            adapter = TaskEngineAdapter(task_engine=MagicMock())
            adapter.task_engine.execute = MagicMock()
            adapter.task_engine.execute.return_value = MagicMock(
                success=True, content="fast result", task_type=TaskType.GENERAL_CHAT,
                sources=[], execution_time_ms=50, error=None,
                deliverable_format="text", search_results=[]
            )
            loop_instance = AgentLoop(task_engine_adapter=adapter)
            result = asyncio.new_event_loop().run_until_complete(
                loop_instance.run("test fast mode")
            )
            self.assertTrue(result["success"])
        finally:
            os.environ.pop("OPC_SKIP_REFLECT", None)

    def test_agent_loop_with_task_engine_adapter(self):
        from opc_manager.agent_loop import AgentLoop
        from opc_manager.task_engine_adapter import TaskEngineAdapter
        adapter = TaskEngineAdapter(task_engine=MagicMock())
        adapter.task_engine.execute = MagicMock()
        adapter.task_engine.execute.return_value = MagicMock(
            success=True, content="adapter result", task_type=TaskType.CONTENT_GENERATION,
            sources=["src1"], execution_time_ms=100, error=None,
            deliverable_format="markdown", search_results=[]
        )
        loop_instance = AgentLoop(task_engine_adapter=adapter)
        os.environ["OPC_SKIP_REFLECT"] = "true"
        try:
            result = asyncio.new_event_loop().run_until_complete(
                loop_instance.run("test adapter integration")
            )
            self.assertTrue(result["success"])
        finally:
            os.environ.pop("OPC_SKIP_REFLECT", None)


if __name__ == "__main__":
    unittest.main()
