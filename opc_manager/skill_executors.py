"""
Skill Execution Methods for SkillRegistry

This module contains all skill execution (_execute_*) methods extracted from SkillRegistry.
Implemented as a mixin class (SkillExecutorMixin) to preserve all method signatures.

=== Extracted Components ===
- SkillExecutorMixin: Mixin providing all _execute_* methods
  - Core executors: _execute_intent_analysis, _execute_search, _execute_analysis,
    _execute_content_generation, _execute_operation, _execute_notification, _execute_output
  - Domain-specific executors: _execute_email, _execute_finance, _execute_task,
    _execute_crm, _execute_social, _execute_proposal, _execute_invoice,
    _execute_report, _execute_calendar, _execute_competitor, _execute_pricing,
    _execute_tax_reminder, _execute_dashboard, _execute_knowledge
  - Helper methods: _do_web_search, _call_llm_generate, _get_analysis_template,
    _get_content_template, _parse_analysis_result, _rule_based_analysis,
    _rule_based_content_generation

=== Design Notes ===
- Uses mixin pattern so SkillRegistry inherits these methods without signature changes
- Each executor delegates to domain-specific skill modules (email_skill, finance_skill, etc.)
- LLM-enhanced execution with rule-based fallback for resilience
"""

import asyncio
import json
import logging
import re
from typing import Dict, Optional, Any, TYPE_CHECKING

from opc_manager.skill_models import SkillContext

logger = logging.getLogger(__name__)


