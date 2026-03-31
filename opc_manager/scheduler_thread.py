#!/usr/bin/env python3

import re
import time
import json
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path


class SchedulerThread(threading.Thread):

    def __init__(self, task_executor=None, storage_path="data/schedules"):
        super().__init__(daemon=True)
        self.task_executor = task_executor
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.scheduled_tasks: List[Dict[str, Any]] = []
        self._stop_event = threading.Event()
        self.logger = logging.getLogger(__name__)
        self._load()

    def run(self):
        self.logger.info("[SchedulerThread] 启动")
        while not self._stop_event.is_set():
            self._check_and_execute()
            self._stop_event.wait(60)
        self.logger.info("[SchedulerThread] 停止")

    def stop(self):
        self._stop_event.set()

    def schedule_monitoring(self, task_id: str, monitoring_plan: List[Dict[str, Any]]):
        for mp in monitoring_plan:
            trigger = mp.get("trigger", "")
            interval_minutes = self._parse_interval(trigger)
            if interval_minutes and interval_minutes > 0:
                trigger_time = datetime.now() + timedelta(minutes=interval_minutes)
                self.scheduled_tasks.append({
                    "id": f"{task_id}_mon_{len(self.scheduled_tasks)}",
                    "task_id": task_id,
                    "type": "monitor",
                    "trigger_time": trigger_time.isoformat(),
                    "interval_minutes": interval_minutes,
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                })
                self.logger.info(f"[调度] 监控计划: {task_id} 将在{interval_minutes}分钟后检查")
        self._save()

    def schedule_report(self, task_id: str, trigger_time: datetime, description: str = ""):
        self.scheduled_tasks.append({
            "id": f"{task_id}_rpt_{len(self.scheduled_tasks)}",
            "task_id": task_id,
            "type": "report",
            "trigger_time": trigger_time.isoformat(),
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        })
        self.logger.info(f"[调度] 定时报告: {task_id} 将在{trigger_time.strftime('%H:%M')}推送")
        self._save()

    def parse_time_requirement(self, text: str) -> Optional[datetime]:
        now = datetime.now()
        patterns = [
            (r"(\d{1,2})点", "hour"),
            (r"下午(\d{1,2})点", "pm_hour"),
            (r"上午(\d{1,2})点", "am_hour"),
            (r"(\d{1,2})分钟(后|之后)", "minutes"),
            (r"(\d{1,2})小时(后|之后)", "hours"),
        ]
        for pattern, time_type in patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1))
                if time_type == "hour":
                    target = now.replace(hour=value, minute=0, second=0, microsecond=0)
                    if target < now:
                        target += timedelta(days=1)
                    return target
                elif time_type == "pm_hour":
                    target = now.replace(hour=value + 12 if value < 12 else value, minute=0, second=0, microsecond=0)
                    if target < now:
                        target += timedelta(days=1)
                    return target
                elif time_type == "am_hour":
                    target = now.replace(hour=value, minute=0, second=0, microsecond=0)
                    if target < now:
                        target += timedelta(days=1)
                    return target
                elif time_type == "minutes":
                    return now + timedelta(minutes=value)
                elif time_type == "hours":
                    return now + timedelta(hours=value)
        return None

    def _check_and_execute(self):
        now = datetime.now()
        pending = [t for t in self.scheduled_tasks if t["status"] == "pending"]
        for task in pending:
            try:
                trigger_time = datetime.fromisoformat(task["trigger_time"])
                if now >= trigger_time:
                    if task["type"] == "monitor":
                        self._execute_monitoring(task)
                    elif task["type"] == "report":
                        self._execute_report(task)
                    task["status"] = "completed"
                    task["executed_at"] = now.isoformat()
            except Exception as e:
                self.logger.warning(f"[调度] 执行失败: {task['id']}: {e}")
                task["status"] = "failed"
        self._save()

    def _execute_monitoring(self, task: Dict[str, Any]):
        task_id = task["task_id"]
        self.logger.info(f"[监控] 检查任务: {task_id}")
        if self.task_executor:
            status = self.task_executor.get_task_status(task_id)
            if status and status.get("state") == "failed":
                self.logger.warning(f"[监控] 任务{task_id}已失败，需要干预")
            elif status and status.get("state") == "running":
                progress = status.get("progress", 0)
                self.logger.info(f"[监控] 任务{task_id}进行中，进度: {progress}%")

    def _execute_report(self, task: Dict[str, Any]):
        task_id = task["task_id"]
        self.logger.info(f"[报告] 生成进度报告: {task_id}")
        report = {
            "task_id": task_id,
            "type": "progress_report",
            "timestamp": datetime.now().isoformat(),
            "description": task.get("description", "")
        }
        if self.task_executor:
            status = self.task_executor.get_task_status(task_id)
            if status:
                report["state"] = status.get("state", "unknown")
                report["progress"] = status.get("progress", 0)
        report_path = self.storage_path / f"report_{task_id}_{int(time.time())}.json"
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _parse_interval(self, trigger: str) -> Optional[int]:
        if not trigger:
            return None
        match = re.search(r"(\d+)\s*(分钟|minute|min|小时|hour|hr)", trigger, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            if "小时" in unit or "hour" in unit or "hr" in unit:
                return value * 60
            return value
        match = re.search(r"每\s*(\d+)\s*(分钟|minute|min|小时|hour|hr)", trigger, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            if "小时" in unit or "hour" in unit or "hr" in unit:
                return value * 60
            return value
        return None

    def get_scheduled_tasks(self, task_id: str = None) -> List[Dict]:
        if task_id:
            return [t for t in self.scheduled_tasks if t["task_id"] == task_id]
        return self.scheduled_tasks

    def _save(self):
        path = self.storage_path / "scheduled_tasks.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.scheduled_tasks, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load(self):
        path = self.storage_path / "scheduled_tasks.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.scheduled_tasks = json.load(f)
            except Exception:
                self.scheduled_tasks = []
