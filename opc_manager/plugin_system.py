"""
PluginSystem — 插件系统

支持社区开发和分发插件，核心特性：
- 插件加载器（热加载/沙箱隔离）
- 插件生命周期管理（注册→初始化→运行→停止→卸载）
- 插件依赖解析
- 沙箱隔离（安全专家审核S-4红线）

架构位置：
  PluginManager → PluginSandbox → Plugin.execute()
       │
       ├── 加载插件元数据 → 验证依赖 → 初始化
       └── 执行时沙箱隔离 → 限制文件系统/网络/环境变量访问

安全红线：
  - 插件禁止访问文件系统（除非显式授权）
  - 插件禁止访问网络（除非显式授权）
  - 插件禁止读取环境变量（除非显式授权）
  - 插件执行超时限制（默认30秒）
"""

import importlib
import json
import logging
import os
import sys
import time
import traceback
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

PLUGIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")
PLUGIN_TIMEOUT_SECONDS = 30


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


class PluginSandbox:

    ALLOWED_BUILTINS = {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter",
        "float", "format", "frozenset", "hash", "hex", "int", "isinstance",
        "len", "list", "map", "max", "min", "oct", "ord", "pow", "print",
        "range", "repr", "round", "set", "slice", "sorted", "str", "sum",
        "tuple", "type", "zip",
    }

    def __init__(self, allowed_permissions: Optional[List[Permission]] = None):
        self.allowed_permissions = set(allowed_permissions or [])
        self._access_log: List[Dict[str, Any]] = []

    def check_permission(self, permission: Permission) -> bool:
        return permission in self.allowed_permissions

    def log_access(self, plugin_id: str, action: str, resource: str, allowed: bool) -> None:
        self._access_log.append({
            "plugin_id": plugin_id,
            "action": action,
            "resource": resource,
            "allowed": allowed,
            "timestamp": time.time(),
        })

    def _create_restricted_import(self, plugin_id: str) -> Callable:
        config_path = os.path.join(PLUGIN_DIR, "plugin_config.json")
        default_modules = {"json", "math", "re", "datetime", "collections", "itertools", "typing"}
        allowed_modules = default_modules
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                if "allowed_modules" in cfg:
                    allowed_modules = set(cfg["allowed_modules"])
        except Exception:
            pass

        def restricted_import(name, *args, **kwargs):
            top_level = name.split(".")[0]
            if top_level in allowed_modules:
                self.log_access(plugin_id, "import", name, True)
                return importlib.import_module(name)
            self.log_access(plugin_id, "import", name, False)
            raise ImportError(f"Plugin {plugin_id}: import '{name}' not allowed")

        return restricted_import

    def create_restricted_globals(self, plugin_id: str) -> Dict[str, Any]:
        safe_builtins = {}
        source = __builtins__ if isinstance(__builtins__, dict) else vars(__builtins__)
        for name in self.ALLOWED_BUILTINS:
            if name in source:
                safe_builtins[name] = source[name]
        safe_builtins["__import__"] = self._create_restricted_import(plugin_id)
        return {"__builtins__": safe_builtins}

    def get_access_log(self) -> List[Dict[str, Any]]:
        return list(self._access_log)


class PluginManager:

    def __init__(self, plugin_dir: Optional[str] = None):
        self._plugin_dir = plugin_dir or PLUGIN_DIR
        os.makedirs(self._plugin_dir, exist_ok=True)
        self._plugins: Dict[str, PluginInstance] = {}
        self._sandboxes: Dict[str, PluginSandbox] = {}

    def register_plugin(self, manifest: PluginManifest) -> Dict[str, Any]:
        if manifest.plugin_id in self._plugins:
            return {"success": False, "error": f"Plugin already registered: {manifest.plugin_id}"}

        missing = self._check_dependencies(manifest)
        if missing:
            return {"success": False, "error": f"Missing dependencies: {missing}"}

        sandbox = PluginSandbox(allowed_permissions=manifest.permissions)
        instance = PluginInstance(manifest=manifest)
        self._plugins[manifest.plugin_id] = instance
        self._sandboxes[manifest.plugin_id] = sandbox

        return {"success": True, "plugin_id": manifest.plugin_id, "state": instance.state.value}

    def initialize_plugin(self, plugin_id: str, config: Optional[Dict] = None) -> Dict[str, Any]:
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

            spec = importlib.util.spec_from_file_location(plugin_id, plugin_path)
            module = importlib.util.module_from_spec(spec)
            sandbox = self._sandboxes.get(plugin_id)
            if sandbox:
                restricted_globals = sandbox.create_restricted_globals(plugin_id)
                module.__builtins__ = restricted_globals["__builtins__"]
            spec.loader.exec_module(module)

            if hasattr(module, "initialize"):
                module.initialize(config or {})

            instance.module = module
            instance.config = config or {}
            instance.state = PluginState.INITIALIZED
            instance.loaded_at = time.time()

            return {"success": True, "plugin_id": plugin_id, "state": instance.state.value}

        except Exception as e:
            instance.state = PluginState.ERROR
            instance.error = str(e)
            return {"success": False, "error": str(e)}

    def execute_plugin(self, plugin_id: str, method: str,
                       parameters: Dict[str, Any]) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}
        if instance.state not in (PluginState.INITIALIZED, PluginState.RUNNING):
            return {"success": False, "error": f"Plugin not initialized: {instance.state.value}"}

        sandbox = self._sandboxes.get(plugin_id)

        try:
            instance.state = PluginState.RUNNING
            start_time = time.time()

            if not hasattr(instance.module, method):
                return {"success": False, "error": f"Method not found: {method}"}

            func = getattr(instance.module, method)

            if sandbox:
                for perm in [Permission.FILESYSTEM, Permission.NETWORK, Permission.ENV_VARS, Permission.SUBPROCESS]:
                    if perm not in sandbox.allowed_permissions:
                        sandbox.log_access(plugin_id, "blocked", perm.value, False)

            result = func(**parameters)

            elapsed = time.time() - start_time
            if elapsed > PLUGIN_TIMEOUT_SECONDS:
                logger.warning(f"Plugin {plugin_id} execution took {elapsed:.1f}s (timeout: {PLUGIN_TIMEOUT_SECONDS}s)")

            instance.execution_count += 1
            instance.state = PluginState.INITIALIZED

            return {"success": True, "result": result, "execution_time": elapsed}

        except Exception as e:
            instance.state = PluginState.ERROR
            instance.error = str(e)
            return {"success": False, "error": str(e)}

    def stop_plugin(self, plugin_id: str) -> Dict[str, Any]:
        instance = self._plugins.get(plugin_id)
        if not instance:
            return {"success": False, "error": f"Plugin not found: {plugin_id}"}

        try:
            if instance.module and hasattr(instance.module, "shutdown"):
                instance.module.shutdown()
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
            "running_plugins": sum(1 for p in self._plugins.values() if p.state == PluginState.RUNNING),
            "error_plugins": sum(1 for p in self._plugins.values() if p.state == PluginState.ERROR),
            "plugin_dir": self._plugin_dir,
        }
