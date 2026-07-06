"""ConsequencePredictor - 后果预判服务

[P2-15] Step 2: 从 ReflectorBrain 抽出的后果预判职责。
负责在执行前预测行动后果（少数派报告模式），用于三贤者并行投票。
"""

from typing import Any, Dict, Optional
import asyncio
import json
import logging

from opc_manager.utils import (
    extract_json_from_llm,
    sanitize_for_llm,
    call_llm_service,
)
from .consensus_engine import Opinion, OpinionType

logger = logging.getLogger(__name__)


class ConsequencePredictor:
    """后果预判器 — 在执行前预测行动后果。

    少数派报告模式：执行前预判，与 evaluate_result（事后评估）形成二级保障。
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service

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

                if is_dataclass(intent) and not isinstance(intent, type):
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

                if is_dataclass(plan) and not isinstance(plan, type):
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
