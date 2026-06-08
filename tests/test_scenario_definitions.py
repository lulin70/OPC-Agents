"""
Comprehensive unit tests for scenario_definitions.py

Covers:
1. Data structure validation (all required fields present)
2. Built-in scenario completeness checks
3. Referential integrity between scenarios and business types
4. Default value correctness
5. Serialization/deserialization (to_dict)
6. Scenario lookup by business type
7. Scenario lookup by name/ID
8. Edge cases: unknown business type, missing scenario
"""

import unittest
from typing import Dict, List

from opc_manager.business_types import BusinessType
from opc_manager.scenario_definitions import (
    OutputSpec,
    DeliverableTemplate,
    WorkflowStep,
    ScenarioConfig,
    ScenarioResult,
    BUILT_IN_SCENARIOS,
    launch_product_scenario,
    write_report_scenario,
    organize_meeting_scenario,
    content_calendar_scenario,
    digital_product_launch_scenario,
    feedback_analysis_scenario,
    consulting_proposal_scenario,
    ecommerce_ops_scenario,
    project_deliverable_scenario,
)


# ==================== OutputSpec Tests ====================


class TestOutputSpec(unittest.TestCase):
    """Test OutputSpec dataclass."""

    def test_required_fields(self):
        spec = OutputSpec(name="Test", format="PDF")
        self.assertEqual(spec.name, "Test")
        self.assertEqual(spec.format, "PDF")
        self.assertEqual(spec.includes, [])

    def test_with_includes(self):
        spec = OutputSpec(name="Report", format="Word", includes=["summary", "body"])
        self.assertEqual(len(spec.includes), 2)

    def test_default_includes_is_empty_list(self):
        spec = OutputSpec(name="X", format="Y")
        self.assertIsInstance(spec.includes, list)
        self.assertEqual(len(spec.includes), 0)


# ==================== DeliverableTemplate Tests ====================


class TestDeliverableTemplate(unittest.TestCase):
    """Test DeliverableTemplate dataclass."""

    def test_required_fields(self):
        tmpl = DeliverableTemplate(name="Test", sections=["A", "B"])
        self.assertEqual(tmpl.name, "Test")
        self.assertEqual(tmpl.sections, ["A", "B"])
        self.assertEqual(tmpl.format, "Multi-format")

    def test_custom_format(self):
        tmpl = DeliverableTemplate(name="Test", sections=["A"], format="PDF")
        self.assertEqual(tmpl.format, "PDF")

    def test_default_format(self):
        tmpl = DeliverableTemplate(name="Test", sections=[])
        self.assertEqual(tmpl.format, "Multi-format")


# ==================== WorkflowStep Tests ====================


class TestWorkflowStep(unittest.TestCase):
    """Test WorkflowStep dataclass and serialization."""

    def test_required_fields(self):
        step = WorkflowStep(
            step_id=1,
            name="Test Step",
            type="research",
            description="Do research",
            estimated_duration="1 hour",
        )
        self.assertEqual(step.step_id, 1)
        self.assertEqual(step.name, "Test Step")
        self.assertEqual(step.type, "research")
        self.assertEqual(step.description, "Do research")
        self.assertEqual(step.estimated_duration, "1 hour")
        self.assertEqual(step.dependencies, [])
        self.assertIsNone(step.output_spec)
        self.assertEqual(step.executor, "")

    def test_with_dependencies(self):
        step = WorkflowStep(
            step_id=2,
            name="Step 2",
            type="analysis",
            description="Analyze",
            estimated_duration="30 min",
            dependencies=[1],
        )
        self.assertEqual(step.dependencies, [1])

    def test_with_output_spec(self):
        spec = OutputSpec(name="Output", format="PDF", includes=["data"])
        step = WorkflowStep(
            step_id=1,
            name="Step",
            type="gen",
            description="Generate",
            estimated_duration="10m",
            output_spec=spec,
        )
        self.assertIsNotNone(step.output_spec)
        self.assertEqual(step.output_spec.name, "Output")

    def test_to_dict(self):
        spec = OutputSpec(name="Output", format="PDF", includes=["data"])
        step = WorkflowStep(
            step_id=1,
            name="Step",
            type="gen",
            description="Generate",
            estimated_duration="10m",
            dependencies=[],
            output_spec=spec,
            executor="agent_1",
        )
        d = step.to_dict()
        self.assertEqual(d["step_id"], 1)
        self.assertEqual(d["name"], "Step")
        self.assertEqual(d["type"], "gen")
        self.assertEqual(d["description"], "Generate")
        self.assertEqual(d["estimated_duration"], "10m")
        self.assertEqual(d["dependencies"], [])
        self.assertIsNotNone(d["output_spec"])
        self.assertEqual(d["output_spec"]["name"], "Output")
        self.assertEqual(d["output_spec"]["format"], "PDF")
        self.assertEqual(d["output_spec"]["includes"], ["data"])
        self.assertEqual(d["executor"], "agent_1")

    def test_to_dict_without_output_spec(self):
        step = WorkflowStep(
            step_id=1,
            name="Step",
            type="gen",
            description="Generate",
            estimated_duration="10m",
        )
        d = step.to_dict()
        self.assertIsNone(d["output_spec"])


