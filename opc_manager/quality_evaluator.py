"""QualityEvaluator - 执行结果质量评估服务

[P2-15] Step 4: 从 ReflectorBrain 抽出的质量评估职责。
负责评估执行结果质量、计算质量评分、分析偏差、提取关键发现。
"""

from typing import Any, Dict, List, Optional
import json
import re
import logging

from opc_manager.utils import (
    extract_json_from_llm,
    sanitize_for_llm,
    call_llm_service,
)
from .reflector_models import EvaluationResult, Evaluation

logger = logging.getLogger(__name__)

WEIGHT_SUCCESS = 0.3
WEIGHT_DATA_COMPLETE_DICT = 0.25
WEIGHT_DATA_COMPLETE_OTHER = 0.2
WEIGHT_RELEVANCE = 0.25
WEIGHT_TIMELY = 0.05
WEIGHT_ALL_STEPS_DONE = 0.15
PENALTY_ERROR = 0.3


class QualityEvaluator:
    """质量评估器 — 评估执行结果质量。

    支持双路径：LLM 评估（结构化 JSON）+ 规则评估（加权评分）。
    """

    def __init__(self, llm_service=None, evaluation_thresholds: Optional[Dict] = None):
        self.llm_service = llm_service
        if evaluation_thresholds is not None:
            self.evaluation_thresholds = evaluation_thresholds
        else:
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
        """根据质量评分确定评估等级。"""
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
        """分析偏差原因。"""
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
        """提取关键发现。"""
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
