"""
ToolSystem 单元测试

覆盖工具注册/注销、命令白名单、权限检查、命令注入防护、
参数校验、错误处理、异步工具执行等核心逻辑。
"""

import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from opc_manager.tool_system import (
    ToolSystem,
    Tool,
    ToolCategory,
    ToolParameter,
    PermissionLevel,
    ALLOWED_COMMANDS,
    INPUT_LENGTH_LIMITS,
    COMMAND_TIMEOUT_SECONDS,
    _validate_path,
    _validate_input_length,
    _configure_allowed_dirs,
    _ensure_allowed_dirs,
    AuditLogger,
)


def _make_tool(
    tool_id: str = "test_tool",
    name: str = "Test Tool",
    category: ToolCategory = ToolCategory.FILE,
    permission: PermissionLevel = PermissionLevel.PUBLIC,
    execute=None,
    params=None,
    enabled: bool = True,
) -> Tool:
    if execute is None:
        execute = MagicMock(return_value={"result": "ok"})
    if params is None:
        params = [ToolParameter(name="query", type="str", description="test param")]
    return Tool(
        tool_id=tool_id,
        name=name,
        description="A test tool",
        category=category,
        parameters=params,
        execute=execute,
        permission=permission,
        enabled=enabled,
    )


# ─── Tool dataclass tests ──────────────────────────────────────────


class TestToolParameter(unittest.TestCase):
    """ToolParameter 数据类"""

    def test_default_allowed_values_is_empty_list(self):
        p = ToolParameter(name="x", type="str")
        self.assertEqual(p.allowed_values, [])

    def test_post_init_sets_allowed_values(self):
        p = ToolParameter(name="x", type="str", allowed_values=None)
        self.assertEqual(p.allowed_values, [])


class TestToolValidateParameters(unittest.TestCase):
    """Tool.validate_parameters 校验"""

    def _tool_with_params(self, params):
        return Tool(
            tool_id="t",
            name="T",
            description="",
            category=ToolCategory.FILE,
            parameters=params,
            execute=MagicMock(),
        )

    def test_missing_required_param(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="query", type="str", required=True),
            ]
        )
        errors = tool.validate_parameters({})
        self.assertTrue(any("缺少必填参数" in e for e in errors))

    def test_wrong_type_str(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="q", type="str", required=True),
            ]
        )
        errors = tool.validate_parameters({"q": 123})
        self.assertTrue(any("字符串类型" in e for e in errors))

    def test_wrong_type_int(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="n", type="int", required=True),
            ]
        )
        errors = tool.validate_parameters({"n": "abc"})
        self.assertTrue(any("整数类型" in e for e in errors))

    def test_wrong_type_float(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="f", type="float", required=True),
            ]
        )
        errors = tool.validate_parameters({"f": "abc"})
        self.assertTrue(any("浮点数类型" in e for e in errors))

    def test_wrong_type_bool(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="b", type="bool", required=True),
            ]
        )
        errors = tool.validate_parameters({"b": "yes"})
        self.assertTrue(any("布尔类型" in e for e in errors))

    def test_wrong_type_list(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="l", type="list", required=True),
            ]
        )
        errors = tool.validate_parameters({"l": "not a list"})
        self.assertTrue(any("列表类型" in e for e in errors))

    def test_wrong_type_dict(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="d", type="dict", required=True),
            ]
        )
        errors = tool.validate_parameters({"d": [1, 2]})
        self.assertTrue(any("字典类型" in e for e in errors))

    def test_value_not_in_allowed_values(self):
        tool = self._tool_with_params(
            [
                ToolParameter(
                    name="mode",
                    type="str",
                    required=True,
                    allowed_values=["fast", "slow"],
                ),
            ]
        )
        errors = tool.validate_parameters({"mode": "medium"})
        self.assertTrue(any("不在允许范围内" in e for e in errors))

    def test_valid_parameters_no_errors(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="q", type="str", required=True),
                ToolParameter(name="n", type="int", required=False, default=5),
            ]
        )
        errors = tool.validate_parameters({"q": "hello", "n": 10})
        self.assertEqual(errors, [])

    def test_optional_param_missing_no_error(self):
        tool = self._tool_with_params(
            [
                ToolParameter(name="opt", type="str", required=False),
            ]
        )
        errors = tool.validate_parameters({})
        self.assertEqual(errors, [])


