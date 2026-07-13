"""Tests for opc_manager.mcp_protocol module — skill tool discovery and routing.

Coverage dimensions:
- Happy Path: tool discovery, skill→MCP tool mapping, skill tool execution
- Error Case: SkillRegistry unavailable, execution failure, unknown tool
- Boundary: frozen/disabled skills skipped, name conflict with base tools,
  empty inputs, missing required params
- Configuration: get_stats reflects skill tool count
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

from opc_manager.mcp_protocol import (
    MCPServer,
    MCPTool,
)
from opc_manager.skill_models import Skill, SkillCategory, SkillInput, SkillOutput

# ---------------------------------------------------------------------------
# Real fake classes (project convention: no MagicMock for domain objects)
# ---------------------------------------------------------------------------


class FakeSkillRegistry:
    """Real fake SkillRegistry with configurable skill list and async execute_skill."""

    def __init__(self, skills: Optional[List[Skill]] = None) -> None:
        self._skills = skills or []
        self._execute_calls: List[Dict[str, Any]] = []
        self._execute_result: Dict[str, Any] = {
            "success": True,
            "data": {"content": "skill result content"},
        }

    def list_all_skills(self) -> List[Skill]:
        return list(self._skills)

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        for s in self._skills:
            if s.skill_id == skill_id:
                return s
        return None

    def find_by_intent(self, intent_text: str) -> List[Skill]:
        return []

    def set_execute_result(self, result: Dict[str, Any]) -> None:
        self._execute_result = result

    async def execute_skill(
        self, skill_id: str, context: Any = None, **kwargs: Any
    ) -> Dict[str, Any]:
        self._execute_calls.append(
            {"skill_id": skill_id, "context": context, "kwargs": kwargs}
        )
        return self._execute_result

    @property
    def execute_calls(self) -> List[Dict[str, Any]]:
        return self._execute_calls


def _make_skill(
    skill_id: str = "test_skill",
    name: str = "Test Skill",
    description: str = "A test skill",
    category: SkillCategory = SkillCategory.UTILITY,
    inputs: Optional[List[SkillInput]] = None,
    enabled: bool = True,
    frozen: Any = False,
) -> Skill:
    """Factory for creating Skill instances with a no-op execute callable."""
    if inputs is None:
        inputs = [SkillInput(name="goal", type="str", description="Execution goal")]
    return Skill(
        skill_id=skill_id,
        name=name,
        description=description,
        category=category,
        inputs=inputs,
        outputs=[SkillOutput(name="result", type="dict", description="Result")],
        execute=lambda **kw: {"content": "ok"},
        enabled=enabled,
        frozen=frozen,
    )


# ---------------------------------------------------------------------------
# Tests: _build_input_schema
# ---------------------------------------------------------------------------


class TestBuildInputSchema:
    """Test MCPServer._build_input_schema — SkillInput → JSON Schema mapping."""

    def test_maps_required_string_param(self):
        """Verify: required str param becomes string type in required list."""
        server = MCPServer()
        skill = _make_skill(
            inputs=[SkillInput(name="query", type="str", description="Search query")]
        )
        schema = server._build_input_schema(skill)
        assert schema["type"] == "object"
        assert schema["properties"]["query"] == {
            "type": "string",
            "description": "Search query",
        }
        assert "query" in schema["required"]

    def test_maps_optional_int_param_with_default(self):
        """Verify: optional int param with default includes default in schema."""
        server = MCPServer()
        skill = _make_skill(
            inputs=[
                SkillInput(
                    name="max_results",
                    type="int",
                    required=False,
                    default=10,
                    description="Max results",
                )
            ]
        )
        schema = server._build_input_schema(skill)
        assert schema["properties"]["max_results"]["type"] == "integer"
        assert schema["properties"]["max_results"]["default"] == 10
        assert "max_results" not in schema["required"]

    def test_maps_all_python_types(self):
        """Verify: all Python type strings map to correct JSON Schema types."""
        server = MCPServer()
        type_pairs = [
            ("str", "string"),
            ("int", "integer"),
            ("float", "number"),
            ("bool", "boolean"),
            ("dict", "object"),
            ("list", "array"),
        ]
        for py_type, json_type in type_pairs:
            skill = _make_skill(inputs=[SkillInput(name="param", type=py_type)])
            schema = server._build_input_schema(skill)
            assert (
                schema["properties"]["param"]["type"] == json_type
            ), f"Failed for {py_type} → {json_type}"

    def test_unknown_type_falls_back_to_string(self):
        """Verify: unrecognized type defaults to string."""
        server = MCPServer()
        skill = _make_skill(inputs=[SkillInput(name="param", type="custom_type")])
        schema = server._build_input_schema(skill)
        assert schema["properties"]["param"]["type"] == "string"

    def test_empty_inputs_produces_empty_schema(self):
        """Verify: skill with no inputs produces empty properties."""
        server = MCPServer()
        skill = _make_skill(inputs=[])
        schema = server._build_input_schema(skill)
        assert schema["properties"] == {}
        assert schema["required"] == []


# ---------------------------------------------------------------------------
# Tests: _skill_to_mcp_tool
# ---------------------------------------------------------------------------


class TestSkillToMcpTool:
    """Test MCPServer._skill_to_mcp_tool — Skill → MCPTool conversion."""

    def test_converts_basic_skill(self):
        """Verify: skill fields map to MCPTool fields correctly."""
        server = MCPServer()
        skill = _make_skill(
            skill_id="search",
            name="搜索",
            description="搜索相关信息",
        )
        tool = server._skill_to_mcp_tool(skill)
        assert isinstance(tool, MCPTool)
        assert tool.name == "search"
        assert tool.description == "搜索相关信息"

    def test_uses_fallback_description_when_empty(self):
        """Verify: empty description falls back to generated description."""
        server = MCPServer()
        skill = _make_skill(
            skill_id="my_skill",
            name="My Skill",
            description="",
        )
        tool = server._skill_to_mcp_tool(skill)
        assert "My Skill" in tool.description

    def test_input_schema_is_built(self):
        """Verify: input_schema is populated from skill inputs."""
        server = MCPServer()
        skill = _make_skill(
            inputs=[
                SkillInput(name="goal", type="str", description="Goal"),
                SkillInput(name="count", type="int", required=False),
            ]
        )
        tool = server._skill_to_mcp_tool(skill)
        assert "goal" in tool.input_schema["properties"]
        assert "count" in tool.input_schema["properties"]
        assert "goal" in tool.input_schema["required"]


# ---------------------------------------------------------------------------
# Tests: _discover_tools_from_registry
# ---------------------------------------------------------------------------


class TestDiscoverToolsFromRegistry:
    """Test MCPServer._discover_tools_from_registry — auto tool registration."""

    def test_discovers_skills_as_tools(self):
        """Verify: enabled skills from registry become MCP tools."""
        skills = [
            _make_skill(skill_id="search", name="搜索"),
            _make_skill(skill_id="email", name="邮件"),
            _make_skill(skill_id="finance", name="财务"),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        assert "search" in server._tools
        assert "email" in server._tools
        assert "finance" in server._tools
        assert "search" in server._skill_tool_names
        assert "email" in server._skill_tool_names
        assert "finance" in server._skill_tool_names

    def test_skips_frozen_skills(self):
        """Verify: frozen=True skills are not registered as tools."""
        skills = [
            _make_skill(skill_id="active_skill", frozen=False),
            _make_skill(skill_id="frozen_skill", frozen=True),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        assert "active_skill" in server._tools
        assert "frozen_skill" not in server._tools
        assert "frozen_skill" not in server._skill_tool_names

    def test_skips_disabled_skills(self):
        """Verify: enabled=False skills are not registered as tools."""
        skills = [
            _make_skill(skill_id="enabled_skill", enabled=True),
            _make_skill(skill_id="disabled_skill", enabled=False),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        assert "enabled_skill" in server._tools
        assert "disabled_skill" not in server._tools

    def test_base_tools_take_precedence_on_name_conflict(self):
        """Verify: skill_id colliding with base tool name is skipped."""
        skills = [
            _make_skill(skill_id="execute_task", name="Conflict"),
            _make_skill(skill_id="unique_skill", name="Unique"),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        # Base tool 'execute_task' should still exist but NOT be in skill_tool_names
        assert "execute_task" in server._tools
        assert "execute_task" not in server._skill_tool_names
        assert "unique_skill" in server._skill_tool_names

    def test_no_skill_registry_discovers_nothing(self):
        """Verify: skill_registry=None does not crash and discovers no tools."""
        server = MCPServer(skill_registry=None)
        # Only base tools should exist
        assert len(server._skill_tool_names) == 0
        assert "execute_task" in server._tools

    def test_skips_semi_frozen_skills(self):
        """Verify: frozen='semi' skills are still registered (not fully frozen)."""
        skills = [
            _make_skill(skill_id="semi_frozen", frozen="semi"),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        # 'semi' is falsy when checked with `is True`, so it should be registered
        assert "semi_frozen" in server._tools

    def test_registry_listing_failure_is_handled(self):
        """Verify: list_all_skills raising exception doesn't crash discovery."""
        registry = FakeSkillRegistry()
        registry.list_all_skills = MagicMock(side_effect=RuntimeError("DB error"))
        server = MCPServer(skill_registry=registry)

        # Should not crash, base tools should still exist
        assert "execute_task" in server._tools
        assert len(server._skill_tool_names) == 0


