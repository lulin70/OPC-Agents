"""
Skill Data Models for OPC-Agents Skill Registry

This module contains all data classes used by the skill system,
extracted to avoid circular imports between skill_registry, skill_builtin, and skill_executors.

=== Data Classes ===
- SkillContext: Execution context for skill calls
- SkillCategory: Enum of skill type categories
- SkillInput: Input parameter specification
- SkillOutput: Output specification
- Skill: Complete skill definition with metadata
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class SkillContext:
    user_input: str
    session_id: str = ""
    step_results: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillCategory(Enum):
    """技能分类枚举"""

    ANALYSIS = "analysis"  # 分析类
    CREATION = "creation"  # 创作类
    OPERATION = "operation"  # 操作类
    SEARCH = "search"  # 搜索类
    NOTIFICATION = "notification"  # 通知类
    UTILITY = "utility"  # 工具类


@dataclass
class SkillInput:
    """技能输入规范"""

    name: str  # 参数名称
    type: str  # 参数类型
    required: bool = True  # 是否必填
    description: str = ""  # 参数描述
    default: Any = None  # 默认值


@dataclass
class SkillOutput:
    """技能输出规范"""

    name: str  # 输出名称
    type: str  # 输出类型
    description: str = ""  # 输出描述


@dataclass
class Skill:
    """技能对象"""

    skill_id: str  # 技能唯一标识
    name: str  # 技能名称
    description: str  # 技能描述
    category: SkillCategory  # 技能分类
    inputs: List[SkillInput]  # 输入参数规范
    outputs: List[SkillOutput]  # 输出规范
    execute: Callable[..., Dict[str, Any]]
    enabled: bool = True  # 是否启用
    version: str = "1.0"  # 版本号
    intent_keywords: List[str] = None  # 触发意图的关键词

    def __post_init__(self):
        if self.intent_keywords is None:
            self.intent_keywords = []
