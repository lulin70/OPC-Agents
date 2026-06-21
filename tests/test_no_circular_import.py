"""循环导入检测测试 [S2-T8]

验证 opc_manager 核心模块无循环导入，且核心模块不再使用模块级 __getattr__ 延迟导入。
"""

import importlib
import os
import sys

import pytest


class TestNoCircularImport:
    """验证关键模块无循环导入"""

    @pytest.mark.parametrize(
        "module_name",
        [
            "opc_manager",
            "opc_manager.agent_loop",
            "opc_manager.consensus_engine",
            "opc_manager.strategist_brain",
            "opc_manager.executor_brain",
            "opc_manager.reflector_brain",
            "opc_manager.task_lifecycle",
            "opc_manager.intent_classifier",
            "opc_manager.skill_registry",
            "opc_manager.protocols",
        ],
    )
    def test_module_imports_without_circular(self, module_name):
        """每个核心模块都能独立导入无循环依赖"""
        # 清除已导入的 opc_manager 模块，确保独立导入测试有效
        for key in list(sys.modules.keys()):
            if "opc_manager" in key:
                del sys.modules[key]
        # 尝试导入
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            if "circular" in str(e).lower():
                pytest.fail(f"循环导入: {module_name} -> {e}")
            # 其他 ImportError 可能是缺少依赖，跳过
            pytest.skip(f"非循环导入错误: {e}")

    def test_no_getattr_in_core_modules(self):
        """核心模块不应有模块级 __getattr__ 延迟导入"""
        core_modules_dir = os.path.dirname(
            importlib.import_module("opc_manager").__file__
        )
        forbidden_files = [
            "agent_loop.py",
            "consensus_engine.py",
            "strategist_brain.py",
            "executor_brain.py",
            "reflector_brain.py",
            "task_lifecycle.py",
            "intent_classifier.py",
            "skill_registry.py",
            "protocols.py",
            "__init__.py",
        ]
        for fname in forbidden_files:
            fpath = os.path.join(core_modules_dir, fname)
            if not os.path.exists(fpath):
                continue
            with open(fpath) as f:
                content = f.read()
            # 模块级 __getattr__ 通常在文件顶层（不以空格开头）
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "def __getattr__" in line and not line.startswith(" "):
                    pytest.fail(
                        f"{fname} L{i+1}: 模块级 __getattr__ 延迟导入: {line.strip()}"
                    )

    def test_package_symbols_eagerly_available(self):
        """[S2-T8] 包顶层符号在导入后立即可用（无需 __getattr__ 触发）"""
        for key in list(sys.modules.keys()):
            if "opc_manager" in key:
                del sys.modules[key]
        import opc_manager

        # 这些符号此前通过 __getattr__ 延迟加载，现在应直接存在于模块字典
        expected_symbols = [
            "StrategistBrain",
            "ExecutorBrain",
            "ReflectorBrain",
            "ConsensusEngine",
            "Opinion",
            "SkillRegistry",
            "ToolSystem",
            "AgentLoop",
            "AgentContext",
            "EventEmitter",
        ]
        missing = [s for s in expected_symbols if s not in opc_manager.__dict__]
        assert not missing, f"以下符号未在包导入后立即可用: {missing}"
