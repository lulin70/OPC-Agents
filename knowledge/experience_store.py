#!/usr/bin/env python3
"""
Experience Store for OPC-Agents

Stores agent experiences and lessons learned from task execution.
"""

import time
import json
import logging
import threading
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Experience:
    """经验条目"""
    id: str
    agent_name: str
    task_id: str
    task_type: str
    description: str
    approach: str
    outcome: str
    lessons_learned: List[str] = field(default_factory=list)
    success: bool = True
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "description": self.description,
            "approach": self.approach,
            "outcome": self.outcome,
            "lessons_learned": self.lessons_learned,
            "success": self.success,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "access_count": self.access_count
        }


    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Experience':
        return cls(
            id=data["id"],
            agent_name=data["agent_name"],
            task_id=data["task_id"],
            task_type=data.get("task_type", ""),
            description=data.get("description", ""),
            approach=data.get("approach", ""),
            outcome=data.get("outcome", ""),
            lessons_learned=data.get("lessons_learned", []),
            success=data.get("success", True),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("created_at", time.time()),
            accessed_at=data.get("access_at", time.time())
        )


    
    def update_access(self):
        """更新访问时间"""
        self.accessed_at = time.time()


    
    def add_lesson(self, lesson: str):
        """添加经验教训"""
        if lesson not in self.lessons_learned:
            self.lessons_learned.append(lesson)


class ExperienceStore:
    """经验存储
    
    存储Agent在任务执行中获得的经验和教训。
    """
    
    def __init__(self, storage_path: str = "data/knowledge"):
        """初始化经验存储
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.logger = logging.getLogger("OPC-Agents.ExperienceStore")
        
        # 内存缓存
        self._experiences: Dict[str, Experience] = {}
        self._agent_index: Dict[str, List[str]] = {}
        self._task_type_index: Dict[str, List[str]] = {}
        
        # 锁
        self._lock = threading.Lock()
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载已有经验
        self._load_all()
        
        self.logger.info(f"ExperienceStore initialized at {storage_path}")
    
    def _load_all(self):
        """加载所有经验"""
        experience_file = os.path.join(self.storage_path, "experiences.json")
        if os.path.exists(experience_file):
            try:
                with open(experience_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for exp_data in data.get("experiences", []):
                    experience = Experience.from_dict(exp_data)
                    self._experiences[experience.id] = experience
                    
                    # 更新索引
                    self._update_indexes(experience)
                
                self.logger.info(f"Loaded {len(self._experiences)} experiences")
            except Exception as e:
                self.logger.error(f"Failed to load experiences: {e}")
    
    def _update_indexes(self, experience: Experience):
        """更新索引"""
        # Agent索引
        if experience.agent_name not in self._agent_index:
            self._agent_index[experience.agent_name] = []
        self._agent_index[experience.agent_name].append(experience.id)
        
        # 任务类型索引
        if experience.task_type not in self._task_type_index:
            self._task_type_index[experience.task_type] = []
        self._task_type_index[experience.task_type].append(experience.id)
    
    def _save_all(self):
        """保存所有经验"""
        experience_file = os.path.join(self.storage_path, "experiences.json")
        try:
            data = {
                "experiences": [e.to_dict() for e in self._experiences.values()],
                "updated_at": time.time()
            }
            with open(experience_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save experiences: {e}")
    
    def add_experience(self, experience: Experience) -> bool:
        """添加经验
        
        Args:
            experience: 经验条目
            
        Returns:
            是否成功
        """
        with self._lock:
            if experience.id in self._experiences:
                self.logger.warning(f"Experience already exists: {experience.id}")
                return False
            
            self._experiences[experience.id] = experience
            self._update_indexes(experience)
            self._save_all()
            
            self.logger.info(f"Added experience: {experience.id}")
            return True
    
    def update_experience(self, experience: Experience) -> bool:
        """更新经验
        
        Args:
            experience: 经验条目
            
        Returns:
            是否成功
        """
        with self._lock:
            if experience.id not in self._experiences:
                self.logger.warning(f"Experience not found: {experience.id}")
                return False
            
            
            old_exp = self._experiences[experience.id]
            
            # 更新索引（移除旧的)
            if old_exp.agent_name != experience.agent_name:
                if old_exp.id in self._agent_index.get(old_exp.agent_name, []):
                    self._agent_index[old_exp.agent_name].remove(old_exp.id)
            
            if old_exp.task_type != experience.task_type:
                if old_exp.id in self._task_type_index.get(old_exp.task_type, []):
                    self._task_type_index[old_exp.task_type].remove(old_exp.id)
            
            # 更新条目
            self._experiences[experience.id] = experience
            self._update_indexes(experience)
            self._save_all()
            
            self.logger.info(f"Updated experience: {experience.id}")
            return True
    
    def get_experience(self, experience_id: str) -> Optional[Experience]:
        """获取经验"""
        with self._lock:
            exp = self._experiences.get(experience_id)
            if exp:
                exp.update_access()
            return exp
    
    def get_agent_experiences(self, agent_name: str) -> List[Experience]:
        """获取Agent的经验"""
        with self._lock:
            exp_ids = self._agent_index.get(agent_name, [])
            return [self._experiences[eid] for eid in exp_ids if eid in self._experiences]
    
    def get_task_type_experiences(self, task_type: str) -> List[Experience]:
        """获取任务类型的经验"""
        with self._lock:
            exp_ids = self._task_type_index.get(task_type, [])
            return [self._experiences[eid] for eid in exp_ids if eid in self._experiences]
    
    def get_successful_experiences(self) limit: int = 10) -> List[Experience]:
        """获取成功经验"""
        with self._lock:
            return [e for e in self._experiences.values() if e.success][:limit]
    
    def get_recent_experiences(self, limit: int = 10) -> List[Experience]:
        """获取最近经验"""
        with self._lock:
            sorted_exps = sorted(
                self._experiences.values(),
                key=lambda e: e.created_at,
                reverse=True
            )
            return sorted_exps[:limit]
    
    def search_by_description(self, query: str, limit: int = 10) -> List[Experience]:
        """按描述搜索"""
        query_lower = query.lower()
        
        with self._lock:
            results = []
            for exp in self._experiences.values():
                if (query_lower in exp.description.lower() or
                    query_lower in exp.approach.lower() or
                    query_lower in exp.outcome.lower()):
                    results.append(exp)
                    if len(results) >= limit:
                        break
            
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._experiences)
            successful = sum(1 for e in self._experiences.values() if e.success)
            by_agent = len(self._agent_index)
            by_task_type = len(self._task_type_index)
            
            return {
                "total_experiences": total,
                "successful_experiences": successful,
                "failed_experiences": total - successful,
                "agents_with_experience": by_agent,
                "task_types_with_experience": by_task_type
            }
