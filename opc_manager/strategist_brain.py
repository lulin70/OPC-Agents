"""
策略脑 (StrategistBrain) - 负责意图理解和任务规划

这是三贤者架构中的贤者一，专注于宏观战略思考：
- 理解用户意图
- 制定执行计划
- 规划资源分配
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import re
import uuid
import logging

from opc_manager.utils import extract_json_from_llm, sanitize_for_llm, _llm_thread_semaphore

logger = logging.getLogger(__name__)

ESTIMATED_TIME_PER_STEP = 30


class IntentType(Enum):
    """意图类型枚举"""
    UNKNOWN = "unknown"
    ANALYSIS = "analysis"          # 分析类任务
    CREATION = "creation"          # 创作类任务
    OPERATION = "operation"        # 操作类任务
    SEARCH = "search"              # 搜索类任务
    NOTIFICATION = "notification"  # 通知类任务
    COMBINED = "combined"          # 组合任务


class ConstraintType(Enum):
    """约束类型枚举"""
    TIME = "time"           # 时间约束
    COUNT = "count"         # 数量约束
    FORMAT = "format"       # 格式约束
    SCOPE = "scope"         # 范围约束
    BUDGET = "budget"       # 预算约束


@dataclass
class Constraint:
    """约束对象"""
    type: ConstraintType
    value: Any
    description: str = ""


@dataclass
class Intent:
    """意图对象 - 表示用户的核心目标和约束"""
    goal: str                          # 核心目标
    type: IntentType                   # 意图类型
    constraints: List[Constraint] = None  # 约束条件列表
    context: Dict[str, Any] = None      # 上下文信息
    confidence: float = 1.0             # 置信度
    sub_intents: List['Intent'] = None   # 子意图列表（复合意图时使用）

    def __post_init__(self):
        if self.constraints is None:
            self.constraints = []
        if self.context is None:
            self.context = {}
        if self.sub_intents is None:
            self.sub_intents = []


@dataclass
class Step:
    """执行步骤对象"""
    id: str                           # 步骤唯一标识
    skill_id: str                     # 技能ID
    description: str                  # 步骤描述
    parameters: Dict[str, Any] = None # 执行参数
    dependencies: List[str] = None    # 依赖的步骤ID列表
    retry_count: int = 0              # 重试次数

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class ExecutionPlan:
    """执行计划对象"""
    plan_id: str                      # 计划唯一标识
    intent: Intent                    # 关联的意图
    steps: List[Step]                 # 步骤列表
    resources: Dict[str, Any] = None  # 资源配置
    estimated_time: int = 0           # 预估执行时间（秒）

    def __post_init__(self):
        if self.resources is None:
            self.resources = {}


class StrategistBrain:
    """策略脑 — 负责意图理解和任务规划"""

    def __init__(self, llm_service=None):
        """
        初始化策略脑
        
        Args:
            llm_service: LLM服务实例，用于意图理解
        """
        self.llm_service = llm_service
        
        # 意图关键词映射
        self.intent_keywords = {
            IntentType.ANALYSIS: [
                "分析", "调研", "研究", "评估", "评价", "竞品", 
                "市场", "SWOT", "分析报告", "数据分析", "对比"
            ],
            IntentType.CREATION: [
                "写", "创作", "生成", "设计", "方案", "报告", 
                "文档", "文案", "策划", "规划", "脚本", "邮件"
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
                "发送", "通知", "邮件", "消息", "提醒", "告知"
            ]
        }

        # 约束关键词映射
        self.constraint_keywords = {
            ConstraintType.TIME: ["时间", "尽快", "今天", "本周", "按时"],
            ConstraintType.COUNT: ["个", "份", "项", "数量", "限制"],
            ConstraintType.FORMAT: ["格式", "格式为", "输出为", "保存为"],
            ConstraintType.SCOPE: ["范围", "限于", "包含", "涉及"],
            ConstraintType.BUDGET: ["预算", "费用", "成本"]
        }

    def understand_intent(self, user_input: str, context: Optional[Dict] = None) -> Intent:
        logger.info(f"开始理解意图: {user_input[:50]}...")
        
        if self.llm_service:
            try:
                intent = self._understand_intent_with_llm(user_input, context)
                if intent and intent.confidence > 0.5:
                    logger.info(f"LLM意图理解成功: {intent.type.name} (置信度: {intent.confidence:.2f})")
                    return intent
                logger.info("LLM意图理解置信度不足，降级到关键词匹配")
            except Exception as e:
                logger.warning(f"LLM意图理解失败，降级到关键词匹配: {e}")
        
        intent_type = self._detect_intent_type(user_input)
        constraints = self._extract_constraints(user_input)
        goal = self._extract_goal(user_input, intent_type)
        
        if context is None:
            context = {}
        
        confidence = self._calculate_confidence(user_input, intent_type)
        
        sub_intents = []
        if intent_type == IntentType.COMBINED:
            sub_intents = self._decompose_intent(user_input)
        
        intent = Intent(
            goal=goal,
            type=intent_type,
            constraints=constraints,
            context=context,
            confidence=confidence,
            sub_intents=sub_intents
        )
        
        logger.info(f"意图理解完成: {intent.type.name} - '{goal}' (置信度: {confidence:.2f}, 子意图: {len(sub_intents)})")
        return intent

    def _understand_intent_with_llm(self, user_input: str, context: Optional[Dict] = None) -> Optional[Intent]:
        sanitized_input = sanitize_for_llm(user_input, 500)
        
        prompt = f"""分析以下用户请求，返回JSON格式的意图分析结果。

