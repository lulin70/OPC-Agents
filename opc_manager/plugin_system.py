"""
PluginSystem — 插件系统

支持社区开发和分发插件，核心特性：
- 插件加载器（热加载/进程级沙箱隔离）
- 插件生命周期管理（注册→初始化→运行→停止→卸载）
- 插件依赖解析
- subprocess进程隔离（安全专家审核S-4红线）

架构位置：
  PluginManager → PluginProcessPool → plugin_worker.py (子进程)
       │                                    │
       ├── 加载插件元数据 → 验证依赖 → 初始化  └── 受限import + rlimit + 超时kill
       └── 执行时进程隔离 → 限制文件系统/网络/环境变量/内存/CPU

安全红线：
  - 插件在独立子进程中运行，主进程不受影响
  - 插件禁止访问文件系统（除非显式授权）
  - 插件禁止访问网络（除非显式授权）
  - 插件禁止读取环境变量（除非显式授权）
  - 插件内存限制256MB，CPU时间限制30秒
  - 插件执行超时限制（默认30秒），超时强制kill
  - 插件仅允许导入安全模块（json/math/re/datetime等）
"""

import importlib
import json
import logging
import os
import subprocess
import sys
import time
import threading
import traceback
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future

logger = logging.getLogger(__name__)

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
PLUGIN_TIMEOUT_SECONDS = 30
MAX_CONCURRENT_PLUGINS = 4

_WORKER_PATH = os.path.join(
    os.path.dirname(__file__), "experimental", "plugin_worker.py"
)


class PluginState(str, Enum):
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class Permission(str, Enum):
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    ENV_VARS = "env_vars"
    SUBPROCESS = "subprocess"


@dataclass
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    entry_point: str
    dependencies: List[str] = field(default_factory=list)
    permissions: List[Permission] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    min_app_version: str = "0.1.0"


@dataclass
class PluginInstance:
    manifest: PluginManifest
    state: PluginState = PluginState.REGISTERED
    module: Any = None
    config: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    loaded_at: float = 0.0
    execution_count: int = 0


