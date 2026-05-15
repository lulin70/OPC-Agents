"""
技能注册表 (SkillRegistry) - 负责技能的注册、发现和调用

这是三贤者架构的技能管理中心：
- 注册技能
- 发现技能
- 调用技能
- 依赖注入LLMService/SearchResultProcessor/ToolSystem
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import logging
import re
import threading

from opc_manager.intent_types import IntentType, INTENT_KEYWORDS, INTENT_STEP_MAP, SKILL_INTENT_MAP
from opc_manager.protocols import LLMServiceProtocol

logger = logging.getLogger(__name__)

SKILL_COLLABORATIONS = {
    "crm_to_email": {"trigger": ["跟进", "发邮件"], "skills": ["crm", "email"]},
    "finance_to_tax": {"trigger": ["记账", "报税"], "skills": ["finance", "tax_reminder"]},
    "deal_to_income": {"trigger": ["成交", "收款"], "skills": ["crm", "finance"]},
    "report_full": {"trigger": ["经营报告", "全面报告"], "skills": ["finance", "crm", "task_manager", "report"]},
    "deal_to_email": {"trigger": ["成交后发邮件", "成交通知"], "skills": ["crm", "email"]},
    "report_to_calendar": {"trigger": ["报告截止", "报告日程"], "skills": ["report", "calendar"]},
    "proposal_to_email": {"trigger": ["报价后发邮件", "报价通知"], "skills": ["proposal", "email"]},
}


@dataclass
class SkillContext:
    user_input: str
    session_id: str = ""
    step_results: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillCategory(Enum):
    """技能分类枚举"""
    ANALYSIS = "analysis"           # 分析类
    CREATION = "creation"           # 创作类
    OPERATION = "operation"         # 操作类
    SEARCH = "search"               # 搜索类
    NOTIFICATION = "notification"   # 通知类
    UTILITY = "utility"             # 工具类


@dataclass
class SkillInput:
    """技能输入规范"""
    name: str                       # 参数名称
    type: str                       # 参数类型
    required: bool = True           # 是否必填
    description: str = ""           # 参数描述
    default: Any = None             # 默认值


@dataclass
class SkillOutput:
    """技能输出规范"""
    name: str                       # 输出名称
    type: str                       # 输出类型
    description: str = ""           # 输出描述


@dataclass
class Skill:
    """技能对象"""
    skill_id: str                   # 技能唯一标识
    name: str                       # 技能名称
    description: str                # 技能描述
    category: SkillCategory         # 技能分类
    inputs: List[SkillInput]        # 输入参数规范
    outputs: List[SkillOutput]      # 输出规范
    execute: Callable[..., Dict[str, Any]]
    enabled: bool = True            # 是否启用
    version: str = "1.0"            # 版本号
    intent_keywords: List[str] = None  # 触发意图的关键词

    def __post_init__(self):
        if self.intent_keywords is None:
            self.intent_keywords = []


class SkillRegistry:
    """技能注册表 — 负责技能的注册、发现和调用"""

    _instance = None
    _instance_lock = threading.Lock()
    _init_lock = threading.Lock()

    def __new__(cls, llm_service=None, search_processor=None, tool_system=None, register_builtins: bool = True, register_external: bool = True):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        llm_service=None,
        search_processor=None,
        tool_system=None,
        register_builtins: bool = True,
        register_external: bool = True,
    ):
        with self._init_lock:
            if hasattr(self, '_initialized') and self._initialized:
                if llm_service is not None:
                    self.llm_service = llm_service
                if search_processor is not None:
                    self.search_processor = search_processor
                if tool_system is not None:
                    self.tool_system = tool_system
                return
            self._initialized = True
            self.llm_service: Optional[LLMServiceProtocol] = llm_service
            self.search_processor = search_processor
            self.tool_system = tool_system
            self.skills: Dict[str, Skill] = {}
            self.category_index: Dict[str, List[str]] = {}
            self.keyword_index: Dict[str, List[str]] = {}
            self._collab_in_progress = False
            self._external_marketplace = None

            if register_builtins:
                self._register_builtin_skills()

            if register_external:
                self._register_external_skills()

            self._web_search = None
            self._content_generator = None

    def _register_builtin_skills(self):
        intent_analysis_skill = Skill(
            skill_id="intent_analysis",
            name="意图分析",
            description="分析用户意图和需求",
            category=SkillCategory.UTILITY,
            inputs=[
                SkillInput(name="user_input", type="str", description="用户输入文本"),
                SkillInput(name="context", type="dict", required=False, description="上下文信息")
            ],
            outputs=[
                SkillOutput(name="intent", type="Intent", description="解析后的意图对象"),
                SkillOutput(name="confidence", type="float", description="置信度")
            ],
            execute=self._execute_intent_analysis,
            intent_keywords=["分析", "理解", "需求"]
        )
        self.register_skill(intent_analysis_skill)

        search_skill = Skill(
            skill_id="search",
            name="搜索",
            description="搜索相关信息和数据",
            category=SkillCategory.SEARCH,
            inputs=[
                SkillInput(name="query", type="str", description="搜索查询词"),
                SkillInput(name="max_results", type="int", required=False, default=10, description="最大结果数")
            ],
            outputs=[
                SkillOutput(name="results", type="list", description="搜索结果列表（含title/url/snippet）"),
                SkillOutput(name="count", type="int", description="结果数量"),
                SkillOutput(name="fallback_used", type="bool", description="是否使用了知识库兜底")
            ],
            execute=self._execute_search,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("search"), [])
        )
        self.register_skill(search_skill)

        analysis_skill = Skill(
            skill_id="analysis",
            name="分析",
            description="进行深度分析（自动搜索增强）",
            category=SkillCategory.ANALYSIS,
            inputs=[
                SkillInput(name="data", type="list", required=False, description="待分析数据（可选，自动搜索）"),
                SkillInput(name="goal", type="str", description="分析目标")
            ],
            outputs=[
                SkillOutput(name="analysis_result", type="str", description="分析结果"),
                SkillOutput(name="key_findings", type="list", description="关键发现"),
                SkillOutput(name="swot", type="dict", description="SWOT分析"),
                SkillOutput(name="action_items", type="list", description="行动清单")
            ],
            execute=self._execute_analysis,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("analysis"), [])
        )
        self.register_skill(analysis_skill)

        content_gen_skill = Skill(
            skill_id="content_generation",
            name="内容生成",
            description="生成各种类型的内容",
            category=SkillCategory.CREATION,
            inputs=[
                SkillInput(name="goal", type="str", description="生成目标"),
                SkillInput(name="format", type="str", required=False, default="markdown", description="输出格式")
            ],
            outputs=[
                SkillOutput(name="content", type="str", description="生成的内容"),
                SkillOutput(name="format", type="str", description="输出格式")
            ],
            execute=self._execute_content_generation,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("content_generation"), [])
        )
        self.register_skill(content_gen_skill)

        operation_skill = Skill(
            skill_id="execute_operation",
            name="操作执行",
            description="执行各种操作",
            category=SkillCategory.OPERATION,
            inputs=[
                SkillInput(name="operation", type="str", description="操作名称"),
                SkillInput(name="parameters", type="dict", required=False, description="操作参数")
            ],
            outputs=[
                SkillOutput(name="result", type="dict", description="操作结果")
            ],
            execute=self._execute_operation,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("execute_operation"), [])
        )
        self.register_skill(operation_skill)

        notification_skill = Skill(
            skill_id="send_notification",
            name="发送通知",
            description="发送消息通知",
            category=SkillCategory.NOTIFICATION,
            inputs=[
                SkillInput(name="message", type="str", description="消息内容"),
                SkillInput(name="recipient", type="str", required=False, description="接收者")
            ],
            outputs=[
                SkillOutput(name="sent", type="bool", description="是否发送成功")
            ],
            execute=self._execute_notification,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("send_notification"), [])
        )
        self.register_skill(notification_skill)

        output_skill = Skill(
            skill_id="output_result",
            name="结果输出",
            description="输出最终结果",
            category=SkillCategory.UTILITY,
            inputs=[
                SkillInput(name="data", type="dict", required=False, description="结果数据"),
                SkillInput(name="format", type="str", required=False, default="markdown", description="输出格式")
            ],
            outputs=[
                SkillOutput(name="output", type="str", description="格式化输出")
            ],
            execute=self._execute_output,
            intent_keywords=["输出", "生成", "报告"]
        )
        self.register_skill(output_skill)

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
            execute=self._execute_email,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("email"), [])
        )
        self.register_skill(email_skill)

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
            execute=self._execute_finance,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("finance"), [])
        )
        self.register_skill(finance_skill)

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
            execute=self._execute_task,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("task_manager"), [])
        )
        self.register_skill(task_skill)

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
            execute=self._execute_crm,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("crm"), [])
        )
        self.register_skill(crm_skill)

        social_skill = Skill(
            skill_id="social_publish",
            name="社交发布",
            description="生成社交平台内容+发布指引",
            category=SkillCategory.CREATION,
            inputs=[SkillInput(name="goal", type="str", description="发布目标")],
            outputs=[SkillOutput(name="result", type="dict", description="生成结果")],
            execute=self._execute_social,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("social_publish"), [])
        )
        self.register_skill(social_skill)

        proposal_skill = Skill(
            skill_id="proposal",
            name="报价提案",
            description="生成报价单和提案",
            category=SkillCategory.CREATION,
            inputs=[SkillInput(name="goal", type="str", description="报价目标")],
            outputs=[SkillOutput(name="result", type="dict", description="报价结果")],
            execute=self._execute_proposal,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("proposal"), [])
        )
        self.register_skill(proposal_skill)

        invoice_skill = Skill(
            skill_id="invoice",
            name="发票税务",
            description="生成发票+税务日历",
            category=SkillCategory.OPERATION,
            inputs=[SkillInput(name="goal", type="str", description="发票/税务目标")],
            outputs=[SkillOutput(name="result", type="dict", description="操作结果")],
            execute=self._execute_invoice,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("invoice"), [])
        )
        self.register_skill(invoice_skill)

        report_skill = Skill(
            skill_id="report",
            name="报告生成",
            description="周报/月报/年报自动生成",
            category=SkillCategory.CREATION,
            inputs=[SkillInput(name="goal", type="str", description="报告目标")],
            outputs=[SkillOutput(name="result", type="dict", description="报告结果")],
            execute=self._execute_report,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("report"), [])
        )
        self.register_skill(report_skill)

        calendar_skill = Skill(
            skill_id="calendar",
            name="日程管理",
            description="日程安排+提醒",
            category=SkillCategory.OPERATION,
            inputs=[SkillInput(name="goal", type="str", description="日程目标")],
            outputs=[SkillOutput(name="result", type="dict", description="日程结果")],
            execute=self._execute_calendar,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("calendar"), [])
        )
        self.register_skill(calendar_skill)

        competitor_skill = Skill(
            skill_id="competitor_watch",
            name="竞品监控",
            description="竞品添加/动态记录/分析报告",
            category=SkillCategory.ANALYSIS,
            inputs=[SkillInput(name="goal", type="str", description="竞品监控目标")],
            outputs=[SkillOutput(name="result", type="dict", description="监控结果")],
            execute=self._execute_competitor,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("competitor_watch"), [])
        )
        self.register_skill(competitor_skill)

        pricing_skill = Skill(
            skill_id="pricing",
            name="定价优化",
            description="定价计算+行业参考+建议",
            category=SkillCategory.ANALYSIS,
            inputs=[SkillInput(name="goal", type="str", description="定价目标")],
            outputs=[SkillOutput(name="result", type="dict", description="定价结果")],
            execute=self._execute_pricing,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("pricing"), [])
        )
        self.register_skill(pricing_skill)

        tax_reminder_skill = Skill(
            skill_id="tax_reminder",
            name="税务提醒",
            description="税务截止提醒+申报清单",
            category=SkillCategory.NOTIFICATION,
            inputs=[SkillInput(name="goal", type="str", description="税务提醒目标")],
            outputs=[SkillOutput(name="result", type="dict", description="提醒结果")],
            execute=self._execute_tax_reminder,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("tax_reminder"), [])
        )
        self.register_skill(tax_reminder_skill)

        dashboard_skill = Skill(
            skill_id="dashboard",
            name="数据看板",
            description="经营数据概览+趋势分析",
            category=SkillCategory.ANALYSIS,
            inputs=[SkillInput(name="goal", type="str", description="看板目标")],
            outputs=[SkillOutput(name="result", type="dict", description="看板结果")],
            execute=self._execute_dashboard,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("dashboard"), [])
        )
        self.register_skill(dashboard_skill)

        knowledge_skill = Skill(
            skill_id="knowledge_mgmt",
            name="知识管理",
            description="知识库CRUD+标签+检索",
            category=SkillCategory.OPERATION,
            inputs=[SkillInput(name="goal", type="str", description="知识管理目标")],
            outputs=[SkillOutput(name="result", type="dict", description="管理结果")],
            execute=self._execute_knowledge,
            intent_keywords=INTENT_KEYWORDS.get(SKILL_INTENT_MAP.get("knowledge_mgmt"), [])
        )
        self.register_skill(knowledge_skill)

    def _register_external_skills(self):
        try:
            from opc_manager.data_manager import init_db, execute_query
            init_db()
            rows = execute_query("SELECT * FROM external_skills")
            for row in rows:
                skill_id = row["id"]
                if skill_id in self.skills:
                    continue
                config = {}
                if row.get("skill_config"):
                    try:
                        config = json.loads(row["skill_config"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                ext_skill = Skill(
                    skill_id=f"ext_{skill_id}",
                    name=row.get("name", skill_id),
                    description=row.get("description", ""),
                    category=SkillCategory.UTILITY,
                    inputs=[SkillInput(name="goal", type="str", description="执行目标")],
                    outputs=[SkillOutput(name="result", type="dict", description="执行结果")],
                    execute=self._execute_extended_skill,
                    enabled=True,
                    version=row.get("version", "1.0.0"),
                    intent_keywords=config.get("keywords", []),
                )
                self.register_skill(ext_skill)
        except Exception as e:
            logger.debug("注册外部技能失败: %s", e)

    def _execute_extended_skill(self, goal: str = "", _context: Optional[SkillContext] = None, **kwargs) -> Dict[str, Any]:
        try:
            from opc_manager.skill_marketplace import ExternalSkillMarketplace
            if self._external_marketplace is None:
                self._external_marketplace = ExternalSkillMarketplace()
            skill_id = kwargs.get("skill_id", "")
            if skill_id:
                clean_skill_id = skill_id.replace("ext_", "") if skill_id.startswith("ext_") else skill_id
                return self._external_marketplace.execute_in_sandbox(
                    clean_skill_id, {"goal": goal, **kwargs}
                )
        except Exception as e:
            logger.warning("Extended skill sandbox execution failed: %s", e)
        return {
            "success": False,
            "error": "外部技能执行失败",
            "data": {"goal": goal, "extended": True},
        }

    def install_external_skill(self, skill_id: str, source: str = "opc_official") -> Dict[str, Any]:
        if self._external_marketplace is None:
            from opc_manager.skill_marketplace import ExternalSkillMarketplace
            self._external_marketplace = ExternalSkillMarketplace()

        result = self._external_marketplace.install_skill(skill_id, source)
        if result.get("success"):
            self._register_external_skills()
        return result

    def uninstall_external_skill(self, skill_id: str) -> Dict[str, Any]:
        if self._external_marketplace is None:
            from opc_manager.skill_marketplace import ExternalSkillMarketplace
            self._external_marketplace = ExternalSkillMarketplace()

        ext_skill_id = f"ext_{skill_id}"
        result = self._external_marketplace.uninstall_skill(skill_id)
        if result.get("success"):
            if ext_skill_id in self.skills:
                del self.skills[ext_skill_id]
        return result

    def register_skill(self, skill: Skill) -> bool:
        """
        注册技能
        
        Args:
            skill: 技能对象
        
        Returns:
            bool: 是否注册成功
        """
        if skill.skill_id in self.skills:
            existing = self.skills[skill.skill_id]
            try:
                from packaging.version import Version
                if Version(skill.version) > Version(existing.version):
                    logger.info("技能版本升级: %s %s→%s", skill.skill_id, existing.version, skill.version)
                    self.skills[skill.skill_id] = skill
                    return True
            except Exception:
                pass
            logger.warning("技能已存在: %s", skill.skill_id)
            return False
        
        self.skills[skill.skill_id] = skill
        
        # 更新分类索引
        category_name = skill.category.value
        if category_name not in self.category_index:
            self.category_index[category_name] = []
        self.category_index[category_name].append(skill.skill_id)
        
        # 更新关键词索引
        for keyword in skill.intent_keywords:
            if keyword not in self.keyword_index:
                self.keyword_index[keyword] = []
            self.keyword_index[keyword].append(skill.skill_id)
        
        logger.info("技能注册成功: %s", skill.skill_id)
        return True

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        获取技能
        
        Args:
            skill_id: 技能ID
        
        Returns:
            Optional[Skill]: 技能对象，如果存在的话
        """
        return self.skills.get(skill_id)

    def find_by_intent(self, intent_text: str) -> List[Skill]:
        """
        根据意图查找技能
        
        Args:
            intent_text: 意图文本
        
        Returns:
            List[Skill]: 匹配的技能列表
        """
        matched_skill_ids = set()
        
        # 查找匹配的关键词
        for keyword, skill_ids in self.keyword_index.items():
            if keyword in intent_text:
                matched_skill_ids.update(skill_ids)
        
        # 返回技能对象列表
        return [self.skills[sid] for sid in matched_skill_ids if sid in self.skills]

    def find_by_category(self, category: SkillCategory) -> List[Skill]:
        """
        根据分类查找技能
        
        Args:
            category: 技能分类
        
        Returns:
            List[Skill]: 该分类下的技能列表
        """
        category_name = category.value
        skill_ids = self.category_index.get(category_name, [])
        return [self.skills[sid] for sid in skill_ids if sid in self.skills]

    def list_all_skills(self) -> List[Skill]:
        """
        获取所有技能列表
        
        Returns:
            List[Skill]: 所有技能列表
        """
        return list(self.skills.values())

    async def execute_skill(self, skill_id: str, context: Optional[SkillContext] = None, **kwargs) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        if not skill.enabled:
            return {"success": False, "error": f"技能已禁用: {skill_id}"}

        try:
            missing_params = []
            for input_spec in skill.inputs:
                if input_spec.required and input_spec.name not in kwargs:
                    missing_params.append(input_spec.name)

            if missing_params:
                return {"success": False, "error": f"缺少必填参数: {', '.join(missing_params)}"}

            if asyncio.iscoroutinefunction(skill.execute):
                result = await skill.execute(**kwargs, _context=context)
            else:
                result = skill.execute(**kwargs, _context=context)

            from opc_manager.export.models import SKILL_EXPORT_CAPABILITIES, ExportFormat
            supported = SKILL_EXPORT_CAPABILITIES.get(skill_id, [ExportFormat.MARKDOWN])
            result["_exportable_formats"] = [f.value for f in supported]

            return {"success": True, "data": result}

        except Exception as e:
            logger.error("技能执行异常: %s, 错误: %s", skill_id, str(e))
            return {"success": False, "error": str(e)}

    def export_result(self, skill_id: str, result_data: Dict[str, Any], fmt: str, **opts) -> bytes:
        from opc_manager.export import ExportManager
        from opc_manager.export.models import ResultData, ExportFormat

        manager = ExportManager()
        format_enum = ExportFormat(fmt)
        content = result_data.get("content", result_data.get("output", ""))
        data = ResultData(
            content=content,
            metadata=result_data.get("metadata", {"title": result_data.get("title", "Export")}),
        )
        return manager.export_sync(data, format_enum, **opts)

    def to_dict(self) -> Dict[str, Any]:
        """
        将技能注册表转换为字典
        
        Returns:
            Dict[str, Any]: 状态字典
        """
        return {
            "type": "skill_registry",
            "skill_count": len(self.skills),
            "categories": self.category_index,
            "skills": {
                sid: {
                    "name": s.name,
                    "category": s.category.value,
                    "description": s.description
                }
                for sid, s in self.skills.items()
            }
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        pass

    def _execute_collaborative(self, goal: str, _context: Optional[SkillContext] = None) -> Optional[Dict[str, Any]]:
        if self._collab_in_progress:
            return None
        collab = None
        collab_name = None
        for collab_id, cfg in SKILL_COLLABORATIONS.items():
            if any(t in goal for t in cfg["trigger"]):
                collab = cfg
                collab_name = collab_id
                break
        if not collab:
            return None
        self._collab_in_progress = True
        try:
            results = []
            context_data = {}
            for skill_id in collab["skills"]:
                skill = self.get_skill(skill_id)
                if not skill or not skill.execute:
                    continue

                enriched_goal = goal
                if skill_id == "email" and "crm" in context_data:
                    crm_data = context_data["crm"]
                    if isinstance(crm_data, dict) and crm_data.get("customer"):
                        cust = crm_data["customer"]
                        enriched_goal = f"{goal} 收件人:{cust.get('name','')} 邮箱:{cust.get('email','')}"
                elif skill_id == "finance" and "crm" in context_data:
                    crm_data = context_data["crm"]
                    if isinstance(crm_data, dict) and crm_data.get("deal"):
                        deal = crm_data["deal"]
                        enriched_goal = f"{goal} 金额:{deal.get('amount',0)} 来源:{deal.get('description','')}"

                try:
                    result = skill.execute(goal=enriched_goal, _context=_context)
                    results.append({"skill_id": skill_id, "result": result})
                    context_data[skill_id] = result
                except Exception as e:
                    results.append({"skill_id": skill_id, "result": {"success": False, "error": str(e)}})

            if results:
                return {
                    "success": any(isinstance(r["result"], dict) and r["result"].get("success") for r in results),
                    "collaboration": collab_name,
                    "results": results,
                    "message": f"协作执行完成: {' → '.join(collab['skills'])}",
                }
        finally:
            self._collab_in_progress = False
        return None

    # 内置技能执行函数
    def _execute_intent_analysis(self, user_input: str, context: dict = None, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        """执行意图分析"""
        return {
            "intent": {"goal": user_input, "type": "analysis"},
            "confidence": 0.85
        }

    async def _execute_search(self, query: str, max_results: int = 10, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        cleaned_query = re.sub(r'[<>&"\']', '', query).strip()
        if not cleaned_query:
            return {"results": [], "count": 0, "fallback_used": False}

        if self.search_processor is not None:
            try:
                raw_results = await self._do_web_search(cleaned_query, max_results)
                processed = self.search_processor.process(cleaned_query, raw_results)
                return {
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", r.get("url", "")),
                            "snippet": r.get("body", r.get("snippet", "")),
                        }
                        for r in processed.results
                    ],
                    "count": len(processed.results),
                    "fallback_used": processed.fallback_used,
                }
            except Exception as e:
                logger.warning("搜索增强失败，使用降级: %s", e)

        raw_results = await self._do_web_search(cleaned_query, max_results)
        return {
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("url", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                }
                for r in raw_results
            ],
            "count": len(raw_results),
            "fallback_used": False,
        }

    async def _do_web_search(self, query: str, max_results: int) -> list:
        try:
            if self._web_search is None:
                try:
                    from opc_hr.web_search import WebSearchMCP
                    self._web_search = WebSearchMCP()
                except ImportError:
                    self._web_search = False
            if self._web_search is False:
                return []
            if self._web_search.is_available():
                loop = asyncio.get_running_loop()
                results = await loop.run_in_executor(
                    None, self._web_search.search, query, max_results
                )
                return results
        except Exception as e:
            logger.warning("Web搜索失败: %s", e)
        return []

    async def _execute_analysis(self, data: list = None, goal: str = "", _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        if self.llm_service is not None:
            try:
                search_results = data or []
                if not search_results and goal:
                    search_result = await self.execute_skill(
                        "search", context=_context, query=goal, max_results=5
                    )
                    if search_result.get("success") and search_result.get("data"):
                        search_results = search_result["data"].get("results", [])

                template = self._get_analysis_template(goal)
                gen_result = await self._call_llm_generate(
                    user_input=goal,
                    template=template,
                    search_results=search_results,
                )
                if gen_result and gen_result.success:
                    return self._parse_analysis_result(gen_result.content, goal)
            except Exception as e:
                logger.warning("LLM分析失败，使用规则引擎降级: %s", e)

        return self._rule_based_analysis(goal, data or [])

    async def _execute_content_generation(self, goal: str, format: str = "markdown", _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        if self.llm_service is not None:
            try:
                search_results = []
                search_result = await self.execute_skill(
                    "search", context=_context, query=goal, max_results=5
                )
                if search_result.get("success") and search_result.get("data"):
                    search_results = search_result["data"].get("results", [])

                template = self._get_content_template(goal)
                gen_result = await self._call_llm_generate(
                    user_input=goal,
                    template=template,
                    search_results=search_results,
                )
                if gen_result and gen_result.success:
                    return {
                        "content": gen_result.content,
                        "format": format,
                        "fallback_used": gen_result.fallback_used,
                        "quality_score": gen_result.quality_score,
                    }
            except Exception as e:
                logger.warning("LLM内容生成失败，使用规则引擎降级: %s", e)

        return self._rule_based_content_generation(goal, format)

    async def _call_llm_generate(self, user_input: str, template: str, search_results: list = None):
        try:
            from opc_manager.llm_content import LLMEnhancedContentGenerator
            if self._content_generator is None:
                self._content_generator = LLMEnhancedContentGenerator()
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._content_generator.generate,
                user_input,
                template,
                search_results or [],
            )
            return result
        except ImportError:
            logger.warning("LLMEnhancedContentGenerator不可用")
            return None
        except Exception as e:
            logger.warning("LLM生成调用失败: %s", e)
            return None

    def _get_analysis_template(self, goal: str) -> str:
        return (
            "# {topic} 分析报告\n\n"
            "## 摘要\n\n请提供简要分析摘要。\n\n"
            "## 关键发现\n\n请列出3-5个关键发现。\n\n"
            "## SWOT分析\n\n"
            "### 优势 (Strengths)\n请列出主要优势。\n\n"
            "### 劣势 (Weaknesses)\n请列出主要劣势。\n\n"
            "### 机会 (Opportunities)\n请列出主要机会。\n\n"
            "### 威胁 (Threats)\n请列出主要威胁。\n\n"
            "## 行动清单\n\n请列出优先级排序的具体行动建议。\n"
        )

    def _get_content_template(self, goal: str) -> str:
        goal_lower = goal.lower()
        if any(kw in goal_lower for kw in ["方案", "计划", "策略"]):
            return (
                "# {topic}\n\n"
                "## 目标\n\n请明确目标。\n\n"
                "## 路线图\n\n请提供实施路线图。\n\n"
                "## 资源需求\n\n请列出所需资源。\n\n"
                "## 风险与应对\n\n请列出主要风险及应对措施。\n\n"
                "## 验收标准\n\n请定义验收标准。\n"
            )
        elif any(kw in goal_lower for kw in ["报告", "总结", "回顾"]):
            return (
                "# {topic}\n\n"
                "## 摘要\n\n请提供摘要。\n\n"
                "## 正文\n\n请提供详细内容。\n\n"
                "## 结论\n\n请提供结论。\n\n"
                "## 建议\n\n请提供建议。\n"
            )
        return "# {topic}\n\n请根据用户需求生成详细内容。\n"

    def _parse_analysis_result(self, content: str, goal: str) -> Dict[str, Any]:
        try:
            json_str = content
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]
            parsed = json.loads(json_str.strip())
            if isinstance(parsed, dict):
                return {
                    "analysis_result": content,
                    "summary": parsed.get("summary", ""),
                    "key_findings": parsed.get("key_findings", []),
                    "swot": parsed.get("swot", {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}),
                    "action_items": parsed.get("action_items", []),
                }
        except (json.JSONDecodeError, IndexError, AttributeError):
            pass

        result = {
            "analysis_result": content,
            "summary": "",
            "key_findings": [],
            "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
            "action_items": [],
        }
        sections = content.split("##")
        for section in sections:
            section_lower = section.lower()
            if "摘要" in section_lower:
                result["summary"] = section.strip().split("\n", 1)[-1].strip()
            elif "关键发现" in section_lower:
                lines = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip().startswith(("-", "•", "*")) or any(l.strip().startswith(f"{i}.") for i in range(1, 10))]
                result["key_findings"] = lines
            elif "优势" in section_lower or "strengths" in section_lower:
                result["swot"]["strengths"] = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
            elif "劣势" in section_lower or "weaknesses" in section_lower:
                result["swot"]["weaknesses"] = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
            elif "机会" in section_lower or "opportunities" in section_lower:
                result["swot"]["opportunities"] = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
            elif "威胁" in section_lower or "threats" in section_lower:
                result["swot"]["threats"] = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
            elif "行动" in section_lower:
                result["action_items"] = [l.strip().lstrip("-•*0-9. ") for l in section.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
        return result

    def _rule_based_analysis(self, goal: str, data: list) -> Dict[str, Any]:
        data_summary = ""
        if data:
            items = data[:5]
            data_summary = "\n".join(f"- {item}" for item in items)

        return {
            "analysis_result": f"# {goal} 分析报告\n\n## 摘要\n\n基于现有数据的分析。\n\n## 关键发现\n\n- 需要更多数据支持深度分析\n- 建议结合搜索结果进行LLM增强分析\n\n## 数据概览\n\n{data_summary}\n\n## SWOT分析\n\n### 优势\n- 数据可用，可进行基础分析\n\n### 劣势\n- 缺乏LLM深度推理能力\n\n### 机会\n- 可通过启用LLM服务获得更高质量分析\n\n### 威胁\n- 数据不足可能导致分析偏差\n\n## 行动清单\n\n1. 收集更多相关数据\n2. 启用LLM服务进行深度分析\n",
            "summary": f"基于现有数据的{goal}分析",
            "key_findings": ["需要更多数据支持深度分析", "建议结合搜索结果进行LLM增强分析"],
            "swot": {"strengths": ["数据可用，可进行基础分析"], "weaknesses": ["缺乏LLM深度推理能力"], "opportunities": ["可通过启用LLM服务获得更高质量分析"], "threats": ["数据不足可能导致分析偏差"]},
            "action_items": ["收集更多相关数据", "启用LLM服务进行深度分析"],
        }

    def _rule_based_content_generation(self, goal: str, format: str) -> Dict[str, Any]:
        return {
            "content": f"# {goal}\n\n基于规则引擎生成的内容。建议启用LLM服务获取更高质量的输出。\n",
            "format": format,
            "fallback_used": True,
            "quality_score": 0.3,
        }

    async def _execute_operation(self, operation: str, parameters: dict = None, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        params = parameters or {}
        if self.tool_system is not None:
            try:
                tool_map = {
                    "read_file": "file_read",
                    "write_file": "file_write",
                    "list_directory": "file_list",
                    "search_files": "file_search",
                }
                tool_id = tool_map.get(operation)
                if tool_id is None:
                    return {"success": False, "error": f"不支持的操作: {operation}"}
                result = await self.tool_system.call_tool(tool_id, params)
                return result
            except Exception as e:
                logger.warning("工具系统操作失败: %s", e)
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "工具系统未初始化"}

    async def _execute_notification(self, message: str, recipient: str = None, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        if self.tool_system is not None:
            try:
                cleaned_recipient = (recipient or "").replace("\r", "").replace("\n", "")
                result = await self.tool_system.call_tool("send_email", {
                    "to": cleaned_recipient,
                    "subject": "OPC-Agents 通知",
                    "body": message,
                })
                return result
            except Exception as e:
                logger.warning("邮件发送失败: %s", e)
                return {"success": False, "error": str(e)}
        return {
            "sent": False,
            "recipient": recipient or "",
            "message": message,
            "error": "工具系统未初始化",
        }

    def _execute_output(self, data: dict = None, format: str = "markdown", _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        if data is None:
            data = {}
        return {
            "output": f"## 执行结果\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            "format": format
        }

    def _execute_email(self, goal: str, to: str = "", subject: str = "",
                       body: str = "", _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.email_skill import execute_goal
        return execute_goal(goal, _context, to=to, subject=subject, body=body)

    def _execute_finance(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.finance_skill import execute_goal as finance_execute_goal
        if any(kw in goal for kw in ["报税", "提醒"]):
            collab_result = self._execute_collaborative(goal, _context)
            if collab_result:
                return collab_result
        return finance_execute_goal(goal, _context)

    def _execute_task(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.task_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_crm(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.crm_skill import execute_goal as crm_execute_goal
        if any(kw in goal for kw in ["发邮件", "跟进"]):
            crm_result = None
            name = goal
            for kw in ["给", "发邮件", "跟进", "帮我", "的", "客户"]:
                name = name.replace(kw, "")
            name = name.strip().strip("，。、的")
            if name:
                from opc_manager.crm_skill import get_customer
                crm_result = get_customer(name=name)
            collab_result = self._execute_collaborative(goal, _context)
            if collab_result:
                if crm_result:
                    collab_result["crm_lookup"] = crm_result
                return collab_result
        return crm_execute_goal(goal, _context)

    def _execute_social(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.social_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_proposal(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.proposal_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_invoice(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.invoice_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_report(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.report_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_calendar(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.calendar_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_competitor(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.competitor_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_pricing(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.pricing_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_tax_reminder(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.tax_reminder_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_dashboard(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.dashboard_skill import execute_goal
        return execute_goal(goal, _context)

    def _execute_knowledge(self, goal: str, _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        from opc_manager.knowledge_skill import execute_goal
        return execute_goal(goal, _context)
