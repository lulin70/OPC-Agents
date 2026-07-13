"""
工具注册中心 (ToolRegistry) — 工具注册、发现与元数据管理

从 tool_system.py 拆分（Phase 3 架构演进），职责：
- 工具数据模型（ToolCategory / PermissionLevel / ToolParameter / Tool）
- 工具注册与索引（按 category / permission）
- 工具调用分发（call_tool + 权限检查 + 参数校验）
- 输入长度限制（安全防护，跨 handler 共享）

Handler 实现分别位于 tool_handlers_fs / tool_handlers_smtp / tool_handlers_cmd，
ToolSystem（tool_system.py）作为 Facade 组合 Registry + 各 Handler。
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

INPUT_LENGTH_LIMITS: Dict[str, int] = {
    "user_input": 10000,
    "command_arg": 1000,
    "file_path": 500,
    "skill_param": 5000,
}


def _validate_input_length(input_type: str, value: str) -> None:
    limit = INPUT_LENGTH_LIMITS.get(input_type, 10000)
    if len(value) > limit:
        raise ValueError(f"输入超出长度限制: {len(value)} > {limit} ({input_type})")


class ToolCategory(Enum):
    SEARCH = "search"
    FILE = "file"
    API = "api"
    DATABASE = "database"
    SYSTEM = "system"
    NOTIFICATION = "notification"


class PermissionLevel(Enum):
    PUBLIC = "public"
    USER = "user"
    ADMIN = "admin"


@dataclass
class ToolParameter:
    name: str
    type: str
    required: bool = True
    description: str = ""
    default: Any = None
    allowed_values: Optional[List[Any]] = None

    def __post_init__(self) -> None:
        if self.allowed_values is None:
            self.allowed_values = []


@dataclass
class Tool:
    tool_id: str
    name: str
    description: str
    category: ToolCategory
    parameters: List[ToolParameter]
    execute: Callable
    permission: PermissionLevel = PermissionLevel.PUBLIC
    enabled: bool = True
    version: str = "1.0"

    def validate_parameters(self, kwargs: Dict[str, Any]) -> List[str]:
        errors: List[str] = []

        for param in self.parameters:
            if param.required and param.name not in kwargs:
                errors.append(f"缺少必填参数: {param.name}")
                continue

            if param.name in kwargs:
                value = kwargs[param.name]
                if param.type == "str" and not isinstance(value, str):
                    errors.append(f"参数 {param.name} 应为字符串类型")
                elif param.type == "int" and not isinstance(value, int):
                    errors.append(f"参数 {param.name} 应为整数类型")
                elif param.type == "float" and not isinstance(value, float):
                    errors.append(f"参数 {param.name} 应为浮点数类型")
                elif param.type == "bool" and not isinstance(value, bool):
                    errors.append(f"参数 {param.name} 应为布尔类型")
                elif param.type == "list" and not isinstance(value, list):
                    errors.append(f"参数 {param.name} 应为列表类型")
                elif param.type == "dict" and not isinstance(value, dict):
                    errors.append(f"参数 {param.name} 应为字典类型")

                if param.allowed_values and value not in param.allowed_values:
                    errors.append(
                        f"参数 {param.name} 的值 {value} 不在允许范围内: {param.allowed_values}"
                    )

        return errors


class ToolRegistry:
    """工具注册中心 — 注册、索引、调用分发与权限检查。

    Handler 方法（_execute_file_read 等）由 Facade（ToolSystem）通过
    多重继承注入，call_tool 通过 tool.execute 回调统一分发，不耦合具体 handler。
    """

    def __init__(self, register_builtins: bool = True):
        self.tools: Dict[str, Tool] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.permission_index: Dict[str, List[str]] = {}
        if register_builtins:
            self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """由 Facade（ToolSystem）覆写，注册内置工具。"""
        # Template Method: 子类/Facade 负责具体注册逻辑
        pass

    def register_tool(self, tool: Tool) -> bool:
        if tool.tool_id in self.tools:
            logger.warning("工具已存在: %s", tool.tool_id)
            return False

        self.tools[tool.tool_id] = tool

        category_name = tool.category.value
        if category_name not in self.category_index:
            self.category_index[category_name] = []
        self.category_index[category_name].append(tool.tool_id)

        permission_name = tool.permission.value
        if permission_name not in self.permission_index:
            self.permission_index[permission_name] = []
        self.permission_index[permission_name].append(tool.tool_id)

        logger.info("工具注册成功: %s", tool.tool_id)
        return True

    def get_tool(self, tool_id: str) -> Optional[Tool]:
        return self.tools.get(tool_id)

    def find_by_category(self, category: ToolCategory) -> List[Tool]:
        category_name = category.value
        tool_ids = self.category_index.get(category_name, [])
        return [self.tools[tid] for tid in tool_ids if tid in self.tools]

    def find_by_permission(self, permission: PermissionLevel) -> List[Tool]:
        permission_name = permission.value
        tool_ids = self.permission_index.get(permission_name, [])
        return [self.tools[tid] for tid in tool_ids if tid in self.tools]

    def list_all_tools(self) -> List[Tool]:
        return list(self.tools.values())

    async def call_tool(
        self,
        tool_id: str,
        user_permission: PermissionLevel = PermissionLevel.PUBLIC,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """调用工具

        注意：当前权限模型中 user_permission 由调用方传入，适用于受信任的内部调用场景。
        生产环境应替换为基于 session/token 的认证上下文获取权限等级。
        """
        tool = self.get_tool(tool_id)
        if not tool:
            return {"success": False, "error": f"工具不存在: {tool_id}"}

        if not tool.enabled:
            return {"success": False, "error": f"工具已禁用: {tool_id}"}

        if not self._check_permission(user_permission, tool.permission):
            return {
                "success": False,
                "error": f"权限不足: 需要 {tool.permission.value} 权限",
            }

        validation_errors = tool.validate_parameters(kwargs)
        if validation_errors:
            return {"success": False, "error": "; ".join(validation_errors)}

        try:
            if asyncio.iscoroutinefunction(tool.execute):
                result = await tool.execute(**kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, lambda: tool.execute(**kwargs)
                )

            return {"success": True, "data": result}

        except Exception as e:
            logger.error("工具调用异常: %s, 错误: %s", tool_id, str(e))
            return {"success": False, "error": str(e)}

    def _check_permission(
        self, user_permission: PermissionLevel, required_permission: PermissionLevel
    ) -> bool:
        permission_order = [
            PermissionLevel.PUBLIC.value,
            PermissionLevel.USER.value,
            PermissionLevel.ADMIN.value,
        ]

        user_level = permission_order.index(user_permission.value)
        required_level = permission_order.index(required_permission.value)

        return user_level >= required_level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "tool_system",
            "tool_count": len(self.tools),
            "categories": self.category_index,
            "permissions": self.permission_index,
            "tools": {
                tid: {
                    "name": t.name,
                    "category": t.category.value,
                    "permission": t.permission.value,
                    "description": t.description,
                }
                for tid, t in self.tools.items()
            },
        }