用户请求: {sanitized_input}

请返回如下JSON格式（不要包含其他内容）:
{{
  "goal": "用户的核心目标（一句话描述）",
  "intent_type": "analysis|creation|operation|search|notification|combined",
  "confidence": 0.0-1.0的置信度,
  "sub_intents": ["子意图1", "子意图2"],
  "constraints": ["约束1", "约束2"]
}}

意图类型说明:
- analysis: 分析/调研/评估/竞品分析/SWOT/对比
- creation: 写/创建/生成/制作/起草/方案/报告/计划
- operation: 执行/操作/处理/整理/转换
- search: 搜索/查找/查询/了解
- notification: 通知/提醒/发送/告知
- combined: 包含两个及以上不同类型的子任务"""

        llm_response = self._call_llm(prompt)
        if not llm_response:
            return None

        try:
            data = extract_json_from_llm(llm_response)
            if not data:
                return None
            
            intent_type_str = data.get("intent_type", "unknown")
            intent_type = IntentType.UNKNOWN
            for it in IntentType:
                if it.value == intent_type_str:
                    intent_type = it
                    break
            
            goal = data.get("goal", user_input)
            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
            
            sub_intents = []
            for sub_goal in data.get("sub_intents", []):
                sub_type = self._detect_intent_type(sub_goal)
                sub_intents.append(Intent(
                    goal=sub_goal,
                    type=sub_type,
                    confidence=self._calculate_confidence(sub_goal, sub_type)
                ))
            
            constraints = []
            for c_str in data.get("constraints", []):
                constraints.append(Constraint(
                    type=ConstraintType.SCOPE,
                    value=None,
                    description=c_str
                ))
            constraints.extend(self._extract_constraints(user_input))
            
            return Intent(
                goal=goal,
                type=intent_type,
                constraints=constraints,
                context=context or {},
                confidence=confidence,
                sub_intents=sub_intents
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"LLM意图解析失败: {e}")
            return None

    def _call_llm(self, prompt: str) -> Optional[str]:
        if not self.llm_service:
            return None
        try:
            _llm_thread_semaphore.acquire(timeout=30)
            try:
                if hasattr(self.llm_service, 'generate'):
                    return self.llm_service.generate(prompt, max_tokens=500, timeout=15)
                elif hasattr(self.llm_service, '_call_llm_api'):
                    return self.llm_service._call_llm_api(prompt)
            finally:
                _llm_thread_semaphore.release()
        except Exception as e:
            logger.warning(f"LLM调用失败: {e}")
        return None

    def _detect_intent_type(self, user_input: str) -> IntentType:
        """
        检测意图类型
        
        Args:
            user_input: 用户输入文本
        
        Returns:
            IntentType: 意图类型
        """
        # 检查组合任务（包含多个类型关键词）
        matched_types = []
        for intent_type, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in user_input:
                    matched_types.append(intent_type)
                    break
        
        if len(matched_types) >= 2:
            return IntentType.COMBINED
        elif matched_types:
            return matched_types[0]
        else:
            return IntentType.UNKNOWN

    def _decompose_intent(self, user_input: str) -> List[Intent]:
        sub_intents = []
        separators = ["然后", "接着", "再", "并且", "以及", "还有", "和", "，", "、"]
        segments = [user_input]
        for sep in separators:
            new_segments = []
            for seg in segments:
                parts = seg.split(sep)
                new_segments.extend([p.strip() for p in parts if p.strip()])
            segments = new_segments
            if len(segments) >= 4:
                break

        if len(segments) < 2:
            segments = [user_input]

        for segment in segments:
            seg_type = self._detect_single_intent_type(segment)
            goal = self._extract_goal(segment, seg_type)
            confidence = self._calculate_confidence(segment, seg_type)
            sub_intents.append(Intent(
                goal=goal,
                type=seg_type,
                confidence=confidence
            ))

        return sub_intents

    def _detect_single_intent_type(self, text: str) -> IntentType:
        for intent_type, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return intent_type
        return IntentType.UNKNOWN

    def _extract_constraints(self, user_input: str) -> List[Constraint]:
        """
        从用户输入中提取约束条件
        
        Args:
            user_input: 用户输入文本
        
        Returns:
            List[Constraint]: 约束条件列表
        """
        constraints = []
        
        for constraint_type, keywords in self.constraint_keywords.items():
            for keyword in keywords:
                if keyword in user_input:
                    constraints.append(Constraint(
                        type=constraint_type,
                        value=None,
                        description=f"包含约束关键词: {keyword}"
                    ))
                    break
        
        number_matches = re.findall(r'(\d+)\s*(个|份|项|篇)', user_input)
        if number_matches:
            constraints.append(Constraint(
                type=ConstraintType.COUNT,
                value=int(number_matches[0][0]),
                description=f"数量限制为: {number_matches[0][0]}"
            ))
        
        return constraints

    def _extract_goal(self, user_input: str, intent_type: IntentType) -> str:
        """
        提取核心目标
        
        Args:
            user_input: 用户输入文本
            intent_type: 意图类型
        
        Returns:
            str: 核心目标描述
        """
        # 简单的目标提取：移除常见前缀词
        prefixes_to_remove = ["帮我", "请帮我", "我想", "我需要", "能不能"]
        
        goal = user_input.strip()
        for prefix in prefixes_to_remove:
            if goal.startswith(prefix):
                goal = goal[len(prefix):].strip()
                break
        
        # 添加意图类型描述
        type_descriptions = {
            IntentType.ANALYSIS: "分析任务",
            IntentType.CREATION: "创作任务",
            IntentType.OPERATION: "操作任务",
            IntentType.SEARCH: "搜索任务",
            IntentType.NOTIFICATION: "通知任务",
            IntentType.COMBINED: "组合任务",
            IntentType.UNKNOWN: "未知任务"
        }
        
        return f"{type_descriptions[intent_type]}: {goal}"

    def _calculate_confidence(self, user_input: str, intent_type: IntentType) -> float:
        """
        计算意图识别的置信度
        
        Args:
            user_input: 用户输入文本
            intent_type: 意图类型
        
        Returns:
            float: 置信度 (0.0-1.0)
        """
        if intent_type == IntentType.UNKNOWN:
            return 0.3
        
        # 根据匹配的关键词数量计算置信度
        confidence = 0.5
        keywords = self.intent_keywords.get(intent_type, [])
        matched_count = sum(1 for kw in keywords if kw in user_input)
        
        if matched_count >= 2:
            confidence = min(0.95, 0.5 + matched_count * 0.15)
        elif matched_count == 1:
            confidence = 0.7
        
        return confidence

    def plan(self, intent: Intent) -> ExecutionPlan:
        logger.info(f"开始制定执行计划: {intent.goal[:50]}...")
        
        if self.llm_service:
            try:
                plan = self._plan_with_llm(intent)
                if plan and plan.steps:
                    logger.info(f"LLM规划完成: {len(plan.steps)} 个步骤")
                    return plan
                logger.info("LLM规划失败，降级到规则规划")
            except Exception as e:
                logger.warning(f"LLM规划异常，降级到规则规划: {e}")
        
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        steps = self._generate_steps(intent)
        estimated_time = len(steps) * ESTIMATED_TIME_PER_STEP
        
        plan = ExecutionPlan(
            plan_id=plan_id,
            intent=intent,
            steps=steps,
            estimated_time=estimated_time
        )
        
        logger.info(f"执行计划制定完成: {len(steps)} 个步骤")
        return plan

    def _plan_with_llm(self, intent: Intent) -> Optional[ExecutionPlan]:
        sub_goals = [si.goal for si in intent.sub_intents] if intent.sub_intents else []
        
        prompt = f"""为以下任务制定执行计划，返回JSON格式。

