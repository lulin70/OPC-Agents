#!/usr/bin/env python3

import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime


class LoopController:

    def __init__(self, max_iterations: int = 100, storage_path: str = "data/loop_progress"):
        self.max_iterations = max_iterations
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.iteration_count = 0
        self._stopped = False
        self.loop_progress = self._load_progress()

    def _load_progress(self) -> Dict[str, Any]:
        path = self.storage_path / "loop_progress.json"
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "iteration_count": 0,
            "start_time": None,
            "last_update": None,
            "current_task": None,
            "tasks_completed": [],
            "tasks_failed": [],
            "tasks_pending": [],
            "exit_reason": None
        }

    def save_progress(self):
        self.loop_progress["last_update"] = datetime.now().isoformat()
        self.loop_progress["iteration_count"] = self.iteration_count
        path = self.storage_path / "loop_progress.json"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.loop_progress, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start_task(self, task_id: str, task_description: str) -> bool:
        self.loop_progress["current_task"] = task_id
        if task_id not in self.loop_progress["tasks_pending"]:
            self.loop_progress["tasks_pending"].append(task_id)
        if not self.loop_progress["start_time"]:
            self.loop_progress["start_time"] = datetime.now().isoformat()
        self.save_progress()
        return True

    def complete_task(self, task_id: str, success: bool = True,
                      artifacts: Dict[str, Any] = None) -> bool:
        if task_id in self.loop_progress["tasks_pending"]:
            self.loop_progress["tasks_pending"].remove(task_id)
        if success:
            if task_id not in self.loop_progress["tasks_completed"]:
                self.loop_progress["tasks_completed"].append(task_id)
        else:
            if task_id not in self.loop_progress["tasks_failed"]:
                self.loop_progress["tasks_failed"].append(task_id)
        self.loop_progress["current_task"] = None
        self.save_progress()
        return True

    def check_all_completed(self) -> bool:
        return len(self.loop_progress.get("tasks_pending", [])) == 0

    def should_exit(self) -> Tuple[bool, str]:
        if self._stopped:
            return True, "manual_stop"
        if self.iteration_count >= self.max_iterations:
            return True, "max_iterations_reached"
        if self.check_all_completed() and self.loop_progress.get("tasks_completed"):
            return True, "all_tasks_completed"
        return False, ""

    def stop(self):
        self._stopped = True

    def reset(self):
        self.iteration_count = 0
        self._stopped = False
        self.loop_progress = self._load_progress()

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            "tasks_completed": len(self.loop_progress.get("tasks_completed", [])),
            "tasks_failed": len(self.loop_progress.get("tasks_failed", [])),
            "tasks_pending": len(self.loop_progress.get("tasks_pending", [])),
            "start_time": self.loop_progress.get("start_time"),
            "last_update": self.loop_progress.get("last_update"),
            "exit_reason": self.loop_progress.get("exit_reason"),
            "stopped": self._stopped
        }
