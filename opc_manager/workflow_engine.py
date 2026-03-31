#!/usr/bin/env python3

import os
import json
import copy
import uuid
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    description: str
    role_id: str
    action: str
    depends_on: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 2
    timeout: int = 3600
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class WorkflowDefinition:
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class WorkflowInstance:
    instance_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    handoff_history: List[Dict[str, str]] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: str = ""


class WorkflowEngine:

    def __init__(self, storage_path: str = "data/workflows"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.definitions: Dict[str, WorkflowDefinition] = {}
        self.instances: Dict[str, WorkflowInstance] = {}
        self.executors: Dict[str, Callable] = {}
        self.checkpoint_interval = 2
        self._load()

    def _load(self):
        defs_file = self.storage_path / "definitions.json"
        if defs_file.exists():
            try:
                with open(defs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for wf_id, wf_data in data.get('definitions', {}).items():
                    steps = []
                    for s in wf_data.get('steps', []):
                        steps.append(WorkflowStep(
                            step_id=s['step_id'], name=s['name'], description=s['description'],
                            role_id=s['role_id'], action=s['action'],
                            depends_on=s.get('depends_on', []),
                            conditions=s.get('conditions', {}),
                            inputs=s.get('inputs', {}),
                            retry_count=s.get('retry_count', 2),
                            status=StepStatus(s.get('status', 'pending'))
                        ))
                    self.definitions[wf_id] = WorkflowDefinition(
                        workflow_id=wf_id, name=wf_data['name'],
                        description=wf_data['description'], steps=steps,
                        variables=wf_data.get('variables', {}),
                        metadata=wf_data.get('metadata', {})
                    )
            except Exception:
                pass

    def _save(self):
        data = {'version': '1.0', 'updated_at': datetime.now().isoformat(), 'definitions': {}}
        for wf_id, d in self.definitions.items():
            data['definitions'][wf_id] = {
                'workflow_id': d.workflow_id, 'name': d.name, 'description': d.description,
                'steps': [{'step_id': s.step_id, 'name': s.name, 'description': s.description,
                           'role_id': s.role_id, 'action': s.action, 'depends_on': s.depends_on,
                           'conditions': s.conditions, 'inputs': s.inputs,
                           'retry_count': s.retry_count,
                           'status': s.status.value if isinstance(s.status, StepStatus) else s.status}
                          for s in d.steps],
                'variables': d.variables, 'metadata': d.metadata, 'created_at': d.created_at
            }
        try:
            with open(self.storage_path / "definitions.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def register_executor(self, action: str, executor: Callable):
        self.executors[action] = executor

    def create_workflow(self, name: str, description: str,
                        steps: List[WorkflowStep]) -> WorkflowDefinition:
        wf_id = f"wf_{uuid.uuid4().hex[:8]}"
        definition = WorkflowDefinition(workflow_id=wf_id, name=name,
                                         description=description, steps=steps)
        self.definitions[wf_id] = definition
        self._save()
        return definition

    def start_workflow(self, workflow_id: str,
                       variables: Dict[str, Any] = None) -> Optional[WorkflowInstance]:
        definition = self.definitions.get(workflow_id)
        if not definition:
            return None
        instance_id = f"{workflow_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        instance = WorkflowInstance(
            instance_id=instance_id, workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            variables=variables or {},
            started_at=datetime.now().isoformat()
        )
        self.instances[instance_id] = instance
        self._execute_next_step(instance)
        return instance

    def pause_workflow(self, instance_id: str) -> bool:
        instance = self.instances.get(instance_id)
        if not instance or instance.status != WorkflowStatus.RUNNING:
            return False
        instance.status = WorkflowStatus.PAUSED
        self._save_instance(instance)
        return True

    def resume_workflow(self, instance_id: str) -> bool:
        instance = self.instances.get(instance_id)
        if not instance or instance.status != WorkflowStatus.PAUSED:
            return False
        instance.status = WorkflowStatus.RUNNING
        self._execute_next_step(instance)
        return True

    def get_progress(self, instance_id: str) -> Dict[str, Any]:
        instance = self.instances.get(instance_id)
        if not instance:
            return {}
        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            return {}
        total = len(definition.steps)
        completed = len(instance.completed_steps)
        failed = len(instance.failed_steps)
        return {
            'instance_id': instance_id,
            'workflow_name': definition.name,
            'status': instance.status.value,
            'total_steps': total,
            'completed_steps': completed,
            'failed_steps': failed,
            'progress_pct': round(completed / total * 100, 1) if total > 0 else 0,
            'current_step': instance.current_step,
            'handoff_count': len(instance.handoff_history)
        }

    def get_active_instances(self) -> List[Dict[str, Any]]:
        return [self.get_progress(iid) for iid in self.instances
                if self.instances[iid].status in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED)]

    def _execute_next_step(self, instance: WorkflowInstance):
        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            instance.status = WorkflowStatus.FAILED
            return

        next_step = None
        for step in definition.steps:
            if step.step_id not in instance.completed_steps and step.step_id not in instance.failed_steps:
                deps_met = all(d in instance.completed_steps for d in step.depends_on)
                if deps_met:
                    next_step = step
                    break

        if not next_step:
            self._complete_workflow(instance)
            return

        if not self._check_conditions(next_step.conditions, instance.variables):
            next_step.status = StepStatus.SKIPPED
            instance.completed_steps.append(next_step.step_id)
            self._execute_next_step(instance)
            return

        instance.current_step = next_step.step_id
        next_step.status = StepStatus.RUNNING
        next_step.started_at = datetime.now().isoformat()

        try:
            executor = self.executors.get(next_step.action)
            if not executor:
                raise Exception(f"no executor for action: {next_step.action}")

            resolved_inputs = self._resolve_variables(next_step.inputs, instance.variables)
            result = executor(next_step, resolved_inputs, instance)

            next_step.status = StepStatus.COMPLETED
            next_step.result = result
            next_step.completed_at = datetime.now().isoformat()
            instance.completed_steps.append(next_step.step_id)

            if isinstance(result, dict):
                instance.results.update(result)
                instance.variables.update(result)

            if len(instance.completed_steps) % self.checkpoint_interval == 0:
                self._save_instance(instance)

            self._execute_next_step(instance)

        except Exception as e:
            if next_step.retry_count > 0:
                next_step.retry_count -= 1
                self._execute_next_step(instance)
            else:
                next_step.status = StepStatus.FAILED
                next_step.error = str(e)
                instance.failed_steps.append(next_step.step_id)
                instance.status = WorkflowStatus.FAILED
                instance.error = f"step {next_step.name} failed: {e}"
                self._save_instance(instance)

    def _check_conditions(self, conditions: Dict[str, Any], variables: Dict[str, Any]) -> bool:
        if not conditions:
            return True
        for key, expected in conditions.items():
            actual = variables.get(key)
            if actual != expected:
                return False
        return True

    def _resolve_variables(self, data: Any, variables: Dict[str, Any]) -> Any:
        if isinstance(data, str):
            for key, value in variables.items():
                data = data.replace(f"${{{key}}}", str(value))
            return data
        elif isinstance(data, dict):
            return {k: self._resolve_variables(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_variables(item, variables) for item in data]
        return data

    def _complete_workflow(self, instance: WorkflowInstance):
        instance.status = WorkflowStatus.COMPLETED
        instance.completed_at = datetime.now().isoformat()
        instance.current_step = None
        self._save_instance(instance)

    def _save_instance(self, instance: WorkflowInstance):
        path = self.storage_path / f"instance_{instance.instance_id}.json"
        try:
            data = {
                'instance_id': instance.instance_id,
                'workflow_id': instance.workflow_id,
                'status': instance.status.value,
                'current_step': instance.current_step,
                'completed_steps': instance.completed_steps,
                'failed_steps': instance.failed_steps,
                'variables': instance.variables,
                'results': instance.results,
                'handoff_history': instance.handoff_history,
                'started_at': instance.started_at,
                'completed_at': instance.completed_at,
                'error': instance.error
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_instance(self, instance_id: str) -> Optional[WorkflowInstance]:
        path = self.storage_path / f"instance_{instance_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return WorkflowInstance(
                instance_id=data['instance_id'],
                workflow_id=data['workflow_id'],
                status=WorkflowStatus(data['status']),
                current_step=data.get('current_step'),
                completed_steps=data.get('completed_steps', []),
                failed_steps=data.get('failed_steps', []),
                variables=data.get('variables', {}),
                results=data.get('results', {}),
                handoff_history=data.get('handoff_history', []),
                started_at=data.get('started_at'),
                completed_at=data.get('completed_at'),
                error=data.get('error', '')
            )
        except Exception:
            return None
