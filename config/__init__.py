"""
OPC-Agents 配置模块

包含系统所有配置项
"""

from .president_office_persona import (
    PRESIDENT_OFFICE_PERSONA,
    SCENARIO_SHORTCUTS,
    get_persona,
    get_greeting,
    get_response
)
from .task_tags import (
    TASK_TAG_SYSTEM,
    TAG_RECOMMENDATION_RULES,
    TAG_PRESETS,
    get_all_tags,
    get_tag_options,
    recommend_tags,
    get_preset,
    list_presets
)

__all__ = [
    'PRESIDENT_OFFICE_PERSONA',
    'SCENARIO_SHORTCUTS',
    'TASK_TAG_SYSTEM',
    'TAG_RECOMMENDATION_RULES',
    'TAG_PRESETS',
    'get_persona',
    'get_greeting',
    'get_response',
    'get_all_tags',
    'get_tag_options',
    'recommend_tags',
    'get_preset',
    'list_presets'
]
