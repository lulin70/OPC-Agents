#!/usr/bin/env python3

import os
import json
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class KnowledgeItem:
    id: str = ""
    category: str = ""
    title: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    source_task: str = ""
    confidence: float = 1.0
    created_at: str = ""
    access_count: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = f"kb_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class ExperienceItem:
    id: str = ""
    task_type: str = ""
    task_description: str = ""
    success: bool = False
    lessons_learned: List[str] = field(default_factory=list)
    best_practices: List[str] = field(default_factory=list)
    execution_plan_summary: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = f"exp_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class UserProfile:
    preferences: Dict[str, str] = field(default_factory=dict)
    task_history: List[str] = field(default_factory=list)
    department_usage: Dict[str, int] = field(default_factory=dict)
    common_patterns: List[str] = field(default_factory=list)


class GlobalContext:
    MAX_KNOWLEDGE = 1000
    MAX_EXPERIENCE = 500
    MAX_HISTORY = 100

    def __init__(self, storage_path: str = "data/context"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.knowledge: Dict[str, KnowledgeItem] = {}
        self.experiences: Dict[str, ExperienceItem] = {}
        self.user_profile = UserProfile()
        self._load()

    def add_knowledge(self, item: KnowledgeItem):
        self.knowledge[item.id] = item
        self._evict_knowledge()
        self._save()

    def add_experience(self, item: ExperienceItem):
        self.experiences[item.id] = item
        self._evict_experience()
        self._save()

    def search_knowledge(self, keywords: List[str], limit: int = 5) -> List[KnowledgeItem]:
        if not keywords:
            return []
        scored = []
        for item in self.knowledge.values():
            score = 0
            text = (item.title + " " + item.content + " " + " ".join(item.tags)).lower()
            for kw in keywords:
                if kw.lower() in text:
                    score += 1
            if score > 0:
                scored.append((item, score))
                item.access_count += 1
        scored.sort(key=lambda x: (-x[1], -x[0].access_count))
        return [item for item, _ in scored[:limit]]

    def find_similar_experiences(self, task_description: str, limit: int = 3) -> List[ExperienceItem]:
        if not task_description:
            return []
        keywords = re.findall(r'[\w]{2,}', task_description.lower())
        scored = []
        for exp in self.experiences.values():
            score = 0
            text = exp.task_description.lower()
            for kw in keywords:
                if kw in text:
                    score += 1
            if score > 0:
                scored.append((exp, score))
        scored.sort(key=lambda x: -x[1])
        return [exp for exp, _ in scored[:limit]]

    def update_user_profile(self, task_type: str = None, department: str = None,
                            preference: str = None, pattern: str = None):
        if task_type:
            self.user_profile.task_history.append(task_type)
            if len(self.user_profile.task_history) > self.MAX_HISTORY:
                self.user_profile.task_history = self.user_profile.task_history[-self.MAX_HISTORY:]
        if department:
            self.user_profile.department_usage[department] = \
                self.user_profile.department_usage.get(department, 0) + 1
        if preference:
            self.user_profile.preferences[preference] = \
                self.user_profile.preferences.get(preference, 0) + 1
        if pattern and pattern not in self.user_profile.common_patterns:
            self.user_profile.common_patterns.append(pattern)
            if len(self.user_profile.common_patterns) > 50:
                self.user_profile.common_patterns = self.user_profile.common_patterns[-50:]
        self._save()

    def get_preferred_departments(self, limit: int = 3) -> List[str]:
        sorted_depts = sorted(self.user_profile.department_usage.items(), key=lambda x: -x[1])
        return [d for d, _ in sorted_depts[:limit]]

    def _evict_knowledge(self):
        if len(self.knowledge) > self.MAX_KNOWLEDGE:
            sorted_items = sorted(self.knowledge.values(), key=lambda x: x.access_count)
            for item in sorted_items[:len(self.knowledge) - self.MAX_KNOWLEDGE]:
                del self.knowledge[item.id]

    def _evict_experience(self):
        if len(self.experiences) > self.MAX_EXPERIENCE:
            sorted_items = sorted(self.experiences.values(), key=lambda x: x.created_at)
            for item in sorted_items[:len(self.experiences) - self.MAX_EXPERIENCE]:
                del self.experiences[item.id]

    def _save(self):
        data = {
            "knowledge": {k: asdict(v) for k, v in self.knowledge.items()},
            "experiences": {k: asdict(v) for k, v in self.experiences.items()},
            "user_profile": asdict(self.user_profile)
        }
        path = self.storage_path / "global_context.json"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load(self):
        path = self.storage_path / "global_context.json"
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k, v in data.get("knowledge", {}).items():
                self.knowledge[k] = KnowledgeItem(**v)
            for k, v in data.get("experiences", {}).items():
                self.experiences[k] = ExperienceItem(**v)
            up = data.get("user_profile", {})
            self.user_profile = UserProfile(
                preferences=up.get("preferences", {}),
                task_history=up.get("task_history", []),
                department_usage=up.get("department_usage", {}),
                common_patterns=up.get("common_patterns", [])
            )
        except Exception:
            pass


class TaskContext:
    def __init__(self, task_id: str, definition: Dict[str, Any] = None):
        self.task_id = task_id
        self.definition = definition or {}
        self.thought_records: List[Dict[str, Any]] = []
        self.artifacts: Dict[str, Any] = {}
        self.knowledge_refs: List[str] = []
        self.experience_refs: List[str] = []
        self.injected_context: str = ""

    def add_thought(self, role: str, thought_type: str, content: str):
        self.thought_records.append({
            "role": role, "type": thought_type, "content": content,
            "timestamp": datetime.now().isoformat()
        })

    def add_artifact(self, name: str, value: Any):
        self.artifacts[name] = value

    def set_injected_context(self, context_str: str):
        self.injected_context = context_str


class ContextSynchronizer:

    def __init__(self):
        self.sync_history: List[Dict[str, Any]] = []

    def sync_global_to_task(self, global_ctx: GlobalContext,
                           task_ctx: TaskContext,
                           task_description: str) -> Dict[str, Any]:
        result = {"direction": "global_to_task", "task_id": task_ctx.task_id,
                  "timestamp": datetime.now().isoformat(), "injections": []}

        keywords = re.findall(r'[\w]{2,}', task_description.lower())

        knowledge = global_ctx.search_knowledge(keywords, limit=5)
        for k in knowledge:
            task_ctx.knowledge_refs.append(k.id)
            result["injections"].append({"type": "knowledge", "id": k.id, "title": k.title})

        experiences = global_ctx.find_similar_experiences(task_description, limit=3)
        for e in experiences:
            task_ctx.experience_refs.append(e.id)
            result["injections"].append({"type": "experience", "id": e.id, "success": e.success})

        preferred_depts = global_ctx.get_preferred_departments()
        if preferred_depts:
            result["injections"].append({"type": "preferred_departments", "departments": preferred_depts})

        context_parts = []
        if knowledge:
            kb_text = "\n".join([f"- [{k.title}] {k.content[:200]}" for k in knowledge])
            context_parts.append(f"## 相关知识\n{kb_text}")
        if experiences:
            exp_text = "\n".join([f"- {'成功' if e.success else '失败'}: {e.task_description[:100]} | 经验: {'; '.join(e.lessons_learned[:2])}" for e in experiences])
            context_parts.append(f"## 历史经验\n{exp_text}")
        if preferred_depts:
            context_parts.append(f"## 用户常用部门\n{', '.join(preferred_depts)}")

        task_ctx.set_injected_context("\n\n".join(context_parts))
        self.sync_history.append(result)
        return result

    def sync_task_to_global(self, global_ctx: GlobalContext,
                           task_ctx: TaskContext,
                           success: bool) -> Dict[str, Any]:
        result = {"direction": "task_to_global", "task_id": task_ctx.task_id,
                  "timestamp": datetime.now().isoformat(), "updates": []}

        experience = self._extract_experience(task_ctx, success)
        if experience:
            global_ctx.add_experience(experience)
            result["updates"].append({"type": "experience", "id": experience.id})

        knowledge_items = self._extract_knowledge(task_ctx)
        for k in knowledge_items:
            global_ctx.add_knowledge(k)
            result["updates"].append({"type": "knowledge", "id": k.id})

        self.sync_history.append(result)
        return result

    def _extract_experience(self, task_ctx: TaskContext, success: bool) -> Optional[ExperienceItem]:
        desc = task_ctx.definition.get("task_name", "") or task_ctx.definition.get("description", "")
        if not desc:
            return None
        task_type = "general"
        for dept in ["engineering", "design", "marketing", "product", "testing"]:
            if dept in desc.lower() or dept in str(task_ctx.definition.get("department", "")).lower():
                task_type = dept
                break
        lessons = [f"Task {'succeeded' if success else 'failed'}: {desc[:100]}"]
        if task_ctx.artifacts:
            lessons.append(f"Produced {len(task_ctx.artifacts)} artifacts")
        return ExperienceItem(
            task_type=task_type, task_description=desc[:200],
            success=success, lessons_learned=lessons,
            best_practices=[desc[:100]] if success else [],
            execution_plan_summary=str(task_ctx.definition.get("execution_plan", ""))[:200]
        )

    def _extract_knowledge(self, task_ctx: TaskContext) -> List[KnowledgeItem]:
        items = []
        for name, value in task_ctx.artifacts.items():
            if isinstance(value, str) and len(value) > 100:
                items.append(KnowledgeItem(
                    category="artifact", title=f"Artifact: {name}",
                    content=value[:500], tags=[task_ctx.task_id],
                    source_task=task_ctx.task_id
                ))
        return items[:3]
