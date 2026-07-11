"""
Business Type Detector - BusinessTypeDetector V2

Phase 2 Enhanced: Improve accuracy from 80% to 95%+
New features:
- Pattern recognition (common expression patterns)
- Negation detection (avoid misclassification)
- Context awareness (conversation history weighting)
- Synonym expansion
- LLM assistance interface (reserved)

=== Architecture (Mixin-based facade) ===
BusinessTypeDetectorV2 is now a facade composing three mixins (each in its own
module):
  - BusinessTypeDetectorDatabaseMixin   (opc_manager.business_type_detector_v2_database)
    — _init_keyword_database_v2 / _init_pattern_database
  - BusinessTypeDetectorScoringMixin    (opc_manager.business_type_detector_v2_scoring)
    — _calculate_enhanced_score / _extract_matched_keywords_enhanced /
      _contains_negation / _adjust_for_negation / _analyze_context /
      _apply_context_boost
  - BusinessTypeDetectorStrategiesMixin (opc_manager.business_type_detector_v2_strategies)
    — _detect_by_pattern / _detect_by_keywords / _detect_by_llm /
      _infer_from_profile
This facade retains __init__, detect (public entry), _build_result,
_record_method, get_statistics — the public API is 100% backward compatible.

Detection strategy priority:
1. Pattern matching (highest priority) - Identify specific expression patterns
2. Keyword matching (main strategy) - Extract feature words from user input
3. Context analysis (auxiliary) - Analyze patterns in conversation history
4. User profile inference (auxiliary) - If user has saved type preference
5. LLM assistance (optional) - Call large model for semantic understanding
6. Default fallback - If all above fail, return default type

Phase 2 improvements:
- Accuracy target: 95%+ (up from 80%)
- Added pattern recognition capability
- Added negation detection mechanism
- Added context awareness
- Added synonym expansion
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging

from opc_manager.business_types import BusinessType

logger = logging.getLogger(__name__)

__all__ = [
    "BusinessTypeDetectorV2",
    "DetectionResult",
]


@dataclass
class DetectionResult:
    """Detection result"""

    business_type: BusinessType
    confidence: float
    method: str  # "pattern_match", "keyword_match", "profile_inference", "history_analysis", "llm_assisted", "default"
    matched_keywords: List[str] = field(default_factory=list)
    alternative_types: List[Tuple[BusinessType, float]] = field(default_factory=list)
    detected_patterns: List[str] = field(default_factory=list)
    reasoning: str = ""


# DetectionResult is defined ABOVE so the mixin modules can safely do
# `from opc_manager.business_type_detector_v2 import DetectionResult` without
# triggering a circular-import error at load time.
from opc_manager.business_type_detector_v2_database import (  # noqa: E402
    BusinessTypeDetectorDatabaseMixin,
)
from opc_manager.business_type_detector_v2_scoring import (  # noqa: E402
    BusinessTypeDetectorScoringMixin,
)
from opc_manager.business_type_detector_v2_strategies import (  # noqa: E402
    BusinessTypeDetectorStrategiesMixin,
)


class BusinessTypeDetectorV2(
    BusinessTypeDetectorDatabaseMixin,
    BusinessTypeDetectorScoringMixin,
    BusinessTypeDetectorStrategiesMixin,
):
    """
    Business Type Detector V2 (Phase 2 Enhanced)

    Facade composing three behavior mixins (Database / Scoring / Strategies).
    Cross-mixin calls (e.g. self._calculate_enhanced_score) are resolved at
    runtime on this facade instance via Python's MRO.

    Detection strategy priority:
    1. Pattern matching (highest priority) - Identify specific expression patterns
    2. Keyword matching (main strategy) - Extract feature words from user input
    3. Context analysis (auxiliary) - Analyze patterns in conversation history
    4. User profile inference (auxiliary) - If user has saved type preference
    5. LLM assistance (optional) - Call large model for semantic understanding
    6. Default fallback - If all above fail, return default type

    Phase 2 improvements:
    - Accuracy target: 95%+ (up from 80%)
    - Added pattern recognition capability
    - Added negation detection mechanism
    - Added context awareness
    - Added synonym expansion
    """

    def __init__(
        self, enable_llm: bool = False, llm_service: Optional[Any] = None
    ) -> None:
        """
        Initialize Detector V2

        Args:
            enable_llm: Whether to enable LLM-assisted detection (requires API Key)
            llm_service: LLM service instance (Phase 3 addition, supports external injection)
        """
        self.type_keywords = self._init_keyword_database_v2()
        self.patterns = self._init_pattern_database()
        self.negation_words = {"不", "不是", "没有", "别", "不要", "非", "无", "没"}
        self.default_type = BusinessType.CONTENT_CREATOR
        self.confidence_threshold = 0.12
        self.enable_llm = enable_llm
        self.llm_service = llm_service
        self._stats: Dict[str, Any] = {
            "total_detections": 0,
            "method_distribution": {},
        }

    def detect(
        self,
        input_text: str,
        user_profile: Optional[Dict] = None,
        history: Optional[List[Dict]] = None,
        min_confidence: Optional[float] = None,
    ) -> DetectionResult:
        """
        Detect user's business type (V2 Enhanced)

        Args:
            input_text: User input text
            user_profile: User profile info (optional)
            history: Conversation history (optional)
            min_confidence: Minimum confidence threshold (optional)

        Returns:
            DetectionResult: Contains detection result and reasoning process
        """
        if min_confidence is None:
            min_confidence = self.confidence_threshold

        self._stats["total_detections"] += 1

        # Step 1: Pattern matching (highest priority)
        pattern_result = self._detect_by_pattern(input_text)
        if pattern_result and pattern_result.confidence >= 0.8:
            self._record_method("pattern_match")
            return self._build_result(
                pattern_result.business_type,
                pattern_result.confidence,
                "pattern_match",
                input_text,
                detected_patterns=pattern_result.detected_patterns,
            )

        # Step 2: Keyword matching (main strategy)
        keyword_result = self._detect_by_keywords(input_text)

        # Step 3: Negation detection (reduce misclassification)
        if self._contains_negation(input_text):
            keyword_result = self._adjust_for_negation(keyword_result, input_text)

        # Step 4: Context analysis (if history exists)
        if history and len(history) >= 3:
            context_boost = self._analyze_context(history)
            keyword_result = self._apply_context_boost(keyword_result, context_boost)

        # Step 5: User profile inference (if available)
        if user_profile and keyword_result.confidence < 0.6:
            profile_type = self._infer_from_profile(user_profile)
            if profile_type and keyword_result.business_type != profile_type:
                if keyword_result.confidence < 0.4:
                    keyword_result = self._build_result(
                        profile_type, 0.55, "profile_inference", input_text
                    )
                    self._record_method("profile_inference")

        # Step 6: LLM assistance (if enabled and confidence is low)
        if self.enable_llm and keyword_result.confidence < 0.5:
            try:
                llm_result = self._detect_by_llm(input_text, history)
                if llm_result and llm_result.confidence > keyword_result.confidence:
                    keyword_result = llm_result
                    self._record_method("llm_assisted")
            except Exception as e:
                logger.debug("[BusinessTypeDetectorV2] LLM assist failed: %s", e)

        # Ensure minimum threshold is met
        if keyword_result.confidence < min_confidence:
            if user_profile:
                profile_type = self._infer_from_profile(user_profile)
                if profile_type:
                    keyword_result = self._build_result(
                        profile_type,
                        min_confidence + 0.1,
                        "profile_fallback",
                        input_text,
                    )
                else:
                    keyword_result = self._build_result(
                        self.default_type, 0.2, "default", input_text
                    )
            else:
                keyword_result = self._build_result(
                    self.default_type, 0.2, "default", input_text
                )

        self._record_method("keyword_match")
        return keyword_result

    def _build_result(
        self,
        business_type: BusinessType,
        confidence: float,
        method: str,
        input_text: str,
        matched_keywords: Optional[List[str]] = None,
        detected_patterns: Optional[List[str]] = None,
        reasoning: str = "",
    ) -> DetectionResult:
        """Build standardized detection result"""
        if matched_keywords is None:
            config = self.type_keywords.get(business_type, {})
            matched_keywords = self._extract_matched_keywords_enhanced(
                input_text.lower(), config
            )

        if detected_patterns is None:
            detected_patterns = []

        alternative_types = []
        for bt in self.type_keywords.keys():
            if bt != business_type:
                config = self.type_keywords[bt]
                score = self._calculate_enhanced_score(input_text.lower(), config)
                if score > 0.08:
                    alternative_types.append((bt, round(score, 3)))

        alternative_types.sort(key=lambda x: x[1], reverse=True)
        alternative_types = alternative_types[:3]

        return DetectionResult(
            business_type=business_type,
            confidence=confidence,
            method=method,
            matched_keywords=matched_keywords,
            alternative_types=alternative_types,
            detected_patterns=detected_patterns,
            reasoning=reasoning or f"Method: {method}",
        )

    def _record_method(self, method: str) -> None:
        """Record detection method usage statistics"""
        if method not in self._stats["method_distribution"]:
            self._stats["method_distribution"][method] = 0
        self._stats["method_distribution"][method] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get detector statistics"""
        type_info = {}
        for bt, config in self.type_keywords.items():
            type_info[bt.value] = {
                "name": config["name"],
                "emoji": config["emoji"],
                "primary_count": len(config.get("primary_keywords", [])),
                "secondary_count": len(config.get("secondary_keywords", [])),
                "patterns_count": len(self.patterns.get(bt, [])),
            }

        return {
            "version": "2.2.0 (Phase 2 Enhanced)",
            "total_detections": self._stats["total_detections"],
            "method_distribution": self._stats["method_distribution"],
            "supported_types": list(type_info.keys()),
            "type_details": type_info,
            "features": [
                "Pattern matching (regex)",
                "Enhanced keyword scoring",
                "Negation detection",
                "Context awareness",
                "Synonym expansion",
                "LLM assistance (optional)",
            ],
        }


