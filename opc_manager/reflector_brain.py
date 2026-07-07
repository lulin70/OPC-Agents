"""
反思脑 (ReflectorBrain) - 负责结果评估和策略调整

这是三贤者架构中的贤者三，专注于全局反思：
- 评估执行结果
- 分析偏差原因
- 决定下一步行动

[P2-15] Step 4: 质量评估 + 行动决策职责已抽到独立服务，
ReflectorBrain 作为 Facade 保留公共 API 向后兼容。
"""

from typing import Any, Dict, List, Optional
import logging

from .consensus_engine import Opinion

# [P2-15] Step 1: 数据模型抽到 reflector_models.py，此处 re-export 保向后兼容
from .reflector_models import (  # noqa: F401
    EvaluationResult,
    NextActionType,
    CorrectionStrategy,
    Evaluation,
    NextAction,
)

# [P2-15] Step 2: 后果预判职责抽到 ConsequencePredictor
from .consequence_predictor import ConsequencePredictor

# [P2-15] Step 4: 质量评估 + 行动决策抽到独立服务
from .quality_evaluator import QualityEvaluator
from .next_action_decider import NextActionDecider

# 评估权重常量（re-export 保向后兼容，实际定义在 quality_evaluator.py）
from .quality_evaluator import (  # noqa: F401
    WEIGHT_SUCCESS,
    WEIGHT_DATA_COMPLETE_DICT,
    WEIGHT_DATA_COMPLETE_OTHER,
    WEIGHT_RELEVANCE,
    WEIGHT_TIMELY,
    WEIGHT_ALL_STEPS_DONE,
    PENALTY_ERROR,
)

# 行动决策常量（re-export 保向后兼容，实际定义在 next_action_decider.py）
from .next_action_decider import (  # noqa: F401
    MAX_RETRY_COUNT,
    CONFIDENCE_CAP,
    IMPROVEMENT_QUALITY_THRESHOLD,
    QUALITY_THRESHOLD_CORRECTION,
    MAX_CORRECTION_ATTEMPTS,
    PLACEHOLDER_PATTERNS,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ReflectorBrain",
    "EvaluationResult",
    "NextActionType",
    "CorrectionStrategy",
    "Evaluation",
    "NextAction",
    "WEIGHT_SUCCESS",
    "WEIGHT_DATA_COMPLETE_DICT",
    "WEIGHT_DATA_COMPLETE_OTHER",
    "WEIGHT_RELEVANCE",
    "WEIGHT_TIMELY",
    "WEIGHT_ALL_STEPS_DONE",
    "PENALTY_ERROR",
    "MAX_RETRY_COUNT",
    "CONFIDENCE_CAP",
    "IMPROVEMENT_QUALITY_THRESHOLD",
    "QUALITY_THRESHOLD_CORRECTION",
    "MAX_CORRECTION_ATTEMPTS",
    "PLACEHOLDER_PATTERNS",
]


