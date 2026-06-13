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
import fnmatch
import json
import logging
import os
import re
import shlex
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "echo",
    "pwd",
    "whoami",
    "date",
    "df",
    "du",
    "find",
    "grep",
    "sort",
    "uniq",
}

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ALLOWED_BASE_DIRS: List[str] = []
_ALLOWED_BASE_DIRS_INITIALIZED = False


def _ensure_allowed_dirs() -> None:
    global _ALLOWED_BASE_DIRS, _ALLOWED_BASE_DIRS_INITIALIZED
    if _ALLOWED_BASE_DIRS_INITIALIZED:
        return
    _ALLOWED_BASE_DIRS_INITIALIZED = True
    _ALLOWED_BASE_DIRS = [
        os.path.join(_PROJECT_ROOT, "data"),
        os.path.join(_PROJECT_ROOT, "output"),
        os.path.join(_PROJECT_ROOT, "logs"),
    ]


INPUT_LENGTH_LIMITS = {
    "user_input": 10000,
    "command_arg": 1000,
    "file_path": 500,
    "skill_param": 5000,
}

COMMAND_TIMEOUT_SECONDS = 30
AUDIT_LOG_FILE = "logs/security_audit.jsonl"


def _configure_allowed_dirs(dirs: List[str]) -> None:
    global _ALLOWED_BASE_DIRS
    _ALLOWED_BASE_DIRS = [os.path.realpath(d) for d in dirs]


