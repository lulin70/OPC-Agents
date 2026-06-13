"""OPC-Agents 三贤者架构模块

Lazy imports to prevent circular dependency issues.
All symbols are available via `from opc_manager import X` but only loaded on first access.
"""

from .version import __version__, get_version, get_version_info, get_version_string

__all__ = [
    # 版本信息
    "__version__",
    "get_version",
    "get_version_info",
    "get_version_string",
    # 策略脑
    "StrategistBrain",
    "Intent",
    "IntentType",
    "Constraint",
    "ConstraintType",
    "ExecutionPlan",
    "Step",
    # 执行脑
    "ExecutorBrain",
    "ExecutionResult",
    "ExecutionStatus",
    "ExecutionStatusType",
    "ExecutionResultType",
    # 反思脑
    "ReflectorBrain",
    "Evaluation",
    "EvaluationResult",
    "NextAction",
    "NextActionType",
    "CorrectionStrategy",
    # 共识引擎
    "ConsensusEngine",
    "Opinion",
    "OpinionType",
    "Decision",
    "DecisionType",
    # 技能注册表
    "SkillRegistry",
    "Skill",
    "SkillCategory",
    "SkillInput",
    "SkillOutput",
    "SkillContext",
    # 工具调用框架
    "ToolSystem",
    "Tool",
    "ToolCategory",
    "ToolParameter",
    "PermissionLevel",
    # 执行循环
    "AgentLoop",
    "AgentContext",
    "AgentState",
    # 公共工具
    "BoundedDict",
    "EventEmitter",
    "Event",
    # 外部技能市场
    "SkillMarketplace",
    "ExternalSkillMarketplace",
    "ExternalSkill",
    "MCPServerInfo",
    "TrustLevel",
    # 用户画像
    "UserProfile",
    # 设置管理器
    "SettingsManager",
    "SettingsCategory",
    "LLMSettings",
    "SMTPSettings",
    "SecuritySettings",
    "ProfileSettings",
    "get_settings",
]

# Lazy import mapping: name -> (module_path, attribute_name)
_LAZY_IMPORTS = {
    # 策略脑
    "StrategistBrain": (".strategist_brain", "StrategistBrain"),
    "Intent": (".strategist_brain", "Intent"),
    "IntentType": (".strategist_brain", "IntentType"),
    "Constraint": (".strategist_brain", "Constraint"),
    "ConstraintType": (".strategist_brain", "ConstraintType"),
    "ExecutionPlan": (".strategist_brain", "ExecutionPlan"),
    "Step": (".strategist_brain", "Step"),
    # 执行脑
    "ExecutorBrain": (".executor_brain", "ExecutorBrain"),
    "ExecutionResult": (".executor_brain", "ExecutionResult"),
    "ExecutionStatus": (".executor_brain", "ExecutionStatus"),
    "ExecutionStatusType": (".executor_brain", "ExecutionStatusType"),
    "ExecutionResultType": (".executor_brain", "ExecutionResultType"),
    # 反思脑
    "ReflectorBrain": (".reflector_brain", "ReflectorBrain"),
    "Evaluation": (".reflector_brain", "Evaluation"),
    "EvaluationResult": (".reflector_brain", "EvaluationResult"),
    "NextAction": (".reflector_brain", "NextAction"),
    "NextActionType": (".reflector_brain", "NextActionType"),
    "CorrectionStrategy": (".reflector_brain", "CorrectionStrategy"),
    # 共识引擎
    "ConsensusEngine": (".consensus_engine", "ConsensusEngine"),
    "Opinion": (".consensus_engine", "Opinion"),
    "OpinionType": (".consensus_engine", "OpinionType"),
    "Decision": (".consensus_engine", "Decision"),
    "DecisionType": (".consensus_engine", "DecisionType"),
    # 技能注册表
    "SkillRegistry": (".skill_registry", "SkillRegistry"),
    "Skill": (".skill_registry", "Skill"),
    "SkillCategory": (".skill_registry", "SkillCategory"),
    "SkillInput": (".skill_registry", "SkillInput"),
    "SkillOutput": (".skill_registry", "SkillOutput"),
    "SkillContext": (".skill_registry", "SkillContext"),
    # 工具调用框架
    "ToolSystem": (".tool_system", "ToolSystem"),
    "Tool": (".tool_system", "Tool"),
    "ToolCategory": (".tool_system", "ToolCategory"),
    "ToolParameter": (".tool_system", "ToolParameter"),
    "PermissionLevel": (".tool_system", "PermissionLevel"),
    # 执行循环
    "AgentLoop": (".agent_loop", "AgentLoop"),
    "AgentContext": (".agent_context", "AgentContext"),
    "AgentState": (".agent_context", "AgentState"),
    # 公共工具
    "BoundedDict": (".utils", "BoundedDict"),
    "EventEmitter": (".utils", "EventEmitter"),
    "Event": (".utils", "Event"),
    # 外部技能市场
    "SkillMarketplace": (".skill_marketplace", "SkillMarketplace"),
    "ExternalSkillMarketplace": (".skill_marketplace", "ExternalSkillMarketplace"),
    "ExternalSkill": (".skill_marketplace", "ExternalSkill"),
    "MCPServerInfo": (".skill_marketplace", "MCPServerInfo"),
    "TrustLevel": (".skill_marketplace", "TrustLevel"),
    # 用户画像
    "UserProfile": (".user_profile", "UserProfile"),
    # 设置管理器
    "SettingsManager": (".settings", "SettingsManager"),
    "SettingsCategory": (".settings", "SettingsCategory"),
    "LLMSettings": (".settings", "LLMSettings"),
    "SMTPSettings": (".settings", "SMTPSettings"),
    "SecuritySettings": (".settings", "SecuritySettings"),
    "ProfileSettings": (".settings", "ProfileSettings"),
    "get_settings": (".settings", "get_settings"),
}


def __getattr__(name):
    """Lazy import: only load modules when accessed, preventing circular imports."""
    if name in _LAZY_IMPORTS:
        module_path, attr_name = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path, __name__)
        attr = getattr(module, attr_name)
        # Cache in module globals for subsequent access
        globals()[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
