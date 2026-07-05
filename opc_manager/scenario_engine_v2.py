"""
Scenario Engine V2 - Execution layer (matching, selection, running)

Definition layer (dataclasses, templates, built-in scenarios) lives in scenario_definitions.py.
This module re-exports all public symbols for backward compatibility.
"""

from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from opc_manager.business_types import BusinessType

from opc_manager.scenario_definitions import (
    ScenarioConfig,
    ScenarioResult,
    BUILT_IN_SCENARIOS,
)

logger = logging.getLogger(__name__)


class ScenarioEngineV2:
    """
    Scenario Engine V2 - Core scenario recognition and workflow orchestration engine

    Features:
    - Supports 9 core scenarios (3 original + 6 new)
    - Business type aware routing (6 types)
    - Structured workflow step definitions
    - Confidence scoring and multi-candidate ranking
    - Persona system integration interface
    """

    def __init__(self):
        """Initialize Scenario Engine V2"""
        self.scenarios: Dict[str, ScenarioConfig] = dict(BUILT_IN_SCENARIOS)
        self.type_detector = None
        self.persona_manager = None

    def process(
        self, user_input: str, user_context: Optional[Dict[str, Any]] = None
    ) -> ScenarioResult:
        """
        Process user input and return scenario matching result

        Args:
            user_input: User natural language input
            user_context: User context information (optional)
                - profile: User profile
                - conversation_history: Conversation history
                - user_id: User ID
                - preferred_business_type: User's preferred business type

        Returns:
            ScenarioResult: Scenario matching and processing result
        """
        if user_context is None:
            user_context = {}

        detected_type = BusinessType.CONTENT_CREATOR

        if self.type_detector:
            try:
                detection_result = self.type_detector.detect(
                    input_text=user_input,
                    user_profile=user_context.get("profile"),
                    history=user_context.get("conversation_history", []),
                )
                detected_type = detection_result.business_type
            except Exception as e:
                logger.error("BusinessTypeDetector failed, using default type: %s", e)

        candidates: List[Dict[str, Any]] = []
        for scenario_id, config in self.scenarios.items():
            is_target_type = detected_type in config.target_business_types or len(
                config.target_business_types
            ) == len(BusinessType.get_all_types())

            if is_target_type:
                confidence = self._calculate_match_confidence(
                    user_input, config.trigger_phrases
                )

                if confidence >= config.confidence_threshold:
                    candidates.append(
                        {
                            "scenario_id": scenario_id,
                            "confidence": confidence,
                            "config": config,
                        }
                    )

        candidates.sort(key=lambda x: x["confidence"], reverse=True)

        persona = None
        if self.persona_manager and user_context.get("user_id"):
            try:
                persona = self.persona_manager.get_persona(
                    user_id=user_context.get("user_id"),
                    business_type=detected_type,
                    context={
                        "scenario_id": (
                            candidates[0]["scenario_id"] if candidates else None
                        )
                    },
                )
            except Exception as e:
                logger.error("PersonaManager failed: %s", e)

        if not candidates:
            return ScenarioResult(
                matched=False,
                confidence=0.0,
                detected_business_type=detected_type,
                suggestion="未匹配到具体场景，是否需要我帮您梳理需求？您可以尝试：\n"
                "- 内容创作：'帮我规划下周的内容日历'\n"
                "- 产品发布：'我要发布一个新产品'\n"
                "- 报告撰写：'帮我写一份月度报告'",
                candidates=[],
            )

        best_match = candidates[0]

        return ScenarioResult(
            matched=True,
            scenario_id=best_match["scenario_id"],
            scenario_config=best_match["config"],
            confidence=best_match["confidence"],
            detected_business_type=detected_type,
            persona=persona,
            workflow=[step.to_dict() for step in best_match["config"].workflow_steps],
            candidates=candidates[:3],
        )

    def _calculate_match_confidence(
        self, user_input: str, trigger_phrases: List[str]
    ) -> float:
        """
        Calculate match confidence between user input and trigger phrases

        Algorithm:
        - Exact match (complete phrase appears in input): 0.9
        - Partial match (keyword hit): 0.5-0.7 * keyword coverage rate
        """
        user_input_lower = user_input.lower().strip()

        max_confidence = 0.0

        for phrase in trigger_phrases:
            phrase_lower = phrase.lower()

            if phrase_lower in user_input_lower:
                confidence = 0.9
            else:
                keywords = phrase_lower.split()
                match_count = sum(
                    1 for kw in keywords if kw in user_input_lower and len(kw) > 1
                )
                confidence = (match_count / len(keywords)) * 0.7 if keywords else 0.0

            max_confidence = max(max_confidence, confidence)

        return max_confidence

    def get_scenario(self, scenario_id: str) -> Optional[ScenarioConfig]:
        """Get scenario configuration by ID"""
        return self.scenarios.get(scenario_id)

    def list_scenarios(
        self, business_type: Optional[BusinessType] = None
    ) -> List[Dict[str, Any]]:
        """
        List all scenarios (can be filtered by business type)

        Args:
            business_type: Optional business type filter

        Returns:
            Scenario list (summary information)
        """
        scenarios_list = []

        for scenario_id, config in self.scenarios.items():
            if business_type is None or business_type in config.target_business_types:
                scenarios_list.append(
                    {
                        "id": config.id,
                        "name": config.name,
                        "description": config.description,
                        "estimated_duration": config.estimated_duration,
                        "target_business_types": [
                            bt.value for bt in config.target_business_types
                        ],
                        "steps_count": len(config.workflow_steps),
                    }
                )

        return scenarios_list

    def get_statistics(self) -> Dict[str, Any]:
        """Get scenario engine statistics"""
        type_distribution = {}
        for config in self.scenarios.values():
            for bt in config.target_business_types:
                type_key = bt.value
                if type_key not in type_distribution:
                    type_distribution[type_key] = 0
                type_distribution[type_key] += 1

        return {
            "total_scenarios": len(self.scenarios),
            "business_types_supported": list(type_distribution.keys()),
            "scenarios_per_type": type_distribution,
            "version": "2.1.0",
            "loaded_at": datetime.now().isoformat(),
        }