class ReflectorBrain:
    """反思脑 — 负责结果评估和策略调整（Facade）"""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        # [P2-15] Step 2: 后果预判委托给 ConsequencePredictor
        self._consequence_predictor = ConsequencePredictor(llm_service=llm_service)
        # [P2-15] Step 4: 质量评估 + 行动决策委托给独立服务
        self._quality_evaluator = QualityEvaluator(llm_service=llm_service)
        self._next_action_decider = NextActionDecider()
        # 评估阈值配置（保留下用于 to_dict / from_dict）
        self.evaluation_thresholds = {
            EvaluationResult.EXCELLENT: 0.9,
            EvaluationResult.GOOD: 0.7,
            EvaluationResult.ACCEPTABLE: 0.5,
            EvaluationResult.POOR: 0.3,
            EvaluationResult.FAILURE: 0.0,
        }

    def evaluate_result(
        self, actual_result: Dict[str, Any], expected_intent: Dict[str, Any]
    ) -> Evaluation:
        """评估执行结果。

        [P2-15] Step 4: 委托给 QualityEvaluator，保留 Facade API 向后兼容。
        """
        return self._quality_evaluator.evaluate_result(actual_result, expected_intent)

    def decide_next_action(
        self, evaluation: Evaluation, plan: Optional[Dict[str, Any]] = None
    ) -> NextAction:
        """决定下一步行动。

        [P2-15] Step 4: 委托给 NextActionDecider，保留 Facade API 向后兼容。
        """
        return self._next_action_decider.decide_next_action(evaluation, plan)

    def suggest_improvement(
        self, evaluation: Evaluation, plan: Dict[str, Any]
    ) -> List[str]:
        """建议改进措施。

        [P2-15] Step 4: 委托给 NextActionDecider。
        """
        return self._next_action_decider.suggest_improvement(evaluation, plan)

    def suggest_correction_strategy(
        self,
        evaluation: Evaluation,
        execution_results: List[Dict],
        correction_count: int = 0,
    ) -> Optional[CorrectionStrategy]:
        """建议修正策略。

        [P2-15] Step 4: 委托给 NextActionDecider。
        """
        return self._next_action_decider.suggest_correction_strategy(
            evaluation, execution_results, correction_count
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        将反思脑状态转换为字典

        Returns:
            Dict[str, Any]: 状态字典
        """
        return {
            "type": "reflector_brain",
            "evaluation_thresholds": {
                k.name: v for k, v in self.evaluation_thresholds.items()
            },
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        if "evaluation_thresholds" in data:
            parsed = {}
            for k, v in data["evaluation_thresholds"].items():
                val = getattr(EvaluationResult, k, None)
                if val is not None:
                    parsed[val] = v
            self.evaluation_thresholds = parsed
            # 同步到 QualityEvaluator
            self._quality_evaluator.evaluation_thresholds = parsed

    def express_opinion(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Dict[str, Any]:
        """反思脑对决策点表达意见。

        P2-9 修复：统一三脑签名，接收 decision_point 参数（向后兼容，默认 None）。
        当 decision_point 不为 None 时，在 reasoning 中提及决策点，提升意见价值。

        Args:
            context: 包含 evaluation / next_action 等上下文信息
            decision_point: 决策点标识（如 "execute_step", "send_email" 等）

        Returns:
            Dict[str, Any]: 包含 brain_type, opinion_type, reasoning, confidence
        """
        evaluation = context.get("evaluation")
        action = context.get("next_action")
        quality_score = evaluation.quality_score if evaluation else 0.5
        opinion_type = "AGREE"
        if action:
            action_type = getattr(action, "action_type", None)
            if action_type and action_type not in (
                NextActionType.CONTINUE,
                NextActionType.RETRY,
            ):
                opinion_type = "DISAGREE"
        reasoning = (
            f"反思评估: {evaluation.result.name}" if evaluation else "无评估信息"
        )
        # P2-9 修复：decision_point 不为 None 时，在 reasoning 中提及决策点
        if decision_point is not None:
            reasoning = f"反思脑对决策点[{decision_point}]的意见: {reasoning}"
        return {
            "brain_type": "reflector",
            "opinion_type": opinion_type,
            "reasoning": reasoning,
            "confidence": quality_score,
        }

    def predict_consequence(
        self, context: Dict[str, Any], planned_action: Dict[str, Any]
    ) -> Opinion:
        """前置预判行动后果（少数派报告模式）。

        [P2-15] Step 2: 委托给 ConsequencePredictor，保留 Facade API 向后兼容。
        [S2-T5] 三贤者并行投票用，在执行前预测后果。
        保留 evaluate_result() 用于事后评估（二级保障）。
        """
        return self._consequence_predictor.predict_consequence(context, planned_action)

    async def predict_consequence_async(
        self, context: Dict[str, Any], planned_action: Dict[str, Any]
    ) -> Opinion:
        """异步版本（并行投票用）。

        [P2-15] Step 2: 委托给 ConsequencePredictor。
        """
        return await self._consequence_predictor.predict_consequence_async(
            context, planned_action
        )
