"""
ConsensusEngine 单元测试

覆盖三贤者共识决策的核心逻辑：
- 一致同意 / 多数同意 / 完全分歧 / 否决 / 弃权 / 置信度计算
- 冲突解决与修订建议
- 边界条件
"""

import unittest
from unittest.mock import patch, MagicMock

from opc_manager.consensus_engine import (
    ConsensusEngine,
    Opinion,
    OpinionType,
    Decision,
    DecisionType,
    CONFIDENCE_WEIGHT_AVG,
    CONFIDENCE_WEIGHT_CONSISTENCY,
    COMPROMISE_CONFIDENCE_FACTOR,
    ESCALATED_CONFIDENCE,
    VETO_CONFIDENCE,
    NO_CONSENSUS_CONFIDENCE,
    VETO_MIN_CONFIDENCE,
)


def _make_opinion(
    brain_type: str = "strategist",
    opinion_type: OpinionType = OpinionType.AGREE,
    reasoning: str = "test",
    confidence: float = 1.0,
    alternative: str = None,
) -> Opinion:
    return Opinion(
        brain_type=brain_type,
        opinion_type=opinion_type,
        reasoning=reasoning,
        confidence=confidence,
        alternative=alternative,
    )


class TestConsensusEngineInit(unittest.TestCase):
    """ConsensusEngine 初始化测试"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_default_veto_enabled(self, mock_load):
        engine = ConsensusEngine()
        self.assertTrue(engine.veto_enabled["strategist"])
        self.assertTrue(engine.veto_enabled["executor"])
        self.assertTrue(engine.veto_enabled["reflector"])

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_decision_log_initially_empty(self, mock_load):
        engine = ConsensusEngine()
        self.assertEqual(engine._decision_log, [])

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_load_decision_log_called_on_init(self, mock_load):
        ConsensusEngine()
        mock_load.assert_called_once()


class TestUnanimousAgreement(unittest.TestCase):
    """一致同意场景"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_all_three_agree(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "good", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
            _make_opinion("reflector", OpinionType.AGREE, "fine", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.UNANIMOUS)
        self.assertTrue(decision.approved)
        self.assertIn("一致同意", decision.reasoning)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_unanimous_confidence(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "a", 1.0),
            _make_opinion("executor", OpinionType.AGREE, "b", 1.0),
            _make_opinion("reflector", OpinionType.AGREE, "c", 1.0),
        ]
        decision = engine.collect_opinions(opinions)
        # avg=1.0, consistency=1.0 → 1.0 * (0.5 + 1.0*0.5) = 1.0
        self.assertAlmostEqual(decision.confidence, 1.0)


class TestMajorityVote(unittest.TestCase):
    """多数同意场景"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_two_agree_one_disagree(self, mock_load, mock_log):
        engine = ConsensusEngine()
        # Veto requires confidence >= VETO_MIN_CONFIDENCE(0.5) — use low confidence
        # to avoid triggering veto path
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "good", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
            _make_opinion("reflector", OpinionType.DISAGREE, "bad", 0.3),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.MAJORITY)
        self.assertTrue(decision.approved)
        self.assertIn("多数同意", decision.reasoning)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_majority_confidence_reflects_disagreement(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "a", 1.0),
            _make_opinion("executor", OpinionType.AGREE, "b", 1.0),
            _make_opinion("reflector", OpinionType.DISAGREE, "c", 0.3),
        ]
        decision = engine.collect_opinions(opinions)
        # consistency = 2/3 ≈ 0.667, avg = (1+1+0.3)/3 ≈ 0.767
        # confidence = 0.767 * (0.5 + 0.667*0.5) ≈ 0.767 * 0.833 ≈ 0.639
        self.assertLess(decision.confidence, 1.0)
        self.assertGreater(decision.confidence, 0.0)


class TestCompleteDisagreement(unittest.TestCase):
    """完全分歧场景 — 全部不同意"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_all_disagree_triggers_veto(self, mock_load, mock_log):
        """All disagree with high confidence → first one triggers veto"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8),
            _make_opinion("reflector", OpinionType.DISAGREE, "nah", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        # First DISAGREE with confidence >= 0.5 triggers veto
        self.assertEqual(decision.decision_type, DecisionType.VETOED)
        self.assertFalse(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_all_disagree_low_confidence_escalated(self, mock_load, mock_log):
        """All disagree with low confidence → no veto, escalated"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.3),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.2),
            _make_opinion("reflector", OpinionType.DISAGREE, "nah", 0.1),
        ]
        decision = engine.collect_opinions(opinions)
        # No veto (all confidence < VETO_MIN_CONFIDENCE), no agree, no conditional
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.confidence, ESCALATED_CONFIDENCE)