if __name__ == "__main__":
    detector = BusinessTypeDetectorV2(enable_llm=False)

    print("=" * 70)
    print("OPC-Agents Business Type Detector v2.2 (Phase 2 Enhanced)")
    print("=" * 70)

    stats = detector.get_statistics()
    print(f"\nVersion: {stats['version']}")
    print(f"Supported types: {', '.join(stats['supported_types'])}")
    print(f"Features: {', '.join(stats['features'])}")

    test_cases = [
        ("帮我规划下周的内容日历，要考虑粉丝画像", "内容创作者"),
        ("我要在Gumroad上发布一个新课程，需要定价建议", "数字产品"),
        ("帮我的淘宝店铺策划双十一促销活动", "电商运营"),
        ("客户需要一份数字化转型战略咨询提案", "咨询师"),
        ("分析一下用户在App Store上的评论反馈，生成优先级矩阵", "AI工具"),
        ("设计稿完成了，准备打包交付给客户", "创意工作者"),
        ("我的小红书账号想涨粉", "内容创作者"),
        ("这个AI应用的API响应时间太长了，需要优化", "AI工具"),
        ("我不想做电商了，想转行做内容", "内容创作者"),
        ("帮我在Figma里设计一个APP的UI原型", "创意工作者"),
    ]

    print(f"\n{'=' * 70}")
    print(f"Test Cases ({len(test_cases)})")
    print(f"{'=' * 70}")

    correct_count = 0
    for i, (input_text, expected_type) in enumerate(test_cases, 1):
        result = detector.detect(input_text)

        type_name_map = {
            "content_creator": "内容创作者",
            "digital_product": "数字产品",
            "ai_tool_builder": "AI工具开发者",
            "consultant": "专业咨询师",
            "ecommerce": "电商运营者",
            "creative_work": "创意工作者",
        }

        detected_name = type_name_map.get(
            result.business_type.value, result.business_type.value
        )
        is_correct = detected_name in expected_type
        if is_correct:
            correct_count += 1
            status = ""
        else:
            status = ""

        print(f'\n{status} [{i}] "{input_text[:45]}..."')
        print(f"   Expected: {expected_type}")
        print(f"   Detected: {result.business_type.value} ({detected_name})")
        print(f"   Confidence: {result.confidence:.3f} | Method: {result.method}")
        print(
            f"   Keywords({len(result.matched_keywords)}): {', '.join(result.matched_keywords[:4])}"
        )
        if result.detected_patterns:
            print(f"   Patterns: {len(result.detected_patterns)}")

    accuracy = (correct_count / len(test_cases)) * 100
    print(f"\n{'=' * 70}")
    print(f"Accuracy: {correct_count}/{len(test_cases)} = {accuracy:.1f}%")
    print(f"Target: 95%+ | {' Met' if accuracy >= 95 else ' Needs optimization'}")
    print("=" * 70)
