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

logger = logging.getLogger(__name__)


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
    execute: Callable               # 执行函数
    enabled: bool = True            # 是否启用
    version: str = "1.0"            # 版本号
    intent_keywords: List[str] = None  # 触发意图的关键词

    def __post_init__(self):
        if self.intent_keywords is None:
            self.intent_keywords = []


class SkillRegistry:
    """技能注册表 — 负责技能的注册、发现和调用"""

    def __init__(
        self,
        llm_service=None,
        search_processor=None,
        tool_system=None,
    ):
        """初始化技能注册表

        Args:
            llm_service: LLM服务实例（可选，用于技能内容生成）
            search_processor: 搜索结果处理器（可选，用于搜索增强）
            tool_system: 工具系统实例（可选，用于文件操作和通知）
        """
        self.llm_service = llm_service
        self.search_processor = search_processor
        self.tool_system = tool_system
        self.skills: Dict[str, Skill] = {}
        self.category_index: Dict[str, List[str]] = {}
        self.keyword_index: Dict[str, List[str]] = {}
        
        # 注册内置技能
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """注册内置技能"""
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
        
        # 搜索技能
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
            intent_keywords=["搜索", "查找", "查询"]
        )
        self.register_skill(search_skill)
        
        # 分析技能
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
            intent_keywords=["分析", "研究", "评估"]
        )
        self.register_skill(analysis_skill)
        
        # 内容生成技能
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
            intent_keywords=["写", "创作", "生成"]
        )
        self.register_skill(content_gen_skill)
        
        # 操作执行技能
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
            intent_keywords=["执行", "操作", "运行"]
        )
        self.register_skill(operation_skill)
        
        # 通知发送技能
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
            intent_keywords=["发送", "通知", "邮件"]
        )
        self.register_skill(notification_skill)
        
        # 结果输出技能
        output_skill = Skill(
            skill_id="output_result",
            name="结果输出",
            description="输出最终结果",
            category=SkillCategory.UTILITY,
            inputs=[
                SkillInput(name="data", type="dict", description="结果数据"),
                SkillInput(name="format", type="str", required=False, default="markdown", description="输出格式")
            ],
            outputs=[
                SkillOutput(name="output", type="str", description="格式化输出")
            ],
            execute=self._execute_output,
            intent_keywords=["输出", "生成", "报告"]
        )
        self.register_skill(output_skill)

    def register_skill(self, skill: Skill) -> bool:
        """
        注册技能
        
        Args:
            skill: 技能对象
        
        Returns:
            bool: 是否注册成功
        """
        if skill.skill_id in self.skills:
            logger.warning(f"技能已存在: {skill.skill_id}")
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
        
        logger.info(f"技能注册成功: {skill.skill_id}")
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

            return {"success": True, "data": result}

        except Exception as e:
            logger.error(f"技能执行异常: {skill_id}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}

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
        if "skills" in data:
            for sid, sdata in data["skills"].items():
                if sid not in self.skills:
                    logger.warning(f"跳过未知技能恢复: {sid}")

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
                logger.warning(f"搜索增强失败，使用降级: {e}")

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
            from opc_hr.web_search import WebSearchMCP
            if not hasattr(self, '_web_search') or self._web_search is None:
                self._web_search = WebSearchMCP()
            if self._web_search.is_available():
                loop = asyncio.get_running_loop()
                results = await loop.run_in_executor(
                    None, self._web_search.search, query, max_results
                )
                return results
        except ImportError:
            logger.warning("WebSearchMCP不可用，搜索功能降级")
        except Exception as e:
            logger.warning(f"Web搜索失败: {e}")
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
                logger.warning(f"LLM分析失败，使用规则引擎降级: {e}")

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
                logger.warning(f"LLM内容生成失败，使用规则引擎降级: {e}")

        return self._rule_based_content_generation(goal, format)

    async def _call_llm_generate(self, user_input: str, template: str, search_results: list = None):
        try:
            from opc_manager.llm_content import LLMEnhancedContentGenerator
            if not hasattr(self, '_content_generator') or self._content_generator is None:
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
            logger.warning(f"LLM生成调用失败: {e}")
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
        return {
            "analysis_result": f"# {goal} 分析报告\n\n## 摘要\n\n基于现有数据的分析。\n\n## 关键发现\n\n- 需要更多数据支持深度分析\n- 建议结合搜索结果进行LLM增强分析\n\n## SWOT分析\n\n### 优势\n- 待分析\n\n### 劣势\n- 待分析\n\n### 机会\n- 待分析\n\n### 威胁\n- 待分析\n\n## 行动清单\n\n1. 收集更多相关数据\n2. 启用LLM服务进行深度分析\n",
            "summary": f"基于现有数据的{goal}分析",
            "key_findings": ["需要更多数据支持深度分析", "建议结合搜索结果进行LLM增强分析"],
            "swot": {"strengths": ["待分析"], "weaknesses": ["待分析"], "opportunities": ["待分析"], "threats": ["待分析"]},
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
                logger.warning(f"工具系统操作失败: {e}")
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
                logger.warning(f"邮件发送失败: {e}")
                return {"success": False, "error": str(e)}
        return {
            "sent": False,
            "recipient": recipient or "",
            "message": message,
            "error": "工具系统未初始化",
        }

    def _execute_output(self, data: dict, format: str = "markdown", _context: Optional[SkillContext] = None) -> Dict[str, Any]:
        """输出结果"""
        return {
            "output": f"## 执行结果\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            "format": format
        }