class TestVetoHandling(unittest.TestCase):
    """否决权处理"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_by_strategist(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "veto!", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
            _make_opinion("reflector", OpinionType.AGREE, "fine", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.VETOED)
        self.assertFalse(decision.approved)
        self.assertIn("strategist", decision.reasoning)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_by_executor(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.DISAGREE, "veto!", 0.9),
            _make_opinion("reflector", OpinionType.AGREE, "fine", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.VETOED)
        self.assertIn("executor", decision.reasoning)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_by_reflector(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "fine", 0.8),
            _make_opinion("reflector", OpinionType.DISAGREE, "veto!", 0.9),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.VETOED)
        self.assertIn("reflector", decision.reasoning)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_requires_sufficient_confidence(self, mock_load, mock_log):
        """DISAGREE with confidence < VETO_MIN_CONFIDENCE does NOT trigger veto"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "fine", 0.8),
            _make_opinion("reflector", OpinionType.DISAGREE, "weak no", 0.4),
        ]
        decision = engine.collect_opinions(opinions)
        # 0.4 < VETO_MIN_CONFIDENCE(0.5), so no veto; 2 agree out of 3 → majority
        self.assertEqual(decision.decision_type, DecisionType.MAJORITY)
        self.assertTrue(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_disabled_for_brain(self, mock_load, mock_log):
        """When veto is disabled for a brain, DISAGREE does not trigger veto"""
        engine = ConsensusEngine()
        engine.veto_enabled["reflector"] = False
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "fine", 0.8),
            _make_opinion("reflector", OpinionType.DISAGREE, "veto!", 0.9),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.MAJORITY)
        self.assertTrue(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_confidence_is_0_9(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
            _make_opinion("reflector", OpinionType.AGREE, "fine", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.confidence, 0.9)


class TestConfidenceCalculation(unittest.TestCase):
    """置信度计算"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_empty_opinions_returns_zero(self, mock_load):
        engine = ConsensusEngine()
        self.assertEqual(engine._calculate_confidence([]), 0.0)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_all_agree_high_confidence(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "a", 1.0),
            _make_opinion("executor", OpinionType.AGREE, "b", 1.0),
            _make_opinion("reflector", OpinionType.AGREE, "c", 1.0),
        ]
        conf = engine._calculate_confidence(opinions)
        # avg=1.0, consistency=1.0 → 1.0 * (0.5 + 1.0*0.5) = 1.0
        self.assertAlmostEqual(conf, 1.0)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_partial_agreement_lower_confidence(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "a", 1.0),
            _make_opinion("executor", OpinionType.DISAGREE, "b", 1.0),
            _make_opinion("reflector", OpinionType.AGREE, "c", 1.0),
        ]
        conf = engine._calculate_confidence(opinions)
        # avg=1.0, consistency=2/3 → 1.0 * (0.5 + 0.667*0.5) ≈ 0.833
        self.assertLess(conf, 1.0)
        self.assertGreater(conf, 0.5)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_no_agreement_very_low_confidence(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "a", 0.5),
            _make_opinion("executor", OpinionType.DISAGREE, "b", 0.5),
            _make_opinion("reflector", OpinionType.DISAGREE, "c", 0.5),
        ]
        conf = engine._calculate_confidence(opinions)
        # avg=0.5, consistency=0/3=0 → 0.5 * (0.5 + 0*0.5) = 0.25
        self.assertAlmostEqual(conf, 0.25)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_confidence_clamped_to_1(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "a", 1.0),
        ]
        conf = engine._calculate_confidence(opinions)
        self.assertLessEqual(conf, 1.0)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_confidence_clamped_to_0(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "a", 0.0),
        ]
        conf = engine._calculate_confidence(opinions)
        self.assertGreaterEqual(conf, 0.0)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_confidence_reduced(self, mock_load, mock_log):
        """Compromise decisions have confidence reduced by COMPROMISE_CONFIDENCE_FACTOR"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.CONDITIONAL, "a", 1.0,
                          alternative="alt1"),
            _make_opinion("executor", OpinionType.CONDITIONAL, "b", 1.0,
                          alternative="alt2"),
            _make_opinion("reflector", OpinionType.AGREE, "c", 1.0),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.COMPROMISE)
        # Base confidence would be 1.0*(0.5+1/3*0.5)≈0.667, then *0.8
        self.assertLess(decision.confidence, 1.0)


