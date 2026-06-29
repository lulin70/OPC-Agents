"""
技能注册表 (SkillRegistry) - 负责技能的注册、发现和调用

这是三贤者架构的技能管理中心：
- 注册技能
- 发现技能
- 调用技能
- 依赖注入LLMService/SearchResultProcessor/ToolSystem

=== Module Structure (after refactoring) ===
- This file: Core registry logic (singleton, query, dispatch, export)
- skill_builtin.py: 21 built-in skill definitions and registration
- skill_executors.py: All _execute_* method implementations (mixin)
"""

from typing import Dict, List, Optional, Any, TYPE_CHECKING
import asyncio
import json
import logging
import threading

from opc_manager.protocols import LLMServiceProtocol
from opc_manager.skill_models import (
    SkillContext,
    SkillCategory,
    SkillInput,
    SkillOutput,
    Skill,
)
from opc_manager.skill_builtin import register_builtin_skills
from opc_manager.skill_executors import SkillExecutorMixin

if TYPE_CHECKING:
    # 仅为类型检查导入，避免循环依赖；运行时在方法内部懒加载
    from opc_manager.skill_marketplace import ExternalSkillMarketplace

__all__ = [
    "SkillRegistry",
    "SKILL_COLLABORATIONS",
    "Skill",
    "SkillCategory",
    "SkillInput",
    "SkillOutput",
    "SkillContext",
]

logger = logging.getLogger(__name__)

SKILL_COLLABORATIONS = {
    "crm_to_email": {"trigger": ["跟进", "发邮件"], "skills": ["crm", "email"]},
    # P1 修复：finance_to_tax 已删除（tax_reminder 已冻结 v0.3.0）
    # "finance_to_tax": {"trigger": ["记账", "报税"], "skills": ["finance", "tax_reminder"]},
    "deal_to_income": {"trigger": ["成交", "收款"], "skills": ["crm", "finance"]},
    "report_full": {
        "trigger": ["经营报告", "全面报告"],
        "skills": ["finance", "crm", "task_manager", "report"],
    },
    "deal_to_email": {
        "trigger": ["成交后发邮件", "成交通知"],
        "skills": ["crm", "email"],
    },
    # P1 修复：report_to_calendar 已删除（calendar 已冻结 v0.3.0）
    # "report_to_calendar": {"trigger": ["报告截止", "报告日程"], "skills": ["report", "calendar"]},
    # P1 修复：proposal_to_email 已删除（proposal 已冻结 v0.3.0）
    # "proposal_to_email": {"trigger": ["报价后发邮件", "报价通知"], "skills": ["proposal", "email"]},
}