# ==================== ScenarioConfig Tests ====================


class TestScenarioConfig(unittest.TestCase):
    """Test ScenarioConfig dataclass and serialization."""

    def _make_config(self) -> ScenarioConfig:
        return ScenarioConfig(
            id="test_scenario",
            name="Test Scenario",
            description="A test scenario",
            trigger_phrases=["test", "testing"],
            target_business_types=[BusinessType.CONTENT_CREATOR],
            workflow_steps=[
                WorkflowStep(
                    step_id=1,
                    name="Step 1",
                    type="research",
                    description="Research",
                    estimated_duration="1h",
                )
            ],
            estimated_duration="1 hour",
            deliverable_template=DeliverableTemplate(
                name="Deliverable", sections=["Section 1"]
            ),
        )

    def test_required_fields(self):
        config = self._make_config()
        self.assertEqual(config.id, "test_scenario")
        self.assertEqual(config.name, "Test Scenario")
        self.assertEqual(config.description, "A test scenario")
        self.assertEqual(config.trigger_phrases, ["test", "testing"])
        self.assertEqual(config.target_business_types, [BusinessType.CONTENT_CREATOR])
        self.assertEqual(len(config.workflow_steps), 1)
        self.assertEqual(config.estimated_duration, "1 hour")
        self.assertIsNotNone(config.deliverable_template)

    def test_default_confidence_threshold(self):
        config = self._make_config()
        self.assertEqual(config.confidence_threshold, 0.5)

    def test_custom_confidence_threshold(self):
        config = self._make_config()
        config.confidence_threshold = 0.8
        self.assertEqual(config.confidence_threshold, 0.8)

    def test_to_dict(self):
        config = self._make_config()
        d = config.to_dict()
        self.assertEqual(d["id"], "test_scenario")
        self.assertEqual(d["name"], "Test Scenario")
        self.assertEqual(d["description"], "A test scenario")
        self.assertEqual(d["trigger_phrases"], ["test", "testing"])
        self.assertEqual(d["target_business_types"], ["content_creator"])
        self.assertIsInstance(d["workflow_steps"], list)
        self.assertEqual(len(d["workflow_steps"]), 1)
        self.assertEqual(d["estimated_duration"], "1 hour")
        self.assertEqual(d["confidence_threshold"], 0.5)
        self.assertIn("deliverable_template", d)
        self.assertEqual(d["deliverable_template"]["name"], "Deliverable")

    def test_to_dict_business_types_as_strings(self):
        config = self._make_config()
        d = config.to_dict()
        for bt_str in d["target_business_types"]:
            self.assertIsInstance(bt_str, str)

    def test_to_dict_workflow_steps_serialized(self):
        config = self._make_config()
        d = config.to_dict()
        step = d["workflow_steps"][0]
        self.assertIn("step_id", step)
        self.assertIn("name", step)
        self.assertIn("type", step)


# ==================== ScenarioResult Tests ====================