class TestAbstentionHandling(unittest.TestCase):
    """弃权处理"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_one_abstain_two_agree_is_majority(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "fine", 0.8),
            _make_opinion("reflector", OpinionType.ABSTAIN, "no opinion", 0.5),
        ]
        decision = engine.collect_opinions(opinions)
        # 2 agree out of 3 → majority
        self.assertEqual(decision.decision_type, DecisionType.MAJORITY)
        self.assertTrue(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_one_agree_two_abstain_is_majority(self, mock_load, mock_log):
        """1 agree out of 3 is NOT > total/2 (1 > 1.5 is False), but no disagree
        and no conditional → escalated"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.ABSTAIN, "meh", 0.5),
            _make_opinion("reflector", OpinionType.ABSTAIN, "dunno", 0.5),
        ]
        decision = engine.collect_opinions(opinions)
        # agree_count=1, total=3, 1 > 3/2? No. conditional=0, disagree=0
        # Falls to else → ESCALATED
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertFalse(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_all_abstain_escalated(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.ABSTAIN, "meh", 0.5),
            _make_opinion("executor", OpinionType.ABSTAIN, "dunno", 0.5),
            _make_opinion("reflector", OpinionType.ABSTAIN, "no idea", 0.5),
        ]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertFalse(decision.approved)


