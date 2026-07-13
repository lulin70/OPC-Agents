"""
文件系统工具处理器 (FileSystemHandlers) — Mixin

从 tool_system.py 拆分（Phase 3 架构演进），职责：
- 文件读取 / 写入 / 列表工具的执行逻辑
- 路径安全校验（_validate_path：禁止 .. 穿越 + 白名单目录限制）
- 输入长度校验（复用 tool_registry._validate_input_length）

作为 Mixin 供 ToolSystem（Facade）继承，方法通过 self 被 _register_builtin_tools
注册为 Tool.execute 回调。AuditLogger 记录所有路径访问（授权/拒绝）。
"""

import asyncio
import fnmatch
import logging
import os
from typing import Any, Dict, List, Optional

from opc_manager.tool_audit_logger import AuditLogger
from opc_manager.tool_registry import _validate_input_length

logger = logging.getLogger(__name__)

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


class FileSystemHandlers:
    """文件系统工具处理器 Mixin — 供 ToolSystem 继承。"""

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
        self, dir_path: str, pattern: Optional[str] = None
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
    def _list_files_sync(
        safe_path: str, pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        files = os.listdir(safe_path)
        if pattern:
            files = fnmatch.filter(files, pattern)
        file_info: List[Dict[str, Any]] = []
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
