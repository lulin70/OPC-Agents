"""架构守护测试 — IOC 分层规则 enforcement

[P2-14] 虚拟分层配套测试，断言 OPC-Agents 的 5 层（I/C/O/S/F）依赖方向：
- F (Infra) 不依赖 C (Control) / S (Skills) / O (Output) / I (Input)
- S (Skills) 不依赖 C (Control)
- I (Input) 不依赖 C (Control) / O (Output) / S (Skills)

规则源于 docs/internal/DIRECTORY_STRUCTURE.md 的 IOC 原则。
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Set

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
OPC_MANAGER_DIR = PROJECT_ROOT / "opc_manager"


# 层次分类（与 DIRECTORY_STRUCTURE.md 一致）
INFRA_FILES = {
    "config.py",
    "constants.py",
    "data_manager.py",
    "data_backup.py",
    "settings.py",
    "settings_encryption.py",
    "settings_persistence.py",
    "settings_operations.py",
    "secure_storage.py",
    "audit_log.py",
    "monitoring.py",
    "performance_monitor.py",
    "error_handler.py",
    "protocols.py",
    "mcp_protocol.py",
    "mcp_transport.py",
    "embedding_service.py",
    "memory_bridge.py",
    "knowledge_bridge.py",
    "utils.py",
    "version.py",
    "unified_types.py",
    "tool_system.py",
    "tool_registry.py",
    "tool_handlers_fs.py",
    "tool_handlers_smtp.py",
    "tool_handlers_cmd.py",
    "async_executor.py",
    "parallel_executor.py",
}

INPUT_FILES = {
    "cli.py",
    "intent_classifier.py",
    "intent_types.py",
    "shortcuts_handler.py",
    "validators.py",
    "onboarding.py",
}

# Brain Facade 和拆出的服务都在 Control 层
CONTROL_FILES = {
    "agent_loop.py",
    "agent_context.py",
    "agent_error_handler.py",
    "agent_utils.py",
    "strategist_brain.py",
    "strategist_models.py",
    "intent_understanding_service.py",
    "planning_service.py",
    "external_skill_resolver.py",
    "executor_brain.py",
    "reflector_brain.py",
    "reflector_models.py",
    "quality_evaluator.py",
    "next_action_decider.py",
    "consequence_predictor.py",
    "consensus_engine.py",
    "confirmer.py",
    "correction_manager.py",
    "task_engine_v3.py",
    "task_engine_v3_search.py",
    "task_engine_v3_executors.py",
    "task_engine_v3_parallel.py",
    "task_orchestrator.py",
    "task_lifecycle.py",
    "task_content_generators.py",
    "task_types.py",
    "scenario_engine_v2.py",
    "scenario_definitions.py",
    "state_manager.py",
    "session_context.py",
}

SKILL_FILES = {
    "competitor_skill.py",
    "crm_skill.py",
    "dashboard_skill.py",
    "email_skill.py",
    "finance_skill.py",
    "invoice_skill.py",
    "knowledge_skill.py",
    "pricing_skill.py",
    "report_skill.py",
    "social_skill.py",
    "task_skill.py",
    "skill_registry.py",
    "skill_builtin.py",
    "skill_editor.py",
    "skill_executors.py",
    "skill_models.py",
    "skill_reviews.py",
    "skill_marketplace.py",
    "skill_marketplace_api.py",
    "skill_marketplace_constants.py",
    "skill_marketplace_external.py",
}


def _layer_of(filename: str) -> str:
    if filename in INFRA_FILES:
        return "F"
    if filename in INPUT_FILES:
        return "I"
    if filename in CONTROL_FILES:
        return "C"
    if filename in SKILL_FILES:
        return "S"
    return "O"  # 默认归 Output（含 llm_*/business_*/search_*/export 等）


def _extract_internal_imports(file_path: Path) -> Set[str]:
    """提取一个 .py 文件中对 opc_manager 内部模块的导入（返回模块名集合）。

    使用 AST 解析，避免执行代码。仅识别 `import opc_manager.X` 和
    `from opc_manager.X import ...` 两种形式。
    """
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()

    internal: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("opc_manager."):
                    internal.add(alias.name.split(".")[1])
                elif alias.name == "opc_manager":
                    internal.add("__init__")
        elif isinstance(node, ast.ImportFrom):
            if (
                node.level == 0
                and node.module
                and node.module.startswith("opc_manager.")
            ):
                parts = node.module.split(".")
                if len(parts) >= 2:
                    internal.add(parts[1])
    return internal


def _list_py_files(layer_files: Set[str]) -> list:
    """根据文件名集合返回实际存在的 Path 列表。"""
    result = []
    for fname in layer_files:
        path = OPC_MANAGER_DIR / fname
        if path.exists():
            result.append(path)
    return result


# ===================================================================
# F (Infra) 层不应依赖 C / S / O / I
# ===================================================================
class TestInfraLayerIsolation:
    """F 层（基础设施）必须独立，不依赖业务层。"""

    @pytest.mark.parametrize(
        "file_path", _list_py_files(INFRA_FILES), ids=lambda p: p.name
    )
    def test_infra_does_not_import_control(self, file_path: Path):
        imports = _extract_internal_imports(file_path)
        forbidden = CONTROL_FILES - {file_path.name}
        leaked = imports & forbidden
        assert not leaked, (
            f"F 层 {file_path.name} 不应导入 C 层模块: {leaked}. "
            f"IOC 规则：Infra 必须独立于业务层，否则形成循环依赖。"
        )

    @pytest.mark.parametrize(
        "file_path", _list_py_files(INFRA_FILES), ids=lambda p: p.name
    )
    def test_infra_does_not_import_skills(self, file_path: Path):
        imports = _extract_internal_imports(file_path)
        leaked = imports & SKILL_FILES
        assert not leaked, f"F 层 {file_path.name} 不应导入 S 层技能模块: {leaked}."


# ===================================================================
# S (Skills) 层不应依赖 C (Control)
# ===================================================================
class TestSkillsLayerIsolation:
    """S 层（技能）不应引用引擎/Brain，避免技能反向依赖控制层。"""

    @pytest.mark.parametrize(
        "file_path", _list_py_files(SKILL_FILES), ids=lambda p: p.name
    )
    def test_skills_do_not_import_control(self, file_path: Path):
        imports = _extract_internal_imports(file_path)
        leaked = imports & CONTROL_FILES
        assert not leaked, (
            f"S 层 {file_path.name} 不应导入 C 层控制模块: {leaked}. "
            f"IOC 规则：技能不应引用引擎，否则破坏可插拔性。"
        )


# ===================================================================
# I (Input) 层不应依赖 C / O / S
# ===================================================================
class TestInputLayerIsolation:
    """I 层（输入）只依赖 F，不依赖业务层。"""

    @pytest.mark.parametrize(
        "file_path", _list_py_files(INPUT_FILES), ids=lambda p: p.name
    )
    def test_input_does_not_import_control(self, file_path: Path):
        imports = _extract_internal_imports(file_path)
        leaked = imports & CONTROL_FILES
        assert not leaked, f"I 层 {file_path.name} 不应导入 C 层控制模块: {leaked}."

    @pytest.mark.parametrize(
        "file_path", _list_py_files(INPUT_FILES), ids=lambda p: p.name
    )
    def test_input_does_not_import_skills(self, file_path: Path):
        imports = _extract_internal_imports(file_path)
        leaked = imports & SKILL_FILES
        assert not leaked, f"I 层 {file_path.name} 不应导入 S 层技能模块: {leaked}."


# ===================================================================
# P2-15 拆分回归：Brain 服务不形成循环依赖
# ===================================================================
class TestBrainServicesNoCircularImport:
    """[P2-15] Brain 拆分后的 10 个服务模块必须可独立导入，无循环依赖。"""

    BRAIN_SERVICE_MODULES = [
        "strategist_models",
        "intent_understanding_service",
        "planning_service",
        "external_skill_resolver",
        "reflector_models",
        "quality_evaluator",
        "next_action_decider",
        "consequence_predictor",
        "strategist_brain",
        "reflector_brain",
    ]

    @pytest.mark.parametrize("module_name", BRAIN_SERVICE_MODULES)
    def test_module_importable(self, module_name: str):
        """每个 Brain 服务模块都能独立 importlib.import_module 成功。"""
        try:
            mod = importlib.import_module(f"opc_manager.{module_name}")
            assert mod is not None
        except ImportError as e:
            pytest.fail(
                f"Brain 服务模块 {module_name} 导入失败（可能存在循环依赖）: {e}"
            )
