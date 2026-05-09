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
import logging

logger = logging.getLogger(__name__)

WEIGHT_SUCCESS = 0.3
WEIGHT_DATA_COMPLETE_DICT = 0.3
WEIGHT_DATA_COMPLETE_OTHER = 0.25
WEIGHT_RELEVANCE = 0.2
WEIGHT_TIMELY = 0.1
WEIGHT_ALL_STEPS_DONE = 0.1
PENALTY_ERROR = 0.3
MAX_RETRY_COUNT = 3
CONFIDENCE_CAP = 0.95
IMPROVEMENT_QUALITY_THRESHOLD = 0.7


class EvaluationResult(Enum):
    """评估结果类型枚举"""
    EXCELLENT = "excellent"       # 优秀（完全符合预期）
    GOOD = "good"                 # 良好（基本符合预期）
    ACCEPTABLE = "acceptable"     # 可接受（部分符合预期）
    POOR = "poor"                 # 差（不符合预期）
    FAILURE = "failure"           # 失败（完全不符合预期）


class NextActionType(Enum):
    """下一步行动类型枚举"""
    CONTINUE = "continue"           # 继续执行（结果符合预期）
    RETRY = "retry"                 # 重试（执行失败，可重试）
    ADJUST_STRATEGY = "adjust_strategy"  # 调整策略（路径错误）
    ABANDON = "abandon"             # 放弃（无法完成）
    REVIEW = "review"               # 人工复核（需要人工介入）


class CorrectionStrategy(Enum):
    """修正策略类型枚举"""
    RETRY = "retry"                           # 重试当前步骤
    SEARCH_AND_RETRY = "search_and_retry"     # 补充搜索后重试
    SWITCH_SKILL = "switch_skill"             # 换技能执行
    DEGRADE = "degrade"                       # 降级到规则引擎


QUALITY_THRESHOLD_CORRECTION = 0.6
MAX_CORRECTION_ATTEMPTS = 2
PLACEHOLDER_PATTERNS = ["[待补充]", "[占位符]", "[TODO]", "[placeholder]", "[待完善]", "[TBD]"]


@dataclass
class Evaluation:
    """评估结果对象"""
    result: EvaluationResult        # 评估结果类型
    quality_score: float            # 质量评分 (0.0-1.0)
    deviation_analysis: str         # 偏差分析
    key_findings: List[str] = None  # 关键发现
    
    def __post_init__(self):
        if self.key_findings is None:
            self.key_findings = []


