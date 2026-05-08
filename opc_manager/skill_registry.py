"""
技能注册表 (SkillRegistry) - 负责技能的注册、发现和调用

这是三贤者架构的技能管理中心：
- 注册技能
- 发现技能
- 调用技能
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


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

    def __init__(self):
        """初始化技能注册表"""
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
                SkillOutput(name="results", type="list", description="搜索结果列表"),
                SkillOutput(name="count", type="int", description="结果数量")
            ],
            execute=self._execute_search,
            intent_keywords=["搜索", "查找", "查询"]
        )
        self.register_skill(search_skill)
        
        # 分析技能
        analysis_skill = Skill(
            skill_id="analysis",
            name="分析",
            description="进行深度分析",
            category=SkillCategory.ANALYSIS,
            inputs=[
                SkillInput(name="data", type="list", description="待分析数据"),
                SkillInput(name="goal", type="str", description="分析目标")
            ],
            outputs=[
                SkillOutput(name="analysis_result", type="str", description="分析结果"),
                SkillOutput(name="key_findings", type="list", description="关键发现")
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

    async def execute_skill(self, skill_id: str, **kwargs) -> Dict[str, Any]:
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
                result = await skill.execute(**kwargs)
            else:
                result = skill.execute(**kwargs)

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
    def _execute_intent_analysis(self, user_input: str, context: dict = None) -> Dict[str, Any]:
        """执行意图分析"""
        return {
            "intent": {"goal": user_input, "type": "analysis"},
            "confidence": 0.85
        }

    def _execute_search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        return {
            "results": [f"搜索结果 {i}: {query}" for i in range(min(max_results, 5))],
            "count": min(max_results, 5)
        }

    def _execute_analysis(self, data: list, goal: str) -> Dict[str, Any]:
        """执行分析"""
        return {
            "analysis_result": f"针对 '{goal}' 的分析结果",
            "key_findings": ["发现1", "发现2", "发现3"]
        }

    def _execute_content_generation(self, goal: str, format: str = "markdown") -> Dict[str, Any]:
        """执行内容生成"""
        return {
            "content": f"# {goal}\n\n根据您的需求，我已生成了相关内容。",
            "format": format
        }

    def _execute_operation(self, operation: str, parameters: dict = None) -> Dict[str, Any]:
        """执行操作"""
        return {
            "result": f"操作 '{operation}' 执行成功"
        }

    def _execute_notification(self, message: str, recipient: str = None) -> Dict[str, Any]:
        """发送通知"""
        return {
            "sent": True,
            "recipient": recipient or "默认接收者",
            "message": message
        }

    def _execute_output(self, data: dict, format: str = "markdown") -> Dict[str, Any]:
        """输出结果"""
        return {
            "output": f"## 执行结果\n\n{json.dumps(data, indent=2, ensure_ascii=False)}",
            "format": format
        }