# ---------------------------------------------------------------------------
# Tests: _handle_tools_call — skill tool routing
# ---------------------------------------------------------------------------


class TestSkillToolExecution:
    """Test MCPServer._handle_tools_call routing to SkillRegistry."""

    def test_skill_tool_routes_to_execute_skill(self):
        """Verify: calling a skill-based tool invokes execute_skill with correct args."""
        skills = [_make_skill(skill_id="search", name="搜索")]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "search",
                    "arguments": {"goal": "find something"},
                },
            }
        )

        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["content"][0]["text"] == "skill result content"
        assert len(registry.execute_calls) == 1
        assert registry.execute_calls[0]["skill_id"] == "search"
        assert registry.execute_calls[0]["kwargs"]["goal"] == "find something"

    def test_skill_tool_execution_failure_returns_error(self):
        """Verify: execute_skill returning failure produces isError response."""
        skills = [_make_skill(skill_id="failing_skill")]
        registry = FakeSkillRegistry(skills=skills)
        registry.set_execute_result({"success": False, "error": "Skill not available"})
        server = MCPServer(skill_registry=registry)

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 2,
                "params": {
                    "name": "failing_skill",
                    "arguments": {"goal": "test"},
                },
            }
        )

        assert response["result"]["isError"] is True
        assert "Skill not available" in response["result"]["content"][0]["text"]

    def test_skill_tool_with_dict_data_no_content_key(self):
        """Verify: skill returning dict without 'content' key is JSON-serialized."""
        skills = [_make_skill(skill_id="data_skill")]
        registry = FakeSkillRegistry(skills=skills)
        registry.set_execute_result(
            {"success": True, "data": {"results": [1, 2, 3], "count": 3}}
        )
        server = MCPServer(skill_registry=registry)

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 3,
                "params": {
                    "name": "data_skill",
                    "arguments": {"goal": "test"},
                },
            }
        )

        text = response["result"]["content"][0]["text"]
        parsed = json.loads(text)
        assert parsed["results"] == [1, 2, 3]
        assert parsed["count"] == 3

    def test_missing_required_param_returns_error(self):
        """Verify: missing required parameter produces error before execution."""
        skills = [
            _make_skill(
                skill_id="strict_skill",
                inputs=[
                    SkillInput(name="goal", type="str", required=True),
                ],
            )
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 4,
                "params": {
                    "name": "strict_skill",
                    "arguments": {},
                },
            }
        )

        assert response["result"]["isError"] is True
        assert (
            "Missing required parameter: goal"
            in response["result"]["content"][0]["text"]
        )
        assert len(registry.execute_calls) == 0

    def test_base_tool_still_works_after_discovery(self):
        """Verify: base tool execute_task still works alongside skill tools."""
        skills = [_make_skill(skill_id="custom_skill")]
        registry = FakeSkillRegistry(skills=skills)
        task_engine = MagicMock()
        task_result = MagicMock()
        task_result.content = "task engine result"
        task_engine.execute.return_value = task_result
        server = MCPServer(skill_registry=registry, task_engine=task_engine)

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 5,
                "params": {
                    "name": "execute_task",
                    "arguments": {"user_input": "do something"},
                },
            }
        )

        # execute_task falls back to task_engine since find_by_intent returns []
        text = response["result"]["content"][0]["text"]
        assert "task engine result" in text


