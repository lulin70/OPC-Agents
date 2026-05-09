"""
MCPProtocol — Model Context Protocol 支持

兼容微软 Model Context Protocol (MCP) 标准，提供：
- MCP Server端点（工具/资源/提示词模板）
- 工具注册与发现（MCP tools/list → SkillRegistry）
- 资源映射（MCP resources → OPC-Agents deliverables）
- 提示词模板（MCP prompts/list → PersonaManager）

架构位置：
  MCP客户端 → MCPServer → SkillRegistry / TaskEngineAdapter / PersonaManager

参考规范：https://spec.modelcontextprotocol.io/specification/2024-11-05/
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "opc-agents"
MCP_SERVER_VERSION = "0.1.9-gamma"


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

    def __init__(self, skill_registry=None, task_engine_adapter=None):
        self.skill_registry = skill_registry
        self.task_engine_adapter = task_engine_adapter
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, MCPResource] = {}
        self._prompts: Dict[str, MCPPrompt] = {}
        self._register_default_tools()
        self._register_default_resources()
        self._register_default_prompts()

    def _register_default_tools(self) -> None:
        self._tools["execute_task"] = MCPTool(
            name="execute_task",
            description="Execute a task using OPC-Agents Three-Sage Architecture",
            input_schema={
                "type": "object",
                "properties": {
                    "user_input": {"type": "string", "description": "User's task description"},
                    "business_type": {"type": "string", "description": "Business type hint"},
                    "mode": {"type": "string", "enum": ["quality", "fast"], "default": "quality"},
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
                    "analysis_type": {"type": "string", "enum": ["swot", "competitive", "market"]},
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
                    "content_type": {"type": "string", "enum": ["report", "plan", "proposal", "email"]},
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
                {"name": "type", "description": "Analysis type (swot/competitive/market)", "required": False},
            ],
        )
        self._prompts["content_creation"] = MCPPrompt(
            name="content_creation",
            description="Generate a content creation prompt",
            arguments=[
                {"name": "topic", "description": "Content topic", "required": True},
                {"name": "format", "description": "Output format (report/plan/proposal)", "required": False},
            ],
        )

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
            logger.error(f"MCP handler error for {method}: {e}")
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

        if tool_name not in self._tools:
            return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

        if tool_name == "execute_task" and self.task_engine_adapter:
            user_input = arguments.get("user_input", "")
            result = self.task_engine_adapter.execute_skill(
                skill_id="content_generation",
                parameters={"query": user_input, "goal": user_input},
            )
            content = result.get("data", {}).get("content", "")
            return {"content": [{"type": "text", "text": content or "No content generated"}]}

        if tool_name == "search_web" and self.task_engine_adapter:
            result = self.task_engine_adapter.execute_skill(
                skill_id="search",
                parameters={"query": arguments.get("query", ""), "max_results": arguments.get("max_results", 5)},
            )
            return {"content": [{"type": "text", "text": json.dumps(result.get("data", {}), ensure_ascii=False)}]}

        return {"content": [{"type": "text", "text": f"Tool {tool_name} executed with args: {arguments}"}]}

    def _handle_resources_list(self, params: Dict) -> Dict[str, Any]:
        return {"resources": [r.to_dict() for r in self._resources.values()]}

    def _handle_resources_read(self, params: Dict) -> Dict[str, Any]:
        uri = params.get("uri", "")
        if uri == "opc://skills" and self.skill_registry:
            skills = self.skill_registry.list_skills()
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(skills, ensure_ascii=False)}]}
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Resource: {uri}"}]}

    def _handle_prompts_list(self, params: Dict) -> Dict[str, Any]:
        return {"prompts": [p.to_dict() for p in self._prompts.values()]}

    def _handle_prompts_get(self, params: Dict) -> Dict[str, Any]:
        name = params.get("name", "")
        prompt = self._prompts.get(name)
        if not prompt:
            return {"description": f"Unknown prompt: {name}", "messages": []}
        args = params.get("arguments", {})
        topic = args.get("topic", "")
        messages = [{"role": "user", "content": {"type": "text", "text": f"请帮我{prompt.description}：{topic}"}}]
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
            "resources": len(self._resources),
            "prompts": len(self._prompts),
            "protocol_version": MCP_PROTOCOL_VERSION,
            "server_version": MCP_SERVER_VERSION,
        }
