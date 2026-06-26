"""
Unified Type Mapping Layer for OPC-Agents Dual-Engine System.

This module provides a unified classification system that bridges the gap between:
- AgentLoop's IntentType (22 types): Fine-grained user intent detection
- TaskEngineV3's TaskType (6 types): Coarse-grained execution path selection

Design Principles:
1. Sufficient granularity for differentiated processing (Confirmer risk levels, UI display, routing)
2. Sufficient coarseness to avoid combinatorial explosion
3. Fully bidirectional compatible with both existing systems
4. Backward compatibility: All old code paths continue to work
5. Extensible: Easy to add new categories without breaking changes

Migration Strategy:
- Phase 1: Dual-track operation (current) - New code uses UnifiedTaskCategory, old interfaces still support IntentType/TaskType strings
- Phase 2: Gradual migration - Convert all internal calls to use UnifiedTaskCategory, keep old serialization compatibility
- Phase 3: Cleanup (future) - Remove old IntentType/TaskType enums, keep only UnifiedTaskCategory
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .intent_types import IntentType
from .task_types import TaskType
from .confirmer import RiskLevel


class UnifiedTaskCategory(Enum):
    """Unified task classification system (13 main categories).

    Design rationale:
    - Information acquisition (low risk): Search, query operations that don't modify state
    - Content creation (medium risk): Generate documents, messages, emails
    - Business operations (medium-high risk): Modify tasks, finance, CRM, calendar data
    - Publishing (high risk): Social media posts, email sending (external impact)
    - Analysis (low-medium risk): Data analysis, insights, comparisons
    - Automation (medium risk): Complex workflows, batch operations
    - General (low risk): Chat, greetings, simple Q&A
    """

    # === Information Acquisition (Low Risk) ===
    INFO_SEARCH = "info_search"  # Search information, knowledge retrieval
    DATA_QUERY = "data_query"  # Query data, view reports/dashboards

    # === Content Creation (Medium Risk) ===
    DOCUMENT_WRITING = "document_writing"  # Write reports/proposals/documents
    MESSAGE_COMPOSE = "message_compose"  # Write emails/messages/notifications

    # === Business Operations (Medium-High Risk) ===
    TASK_MANAGEMENT = "task_management"  # Task creation/update/completion
    FINANCE_OPERATION = "finance_operation"  # Income/expense recording
    CRM_OPERATION = "crm_operation"  # Customer/opportunity/follow-up management
    CALENDAR_OPERATION = "calendar_operation"  # Schedule/meeting arrangement

    # === Publishing (High Risk) ===
    SOCIAL_PUBLISH = "social_publish"  # Social media publishing
    EMAIL_SEND = "email_send"  # Email sending (distinguished from compose)

    # === Analysis (Low-Medium Risk) ===
    DATA_ANALYSIS = "data_analysis"  # Data analysis/comparison/insights
    WORKFLOW_AUTOMATION = "workflow_automation"  # Scenario workflows/batch operations

    # === General (Low Risk) ===
    GENERAL_CHAT = "general_chat"  # Chat/greetings/simple Q&A


# =============================================================================
# Bidirectional Mapping Tables
# =============================================================================

# IntentType → UnifiedTaskCategory mapping
# Design decisions documented for each mapping
INTENT_TO_UNIFIED_MAP: Dict[IntentType, UnifiedTaskCategory] = {
    # Information Acquisition (Low Risk)
    # Rationale: These are read-only operations that don't modify external state
    IntentType.SEARCH: UnifiedTaskCategory.INFO_SEARCH,
    IntentType.KNOWLEDGE: UnifiedTaskCategory.INFO_SEARCH,
    IntentType.DASHBOARD: UnifiedTaskCategory.DATA_QUERY,
    # Content Creation (Medium Risk)
    # Rationale: These generate content but may require review before use
    IntentType.REPORT: UnifiedTaskCategory.DOCUMENT_WRITING,
    IntentType.PROPOSAL: UnifiedTaskCategory.DOCUMENT_WRITING,
    IntentType.ANALYSIS: UnifiedTaskCategory.DOCUMENT_WRITING,  # Analysis reports are documents
    IntentType.CREATION: UnifiedTaskCategory.DOCUMENT_WRITING,  # Generic creation maps to document writing
    # Business Operations (Medium-High Risk)
    # Rationale: These modify business data and have operational impact
    IntentType.TASK: UnifiedTaskCategory.TASK_MANAGEMENT,
    IntentType.FINANCE: UnifiedTaskCategory.FINANCE_OPERATION,
    IntentType.INVOICE: UnifiedTaskCategory.FINANCE_OPERATION,  # Invoicing is financial operation
    IntentType.CRM: UnifiedTaskCategory.CRM_OPERATION,
    IntentType.CALENDAR: UnifiedTaskCategory.CALENDAR_OPERATION,
    IntentType.PRICING: UnifiedTaskCategory.CRM_OPERATION,  # Pricing affects customer relationships
    IntentType.COMPETITOR: UnifiedTaskCategory.DATA_ANALYSIS,  # Competitor monitoring is analytical
    IntentType.TAX_REMINDER: UnifiedTaskCategory.CALENDAR_OPERATION,  # Tax reminders are calendar events
    # Publishing (High Risk)
    # Rationale: These have external visibility and cannot be easily undone
    IntentType.SOCIAL: UnifiedTaskCategory.SOCIAL_PUBLISH,
    IntentType.EMAIL: UnifiedTaskCategory.EMAIL_SEND,
    # Communication (Medium Risk)
    # Rationale: Internal notifications, lower risk than external publishing
    IntentType.NOTIFICATION: UnifiedTaskCategory.MESSAGE_COMPOSE,
    # Operations (Medium-High Risk)
    # Rationale: Generic operations that could affect system state
    IntentType.OPERATION: UnifiedTaskCategory.WORKFLOW_AUTOMATION,
    # Complex Scenarios (Medium Risk)
    # Rationale: Multi-step workflows require coordination
    IntentType.COMBINED: UnifiedTaskCategory.WORKFLOW_AUTOMATION,
    IntentType.EXTENDED_SKILL: UnifiedTaskCategory.WORKFLOW_AUTOMATION,
    # Fallback (Medium Risk)
    # Rationale: Unknown intents should be treated with caution
    IntentType.UNKNOWN: UnifiedTaskCategory.GENERAL_CHAT,
}

# TaskType → UnifiedTaskCategory mapping (one-to-many, pick most common)
# Design decisions: Map to the most representative category
TASK_TO_UNIFIED_MAP: Dict[TaskType, UnifiedTaskCategory] = {
    # INFO_COLLECTION covers search and knowledge queries
    TaskType.INFO_COLLECTION: UnifiedTaskCategory.INFO_SEARCH,
    # CONTENT_GENERATION is the most versatile, used for documents, messages, social content
    TaskType.CONTENT_GENERATION: UnifiedTaskCategory.DOCUMENT_WRITING,
    # DATA_ANALYSIS for dashboards, reports, comparisons
    TaskType.DATA_ANALYSIS: UnifiedTaskCategory.DATA_ANALYSIS,
    # SCENARIO_BASED for complex multi-step workflows (tasks, CRM, calendar, finance)
    TaskType.SCENARIO_BASED: UnifiedTaskCategory.WORKFLOW_AUTOMATION,
    # BUSINESS_OPERATION for specific business actions
    TaskType.BUSINESS_OPERATION: UnifiedTaskCategory.WORKFLOW_AUTOMATION,
    # GENERAL_CHAT for casual conversation
    TaskType.GENERAL_CHAT: UnifiedTaskCategory.GENERAL_CHAT,
}

# Reverse mapping: UnifiedTaskCategory → TaskType
# Design decisions: Choose the most appropriate TaskType for execution routing
UNIFIED_TO_TASK_MAP: Dict[UnifiedTaskCategory, TaskType] = {
    UnifiedTaskCategory.INFO_SEARCH: TaskType.INFO_COLLECTION,
    UnifiedTaskCategory.DATA_QUERY: TaskType.DATA_ANALYSIS,
    UnifiedTaskCategory.DOCUMENT_WRITING: TaskType.CONTENT_GENERATION,
    UnifiedTaskCategory.MESSAGE_COMPOSE: TaskType.CONTENT_GENERATION,
    UnifiedTaskCategory.TASK_MANAGEMENT: TaskType.SCENARIO_BASED,
    UnifiedTaskCategory.FINANCE_OPERATION: TaskType.SCENARIO_BASED,
    UnifiedTaskCategory.CRM_OPERATION: TaskType.SCENARIO_BASED,
    UnifiedTaskCategory.CALENDAR_OPERATION: TaskType.SCENARIO_BASED,
    UnifiedTaskCategory.SOCIAL_PUBLISH: TaskType.CONTENT_GENERATION,
    UnifiedTaskCategory.EMAIL_SEND: TaskType.CONTENT_GENERATION,
    UnifiedTaskCategory.DATA_ANALYSIS: TaskType.DATA_ANALYSIS,
    UnifiedTaskCategory.WORKFLOW_AUTOMATION: TaskType.SCENARIO_BASED,
    UnifiedTaskCategory.GENERAL_CHAT: TaskType.GENERAL_CHAT,
}


# =============================================================================
# Core Utility Functions
# =============================================================================


def unify_intent(intent_type: str) -> UnifiedTaskCategory:
    """Convert AgentLoop's IntentType string to unified category.

    Args:
        intent_type: String value of IntentType enum (e.g., "search", "email")

    Returns:
        UnifiedTaskCategory enum value

    Raises:
        ValueError: If intent_type is not a valid IntentType string
    """
    try:
        intent_enum = IntentType(intent_type.lower())
    except ValueError:
        return UnifiedTaskCategory.GENERAL_CHAT

    return INTENT_TO_UNIFIED_MAP.get(intent_enum, UnifiedTaskCategory.GENERAL_CHAT)


def unify_intent_from_enum(intent_enum: IntentType) -> UnifiedTaskCategory:
    """Convert AgentLoop's IntentType enum directly to unified category.

    Args:
        intent_enum: IntentType enum value

    Returns:
        UnifiedTaskCategory enum value
    """
    return INTENT_TO_UNIFIED_MAP.get(intent_enum, UnifiedTaskCategory.GENERAL_CHAT)


def unify_task(task_type: TaskType, context: str = None) -> UnifiedTaskCategory:
    """Convert TaskEngineV3's TaskType to unified category with optional context enhancement.

    Args:
        task_type: TaskType enum value
        context: Optional context string for disambiguation (e.g., "sending email" vs "writing email")

    Returns:
        UnifiedTaskCategory enum value
    """
    base_category = TASK_TO_UNIFIED_MAP.get(task_type, UnifiedTaskCategory.GENERAL_CHAT)

    if context and task_type == TaskType.CONTENT_GENERATION:
        context_lower = context.lower()
        # Check email first (more specific) before general sending
        if any(word in context_lower for word in ["邮件", "email", "信"]):
            return UnifiedTaskCategory.EMAIL_SEND
        elif any(
            word in context_lower
            for word in ["发送", "send", "发布", "publish", "post"]
        ):
            return UnifiedTaskCategory.SOCIAL_PUBLISH
        elif any(
            word in context_lower for word in ["消息", "消息", "通知", "notification"]
        ):
            return UnifiedTaskCategory.MESSAGE_COMPOSE

    return base_category


def to_task_type(category: UnifiedTaskCategory) -> TaskType:
    """Convert unified category back to TaskEngineV3's TaskType.

    Args:
        category: UnifiedTaskCategory enum value

    Returns:
        TaskType enum value for execution routing
    """
    return UNIFIED_TO_TASK_MAP.get(category, TaskType.GENERAL_CHAT)


def get_risk_level(category: UnifiedTaskCategory) -> RiskLevel:
    """Return risk level based on unified category for Confirmer integration.

    Risk assessment rationale:
    - LOW (70% threshold): Read-only operations, no state modification
    - MEDIUM (85% threshold): Content generation, internal operations
    - HIGH (95% threshold): External publishing, irreversible actions

    Args:
        category: UnifiedTaskCategory enum value

    Returns:
        RiskLevel enum value
    """
    risk_map = {
        # Low Risk: Information acquisition and general chat
        UnifiedTaskCategory.INFO_SEARCH: RiskLevel.LOW,
        UnifiedTaskCategory.DATA_QUERY: RiskLevel.LOW,
        UnifiedTaskCategory.DATA_ANALYSIS: RiskLevel.LOW,
        UnifiedTaskCategory.GENERAL_CHAT: RiskLevel.LOW,
        # Medium Risk: Content creation and business operations
        UnifiedTaskCategory.DOCUMENT_WRITING: RiskLevel.MEDIUM,
        UnifiedTaskCategory.MESSAGE_COMPOSE: RiskLevel.MEDIUM,
        UnifiedTaskCategory.TASK_MANAGEMENT: RiskLevel.MEDIUM,
        UnifiedTaskCategory.FINANCE_OPERATION: RiskLevel.MEDIUM,
        UnifiedTaskCategory.CRM_OPERATION: RiskLevel.MEDIUM,
        UnifiedTaskCategory.CALENDAR_OPERATION: RiskLevel.MEDIUM,
        UnifiedTaskCategory.WORKFLOW_AUTOMATION: RiskLevel.MEDIUM,
        # High Risk: External publishing with public visibility
        UnifiedTaskCategory.SOCIAL_PUBLISH: RiskLevel.HIGH,
        UnifiedTaskCategory.EMAIL_SEND: RiskLevel.HIGH,
    }

    return risk_map.get(category, RiskLevel.MEDIUM)


# =============================================================================
# i18n Support Functions
# =============================================================================

CATEGORY_LABELS: Dict[UnifiedTaskCategory, Dict[str, str]] = {
    UnifiedTaskCategory.INFO_SEARCH: {
        "zh_CN": "信息搜索",
        "en_US": "Information Search",
        "ja_JP": "情報検索",
    },
    UnifiedTaskCategory.DATA_QUERY: {
        "zh_CN": "数据查询",
        "en_US": "Data Query",
        "ja_JP": "データ照会",
    },
    UnifiedTaskCategory.DOCUMENT_WRITING: {
        "zh_CN": "文档撰写",
        "en_US": "Document Writing",
        "ja_JP": "文書作成",
    },
    UnifiedTaskCategory.MESSAGE_COMPOSE: {
        "zh_CN": "消息编写",
        "en_US": "Message Compose",
        "ja_JP": "メッセージ作成",
    },
    UnifiedTaskCategory.TASK_MANAGEMENT: {
        "zh_CN": "任务管理",
        "en_US": "Task Management",
        "ja_JP": "タスク管理",
    },
    UnifiedTaskCategory.FINANCE_OPERATION: {
        "zh_CN": "财务操作",
        "en_US": "Finance Operation",
        "ja_JP": "財務操作",
    },
    UnifiedTaskCategory.CRM_OPERATION: {
        "zh_CN": "客户管理",
        "en_US": "CRM Operation",
        "ja_JP": "顧客管理",
    },
    UnifiedTaskCategory.CALENDAR_OPERATION: {
        "zh_CN": "日程管理",
        "en_US": "Calendar Operation",
        "ja_JP": "カレンダー操作",
    },
    UnifiedTaskCategory.SOCIAL_PUBLISH: {
        "zh_CN": "社交发布",
        "en_US": "Social Publish",
        "ja_JP": "SNS投稿",
    },
    UnifiedTaskCategory.EMAIL_SEND: {
        "zh_CN": "邮件发送",
        "en_US": "Email Send",
        "ja_JP": "メール送信",
    },
    UnifiedTaskCategory.DATA_ANALYSIS: {
        "zh_CN": "数据分析",
        "en_US": "Data Analysis",
        "ja_JP": "データ分析",
    },
    UnifiedTaskCategory.WORKFLOW_AUTOMATION: {
        "zh_CN": "工作流自动化",
        "en_US": "Workflow Automation",
        "ja_JP": "ワークフロー自動化",
    },
    UnifiedTaskCategory.GENERAL_CHAT: {
        "zh_CN": "通用对话",
        "en_US": "General Chat",
        "ja_JP": "一般チャット",
    },
}


def get_category_label(category: UnifiedTaskCategory, locale: str = "zh_CN") -> str:
    """Get human-readable label for category with i18n support.

    Args:
        category: UnifiedTaskCategory enum value
        locale: Language locale (default: "zh_CN")

    Returns:
        Localized label string
    """
    labels = CATEGORY_LABELS.get(category, {})
    return labels.get(locale, labels.get("zh_CN", category.value))


CATEGORY_ICONS: Dict[UnifiedTaskCategory, str] = {
    UnifiedTaskCategory.INFO_SEARCH: "",
    UnifiedTaskCategory.DATA_QUERY: "",
    UnifiedTaskCategory.DOCUMENT_WRITING: "",
    UnifiedTaskCategory.MESSAGE_COMPOSE: "",
    UnifiedTaskCategory.TASK_MANAGEMENT: "",
    UnifiedTaskCategory.FINANCE_OPERATION: "",
    UnifiedTaskCategory.CRM_OPERATION: "",
    UnifiedTaskCategory.CALENDAR_OPERATION: "",
    UnifiedTaskCategory.SOCIAL_PUBLISH: "",
    UnifiedTaskCategory.EMAIL_SEND: "",
    UnifiedTaskCategory.DATA_ANALYSIS: "",
    UnifiedTaskCategory.WORKFLOW_AUTOMATION: "",
    UnifiedTaskCategory.GENERAL_CHAT: "",
}


def get_category_icon(category: UnifiedTaskCategory) -> str:
    """Get emoji icon for unified category.

    Args:
        category: UnifiedTaskCategory enum value

    Returns:
        Emoji icon string
    """
    return CATEGORY_ICONS.get(category, "")


# =============================================================================
# Smart Suggestions System
# =============================================================================

FOLLOW_UP_ACTIONS: Dict[UnifiedTaskCategory, List[str]] = {
    UnifiedTaskCategory.INFO_SEARCH: [
        "深入分析搜索结果",
        "将结果保存到知识库",
        "生成搜索报告",
        "分享给团队成员",
    ],
    UnifiedTaskCategory.DATA_QUERY: [
        "导出数据报表",
        "设置数据监控提醒",
        "对比历史数据",
        "生成数据洞察报告",
    ],
    UnifiedTaskCategory.DOCUMENT_WRITING: [
        "审阅并修改文档",
        "转换为其他格式（PDF/Word）",
        "分享给相关方",
        "创建文档模板",
    ],
    UnifiedTaskCategory.MESSAGE_COMPOSE: [
        "预览消息效果",
        "添加附件或链接",
        "定时发送",
        "保存为草稿",
    ],
    UnifiedTaskCategory.TASK_MANAGEMENT: [
        "设置任务优先级",
        "分配给团队成员",
        "添加截止日期提醒",
        "创建子任务",
    ],
    UnifiedTaskCategory.FINANCE_OPERATION: [
        "生成财务报表",
        "设置预算提醒",
        "分类统计收支",
        "导出税务数据",
    ],
    UnifiedTaskCategory.CRM_OPERATION: [
        "更新客户跟进计划",
        "查看客户历史交互",
        "设置回访提醒",
        "生成销售漏斗分析",
    ],
    UnifiedTaskCategory.CALENDAR_OPERATION: [
        "邀请参会人员",
        "设置会议提醒",
        "检查日程冲突",
        "生成会议议程",
    ],
    UnifiedTaskCategory.SOCIAL_PUBLISH: [
        "预览发布效果",
        "选择最佳发布时间",
        "添加话题标签",
        "分析历史发布数据",
    ],
    UnifiedTaskCategory.EMAIL_SEND: [
        "添加抄送/密送",
        "请求阅读回执",
        "设置优先级标志",
        "保存到已发邮件",
    ],
    UnifiedTaskCategory.DATA_ANALYSIS: [
        "生成可视化图表",
        "导出分析报告",
        "设置数据监控",
        "分享分析结论",
    ],
    UnifiedTaskCategory.WORKFLOW_AUTOMATION: [
        "查看执行日志",
        "暂停或恢复工作流",
        "修改工作流配置",
        "批量处理类似任务",
    ],
    UnifiedTaskCategory.GENERAL_CHAT: [
        "开始具体任务",
        "查看帮助文档",
        "了解系统功能",
        "提供反馈意见",
    ],
}


def suggest_follow_up_actions(category: UnifiedTaskCategory) -> List[str]:
    """Suggest follow-up actions based on unified category for smart suggestion system.

    Args:
        category: UnifiedTaskCategory enum value

    Returns:
        List of suggested action strings
    """
    return FOLLOW_UP_ACTIONS.get(category, [])


# =============================================================================
# Backward Compatibility Utilities
# =============================================================================


def legacy_intent_to_risk(intent_type: str) -> RiskLevel:
    """Backward-compatible function: Convert legacy intent type string to risk level.

    This function maintains compatibility with old code that uses string-based intent types.
    New code should use unify_intent() + get_risk_level() instead.

    Args:
        intent_type: Legacy intent type string (e.g., "SEARCH", "EMAIL")

    Returns:
        RiskLevel enum value
    """
    category = unify_intent(intent_type)
    return get_risk_level(category)


@dataclass
class UnifiedClassificationResult:
    """Container for unified classification result with metadata.

    Attributes:
        category: The unified task category
        original_intent: Original IntentType (if provided)
        original_task: Original TaskType (if provided)
        risk_level: Calculated risk level
        label: Human-readable label (default locale)
        icon: Emoji icon
        suggestions: Follow-up action suggestions
    """

    category: UnifiedTaskCategory
    original_intent: Optional[str] = None
    original_task: Optional[str] = None
    risk_level: Optional[RiskLevel] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    suggestions: Optional[List[str]] = None

    def __post_init__(self):
        if self.risk_level is None:
            self.risk_level = get_risk_level(self.category)
        if self.label is None:
            self.label = get_category_label(self.category)
        if self.icon is None:
            self.icon = get_category_icon(self.category)
        if self.suggestions is None:
            self.suggestions = suggest_follow_up_actions(self.category)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "original_intent": self.original_intent,
            "original_task": self.original_task,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "label": self.label,
            "icon": self.icon,
            "suggestions": self.suggestions,
        }


def classify_unified(
    intent_type: str = None, task_type: TaskType = None, context: str = None
) -> UnifiedClassificationResult:
    """Main entry point: Classify operation into unified category with full metadata.

    This is the recommended way to use the unified type system. It provides
    a complete classification result with all metadata for UI display,
    risk assessment, and smart suggestions.

    Args:
        intent_type: Optional IntentType string from AgentLoop
        task_type: Optional TaskType from TaskEngineV3
        context: Optional context string for disambiguation

    Returns:
        UnifiedClassificationResult with all metadata
    """
    category = UnifiedTaskCategory.GENERAL_CHAT

    if intent_type:
        category = unify_intent(intent_type)
    elif task_type:
        category = unify_task(task_type, context)

    return UnifiedClassificationResult(
        category=category,
        original_intent=intent_type,
        original_task=task_type.value if task_type else None,
    )
