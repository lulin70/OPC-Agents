"""
PluginWorker — 插件子进程入口

在独立子进程中加载并执行插件，通过stdin/stdout JSON通信。
主进程通过subprocess启动此模块，传递执行请求，接收执行结果。

通信协议：
  主进程 → 子进程: stdin写入JSON {"action":"execute","plugin_path":"...","method":"...","parameters":{...}}
  子进程 → 主进程: stdout写入JSON {"success":true,"result":...} 或 {"success":false,"error":"..."}
"""

import json
import os
import sys
import resource
import signal
import traceback

_MEMORY_LIMIT_MB = 256
_CPU_TIME_LIMIT_SECONDS = 30

ALLOWED_MODULES = frozenset(
    {
        "json",
        "math",
        "re",
        "datetime",
        "collections",
        "itertools",
        "typing",
        "string",
        "copy",
        "operator",
        "functools",
        "decimal",
        "fractions",
        "statistics",
        "textwrap",
        "unicodedata",
        "hashlib",
        "base64",
        "struct",
        "pprint",
    }
)


def _setup_resource_limits():
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limit_bytes = _MEMORY_LIMIT_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (min(limit_bytes, hard), hard))
    except (ValueError, resource.error):
        pass

    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_CPU)
        resource.setrlimit(resource.RLIMIT_CPU, (_CPU_TIME_LIMIT_SECONDS, hard))
    except (ValueError, resource.error):
        pass


def _cpu_timeout_handler(signum, frame):
    raise TimeoutError(f"Plugin CPU time limit exceeded ({_CPU_TIME_LIMIT_SECONDS}s)")


def _create_restricted_import():
    def restricted_import(name, *args, **kwargs):
        top_level = name.split(".")[0]
        if top_level in ALLOWED_MODULES:
            return __import__(name, *args, **kwargs)
        raise ImportError(f"Import '{name}' not allowed in plugin sandbox")

    return restricted_import


def _load_and_execute(plugin_path, method, parameters):
    import importlib.util

    if not os.path.exists(plugin_path):
        return {"success": False, "error": f"Plugin not found: {plugin_path}"}

    spec = importlib.util.spec_from_file_location("_sandboxed_plugin", plugin_path)
    module = importlib.util.module_from_spec(spec)

    builtins_dict = (
        dict(vars(__builtins__))
        if not isinstance(__builtins__, dict)
        else dict(__builtins__)
    )
    safe_builtins = {
        k: v
        for k, v in builtins_dict.items()
        if k
        in {
            "abs",
            "all",
            "any",
            "bool",
            "dict",
            "enumerate",
            "filter",
            "float",
            "format",
            "frozenset",
            "hash",
            "hex",
            "int",
            "isinstance",
            "len",
            "list",
            "map",
            "max",
            "min",
            "oct",
            "ord",
            "pow",
            "print",
            "range",
            "repr",
            "round",
            "set",
            "slice",
            "sorted",
            "str",
            "sum",
            "tuple",
            "zip",
            "True",
            "False",
            "None",
        }
    }
    safe_builtins["__import__"] = _create_restricted_import()
    module.__builtins__ = safe_builtins

    spec.loader.exec_module(module)

    if not hasattr(module, method):
        return {"success": False, "error": f"Method '{method}' not found in plugin"}

    func = getattr(module, method)
    if not callable(func):
        return {"success": False, "error": f"'{method}' is not callable"}

    result = func(**parameters)
    return {"success": True, "result": result}


def main():
    _setup_resource_limits()
    signal.signal(signal.SIGXCPU, _cpu_timeout_handler)

    try:
        request_line = sys.stdin.readline()
        if not request_line:
            sys.exit(0)

        request = json.loads(request_line.strip())
        action = request.get("action", "")

        if action == "execute":
            plugin_path = request["plugin_path"]
            method = request["method"]
            parameters = request.get("parameters", {})

            result = _load_and_execute(plugin_path, method, parameters)
            sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
        elif action == "ping":
            sys.stdout.write(json.dumps({"success": True, "pong": True}) + "\n")
            sys.stdout.flush()
        else:
            sys.stdout.write(
                json.dumps({"success": False, "error": f"Unknown action: {action}"})
                + "\n"
            )
            sys.stdout.flush()

    except TimeoutError as e:
        sys.stdout.write(json.dumps({"success": False, "error": str(e)}) + "\n")
        sys.stdout.flush()
        sys.exit(1)
    except MemoryError:
        sys.stdout.write(
            json.dumps({"success": False, "error": "Memory limit exceeded"}) + "\n"
        )
        sys.stdout.flush()
        sys.exit(1)
    except Exception as e:
        sys.stdout.write(
            json.dumps(
                {
                    "success": False,
                    "error": f"{type(e).__name__}: {str(e)}",
                    "traceback": traceback.format_exc(),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.stdout.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