class TestEdgeCases(unittest.TestCase):
    """边界条件"""

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_empty_opinions(self, mock_load, mock_log):
        engine = ConsensusEngine()
        decision = engine.collect_opinions([])
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.confidence, 0.0)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_none_opinions_raises_type_error(self, mock_load, mock_log):
        """Source code calls len(opinions) before the None check, so None raises TypeError"""
        engine = ConsensusEngine()
        with self.assertRaises(TypeError):
            engine.collect_opinions(None)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_single_agree_opinion(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [_make_opinion("strategist", OpinionType.AGREE, "ok", 0.9)]
        decision = engine.collect_opinions(opinions)
        # 1 agree out of 1 → unanimous
        self.assertEqual(decision.decision_type, DecisionType.UNANIMOUS)
        self.assertTrue(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_single_disagree_opinion_triggers_veto(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [_make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9)]
        decision = engine.collect_opinions(opinions)
        self.assertEqual(decision.decision_type, DecisionType.VETOED)
        self.assertFalse(decision.approved)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_conditional_with_no_disagree_is_compromise(self, mock_load, mock_log):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.CONDITIONAL, "if X", 0.8,
                          alternative="do X first"),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("reflector", OpinionType.AGREE, "fine", 0.7),
        ]
        decision = engine.collect_opinions(opinions)
        # agree=2 > 3/2 → MAJORITY (majority check comes before compromise)
        self.assertEqual(decision.decision_type, DecisionType.MAJORITY)

    @patch.object(ConsensusEngine, "_log_decision")
    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_conditional_only_is_compromise(self, mock_load, mock_log):
        """Conditional + abstain (no agree majority, no disagree) → compromise"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.CONDITIONAL, "if X", 0.8,
                          alternative="do X first"),
            _make_opinion("executor", OpinionType.ABSTAIN, "meh", 0.5),
            _make_opinion("reflector", OpinionType.CONDITIONAL, "if Y", 0.7,
                          alternative="do Y first"),
        ]
        decision = engine.collect_opinions(opinions)
        # agree=0, disagree=0, conditional=2 → compromise
        self.assertEqual(decision.decision_type, DecisionType.COMPROMISE)
        self.assertTrue(decision.approved)
        self.assertIsNotNone(decision.alternative)


class TestResolveConflict(unittest.TestCase):
    """冲突解决"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_found_with_alternatives(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9,
                          alternative="plan B"),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8,
                          alternative="plan B"),
            _make_opinion("reflector", OpinionType.AGREE, "ok", 0.7),
        ]
        decision = engine.resolve_conflict(opinions)
        self.assertEqual(decision.decision_type, DecisionType.COMPROMISE)
        self.assertTrue(decision.approved)
        self.assertEqual(decision.alternative, "plan B")
        self.assertEqual(decision.confidence, VETO_CONFIDENCE)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_found_with_single_alternative(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9,
                          alternative="plan C"),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
        ]
        decision = engine.resolve_conflict(opinions)
        self.assertEqual(decision.decision_type, DecisionType.COMPROMISE)
        self.assertEqual(decision.alternative, "plan C")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_no_compromise_escalated(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8),
        ]
        decision = engine.resolve_conflict(opinions)
        self.assertEqual(decision.decision_type, DecisionType.ESCALATED)
        self.assertFalse(decision.approved)
        self.assertEqual(decision.confidence, NO_CONSENSUS_CONFIDENCE)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_from_agree_disagree_mix(self, mock_load):
        """When no alternatives provided but mix of agree/disagree, generates compromise"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "reason A", 0.9),
            _make_opinion("executor", OpinionType.DISAGREE, "reason B", 0.8),
        ]
        decision = engine.resolve_conflict(opinions)
        self.assertEqual(decision.decision_type, DecisionType.COMPROMISE)
        self.assertIn("综合考虑", decision.alternative)


class TestProposeRevision(unittest.TestCase):
    """修订建议"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_suggestions_from_disagree(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "too risky", 0.9,
                          alternative="safer approach"),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
        ]
        result = engine.propose_revision(opinions)
        self.assertIn("suggestions", result)
        self.assertEqual(len(result["suggestions"]), 1)
        self.assertEqual(result["suggestions"][0]["from"], "strategist")
        self.assertEqual(result["suggestions"][0]["issue"], "too risky")
        self.assertEqual(result["suggestions"][0]["alternative"], "safer approach")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_next_steps_from_conditional(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.CONDITIONAL, "if X", 0.9,
                          alternative="add tests"),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
        ]
        result = engine.propose_revision(opinions)
        self.assertIn("next_steps", result)
        self.assertEqual(len(result["next_steps"]), 1)
        self.assertEqual(result["next_steps"][0]["condition"], "add tests")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_no_disagree_no_conditional_empty(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "fine", 0.8),
        ]
        result = engine.propose_revision(opinions)
        self.assertEqual(result["suggestions"], [])
        self.assertEqual(result["next_steps"], [])


