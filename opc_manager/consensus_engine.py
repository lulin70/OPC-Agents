"""
共识引擎 (ConsensusEngine) - 负责协调三贤者决策

这是三贤者架构的核心协调器：
- 收集三贤者意见
- 解决意见冲突
- 做出最终决策
"""

from typing import Awaitable, Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

CONFIDENCE_WEIGHT_AVG = 0.5
CONFIDENCE_WEIGHT_CONSISTENCY = 0.5
COMPROMISE_CONFIDENCE_FACTOR = 0.8
ESCALATED_CONFIDENCE = 0.5
VETO_CONFIDENCE = 0.7
NO_CONSENSUS_CONFIDENCE = 0.4
VETO_MIN_CONFIDENCE = 0.5


class OpinionType(Enum):
    """意见类型枚举"""

    AGREE = "agree"  # 同意
    DISAGREE = "disagree"  # 不同意
    CONDITIONAL = "conditional"  # 有条件同意
    ABSTAIN = "abstain"  # 弃权


class DecisionType(Enum):
    """决策类型枚举"""

    UNANIMOUS = "unanimous"  # 一致同意
    MAJORITY = "majority"  # 多数同意
    COMPROMISE = "compromise"  # 折中方案
    ESCALATED = "escalated"  # 需要升级决策
    VETOED = "vetoed"  # 被否决


@dataclass
class Opinion:
    """意见对象"""

    brain_type: str  # 贤者类型 (strategist/executor/reflector)
    opinion_type: OpinionType  # 意见类型
    reasoning: str  # 理由
    confidence: float = 1.0  # 置信度
    alternative: Optional[str] = None  # 替代方案


@dataclass
class Decision:
    """决策对象"""

    decision_type: DecisionType  # 决策类型
    approved: bool  # 是否批准
    reasoning: str  # 决策理由
    alternative: Optional[str] = None  # 替代方案
    confidence: float = 0.0  # 决策置信度


