"""
工具调用框架 (ToolSystem) — Facade

三贤者架构的工具基础设施：
- 注册工具
- 调用工具
- 权限检查

Phase 3 架构演进：将实现拆分为 4 个子模块，tool_system.py 保留为 Facade：
- tool_registry.py — 数据模型 + 注册/发现/调用分发 + 输入长度校验
- tool_handlers_fs.py — 文件系统工具处理器 + 路径校验
- tool_handlers_smtp.py — 邮件工具处理器 + CRLF 注入防护
- tool_handlers_cmd.py — 命令执行处理器 + shlex 白名单防护
- tool_audit_logger.py — 审计日志（独立模块，不变）

ToolSystem 通过多重继承组合 Registry + 各 Handler，_register_builtin_tools
将 handler 方法注册为 Tool.execute 回调。

向后兼容：所有公共符号（Tool/ToolCategory/PermissionLevel/ToolParameter/
ToolSystem/AuditLogger/ALLOWED_COMMANDS/INPUT_LENGTH_LIMITS/COMMAND_TIMEOUT_SECONDS/
_validate_path/_validate_input_length/_configure_allowed_dirs）从此模块 re-export，
现有 `from opc_manager.tool_system import X` 无需修改。
"""

# asyncio 必须在模块顶层导入：测试通过 patch("opc_manager.tool_system.asyncio.create_subprocess_exec")
# 拦截子进程创建，移除会导致测试失败。
import asyncio  # noqa: F401

from opc_manager.tool_audit_logger import AuditLogger
from opc_manager.tool_handlers_cmd import (
    ALLOWED_COMMANDS,
    COMMAND_TIMEOUT_SECONDS,
    CommandHandlers,
)
from opc_manager.tool_handlers_fs import (
    FileSystemHandlers,
    _ALLOWED_BASE_DIRS,
    _configure_allowed_dirs,
    _ensure_allowed_dirs,
    _validate_path,
)
from opc_manager.tool_handlers_smtp import SmtpHandlers
from opc_manager.tool_registry import (
    INPUT_LENGTH_LIMITS,
    PermissionLevel,
    Tool,
    ToolCategory,
    ToolParameter,
    ToolRegistry,
    _validate_input_length,
)

# Facade re-exports：保持 `from opc_manager.tool_system import X` 向后兼容
__all__ = [
    "ToolSystem",
    "Tool",
    "ToolCategory",
    "ToolParameter",
    "PermissionLevel",
    "ToolRegistry",
    "AuditLogger",
    "ALLOWED_COMMANDS",
    "INPUT_LENGTH_LIMITS",
    "COMMAND_TIMEOUT_SECONDS",
    "_validate_path",
    "_validate_input_length",
    "_configure_allowed_dirs",
    "_ensure_allowed_dirs",
    "_ALLOWED_BASE_DIRS",
]


class ToolSystem(ToolRegistry, FileSystemHandlers, SmtpHandlers, CommandHandlers):
    """工具系统 Facade — 组合注册中心 + 文件/邮件/命令处理器。

    通过多重继承获得：
    - ToolRegistry: 工具注册/发现/调用分发/权限检查
    - FileSystemHandlers: file_read/file_write/file_list 执行逻辑
    - SmtpHandlers: send_email 执行逻辑
    - CommandHandlers: run_command 执行逻辑（含 shlex 白名单防护）
    """

    def _register_builtin_tools(self) -> None:
        file_read_tool = Tool(
            tool_id="file_read",
            name="读取文件",
            description="读取指定路径的文件内容",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="file_path", type="str", description="文件路径"),
                ToolParameter(
                    name="encoding",
                    type="str",
                    required=False,
                    default="utf-8",
                    description="文件编码",
                ),
            ],
            execute=self._execute_file_read,
            permission=PermissionLevel.USER,
        )
        self.register_tool(file_read_tool)

        file_write_tool = Tool(
            tool_id="file_write",
            name="写入文件",
            description="将内容写入指定文件",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="file_path", type="str", description="文件路径"),
                ToolParameter(name="content", type="str", description="文件内容"),
                ToolParameter(
                    name="encoding",
                    type="str",
                    required=False,
                    default="utf-8",
                    description="文件编码",
                ),
                ToolParameter(
                    name="overwrite",
                    type="bool",
                    required=False,
                    default=False,
                    description="是否覆盖",
                ),
            ],
            execute=self._execute_file_write,
            permission=PermissionLevel.USER,
        )
        self.register_tool(file_write_tool)

        file_list_tool = Tool(
            tool_id="file_list",
            name="列出文件",
            description="列出指定目录的文件列表",
            category=ToolCategory.FILE,
            parameters=[
                ToolParameter(name="dir_path", type="str", description="目录路径"),
                ToolParameter(
                    name="pattern",
                    type="str",
                    required=False,
                    description="文件名匹配模式",
                ),
            ],
            execute=self._execute_file_list,
            permission=PermissionLevel.USER,
        )
        self.register_tool(file_list_tool)

        search_tool = Tool(
            tool_id="web_search",
            name="网络搜索",
            description="搜索互联网信息",
            category=ToolCategory.SEARCH,
            parameters=[
                ToolParameter(name="query", type="str", description="搜索查询词"),
                ToolParameter(
                    name="max_results",
                    type="int",
                    required=False,
                    default=10,
                    description="最大结果数",
                ),
            ],
            execute=self._execute_web_search,
            permission=PermissionLevel.PUBLIC,
        )
        self.register_tool(search_tool)

        email_tool = Tool(
            tool_id="send_email",
            name="发送邮件",
            description="发送电子邮件",
            category=ToolCategory.NOTIFICATION,
            parameters=[
                ToolParameter(name="to", type="str", description="收件人邮箱"),
                ToolParameter(name="subject", type="str", description="邮件主题"),
                ToolParameter(name="body", type="str", description="邮件内容"),
                ToolParameter(
                    name="attachments",
                    type="list",
                    required=False,
                    description="附件路径列表",
                ),
            ],
            execute=self._execute_send_email,
            permission=PermissionLevel.USER,
        )
        self.register_tool(email_tool)

        command_tool = Tool(
            tool_id="run_command",
            name="执行命令",
            description="执行系统命令",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter(name="command", type="str", description="命令字符串"),
                ToolParameter(
                    name="cwd", type="str", required=False, description="工作目录"
                ),
            ],
            execute=self._execute_run_command,
            permission=PermissionLevel.ADMIN,
        )
        self.register_tool(command_tool)

    async def _execute_web_search(self, query: str, max_results: int = 10) -> dict:
        # NOTE: Placeholder results returned when no search API is configured.
        # Real search requires DuckDuckGo or other search provider.
        return {
            "query": query,
            "results": [
                {
                    "title": f"搜索结果 {i}",
                    "url": f"https://example.com/result/{i}",
                    "snippet": f"这是搜索结果 {i} 的摘要内容",
                }
                for i in range(min(max_results, 5))
            ],
            "total": min(max_results, 5),
        }
