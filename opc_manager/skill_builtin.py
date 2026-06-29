"""
Built-in Skill Registration for SkillRegistry

This module contains the built-in skill definitions and registration logic
extracted from SkillRegistry._register_builtin_skills().

=== Design Notes ===
- Contains all 21 built-in skill definitions with their inputs, outputs, and intent keywords
- Provides register_builtin_skills(registry) function that registers all skills
- Each skill definition follows the Skill dataclass schema from skill_registry

=== Built-in Skills (21 total) ===
Utility: intent_analysis, output_result
Search: search
Analysis: analysis, competitor_watch, pricing, dashboard
Creation: content_generation, social_publish, proposal, report
Operation: execute_operation, send_notification, email, finance,
           task_manager, crm, invoice, calendar, knowledge_mgmt
Notification: tax_reminder
"""

import logging

from opc_manager.skill_models import (
    Skill,
    SkillCategory,
    SkillInput,
    SkillOutput,
)
from opc_manager.intent_types import (
    INTENT_KEYWORDS,
    SKILL_INTENT_MAP,
    IntentType,
)

logger = logging.getLogger(__name__)


def register_builtin_skills(registry) -> None:
    """Register all 21 built-in skills into the given SkillRegistry instance.

    Args:
        registry: A SkillRegistry instance to register skills into.
                  Must have a register_skill() method.
    """
    intent_analysis_skill = Skill(
        skill_id="intent_analysis",
        name="意图分析",
        description="分析用户意图和需求",
        category=SkillCategory.UTILITY,
        inputs=[
            SkillInput(name="user_input", type="str", description="用户输入文本"),
            SkillInput(
                name="context", type="dict", required=False, description="上下文信息"
            ),
        ],
        outputs=[
            SkillOutput(name="intent", type="Intent", description="解析后的意图对象"),
            SkillOutput(name="confidence", type="float", description="置信度"),
        ],
        execute=registry._execute_intent_analysis,
        intent_keywords=["分析", "理解", "需求"],
    )
    registry.register_skill(intent_analysis_skill)

    search_skill = Skill(
        skill_id="search",
        name="搜索",
        description="搜索相关信息和数据",
        category=SkillCategory.SEARCH,
        inputs=[
            SkillInput(name="query", type="str", description="搜索查询词"),
            SkillInput(
                name="max_results",
                type="int",
                required=False,
                default=10,
                description="最大结果数",
            ),
        ],
        outputs=[
            SkillOutput(
                name="results",
                type="list",
                description="搜索结果列表（含title/url/snippet）",
            ),
            SkillOutput(name="count", type="int", description="结果数量"),
            SkillOutput(
                name="fallback_used", type="bool", description="是否使用了知识库兜底"
            ),
        ],
        execute=registry._execute_search,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("search", IntentType.UNKNOWN), []),
    )
    registry.register_skill(search_skill)

    analysis_skill = Skill(
        skill_id="analysis",
        name="分析",
        description="进行深度分析（自动搜索增强）",
        category=SkillCategory.ANALYSIS,
        inputs=[
            SkillInput(
                name="data",
                type="list",
                required=False,
                description="待分析数据（可选，自动搜索）",
            ),
            SkillInput(name="goal", type="str", description="分析目标"),
        ],
        outputs=[
            SkillOutput(name="analysis_result", type="str", description="分析结果"),
            SkillOutput(name="key_findings", type="list", description="关键发现"),
            SkillOutput(name="swot", type="dict", description="SWOT分析"),
            SkillOutput(name="action_items", type="list", description="行动清单"),
        ],
        execute=registry._execute_analysis,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("analysis", IntentType.UNKNOWN), []),
    )
    registry.register_skill(analysis_skill)

    content_gen_skill = Skill(
        skill_id="content_generation",
        name="内容生成",
        description="生成各种类型的内容",
        category=SkillCategory.CREATION,
        inputs=[
            SkillInput(name="goal", type="str", description="生成目标"),
            SkillInput(
                name="format",
                type="str",
                required=False,
                default="markdown",
                description="输出格式",
            ),
        ],
        outputs=[
            SkillOutput(name="content", type="str", description="生成的内容"),
            SkillOutput(name="format", type="str", description="输出格式"),
        ],
        execute=registry._execute_content_generation,
        intent_keywords=INTENT_KEYWORDS.get(
            SKILL_INTENT_MAP.get("content_generation", IntentType.UNKNOWN), []
        ),
    )
    registry.register_skill(content_gen_skill)

    operation_skill = Skill(
        skill_id="execute_operation",
        name="操作执行",
        description="执行各种操作",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(name="operation", type="str", description="操作名称"),
            SkillInput(
                name="parameters", type="dict", required=False, description="操作参数"
            ),
        ],
        outputs=[SkillOutput(name="result", type="dict", description="操作结果")],
        execute=registry._execute_operation,
        intent_keywords=INTENT_KEYWORDS.get(
            SKILL_INTENT_MAP.get("execute_operation", IntentType.UNKNOWN), []
        ),
    )
    registry.register_skill(operation_skill)

    notification_skill = Skill(
        skill_id="send_notification",
        name="发送通知",
        description="发送消息通知",
        category=SkillCategory.NOTIFICATION,
        inputs=[
            SkillInput(name="message", type="str", description="消息内容"),
            SkillInput(
                name="recipient", type="str", required=False, description="接收者"
            ),
        ],
        outputs=[SkillOutput(name="sent", type="bool", description="是否发送成功")],
        execute=registry._execute_notification,
        intent_keywords=INTENT_KEYWORDS.get(
            SKILL_INTENT_MAP.get("send_notification", IntentType.UNKNOWN), []
        ),
    )
    registry.register_skill(notification_skill)

    output_skill = Skill(
        skill_id="output_result",
        name="结果输出",
        description="输出最终结果",
        category=SkillCategory.UTILITY,
        inputs=[
            SkillInput(
                name="data", type="dict", required=False, description="结果数据"
            ),
            SkillInput(
                name="format",
                type="str",
                required=False,
                default="markdown",
                description="输出格式",
            ),
        ],
        outputs=[SkillOutput(name="output", type="str", description="格式化输出")],
        execute=registry._execute_output,
        intent_keywords=["输出", "生成", "报告"],
    )
    registry.register_skill(output_skill)

    email_skill = Skill(
        skill_id="email",
        name="邮件管理",
        description="发送邮件、管理模板和草稿",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(name="goal", type="str", description="邮件目标"),
            SkillInput(name="to", type="str", required=False, description="收件人"),
            SkillInput(name="subject", type="str", required=False, description="主题"),
            SkillInput(name="body", type="str", required=False, description="正文"),
        ],
        outputs=[
            SkillOutput(name="result", type="dict", description="发送结果"),
        ],
        execute=registry._execute_email,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("email", IntentType.UNKNOWN), []),
    )
    registry.register_skill(email_skill)

    finance_skill = Skill(
        skill_id="finance",
        name="财务记账",
        description="记账、报表、报税提醒",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(name="goal", type="str", description="财务操作目标"),
        ],
        outputs=[
            SkillOutput(name="result", type="dict", description="操作结果"),
        ],
        execute=registry._execute_finance,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("finance", IntentType.UNKNOWN), []),
    )
    registry.register_skill(finance_skill)

    task_skill = Skill(
        skill_id="task_manager",
        name="待办管理",
        description="创建/完成/查看待办",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(name="goal", type="str", description="待办操作目标"),
        ],
        outputs=[
            SkillOutput(name="result", type="dict", description="操作结果"),
        ],
        execute=registry._execute_task,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("task_manager", IntentType.UNKNOWN), []),
    )
    registry.register_skill(task_skill)

    crm_skill = Skill(
        skill_id="crm",
        name="客户管理",
        description="客户档案、合作记录、跟进提醒",
        category=SkillCategory.OPERATION,
        inputs=[
            SkillInput(name="goal", type="str", description="客户操作目标"),
        ],
        outputs=[
            SkillOutput(name="result", type="dict", description="操作结果"),
        ],
        execute=registry._execute_crm,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("crm", IntentType.UNKNOWN), []),
    )
    registry.register_skill(crm_skill)

    social_skill = Skill(
        skill_id="social_publish",
        name="社交发布",
        description="生成社交平台内容+发布指引",
        category=SkillCategory.CREATION,
        inputs=[SkillInput(name="goal", type="str", description="发布目标")],
        outputs=[SkillOutput(name="result", type="dict", description="生成结果")],
        execute=registry._execute_social,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("social_publish", IntentType.UNKNOWN), []),
    )
    registry.register_skill(social_skill)

    proposal_skill = Skill(
        skill_id="proposal",
        name="报价提案",
        description="生成报价单和提案",
        category=SkillCategory.CREATION,
        inputs=[SkillInput(name="goal", type="str", description="报价目标")],
        outputs=[SkillOutput(name="result", type="dict", description="报价结果")],
        execute=registry._execute_proposal,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("proposal", IntentType.UNKNOWN), []),
    )
    registry.register_skill(proposal_skill)

    invoice_skill = Skill(
        skill_id="invoice",
        name="发票税务",
        description="生成发票+税务日历",
        category=SkillCategory.OPERATION,
        inputs=[SkillInput(name="goal", type="str", description="发票/税务目标")],
        outputs=[SkillOutput(name="result", type="dict", description="操作结果")],
        execute=registry._execute_invoice,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("invoice", IntentType.UNKNOWN), []),
    )
    registry.register_skill(invoice_skill)

    report_skill = Skill(
        skill_id="report",
        name="报告生成",
        description="周报/月报/年报自动生成",
        category=SkillCategory.CREATION,
        inputs=[SkillInput(name="goal", type="str", description="报告目标")],
        outputs=[SkillOutput(name="result", type="dict", description="报告结果")],
        execute=registry._execute_report,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("report", IntentType.UNKNOWN), []),
    )
    registry.register_skill(report_skill)

    calendar_skill = Skill(
        skill_id="calendar",
        name="日程管理",
        description="日程安排+提醒",
        category=SkillCategory.OPERATION,
        inputs=[SkillInput(name="goal", type="str", description="日程目标")],
        outputs=[SkillOutput(name="result", type="dict", description="日程结果")],
        execute=registry._execute_calendar,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("calendar", IntentType.UNKNOWN), []),
    )
    registry.register_skill(calendar_skill)

    competitor_skill = Skill(
        skill_id="competitor_watch",
        name="竞品监控",
        description="竞品添加/动态记录/分析报告",
        category=SkillCategory.ANALYSIS,
        inputs=[SkillInput(name="goal", type="str", description="竞品监控目标")],
        outputs=[SkillOutput(name="result", type="dict", description="监控结果")],
        execute=registry._execute_competitor,
        intent_keywords=INTENT_KEYWORDS.get(
            SKILL_INTENT_MAP.get("competitor_watch", IntentType.UNKNOWN), []
        ),
    )
    registry.register_skill(competitor_skill)

    pricing_skill = Skill(
        skill_id="pricing",
        name="定价优化",
        description="定价计算+行业参考+建议",
        category=SkillCategory.ANALYSIS,
        inputs=[SkillInput(name="goal", type="str", description="定价目标")],
        outputs=[SkillOutput(name="result", type="dict", description="定价结果")],
        execute=registry._execute_pricing,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("pricing", IntentType.UNKNOWN), []),
    )
    registry.register_skill(pricing_skill)

    tax_reminder_skill = Skill(
        skill_id="tax_reminder",
        name="税务提醒",
        description="税务截止提醒+申报清单",
        category=SkillCategory.NOTIFICATION,
        inputs=[SkillInput(name="goal", type="str", description="税务提醒目标")],
        outputs=[SkillOutput(name="result", type="dict", description="提醒结果")],
        execute=registry._execute_tax_reminder,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("tax_reminder", IntentType.UNKNOWN), []),
    )
    registry.register_skill(tax_reminder_skill)

    dashboard_skill = Skill(
        skill_id="dashboard",
        name="数据看板",
        description="经营数据概览+趋势分析",
        category=SkillCategory.ANALYSIS,
        inputs=[SkillInput(name="goal", type="str", description="看板目标")],
        outputs=[SkillOutput(name="result", type="dict", description="看板结果")],
        execute=registry._execute_dashboard,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("dashboard", IntentType.UNKNOWN), []),
    )
    registry.register_skill(dashboard_skill)

    knowledge_skill = Skill(
        skill_id="knowledge_mgmt",
        name="知识管理",
        description="知识库CRUD+标签+检索",
        category=SkillCategory.OPERATION,
        inputs=[SkillInput(name="goal", type="str", description="知识管理目标")],
        outputs=[SkillOutput(name="result", type="dict", description="管理结果")],
        execute=registry._execute_knowledge,
        intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("knowledge_mgmt", IntentType.UNKNOWN), []),
    )
    registry.register_skill(knowledge_skill)

    # [v0.3.0] Freeze non-core skills (13→3 contraction)
    # See docs/spec/SKILL_FREEZE_LIST.md for rationale and revival conditions
    _FROZEN_DATE = "2026-06-19"
    _FULLY_FROZEN = {
        "calendar",
        "competitor_watch",
        "dashboard",
        "invoice",
        "knowledge_mgmt",
        "pricing",
        "proposal",
        "social_publish",
        "tax_reminder",
    }
    _SEMI_FROZEN = {"task_manager", "crm"}  # referenced by email/report core skills

    for skill_id in _FULLY_FROZEN:
        skill = registry.get_skill(skill_id)
        if skill:
            skill.frozen = True
            skill.frozen_date = _FROZEN_DATE
    for skill_id in _SEMI_FROZEN:
        skill = registry.get_skill(skill_id)
        if skill:
            skill.frozen = "semi"
            skill.frozen_date = _FROZEN_DATE

    logger.info(
        "[SkillBuiltin] Registered %d built-in skills (%d fully frozen, %d semi-frozen)",
        21,
        len(_FULLY_FROZEN),
        len(_SEMI_FROZEN),
    )