# ─── ToolSystem registration tests ─────────────────────────────────


class TestToolSystemRegistration(unittest.TestCase):
    """工具注册与注销"""

    def test_register_tool_success(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("my_tool")
        result = ts.register_tool(tool)
        self.assertTrue(result)
        self.assertIn("my_tool", ts.tools)

    def test_register_duplicate_returns_false(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("dup")
        ts.register_tool(tool)
        result = ts.register_tool(tool)
        self.assertFalse(result)

    def test_register_updates_category_index(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("t1", category=ToolCategory.SEARCH)
        ts.register_tool(tool)
        self.assertIn("search", ts.category_index)
        self.assertIn("t1", ts.category_index["search"])

    def test_register_updates_permission_index(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("t1", permission=PermissionLevel.ADMIN)
        ts.register_tool(tool)
        self.assertIn("admin", ts.permission_index)
        self.assertIn("t1", ts.permission_index["admin"])

    def test_get_tool_exists(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("find_me")
        ts.register_tool(tool)
        self.assertEqual(ts.get_tool("find_me"), tool)

    def test_get_tool_not_exists(self):
        ts = ToolSystem(register_builtins=False)
        self.assertIsNone(ts.get_tool("nonexistent"))

    def test_find_by_category(self):
        ts = ToolSystem(register_builtins=False)
        t1 = _make_tool("t1", category=ToolCategory.SEARCH)
        t2 = _make_tool("t2", category=ToolCategory.SEARCH)
        t3 = _make_tool("t3", category=ToolCategory.FILE)
        ts.register_tool(t1)
        ts.register_tool(t2)
        ts.register_tool(t3)
        search_tools = ts.find_by_category(ToolCategory.SEARCH)
        self.assertEqual(len(search_tools), 2)

    def test_find_by_permission(self):
        ts = ToolSystem(register_builtins=False)
        t1 = _make_tool("t1", permission=PermissionLevel.ADMIN)
        t2 = _make_tool("t2", permission=PermissionLevel.PUBLIC)
        ts.register_tool(t1)
        ts.register_tool(t2)
        admin_tools = ts.find_by_permission(PermissionLevel.ADMIN)
        self.assertEqual(len(admin_tools), 1)

    def test_list_all_tools(self):
        ts = ToolSystem(register_builtins=False)
        ts.register_tool(_make_tool("a"))
        ts.register_tool(_make_tool("b"))
        self.assertEqual(len(ts.list_all_tools()), 2)

    def test_builtin_tools_registered(self):
        ts = ToolSystem(register_builtins=True)
        self.assertIn("file_read", ts.tools)
        self.assertIn("file_write", ts.tools)
        self.assertIn("file_list", ts.tools)
        self.assertIn("web_search", ts.tools)
        self.assertIn("send_email", ts.tools)
        self.assertIn("run_command", ts.tools)

    def test_no_builtins_when_disabled(self):
        ts = ToolSystem(register_builtins=False)
        self.assertEqual(len(ts.tools), 0)


# ─── Permission checks ─────────────────────────────────────────────


class TestPermissionChecks(unittest.TestCase):
    """权限检查"""

    def test_public_can_access_public(self):
        ts = ToolSystem(register_builtins=False)
        self.assertTrue(
            ts._check_permission(PermissionLevel.PUBLIC, PermissionLevel.PUBLIC)
        )

    def test_public_cannot_access_user(self):
        ts = ToolSystem(register_builtins=False)
        self.assertFalse(
            ts._check_permission(PermissionLevel.PUBLIC, PermissionLevel.USER)
        )

    def test_public_cannot_access_admin(self):
        ts = ToolSystem(register_builtins=False)
        self.assertFalse(
            ts._check_permission(PermissionLevel.PUBLIC, PermissionLevel.ADMIN)
        )

    def test_user_can_access_public(self):
        ts = ToolSystem(register_builtins=False)
        self.assertTrue(
            ts._check_permission(PermissionLevel.USER, PermissionLevel.PUBLIC)
        )

    def test_user_can_access_user(self):
        ts = ToolSystem(register_builtins=False)
        self.assertTrue(
            ts._check_permission(PermissionLevel.USER, PermissionLevel.USER)
        )

    def test_user_cannot_access_admin(self):
        ts = ToolSystem(register_builtins=False)
        self.assertFalse(
            ts._check_permission(PermissionLevel.USER, PermissionLevel.ADMIN)
        )

    def test_admin_can_access_all(self):
        ts = ToolSystem(register_builtins=False)
        for perm in [
            PermissionLevel.PUBLIC,
            PermissionLevel.USER,
            PermissionLevel.ADMIN,
        ]:
            self.assertTrue(ts._check_permission(PermissionLevel.ADMIN, perm))


# ─── call_tool tests ───────────────────────────────────────────────


class TestCallTool(unittest.TestCase):
    """工具调用"""

    def test_call_nonexistent_tool(self):
        ts = ToolSystem(register_builtins=False)
        result = asyncio.run(ts.call_tool("nonexistent", PermissionLevel.PUBLIC))
        self.assertFalse(result["success"])
        self.assertIn("不存在", result["error"])

    def test_call_disabled_tool(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("disabled_tool", enabled=False)
        ts.register_tool(tool)
        result = asyncio.run(ts.call_tool("disabled_tool", PermissionLevel.PUBLIC))
        self.assertFalse(result["success"])
        self.assertIn("禁用", result["error"])

    def test_call_tool_insufficient_permission(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("admin_tool", permission=PermissionLevel.ADMIN)
        ts.register_tool(tool)
        result = asyncio.run(
            ts.call_tool("admin_tool", PermissionLevel.PUBLIC, query="test")
        )
        self.assertFalse(result["success"])
        self.assertIn("权限不足", result["error"])

    def test_call_tool_validation_error(self):
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool(
            "val_tool",
            params=[
                ToolParameter(name="required_field", type="str", required=True),
            ],
        )
        ts.register_tool(tool)
        result = asyncio.run(ts.call_tool("val_tool", PermissionLevel.PUBLIC))
        self.assertFalse(result["success"])
        self.assertIn("缺少必填参数", result["error"])

    def test_call_tool_sync_execute_success(self):
        mock_exec = MagicMock(return_value={"data": "hello"})
        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("sync_tool", execute=mock_exec)
        ts.register_tool(tool)
        result = asyncio.run(
            ts.call_tool("sync_tool", PermissionLevel.PUBLIC, query="test")
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"data": "hello"})

    def test_call_tool_async_execute_success(self):
        async def async_exec(**kwargs):
            return {"async_data": True}

        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("async_tool", execute=async_exec)
        ts.register_tool(tool)
        result = asyncio.run(
            ts.call_tool("async_tool", PermissionLevel.PUBLIC, query="test")
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"async_data": True})

    def test_call_tool_exception_returns_error(self):
        def failing_exec(**kwargs):
            raise RuntimeError("boom")

        ts = ToolSystem(register_builtins=False)
        tool = _make_tool("fail_tool", execute=failing_exec)
        ts.register_tool(tool)
        result = asyncio.run(
            ts.call_tool("fail_tool", PermissionLevel.PUBLIC, query="test")
        )
        self.assertFalse(result["success"])
        self.assertIn("boom", result["error"])


# ─── Command allowlist enforcement ─────────────────────────────────


class TestCommandAllowlist(unittest.TestCase):
    """命令白名单"""

    def test_allowed_commands_is_set(self):
        self.assertIsInstance(ALLOWED_COMMANDS, set)

    def test_safe_commands_in_allowlist(self):
        for cmd in ["ls", "cat", "head", "tail", "wc", "echo", "pwd", "grep", "find"]:
            self.assertIn(cmd, ALLOWED_COMMANDS)

    def test_dangerous_commands_not_in_allowlist(self):
        for cmd in [
            "rm",
            "rmdir",
            "mv",
            "cp",
            "chmod",
            "chown",
            "sudo",
            "dd",
            "mkfs",
            "format",
            "shutdown",
            "reboot",
            "kill",
            "curl",
            "wget",
            "bash",
            "sh",
            "python",
            "perl",
            "ruby",
            "node",
        ]:
            self.assertNotIn(cmd, ALLOWED_COMMANDS)


class TestCommandInjectionPrevention(unittest.TestCase):
    """命令注入防护

    The defense model:
    1. shlex.split + create_subprocess_exec (no shell=True) means shell
       metacharacters (;, |, $(), ``) are treated as literal arguments,
       not shell operators.
    2. The base_cmd allowlist check on the first token is the primary gate.
    """

    def _run_command(self, command: str):
        ts = ToolSystem(register_builtins=False)
        return asyncio.run(ts._execute_run_command(command))

    def test_rm_rf_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("rm -rf /")
        self.assertIn("不被允许", str(ctx.exception))

    def test_semicolon_injection_base_cmd_is_ls(self):
        """'ls ; rm -rf /' → shlex.split gives ['ls', ';', 'rm', '-rf', '/'].
        base_cmd='ls' is allowed, but create_subprocess_exec treats ';' as a
        literal arg to ls, not a shell operator. So this is safe by design.
        We verify the command is NOT rejected by the allowlist (base_cmd=ls)."""
        ts = ToolSystem(register_builtins=False)
        with patch("opc_manager.tool_system.asyncio.create_subprocess_exec") as mock_sp:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_sp.return_value = mock_proc
            # Should NOT raise — base_cmd is 'ls' which is allowed
            result = asyncio.run(ts._execute_run_command("ls ; rm -rf /"))
            self.assertEqual(result["return_code"], 0)

    def test_dollar_substitution_base_cmd_is_echo(self):
        """'echo $(cat /etc/passwd)' → base_cmd='echo' is allowed.
        create_subprocess_exec won't interpret $() — it's a literal arg."""
        ts = ToolSystem(register_builtins=False)
        with patch("opc_manager.tool_system.asyncio.create_subprocess_exec") as mock_sp:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_sp.return_value = mock_proc
            result = asyncio.run(ts._execute_run_command("echo $(cat /etc/passwd)"))
            self.assertEqual(result["return_code"], 0)

    def test_backtick_injection_base_cmd_is_echo(self):
        """'echo `cat /etc/passwd`' → base_cmd='echo' is allowed.
        create_subprocess_exec won't interpret backticks."""
        ts = ToolSystem(register_builtins=False)
        with patch("opc_manager.tool_system.asyncio.create_subprocess_exec") as mock_sp:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_sp.return_value = mock_proc
            result = asyncio.run(ts._execute_run_command("echo `cat /etc/passwd`"))
            self.assertEqual(result["return_code"], 0)

    def test_pipe_injection_base_cmd_is_ls(self):
        """'ls | rm -rf /' → base_cmd='ls' is allowed.
        create_subprocess_exec treats '|' as a literal arg."""
        ts = ToolSystem(register_builtins=False)
        with patch("opc_manager.tool_system.asyncio.create_subprocess_exec") as mock_sp:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_sp.return_value = mock_proc
            result = asyncio.run(ts._execute_run_command("ls | rm -rf /"))
            self.assertEqual(result["return_code"], 0)

    def test_dangerous_base_cmd_rejected_regardless_of_injection(self):
        """If the base command itself is dangerous, it's rejected outright."""
        with self.assertRaises(Exception) as ctx:
            self._run_command("rm -rf /")
        self.assertIn("不被允许", str(ctx.exception))

    def test_sudo_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("sudo ls")
        self.assertIn("不被允许", str(ctx.exception))

    def test_curl_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("curl http://evil.com")
        self.assertIn("不被允许", str(ctx.exception))

    def test_wget_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("wget http://evil.com")
        self.assertIn("不被允许", str(ctx.exception))

    def test_empty_command_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("")
        self.assertIn("空命令", str(ctx.exception))

    def test_whitespace_only_command_rejected(self):
        with self.assertRaises(Exception) as ctx:
            self._run_command("   ")
        self.assertIn("空命令", str(ctx.exception))

    def test_allowed_command_accepted(self):
        """ls is in ALLOWED_COMMANDS — should not raise ValueError."""
        ts = ToolSystem(register_builtins=False)
        with patch("opc_manager.tool_system.asyncio.create_subprocess_exec") as mock_sp:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"file.txt\n", b""))
            mock_proc.returncode = 0
            mock_sp.return_value = mock_proc
            result = asyncio.run(ts._execute_run_command("ls"))
            self.assertEqual(result["return_code"], 0)

    def test_shell_metacharacters_are_not_interpreted(self):
        """Verify that shlex.split + subprocess_exec neutralizes shell metacharacters.
        The injected payload becomes a literal argument, not a command."""
        import shlex

        # Semicolons, pipes, and subshells are split into literal tokens
        tokens = shlex.split("ls ; rm -rf /")
        self.assertEqual(tokens[0], "ls")  # base_cmd is safe
        self.assertIn(";", tokens)  # ';' is just an arg, not a shell operator


# ─── Path validation ───────────────────────────────────────────────


class TestPathValidation(unittest.TestCase):
    """路径校验"""

    def test_path_with_dotdot_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            _validate_path("/some/safe/../etc/passwd")
        self.assertIn("..", str(ctx.exception))

    def test_path_outside_allowed_dirs_rejected(self):
        _configure_allowed_dirs(["/tmp/safe_dir"])
        with self.assertRaises(ValueError) as ctx:
            _validate_path("/etc/passwd")
        self.assertIn("超出允许范围", str(ctx.exception))

    def test_path_within_allowed_dirs_accepted(self):
        import tempfile

        with tempfile.TemporaryDirectory() as safe_dir:
            _configure_allowed_dirs([safe_dir])
            result = _validate_path(os.path.join(safe_dir, "file.txt"))
            # Both _configure_allowed_dirs and _validate_path use os.path.realpath,
            # so compare against the resolved path
            self.assertTrue(result.startswith(os.path.realpath(safe_dir)))


# ─── Input length validation ───────────────────────────────────────


class TestInputLengthValidation(unittest.TestCase):
    """输入长度校验"""

    def test_within_limit_ok(self):
        _validate_input_length("user_input", "short text")

    def test_exceeds_limit_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _validate_input_length(
                "user_input", "x" * (INPUT_LENGTH_LIMITS["user_input"] + 1)
            )
        self.assertIn("超出长度限制", str(ctx.exception))

    def test_command_arg_limit(self):
        with self.assertRaises(ValueError):
            _validate_input_length(
                "command_arg", "x" * (INPUT_LENGTH_LIMITS["command_arg"] + 1)
            )

    def test_file_path_limit(self):
        with self.assertRaises(ValueError):
            _validate_input_length(
                "file_path", "x" * (INPUT_LENGTH_LIMITS["file_path"] + 1)
            )

    def test_unknown_type_uses_default(self):
        # Unknown input type defaults to 10000
        _validate_input_length("unknown_type", "short")
        with self.assertRaises(ValueError):
            _validate_input_length("unknown_type", "x" * 10001)


# ─── to_dict ───────────────────────────────────────────────────────


class TestToolSystemToDict(unittest.TestCase):
    """to_dict 序列化"""

    def test_to_dict_structure(self):
        ts = ToolSystem(register_builtins=False)
        ts.register_tool(
            _make_tool(
                "t1", category=ToolCategory.SEARCH, permission=PermissionLevel.PUBLIC
            )
        )
        d = ts.to_dict()
        self.assertEqual(d["type"], "tool_system")
        self.assertEqual(d["tool_count"], 1)
        self.assertIn("categories", d)
        self.assertIn("permissions", d)
        self.assertIn("tools", d)
        self.assertIn("t1", d["tools"])


# ─── AuditLogger tests ─────────────────────────────────────────────


class TestAuditLogger(unittest.TestCase):
    """审计日志"""

    def test_configure_sets_log_file(self):
        original = AuditLogger._log_file
        AuditLogger.configure("/tmp/test_audit.jsonl")
        self.assertEqual(AuditLogger._log_file, "/tmp/test_audit.jsonl")
        AuditLogger.configure(original)

    def test_write_sync_creates_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.jsonl")
            AuditLogger.configure(log_file)
            AuditLogger._write_sync({"event": "test", "data": 123})
            with open(log_file) as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            import json

            record = json.loads(lines[0])
            self.assertEqual(record["event"], "test")

    def test_query_nonexistent_file_returns_empty(self):
        AuditLogger.configure("/tmp/nonexistent_audit_test.jsonl")
        result = AuditLogger.query()
        self.assertEqual(result, [])

    def test_log_sync_path(self):
        """AuditLogger.log falls back to _write_sync when no event loop"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit_sync.jsonl")
            AuditLogger.configure(log_file)
            # Reset queue/writer state
            AuditLogger._write_queue = None
            AuditLogger._writer_task = None
            AuditLogger._shutdown_event = None
            AuditLogger.log("TEST_EVENT", {"key": "value"})
            import json

            with open(log_file) as f:
                record = json.loads(f.readline())
            self.assertEqual(record["event_type"], "TEST_EVENT")


# ─── Email validation in _execute_send_email ────────────────────────


class TestEmailValidation(unittest.TestCase):
    """邮件地址校验"""

    def test_invalid_email_returns_error(self):
        ts = ToolSystem(register_builtins=False)
        result = asyncio.run(
            ts._execute_send_email(to="not-an-email", subject="test", body="hi")
        )
        self.assertFalse(result.get("sent", True))

    def test_empty_email_returns_error(self):
        ts = ToolSystem(register_builtins=False)
        result = asyncio.run(ts._execute_send_email(to="", subject="test", body="hi"))
        self.assertFalse(result.get("sent", True))

    def test_valid_email_format(self):
        ts = ToolSystem(register_builtins=False)
        # Without SMTP configured, it falls back to logging the notification
        result = asyncio.run(
            ts._execute_send_email(to="user@example.com", subject="test", body="hi")
        )
        # Should succeed (logged mode, not SMTP)
        self.assertTrue(result.get("sent", False))
        self.assertEqual(result.get("delivery_mode"), "logged")


# ─── Web search placeholder ────────────────────────────────────────


class TestWebSearchPlaceholder(unittest.TestCase):
    """网络搜索占位实现"""

    def test_returns_placeholder_results(self):
        ts = ToolSystem(register_builtins=False)
        result = asyncio.run(ts._execute_web_search("test query", max_results=3))
        self.assertEqual(result["query"], "test query")
        self.assertLessEqual(result["total"], 3)
        self.assertIsInstance(result["results"], list)


# ─── Command timeout ───────────────────────────────────────────────


class TestCommandTimeout(unittest.TestCase):
    """命令超时"""

    def test_timeout_constant(self):
        self.assertEqual(COMMAND_TIMEOUT_SECONDS, 30)


if __name__ == "__main__":
    unittest.main()