@dataclass
class NextAction:
    """下一步行动对象"""
    action_type: NextActionType     # 行动类型
    reason: str                     # 行动原因
    parameters: Dict[str, Any] = None  # 行动参数
    confidence: float = 0.0         # 决策置信度
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class ReflectorBrain:
    """反思脑 — 负责结果评估和策略调整"""

    def __init__(self):
        """初始化反思脑"""
        # 评估阈值配置
        self.evaluation_thresholds = {
            EvaluationResult.EXCELLENT: 0.9,
            EvaluationResult.GOOD: 0.7,
            EvaluationResult.ACCEPTABLE: 0.5,
            EvaluationResult.POOR: 0.3,
            EvaluationResult.FAILURE: 0.0
        }

    def evaluate_result(self, actual_result: Dict[str, Any], 
                       expected_intent: Dict[str, Any]) -> Evaluation:
        """
        评估执行结果
        
        Args:
            actual_result: 实际执行结果
            expected_intent: 预期意图
        
        Returns:
            Evaluation: 评估结果（符合度、质量评分、偏差分析）
        """
        logger.info("开始评估执行结果")
        
        # 提取关键信息
        success = actual_result.get("success", False)
        data = actual_result.get("data", {})
        error = actual_result.get("error", "")
        
        # 计算质量评分
        quality_score = self._calculate_quality_score(actual_result, expected_intent)
        
        # 确定评估等级
        result_type = self._determine_result_type(quality_score)
        
        # 分析偏差
        deviation_analysis = self._analyze_deviation(actual_result, expected_intent)
        
        # 提取关键发现
        key_findings = self._extract_key_findings(actual_result, expected_intent)
        
        evaluation = Evaluation(
            result=result_type,
            quality_score=quality_score,
            deviation_analysis=deviation_analysis,
            key_findings=key_findings
        )
        
        logger.info(f"评估完成: {result_type.name} (质量评分: {quality_score:.2f})")
        return evaluation

    def _calculate_quality_score(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> float:
        if not isinstance(actual, dict):
            logger.warning(f"actual_result 不是dict类型: {type(actual)}")
            return 0.0
        if not isinstance(expected, dict):
            logger.warning(f"expected_intent 不是dict类型: {type(expected)}")
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
            if any(keyword in result_str for keyword in goal_str.split()[:5]):
                factors.append(("结果相关", WEIGHT_RELEVANCE))
        
        execution_time = actual.get("execution_time", 0)
        if isinstance(execution_time, (int, float)) and 0 < execution_time < 60:
            factors.append(("执行及时", WEIGHT_TIMELY))
        
        if isinstance(data, dict):
            results = data.get("results", [])
            if isinstance(results, list) and len(results) > 0:
                completed_steps = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
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

    def _analyze_deviation(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> str:
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

    def _extract_key_findings(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> List[str]:
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
            findings.append("✓ 执行成功")
        else:
            findings.append("✗ 执行失败")
        
        # 检查数据完整性
        data = actual.get("data", {})
        if data and isinstance(data, dict):
            findings.append(f"✓ 返回数据包含 {len(data)} 个字段")
        
        # 检查执行时间
        execution_time = actual.get("execution_time", 0)
        if execution_time > 0:
            findings.append(f"⏱️ 执行耗时: {execution_time:.2f}秒")
        
        # 检查错误信息
        error = actual.get("error")
        if error:
            findings.append(f"⚠️ 错误信息: {error}")
        
        return findings

    def decide_next_action(self, evaluation: Evaluation, 
                          plan: Optional[Dict[str, Any]] = None) -> NextAction:
        """
        决定下一步行动
        
        Args:
            evaluation: 评估结果
            plan: 当前执行计划
        
        Returns:
            NextAction: 下一步行动（类型、参数、原因）
        """
        logger.info(f"根据评估结果决定下一步行动: {evaluation.result.name}")
        
        # 根据评估结果决定行动
        if evaluation.result in [EvaluationResult.EXCELLENT, EvaluationResult.GOOD]:
            # 结果符合预期，继续执行
            action = NextAction(
                action_type=NextActionType.CONTINUE,
                reason=f"执行结果良好（质量评分: {evaluation.quality_score:.2f}），继续下一步",
                confidence=min(CONFIDENCE_CAP, evaluation.quality_score)
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
                        confidence=evaluation.quality_score
                    )
                else:
                    # 最后一步，建议人工复核
                    action = NextAction(
                        action_type=NextActionType.REVIEW,
                        reason=f"结果仅部分符合预期（质量评分: {evaluation.quality_score:.2f}），建议人工复核",
                        confidence=0.6
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.CONTINUE,
                    reason=f"结果可接受，继续执行",
                    confidence=evaluation.quality_score
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
                        confidence=0.5
                    )
                else:
                    # 重试次数已用完，调整策略
                    action = NextAction(
                        action_type=NextActionType.ADJUST_STRATEGY,
                        reason=f"结果较差（质量评分: {evaluation.quality_score:.2f}），重试{retry_count}次仍未成功，需要调整策略",
                        confidence=0.7
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.RETRY,
                    reason=f"结果较差，尝试重试",
                    confidence=0.5
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
                        confidence=0.4
                    )
                else:
                    action = NextAction(
                        action_type=NextActionType.ABANDON,
                        reason=f"执行失败（质量评分: {evaluation.quality_score:.2f}），重试{retry_count}次仍未成功，无法完成任务",
                        confidence=0.9
                    )
            else:
                action = NextAction(
                    action_type=NextActionType.ABANDON,
                    reason=f"执行失败，无法完成任务",
                    confidence=0.8
                )
        
        logger.info(f"决定下一步行动: {action.action_type.name}")
        return action

    def suggest_improvement(self, evaluation: Evaluation, 
                           plan: Dict[str, Any]) -> List[str]:
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

    def suggest_correction_strategy(self, evaluation: Evaluation,
                                    execution_results: List[Dict],
                                    correction_count: int = 0) -> Optional[CorrectionStrategy]:
        if evaluation.quality_score >= QUALITY_THRESHOLD_CORRECTION:
            return None

        if correction_count >= MAX_CORRECTION_ATTEMPTS:
            logger.info(f"修正次数已达上限({MAX_CORRECTION_ATTEMPTS})，标记需人工复核")
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

        logger.info(f"建议修正策略: {strategy.value} (质量评分: {evaluation.quality_score:.2f}, 修正次数: {correction_count})")
        return strategy

    def _check_placeholders(self, execution_results: List[Dict]) -> bool:
        for result in execution_results:
            data = result.get("data")
            if not data:
                continue
            text = ""
            if isinstance(data, dict):
                text = str(data.get("content", "")) + str(data.get("analysis_result", ""))
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
            "evaluation_thresholds": {k.name: v for k, v in self.evaluation_thresholds.items()}
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        从字典恢复反思脑状态
        
        Args:
            data: 状态字典
        """
        if "evaluation_thresholds" in data:
            self.evaluation_thresholds = {
                getattr(EvaluationResult, k): v 
                for k, v in data["evaluation_thresholds"].items()
            }
