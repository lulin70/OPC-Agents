"""
MCPProtocol — Model Context Protocol 支持

兼容微软 Model Context Protocol (MCP) 标准，提供：
- MCP Server端点（工具/资源/提示词模板）
- 工具注册与发现（MCP tools/list → SkillRegistry）
- 资源映射（MCP resources → OPC-Agents deliverables）
- 提示词模板（MCP prompts/list → PersonaManager）

架构位置：
  MCP客户端 → MCPServer → SkillRegistry / TaskEngineV3 / PersonaManager

参考规范：https://spec.modelcontextprotocol.io/specification/2024-11-05/
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "opc-agents"
MCP_SERVER_VERSION = "0.3.28"

# SkillInput.type (Python type string) → JSON Schema type keyword
_PYTHON_TYPE_TO_JSON_SCHEMA: Dict[str, str] = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "dict": "object",
    "object": "object",
    "list": "array",
    "array": "array",
    "Any": "string",
}


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str = "text/markdown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class MCPPrompt:
    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


class MCPServer:

    def __init__(
        self, skill_registry: Optional[Any] = None, task_engine: Optional[Any] = None
    ) -> None:
        self.skill_registry = skill_registry
        self.task_engine = task_engine
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}
        self._skill_tool_names: set = set()
        self._register_default_tools()
        self._discover_tools_from_registry()
        self._register_default_resources()
        self._register_default_prompts()

    def _register_default_tools(self) -> None:
        self._tools["execute_task"] = MCPTool(
            name="execute_task",
            description="Execute a task using OPC-Agents Three-Sage Architecture",
            input_schema={
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "User's task description",
                    },
                    "business_type": {
                        "type": "string",
                        "description": "Business type hint",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["quality", "fast"],
                        "default": "quality",
                    },
                },
                "required": ["user_input"],
            },
        )
        self._tools["search_web"] = MCPTool(
            name="search_web",
            description="Search the web using DuckDuckGo",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        )
        self._tools["analyze_business"] = MCPTool(
            name="analyze_business",
            description="Perform business analysis (SWOT, competitive, market)",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Analysis topic"},
                    "analysis_type": {
                        "type": "string",
                        "enum": ["swot", "competitive", "market"],
                    },
                },
                "required": ["topic"],
            },
        )
        self._tools["generate_content"] = MCPTool(
            name="generate_content",
            description="Generate business content (reports, plans, proposals)",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Content topic"},
                    "content_type": {
                        "type": "string",
                        "enum": ["report", "plan", "proposal", "email"],
                    },
                },
                "required": ["topic"],
            },
        )

    def _register_default_resources(self) -> None:
        self._resources["opc://deliverables"] = MCPResource(
            uri="opc://deliverables",
            name="Deliverables",
            description="Generated deliverables and output files",
        )
        self._resources["opc://knowledge-base"] = MCPResource(
            uri="opc://knowledge-base",
            name="Knowledge Base",
            description="Professional knowledge base for fallback content",
        )
        self._resources["opc://skills"] = MCPResource(
            uri="opc://skills",
            name="Skills Registry",
            description="Available skills and their configurations",
        )

    def _register_default_prompts(self) -> None:
        self._prompts["business_analysis"] = MCPPrompt(
            name="business_analysis",
            description="Generate a business analysis prompt",
            arguments=[
                {"name": "topic", "description": "Analysis topic", "required": True},
                {
                    "name": "type",
                    "description": "Analysis type (swot/competitive/market)",
                    "required": False,
                },
            ],
        )
        self._prompts["content_creation"] = MCPPrompt(
            name="content_creation",
            description="Generate a content creation prompt",
            arguments=[
                {"name": "topic", "description": "Content topic", "required": True},
                {
                    "name": "format",
                    "description": "Output format (report/plan/proposal)",
                    "required": False,
                },
            ],
        )

    def _discover_tools_from_registry(self) -> None:
        """Auto-discover skills from SkillRegistry and register them as MCP tools.

        Skips skills that are disabled, frozen, or whose skill_id collides with
        an already-registered base tool name (base tools take precedence for
        backward compatibility).
        """
        if not self.skill_registry:
            return

        try:
            skills = self.skill_registry.list_all_skills()
        except Exception as e:
            logger.warning(
                "[MCP] Failed to list skills from registry, skipping discovery: %s", e
            )
            return

        for skill in skills:
            skill_id = getattr(skill, "skill_id", None)
            if not skill_id:
                continue

            if not getattr(skill, "enabled", True):
                continue

            if getattr(skill, "frozen", False) is True:
                continue

            # Base tools take precedence — don't overwrite them
            if skill_id in self._tools:
                continue

            try:
                mcp_tool = self._skill_to_mcp_tool(skill)
            except Exception as e:
                logger.warning(
                    "[MCP] Failed to convert skill '%s' to MCP tool: %s", skill_id, e
                )
                continue

            self._tools[skill_id] = mcp_tool
            self._skill_tool_names.add(skill_id)

        logger.info(
            "[MCP] Discovered %d skill-based tools from SkillRegistry",
            len(self._skill_tool_names),
        )

    def _skill_to_mcp_tool(self, skill: Any) -> MCPTool:
        """Convert a Skill dataclass instance to an MCPTool definition."""
        description = (
            getattr(skill, "description", "")
            or f"Execute {getattr(skill, 'name', skill.skill_id)} skill"
        )
        return MCPTool(
            name=skill.skill_id,
            description=description,
            input_schema=self._build_input_schema(skill),
        )

    def _build_input_schema(self, skill: Any) -> Dict[str, Any]:
        """Build a JSON Schema input schema from a Skill's input specifications."""
        schema: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        inputs = getattr(skill, "inputs", []) or []
        for spec in inputs:
            param_name = getattr(spec, "name", "")
            if not param_name:
                continue

            param_type = _PYTHON_TYPE_TO_JSON_SCHEMA.get(
                getattr(spec, "type", "str"), "string"
            )
            prop: Dict[str, Any] = {
                "type": param_type,
                "description": getattr(spec, "description", ""),
            }
            if getattr(spec, "default", None) is not None:
                prop["default"] = spec.default

            schema["properties"][param_name] = prop

            if getattr(spec, "required", False):
                schema["required"].append(param_name)

        return schema

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")

        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }

        handler = handlers.get(method)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        try:
            result = handler(params)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as e:
            logger.error("MCP handler error for %s: %s", method, e)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)},
            }

    def _handle_initialize(self, params: Dict) -> Dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION,
            },
        }

    def _handle_tools_list(self, params: Dict) -> Dict[str, Any]:
        return {"tools": [t.to_dict() for t in self._tools.values()]}

    def _handle_tools_call(self, params: Dict) -> Dict[str, Any]:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            return {
                "content": [{"type": "text", "text": "Missing tool name"}],
                "isError": True,
            }

        if tool_name not in self._tools:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }

        tool = self._tools[tool_name]
        required_params = tool.input_schema.get("required", [])
        for rp in required_params:
            if rp not in arguments:
                return {
                    "content": [
                        {"type": "text", "text": f"Missing required parameter: {rp}"}
                    ],
                    "isError": True,
                }

        # Route skill-based tools directly to SkillRegistry
        if tool_name in self._skill_tool_names and self.skill_registry:
            return self._execute_skill_tool(tool_name, arguments)

        if tool_name == "execute_task":
            result = self._handle_execute_task(arguments.get("user_input", ""))
            if result is not None:
                return result

        if tool_name == "search_web" and self.task_engine:
            result = self.task_engine.execute(
                user_input=arguments.get("query", ""),
                task_type_hint=None,
            )
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result.content or "",
                    }
                ]
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Tool {tool_name} executed with args: {arguments}",
                }
            ]
        }

    def _handle_execute_task(
        self, user_input: str
    ) -> Optional[Dict[str, Any]]:
        """Handle execute_task tool via skill_registry (preferred) or task_engine (fallback).

        Returns None if neither handler is available, so the caller can fall
        through to the default tool response.
        """
        if self.skill_registry:
            matched_skills = self.skill_registry.find_by_intent(user_input)
            if matched_skills:
                import asyncio

                try:
                    _new_loop = asyncio.new_event_loop()
                    try:
                        result = _new_loop.run_until_complete(
                            self.skill_registry.execute_skill(
                                matched_skills[0].skill_id,
                                context=None,
                                goal=user_input,
                            )
                        )
                    finally:
                        _new_loop.close()
                    if result.get("success") and result.get("data"):
                        data = result["data"]
                        content = (
                            data.get("content", "")
                            if isinstance(data, dict)
                            else str(data)
                        )
                        if content:
                            return {"content": [{"type": "text", "text": content}]}
                except Exception as e:
                    logger.warning(
                        "SkillRegistry execute failed, falling back to task_engine: %s",
                        e,
                    )
        if self.task_engine:
            result = self.task_engine.execute(
                user_input=user_input,
                task_type_hint=None,
            )
            content = result.content or ""
            return {
                "content": [
                    {"type": "text", "text": content or "No content generated"}
                ]
            }
        return None

    def _execute_skill_tool(
        self, skill_id: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a skill-based MCP tool via SkillRegistry.execute_skill().

        Bridges the sync MCP request handler to the async execute_skill method
        using a temporary event loop, mirroring the existing execute_task pattern.
        """
        import asyncio

        registry = self.skill_registry
        if registry is None:
            return {
                "content": [
                    {"type": "text", "text": "Error: skill_registry not configured"}
                ],
                "isError": True,
            }

        try:
            _new_loop = asyncio.new_event_loop()
            try:
                result = _new_loop.run_until_complete(
                    registry.execute_skill(skill_id, context=None, **arguments)
                )
            finally:
                _new_loop.close()

            if result.get("success") and result.get("data"):
                data = result["data"]
                if isinstance(data, dict):
                    content = data.get("content", "")
                    if not content:
                        content = json.dumps(data, ensure_ascii=False, indent=2)
                else:
                    content = str(data)
                return {"content": [{"type": "text", "text": content}]}

            error_msg = result.get("error", "Skill execution failed")
            return {
                "content": [{"type": "text", "text": f"Skill error: {error_msg}"}],
                "isError": True,
            }
        except Exception as e:
            logger.warning("[MCP] Skill tool '%s' execution failed: %s", skill_id, e)
            return {
                "content": [{"type": "text", "text": f"Execution failed: {e}"}],
                "isError": True,
            }

    def _handle_resources_list(self, params: Dict) -> Dict[str, Any]:
        return {"resources": [r.to_dict() for r in self._resources.values()]}

    def _handle_resources_read(self, params: Dict) -> Dict[str, Any]:
        uri = params.get("uri", "")
        if uri == "opc://skills" and self.skill_registry:
            skills = self.skill_registry.list_skills()
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(skills, ensure_ascii=False),
                    }
                ]
            }
        return {
            "contents": [
                {"uri": uri, "mimeType": "text/plain", "text": f"Resource: {uri}"}
            ]
        }

    def _handle_prompts_list(self, params: Dict) -> Dict[str, Any]:
        return {"prompts": [p.to_dict() for p in self._prompts.values()]}

    def _handle_prompts_get(self, params: Dict) -> Dict[str, Any]:
        name = params.get("name", "")
        prompt = self._prompts.get(name)
        if not prompt:
            return {"description": f"Unknown prompt: {name}", "messages": []}
        args = params.get("arguments", {})
        topic = args.get("topic", "")
        messages = [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"请帮我{prompt.description}：{topic}",
                },
            }
        ]
        return {"description": prompt.description, "messages": messages}

    def register_tool(self, tool: MCPTool) -> None:
        self._tools[tool.name] = tool

    def register_resource(self, resource: MCPResource) -> None:
        self._resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPrompt) -> None:
        self._prompts[prompt.name] = prompt

    def get_stats(self) -> Dict[str, Any]:
        return {
            "tools": len(self._tools),
            "skill_tools": len(self._skill_tool_names),
            "resources": len(self._resources),
            "prompts": len(self._prompts),
            "protocol_version": MCP_PROTOCOL_VERSION,
            "server_version": MCP_SERVER_VERSION,
        }