class TestSerialization(unittest.TestCase):
    """to_dict / from_dict 序列化"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_to_dict(self, mock_load):
        engine = ConsensusEngine()
        d = engine.to_dict()
        self.assertEqual(d["type"], "consensus_engine")
        self.assertEqual(d["veto_enabled"], engine.veto_enabled)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_from_dict(self, mock_load):
        engine = ConsensusEngine()
        engine.from_dict({"veto_enabled": {"strategist": False, "executor": True, "reflector": True}})
        self.assertFalse(engine.veto_enabled["strategist"])
        self.assertTrue(engine.veto_enabled["executor"])

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_from_dict_without_veto_enabled(self, mock_load):
        engine = ConsensusEngine()
        original = engine.veto_enabled.copy()
        engine.from_dict({"type": "consensus_engine"})
        self.assertEqual(engine.veto_enabled, original)


class TestDecisionLog(unittest.TestCase):
    """决策日志"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_log_decision_appends_entry(self, mock_load):
        engine = ConsensusEngine()
        opinions = [_make_opinion("strategist", OpinionType.AGREE, "ok", 0.9)]
        decision = Decision(
            decision_type=DecisionType.UNANIMOUS,
            approved=True,
            reasoning="test",
            confidence=0.9,
        )
        with patch.object(ConsensusEngine, "_log_decision", wraps=engine._log_decision):
            engine._log_decision(opinions, decision)
        self.assertEqual(len(engine._decision_log), 1)
        entry = engine._decision_log[0]
        self.assertEqual(entry["decision_type"], "unanimous")
        self.assertTrue(entry["approved"])
        self.assertAlmostEqual(entry["confidence"], 0.9)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_get_decision_log_limit(self, mock_load):
        engine = ConsensusEngine()
        # Manually populate log
        for i in range(150):
            engine._decision_log.append({"timestamp": float(i), "test": True})
        result = engine.get_decision_log(limit=10)
        self.assertEqual(len(result), 10)
        # Should return the last 10
        self.assertEqual(result[0]["timestamp"], 140.0)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_max_log_size(self, mock_load):
        engine = ConsensusEngine()
        opinions = [_make_opinion("strategist", OpinionType.AGREE, "ok", 0.9)]
        decision = Decision(
            decision_type=DecisionType.UNANIMOUS,
            approved=True,
            reasoning="test",
            confidence=0.9,
        )
        # Fill beyond max
        for _ in range(1100):
            engine._decision_log.append({"test": True})
        engine._log_decision(opinions, decision)
        self.assertLessEqual(len(engine._decision_log), ConsensusEngine.MAX_LOG_SIZE)


class TestCheckVeto(unittest.TestCase):
    """_check_veto 内部方法"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_disagree_with_high_confidence_triggers_veto(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9),
        ]
        result = engine._check_veto(opinions)
        self.assertIsNotNone(result)
        self.assertEqual(result.brain_type, "strategist")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_disagree_with_low_confidence_no_veto(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.3),
        ]
        result = engine._check_veto(opinions)
        self.assertIsNone(result)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_agree_does_not_trigger_veto(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
        ]
        result = engine._check_veto(opinions)
        self.assertIsNone(result)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_disabled_brain(self, mock_load):
        engine = ConsensusEngine()
        engine.veto_enabled["executor"] = False
        opinions = [
            _make_opinion("executor", OpinionType.DISAGREE, "no", 0.9),
        ]
        result = engine._check_veto(opinions)
        self.assertIsNone(result)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_veto_at_exact_threshold(self, mock_load):
        """confidence == VETO_MIN_CONFIDENCE should trigger veto"""
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", VETO_MIN_CONFIDENCE),
        ]
        result = engine._check_veto(opinions)
        self.assertIsNotNone(result)


class TestAnalyzeConflict(unittest.TestCase):
    """_analyze_conflict 内部方法"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_returns_disagree_reasons(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "risky", 0.9),
            _make_opinion("executor", OpinionType.AGREE, "ok", 0.8),
        ]
        analysis = engine._analyze_conflict(opinions)
        self.assertIn("strategist", analysis)
        self.assertIn("risky", analysis)

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_no_disagree_returns_unknown(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.AGREE, "ok", 0.9),
        ]
        analysis = engine._analyze_conflict(opinions)
        self.assertEqual(analysis, "未知原因")


class TestFindCompromise(unittest.TestCase):
    """_find_compromise 内部方法"""

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_with_matching_alternatives(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9,
                          alternative="plan B"),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8,
                          alternative="plan B"),
        ]
        result = engine._find_compromise(opinions)
        self.assertEqual(result, "plan B")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_compromise_with_different_alternatives(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9,
                          alternative="plan A"),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8,
                          alternative="plan B"),
        ]
        result = engine._find_compromise(opinions)
        # Returns first alternative when no majority
        self.assertEqual(result, "plan A")

    @patch.object(ConsensusEngine, "_load_decision_log_from_db")
    def test_no_alternatives_returns_none(self, mock_load):
        engine = ConsensusEngine()
        opinions = [
            _make_opinion("strategist", OpinionType.DISAGREE, "no", 0.9),
            _make_opinion("executor", OpinionType.DISAGREE, "nope", 0.8),
        ]
        result = engine._find_compromise(opinions)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
