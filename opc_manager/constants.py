"""Shared constants for AgentLoop and TaskOrchestrator.

This module eliminates the circular dependency between agent_loop.py
and task_orchestrator.py by providing a single source of truth for
configuration constants.
"""

import os

# Input limits
MAX_USER_INPUT_LENGTH = 10000

# Retry and execution limits
MAX_RETRY_PER_STEP = int(os.environ.get("OPC_MAX_RETRY_PER_STEP", "3"))
MAX_CONTEXT_HISTORY = int(os.environ.get("OPC_MAX_CONTEXT_HISTORY", "100"))
MAX_REFLECT_ROUNDS = int(os.environ.get("OPC_MAX_REFLECT_ROUNDS", "3"))
RETRY_BACKOFF_BASE = 2
RETRY_BACKOFF_CAP = 10

# Timeout settings
PAUSE_TIMEOUT_SECONDS = int(os.environ.get("OPC_PAUSE_TIMEOUT_SECONDS", "1800"))
AGENT_LOOP_TIMEOUT_SECONDS = int(
    os.environ.get("OPC_AGENT_LOOP_TIMEOUT_SECONDS", "120")
)

# Quality thresholds
QUALITY_THRESHOLD_CORRECTION = 0.6
QUALITY_THRESHOLD_CONSENSUS = 0.7
MAX_CORRECTION_ATTEMPTS = 2

# Parallel voting configuration [S2-T2]
PARALLEL_VOTE_TIMEOUT = int(os.environ.get("OPC_PARALLEL_VOTE_TIMEOUT", "30"))
PARALLEL_VOTE_ENABLED = (
    os.environ.get("OPC_PARALLEL_VOTE_ENABLED", "true").lower() == "true"
)

# Critical decision points (irreversible operations) [S2-T4]
# finance is included because financial writes are data-persistent and irreversible.
CRITICAL_DECISION_SKILLS = {"email", "report", "finance"}
CRITICAL_DECISION_ACTIONS = {
    "send",
    "execute_operation",
    "send_notification",
    "send_email",
}

# Serial consensus fallback timeout (per opinion)
SERIAL_OP_TIMEOUT = 15