class PluginProcessPool:
    """插件子进程池 — 管理并发执行和资源回收

    - 限制最大并发插件数
    - 超时强制kill子进程
    - 僵尸进程回收
    - 执行统计
    """

    def __init__(
        self,
        max_workers: int = MAX_CONCURRENT_PLUGINS,
        default_timeout: int = PLUGIN_TIMEOUT_SECONDS,
    ):
        self._max_workers = max_workers
        self._default_timeout = default_timeout
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_processes: Dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "timeout_kills": 0,
        }

    def execute_in_sandbox(
        self,
        plugin_id: str,
        plugin_path: str,
        method: str,
        parameters: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        timeout = timeout or self._default_timeout
        request = {
            "action": "execute",
            "plugin_path": plugin_path,
            "method": method,
            "parameters": parameters,
        }

        self._stats["total_executions"] += 1
        start_time = time.time()

        try:
            process = subprocess.Popen(
                [sys.executable, _WORKER_PATH],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            with self._lock:
                self._active_processes[plugin_id] = process

            try:
                stdout, stderr = process.communicate(
                    input=json.dumps(request, ensure_ascii=False) + "\n",
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                self._stats["timeout_kills"] += 1
                self._stats["failed_executions"] += 1
                elapsed = time.time() - start_time
                logger.warning(
                    "Plugin %s killed after %.1fs (timeout: %ss)",
                    plugin_id,
                    elapsed,
                    timeout,
                )
                return {
                    "success": False,
                    "error": f"Plugin execution timed out ({timeout}s)",
                    "execution_time": elapsed,
                }
            finally:
                with self._lock:
                    self._active_processes.pop(plugin_id, None)

            elapsed = time.time() - start_time

            if process.returncode != 0:
                self._stats["failed_executions"] += 1
                error_msg = (
                    stderr.strip()[:200]
                    if stderr
                    else f"Process exited with code {process.returncode}"
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "execution_time": elapsed,
                }

            if not stdout.strip():
                self._stats["failed_executions"] += 1
                return {
                    "success": False,
                    "error": "Plugin produced no output",
                    "execution_time": elapsed,
                }

            try:
                result = json.loads(stdout.strip())
            except json.JSONDecodeError as e:
                self._stats["failed_executions"] += 1
                return {
                    "success": False,
                    "error": f"Invalid plugin output: {e}",
                    "execution_time": elapsed,
                }

            result["execution_time"] = elapsed
            if result.get("success"):
                self._stats["successful_executions"] += 1
            else:
                self._stats["failed_executions"] += 1

            return result

        except Exception as e:
            self._stats["failed_executions"] += 1
            with self._lock:
                self._active_processes.pop(plugin_id, None)
            return {"success": False, "error": f"Sandbox error: {str(e)}"}

    def submit_async(
        self,
        plugin_id: str,
        plugin_path: str,
        method: str,
        parameters: Dict[str, Any],
        timeout: Optional[int] = None,
        callback: Optional[Callable] = None,
    ) -> Future:
        future = self._executor.submit(
            self.execute_in_sandbox,
            plugin_id,
            plugin_path,
            method,
            parameters,
            timeout,
        )
        if callback:
            future.add_done_callback(callback)
        return future

    def kill_plugin(self, plugin_id: str) -> bool:
        with self._lock:
            process = self._active_processes.get(plugin_id)
        if process and process.poll() is None:
            process.kill()
            logger.warning("Force killed plugin process: %s", plugin_id)
            return True
        return False

    def kill_all(self) -> int:
        killed = 0
        with self._lock:
            for pid, process in list(self._active_processes.items()):
                if process.poll() is None:
                    process.kill()
                    killed += 1
            self._active_processes.clear()
        return killed

    def get_active_count(self) -> int:
        with self._lock:
            return sum(1 for p in self._active_processes.values() if p.poll() is None)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "active_processes": self.get_active_count(),
            "max_workers": self._max_workers,
        }

    def shutdown(self, wait: bool = True) -> None:
        self.kill_all()
        self._executor.shutdown(wait=wait)


class PluginSandbox:
    """插件沙箱 — 兼容层，委托给PluginProcessPool执行

    保留原有的权限检查和访问日志功能，
    execute()方法委托给进程池实现真正的进程级隔离。
    """

    def __init__(
        self,
        allowed_permissions: Optional[List[Permission]] = None,
        process_pool: Optional[PluginProcessPool] = None,
    ):
        self.allowed_permissions = set(allowed_permissions or [])
        self._access_log: List[Dict[str, Any]] = []
        self._process_pool = process_pool

    def set_process_pool(self, pool: PluginProcessPool) -> None:
        self._process_pool = pool

    def check_permission(self, permission: Permission) -> bool:
        return permission in self.allowed_permissions

    def log_access(
        self, plugin_id: str, action: str, resource: str, allowed: bool
    ) -> None:
        self._access_log.append(
            {
                "plugin_id": plugin_id,
                "action": action,
                "resource": resource,
                "allowed": allowed,
                "timestamp": time.time(),
            }
        )

    def execute_in_sandbox(
        self,
        plugin_id: str,
        plugin_path: str,
        method: str,
        parameters: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        if self._process_pool is None:
            self._process_pool = PluginProcessPool()

        for perm in [
            Permission.FILESYSTEM,
            Permission.NETWORK,
            Permission.ENV_VARS,
            Permission.SUBPROCESS,
        ]:
            if perm not in self.allowed_permissions:
                self.log_access(plugin_id, "blocked", perm.value, False)

        return self._process_pool.execute_in_sandbox(
            plugin_id,
            plugin_path,
            method,
            parameters,
            timeout,
        )

    def get_access_log(self) -> List[Dict[str, Any]]:
        return list(self._access_log)


class PluginManager:

    def __init__(self, plugin_dir: Optional[str] = None):
        self._plugin_dir = plugin_dir or PLUGIN_DIR
        os.makedirs(self._plugin_dir, exist_ok=True)
        self._plugins: Dict[str, PluginInstance] = {}
        self._sandboxes: Dict[str, PluginSandbox] = {}
        self._process_pool = PluginProcessPool()

    def register_plugin(self, manifest: PluginManifest) -> Dict[str, Any]:
        if manifest.plugin_id in self._plugins:
            return {
                "success": False,
                "error": f"Plugin already registered: {manifest.plugin_id}",
            }

        missing = self._check_dependencies(manifest)
        if missing:
            return {"success": False, "error": f"Missing dependencies: {missing}"}

        sandbox = PluginSandbox(
            allowed_permissions=manifest.permissions,
            process_pool=self._process_pool,
        )
        instance = PluginInstance(manifest=manifest)
        self._plugins[manifest.plugin_id] = instance
        self._sandboxes[manifest.plugin_id] = sandbox

        return {
            "success": True,
            "plugin_id": manifest.plugin_id,
            "state": instance.state.value,
        }

    def initialize_plugin(
        self, plugin_id: str, config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}
        if instance.state == PluginState.RUNNING:
            return {"success": False, "error": f"Plugin already running: {plugin_id}"}

        try:
            plugin_path = os.path.join(self._plugin_dir, instance.manifest.entry_point)
            if not os.path.exists(plugin_path):
                instance.state = PluginState.ERROR
                instance.error = f"Entry point not found: {plugin_path}"
                return {"success": False, "error": instance.error}

            instance.config = config or {}
            instance.state = PluginState.INITIALIZED
            instance.loaded_at = time.time()

            return {
                "success": True,
                "plugin_id": plugin_id,
                "state": instance.state.value,
            }

        except Exception as e:
            instance.state = PluginState.ERROR
            instance.error = str(e)
            return {"success": False, "error": str(e)}

    def execute_plugin(
        self, plugin_id: str, method: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}
        if instance.state not in (PluginState.INITIALIZED, PluginState.RUNNING):
            return {
                "success": False,
                "error": f"Plugin not initialized: {instance.state.value}",
            }

        sandbox = self._sandboxes.get(plugin_id)

        try:
            instance.state = PluginState.RUNNING
            start_time = time.time()

            plugin_path = os.path.realpath(
                os.path.join(self._plugin_dir, instance.manifest.entry_point)
            )
            if not plugin_path.startswith(os.path.realpath(self._plugin_dir)):
                instance.state = PluginState.ERROR
                instance.error = "Entry point escapes plugin directory"
                return {
                    "success": False,
                    "error": "Entry point escapes plugin directory",
                }

            if sandbox:
                result = sandbox.execute_in_sandbox(
                    plugin_id,
                    plugin_path,
                    method,
                    parameters,
                    timeout=PLUGIN_TIMEOUT_SECONDS,
                )
            else:
                instance.state = PluginState.ERROR
                instance.error = "No sandbox configured, refusing to execute"
                return {
                    "success": False,
                    "error": f"Plugin {plugin_id} has no sandbox, refusing to execute",
                }

            elapsed = time.time() - start_time
            instance.execution_count += 1
            instance.state = PluginState.INITIALIZED

            return result

        except Exception as e:
            instance.state = PluginState.ERROR
            instance.error = str(e)
            return {"success": False, "error": str(e)}

    def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}

        try:
            self._process_pool.kill_plugin(plugin_id)
            instance.state = PluginState.STOPPED
            return {"success": True, "plugin_id": plugin_id, "state": "stopped"}
        except Exception as e:
            instance.state = PluginState.ERROR
            instance.error = str(e)
            return {"success": False, "error": str(e)}

    def unload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}
        if instance.state == PluginState.RUNNING:
            self.stop_plugin(plugin_id)

        del self._plugins[plugin_id]
        if plugin_id in self._sandboxes:
            del self._sandboxes[plugin_id]

        return {"success": True, "plugin_id": plugin_id}

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {
                "plugin_id": p.manifest.plugin_id,
                "name": p.manifest.name,
                "version": p.manifest.version,
                "state": p.state.value,
                "execution_count": p.execution_count,
                "permissions": [perm.value for perm in p.manifest.permissions],
            }
            for p in self._plugins.values()
        ]

    def get_plugin_info(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return None
        return {
            "plugin_id": instance.manifest.plugin_id,
            "name": instance.manifest.name,
            "version": instance.manifest.version,
            "description": instance.manifest.description,
            "author": instance.manifest.author,
            "state": instance.state.value,
            "permissions": [p.value for p in instance.manifest.permissions],
            "dependencies": instance.manifest.dependencies,
            "execution_count": instance.execution_count,
            "error": instance.error,
        }

    def _check_dependencies(self, manifest: PluginManifest) -> List[str]:
        missing = []
        for dep in manifest.dependencies:
            try:
                importlib.import_module(dep)
            except ImportError:
                missing.append(dep)
        return missing

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_plugins": len(self._plugins),
            "running_plugins": sum(
                1 for p in self._plugins.values() if p.state == PluginState.RUNNING
            ),
            "error_plugins": sum(
                1 for p in self._plugins.values() if p.state == PluginState.ERROR
            ),
            "plugin_dir": self._plugin_dir,
            "process_pool": self._process_pool.get_stats(),
        }

    def shutdown(self) -> None:
        self._process_pool.shutdown(wait=True)
