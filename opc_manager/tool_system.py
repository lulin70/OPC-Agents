"""
工具调用框架 (ToolSystem) - 负责工具的注册、调用和权限管理

这是三贤者架构的工具基础设施：
- 注册工具
- 调用工具
- 权限检查
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import json
import logging
import os
import shlex
from collections import OrderedDict
from datetime import datetime

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "wc", "echo", "pwd", "whoami",
    "date", "df", "du", "find", "grep", "sort", "uniq", "curl", "ping",
}

_ALLOWED_BASE_DIRS: List[str] = []

INPUT_LENGTH_LIMITS = {
    "user_input": 10000,
    "command_arg": 1000,
    "file_path": 500,
    "skill_param": 5000,
}


def configure_allowed_dirs(dirs: List[str]) -> None:
    global _ALLOWED_BASE_DIRS
    _ALLOWED_BASE_DIRS = [os.path.abspath(d) for d in dirs]


def _validate_path(file_path: str) -> str:
    abs_path = os.path.abspath(file_path)
    if ".." in os.path.normpath(file_path).split(os.sep):
        raise ValueError(f"路径不允许包含 '..': {file_path}")
    if _ALLOWED_BASE_DIRS:
        if not any(abs_path.startswith(base) for base in _ALLOWED_BASE_DIRS):
            raise ValueError(f"路径超出允许范围: {file_path}")
    return abs_path


def _validate_input_length(input_type: str, value: str) -> None:
    limit = INPUT_LENGTH_LIMITS.get(input_type, 10000)
    if len(value) > limit:
        raise ValueError(f"输入超出长度限制: {len(value)} > {limit} ({input_type})")


class AuditLogger:
    _log_file = "logs/security_audit.jsonl"

    @classmethod
    def log(cls, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            os.makedirs(os.path.dirname(cls._log_file), exist_ok=True)
            with open(cls._log_file, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"审计日志写入失败: {e}")

    @classmethod
    def query(cls, event_type: str = None,
              start_time: str = None, end_time: str = None) -> List[Dict]:
        results = []
        try:
            with open(cls._log_file, "r") as f:
                for line in f:
                    record = json.loads(line.strip())
                    if event_type and record.get("event_type") != event_type:
                        continue
                    ts = record.get("timestamp", "")
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
                    results.append(record)
        except FileNotFoundError:
            pass
        return results


class ToolCategory(Enum):
    """工具分类枚举"""
    SEARCH = "search"               # 搜索工具
    FILE = "file"                   # 文件操作工具
    API = "api"                     # API调用工具
    DATABASE = "database"           # 数据库工具
    SYSTEM = "system"               # 系统工具
    NOTIFICATION = "notification"   # 通知工具


class PermissionLevel(Enum):
    """权限级别枚举"""
    PUBLIC = "public"               # 公开（无需权限）
    USER = "user"                   # 用户级（需要用户认证）
    ADMIN = "admin"                 # 管理员级（需要管理员权限）


@dataclass
class ToolParameter:
    """工具参数规范"""
    name: str                       # 参数名称
    type: str                       # 参数类型
    required: bool = True           # 是否必填
    description: str = ""           # 参数描述
    default: Any = None             # 默认值
    allowed_values: List[Any] = None  # 允许的值列表

    def __post_init__(self):
        if self.allowed_values is None:
            self.allowed_values = []


@dataclass
class Tool:
    """工具对象"""
    tool_id: str                    # 工具唯一标识
    name: str                       # 工具名称
    description: str                # 工具描述
    category: ToolCategory          # 工具分类
    parameters: List[ToolParameter] # 参数规范
    execute: Callable               # 执行函数
    permission: PermissionLevel = PermissionLevel.PUBLIC  # 权限级别
    enabled: bool = True            # 是否启用
    version: str = "1.0"            # 版本号

    def validate_parameters(self, kwargs: Dict[str, Any]) -> List[str]:
        """
        验证参数是否符合规范
        
        Args:
            kwargs: 传入的参数
        
        Returns:
            List[str]: 错误信息列表
        """
        errors = []
        
        for param in self.parameters:
            # 检查必填参数
            if param.required and param.name not in kwargs:
                errors.append(f"缺少必填参数: {param.name}")
                continue
            
            # 检查参数类型
            if param.name in kwargs:
                value = kwargs[param.name]
                # 简单类型检查
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
                
                # 检查允许的值列表
                if param.allowed_values and value not in param.allowed_values:
                    errors.append(f"参数 {param.name} 的值 {value} 不在允许范围内: {param.allowed_values}")
        
        return errors


class ToolSystem:
    """工具调用框架 — 负责工具的注册、调用和权限管理"""

    def __init__(self):
        """初始化工具调用框架"""
        self.tools: Dict[str, Tool] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.permission_index: Dict[str, List[str]] = {}
        
        # 注册内置工具
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具"""
        # 文件读取工具
        file_read_tool = Tool(
            tool_id="file_read",
            name="读取文件",
            description="读取指定路径的文件内容",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="file_path", type="str", description="文件路径"),
                ToolParameter(name="encoding", type="str", required=False, default="utf-8", description="文件编码")
            ],
            execute=self._execute_file_read,
            permission=PermissionLevel.USER
        )
        self.register_tool(file_read_tool)
        
        # 文件写入工具
        file_write_tool = Tool(
            tool_id="file_write",
            name="写入文件",
            description="将内容写入指定文件",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="file_path", type="str", description="文件路径"),
                ToolParameter(name="content", type="str", description="文件内容"),
                ToolParameter(name="encoding", type="str", required=False, default="utf-8", description="文件编码"),
                ToolParameter(name="overwrite", type="bool", required=False, default=False, description="是否覆盖")
            ],
            execute=self._execute_file_write,
            permission=PermissionLevel.USER
        )
        self.register_tool(file_write_tool)
        
        # 文件列表工具
        file_list_tool = Tool(
            tool_id="file_list",
            name="列出文件",
            description="列出指定目录的文件列表",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="dir_path", type="str", description="目录路径"),
                ToolParameter(name="pattern", type="str", required=False, description="文件名匹配模式")
            ],
            execute=self._execute_file_list,
            permission=PermissionLevel.USER
        )
        self.register_tool(file_list_tool)
        
        # 网络搜索工具
        search_tool = Tool(
            tool_id="web_search",
            name="网络搜索",
            description="搜索互联网信息",
            category=ToolCategory.SEARCH,
            parameters=[
                ToolParameter(name="query", type="str", description="搜索查询词"),
                ToolParameter(name="max_results", type="int", required=False, default=10, description="最大结果数")
            ],
            execute=self._execute_web_search,
            permission=PermissionLevel.PUBLIC
        )
        self.register_tool(search_tool)
        
        # 发送邮件工具
        email_tool = Tool(
            tool_id="send_email",
            name="发送邮件",
            description="发送电子邮件",
            category=ToolCategory.NOTIFICATION,
            parameters=[
                ToolParameter(name="to", type="str", description="收件人邮箱"),
                ToolParameter(name="subject", type="str", description="邮件主题"),
                ToolParameter(name="body", type="str", description="邮件内容"),
                ToolParameter(name="attachments", type="list", required=False, description="附件路径列表")
            ],
            execute=self._execute_send_email,
            permission=PermissionLevel.USER
        )
        self.register_tool(email_tool)
        
        # 系统命令工具
        command_tool = Tool(
            tool_id="run_command",
            name="执行命令",
            description="执行系统命令",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter(name="command", type="str", description="命令字符串"),
                ToolParameter(name="cwd", type="str", required=False, description="工作目录")
            ],
            execute=self._execute_run_command,
            permission=PermissionLevel.ADMIN
        )
        self.register_tool(command_tool)

    def register_tool(self, tool: Tool) -> bool:
        """
        注册工具
        
        Args:
            tool: 工具对象
        
        Returns:
            bool: 是否注册成功
        """
        if tool.tool_id in self.tools:
            logger.warning(f"工具已存在: {tool.tool_id}")
            return False
        
        self.tools[tool.tool_id] = tool
        
        # 更新分类索引
        category_name = tool.category.value
        if category_name not in self.category_index:
            self.category_index[category_name] = []
        self.category_index[category_name].append(tool.tool_id)
        
        # 更新权限索引
        permission_name = tool.permission.value
        if permission_name not in self.permission_index:
            self.permission_index[permission_name] = []
        self.permission_index[permission_name].append(tool.tool_id)
        
        logger.info(f"工具注册成功: {tool.tool_id}")
        return True

    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """
        获取工具
        
        Args:
            tool_id: 工具ID
        
        Returns:
            Optional[Tool]: 工具对象，如果存在的话
        """
        return self.tools.get(tool_id)

    def find_by_category(self, category: ToolCategory) -> List[Tool]:
        """
        根据分类查找工具
        
        Args:
            category: 工具分类
        
        Returns:
            List[Tool]: 该分类下的工具列表
        """
        category_name = category.value
        tool_ids = self.category_index.get(category_name, [])
        return [self.tools[tid] for tid in tool_ids if tid in self.tools]

    def find_by_permission(self, permission: PermissionLevel) -> List[Tool]:
        """
        根据权限级别查找工具
        
        Args:
            permission: 权限级别
        
        Returns:
            List[Tool]: 该权限级别的工具列表
        """
        permission_name = permission.value
        tool_ids = self.permission_index.get(permission_name, [])
        return [self.tools[tid] for tid in tool_ids if tid in self.tools]

    def list_all_tools(self) -> List[Tool]:
        """
        获取所有工具列表
        
        Returns:
            List[Tool]: 所有工具列表
        """
        return list(self.tools.values())

    async def call_tool(self, tool_id: str, user_permission: PermissionLevel = PermissionLevel.PUBLIC, **kwargs) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_id: 工具ID
            user_permission: 用户权限级别
            **kwargs: 工具参数
        
        Returns:
            Dict[str, Any]: 调用结果
        """
        # 获取工具
        tool = self.get_tool(tool_id)
        if not tool:
            return {"success": False, "error": f"工具不存在: {tool_id}"}
        
        # 检查工具是否启用
        if not tool.enabled:
            return {"success": False, "error": f"工具已禁用: {tool_id}"}
        
        # 检查权限
        if not self._check_permission(user_permission, tool.permission):
            return {"success": False, "error": f"权限不足: 需要 {tool.permission.value} 权限"}
        
        # 验证参数
        validation_errors = tool.validate_parameters(kwargs)
        if validation_errors:
            return {"success": False, "error": "; ".join(validation_errors)}
        
        try:
            # 执行工具
            if asyncio.iscoroutinefunction(tool.execute):
                result = await tool.execute(**kwargs)
            else:
                result = tool.execute(**kwargs)
            
            return {"success": True, "data": result}
        
        except Exception as e:
            logger.error(f"工具调用异常: {tool_id}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def _check_permission(self, user_permission: PermissionLevel, required_permission: PermissionLevel) -> bool:
        """
        检查用户权限是否满足要求
        
        Args:
            user_permission: 用户权限级别
            required_permission: 所需权限级别
        
        Returns:
            bool: 是否有权限
        """
        permission_order = [
            PermissionLevel.PUBLIC.value,
            PermissionLevel.USER.value,
            PermissionLevel.ADMIN.value
        ]
        
        user_level = permission_order.index(user_permission.value)
        required_level = permission_order.index(required_permission.value)
        
        return user_level >= required_level

    def to_dict(self) -> Dict[str, Any]:
        """
        将工具系统状态转换为字典
        
        Returns:
            Dict[str, Any]: 状态字典
        """
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
                    "description": t.description
                }
                for tid, t in self.tools.items()
            }
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典恢复工具系统状态
        
        Args:
            data: 状态字典
        """
        # 这里可以添加从持久化存储恢复的逻辑
        pass

    # 内置工具执行函数
    def _execute_file_read(self, file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        try:
            _validate_input_length("file_path", file_path)
            safe_path = _validate_path(file_path)
            with open(safe_path, 'r', encoding=encoding) as f:
                content = f.read()
            AuditLogger.log("PATH_ACCESS_GRANTED", {
                "operation": "read",
                "file_path": safe_path,
            })
            return {"content": content, "file_path": safe_path}
        except ValueError as e:
            AuditLogger.log("PATH_REJECTED", {
                "operation": "read",
                "file_path": file_path,
                "reason": str(e),
            })
            raise Exception(f"路径校验失败: {str(e)}")
        except Exception as e:
            raise Exception(f"文件读取失败: {str(e)}")

    def _execute_file_write(self, file_path: str, content: str, encoding: str = "utf-8", overwrite: bool = False) -> Dict[str, Any]:
        try:
            _validate_input_length("file_path", file_path)
            safe_path = _validate_path(file_path)
        except ValueError as e:
            AuditLogger.log("PATH_REJECTED", {
                "operation": "write",
                "file_path": file_path,
                "reason": str(e),
            })
            raise Exception(f"路径校验失败: {str(e)}")
        
        if os.path.exists(safe_path) and not overwrite:
            raise Exception(f"文件已存在: {safe_path}")
        
        dir_path = os.path.dirname(safe_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        
        try:
            with open(safe_path, 'w', encoding=encoding) as f:
                f.write(content)
            AuditLogger.log("PATH_ACCESS_GRANTED", {
                "operation": "write",
                "file_path": safe_path,
            })
            return {"success": True, "file_path": safe_path}
        except Exception as e:
            raise Exception(f"文件写入失败: {str(e)}")

    def _execute_file_list(self, dir_path: str, pattern: str = None) -> Dict[str, Any]:
        import fnmatch
        
        try:
            _validate_input_length("file_path", dir_path)
            safe_path = _validate_path(dir_path)
        except ValueError as e:
            AuditLogger.log("PATH_REJECTED", {
                "operation": "list",
                "file_path": dir_path,
                "reason": str(e),
            })
            raise Exception(f"路径校验失败: {str(e)}")
        
        try:
            files = os.listdir(safe_path)
            
            if pattern:
                files = fnmatch.filter(files, pattern)
            
            file_info = []
            for filename in files:
                full_path = os.path.join(safe_path, filename)
                file_info.append({
                    "name": filename,
                    "path": full_path,
                    "is_dir": os.path.isdir(full_path),
                    "size": os.path.getsize(full_path) if os.path.isfile(full_path) else 0
                })
            
            return {"files": file_info, "directory": safe_path}
        except Exception as e:
            raise Exception(f"文件列表获取失败: {str(e)}")

    def _execute_web_search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        return {
            "query": query,
            "results": [
                {"title": f"搜索结果 {i}", "url": f"https://example.com/result/{i}", "snippet": f"这是搜索结果 {i} 的摘要内容"}
                for i in range(min(max_results, 5))
            ],
            "total": min(max_results, 5)
        }

    def _execute_send_email(self, to: str, subject: str, body: str, attachments: list = None) -> Dict[str, Any]:
        """发送邮件"""
        # 实际实现可以接入邮件服务
        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "attachments": attachments or []
        }

    async def _execute_run_command(self, command: str, cwd: str = None) -> Dict[str, Any]:
        try:
            _validate_input_length("command_arg", command)
            parts = shlex.split(command)
            if not parts:
                raise ValueError("空命令")
            
            base_cmd = os.path.basename(parts[0])
            if base_cmd not in ALLOWED_COMMANDS:
                AuditLogger.log("COMMAND_REJECTED", {
                    "command": command,
                    "reason": f"命令不被允许: {base_cmd}",
                })
                raise ValueError(f"命令不被允许: {base_cmd}，允许的命令: {', '.join(sorted(ALLOWED_COMMANDS))}")
            
            proc = await asyncio.create_subprocess_exec(
                *parts,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                raise Exception("命令执行超时")
            
            AuditLogger.log("COMMAND_EXECUTED", {
                "command": command,
                "cwd": cwd,
                "return_code": proc.returncode,
            })
            
            return {
                "command": command,
                "cwd": cwd or os.getcwd(),
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "return_code": proc.returncode
            }
        except ValueError as e:
            raise Exception(f"命令验证失败: {str(e)}")
        except Exception as e:
            raise Exception(f"命令执行失败: {str(e)}")
