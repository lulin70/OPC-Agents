"""
Strategies Mixin for BusinessTypeDetectorV2

Extracted from business_type_detector_v2.py to reduce the God Class size.
Contains the per-strategy detection methods:
- _detect_by_pattern: regex pattern matching (highest priority)
- _detect_by_keywords: enhanced keyword scoring (main strategy)
- _detect_by_llm: LLM-assisted detection (Phase 3)
- _infer_from_profile: business type inference from user profile

=== Design Notes ===
Implemented as a mixin class to preserve all method signatures.
BusinessTypeDetectorV2 inherits from this mixin, so all external callers see no
change. Cross-mixin dependencies are resolved at runtime via the composed
facade instance:
- self._calculate_enhanced_score / self._extract_matched_keywords_enhanced
  (BusinessTypeDetectorScoringMixin)
- self.detect (facade — used by _infer_from_profile for interest text)
- self.patterns / self.type_keywords / self.enable_llm / self.llm_service
  (set by facade __init__)
DetectionResult is imported from the facade module; the facade defines it
before importing the mixins to keep the import cycle safe.
"""

import re
from typing import Dict, List, Optional

from opc_manager.business_types import BusinessType
from opc_manager.business_type_detector_v2 import DetectionResult


class BusinessTypeDetectorStrategiesMixin:
    """Mixin class containing per-strategy detection methods for
    BusinessTypeDetectorV2.

    Each strategy method returns a DetectionResult (or None for pattern/LLM
    paths when no match is found). Cross-mixin calls (e.g. scoring helpers)
    are resolved at runtime on the composed facade instance.
    """

    def _detect_by_pattern(self, input_text: str) -> Optional[DetectionResult]:
        """Detect business type via regex pattern matching"""
        best_match = None
        best_confidence = 0.0
        detected_patterns = []

        for btype, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, input_text, re.IGNORECASE)
                if match:
                    confidence = 0.9  # High confidence for pattern matching
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = btype
                        detected_patterns.append(pattern)

        if best_match:
            return DetectionResult(
                business_type=best_match,
                confidence=min(best_confidence, 0.95),
                method="pattern_match",
                matched_keywords=[],
                alternative_types=[],
                detected_patterns=detected_patterns[:3],
                reasoning=f"Matched {len(detected_patterns)} patterns",
            )

        return None

    def _detect_by_keywords(self, input_text: str) -> DetectionResult:
        """Keyword-based detection (enhanced)"""
        text_lower = input_text.lower().strip()

        scores = {}

        for business_type, keyword_config in self.type_keywords.items():
            score = self._calculate_enhanced_score(text_lower, keyword_config)
            scores[business_type] = score

        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        best_type, best_score = sorted_types[0]

        matched_keywords = self._extract_matched_keywords_enhanced(
            text_lower, self.type_keywords[best_type]
        )

        alternative_types = [
            (bt, score) for bt, score in sorted_types[1:4] if score > 0.08
        ]

        return DetectionResult(
            business_type=best_type,
            confidence=round(best_score, 3),
            method="keyword_match",
            matched_keywords=matched_keywords,
            alternative_types=alternative_types,
            detected_patterns=[],
            reasoning=f"Keyword score: {best_score:.3f}, matched {len(matched_keywords)} keywords",
        )

    def _detect_by_llm(
        self, input_text: str, history: Optional[List[Dict]] = None
    ) -> Optional[DetectionResult]:
        """
        LLM-assisted detection (Phase 3 full implementation)

        Uses injected LLMService for business type detection.
        When keyword matching confidence is low, LLM fallback can improve
        recognition accuracy for complex sentences.
        """
        if not self.enable_llm:
            return None

        if self.llm_service is None:
            return None

        try:
            import asyncio

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                self.llm_service.detect_business_type_by_llm(input_text, history)
            )
            loop.close()

            if result.get("business_type") and result["business_type"] != "unknown":
                try:
                    bt = BusinessType(result["business_type"])
                    confidence = float(result.get("confidence", 0.7))
                    reasoning = result.get("reasoning", "")
                    return DetectionResult(
                        business_type=bt,
                        confidence=min(confidence, 0.99),
                        method="llm_assisted",
                        matched_keywords=[],
                        detected_patterns=[],
                        reasoning=f"LLM detection: {reasoning}",
                    )
                except ValueError:
                    pass
            return None
        except Exception as e:
            import logging

            logging.warning(f"[DetectorV2] LLM detection failed: {e}")
            return None

    def _infer_from_profile(self, user_profile: Dict) -> Optional[BusinessType]:
        """Infer business type from user profile"""
        if not user_profile:
            return None

        saved_type_str = user_profile.get("business_type")
        if saved_type_str:
            return BusinessType.from_string(saved_type_str)

        declared_interests = user_profile.get("interests", [])
        if isinstance(declared_interests, list):
            interests_text = " ".join(declared_interests)
            temp_result = self.detect(interests_text)
            if temp_result.confidence > 0.4:
                return temp_result.business_type

        return None
