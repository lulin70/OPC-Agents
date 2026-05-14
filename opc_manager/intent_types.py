from enum import Enum
from typing import Dict, List, Tuple


class IntentType(Enum):
    UNKNOWN = "unknown"
    ANALYSIS = "analysis"
    CREATION = "creation"
    OPERATION = "operation"
    SEARCH = "search"
    NOTIFICATION = "notification"
    COMBINED = "combined"
    EMAIL = "email"
    FINANCE = "finance"
    TASK = "task"
    CRM = "crm"
    SOCIAL = "social"
    PROPOSAL = "proposal"
    INVOICE = "invoice"
    REPORT = "report"
    CALENDAR = "calendar"
    COMPETITOR = "competitor"
    PRICING = "pricing"
    TAX_REMINDER = "tax_reminder"
    DASHBOARD = "dashboard"
    KNOWLEDGE = "knowledge"
    EXTENDED_SKILL = "extended_skill"


INTENT_KEYWORDS: Dict[IntentType, List[str]] = {
    IntentType.ANALYSIS: [
        "分析", "调研", "研究", "评估", "评价", "竞品",
        "市场", "SWOT", "分析报告", "数据分析", "对比"
    ],
    IntentType.CREATION: [
        "写", "创作", "生成", "设计", "方案", "报告",
        "文档", "文案", "策划", "规划", "脚本"
    ],
    IntentType.OPERATION: [
        "操作", "执行", "运行", "启动", "停止", "上传",
        "下载", "保存", "删除", "修改", "更新", "配置"
    ],
    IntentType.SEARCH: [
        "搜索", "查找", "查询", "搜索资料", "找信息",
        "搜索信息", "查找资料"
    ],
    IntentType.NOTIFICATION: [
        "通知", "消息", "提醒", "告知"
    ],
    IntentType.EMAIL: [
        "发邮件", "写信", "跟进邮件", "感谢信", "发信",
        "邮件发送", "发一封", "回邮件"
    ],
    IntentType.FINANCE: [
        "记账", "收入", "支出", "报表", "报税", "利润",
        "赚了多少", "花了多少", "财务", "账目"
    ],
    IntentType.TASK: [
        "待办", "任务", "提醒我", "要做什么",
        "还没做", "待完成", "待办事项"
    ],
    IntentType.CRM: [
        "客户", "联系人", "合作记录", "跟进客户",
        "沉默客户", "客户档案", "客户管理"
    ],
    IntentType.SOCIAL: [
        "小红书", "公众号", "推特", "微博", "知乎",
        "发帖", "发布内容", "社交媒体", "种草"
    ],
    IntentType.PROPOSAL: [
        "报价", "报价单", "提案", "合同", "报价方案",
        "服务方案", "给客户报价"
    ],
    IntentType.INVOICE: [
        "发票", "开票", "税务", "报税", "增值税",
        "个税", "企业所得税"
    ],
    IntentType.REPORT: [
        "周报", "月报", "年报", "报告", "总结",
        "复盘", "经营报告", "工作总结"
    ],
    IntentType.CALENDAR: [
        "日程", "安排", "会议", "约会", "排期",
        "下周安排", "今天有什么"
    ],
    IntentType.COMPETITOR: [
        "竞品", "对手", "同行", "监控竞品", "竞品分析",
        "竞品动态", "竞争对手"
    ],
    IntentType.PRICING: [
        "定价", "报价策略", "怎么收费", "收费多少",
        "价格建议", "费率", "定价策略"
    ],
    IntentType.TAX_REMINDER: [
        "税务提醒", "申报提醒", "报税截止", "税期",
        "该报税了", "税务日历提醒"
    ],
    IntentType.DASHBOARD: [
        "看板", "数据概览", "经营状况", "数据总览",
        "经营数据", "整体情况"
    ],
    IntentType.KNOWLEDGE: [
        "知识库", "知识管理", "笔记", "文档管理",
        "经验总结", "知识检索", "我的文档"
    ]
}


INTENT_STEP_MAP: Dict[IntentType, Tuple[str, str]] = {
    IntentType.SEARCH: ("search", "信息搜索"),
    IntentType.ANALYSIS: ("analysis", "数据分析"),
    IntentType.CREATION: ("content_generation", "内容生成"),
    IntentType.OPERATION: ("execute_operation", "操作执行"),
    IntentType.NOTIFICATION: ("send_notification", "通知发送"),
    IntentType.EMAIL: ("email", "邮件管理"),
    IntentType.FINANCE: ("finance", "财务记账"),
    IntentType.TASK: ("task_manager", "待办管理"),
    IntentType.CRM: ("crm", "客户管理"),
    IntentType.SOCIAL: ("social_publish", "社交发布"),
    IntentType.PROPOSAL: ("proposal", "报价提案"),
    IntentType.INVOICE: ("invoice", "发票合同"),
    IntentType.REPORT: ("report", "报告生成"),
    IntentType.CALENDAR: ("calendar", "日程管理"),
    IntentType.COMPETITOR: ("competitor_watch", "竞品监控"),
    IntentType.PRICING: ("pricing", "定价优化"),
    IntentType.TAX_REMINDER: ("tax_reminder", "税务提醒"),
    IntentType.DASHBOARD: ("dashboard", "数据看板"),
    IntentType.KNOWLEDGE: ("knowledge_mgmt", "知识管理"),
    IntentType.EXTENDED_SKILL: ("ext_skill", "扩展技能"),
}


SKILL_INTENT_MAP: Dict[str, IntentType] = {
    "search": IntentType.SEARCH,
    "analysis": IntentType.ANALYSIS,
    "content_generation": IntentType.CREATION,
    "execute_operation": IntentType.OPERATION,
    "send_notification": IntentType.NOTIFICATION,
    "email": IntentType.EMAIL,
    "finance": IntentType.FINANCE,
    "task_manager": IntentType.TASK,
    "crm": IntentType.CRM,
    "social_publish": IntentType.SOCIAL,
    "proposal": IntentType.PROPOSAL,
    "invoice": IntentType.INVOICE,
    "report": IntentType.REPORT,
    "calendar": IntentType.CALENDAR,
    "competitor_watch": IntentType.COMPETITOR,
    "pricing": IntentType.PRICING,
    "tax_reminder": IntentType.TAX_REMINDER,
    "dashboard": IntentType.DASHBOARD,
    "knowledge_mgmt": IntentType.KNOWLEDGE,
    "ext_skill": IntentType.EXTENDED_SKILL,
}