class SkillRegistry(SkillExecutorMixin):
    """技能注册表 — 负责技能的注册、发现和调用"""

    _instance = None
    _instance_lock = threading.Lock()
    _init_lock = threading.Lock()
    # 仅类型注解，不创建类属性（保留单例 __init__ 的 hasattr 守卫语义）
    _initialized: bool

    def __new__(
        cls,
        llm_service=None,
        search_processor=None,
        tool_system=None,
        register_builtins: bool = True,
        register_external: bool = True,
    ):
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
            if hasattr(self, "_initialized") and self._initialized:
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
            self._external_marketplace: Optional["ExternalSkillMarketplace"] = None

            if register_builtins:
                register_builtin_skills(self)

            if register_external:
                self._register_external_skills()

            self._web_search = None
            self._content_generator = None

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
                    inputs=[
                        SkillInput(name="goal", type="str", description="执行目标")
                    ],
                    outputs=[
                        SkillOutput(name="result", type="dict", description="执行结果")
                    ],
                    execute=self._execute_extended_skill,
                    enabled=True,
                    version=row.get("version", "1.0.0"),
                    intent_keywords=config.get("keywords", []),
                )
                self.register_skill(ext_skill)
        except Exception as e:
            logger.debug("注册外部技能失败: %s", e)

    def _execute_extended_skill(
        self, goal: str = "", _context: Optional[SkillContext] = None, **kwargs
    ) -> Dict[str, Any]:
        try:
            from opc_manager.skill_marketplace import ExternalSkillMarketplace

            if self._external_marketplace is None:
                self._external_marketplace = ExternalSkillMarketplace()
            skill_id = kwargs.get("skill_id", "")
            if skill_id:
                clean_skill_id = (
                    skill_id.replace("ext_", "")
                    if skill_id.startswith("ext_")
                    else skill_id
                )
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

    def install_external_skill(
        self, skill_id: str, source: str = "opc_official"
    ) -> Dict[str, Any]:
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
                    logger.info(
                        "技能版本升级: %s %s→%s",
                        skill.skill_id,
                        existing.version,
                        skill.version,
                    )
                    self.skills[skill.skill_id] = skill
                    return True
            except Exception as e:
                logger.debug("[SkillRegistry] Version comparison failed: %s", e)
            logger.warning("技能已存在: %s", skill.skill_id)
            return False

        self.skills[skill.skill_id] = skill

        category_name = skill.category.value
        if category_name not in self.category_index:
            self.category_index[category_name] = []
        self.category_index[category_name].append(skill.skill_id)

        for keyword in (skill.intent_keywords or []):
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

        for keyword, skill_ids in self.keyword_index.items():
            if keyword in intent_text:
                matched_skill_ids.update(skill_ids)

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

    async def execute_skill(  # type: ignore[override]  # 参数名 skill_id 为公开 API，不可改为父类的 skill_name
        self, skill_id: str, context: Optional[SkillContext] = None, **kwargs
    ) -> Dict[str, Any]:
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_id}"}

        if not skill.enabled:
            return {"success": False, "error": f"技能已禁用: {skill_id}"}

        # P0-3 修复：技能冻结机制真正生效
        # frozen=True 表示完全冻结，拒绝执行；frozen="semi" 表示半冻结，允许维护方法调用
        if getattr(skill, "frozen", False) is True:
            logger.warning("技能已冻结（v0.3.0），拒绝执行: %s", skill_id)
            return {
                "success": False,
                "error": f"技能已冻结（v0.3.0 产品收缩决策）: {skill_id}。详见 docs/spec/SKILL_FREEZE_LIST.md",
            }

        try:
            missing_params = []
            for input_spec in skill.inputs:
                if input_spec.required and input_spec.name not in kwargs:
                    missing_params.append(input_spec.name)

            if missing_params:
                return {
                    "success": False,
                    "error": f"缺少必填参数: {', '.join(missing_params)}",
                }

            if asyncio.iscoroutinefunction(skill.execute):
                result = await skill.execute(**kwargs, _context=context)
            else:
                result = skill.execute(**kwargs, _context=context)

            from opc_manager.export.models import (
                SKILL_EXPORT_CAPABILITIES,
                ExportFormat,
            )

            supported = SKILL_EXPORT_CAPABILITIES.get(skill_id, [ExportFormat.MARKDOWN])
            result["_exportable_formats"] = [f.value for f in supported]

            return {"success": True, "data": result}

        except Exception as e:
            logger.error("技能执行异常: %s, 错误: %s", skill_id, str(e))
            return {"success": False, "error": str(e)}

    def export_result(
        self, skill_id: str, result_data: Dict[str, Any], fmt: str, **opts
    ) -> bytes:
        from opc_manager.export import ExportManager
        from opc_manager.export.models import ResultData, ExportFormat

        manager = ExportManager()
        format_enum = ExportFormat(fmt)
        content = result_data.get("content", result_data.get("output", ""))
        data = ResultData(
            content=content,
            metadata=result_data.get(
                "metadata", {"title": result_data.get("title", "Export")}
            ),
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
                    "description": s.description,
                }
                for sid, s in self.skills.items()
            },
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        pass

    def _execute_collaborative(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Optional[Dict[str, Any]]:
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
            context_data: Dict[str, Any] = {}
            for skill_id in collab["skills"]:
                skill = self.get_skill(skill_id)
                if not skill or skill.execute is None:
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
                    results.append(
                        {
                            "skill_id": skill_id,
                            "result": {"success": False, "error": str(e)},
                        }
                    )

            if results:
                return {
                    "success": any(
                        isinstance(r["result"], dict) and r["result"].get("success")
                        for r in results
                    ),
                    "collaboration": collab_name,
                    "results": results,
                    "message": f"协作执行完成: {' → '.join(collab['skills'])}",
                }
        finally:
            self._collab_in_progress = False
        return None