class ConsensusEngine:
    """共识引擎 — 协调三贤者决策"""

    MAX_LOG_SIZE = 1000

    def __init__(self) -> None:
        self.veto_enabled = {"strategist": True, "executor": True, "reflector": True}
        self._decision_log: List[Dict[str, Any]] = []
        self._load_decision_log_from_db()

    def collect_opinions(self, opinions: List[Opinion]) -> Decision:
        """
        收集并汇总三贤者意见

        Args:
            opinions: 三个贤者的意见列表

        Returns:
            Decision: 最终决策
        """
        logger.info("开始处理 %s 个意见", len(opinions))

        if not opinions or len(opinions) == 0:
            decision = Decision(
                decision_type=DecisionType.ESCALATED,
                approved=False,
                reasoning="未收到任何意见，无法做出决策",
                confidence=0.0,
            )
            self._log_decision(opinions, decision)
            return decision

        veto_opinion = self._check_veto(opinions)
        if veto_opinion:
            logger.info("检测到否决: %s", veto_opinion.brain_type)
            decision = Decision(
                decision_type=DecisionType.VETOED,
                approved=False,
                reasoning=f"{veto_opinion.brain_type} 行使否决权: {veto_opinion.reasoning}",
                confidence=0.9,
            )
            self._log_decision(opinions, decision)
            return decision

        agree_count = sum(1 for o in opinions if o.opinion_type == OpinionType.AGREE)
        disagree_count = sum(
            1 for o in opinions if o.opinion_type == OpinionType.DISAGREE
        )
        conditional_count = sum(
            1 for o in opinions if o.opinion_type == OpinionType.CONDITIONAL
        )

        logger.info(
            "意见统计: 同意=%s, 不同意=%s, 有条件=%s",
            agree_count,
            disagree_count,
            conditional_count,
        )

        total_voters = len(opinions)

        if agree_count == total_voters:
            decision = Decision(
                decision_type=DecisionType.UNANIMOUS,
                approved=True,
                reasoning="三贤者一致同意",
                confidence=self._calculate_confidence(opinions),
            )
        elif agree_count > total_voters / 2:
            decision = Decision(
                decision_type=DecisionType.MAJORITY,
                approved=True,
                reasoning=f"多数同意 ({agree_count}/{total_voters})",
                confidence=self._calculate_confidence(opinions),
            )
        elif conditional_count > 0 and disagree_count == 0:
            alternatives = [o.alternative for o in opinions if o.alternative]
            decision = Decision(
                decision_type=DecisionType.COMPROMISE,
                approved=True,
                reasoning=f"有条件同意，需满足: {'; '.join(alternatives) if alternatives else '特定条件'}",
                alternative="; ".join(alternatives) if alternatives else None,
                confidence=self._calculate_confidence(opinions)
                * COMPROMISE_CONFIDENCE_FACTOR,
            )
        else:
            decision = Decision(
                decision_type=DecisionType.ESCALATED,
                approved=False,
                reasoning=f"意见分歧较大（同意:{agree_count}, 不同意:{disagree_count}），需要人工介入或重新讨论",
                confidence=ESCALATED_CONFIDENCE,
            )

        self._log_decision(opinions, decision)
        return decision

    async def collect_opinions_async(
        self,
        strategist_coro: Awaitable[Opinion],
        executor_coro: Awaitable[Opinion],
        reflector_coro: Awaitable[Opinion],
    ) -> Decision:
        """
        并行收集三贤者意见（asyncio.gather）[S2-T2]

        三贤者并行投票用：
        - 三脑并行执行，任一异常返回 ABSTAIN
        - 复用 collect_opinions() 同步汇总逻辑

        Args:
            strategist_coro: 策略脑意见协程
            executor_coro: 执行脑意见协程
            reflector_coro: 反思脑预判协程

        Returns:
            Decision: 最终决策
        """
        import asyncio

        results = await asyncio.gather(
            strategist_coro,
            executor_coro,
            reflector_coro,
            return_exceptions=True,
        )
        valid_opinions: List[Opinion] = []
        brain_names = ["strategist", "executor", "reflector"]
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                valid_opinions.append(
                    Opinion(
                        brain_type=brain_names[i],
                        opinion_type=OpinionType.ABSTAIN,
                        reasoning=f"并行投票异常: {result}",
                        confidence=0.0,
                    )
                )
            elif isinstance(result, Opinion):
                # P3-19 修复：防御性检查，确保返回的是 Opinion 实例
                valid_opinions.append(result)
            else:
                # P3-19 修复：非 Opinion 返回值转为 ABSTAIN，避免后续 AttributeError
                logger.warning(
                    "脑 %s 返回非 Opinion 类型: %s，转为 ABSTAIN",
                    brain_names[i],
                    type(result).__name__,
                )
                valid_opinions.append(
                    Opinion(
                        brain_type=brain_names[i],
                        opinion_type=OpinionType.ABSTAIN,
                        reasoning=f"非 Opinion 返回值: {type(result).__name__}",
                        confidence=0.0,
                    )
                )
        return self.collect_opinions(valid_opinions)

    def _check_veto(self, opinions: List[Opinion]) -> Optional[Opinion]:
        """
        检查是否有行使否决权的意见

        Args:
            opinions: 意见列表

        Returns:
            Optional[Opinion]: 行使否决权的意见，如果有的话
        """
        for opinion in opinions:
            if (
                opinion.opinion_type == OpinionType.DISAGREE
                and self.veto_enabled.get(opinion.brain_type, False)
                and opinion.confidence >= VETO_MIN_CONFIDENCE
            ):
                return opinion
        return None

    def _calculate_confidence(self, opinions: List[Opinion]) -> float:
        """
        计算决策置信度

        Args:
            opinions: 意见列表

        Returns:
            float: 置信度 (0.0-1.0)
        """
        if not opinions:
            return 0.0

        # 计算平均置信度
        avg_confidence = sum(o.confidence for o in opinions) / len(opinions)

        # 根据意见一致性调整
        agree_count = sum(1 for o in opinions if o.opinion_type == OpinionType.AGREE)
        consistency = agree_count / len(opinions)

        # 综合置信度 = 平均置信度 * 一致性系数
        confidence = avg_confidence * (
            CONFIDENCE_WEIGHT_AVG + consistency * CONFIDENCE_WEIGHT_CONSISTENCY
        )

        return min(1.0, max(0.0, confidence))

    def resolve_conflict(self, opinions: List[Opinion]) -> Decision:
        """
        解决意见冲突

        Args:
            opinions: 存在冲突的意见列表

        Returns:
            Decision: 解决后的决策
        """
        logger.info("尝试解决意见冲突")

        # 分析冲突原因
        conflict_analysis = self._analyze_conflict(opinions)
        logger.info("冲突分析: %s", conflict_analysis)

        # 尝试找到折中方案
        compromise = self._find_compromise(opinions)
        if compromise:
            return Decision(
                decision_type=DecisionType.COMPROMISE,
                approved=True,
                reasoning=f"达成折中方案: {compromise}",
                alternative=compromise,
                confidence=VETO_CONFIDENCE,
            )

        # 无法达成折中，建议升级
        return Decision(
            decision_type=DecisionType.ESCALATED,
            approved=False,
            reasoning=f"无法自动解决冲突: {conflict_analysis}。建议人工介入。",
            confidence=NO_CONSENSUS_CONFIDENCE,
        )

    def _analyze_conflict(self, opinions: List[Opinion]) -> str:
        """
        分析冲突原因

        Args:
            opinions: 意见列表

        Returns:
            str: 冲突分析描述
        """
        reasons = []

        # 收集不同意的理由
        for opinion in opinions:
            if opinion.opinion_type == OpinionType.DISAGREE:
                reasons.append(f"{opinion.brain_type}: {opinion.reasoning}")

        if reasons:
            return "；".join(reasons)
        return "未知原因"

    def _find_compromise(self, opinions: List[Opinion]) -> Optional[str]:
        """
        尝试找到折中方案

        Args:
            opinions: 意见列表

        Returns:
            Optional[str]: 折中方案，如果找到的话
        """
        # 收集所有替代方案
        alternatives = []
        for opinion in opinions:
            if opinion.alternative:
                alternatives.append(opinion.alternative)

        if alternatives:
            from collections import Counter

            alt_counts = Counter(alternatives)
            best_alt, count = alt_counts.most_common(1)[0]
            if count > 1:
                return best_alt
            return alternatives[0]

        # 尝试生成折中方案
        agree_opinions = [o for o in opinions if o.opinion_type == OpinionType.AGREE]
        disagree_opinions = [
            o for o in opinions if o.opinion_type == OpinionType.DISAGREE
        ]

        if agree_opinions and disagree_opinions:
            # 尝试找到双方都能接受的方案
            return f"综合考虑：{agree_opinions[0].reasoning}，同时考虑{disagree_opinions[0].reasoning}"

        return None

    def propose_revision(self, opinions: List[Opinion]) -> Dict[str, Any]:
        """
        根据意见提出修订建议

        Args:
            opinions: 意见列表

        Returns:
            Dict[str, Any]: 修订建议
        """
        suggestions: dict[str, list[dict[str, Any]]] = {
            "suggestions": [],
            "next_steps": [],
        }

        # 分析意见
        disagree_opinions = [
            o for o in opinions if o.opinion_type == OpinionType.DISAGREE
        ]
        conditional_opinions = [
            o for o in opinions if o.opinion_type == OpinionType.CONDITIONAL
        ]

        # 根据不同意见提出建议
        for opinion in disagree_opinions:
            suggestions["suggestions"].append(
                {
                    "from": opinion.brain_type,
                    "issue": opinion.reasoning,
                    "alternative": opinion.alternative,
                }
            )

        # 根据有条件同意提出条件
        for opinion in conditional_opinions:
            if opinion.alternative:
                suggestions["next_steps"].append(
                    {
                        "condition": opinion.alternative,
                        "responsible": opinion.brain_type,
                    }
                )

        return suggestions

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "consensus_engine", "veto_enabled": self.veto_enabled}

    def from_dict(self, data: Dict[str, Any]) -> None:
        if "veto_enabled" in data:
            self.veto_enabled = data["veto_enabled"]

    def _log_decision(self, opinions: List[Opinion], decision: Decision) -> None:
        import time as _time
        import json as _json

        entry = {
            "timestamp": _time.time(),
            "opinion_count": len(opinions),
            "decision_type": decision.decision_type.value,
            "approved": decision.approved,
            "confidence": decision.confidence,
        }
        self._decision_log.append(entry)
        if len(self._decision_log) > self.MAX_LOG_SIZE:
            self._decision_log = self._decision_log[-self.MAX_LOG_SIZE :]
        try:
            from opc_manager.data_manager import execute_write, init_db, gen_id

            init_db()
            execute_write(
                "INSERT INTO consensus_decisions "
                "(id, timestamp, opinion_count, decision_type, approved, confidence, detail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    gen_id(),
                    entry["timestamp"],
                    entry["opinion_count"],
                    entry["decision_type"],
                    int(entry["approved"]),
                    entry["confidence"],
                    _json.dumps(entry, ensure_ascii=False),
                ),
            )
        except Exception as e:
            logger.warning("决策日志持久化失败: %s", e)

    def _load_decision_log_from_db(self) -> None:
        try:
            from opc_manager.data_manager import execute_query, init_db

            init_db()
            rows = execute_query(
                "SELECT timestamp, opinion_count, decision_type, approved, confidence "
                "FROM consensus_decisions ORDER BY timestamp DESC LIMIT ?",
                (self.MAX_LOG_SIZE,),
            )
            if rows:
                self._decision_log = [
                    {
                        "timestamp": row["timestamp"],
                        "opinion_count": row["opinion_count"],
                        "decision_type": row["decision_type"],
                        "approved": bool(row["approved"]),
                        "confidence": row["confidence"],
                    }
                    for row in reversed(rows)
                ]
        except Exception as e:
            logger.debug("加载历史决策日志失败(表可能不存在): %s", e)

    def get_decision_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._decision_log[-limit:]