class SkillExecutorMixin:
    """Mixin class containing all skill execution methods for SkillRegistry.

    These methods handle the actual execution logic for each registered skill.
    Most domain-specific skills delegate to their dedicated modules (e.g.,
    email_skill, finance_skill), while core skills (search, analysis) have
    inline implementations.
    """

    # Attributes provided by SkillRegistry (parent class in mixin pattern).
    # Declared as Any; actual types defined in parent. No runtime value.
    search_processor: Any
    llm_service: Any
    tool_system: Any
    _web_search: Any
    _content_generator: Any

    if TYPE_CHECKING:
        # Method stubs - actual implementation in SkillRegistry (mixin parent).
        # Only visible to mypy; runtime resolves via parent class MRO.
        async def execute_skill(
            self, skill_name: str, context: Any = None, **kwargs: Any
        ) -> Dict[str, Any]: ...

        def _execute_collaborative(
            self, goal: str, context: Any = None
        ) -> Optional[Dict[str, Any]]: ...

    def _execute_intent_analysis(
        self,
        user_input: str,
        context: Optional[dict] = None,
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
        """执行意图分析"""
        return {"intent": {"goal": user_input, "type": "analysis"}, "confidence": 0.85}

    async def _execute_search(
        self, query: str, max_results: int = 10, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        cleaned_query = re.sub(r'[<>&"\']', "", query).strip()
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

    async def _execute_analysis(
        self,
        data: Optional[list] = None,
        goal: str = "",
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
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

    async def _execute_content_generation(
        self,
        goal: str,
        format: str = "markdown",
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
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

    async def _call_llm_generate(
        self, user_input: str, template: str, search_results: Optional[list] = None
    ):
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
                "## 资源需求\n\n列出所需资源。\n\n"
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
                    "swot": parsed.get(
                        "swot",
                        {
                            "strengths": [],
                            "weaknesses": [],
                            "opportunities": [],
                            "threats": [],
                        },
                    ),
                    "action_items": parsed.get("action_items", []),
                }
        except (json.JSONDecodeError, IndexError, AttributeError):
            pass

        result: Dict[str, Any] = {
            "analysis_result": content,
            "summary": "",
            "key_findings": [],
            "swot": {
                "strengths": [],
                "weaknesses": [],
                "opportunities": [],
                "threats": [],
            },
            "action_items": [],
        }
        sections = content.split("##")
        for section in sections:
            section_lower = section.lower()
            if "摘要" in section_lower:
                result["summary"] = section.strip().split("\n", 1)[-1].strip()
            elif "关键发现" in section_lower:
                lines = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip().startswith(("-", "•", "*"))
                    or any(line.strip().startswith(f"{i}.") for i in range(1, 10))
                ]
                result["key_findings"] = lines
            elif "优势" in section_lower or "strengths" in section_lower:
                result["swot"]["strengths"] = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            elif "劣势" in section_lower or "weaknesses" in section_lower:
                result["swot"]["weaknesses"] = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            elif "机会" in section_lower or "opportunities" in section_lower:
                result["swot"]["opportunities"] = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            elif "威胁" in section_lower or "threats" in section_lower:
                result["swot"]["threats"] = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
            elif "行动" in section_lower:
                result["action_items"] = [
                    line.strip().lstrip("-•*0-9. ")
                    for line in section.strip().split("\n")
                    if line.strip() and not line.strip().startswith("#")
                ]
        return result

    def _rule_based_analysis(self, goal: str, data: list) -> Dict[str, Any]:
        data_summary = ""
        if data:
            items = data[:5]
            data_summary = "\n".join(f"- {item}" for item in items)

        return {
            "analysis_result": (
                f"# {goal} 分析报告\n\n"
                "## 摘要\n\n基于现有数据的分析。\n\n"
                "## 关键发现\n\n"
                "- 需要更多数据支持深度分析\n"
                "- 建议结合搜索结果进行LLM增强分析\n\n"
                "## 数据概览\n\n"
                f"{data_summary}\n\n"
                "## SWOT分析\n\n"
                "### 优势\n- 数据可用，可进行基础分析\n\n"
                "### 劣势\n- 缺乏LLM深度推理能力\n\n"
                "### 机会\n- 可通过启用LLM服务获得更高质量分析\n\n"
                "### 威胁\n- 数据不足可能导致分析偏差\n\n"
                "## 行动清单\n\n"
                "1. 收集更多相关数据\n"
                "2. 启用LLM服务进行深度分析\n"
            ),
            "summary": f"基于现有数据的{goal}分析",
            "key_findings": [
                "需要更多数据支持深度分析",
                "建议结合搜索结果进行LLM增强分析",
            ],
            "swot": {
                "strengths": ["数据可用，可进行基础分析"],
                "weaknesses": ["缺乏LLM深度推理能力"],
                "opportunities": ["可通过启用LLM服务获得更高质量分析"],
                "threats": ["数据不足可能导致分析偏差"],
            },
            "action_items": ["收集更多相关数据", "启用LLM服务进行深度分析"],
        }

    def _rule_based_content_generation(self, goal: str, format: str) -> Dict[str, Any]:
        return {
            "content": f"# {goal}\n\n基于规则引擎生成的内容。建议启用LLM服务获取更高质量的输出。\n",
            "format": format,
            "fallback_used": True,
            "quality_score": 0.3,
        }

    async def _execute_operation(
        self,
        operation: str,
        parameters: Optional[dict] = None,
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
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

    async def _execute_notification(
        self,
        message: str,
        recipient: Optional[str] = None,
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
        if self.tool_system is not None:
            try:
                cleaned_recipient = (
                    (recipient or "").replace("\r", "").replace("\n", "")
                )
                result = await self.tool_system.call_tool(
                    "send_email",
                    {
                        "to": cleaned_recipient,
                        "subject": "OPC-Agents 通知",
                        "body": message,
                    },
                )
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

    def _execute_output(
        self,
        data: Optional[dict] = None,
        format: str = "markdown",
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
        if data is None:
            data = {}
        return {
            "output": f"## 执行结果\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            "format": format,
        }

    def _execute_email(
        self,
        goal: str,
        to: str = "",
        subject: str = "",
        body: str = "",
        _context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
        from opc_manager.email_skill import execute_goal

        return execute_goal(goal, _context, to=to, subject=subject, body=body)

    def _execute_finance(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.finance_skill import execute_goal as finance_execute_goal

        if any(kw in goal for kw in ["报税", "提醒"]):
            collab_result = self._execute_collaborative(goal, _context)
            if collab_result:
                return collab_result
        return finance_execute_goal(goal, _context)

    def _execute_task(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.task_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_crm(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
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

    def _execute_social(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.social_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_proposal(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.proposal_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_invoice(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.invoice_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_report(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.report_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_calendar(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.calendar_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_competitor(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.competitor_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_pricing(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.pricing_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_tax_reminder(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.tax_reminder_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_dashboard(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.dashboard_skill import execute_goal

        return execute_goal(goal, _context)

    def _execute_knowledge(
        self, goal: str, _context: Optional[SkillContext] = None
    ) -> Dict[str, Any]:
        from opc_manager.knowledge_skill import execute_goal

        return execute_goal(goal, _context)