任务目标: {intent.goal}
意图类型: {intent.type.value}
子目标: {json.dumps(sub_goals, ensure_ascii=False) if sub_goals else "无"}

可用技能: search(搜索), analysis(分析), content_generation(内容创作), execute_operation(执行操作), send_notification(发送通知), output_result(输出结果)

请返回JSON格式:
{{
  "steps": [
    {{"skill_id": "技能名", "description": "步骤描述", "parameters": {{"key": "value"}}}},
    ...
  ]
}}

规则:
1. 第一步通常是搜索或分析
2. 后续步骤基于前一步结果
3. 最后一步是output_result
4. 复合意图需要多步骤"""

        llm_response = self._call_llm(prompt)
        if not llm_response:
            return None
        
        try:
            data = extract_json_from_llm(llm_response)
            if not data:
                return None
            
            steps_data = data.get("steps", [])
            if not steps_data:
                return None
            
            steps = []
            for i, sd in enumerate(steps_data):
                skill_id = sd.get("skill_id", "output_result")
                if skill_id not in ["search", "analysis", "content_generation", "execute_operation", "send_notification", "intent_analysis", "output_result"]:
                    skill_id = "output_result"
                steps.append(Step(
                    id=f"step_{i+1}",
                    skill_id=skill_id,
                    description=sd.get("description", f"执行步骤{i+1}"),
                    parameters=sd.get("parameters", {"goal": intent.goal}),
                    dependencies=[f"step_{i}"] if i > 0 else []
                ))
            
            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            return ExecutionPlan(
                plan_id=plan_id,
                intent=intent,
                steps=steps,
                estimated_time=len(steps) * ESTIMATED_TIME_PER_STEP
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"LLM规划结果解析失败: {e}")
            return None

    def _generate_steps(self, intent: Intent) -> List[Step]:
        steps = []
        step_id = 1

        steps.append(Step(
            id=f"step_{step_id}",
            skill_id="intent_analysis",
            description="分析用户需求和约束条件",
            parameters={"goal": intent.goal, "constraints": [c.type.value for c in intent.constraints]}
        ))
        step_id += 1

        if intent.type == IntentType.COMBINED and intent.sub_intents:
            prev_step_id = "step_1"
            for sub_intent in intent.sub_intents:
                sub_steps = self._generate_skill_steps(sub_intent, step_id, prev_step_id)
                steps.extend(sub_steps)
                if sub_steps:
                    prev_step_id = sub_steps[-1].id
                    step_id += len(sub_steps)
        else:
            skill_steps = self._generate_skill_steps(intent, step_id, "step_1")
            steps.extend(skill_steps)
            if skill_steps:
                step_id += len(skill_steps)

        steps.append(Step(
            id=f"step_{step_id}",
            skill_id="output_result",
            description="输出最终结果",
            parameters={"format": "markdown"},
            dependencies=[steps[-1].id] if len(steps) > 1 else []
        ))

        return steps

    def _generate_skill_steps(self, intent: Intent, start_id: int, dep_id: str) -> List[Step]:
        steps = []
        step_id = start_id

        if intent.type in [IntentType.ANALYSIS, IntentType.COMBINED]:
            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="search",
                description="搜索相关信息和数据",
                parameters={"query": intent.goal, "max_results": 10},
                dependencies=[dep_id]
            ))
            step_id += 1

            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="analysis",
                description="进行深度分析",
                parameters={"goal": intent.goal},
                dependencies=[f"step_{step_id - 1}"]
            ))
            step_id += 1

        if intent.type in [IntentType.CREATION, IntentType.COMBINED]:
            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="content_generation",
                description="生成内容",
                parameters={"goal": intent.goal, "format": "markdown"},
                dependencies=[dep_id] if not steps else [steps[-1].id]
            ))
            step_id += 1

        if intent.type == IntentType.SEARCH:
            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="search",
                description="执行搜索",
                parameters={"query": intent.goal, "max_results": 15},
                dependencies=[dep_id]
            ))
            step_id += 1

        if intent.type == IntentType.OPERATION:
            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="execute_operation",
                description="执行操作",
                parameters={"operation": intent.goal},
                dependencies=[dep_id]
            ))
            step_id += 1

        if intent.type == IntentType.NOTIFICATION:
            steps.append(Step(
                id=f"step_{step_id}",
                skill_id="send_notification",
                description="发送通知",
                parameters={"message": intent.goal},
                dependencies=[dep_id]
            ))
            step_id += 1

        return steps

    def to_dict(self) -> Dict[str, Any]:
        """
        将策略脑状态转换为字典
        
        Returns:
            Dict[str, Any]: 状态字典
        """
        return {
            "type": "strategist_brain",
            "intent_keywords": {k.name: v for k, v in self.intent_keywords.items()},
            "constraint_keywords": {k.name: v for k, v in self.constraint_keywords.items()}
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典恢复策略脑状态
        
        Args:
            data: 状态字典
        """
        if "intent_keywords" in data:
            self.intent_keywords = {getattr(IntentType, k): v for k, v in data["intent_keywords"].items()}
        if "constraint_keywords" in data:
            self.constraint_keywords = {getattr(ConstraintType, k): v for k, v in data["constraint_keywords"].items()}
