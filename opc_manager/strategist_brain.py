"""
策略脑 (StrategistBrain) - 负责意图理解和任务规划

这是三贤者架构中的贤者一，专注于宏观战略思考：
- 理解用户意图
- 制定执行计划
- 规划资源分配

[P2-15] Step 5: 意图理解 + 任务规划 + 外部技能解析职责已全部抽到独立服务，
StrategistBrain 作为 Facade 保留公共 API 向后兼容。
"""

from typing import Any, Dict, Optional
import logging

from opc_manager.intent_types import IntentType, INTENT_KEYWORDS

# [P2-15] Step 1: 数据模型抽到 strategist_models.py，此处 re-export 保向后兼容
from opc_manager.strategist_models import (  # noqa: F401
    ConstraintType,
    Constraint,
    Intent,
    Step,
    ExecutionPlan,
)

# [P2-15] Step 3: 服务抽到独立模块，Facade 委托
from opc_manager.intent_understanding_service import IntentUnderstandingService
from opc_manager.planning_service import PlanningService

# [P2-15] Step 5: 外部技能解析抽到 ExternalSkillResolver
from opc_manager.external_skill_resolver import ExternalSkillResolver

logger = logging.getLogger(__name__)

ESTIMATED_TIME_PER_STEP = 30

__all__ = [
    "StrategistBrain",
    "ConstraintType",
    "Constraint",
    "Intent",
    "Step",
    "ExecutionPlan",
    "IntentType",
    "ESTIMATED_TIME_PER_STEP",
]


class StrategistBrain:
    """策略脑 — 负责意图理解和任务规划（Facade）"""

    def __init__(
        self, llm_service: Optional[Any] = None, skill_registry: Optional[Any] = None
    ) -> None:
        """
        初始化策略脑

        Args:
            llm_service: LLM服务实例，用于意图理解
            skill_registry: 技能注册表实例，用于动态发现可用技能。
                传入后 LLM 规划将基于注册表实际技能生成计划，
                未传入时降级到基础技能集（向后兼容）。
        """
        self.llm_service = llm_service
        self.skill_registry = skill_registry

        self.intent_keywords = INTENT_KEYWORDS

        # 约束关键词映射
        self.constraint_keywords = {
            ConstraintType.TIME: ["时间", "尽快", "今天", "本周", "按时"],
            ConstraintType.COUNT: ["个", "份", "项", "数量", "限制"],
            ConstraintType.FORMAT: ["格式", "格式为", "输出为", "保存为"],
            ConstraintType.SCOPE: ["范围", "限于", "包含", "涉及"],
            ConstraintType.BUDGET: ["预算", "费用", "成本"],
        }

        # [P2-15] Step 5: 外部技能解析委托给 ExternalSkillResolver
        self._external_skill_resolver = ExternalSkillResolver()

        # [P2-15] Step 3: 委托给独立服务
        self._intent_service = IntentUnderstandingService(
            llm_service=llm_service,
            intent_keywords=self.intent_keywords,
            constraint_keywords=self.constraint_keywords,
            external_fallback=self._external_skill_resolver.resolve,
        )
        self._planning_service = PlanningService(
            llm_service=llm_service,
            skill_registry=skill_registry,
        )

    def understand_intent(
        self, user_input: str, context: Optional[Dict] = None
    ) -> Intent:
        """理解用户意图。

        [P2-15] Step 3: 委托给 IntentUnderstandingService，保留 Facade API 向后兼容。
        """
        return self._intent_service.understand_intent(user_input, context)

    def plan(self, intent: Intent) -> ExecutionPlan:
        """制定执行计划。

        [P2-15] Step 3: 委托给 PlanningService，保留 Facade API 向后兼容。
        """
        return self._planning_service.plan(intent)

    def to_dict(self) -> Dict[str, Any]:
        """
        将策略脑状态转换为字典

        Returns:
            Dict[str, Any]: 状态字典
        """
        return {
            "type": "strategist_brain",
            "intent_keywords": {k.name: v for k, v in self.intent_keywords.items()},
            "constraint_keywords": {
                k.name: v for k, v in self.constraint_keywords.items()
            },
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        if "intent_keywords" in data:
            parsed = {}
            for k, v in data["intent_keywords"].items():
                val = getattr(IntentType, k, None)
                if val is not None:
                    parsed[val] = v
            self.intent_keywords = parsed
            # 同步到 IntentUnderstandingService
            self._intent_service.intent_keywords = parsed
        if "constraint_keywords" in data:
            parsed = {}
            for k, v in data["constraint_keywords"].items():
                val = getattr(ConstraintType, k, None)
                if val is not None:
                    parsed[val] = v
            self.constraint_keywords = parsed
            # 同步到 IntentUnderstandingService
            self._intent_service.constraint_keywords = parsed

    def express_opinion(
        self, context: Dict[str, Any], decision_point: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        策略脑对决策点表达意见。

        P1-6 修复：接收并使用 decision_point 参数，给出针对具体决策点的意见。
        原实现不接收 decision_point，意见与决策点无关，近似于"摆设"。

        Args:
            context: 包含 intent 等上下文信息
            decision_point: 决策点标识（如 "execute_step", "send_email" 等）

        Returns:
            Dict[str, Any]: 包含 brain_type, opinion_type, reasoning, confidence
        """
        intent = context.get("intent")
        confidence = intent.confidence if intent else 0.5
        opinion_type = "AGREE" if confidence > 0.5 else "CONDITIONAL"

        # P1-6 修复：在 reasoning 中提及具体决策点，提升意见价值
        if decision_point:
            reasoning = (
                f"策略脑对决策点[{decision_point}]的意见: " f"置信度 {confidence:.2f}"
                if intent
                else f"策略脑对决策点[{decision_point}]的意见: 无意图信息"
            )
        else:
            reasoning = f"策略脑置信度: {confidence:.2f}" if intent else "无意图信息"

        return {
            "brain_type": "strategist",
            "opinion_type": opinion_type,
            "reasoning": reasoning,
            "confidence": confidence,
        }