_scenario_engine_v2_instance = None


def get_scenario_engine_v2() -> ScenarioEngineV2:
    """Get ScenarioEngineV2 singleton instance"""
    global _scenario_engine_v2_instance
    if _scenario_engine_v2_instance is None:
        _scenario_engine_v2_instance = ScenarioEngineV2()
    return _scenario_engine_v2_instance


if __name__ == "__main__":
    engine = ScenarioEngineV2()

    print("=" * 60)
    print("OPC-Agents Scenario Engine V2.1")
    print("=" * 60)

    stats = engine.get_statistics()
    print("\n Engine statistics:")
    print(f"   Total scenarios: {stats['total_scenarios']}")
    print(
        f"   Supported business types: {', '.join(stats['business_types_supported'])}"
    )
    print(f"   Version: {stats['version']}")

    print("\n All scenarios:")
    for scenario in engine.list_scenarios():
        types_str = ", ".join(scenario["target_business_types"])
        print(f"   [{scenario['id']}] {scenario['name']}")
        print(f"      Description: {scenario['description'][:50]}...")
        print(f"      Target types: {types_str}")
        print(f"      Steps: {scenario['steps_count']}")
        print()

    test_inputs = [
        ("帮我规划下周的内容日历", {"user_id": "test_user_001"}),
        ("我要发布一个新的AI工具", {"user_id": "test_user_002"}),
        ("帮我写一份月度工作报告", {"user_id": "test_user_003"}),
        ("明天下午组织个产品评审会", {"user_id": "test_user_004"}),
    ]

    print("\n" + "=" * 60)
    print(" Test cases")
    print("=" * 60)

    for i, (input_text, context) in enumerate(test_inputs, 1):
        print(f'\nTest {i}: "{input_text}"')
        result = engine.process(input_text, context)
        print(f"Match result: {' Success' if result.matched else ' No match'}")
        if result.matched:
            print(f"Scenario ID: {result.scenario_id}")
            print(f"Confidence: {result.confidence:.2f}")
            if result.detected_business_type:
                print(f"Detected business type: {result.detected_business_type.value}")
            print(f"Workflow steps: {len(result.workflow or [])}")
        print("-" * 40)