class TestScenarioResult(unittest.TestCase):
    """Test ScenarioResult dataclass and serialization."""

    def test_default_values(self):
        result = ScenarioResult(matched=False)
        self.assertFalse(result.matched)
        self.assertIsNone(result.scenario_id)
        self.assertIsNone(result.scenario_config)
        self.assertEqual(result.confidence, 0.0)
        self.assertIsNone(result.detected_business_type)
        self.assertIsNone(result.persona)
        self.assertIsNone(result.workflow)
        self.assertIsNone(result.suggestion)
        self.assertEqual(result.candidates, [])

    def test_matched_result(self):
        config = ScenarioConfig(
            id="test",
            name="Test",
            description="",
            trigger_phrases=[],
            target_business_types=[BusinessType.ECOMMERCE],
            workflow_steps=[],
            estimated_duration="1h",
            deliverable_template=DeliverableTemplate(name="D", sections=[]),
        )
        result = ScenarioResult(
            matched=True,
            scenario_id="test",
            scenario_config=config,
            confidence=0.9,
            detected_business_type=BusinessType.ECOMMERCE,
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.scenario_id, "test")
        self.assertIsNotNone(result.scenario_config)

    def test_to_dict_matched(self):
        config = ScenarioConfig(
            id="test",
            name="Test",
            description="",
            trigger_phrases=[],
            target_business_types=[BusinessType.ECOMMERCE],
            workflow_steps=[],
            estimated_duration="1h",
            deliverable_template=DeliverableTemplate(name="D", sections=[]),
        )
        result = ScenarioResult(
            matched=True,
            scenario_id="test",
            scenario_config=config,
            confidence=0.9,
            detected_business_type=BusinessType.ECOMMERCE,
        )
        d = result.to_dict()
        self.assertTrue(d["matched"])
        self.assertEqual(d["scenario_id"], "test")
        self.assertEqual(d["confidence"], 0.9)
        self.assertEqual(d["detected_business_type"], "ecommerce")
        self.assertIn("scenario_config", d)

    def test_to_dict_not_matched(self):
        result = ScenarioResult(matched=False, suggestion="Try something else")
        d = result.to_dict()
        self.assertFalse(d["matched"])
        self.assertEqual(d["suggestion"], "Try something else")
        self.assertNotIn("scenario_id", d)

    def test_to_dict_with_candidates(self):
        result = ScenarioResult(matched=False, candidates=[{"id": "a", "score": 0.5}])
        d = result.to_dict()
        self.assertIn("candidates", d)
        self.assertEqual(len(d["candidates"]), 1)


# ==================== Built-in Scenario Completeness Tests ====================