def _validate_path(file_path: str) -> str:
    _ensure_allowed_dirs()
    abs_path = os.path.realpath(file_path)
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
    _log_file = AUDIT_LOG_FILE
    _write_queue: Optional[asyncio.Queue] = None
    _writer_task: Optional[asyncio.Task] = None
    _shutdown_event: Optional[asyncio.Event] = None

    @classmethod
    def configure(cls, log_file: str) -> None:
        cls._log_file = log_file

    @classmethod
    def _ensure_queue(cls) -> asyncio.Queue:
        if cls._write_queue is None:
            cls._write_queue = asyncio.Queue(maxsize=1000)
        return cls._write_queue

    @classmethod
    async def _start_writer(cls) -> None:
        if cls._writer_task is not None and not cls._writer_task.done():
            return
        queue = cls._ensure_queue()
        if cls._shutdown_event is None:
            cls._shutdown_event = asyncio.Event()
        shutdown = cls._shutdown_event

        async def _writer():
            try:
                os.makedirs(os.path.dirname(cls._log_file), exist_ok=True)
            except OSError:
                pass
            while not shutdown.is_set():
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                try:
                    with open(cls._log_file, "a") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                except Exception as e:
                    logger.error("审计日志写入失败: %s", e)
                finally:
                    queue.task_done()
            while not queue.empty():
                try:
                    record = queue.get_nowait()
                    with open(cls._log_file, "a") as f:
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    queue.task_done()
                except Exception as e:
                    logger.warning("[ToolSystem] Writer loop error: %s", e)
                    break

        cls._writer_task = asyncio.create_task(_writer())

    @classmethod
    async def shutdown(cls) -> None:
        if cls._shutdown_event is not None:
            cls._shutdown_event.set()
        if cls._writer_task is not None and not cls._writer_task.done():
            try:
                await asyncio.wait_for(cls._writer_task, timeout=5.0)
            except asyncio.TimeoutError:
                cls._writer_task.cancel()
        cls._writer_task = None
        cls._shutdown_event = None

    @classmethod
    async def log_async(cls, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            await cls._start_writer()
            queue = cls._ensure_queue()
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                logger.warning("审计日志队列已满，同步写入")
                cls._write_sync(record)
        except RuntimeError:
            cls._write_sync(record)

    @classmethod
    def log(cls, event_type: str, details: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
        }
        try:
            asyncio.get_running_loop()
            queue = cls._ensure_queue()
            try:
                queue.put_nowait(record)
                if cls._writer_task is None or cls._writer_task.done():
                    asyncio.create_task(cls._start_writer())
            except asyncio.QueueFull:
                cls._write_sync(record)
        except RuntimeError:
            cls._write_sync(record)

    @classmethod
    def _write_sync(cls, record: Dict[str, Any]) -> None:
        try:
            os.makedirs(os.path.dirname(cls._log_file), exist_ok=True)
            with open(cls._log_file, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("审计日志写入失败: %s", e)

    @classmethod
    def query(
        cls, event_type: str = None, start_time: str = None, end_time: str = None
    ) -> List[Dict]:
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
    allowed_values: List[Any] = None

    def __post_init__(self):
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
        errors = []

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


class ToolSystem:

    def __init__(self, register_builtins: bool = True):
        self.tools: Dict[str, Tool] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.permission_index: Dict[str, List[str]] = {}
        if register_builtins:
            self._register_builtin_tools()

    def _register_builtin_tools(self):
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
        **kwargs,
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

    async def _execute_file_read(
        self, file_path: str, encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        try:
            _validate_input_length("file_path", file_path)
            safe_path = _validate_path(file_path)
            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(
                None, self._read_file_sync, safe_path, encoding
            )
            AuditLogger.log(
                "PATH_ACCESS_GRANTED",
                {
                    "operation": "read",
                    "file_path": safe_path,
                },
            )
            return {"content": content, "file_path": safe_path}
        except ValueError as e:
            AuditLogger.log(
                "PATH_REJECTED",
                {
                    "operation": "read",
                    "file_path": file_path,
                    "reason": str(e),
                },
            )
            raise Exception(f"路径校验失败: {str(e)}")
        except Exception as e:
            raise Exception(f"文件读取失败: {str(e)}")

    @staticmethod
    def _read_file_sync(safe_path: str, encoding: str) -> str:
        with open(safe_path, "r", encoding=encoding) as f:
            return f.read()

    async def _execute_file_write(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        try:
            _validate_input_length("file_path", file_path)
            safe_path = _validate_path(file_path)
        except ValueError as e:
            AuditLogger.log(
                "PATH_REJECTED",
                {
                    "operation": "write",
                    "file_path": file_path,
                    "reason": str(e),
                },
            )
            raise Exception(f"路径校验失败: {str(e)}")

        if os.path.exists(safe_path) and not overwrite:
            raise Exception(f"文件已存在: {safe_path}")

        dir_path = os.path.dirname(safe_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._write_file_sync, safe_path, content, encoding
            )
            AuditLogger.log(
                "PATH_ACCESS_GRANTED",
                {
                    "operation": "write",
                    "file_path": safe_path,
                },
            )
            return {"success": True, "file_path": safe_path}
        except Exception as e:
            raise Exception(f"文件写入失败: {str(e)}")

    @staticmethod
    def _write_file_sync(safe_path: str, content: str, encoding: str) -> None:
        with open(safe_path, "w", encoding=encoding) as f:
            f.write(content)

    async def _execute_file_list(
        self, dir_path: str, pattern: str = None
    ) -> Dict[str, Any]:
        try:
            _validate_input_length("file_path", dir_path)
            safe_path = _validate_path(dir_path)
        except ValueError as e:
            AuditLogger.log(
                "PATH_REJECTED",
                {
                    "operation": "list",
                    "file_path": dir_path,
                    "reason": str(e),
                },
            )
            raise Exception(f"路径校验失败: {str(e)}")

        try:
            loop = asyncio.get_running_loop()
            file_info = await loop.run_in_executor(
                None, self._list_files_sync, safe_path, pattern
            )
            return {"files": file_info, "directory": safe_path}
        except Exception as e:
            raise Exception(f"文件列表获取失败: {str(e)}")

    @staticmethod
    def _list_files_sync(safe_path: str, pattern: str = None) -> List[Dict[str, Any]]:
        files = os.listdir(safe_path)
        if pattern:
            files = fnmatch.filter(files, pattern)
        file_info = []
        for filename in files:
            full_path = os.path.join(safe_path, filename)
            file_info.append(
                {
                    "name": filename,
                    "path": full_path,
                    "is_dir": os.path.isdir(full_path),
                    "size": (
                        os.path.getsize(full_path) if os.path.isfile(full_path) else 0
                    ),
                }
            )
        return file_info

    async def _execute_web_search(
        self, query: str, max_results: int = 10
    ) -> Dict[str, Any]:
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

    async def _execute_send_email(
        self, to: str, subject: str, body: str, attachments: list = None
    ) -> Dict[str, Any]:
        to = to.replace("\r", "").replace("\n", "")
        subject = subject.replace("\r", "").replace("\n", "")
        if not to or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
            return {"sent": False, "error": f"Invalid email address: {to}"}

        smtp_host = os.environ.get("OPC_SMTP_HOST", "")
        smtp_port = int(os.environ.get("OPC_SMTP_PORT", "587"))
        smtp_user = os.environ.get("OPC_SMTP_USER", "")
        smtp_pass = os.environ.get("OPC_SMTP_PASS", "")
        smtp_from = os.environ.get("OPC_SMTP_FROM", smtp_user)
        smtp_tls = os.environ.get("OPC_SMTP_TLS", "true").lower() == "true"

        if smtp_host and smtp_user and smtp_pass:
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    self._send_smtp_sync,
                    smtp_host,
                    smtp_port,
                    smtp_user,
                    smtp_pass,
                    smtp_from,
                    to,
                    subject,
                    body,
                    smtp_tls,
                    attachments,
                )
                if result.get("sent"):
                    logger.info("Email sent via SMTP to %s", to)
                    return result
                logger.warning(
                    "SMTP send failed: %s, falling back to log", result.get("error")
                )
            except Exception as e:
                logger.warning("SMTP send exception: %s, falling back to log", e)

        notification_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "notifications"
        )
        timestamp = int(time.time() * 1000)
        filename = f"notification_{timestamp}.json"
        filepath = os.path.join(notification_dir, filename)

        notification = {
            "type": "email",
            "to": to,
            "subject": subject,
            "body": body[:5000],
            "attachments": attachments or [],
            "timestamp": timestamp,
            "status": "logged",
            "note": "SMTP not configured. Notification logged to file. Configure OPC_SMTP_HOST/USER/PASS for actual email delivery.",
        }

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._write_notification_sync, filepath, notification
            )
            logger.info("Notification logged: %s", filepath)
        except Exception as e:
            logger.warning("Failed to log notification: %s", e)

        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "attachments": attachments or [],
            "delivery_mode": "logged",
            "log_file": filename,
        }

    @staticmethod
    def _send_smtp_sync(
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        use_tls: bool,
        attachments: list = None,
    ) -> Dict[str, Any]:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if use_tls:
                server = smtplib.SMTP(host, port)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(host, port)

            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
            server.quit()

            return {
                "sent": True,
                "to": to_addr,
                "subject": subject,
                "delivery_mode": "smtp",
            }
        except Exception as e:
            return {"sent": False, "error": str(e)}

    @staticmethod
    def _write_notification_sync(filepath: str, notification: dict) -> None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notification, f, ensure_ascii=False, indent=2)

    async def _execute_run_command(
        self, command: str, cwd: str = None
    ) -> Dict[str, Any]:
        try:
            _validate_input_length("command_arg", command)
            parts = shlex.split(command)
            if not parts:
                raise ValueError("空命令")

            base_cmd = os.path.basename(parts[0])
            if base_cmd not in ALLOWED_COMMANDS:
                AuditLogger.log(
                    "COMMAND_REJECTED",
                    {
                        "command": command,
                        "reason": f"命令不被允许: {base_cmd}",
                    },
                )
                raise ValueError(
                    f"命令不被允许: {base_cmd}，允许的命令: {', '.join(sorted(ALLOWED_COMMANDS))}"
                )

            proc = await asyncio.create_subprocess_exec(
                *parts,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=COMMAND_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise Exception("命令执行超时")

            AuditLogger.log(
                "COMMAND_EXECUTED",
                {
                    "command": command,
                    "cwd": cwd,
                    "return_code": proc.returncode,
                },
            )

            return {
                "command": command,
                "cwd": cwd or os.getcwd(),
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "return_code": proc.returncode,
            }
        except ValueError as e:
            raise Exception(f"命令验证失败: {str(e)}")
        except Exception as e:
            raise Exception(f"命令执行失败: {str(e)}")
