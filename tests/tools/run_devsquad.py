#!/usr/bin/env python3
"""DevSquad dispatch: OPC-Agents architecture review + test plan"""

import sys, os

DEV_SQUAD_ROOT = os.path.expanduser("~/.trae/skills/devsquad")
sys.path.insert(0, DEV_SQUAD_ROOT)

from scripts.collaboration.dispatcher import MultiAgentDispatcher

TASK_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docs/internal/devsquad_task.md"
)

with open(TASK_FILE, "r") as f:
    task = f.read()

print("=" * 60)
print("DevSquad Multi-Role Dispatch: architect + tester")
print("=" * 60)

disp = MultiAgentDispatcher()
result = disp.dispatch(task, roles=["architect", "tester"], mode="parallel")

print("\n" + "=" * 60)
print("RESULT:")
print("=" * 60)
print(result.to_markdown())

disp.shutdown()
