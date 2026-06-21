"""
反思脑 (ReflectorBrain) - 负责结果评估和策略调整

这是三贤者架构中的贤者三，专注于全局反思：
- 评估执行结果
- 分析偏差原因
- 决定下一步行动
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import json
import re
import logging

from opc_manager.utils import (
    extract_json_from_llm,
    sanitize_for_llm,
    call_llm_service,
)
from .consensus_engine import Opinion, OpinionType

logger = logging.getLogger(__name__)

WEIGHT_SUCCESS = 0.3
WEIGHT_DATA_COMPLETE_DICT = 0.25
WEIGHT_DATA_COMPLETE_OTHER = 0.2
WEIGHT_RELEVANCE = 0.25
WEIGHT_TIMELY = 0.05
WEIGHT_ALL_STEPS_DONE = 0.15
PENALTY_ERROR = 0.3
MAX_RETRY_COUNT = 3
CONFIDENCE_CAP = 0.95
IMPROVEMENT_QUALITY_THRESHOLD = 0.7


class EvaluationResult(Enum):
    """评估结果类型枚举"""

    EXCELLENT = "excellent"  # 优秀（完全符合预期）
    GOOD = "good"  # 良好（基本符合预期）
    ACCEPTABLE = "acceptable"  # 可接受（部分符合预期）
    POOR = "poor"  # 差（不符合预期）
    FAILURE = "failure"  # 失败（完全不符合预期）


class NextActionType(Enum):
    """下一步行动类型枚举"""

    CONTINUE = "continue"  # 继续执行（结果符合预期）
    RETRY = "retry"  # 重试（执行失败，可重试）
    ADJUST_STRATEGY = "adjust_strategy"  # 调整策略（路径错误）
    ABANDON = "abandon"  # 放弃（无法完成）
    REVIEW = "review"  # 人工复核（需要人工介入）


class CorrectionStrategy(Enum):
    """修正策略类型枚举"""

    RETRY = "retry"  # 重试当前步骤
    SEARCH_AND_RETRY = "search_and_retry"  # 补充搜索后重试
    SWITCH_SKILL = "switch_skill"  # 换技能执行
    DEGRADE = "degrade"  # 降级到规则引擎


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


@dataclass
class Evaluation:
    """评估结果对象"""

    result: EvaluationResult  # 评估结果类型
    quality_score: float  # 质量评分 (0.0-1.0)
    deviation_analysis: str  # 偏差分析
    key_findings: List[str] = None  # 关键发现

    def __post_init__(self):
        if self.key_findings is None:
            self.key_findings = []


@dataclass
class NextAction:
    """下一步行动对象"""

    action_type: NextActionType  # 行动类型
    reason: str  # 行动原因
    parameters: Dict[str, Any] = None  # 行动参数
    confidence: float = 0.0  # 决策置信度

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class ReflectorBrain:
    """反思脑 — 负责结果评估和策略调整"""

    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        """初始化反思脑"""
        # 评估阈值配置
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
        logger.info("开始评估执行结果")

        if self.llm_service:
            try:
                evaluation = self._evaluate_with_llm(actual_result, expected_intent)
                if evaluation:
                    logger.info(
                        "LLM评估完成: %s (质量评分: %.2f)",
                        evaluation.result.name,
                        evaluation.quality_score,
                    )
                    return evaluation
                logger.info("LLM评估失败，降级到规则评估")
            except Exception as e:
                logger.warning("LLM评估异常，降级到规则评估: %s", e)

        actual_result.get("success", False)
        actual_result.get("data", {})
        actual_result.get("error", "")

        quality_score = self._calculate_quality_score(actual_result, expected_intent)
        result_type = self._determine_result_type(quality_score)
        deviation_analysis = self._analyze_deviation(actual_result, expected_intent)
        key_findings = self._extract_key_findings(actual_result, expected_intent)

        evaluation = Evaluation(
            result=result_type,
            quality_score=quality_score,
            deviation_analysis=deviation_analysis,
            key_findings=key_findings,
        )

        logger.info("评估完成: %s (质量评分: %.2f)", result_type.name, quality_score)
        return evaluation

    def _evaluate_with_llm(
        self, actual_result: Dict[str, Any], expected_intent: Dict[str, Any]
    ) -> Optional[Evaluation]:
        content = ""
        data = actual_result.get("data", {})
        if isinstance(data, dict):
            content = str(data.get("content", ""))[:800]
        elif isinstance(data, str):
            content = data[:800]

        if not content:
            return None

        goal = (
            str(expected_intent.get("goal", ""))[:200]
            if isinstance(expected_intent, dict)
            else ""
        )
        content = sanitize_for_llm(content, 800)
        goal = sanitize_for_llm(goal, 200)

        prompt = f"""评估以下任务执行结果的质量。

