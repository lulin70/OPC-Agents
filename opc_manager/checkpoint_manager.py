#!/usr/bin/env python3

import os
import json
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Checkpoint:
    checkpoint_id: str = ""
    task_id: str = ""
    step_index: int = 0
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)
    remaining_steps: List[Dict[str, Any]] = field(default_factory=list)
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    dag_state: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self):
        if not self.checkpoint_id:
            self.checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class HandoffDocument:
    handoff_id: str = ""
    task_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    completed_work: List[str] = field(default_factory=list)
    current_state: Dict[str, Any] = field(default_factory=dict)
    next_steps: List[str] = field(default_factory=list)
    important_notes: List[str] = field(default_factory=list)
    context_for_next: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: str = ""

    def __post_init__(self):
        if not self.handoff_id:
            self.handoff_id = f"ho_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_markdown(self) -> str:
        md = f"# Handoff Document\n\n"
        md += f"- **Task ID**: {self.task_id}\n"
        md += f"- **From**: {self.from_agent} → **To**: {self.to_agent}\n"
        md += f"- **Time**: {self.created_at}\n"
        md += f"- **Confidence**: {self.confidence:.0%}\n\n"
        md += "## Completed Work\n"
        for w in self.completed_work:
            md += f"- {w}\n"
        md += "\n## Current State\n"
        for k, v in self.current_state.items():
            md += f"- **{k}**: {v}\n"
        md += "\n## Next Steps\n"
        for s in self.next_steps:
            md += f"- {s}\n"
        if self.important_notes:
            md += "\n## Important Notes\n"
            for n in self.important_notes:
                md += f"- {n}\n"
        return md


class CheckpointManager:

    def __init__(self, storage_path: str = "data/checkpoints"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, task_id: str, step_index: int,
                        completed: List[Dict], remaining: List[Dict],
                        context: Dict[str, Any], dag_state: Dict[str, Any] = None):
        cp = Checkpoint(
            task_id=task_id, step_index=step_index,
            completed_steps=completed, remaining_steps=remaining,
            context_snapshot=context, dag_state=dag_state or {}
        )
        path = self.storage_path / f"{task_id}.json"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(asdict(cp), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return cp

    def load_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        path = self.storage_path / f"{task_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Checkpoint(**data)
        except Exception:
            return None

    def get_resumable_tasks(self) -> List[str]:
        resumable = []
        for path in self.storage_path.glob("*.json"):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get("remaining_steps"):
                    resumable.append(data["task_id"])
            except Exception:
                pass
        return resumable

    def create_handoff(self, task_id: str, from_agent: str, to_agent: str,
                        completed_work: List[str], context: Dict[str, Any] = None,
                        next_steps: List[str] = None) -> HandoffDocument:
        doc = HandoffDocument(
            task_id=task_id, from_agent=from_agent, to_agent=to_agent,
            completed_work=completed_work,
            current_state={"status": "in_progress", "artifacts": list((context or {}).keys())},
            next_steps=next_steps or [],
            context_for_next=context or {}
        )
        handoff_path = self.storage_path / f"{task_id}_handoff.md"
        try:
            with open(handoff_path, 'w', encoding='utf-8') as f:
                f.write(doc.to_markdown())
        except Exception:
            pass
        return doc

    def delete_checkpoint(self, task_id: str):
        for suffix in ["", "_handoff.md"]:
            path = self.storage_path / f"{task_id}{suffix}"
            if path.exists():
                try:
                    os.remove(str(path))
                except Exception:
                    pass