class TestBuiltInScenarioCompleteness(unittest.TestCase):
    """Verify every built-in scenario has all required attributes."""

    REQUIRED_SCENARIO_FIELDS = [
        "id",
        "name",
        "description",
        "trigger_phrases",
        "target_business_types",
        "workflow_steps",
        "estimated_duration",
        "deliverable_template",
    ]

    def test_all_scenarios_present(self):
        expected_ids = {
            "launch_product",
            "write_report",
            "organize_meeting",
            "content_calendar",
            "digital_product_launch",
            "feedback_analysis",
            "consulting_proposal",
            "ecommerce_ops",
            "project_deliverable",
        }
        self.assertEqual(set(BUILT_IN_SCENARIOS.keys()), expected_ids)

    def test_each_scenario_has_required_fields(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            for field_name in self.REQUIRED_SCENARIO_FIELDS:
                self.assertTrue(
                    hasattr(scenario, field_name),
                    f"Scenario '{sid}' missing field '{field_name}'",
                )

    def test_each_scenario_id_matches_key(self):
        for key, scenario in BUILT_IN_SCENARIOS.items():
            self.assertEqual(scenario.id, key, f"Key '{key}' != id '{scenario.id}'")

    def test_each_scenario_has_nonempty_name(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(len(scenario.name) > 0, f"Scenario '{sid}' has empty name")

    def test_each_scenario_has_nonempty_description(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(
                len(scenario.description) > 0,
                f"Scenario '{sid}' has empty description",
            )

    def test_each_scenario_has_trigger_phrases(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(
                len(scenario.trigger_phrases) > 0,
                f"Scenario '{sid}' has no trigger phrases",
            )

    def test_each_scenario_has_target_business_types(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(
                len(scenario.target_business_types) > 0,
                f"Scenario '{sid}' has no target business types",
            )

    def test_each_scenario_has_workflow_steps(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(
                len(scenario.workflow_steps) > 0,
                f"Scenario '{sid}' has no workflow steps",
            )

    def test_each_scenario_has_deliverable_template(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertIsNotNone(
                scenario.deliverable_template,
                f"Scenario '{sid}' has no deliverable template",
            )

    def test_each_scenario_has_estimated_duration(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertTrue(
                len(scenario.estimated_duration) > 0,
                f"Scenario '{sid}' has no estimated duration",
            )


# ==================== Workflow Step Integrity Tests ====================


class TestWorkflowStepIntegrity(unittest.TestCase):
    """Verify workflow steps in each scenario are well-formed."""

    def test_step_ids_are_sequential(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            ids = [step.step_id for step in scenario.workflow_steps]
            self.assertEqual(
                ids,
                list(range(1, len(ids) + 1)),
                f"Scenario '{sid}' has non-sequential step IDs: {ids}",
            )

    def test_dependencies_reference_valid_steps(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            valid_ids = {step.step_id for step in scenario.workflow_steps}
            for step in scenario.workflow_steps:
                for dep in step.dependencies:
                    self.assertIn(
                        dep,
                        valid_ids,
                        f"Scenario '{sid}' step {step.step_id} has invalid dependency {dep}",
                    )

    def test_each_step_has_name_and_type(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            for step in scenario.workflow_steps:
                self.assertTrue(
                    len(step.name) > 0,
                    f"Scenario '{sid}' has step with empty name",
                )
                self.assertTrue(
                    len(step.type) > 0,
                    f"Scenario '{sid}' has step with empty type",
                )

    def test_each_step_has_estimated_duration(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            for step in scenario.workflow_steps:
                self.assertTrue(
                    len(step.estimated_duration) > 0,
                    f"Scenario '{sid}' step '{step.name}' has no estimated duration",
                )


# ==================== Referential Integrity Tests ====================


class TestReferentialIntegrity(unittest.TestCase):
    """Test referential integrity between scenarios and business types."""

    def test_all_target_business_types_are_valid(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            for bt in scenario.target_business_types:
                self.assertIsInstance(
                    bt,
                    BusinessType,
                    f"Scenario '{sid}' has invalid business type: {bt}",
                )

    def test_each_business_type_has_at_least_one_scenario(self):
        """Every BusinessType should be targeted by at least one scenario."""
        types_with_scenarios = set()
        for scenario in BUILT_IN_SCENARIOS.values():
            types_with_scenarios.update(scenario.target_business_types)
        for bt in BusinessType:
            self.assertIn(
                bt,
                types_with_scenarios,
                f"BusinessType '{bt.value}' has no targeting scenario",
            )

    def test_organize_meeting_targets_all_types(self):
        """The organize_meeting scenario should target all business types."""
        scenario = BUILT_IN_SCENARIOS["organize_meeting"]
        all_types = set(BusinessType)
        self.assertEqual(set(scenario.target_business_types), all_types)

    def test_content_calendar_targets_content_creator(self):
        scenario = BUILT_IN_SCENARIOS["content_calendar"]
        self.assertIn(BusinessType.CONTENT_CREATOR, scenario.target_business_types)

    def test_digital_product_launch_targets_digital_product(self):
        scenario = BUILT_IN_SCENARIOS["digital_product_launch"]
        self.assertIn(BusinessType.DIGITAL_PRODUCT, scenario.target_business_types)

    def test_feedback_analysis_targets_ai_tool_builder(self):
        scenario = BUILT_IN_SCENARIOS["feedback_analysis"]
        self.assertIn(BusinessType.AI_TOOL_BUILDER, scenario.target_business_types)

    def test_consulting_proposal_targets_consultant(self):
        scenario = BUILT_IN_SCENARIOS["consulting_proposal"]
        self.assertIn(BusinessType.CONSULTANT, scenario.target_business_types)

    def test_ecommerce_ops_targets_ecommerce(self):
        scenario = BUILT_IN_SCENARIOS["ecommerce_ops"]
        self.assertIn(BusinessType.ECOMMERCE, scenario.target_business_types)

    def test_project_deliverable_targets_creative_work(self):
        scenario = BUILT_IN_SCENARIOS["project_deliverable"]
        self.assertIn(BusinessType.CREATIVE_WORK, scenario.target_business_types)


# ==================== Scenario Lookup Tests ====================


class TestScenarioLookup(unittest.TestCase):
    """Test looking up scenarios by business type and by name/ID."""

    def test_lookup_by_id(self):
        scenario = BUILT_IN_SCENARIOS.get("content_calendar")
        self.assertIsNotNone(scenario)
        self.assertEqual(scenario.name, "内容日历规划")

    def test_lookup_by_id_not_found(self):
        scenario = BUILT_IN_SCENARIOS.get("nonexistent_scenario")
        self.assertIsNone(scenario)

    def test_lookup_by_business_type(self):
        """Find all scenarios targeting a specific business type."""
        ecommerce_scenarios = [
            s
            for s in BUILT_IN_SCENARIOS.values()
            if BusinessType.ECOMMERCE in s.target_business_types
        ]
        self.assertGreater(len(ecommerce_scenarios), 0)

    def test_lookup_by_name(self):
        """Find scenario by name."""
        found = [s for s in BUILT_IN_SCENARIOS.values() if s.name == "电商运营优化"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, "ecommerce_ops")

    def test_scenario_ids_are_unique(self):
        ids = [s.id for s in BUILT_IN_SCENARIOS.values()]
        self.assertEqual(len(ids), len(set(ids)))


# ==================== Serialization Tests ====================


class TestScenarioSerialization(unittest.TestCase):
    """Test to_dict serialization for all built-in scenarios."""

    def test_all_scenarios_serialize(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            d = scenario.to_dict()
            self.assertIsInstance(d, dict, f"Scenario '{sid}' to_dict failed")
            self.assertEqual(d["id"], sid)

    def test_serialized_business_types_are_strings(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            d = scenario.to_dict()
            for bt_str in d["target_business_types"]:
                self.assertIsInstance(bt_str, str)

    def test_serialized_workflow_steps_are_dicts(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            d = scenario.to_dict()
            for step in d["workflow_steps"]:
                self.assertIsInstance(step, dict)
                self.assertIn("step_id", step)

    def test_serialized_deliverable_template(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            d = scenario.to_dict()
            dt = d["deliverable_template"]
            self.assertIn("name", dt)
            self.assertIn("sections", dt)
            self.assertIn("format", dt)

    def test_confidence_threshold_in_serialization(self):
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            d = scenario.to_dict()
            self.assertIn("confidence_threshold", d)
            self.assertIsInstance(d["confidence_threshold"], float)


# ==================== Individual Scenario Factory Tests ====================


class TestScenarioFactories(unittest.TestCase):
    """Test each scenario factory function returns a valid ScenarioConfig."""

    def test_launch_product_scenario(self):
        s = launch_product_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "launch_product")
        self.assertIn(BusinessType.DIGITAL_PRODUCT, s.target_business_types)

    def test_write_report_scenario(self):
        s = write_report_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "write_report")
        self.assertIn(BusinessType.CONSULTANT, s.target_business_types)

    def test_organize_meeting_scenario(self):
        s = organize_meeting_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "organize_meeting")
        self.assertEqual(len(s.target_business_types), len(BusinessType))

    def test_content_calendar_scenario(self):
        s = content_calendar_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "content_calendar")
        self.assertEqual(s.target_business_types, [BusinessType.CONTENT_CREATOR])

    def test_digital_product_launch_scenario(self):
        s = digital_product_launch_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "digital_product_launch")
        self.assertEqual(s.target_business_types, [BusinessType.DIGITAL_PRODUCT])

    def test_feedback_analysis_scenario(self):
        s = feedback_analysis_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "feedback_analysis")
        self.assertEqual(s.target_business_types, [BusinessType.AI_TOOL_BUILDER])

    def test_consulting_proposal_scenario(self):
        s = consulting_proposal_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "consulting_proposal")
        self.assertEqual(s.target_business_types, [BusinessType.CONSULTANT])

    def test_ecommerce_ops_scenario(self):
        s = ecommerce_ops_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "ecommerce_ops")
        self.assertEqual(s.target_business_types, [BusinessType.ECOMMERCE])

    def test_project_deliverable_scenario(self):
        s = project_deliverable_scenario()
        self.assertIsInstance(s, ScenarioConfig)
        self.assertEqual(s.id, "project_deliverable")
        self.assertEqual(s.target_business_types, [BusinessType.CREATIVE_WORK])


# ==================== Edge Case Tests ====================


class TestEdgeCases(unittest.TestCase):
    """Test edge cases for scenario definitions."""

    def test_unknown_business_type_scenario_lookup(self):
        """Looking up scenarios for a valid but uncommon type should still work."""
        scenarios = [
            s
            for s in BUILT_IN_SCENARIOS.values()
            if BusinessType.AI_TOOL_BUILDER in s.target_business_types
        ]
        self.assertGreater(len(scenarios), 0)

    def test_scenario_with_multiple_business_types(self):
        """launch_product targets multiple business types."""
        scenario = BUILT_IN_SCENARIOS["launch_product"]
        self.assertGreater(len(scenario.target_business_types), 1)

    def test_empty_trigger_phrases_would_be_invalid(self):
        """All built-in scenarios should have non-empty trigger phrases."""
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertGreater(len(scenario.trigger_phrases), 0)

    def test_deliverable_template_sections_not_empty(self):
        """All built-in scenarios should have deliverable template with sections."""
        for sid, scenario in BUILT_IN_SCENARIOS.items():
            self.assertGreater(
                len(scenario.deliverable_template.sections),
                0,
                f"Scenario '{sid}' has empty deliverable sections",
            )


if __name__ == "__main__":
    unittest.main()