用户目标: {goal}
执行结果摘要: {content[:800]}

请返回JSON格式（不要包含其他内容）:
{{
  "quality_score": 0.0-1.0的质量评分,
  "result_level": "EXCELLENT|GOOD|ACCEPTABLE|POOR|FAILURE",
  "deviation_analysis": "偏差分析（一句话）",
  "key_findings": ["发现1", "发现2"],
  "improvement_suggestion": "改进建议（如有）"
}}

评分标准:
- EXCELLENT(0.9+): 完全满足目标，内容充实有深度
- GOOD(0.7-0.9): 基本满足目标，内容质量良好
- ACCEPTABLE(0.5-0.7): 部分满足目标，有改进空间
- POOR(0.3-0.5): 未能满足目标，需要修正
- FAILURE(<0.3): 完全未满足目标"""

        llm_response = call_llm_service(self.llm_service, prompt)
        if not llm_response:
            return None

        try:
            data = extract_json_from_llm(llm_response)
            if not data:
                return None

            quality_score = min(1.0, max(0.0, float(data.get("quality_score", 0.5))))
            result_level_str = data.get("result_level", "ACCEPTABLE")
            result_type = EvaluationResult.ACCEPTABLE
            for rt in EvaluationResult:
                if rt.name == result_level_str:
                    result_type = rt
                    break

            return Evaluation(
                result=result_type,
                quality_score=quality_score,
                deviation_analysis=data.get("deviation_analysis", ""),
                key_findings=data.get("key_findings", []),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("LLM评估结果解析失败: %s", e)
            return None

    def _calculate_quality_score(
        self, actual: Dict[str, Any], expected: Dict[str, Any]
    ) -> float:
        if not isinstance(actual, dict):
            logger.warning("actual_result 不是dict类型: %s", type(actual))
            return 0.0
        if not isinstance(expected, dict):
            logger.warning("expected_intent 不是dict类型: %s", type(expected))
            expected = {}

        score = 0.0
        factors = []

        if actual.get("success", False):
            factors.append(("执行成功", WEIGHT_SUCCESS))

        data = actual.get("data")
        if data is not None:
            if isinstance(data, dict) and len(data) > 0:
                factors.append(("数据完整", WEIGHT_DATA_COMPLETE_DICT))
            elif isinstance(data, (list, str)) and len(data) > 0:
                factors.append(("数据完整", WEIGHT_DATA_COMPLETE_OTHER))

        goal = expected.get("goal", "")
        if goal and isinstance(data, dict):
            result_str = str(data).lower()
            goal_str = goal.lower()
            cn_keywords = re.findall(r"[\u4e00-\u9fff]+", goal_str)
            en_keywords = [w for w in goal_str.split() if re.match(r"[a-zA-Z]", w)]
            keywords = cn_keywords[:5] + en_keywords[:5]
            if not keywords:
                keywords = [goal_str[:20]]
            if any(kw in result_str for kw in keywords):
                factors.append(("结果相关", WEIGHT_RELEVANCE))

        execution_time = actual.get("execution_time", 0)
        if isinstance(execution_time, (int, float)) and 0 < execution_time < 60:
            factors.append(("执行及时", WEIGHT_TIMELY))

        if isinstance(data, dict):
            results = data.get("results", [])
            if isinstance(results, list) and len(results) > 0:
                completed_steps = sum(
                    1
                    for r in results
                    if isinstance(r, dict) and r.get("success", False)
                )
                total_steps = len(results)
                if total_steps > 0 and completed_steps == total_steps:
                    factors.append(("步骤全完成", WEIGHT_ALL_STEPS_DONE))

        score = sum(weight for _, weight in factors)

        if actual.get("error"):
            score = max(0.0, score - PENALTY_ERROR)

        return min(1.0, max(0.0, score))

    def _determine_result_type(self, quality_score: float) -> EvaluationResult:
        """
        根据质量评分确定评估等级

        Args:
            quality_score: 质量评分

        Returns:
            EvaluationResult: 评估结果类型
        """
        if quality_score >= self.evaluation_thresholds[EvaluationResult.EXCELLENT]:
            return EvaluationResult.EXCELLENT
        elif quality_score >= self.evaluation_thresholds[EvaluationResult.GOOD]:
            return EvaluationResult.GOOD
        elif quality_score >= self.evaluation_thresholds[EvaluationResult.ACCEPTABLE]:
            return EvaluationResult.ACCEPTABLE
        elif quality_score >= self.evaluation_thresholds[EvaluationResult.POOR]:
            return EvaluationResult.POOR
        else:
            return EvaluationResult.FAILURE

    def _analyze_deviation(
        self, actual: Dict[str, Any], expected: Dict[str, Any]
    ) -> str:
        """
        分析偏差原因

        Args:
            actual: 实际结果
            expected: 预期意图

        Returns:
            str: 偏差分析描述
        """
        analysis = []

        if not actual.get("success", False):
            error = actual.get("error", "未知错误")
            analysis.append(f"执行失败: {error}")

        data = actual.get("data", {})
        if not data:
            analysis.append("返回数据为空")

        # 检查是否达到预期目标
        goal = expected.get("goal", "")
        if goal:
            analysis.append(f"目标: {goal[:50]}")

        if analysis:
            return "; ".join(analysis)
        return "执行正常，符合预期"

    def _extract_key_findings(
        self, actual: Dict[str, Any], expected: Dict[str, Any]
    ) -> List[str]:
        """
        提取关键发现

        Args:
            actual: 实际结果
            expected: 预期意图

        Returns:
            List[str]: 关键发现列表
        """
        findings = []

        # 检查执行状态
        if actual.get("success", False):
            findings.append("[OK] 执行成功")
        else:
            findings.append("[FAIL] 执行失败")

        # 检查数据完整性
        data = actual.get("data", {})
        if data and isinstance(data, dict):
            findings.append(f"[OK] 返回数据包含 {len(data)} 个字段")

        # 检查执行时间
        execution_time = actual.get("execution_time", 0)
        if execution_time > 0:
            findings.append(f"[TIME] 执行耗时: {execution_time:.2f}秒")

        # 检查错误信息
        error = actual.get("error")
        if error:
            findings.append(f"[WARN] 错误信息: {error}")

        return findings

    def decide_next_action(
        self, evaluation: Evaluation, plan: Optional[Dict[str, Any]] = None
    ) -> NextAction:
        """
        决定下一步行动

        Args:
            evaluation: 评估结果
            plan: 当前执行计划

        Returns:
            NextAction: 下一步行动（类型、参数、原因）
        """
        logger.info("根据评估结果决定下一步行动: %s", evaluation.result.name)

        # 根据评估结果决定行动
        if evaluation.result in [EvaluationResult.EXCELLENT, EvaluationResult.GOOD]:
            # 结果符合预期，继续执行
            action = NextAction(
                action_type=NextActionType.CONTINUE,
                reason=f"执行结果良好（质量评分: {evaluation.quality_score:.2f}），继续下一步",
                confidence=min(CONFIDENCE_CAP, evaluation.quality_score),
            )

        elif evaluation.result == EvaluationResult.ACCEPTABLE:
            # 部分符合预期，检查是否需要调整
            if plan and plan.get("steps"):
                remaining_steps = len(plan["steps"])
                if remaining_steps > 1:
                    # 还有多个步骤，继续执行观察
                    action = NextAction(
                        action_type=NextActionType.CONTINUE,
                        reason=f"结果可接受（质量评分: {evaluation.quality_score:.2f}），继续执行后续步骤",
                        confidence=evaluation.quality_score,
                    )
                else:
                    # 最后一步，建议人工复核
                    action = NextAction(
                        action_type=NextActionType.REVIEW,
                        reason=f"结果仅部分符合预期（质量评分: {evaluation.quality_score:.2f}），建议人工复核",
                        confidence=0.6,
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.CONTINUE,
                    reason=f"结果可接受，继续执行",
                    confidence=evaluation.quality_score,
                )

        elif evaluation.result == EvaluationResult.POOR:
            # 结果较差，尝试重试或调整策略
            if plan:
                retry_count = plan.get("retry_count", 0)
                if retry_count < MAX_RETRY_COUNT:
                    # 重试
                    action = NextAction(
                        action_type=NextActionType.RETRY,
                        reason=f"结果较差（质量评分: {evaluation.quality_score:.2f}），尝试重试（第{retry_count + 1}次）",
                        parameters={"retry_count": retry_count + 1},
                        confidence=0.5,
                    )
                else:
                    # 重试次数已用完，调整策略
                    action = NextAction(
                        action_type=NextActionType.ADJUST_STRATEGY,
                        reason=f"结果较差（质量评分: {evaluation.quality_score:.2f}），重试{retry_count}次仍未成功，需要调整策略",
                        confidence=0.7,
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.RETRY,
                    reason=f"结果较差，尝试重试",
                    confidence=0.5,
                )

        else:  # FAILURE
            # 执行失败
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
                    reason=f"执行失败，无法完成任务",
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

        if any("超时" in finding for finding in evaluation.key_findings):
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
            self.evaluation_thresholds = {
                getattr(EvaluationResult, k): v
                for k, v in data["evaluation_thresholds"].items()
            }

    def express_opinion(
        self,
        context: Dict[str, Any],
        decision_point: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        反思脑对决策点表达意见。

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
        """
        前置预判行动后果（少数派报告模式）
        [S2-T5] 三贤者并行投票用，在执行前预测后果
        保留 evaluate_result() 用于事后评估（二级保障）
        """
        logger.info("开始前置预判行动后果（少数派报告模式）")

        if self.llm_service:
            try:
                opinion = self._predict_with_llm(context, planned_action)
                if opinion:
                    logger.info(
                        "LLM预判完成: %s (置信度: %.2f)",
                        opinion.opinion_type.name,
                        opinion.confidence,
                    )
                    return opinion
                logger.info("LLM预判失败，降级到规则预判")
            except Exception as e:
                logger.warning("LLM预判异常，降级到规则预判: %s", e)

        return self._predict_with_rules(context, planned_action)

    def _predict_with_llm(
        self, context: Dict[str, Any], planned_action: Dict[str, Any]
    ) -> Optional[Opinion]:
        """使用 LLM 预判行动后果"""
        # P2-11 修复：skill_id/action 经过 sanitize_for_llm，防止 prompt injection
        # 原实现仅截断，未过滤注入模式
        skill_id = sanitize_for_llm(str(planned_action.get("skill_id", "")), 100)
        action = sanitize_for_llm(str(planned_action.get("action", "")), 100)
        parameters = planned_action.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {"value": str(parameters)[:200]}
        params_str = sanitize_for_llm(json.dumps(parameters, ensure_ascii=False), 300)

        user_input = str(context.get("user_input", ""))[:200]
        # P1-7 修复：intent/plan 对象序列化为结构化 JSON 而非 str()
        # 原实现 str(intent)[:200] 产生 Python 默认 dataclass 字符串，结构化信息被截断
        intent = context.get("intent", "")
        if intent and not isinstance(intent, str):
            try:
                # 优先使用 dataclasses.asdict 序列化为结构化 JSON
                from dataclasses import asdict, is_dataclass

                if is_dataclass(intent):
                    intent = json.dumps(
                        asdict(intent), ensure_ascii=False, default=str
                    )[:300]
                else:
                    intent = json.dumps(intent, ensure_ascii=False, default=str)[:300]
            except Exception:
                intent = str(intent)[:200]
        else:
            intent = str(intent)[:200]

        plan = context.get("plan", "")
        if plan and not isinstance(plan, str):
            try:
                from dataclasses import asdict, is_dataclass

                if is_dataclass(plan):
                    plan = json.dumps(asdict(plan), ensure_ascii=False, default=str)[
                        :300
                    ]
                else:
                    plan = json.dumps(plan, ensure_ascii=False, default=str)[:300]
            except Exception:
                plan = str(plan)[:200]
        else:
            plan = str(plan)[:200]

        user_input = sanitize_for_llm(user_input, 200)
        intent = sanitize_for_llm(intent, 300)
        plan = sanitize_for_llm(plan, 300)

        prompt = f"""你是反思脑（少数派报告先知），需要在执行前预测行动后果。

