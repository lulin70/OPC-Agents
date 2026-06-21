"""Agent Context and State definitions.

Extracted from agent_loop.py to avoid circular imports.
These are pure data structures with no dependencies on other agent modules.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    CONFIRMATION_NEEDED = "confirmation_needed"


@dataclass
class AgentContext:
    task_id: str
    user_input: str
    state: AgentState = AgentState.IDLE
    intent: Optional[object] = None  # Intent from strategist_brain
    plan: Optional[object] = None  # ExecutionPlan from strategist_brain
    execution_results: List[Dict] = field(default_factory=list)
    current_step: int = 0
    retry_count: int = 0
    step_retry_counts: Dict[str, int] = field(default_factory=dict)
    cancel_requested: bool = False
    session_id: Optional[str] = None
    correction_count: int = 0
    paused_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_state(self, new_state: AgentState) -> None:
        self.state = new_state
