"""NextActionDecider - 下一步行动决策服务

[P2-15] Step 4: 从 ReflectorBrain 抽出的下一步行动决策职责。
负责根据评估结果决定下一步行动（继续/重试/调整/放弃/复核）+ 修正策略建议。
"""

from typing import Any, Dict, List, Optional
import logging

from .reflector_models import (
    EvaluationResult,
    Evaluation,
    NextAction,
    NextActionType,
    CorrectionStrategy,
)

logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 3
CONFIDENCE_CAP = 0.95
IMPROVEMENT_QUALITY_THRESHOLD = 0.7
QUALITY_THRESHOLD_CORRECTION = 0.6
MAX_CORRECTION_ATTEMPTS = 2
PLACEHOLDER_PATTERNS = [
    "[待补充]",
    "[占位符]",
    "[TODO]",
    "[placeholder]",
    "[待完善]",
    "[TBD]",
]


class NextActionDecider:
    """下一步行动决策器 — 根据评估结果决定下一步行动。

    决策矩阵：
    - EXCELLENT/GOOD → CONTINUE
    - ACCEPTABLE → CONTINUE（多步骤）或 REVIEW（最后一步）
    - POOR → RETRY（未达上限）或 ADJUST_STRATEGY
    - FAILURE → RETRY（未达上限）或 ABANDON
    """

    def decide_next_action(
        self, evaluation: Evaluation, plan: Optional[Dict[str, Any]] = None
    ) -> NextAction:
        """决定下一步行动。"""
        logger.info("根据评估结果决定下一步行动: %s", evaluation.result.name)

        if evaluation.result in [EvaluationResult.EXCELLENT, EvaluationResult.GOOD]:
            action = NextAction(
                action_type=NextActionType.CONTINUE,
                reason=f"执行结果良好（质量评分: {evaluation.quality_score:.2f}），继续下一步",
                confidence=min(CONFIDENCE_CAP, evaluation.quality_score),
            )

        elif evaluation.result == EvaluationResult.ACCEPTABLE:
            if plan and plan.get("steps"):
                remaining_steps = len(plan["steps"])
                if remaining_steps > 1:
                    action = NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"结果可接受（质量评分: {evaluation.quality_score:.2f}），继续执行后续步骤",
                        confidence=evaluation.quality_score,
                    )
                else:
                    action = NextAction(
                        action_type=NextActionType.REVIEW,
                        reason=f"结果仅部分符合预期（质量评分: {evaluation.quality_score:.2f}），建议人工复核",
                        confidence=0.6,
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.CONTINUE,
                    reason="结果可接受，继续执行",
                    confidence=evaluation.quality_score,
                )

        elif evaluation.result == EvaluationResult.POOR:
            if plan:
                retry_count = plan.get("retry_count", 0)
                if retry_count < MAX_RETRY_COUNT:
                    action = NextAction(
                        action_type=NextActionType.RETRY,
                        reason=f"结果较差（质量评分: {evaluation.quality_score:.2f}），尝试重试（第{retry_count + 1}次）",
                        parameters={"retry_count": retry_count + 1},
                        confidence=0.5,
                    )
                else:
                    action = NextAction(
                        action_type=NextActionType.ADJUST_STRATEGY,
                        reason=f"结果较差（质量评分: {evaluation.quality_score:.2f}），重试{retry_count}次仍未成功，需要调整策略",
                        confidence=0.7,
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.RETRY,
                    reason="结果较差，尝试重试",
                    confidence=0.5,
                )

        else:  # FAILURE
            if plan:
                retry_count = plan.get("retry_count", 0)
                if retry_count < MAX_RETRY_COUNT:
                    action = NextAction(
                        action_type=NextActionType.RETRY,
                        reason=f"执行失败（质量评分: {evaluation.quality_score:.2f}），尝试重试（第{retry_count + 1}次）",
                        parameters={"retry_count": retry_count + 1},
                        confidence=0.4,
                    )
                else:
                    action = NextAction(
                        action_type=NextActionType.ABANDON,
                        reason=f"执行失败（质量评分: {evaluation.quality_score:.2f}），重试{retry_count}次仍未成功，无法完成任务",
                        confidence=0.9,
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.ABANDON,
                    reason="执行失败，无法完成任务",
                    confidence=0.8,
                )

        logger.info("决定下一步行动: %s", action.action_type.name)
        return action

    def suggest_improvement(
        self, evaluation: Evaluation, plan: Dict[str, Any]
    ) -> List[str]:
        suggestions = []

        if evaluation.result in [EvaluationResult.POOR, EvaluationResult.FAILURE]:
            suggestions.append("• 检查输入参数是否正确")
            suggestions.append("• 尝试使用不同的技能或工具")
            suggestions.append("• 考虑拆分任务为更小的步骤")

        if evaluation.quality_score < IMPROVEMENT_QUALITY_THRESHOLD:
            suggestions.append("• 增加执行步骤的详细程度")
            suggestions.append("• 引入人工复核环节")

        if any("超时" in finding for finding in (evaluation.key_findings or [])):
            suggestions.append("• 增加超时时间设置")
            suggestions.append("• 优化执行流程，减少不必要的步骤")

        return suggestions

    def suggest_correction_strategy(
        self,
        evaluation: Evaluation,
        execution_results: List[Dict],
        correction_count: int = 0,
    ) -> Optional[CorrectionStrategy]:
        if evaluation.quality_score >= QUALITY_THRESHOLD_CORRECTION:
            return None

        if correction_count >= MAX_CORRECTION_ATTEMPTS:
            logger.info("修正次数已达上限(%s)，标记需人工复核", MAX_CORRECTION_ATTEMPTS)
            return None

        has_placeholders = self._check_placeholders(execution_results)
        has_error = any(not r.get("success", False) for r in execution_results)
        has_empty_data = any(
            r.get("success") and not r.get("data") for r in execution_results
        )

        if has_error:
            strategy = CorrectionStrategy.RETRY
        elif has_placeholders or has_empty_data:
            strategy = CorrectionStrategy.SEARCH_AND_RETRY
        elif evaluation.result == EvaluationResult.POOR:
            strategy = CorrectionStrategy.SWITCH_SKILL
        else:
            strategy = CorrectionStrategy.DEGRADE

        logger.info(
            "建议修正策略: %s (质量评分: %.2f, 修正次数: %s)",
            strategy.value,
            evaluation.quality_score,
            correction_count,
        )
        return strategy

    def _check_placeholders(self, execution_results: List[Dict]) -> bool:
        for result in execution_results:
            data = result.get("data")
            if not data:
                continue
            text = ""
            if isinstance(data, dict):
                text = str(data.get("content", "")) + str(
                    data.get("analysis_result", "")
                )
            elif isinstance(data, str):
                text = data
            else:
                text = str(data)
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern in text:
                    return True
        return False
