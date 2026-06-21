"""OPC-Agents 三贤者架构模块

[S2-T8] 显式导入替代 __getattr__ 延迟导入。

经分析，子模块均通过具体子模块路径导入（如 `from opc_manager.utils import X`），
不从包顶层导入符号，因此不存在真实循环依赖，可安全使用显式导入。
Protocol 接口（BrainProtocol/SkillRegistryProtocol）已在 protocols.py 中定义，
用于解耦共识调用方与具体贤者/注册表实现。
"""

from .version import __version__, get_version, get_version_info, get_version_string

# 策略脑
from .strategist_brain import (
    StrategistBrain,
    Intent,
    IntentType,
    Constraint,
    ConstraintType,
    ExecutionPlan,
    Step,
)

# 执行脑
from .executor_brain import (
    ExecutorBrain,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStatusType,
    ExecutionResultType,
)

# 反思脑
from .reflector_brain import (
    ReflectorBrain,
    Evaluation,
    EvaluationResult,
    NextAction,
    NextActionType,
    CorrectionStrategy,
)

# 共识引擎
from .consensus_engine import (
    ConsensusEngine,
    Opinion,
    OpinionType,
    Decision,
    DecisionType,
)

# 技能注册表
from .skill_registry import (
    SkillRegistry,
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
    SkillContext,
)

# 工具调用框架
from .tool_system import (
    ToolSystem,
    Tool,
    ToolCategory,
    ToolParameter,
    PermissionLevel,
)

# 执行循环
from .agent_loop import AgentLoop
from .agent_context import AgentContext, AgentState

# 公共工具
from .utils import BoundedDict, EventEmitter, Event

# 外部技能市场
from .skill_marketplace import (
    SkillMarketplace,
    ExternalSkillMarketplace,
    ExternalSkill,
    MCPServerInfo,
    TrustLevel,
)

# 用户画像
from .user_profile import UserProfile

# 设置管理器
from .settings import (
    SettingsManager,
    SettingsCategory,
    LLMSettings,
    SMTPSettings,
    SecuritySettings,
    ProfileSettings,
    get_settings,
)

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