# ---------------------------------------------------------------------------
# Tests: tools/list and get_stats
# ---------------------------------------------------------------------------


class TestToolsListAndStats:
    """Test that tools/list includes discovered skills and get_stats reports counts."""

    def test_tools_list_includes_skill_tools(self):
        """Verify: tools/list returns both base tools and skill-based tools."""
        skills = [
            _make_skill(skill_id="search", name="搜索"),
            _make_skill(skill_id="email", name="邮件"),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        response = server.handle_request(
            {"jsonrpc": "2.0", "method": "tools/list", "id": 1, "params": {}}
        )

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "execute_task" in tool_names  # base tool
        assert "search" in tool_names  # skill tool
        assert "email" in tool_names  # skill tool

    def test_get_stats_reports_skill_tool_count(self):
        """Verify: get_stats includes skill_tools count."""
        skills = [
            _make_skill(skill_id="search"),
            _make_skill(skill_id="email"),
            _make_skill(skill_id="finance"),
        ]
        registry = FakeSkillRegistry(skills=skills)
        server = MCPServer(skill_registry=registry)

        stats = server.get_stats()
        assert stats["skill_tools"] == 3
        # Total tools = 4 base + 3 skill = 7
        assert stats["tools"] == 7

    def test_get_stats_zero_skill_tools_without_registry(self):
        """Verify: get_stats reports 0 skill tools when no registry."""
        server = MCPServer(skill_registry=None)
        stats = server.get_stats()
        assert stats["skill_tools"] == 0
        assert stats["tools"] == 4  # 4 base tools
