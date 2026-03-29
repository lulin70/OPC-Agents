#!/usr/bin/env python3
"""
Solution Library for OPC-Agents

Stores and retrieves task solutions for reuse.
"""

import time
import json
import logging
import threading
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


import hashlib


@dataclass
class Solution:
    """解决方案"""
    id: str
    name: str
    task_type: str
    problem_description: str
    solution_description: str
    steps: List[str] = field(default_factory=list)
    code_snippets: Dict[str, str] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    usage_count: int = 0
    success_rate: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type,
            "problem_description": self.problem_description,
            "solution_description": self.solution_description,
            "steps": self.steps,
            "code_snippets": self.code_snippets,
            "parameters": self.parameters,
            "results": self.results,
            "tags": self.tags,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Solution':
        return cls(
            id=data["id"],
            name=data["name"],
            task_type=data.get("task_type", ""),
            problem_description=data.get("problem_description", ""),
            solution_description=data.get("solution_description", ""),
            steps=data.get("steps", []),
            code_snippets=data.get("code_snippets", {}),
            parameters=data.get("parameters", {}),
            results=data.get("results", {}),
            tags=data.get("tags", []),
            confidence=data.get("confidence", 1.0),
            usage_count=data.get("usage_count", 0),
            success_rate=data.get("success_rate", 1.0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )


    
    def record_usage(self, success: bool):
        """记录使用情况"""
        self.usage_count += 1
        
        # 更新成功率
        if success:
            self.success_rate = (self.success_rate * (self.usage_count - 1) + 1) / self.usage_count
        else:
            self.success_rate = (self.success_rate * (self.usage_count - 1)) / self.usage_count
        
        self.updated_at = time.time()


class SolutionLibrary:
    """解决方案库
    
    存储和检索可复用的任务解决方案。
    """
    
    def __init__(self, storage_path: str = "data/knowledge"):
        """初始化解决方案库
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.logger = logging.getLogger("OPC-Agents.SolutionLibrary")
        
        # 内存缓存
        self._solutions: Dict[str, Solution] = {}
        self._task_type_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        
        # 锁
        self._lock = threading.Lock()
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载已有解决方案
        self._load_all()
        
        self.logger.info(f"SolutionLibrary initialized at {storage_path}")
    
    def _load_all(self):
        """加载所有解决方案"""
        solution_file = os.path.join(self.storage_path, "solutions.json")
        if os.path.exists(solution_file):
            try:
                with open(solution_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for sol_data in data.get("solutions", []):
                    solution = Solution.from_dict(sol_data)
                    self._solutions[solution.id] = solution
                    
                    # 更新索引
                    self._update_indexes(solution)
                
                self.logger.info(f"Loaded {len(self._solutions)} solutions")
            except Exception as e:
                self.logger.error(f"Failed to load solutions: {e}")
    
    def _update_indexes(self, solution: Solution):
        """更新索引"""
        # 任务类型索引
        if solution.task_type not in self._task_type_index:
            self._task_type_index[solution.task_type] = []
        self._task_type_index[solution.task_type].append(solution.id)
        
        # 标签索引
        for tag in solution.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            self._tag_index[tag].append(solution.id)
    
    def _save_all(self):
        """保存所有解决方案"""
        solution_file = os.path.join(self.storage_path, "solutions.json")
        try:
            data = {
                "solutions": [s.to_dict() for s in self._solutions.values()],
                "updated_at": time.time()
            }
            with open(solution_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save solutions: {e}")
    
    def add_solution(self, solution: Solution) -> bool:
        """添加解决方案
        
        Args:
            solution: 解决方案
            
        Returns:
            是否成功
        """
        with self._lock:
            if solution.id in self._solutions:
                self.logger.warning(f"Solution already exists: {solution.id}")
                return False
            
            self._solutions[solution.id] = solution
            self._update_indexes(solution)
            self._save_all()
            
            self.logger.info(f"Added solution: {solution.id}")
            return True
    
    def update_solution(self, solution: Solution) -> bool:
        """更新解决方案"""
        with self._lock:
            if solution.id not in self._solutions:
                self.logger.warning(f"Solution not found: {solution.id}")
                return False
            
            
            old_sol = self._solutions[solution.id]
            
            # 更新索引(移除旧的)
            if old_sol.task_type != solution.task_type:
                if old_sol.id in self._task_type_index.get(old_sol.task_type, []):
                    self._task_type_index[old_sol.task_type].remove(old_sol.id)
            
            for old_tag in old_sol.tags:
                if old_tag not in solution.tags:
                    if old_sol.id in self._tag_index.get(old_tag, []):
                        self._tag_index[old_tag].remove(old_sol.id)
            
            # 更新条目
            self._solutions[solution.id] = solution
            self._update_indexes(solution)
            self._save_all()
            
            self.logger.info(f"Updated solution: {solution.id}")
            return True
    
    def delete_solution(self, solution_id: str) -> bool:
        """删除解决方案"""
        with self._lock:
            if solution_id not in self._solutions:
                return False
            
            solution = self._solutions[solution_id]
            
            # 从索引中移除
            if solution.task_type in self._task_type_index:
                self._task_type_index[solution.task_type].discard(solution_id)
            
            for tag in solution.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(solution_id)
            
            # 删除条目
            del self._solutions[solution_id]
            self._save_all()
            
            self.logger.info(f"Deleted solution: {solution_id}")
            return True
    
    def get_solution(self, solution_id: str) -> Optional[Solution]:
        """获取解决方案"""
        with self._lock:
            return self._solutions.get(solution_id)
    
    def get_solutions_by_task_type(self, task_type: str) -> List[Solution]:
        """按任务类型获取解决方案"""
        with self._lock:
            sol_ids = self._task_type_index.get(task_type, [])
            return [self._solutions[sid] for sid in sol_ids if sid in self._solutions]
    
    def get_solutions_by_tags(self, tags: List[str], match_all: bool = True) -> List[Solution]:
        """按标签获取解决方案"""
        with self._lock:
            if not tags:
                return []
            
            if match_all:
                # 必须匹配所有标签
                matching_ids = None
                for tag in tags:
                    tag_solutions = set(self._tag_index.get(tag, []))
                    if matching_ids is None:
                        matching_ids = tag_solutions
                    else:
                        matching_ids = matching_ids & tag_solutions
                    
                    if not matching_ids:
                        return []
                
                return [self._solutions[sid] for sid in matching_ids if sid in self._solutions]
            else:
                # 匹配任一标签
                matching_ids = set()
                for tag in tags:
                    for sid in self._tag_index.get(tag, []):
                        matching_ids.add(sid)
                
                return [self._solutions[sid] for sid in matching_ids if sid in self._solutions]
    
    def search_solutions(self, query: str, limit: int = 10) -> List[Solution]:
        """搜索解决方案"""
        query_lower = query.lower()
        
        with self._lock:
            results = []
            for solution in self._solutions.values():
                if (query_lower in solution.name.lower() or
                    query_lower in solution.problem_description.lower() or
                    query_lower in solution.solution_description.lower()):
                    results.append(solution)
                    if len(results) >= limit:
                        break
            
            return results
    
    def get_top_solutions(self, limit: int = 10) -> List[Solution]:
        """获取最常用的解决方案"""
        with self._lock:
            sorted_solutions = sorted(
                self._solutions.values(),
                key=lambda s: s.usage_count,
                reverse=True
            )
            return sorted_solutions[:limit]
    
    def get_best_solutions(self, limit: int = 10) -> List[Solution]:
        """获取成功率最高的解决方案"""
        with self._lock:
            sorted_solutions = sorted(
                self._solutions.values(),
                key=lambda s: (s.success_rate, s.usage_count),
                reverse=True
            )
            return sorted_solutions[:limit]
    
    def record_solution_usage(self, solution_id: str, success: bool):
        """记录解决方案使用情况"""
        with self._lock:
            solution = self._solutions.get(solution_id)
            if solution:
                solution.record_usage(success)
                self._save_all()
    
    def get_similar_solutions(self, problem_description: str, limit: int = 5) -> List[Solution]:
        """获取相似问题的解决方案
        
        Args:
            problem_description: 问题描述
            limit: 返回数量限制
            
        Returns:
            相似解决方案列表
        """
        # 皂时使用简单的关键词匹配
        keywords = set(problem_description.lower().split())
        
        with self._lock:
            scored_solutions = []
            
            for solution in self._solutions.values():
                # 计算关键词匹配分数
                solution_keywords = set(solution.problem_description.lower().split())
                common_keywords = keywords & solution_keywords
                
                if common_keywords:
                    score = len(common_keywords) * solution.confidence * solution.success_rate
                    scored_solutions.append((score, solution))
            
            # 按分数排序
            scored_solutions.sort(key=lambda x: x[0], reverse=True)
            
            return [s for _, s in scored_solutions[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            total = len(self._solutions)
            total_usage = sum(s.usage_count for s in self._solutions.values())
            avg_success_rate = sum(s.success_rate for s in self._solutions.values()) / total if total > 0 else 0
            
            return {
                "total_solutions": total,
                "total_usage": total_usage,
                "average_success_rate": avg_success_rate,
                "task_types_with_solutions": len(self._task_type_index),
                "tags_with_solutions": len(self._tag_index)
            }
