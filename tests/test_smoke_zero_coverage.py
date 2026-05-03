"""零覆盖模块冒烟测试

确保关键模块能正确导入和基本实例化，不测试完整功能。
完整功能测试将在v0.1.1中逐步补充。
"""

import unittest
import os
import sys


class TestBusinessTypeDetectorSmoke(unittest.TestCase):
    """business_type_detector_v2.py 冒烟测试"""

    def test_import(self):
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2

        self.assertTrue(BusinessTypeDetectorV2 is not None)

    def test_instantiation(self):
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2

        detector = BusinessTypeDetectorV2()
        self.assertIsNotNone(detector)

    def test_detect_returns_result(self):
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2

        detector = BusinessTypeDetectorV2()
        result = detector.detect("帮我写Q2营销方案")
        self.assertIsNotNone(result)

    def test_detect_empty_input(self):
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2

        detector = BusinessTypeDetectorV2()
        result = detector.detect("")
        self.assertIsNotNone(result)


class TestScenarioEngineSmoke(unittest.TestCase):
    """scenario_engine_v2.py 冒烟测试"""

    def test_import(self):
        from opc_manager.scenario_engine_v2 import ScenarioEngineV2

        self.assertTrue(ScenarioEngineV2 is not None)

    def test_instantiation(self):
        from opc_manager.scenario_engine_v2 import ScenarioEngineV2

        engine = ScenarioEngineV2()
        self.assertIsNotNone(engine)

    def test_list_scenarios(self):
        from opc_manager.scenario_engine_v2 import ScenarioEngineV2

        engine = ScenarioEngineV2()
        scenarios = engine.list_scenarios()
        self.assertIsInstance(scenarios, list)
        self.assertGreater(len(scenarios), 0)

    def test_process_returns_result(self):
        from opc_manager.scenario_engine_v2 import ScenarioEngineV2

        engine = ScenarioEngineV2()
        result = engine.process("帮我写营销方案")
        self.assertIsNotNone(result)


class TestFlywheelTrackerSmoke(unittest.TestCase):
    """flywheel_tracker.py 冒烟测试"""

    def test_import(self):
        from opc_manager.flywheel_tracker import FlywheelTracker

        self.assertTrue(FlywheelTracker is not None)

    def test_instantiation(self):
        from opc_manager.flywheel_tracker import FlywheelTracker

        tracker = FlywheelTracker()
        self.assertIsNotNone(tracker)

    def test_get_level(self):
        from opc_manager.flywheel_tracker import FlywheelTracker

        tracker = FlywheelTracker()
        state = tracker.get_or_create_state("test_user")
        self.assertIsNotNone(state)

    def test_track_scenario(self):
        from opc_manager.flywheel_tracker import FlywheelTracker
        from opc_manager.business_types import BusinessType

        tracker = FlywheelTracker()
        tracker.record_scenario_completion(
            "test_user", "marketing_001", BusinessType.CONTENT_CREATOR
        )

    def test_get_health_score(self):
        from opc_manager.flywheel_tracker import FlywheelTracker

        tracker = FlywheelTracker()
        score = tracker.get_flywheel_health_score("test_user")
        self.assertIsNotNone(score)


class TestPersonaManagerSmoke(unittest.TestCase):
    """persona_manager.py 冒烟测试"""

    def test_import(self):
        from opc_manager.persona_manager import PersonaManager

        self.assertTrue(PersonaManager is not None)

    def test_instantiation(self):
        from opc_manager.persona_manager import PersonaManager

        manager = PersonaManager()
        self.assertIsNotNone(manager)

    def test_get_persona(self):
        from opc_manager.persona_manager import PersonaManager
        from opc_manager.business_types import BusinessType

        manager = PersonaManager()
        persona = manager.get_persona(
            user_id="test", business_type=BusinessType.CONTENT_CREATOR
        )
        self.assertIsNotNone(persona)


class TestLLMServiceSmoke(unittest.TestCase):
    """llm_service.py 冒烟测试"""

    def test_import(self):
        from opc_manager.llm_service import LLMService, LLMConfig, LLMProvider

        self.assertTrue(LLMService is not None)
        self.assertTrue(LLMConfig is not None)
        self.assertTrue(LLMProvider is not None)

    def test_config_creation(self):
        from opc_manager.llm_service import LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.MOKA, api_key="test-key")
        self.assertEqual(config.provider, LLMProvider.MOKA)

    def test_service_creation(self):
        from opc_manager.llm_service import LLMService, LLMConfig, LLMProvider

        config = LLMConfig(provider=LLMProvider.MOKA, api_key="test-key")
        service = LLMService(config)
        self.assertIsNotNone(service)

    def test_usage_tracker(self):
        from opc_manager.llm_service import UsageTracker

        tracker = UsageTracker(daily_budget=5.0)
        tracker.record(
            user_id="test", usage={"prompt_tokens": 10, "completion_tokens": 20}
        )
        report = tracker.get_report()
        self.assertIsNotNone(report)


class TestMonitoringSmoke(unittest.TestCase):
    """monitoring.py 冒烟测试"""

    def test_import(self):
        from opc_manager.monitoring import init_monitoring, track_event, track_error

        self.assertTrue(init_monitoring is not None)
        self.assertTrue(track_event is not None)
        self.assertTrue(track_error is not None)

    def test_track_event_no_crash(self):
        from opc_manager.monitoring import track_event

        track_event("test_event", {"key": "value"})

    def test_track_error_no_crash(self):
        from opc_manager.monitoring import track_error

        track_error(ValueError("test error"), {"context": "test"})


class TestConfigSmoke(unittest.TestCase):
    """config.py 冒烟测试"""

    def test_import(self):
        from opc_manager.config import ConfigManager

        self.assertTrue(ConfigManager is not None)

    def test_default_config(self):
        from opc_manager.config import ConfigManager

        config = ConfigManager()
        self.assertIsNotNone(config)


class TestBusinessTypesSmoke(unittest.TestCase):
    """business_types.py 冒烟测试"""

    def test_import(self):
        from opc_manager.business_types import BusinessType

        self.assertTrue(BusinessType is not None)

    def test_all_types(self):
        from opc_manager.business_types import BusinessType

        types = BusinessType.get_all_types()
        self.assertGreaterEqual(len(types), 6)

    def test_from_string(self):
        from opc_manager.business_types import BusinessType

        result = BusinessType.from_string("content_creator")
        self.assertIsNotNone(result)

    def test_from_string_invalid(self):
        from opc_manager.business_types import BusinessType

        result = BusinessType.from_string("nonexistent_type")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
