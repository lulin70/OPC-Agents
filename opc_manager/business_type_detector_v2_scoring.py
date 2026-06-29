"""
Scoring Mixin for BusinessTypeDetectorV2

Extracted from business_type_detector_v2.py to reduce the God Class size.
Contains the keyword scoring and context-adjustment methods:
- _calculate_enhanced_score: weighted multi-tier keyword scoring
- _extract_matched_keywords_enhanced: includes synonyms in match list
- _contains_negation: detect negation words
- _adjust_for_negation: penalize confidence on negation
- _analyze_context: derive context boost from history
- _apply_context_boost: apply boost to a DetectionResult

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
BusinessTypeDetectorV2 inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
facade instance:
- self._detect_by_keywords (BusinessTypeDetectorStrategiesMixin)
- self.type_keywords / self.negation_words (set by facade __init__)
DetectionResult is imported from the facade module; the facade defines it
before importing the mixins to keep the import cycle safe.
"""

from typing import Dict, List, Set, TYPE_CHECKING

from opc_manager.business_types import BusinessType
from opc_manager.business_type_detector_v2 import DetectionResult


class BusinessTypeDetectorScoringMixin:
    """Mixin class containing scoring and context-adjustment methods for
    BusinessTypeDetectorV2.

    These methods operate on the keyword database built by
    BusinessTypeDetectorDatabaseMixin and produce / mutate DetectionResult
    instances. Cross-mixin calls (e.g. self._detect_by_keywords) are resolved
    at runtime on the composed facade instance.
    """

    if TYPE_CHECKING:
        negation_words: Set[str]

        def _detect_by_keywords(self, text: str) -> DetectionResult: ...

    def _calculate_enhanced_score(self, text_lower: str, config: Dict) -> float:
        """
        Calculate enhanced score

        V2 improvements:
        - primary_keywords: ×2.5 (was ×2)
        - secondary_keywords: ×1.5 (was ×1)
        - context_phrases: ×4.0 (was ×3)
        - domain_phrases: ×3.0 (new)
        - synonyms: ×1.8 (new)
        - Complete phrase match bonus: +0.15
        """
        primary_matches = sum(
            1 for kw in config.get("primary_keywords", []) if kw.lower() in text_lower
        )

        secondary_matches = sum(
            1 for kw in config.get("secondary_keywords", []) if kw.lower() in text_lower
        )

        context_matches = sum(
            1
            for phrase in config.get("context_phrases", [])
            if phrase.lower() in text_lower
        )

        domain_matches = sum(
            1
            for phrase in config.get("domain_phrases", [])
            if phrase.lower() in text_lower
        )

        synonym_matches: float = 0.0
        synonyms = config.get("synonyms", {})
        for base_word, syn_list in synonyms.items():
            if base_word.lower() in text_lower:
                synonym_matches += 1
            else:
                for syn in syn_list:
                    if syn.lower() in text_lower:
                        synonym_matches += 0.7
                        break

        raw_score = (
            primary_matches * 2.5
            + secondary_matches * 1.5
            + context_matches * 4.0
            + domain_matches * 3.0
            + synonym_matches * 1.8
        )

        max_possible = (
            len(config.get("primary_keywords", [])) * 2.5
            + len(config.get("context_phrases", [])) * 4.0
        ) * 0.25

        normalized_score = min(raw_score / max(max_possible, 1), 1.0)

        bonus = 0.0
        for phrase in config.get("context_phrases", []):
            if phrase.lower() in text_lower:
                bonus += 0.05
        bonus = min(bonus, 0.15)

        weighted_score = (normalized_score + bonus) * config.get("weight", 1.0)

        return round(weighted_score, 3)

    def _extract_matched_keywords_enhanced(
        self, text_lower: str, config: Dict
    ) -> List[str]:
        """Extract matched keywords (enhanced, includes synonyms)"""
        matched = []

        all_keyword_sources = [
            config.get("primary_keywords", []),
            config.get("secondary_keywords", []),
            config.get("context_phrases", []),
            config.get("domain_phrases", []),
        ]

        for source in all_keyword_sources:
            for kw in source:
                if kw.lower() in text_lower:
                    if kw not in matched:
                        matched.append(kw)

        synonyms = config.get("synonyms", {})
        for base_word, syn_list in synonyms.items():
            if base_word.lower() in text_lower and base_word not in matched:
                matched.append(base_word)
            else:
                for syn in syn_list:
                    if syn.lower() in text_lower and syn not in matched:
                        matched.append(syn)
                        break

        return matched[:12]

    def _contains_negation(self, text: str) -> bool:
        """Check if text contains negation words"""
        for word in self.negation_words:
            if word in text:
                return True
        return False

    def _adjust_for_negation(
        self, result: DetectionResult, text: str
    ) -> DetectionResult:
        """Adjust result based on negation words"""
        negation_penalty = 0.3
        new_confidence = max(result.confidence - negation_penalty, 0.1)

        return DetectionResult(
            business_type=result.business_type,
            confidence=new_confidence,
            method=result.method + "_with_negation_check",
            matched_keywords=result.matched_keywords,
            alternative_types=result.alternative_types,
            detected_patterns=result.detected_patterns,
            reasoning=f"{result.reasoning} (contains negation, penalty {negation_penalty})",
        )

    def _analyze_context(self, history: List[Dict]) -> Dict[BusinessType, float]:
        """Analyze conversation history context"""
        type_scores = {}

        for item in history[-8:]:
            user_message = (
                item.get("user", "") or item.get("input", "") or item.get("message", "")
            )
            if user_message:
                temp_result = self._detect_by_keywords(user_message)
                bt_key = temp_result.business_type
                if bt_key not in type_scores:
                    type_scores[bt_key] = {"count": 0, "total_confidence": 0.0}
                type_scores[bt_key]["count"] += 1
                type_scores[bt_key]["total_confidence"] += temp_result.confidence

        context_boost = {}
        for bt, data in type_scores.items():
            if data["count"] >= 3:
                avg_conf = data["total_confidence"] / data["count"]
                boost = min(avg_conf * 0.3, 0.2)
                context_boost[bt] = boost

        return context_boost

    def _apply_context_boost(
        self, result: DetectionResult, context_boost: Dict[BusinessType, float]
    ) -> DetectionResult:
        """Apply context boost"""
        if result.business_type in context_boost:
            boost = context_boost[result.business_type]
            new_confidence = min(result.confidence + boost, 1.0)

            return DetectionResult(
                business_type=result.business_type,
                confidence=new_confidence,
                method=result.method + "_context_boosted",
                matched_keywords=result.matched_keywords,
                alternative_types=result.alternative_types,
                detected_patterns=result.detected_patterns,
                reasoning=f"{result.reasoning} (context boost +{boost:.2f})",
            )

        return result
