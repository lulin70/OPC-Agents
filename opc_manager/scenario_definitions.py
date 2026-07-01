"""
Scenario Definitions - Data structures and built-in scenario configurations.

Split from scenario_engine_v2.py for separation of concerns:
- Definition layer: dataclasses, templates, built-in scenario configs
- Execution layer: matching, selection, running (scenario_engine_v2.py)

This module now serves as a facade. It defines the 5 core dataclasses
(OutputSpec, DeliverableTemplate, WorkflowStep, ScenarioConfig, ScenarioResult)
and lazily re-exports the built-in factory functions + BUILT_IN_SCENARIOS from
scenario_definitions_builtin.py via PEP 562 __getattr__. This keeps backward
compatibility for existing imports such as:
    from opc_manager.scenario_definitions import (
        ScenarioConfig, BUILT_IN_SCENARIOS, launch_product_scenario, ...
    )

Dependency direction (one-way, no circular import at load time):
    scenario_definitions_builtin.py  -->  scenario_definitions.py  (dataclasses)
    scenario_definitions.py  --[lazy PEP 562]-->  scenario_definitions_builtin.py
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from opc_manager.business_types import BusinessType


@dataclass
class OutputSpec:
    """Output specification definition"""

    name: str
    format: str
    includes: List[str] = field(default_factory=list)


@dataclass
class DeliverableTemplate:
    """Deliverable template"""

    name: str
    sections: List[str]
    format: str = "Multi-format"


@dataclass
class WorkflowStep:
    """Workflow step definition"""

    step_id: int
    name: str
    type: str
    description: str
    estimated_duration: str
    dependencies: List[int] = field(default_factory=list)
    output_spec: Optional[OutputSpec] = None
    executor: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "estimated_duration": self.estimated_duration,
            "dependencies": self.dependencies,
            "output_spec": (
                {
                    "name": self.output_spec.name,
                    "format": self.output_spec.format,
                    "includes": self.output_spec.includes,
                }
                if self.output_spec
                else None
            ),
            "executor": self.executor,
        }


@dataclass
class ScenarioConfig:
    """Scenario configuration - Complete scenario definition"""

    id: str
    name: str
    description: str
    trigger_phrases: List[str]
    target_business_types: List[BusinessType]
    workflow_steps: List[WorkflowStep]
    estimated_duration: str
    deliverable_template: DeliverableTemplate
    confidence_threshold: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format (V1 interface compatible)"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_phrases": self.trigger_phrases,
            "target_business_types": [bt.value for bt in self.target_business_types],
            "workflow_steps": [step.to_dict() for step in self.workflow_steps],
            "estimated_duration": self.estimated_duration,
            "deliverable_template": {
                "name": self.deliverable_template.name,
                "sections": self.deliverable_template.sections,
                "format": self.deliverable_template.format,
            },
            "confidence_threshold": self.confidence_threshold,
        }


@dataclass
class ScenarioResult:
    """Scenario processing result"""

    matched: bool
    scenario_id: Optional[str] = None
    scenario_config: Optional[ScenarioConfig] = None
    confidence: float = 0.0
    detected_business_type: Optional[BusinessType] = None
    persona: Optional[Dict[str, Any]] = None
    workflow: Optional[List[Dict[str, Any]]] = None
    suggestion: Optional[str] = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        result: Dict[str, Any] = {"matched": self.matched, "confidence": self.confidence}
        if self.matched:
            result.update(
                {
                    "scenario_id": self.scenario_id,
                    "scenario_config": (
                        self.scenario_config.to_dict() if self.scenario_config else None
                    ),
                    "detected_business_type": (
                        self.detected_business_type.value
                        if self.detected_business_type
                        else None
                    ),
                    "persona": self.persona,
                    "workflow": self.workflow,
                }
            )
        else:
            result["suggestion"] = self.suggestion
        if self.candidates:
            result["candidates"] = self.candidates
        return result


# ==================== Lazy re-export (PEP 562) ====================
#
# The 9 built-in scenario factory functions and the BUILT_IN_SCENARIOS registry
# live in scenario_definitions_builtin.py (which imports the dataclasses above
# from this module). To preserve backward compatibility for callers that do
# `from opc_manager.scenario_definitions import launch_product_scenario` or
# `from opc_manager.scenario_definitions import BUILT_IN_SCENARIOS`, we lazily
# re-export those symbols here. The import is deferred to attribute-access time
# so there is no circular import at module load time.


# Public symbols defined directly in this module. Anything not listed here will
# be resolved via __getattr__ below.
__all__ = [
    "OutputSpec",
    "DeliverableTemplate",
    "WorkflowStep",
    "ScenarioConfig",
    "ScenarioResult",
    # Re-exported from scenario_definitions_builtin:
    "launch_product_scenario",
    "write_report_scenario",
    "organize_meeting_scenario",
    "content_calendar_scenario",
    "digital_product_launch_scenario",
    "feedback_analysis_scenario",
    "consulting_proposal_scenario",
    "ecommerce_ops_scenario",
    "project_deliverable_scenario",
    "BUILT_IN_SCENARIOS",
]


# Locally-defined names that __getattr__ must never shadow.
_LOCAL_NAMES = frozenset(
    {
        "OutputSpec",
        "DeliverableTemplate",
        "WorkflowStep",
        "ScenarioConfig",
        "ScenarioResult",
        "BusinessType",
        "__all__",
        "__getattr__",
        "_LOCAL_NAMES",
    }
)


def __getattr__(name: str):
    """Lazy re-export from scenario_definitions_builtin to maintain backward
    compatibility. Only invoked when the attribute is not found normally.

    PEP 562: module-level __getattr__ is called for missing attributes, so
    `from opc_manager.scenario_definitions import launch_product_scenario`
    triggers this function, which imports the builtin module on demand.
    """
    if name.startswith("__"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name in _LOCAL_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from opc_manager import scenario_definitions_builtin

    try:
        return getattr(scenario_definitions_builtin, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Return a complete list of public attributes for tab-completion / dir()."""
    return sorted(set(list(globals().keys()) + list(__all__)))
