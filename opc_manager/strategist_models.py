"""策略脑数据模型

从 strategist_brain.py 抽出的纯数据结构，无业务逻辑。
[P2-15] Step 1: 抽数据模型，保持向后兼容（strategist_brain.py re-export）。
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from opc_manager.intent_types import IntentType


class ConstraintType(Enum):
    """约束类型枚举"""

    TIME = "time"  # 时间约束
    COUNT = "count"  # 数量约束
    FORMAT = "format"  # 格式约束
    SCOPE = "scope"  # 范围约束
    BUDGET = "budget"  # 预算约束


@dataclass
class Constraint:
    """约束对象"""

    type: ConstraintType
    value: Any
    description: str = ""


@dataclass
class Intent:
    """意图对象 - 表示用户的核心目标和约束"""

    goal: str  # 核心目标
    type: IntentType  # 意图类型
    constraints: Optional[List[Constraint]] = None  # 约束条件列表
    context: Optional[Dict[str, Any]] = None  # 上下文信息
    confidence: float = 1.0  # 置信度
    sub_intents: Optional[List["Intent"]] = None  # 子意图列表（复合意图时使用）

    def __post_init__(self) -> None:
        if self.constraints is None:
            self.constraints = []
        if self.context is None:
            self.context = {}
        if self.sub_intents is None:
            self.sub_intents = []


@dataclass
class Step:
    """执行步骤对象"""

    id: str  # 步骤唯一标识
    skill_id: str  # 技能ID
    description: str  # 步骤描述
    parameters: Optional[Dict[str, Any]] = None  # 执行参数
    dependencies: Optional[List[str]] = None  # 依赖的步骤ID列表
    retry_count: int = 0  # 重试次数

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class ExecutionPlan:
    """执行计划对象"""

    plan_id: str  # 计划唯一标识
    intent: Intent  # 关联的意图
    steps: List[Step]  # 步骤列表
    resources: Optional[Dict[str, Any]] = None  # 资源配置
    estimated_time: int = 0  # 预估执行时间（秒）

    def __post_init__(self) -> None:
        if self.resources is None:
            self.resources = {}
