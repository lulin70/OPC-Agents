"""OPC-Agents 三贤者架构模块"""

from .version import __version__, get_version, get_version_info, get_version_string

# 三贤者架构模块
from .strategist_brain import (
    StrategistBrain,
    Intent,
    IntentType,
    Constraint,
    ConstraintType,
    ExecutionPlan,
    Step
)
from .executor_brain import (
    ExecutorBrain,
    ExecutionResult,
    ExecutionStatus,
    ExecutionStatusType,
    ExecutionResultType
)
from .reflector_brain import (
    ReflectorBrain,
    Evaluation,
    EvaluationResult,
    NextAction,
    NextActionType,
    CorrectionStrategy
)
from .consensus_engine import (
    ConsensusEngine,
    Opinion,
    OpinionType,
    Decision,
    DecisionType
)
from .skill_registry import (
    SkillRegistry,
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
    SkillContext
)
from .tool_system import (
    ToolSystem,
    Tool,
    ToolCategory,
    ToolParameter,
    PermissionLevel
)
from .agent_loop import (
    AgentLoop,
    AgentContext,
    AgentState
)
from .scenario_migrator import (
    ScenarioToSkillMigrator,
    migrate_scenarios_to_skills,
    get_migration_status
)
from .utils import BoundedDict, EventEmitter, Event
from .skill_marketplace import (
    SkillMarketplace,
    ExternalSkillMarketplace,
    ExternalSkill,
    MCPServerInfo,
    TrustLevel
)
from .user_profile import UserProfile

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
    
    # 场景迁移器
    "ScenarioToSkillMigrator",
    "migrate_scenarios_to_skills",
    "get_migration_status",
    
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
]
