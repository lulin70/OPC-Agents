#!/usr/bin/env python3

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field


@dataclass
class DAGTask:
    task_id: str
    step: int
    depends_on_steps: List[int] = field(default_factory=list)
    status: str = "pending"
    blocked_by: List[str] = field(default_factory=list)


class DAGScheduler:

    def __init__(self):
        self.tasks: Dict[str, DAGTask] = {}
        self.step_to_task_id: Dict[int, str] = {}
        self.completed: Set[str] = set()
        self.failed: Set[str] = set()
        self.blocked: Set[str] = set()

    def add_task(self, task_id: str, step: int, depends_on_steps: List[int] = None):
        self.tasks[task_id] = DAGTask(
            task_id=task_id, step=step,
            depends_on_steps=depends_on_steps or []
        )
        self.step_to_task_id[step] = task_id

    def get_ready_tasks(self) -> List[str]:
        ready = []
        for task_id, task in self.tasks.items():
            if task.status != "pending" or task_id in self.blocked:
                continue
            all_deps_met = True
            for dep_step in task.depends_on_steps:
                dep_task_id = self.step_to_task_id.get(dep_step)
                if dep_task_id and dep_task_id not in self.completed:
                    all_deps_met = False
                    break
            if all_deps_met:
                ready.append(task_id)
        return ready

    def on_task_completed(self, task_id: str) -> List[str]:
        self.completed.add(task_id)
        if task_id in self.tasks:
            self.tasks[task_id].status = "completed"
        newly_ready = []
        for tid in self.blocked:
            task = self.tasks.get(tid)
            if task:
                still_blocked = False
                for dep_step in task.depends_on_steps:
                    dep_tid = self.step_to_task_id.get(dep_step)
                    if dep_tid and dep_tid not in self.completed:
                        still_blocked = True
                        break
                if not still_blocked:
                    newly_ready.append(tid)
        for tid in newly_ready:
            self.blocked.discard(tid)
        return newly_ready

    def on_task_failed(self, task_id: str) -> List[str]:
        self.failed.add(task_id)
        if task_id in self.tasks:
            self.tasks[task_id].status = "failed"
        cascade_blocked = []
        for tid, task in self.tasks.items():
            if task.status == "pending" and tid not in self.blocked:
                for dep_step in task.depends_on_steps:
                    dep_tid = self.step_to_task_id.get(dep_step)
                    if dep_tid == task_id or dep_tid in self.failed:
                        self.blocked.add(tid)
                        task.blocked_by.append(task_id)
                        cascade_blocked.append(tid)
                        break
        return cascade_blocked

    def is_dag(self) -> bool:
        visited = set()
        rec_stack = set()

        def _dfs(task_id):
            visited.add(task_id)
            rec_stack.add(task_id)
            task = self.tasks.get(task_id)
            if task:
                for dep_step in task.depends_on_steps:
                    dep_tid = self.step_to_task_id.get(dep_step)
                    if dep_tid:
                        if dep_tid not in visited:
                            if not _dfs(dep_tid):
                                return False
                        elif dep_tid in rec_stack:
                            return False
            rec_stack.discard(task_id)
            return True

        for tid in self.tasks:
            if tid not in visited:
                if not _dfs(tid):
                    return False
        return True

    def get_blocked_tasks(self) -> List[str]:
        return list(self.blocked)

    def get_progress(self) -> Dict[str, Any]:
        total = len(self.tasks)
        completed_count = len(self.completed)
        failed_count = len(self.failed)
        blocked_count = len(self.blocked)
        pending_count = total - completed_count - failed_count - blocked_count
        return {
            "total": total,
            "completed": completed_count,
            "failed": failed_count,
            "blocked": blocked_count,
            "pending": pending_count,
            "progress_pct": round(completed_count / total * 100, 1) if total > 0 else 0
        }

    def get_state(self) -> Dict[str, Any]:
        return {
            "tasks": {tid: {"step": t.step, "status": t.status, "depends_on": t.depends_on_steps}
                     for tid, t in self.tasks.items()},
            "completed": list(self.completed),
            "failed": list(self.failed),
            "blocked": list(self.blocked)
        }
