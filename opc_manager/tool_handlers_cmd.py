"""
命令执行工具处理器 (CommandHandlers) — Mixin

从 tool_system.py 拆分（Phase 3 架构演进），职责：
- 系统命令执行工具（_execute_run_command）

安全防护（独立模块以强调命令注入防护的重要性）：
- shlex.split 正确分词（防止 shell 元字符注入）
- ALLOWED_COMMANDS 白名单（仅允许只读安全命令）
- 输入长度校验（command_arg 限 1000 字符）
- COMMAND_TIMEOUT_SECONDS 超时保护（默认 30s）
- AuditLogger 记录命令拒绝与执行

作为 Mixin 供 ToolSystem（Facade）继承。
"""

import asyncio
import logging
import os
import shlex
from typing import Any, Dict, Optional

from opc_manager.tool_audit_logger import AuditLogger
from opc_manager.tool_registry import _validate_input_length

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

COMMAND_TIMEOUT_SECONDS = 30


class CommandHandlers:
    """命令执行工具处理器 Mixin — 供 ToolSystem 继承。"""

    async def _execute_run_command(
        self, command: str, cwd: Optional[str] = None
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
