"""IntentUnderstandingService - 意图理解服务

[P2-15] Step 3: 从 StrategistBrain 抽出的意图理解职责。
负责解析用户输入，识别意图类型、约束条件、子意图。
"""

from typing import Any, Callable, Dict, List, Optional
import json
import logging
import re

from opc_manager.intent_types import IntentType, INTENT_KEYWORDS
from opc_manager.utils import (
    extract_json_from_llm,
    sanitize_for_llm,
    call_llm_service,
)
from opc_manager.strategist_models import (
    ConstraintType,
    Constraint,
    Intent,
)

logger = logging.getLogger(__name__)


class IntentUnderstandingService:
    """意图理解服务 — 解析用户输入为 Intent 对象。

    支持双路径：LLM 意图理解（高置信度）+ 关键词匹配降级（兜底）。
    """

    def __init__(
        self,
        llm_service=None,
        intent_keywords: Optional[Dict] = None,
        constraint_keywords: Optional[Dict[ConstraintType, List[str]]] = None,
        external_fallback: Optional[
            Callable[[str, str], Optional[Dict[str, Any]]]
        ] = None,
    ):
        self.llm_service = llm_service
        self.intent_keywords = (
            intent_keywords if intent_keywords is not None else INTENT_KEYWORDS
        )
        self.constraint_keywords = (
            constraint_keywords
            if constraint_keywords is not None
            else {
                ConstraintType.TIME: ["时间", "尽快", "今天", "本周", "按时"],
                ConstraintType.COUNT: ["个", "份", "项", "数量", "限制"],
                ConstraintType.FORMAT: ["格式", "格式为", "输出为", "保存为"],
                ConstraintType.SCOPE: ["范围", "限于", "包含", "涉及"],
                ConstraintType.BUDGET: ["预算", "费用", "成本"],
            }
        )
        # [P2-15] Step 5 之前：external_fallback 由 StrategistBrain 注入（_fallback_to_external）
        self._external_fallback = external_fallback

    def understand_intent(
        self, user_input: str, context: Optional[Dict] = None
    ) -> Intent:
        logger.info("开始理解意图: %s...", user_input[:50])

        if self.llm_service:
            try:
                intent = self._understand_intent_with_llm(user_input, context)
                if intent and intent.confidence > 0.5:
                    logger.info(
                        "LLM意图理解成功: %s (置信度: %.2f)",
                        intent.type.name,
                        intent.confidence,
                    )
                    return intent
                logger.info("LLM意图理解置信度不足，降级到关键词匹配")
            except Exception as e:
                logger.warning("LLM意图理解失败，降级到关键词匹配: %s", e)

        intent_type = self._detect_intent_type(user_input)
        constraints = self._extract_constraints(user_input)
        goal = self._extract_goal(user_input, intent_type)

        if context is None:
            context = {}

        if intent_type == IntentType.UNKNOWN and self._external_fallback is not None:
            fallback_result = self._external_fallback(user_input, goal)
            if fallback_result:
                intent_type = IntentType.EXTENDED_SKILL
                context.update(fallback_result.get("context", {}))
                goal = fallback_result.get("goal", goal)

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
            sub_intents=sub_intents,
        )

        logger.info(
            "意图理解完成: %s - '%s' (置信度: %.2f, 子意图: %s)",
            intent.type.name,
            goal,
            confidence,
            len(sub_intents),
        )
        return intent

    def _understand_intent_with_llm(
        self, user_input: str, context: Optional[Dict] = None
    ) -> Optional[Intent]:
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

        llm_response = call_llm_service(self.llm_service, prompt)
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
                sub_intents.append(
                    Intent(
                        goal=sub_goal,
                        type=sub_type,
                        confidence=self._calculate_confidence(sub_goal, sub_type),
                    )
                )

            constraints = []
            for c_str in data.get("constraints", []):
                constraints.append(
                    Constraint(
                        type=self._infer_constraint_type(c_str),
                        value=None,
                        description=c_str,
                    )
                )
            constraints.extend(self._extract_constraints(user_input))

            return Intent(
                goal=goal,
                type=intent_type,
                constraints=constraints,
                context=context or {},
                confidence=confidence,
                sub_intents=sub_intents,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("LLM意图解析失败: %s", e)
            return None

    def _detect_intent_type(self, user_input: str) -> IntentType:
        matched_types = []
        for intent_type, keywords in self.intent_keywords.items():
            sorted_keywords = sorted(keywords, key=len, reverse=True)
            for keyword in sorted_keywords:
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
            sub_intents.append(Intent(goal=goal, type=seg_type, confidence=confidence))

        return sub_intents

    def _detect_single_intent_type(self, text: str) -> IntentType:
        for intent_type, keywords in self.intent_keywords.items():
            sorted_keywords = sorted(keywords, key=len, reverse=True)
            for keyword in sorted_keywords:
                if keyword in text:
                    return intent_type
        return IntentType.UNKNOWN

    def _infer_constraint_type(self, constraint_text: str) -> ConstraintType:
        schedule_keywords = [
            "时间",
            "日期",
            "截止",
            "时限",
            "期限",
            "按时",
            "尽快",
            "今天",
            "本周",
            "明天",
        ]
        budget_keywords = ["预算", "费用", "成本", "花费", "金额", "价格", "开销"]
        quality_keywords = ["质量", "标准", "要求", "规范", "精度", "准确", "可靠"]
        for kw in schedule_keywords:
            if kw in constraint_text:
                return ConstraintType.TIME
        for kw in budget_keywords:
            if kw in constraint_text:
                return ConstraintType.BUDGET
        for kw in quality_keywords:
            if kw in constraint_text:
                return ConstraintType.SCOPE
        return ConstraintType.SCOPE

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
                    constraints.append(
                        Constraint(
                            type=constraint_type,
                            value=None,
                            description=f"包含约束关键词: {keyword}",
                        )
                    )
                    break

        number_matches = re.findall(r"(\d+)\s*(个|份|项|篇)", user_input)
        if number_matches:
            constraints.append(
                Constraint(
                    type=ConstraintType.COUNT,
                    value=int(number_matches[0][0]),
                    description=f"数量限制为: {number_matches[0][0]}",
                )
            )

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
        suffix_particles = ["吧", "呢", "吗", "啊", "呀", "哦"]
        complex_patterns = [("能不能帮我", ""), ("请帮我", "")]

        goal = user_input.strip()
        for pattern, replacement in complex_patterns:
            if goal.startswith(pattern):
                goal = replacement + goal[len(pattern) :].strip()
                break
        for prefix in prefixes_to_remove:
            if goal.startswith(prefix):
                goal = goal[len(prefix) :].strip()
                break
        while goal and goal[-1] in suffix_particles:
            goal = goal[:-1].strip()

        return goal

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
