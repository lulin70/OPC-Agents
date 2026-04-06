#!/usr/bin/env python3

import os
import json
import uuid
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class ExperienceType(Enum):
    """经验类型枚举（借鉴 Memory Classification Engine）"""
    USER_PREFERENCE = "user_preference"  # 用户偏好（配置/沟通风格/交付要求）
    CORRECTION = "correction"  # 纠正信号（用户纠正 Agent 判断）
    DECISION = "decision"  # 决策记录（任务中的关键决策）
    TASK_PATTERN = "task_pattern"  # 任务模式（反复出现的任务类型）
    AGENT_OPTIMIZATION = "agent_optimization"  # Agent 优化（成功/失败经验）
    SKILL_USAGE = "skill_usage"  # 技能使用（哪些技能有效/无效）


class ConflictType(Enum):
    """冲突类型"""
    NONE = "none"
    CONTENT_CONTRADICTION = "content_contradiction"  # 内容矛盾
    PREFERENCE_CONFLICT = "preference_conflict"  # 偏好冲突
    OUTDATED_INFO = "outdated_info"  # 信息过时


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
    # 新增：经验分类（借鉴 Memory Classification Engine）
    experience_type: str = "agent_optimization"  # 见 ExperienceType 枚举
    # 新增：权重系统
    weight: float = 1.0  # 0-1 之间的权重值
    confidence: float = 1.0  # 置信度
    usage_count: int = 0  # 使用次数
    source: str = "task_completion"  # 来源：task_completion/user_feedback/auto_optimization
    # 新增：冲突标记
    conflict_status: str = "none"  # none/pending/resolved
    conflict_with: List[str] = field(default_factory=list)  # 冲突的经验 ID 列表
    # 新增：遗忘机制
    last_used_at: str = ""
    decay_factor: float = 0.95  # 每日衰减系数

    def __post_init__(self):
        if not self.id:
            self.id = f"exp_{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.last_used_at:
            self.last_used_at = self.created_at


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
        # 计算经验权重
        item.weight = self._calculate_experience_weight(item)
        
        # 检测冲突
        conflicts = self._detect_conflicts(item)
        if conflicts:
            item.conflict_status = "pending"
            item.conflict_with = [c.id for c in conflicts]
            self._handle_conflict(item, conflicts)
        
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

    def find_similar_experiences(
        self,
        task_description: str,
        limit: int = 3,
        experience_type: Optional[str] = None,
        min_weight: float = 0.3
    ) -> List[ExperienceItem]:
        """
        查找相似经验（增强版）
        
        Args:
            task_description: 任务描述
            limit: 返回数量限制
            experience_type: 经验类型过滤（可选）
            min_weight: 最小权重阈值（默认 0.3）
        """
        if not task_description:
            return []
        
        keywords = re.findall(r'[\w]{2,}', task_description.lower())
        scored = []
        
        for exp in self.experiences.values():
            # 类型过滤
            if experience_type and exp.experience_type != experience_type:
                continue
            
            # 权重过滤
            current_weight = self._calculate_experience_weight(exp)
            if current_weight < min_weight:
                continue
            
            # 关键词匹配评分
            score = 0
            text = exp.task_description.lower()
            for kw in keywords:
                if kw in text:
                    score += 1
            
            if score > 0:
                # 综合评分 = 匹配度 60% + 权重 40%
                combined_score = (score * 0.6) + (current_weight * 10 * 0.4)
                scored.append((exp, combined_score))
                exp.usage_count += 1
                exp.last_used_at = datetime.now().isoformat()
        
        # 按综合评分排序
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
            # 应用遗忘机制：计算每个经验的当前权重
            for exp in self.experiences.values():
                exp.weight = self._calculate_experience_weight(exp)
            
            # 按权重排序，删除权重最低的
            sorted_items = sorted(
                self.experiences.items(),
                key=lambda x: x[1].weight
            )
            for exp_id, _ in sorted_items[:len(self.experiences) - self.MAX_EXPERIENCE]:
                del self.experiences[exp_id]

    def _calculate_experience_weight(self, experience: ExperienceItem) -> float:
        """
        计算经验权重（借鉴 Memory Classification Engine）
        
        权重 = 置信度 40% + 时效性 30% + 使用频率 20% + 来源可靠性 10%
        """
        # 1. 置信度 (40%)
        confidence_score = experience.confidence * 0.4
        
        # 2. 时效性 (30%) - 基于时间和衰减因子
        days_old = self._days_since(experience.created_at)
        time_decay = experience.decay_factor ** days_old
        time_score = time_decay * 0.3
        
        # 3. 使用频率 (20%) - 对数增长，避免过度加权
        import math
        usage_score = (math.log1p(experience.usage_count) / 5.0) * 0.2
        usage_score = min(usage_score, 0.2)  # 上限 0.2
        
        # 4. 来源可靠性 (10%)
        source_reliability = {
            "user_feedback": 1.0,      # 用户直接反馈，最可靠
            "task_completion": 0.8,    # 任务完成自动记录
            "auto_optimization": 0.6   # 自动优化推断
        }
        reliability_score = source_reliability.get(experience.source, 0.7) * 0.1
        
        total_weight = confidence_score + time_score + usage_score + reliability_score
        return min(max(total_weight, 0.0), 1.0)  # 限制在 0-1 之间

    def _days_since(self, date_str: str) -> int:
        """计算从指定日期到现在经过的天数"""
        if not date_str:
            return 0
        try:
            date = datetime.fromisoformat(date_str)
            delta = datetime.now() - date
            return delta.days
        except Exception:
            return 0

    def _detect_conflicts(self, new_experience: ExperienceItem) -> List[ExperienceItem]:
        """
        检测新经验与现有经验的冲突
        
        冲突类型：
        1. 内容矛盾：相同任务类型但建议相反
        2. 偏好冲突：用户偏好相互矛盾
        3. 信息过时：新经验替代旧经验
        """
        conflicts = []
        
        for existing in self.experiences.values():
            # 跳过已标记为冲突的
            if existing.conflict_status != "none":
                continue
            
            # 检查任务类型相似度
            if new_experience.task_type != existing.task_type:
                continue
            
            # 检查内容是否矛盾
            if self._is_contradictory(new_experience, existing):
                conflicts.append(existing)
        
        return conflicts

    def _is_contradictory(self, exp1: ExperienceItem, exp2: ExperienceItem) -> bool:
        """
        判断两个经验是否矛盾
        
        简单实现：检查 lessons_learned 和 best_practices 是否有相反的关键词
        实际应用中可以使用更复杂的语义分析
        """
        contradiction_pairs = [
            ("应该", "不应该"),
            ("推荐", "避免"),
            ("最好", "不要"),
            ("优先", "避免"),
            ("成功", "失败"),
        ]
        
        text1 = " ".join(exp1.lessons_learned + exp1.best_practices).lower()
        text2 = " ".join(exp2.lessons_learned + exp2.best_practices).lower()
        
        for pos, neg in contradiction_pairs:
            if (pos in text1 and neg in text2) or (neg in text1 and pos in text2):
                return True
        
        return False

    def _handle_conflict(self, new_experience: ExperienceItem, conflicts: List[ExperienceItem]):
        """
        处理经验冲突
        
        策略：
        1. 计算权重，保留高权重经验
        2. 如果权重相近，标记为待用户确认
        3. 新经验权重更高时，标记旧经验为过时
        """
        for existing in conflicts:
            existing_weight = self._calculate_experience_weight(existing)
            
            if new_experience.weight > existing_weight + 0.2:
                # 新经验明显更优，标记旧经验为过时
                existing.conflict_status = "resolved"
                existing.decay_factor = 0.5  # 加速遗忘
            elif abs(new_experience.weight - existing_weight) < 0.1:
                # 权重相近，保持冲突状态待用户确认
                pass  # 保持 pending 状态
            else:
                # 旧经验更优，降低新经验的置信度
                new_experience.confidence *= 0.7

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