用户输入: {user_input}
用户意图: {intent}
计划摘要: {plan}
计划行动:
- 技能ID: {skill_id}
- 动作: {action}
- 参数: {params_str}

请从以下维度预判行动后果：
1. 副作用风险：是否会产生不可控的副作用
2. 可逆性：行动是否可逆
3. 数据安全：是否会损坏或泄露数据
4. 用户意图匹配度：行动是否符合用户意图

请返回JSON格式（不要包含其他内容）:
{{
  "opinion_type": "AGREE|DISAGREE|CONDITIONAL",
  "reasoning": "预判的具体后果描述",
  "confidence": 0.0-1.0,
  "alternative": "替代方案（如有）"
}}

判断标准:
- AGREE: 行动安全可逆，符合用户意图，无副作用风险
- CONDITIONAL: 行动有条件风险，需要满足特定条件
- DISAGREE: 行动有不可逆风险，或严重偏离用户意图"""

        llm_response = call_llm_service(self.llm_service, prompt)
        if not llm_response:
            return None

        try:
            data = extract_json_from_llm(llm_response)
            if not data:
                return None

            opinion_type_str = str(data.get("opinion_type", "CONDITIONAL")).upper()
            opinion_type = OpinionType.CONDITIONAL
            for ot in OpinionType:
                if ot.name == opinion_type_str:
                    opinion_type = ot
                    break

            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))
            reasoning = str(data.get("reasoning", ""))[:500]
            if not reasoning:
                reasoning = "LLM未提供预判理由"
            alternative = data.get("alternative")
            if alternative:
                alternative = str(alternative)[:300]

            return Opinion(
                brain_type="reflector",
                opinion_type=opinion_type,
                reasoning=reasoning,
                confidence=confidence,
                alternative=alternative,
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("LLM预判结果解析失败: %s", e)
            return None

    def _predict_with_rules(
        self, context: Dict[str, Any], planned_action: Dict[str, Any]
    ) -> Opinion:
        """基于规则的简单预判（LLM不可用时降级使用）"""
        skill_id = str(planned_action.get("skill_id", "")).lower()
        action = str(planned_action.get("action", "")).lower()
        parameters = planned_action.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        # 高风险行动关键词（不可逆/有副作用/数据安全风险）
        high_risk_keywords = [
            "send_email",
            "send_notification",
            "email",
            "notify",
            "notification",
            "delete",
            "remove",
            "write_file",
            "run_command",
            "execute_operation",
            "send",
            "publish",
            "submit",
        ]
        # 低风险行动关键词（可逆/只读/无副作用）
        low_risk_keywords = [
            "search",
            "query",
            "analysis",
            "analyze",
            "read",
            "get",
            "list",
            "intent_analysis",
            "output_result",
            "content_generation",
        ]

        combined = (
            f"{skill_id} {action} "
            f"{json.dumps(parameters, ensure_ascii=False).lower()}"
        )

        is_high_risk = any(kw in combined for kw in high_risk_keywords)
        is_low_risk = any(kw in combined for kw in low_risk_keywords)

        if is_high_risk and not is_low_risk:
            reasoning = (
                f"规则预判: 行动[{skill_id}/{action}]属于高风险操作"
                f"（发送/删除/写入类），可能产生不可逆副作用，"
                f"建议人工确认后再执行"
            )
            return Opinion(
                brain_type="reflector",
                opinion_type=OpinionType.CONDITIONAL,
                reasoning=reasoning,
                confidence=0.7,
                alternative="建议增加确认环节或降级为只读操作",
            )

        reasoning = (
            f"规则预判: 行动[{skill_id}/{action}]属于低风险操作"
            f"（查询/分析类），可逆且无副作用，符合用户意图"
        )
        return Opinion(
            brain_type="reflector",
            opinion_type=OpinionType.AGREE,
            reasoning=reasoning,
            confidence=0.6,
        )

    async def predict_consequence_async(
        self, context: Dict[str, Any], planned_action: Dict[str, Any]
    ) -> Opinion:
        """异步版本（并行投票用）"""
        return await asyncio.to_thread(
            self.predict_consequence, context, planned_action
        )
