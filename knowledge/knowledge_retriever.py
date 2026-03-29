#!/usr/bin/env python3
"""
Knowledge Retriever for OPC-Agents

Retrieves relevant knowledge from the knowledge base.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass


@dataclass
class RetrievalResult:
    """检索结果"""
    query: str
    knowledge_entries: List[Any] = field(default_factory=list)
    experiences: List[Any] = field(default_factory=list)
    solutions: List[Any] = field(default_factory=list)
    relevance_score: float = 0.0
    retrieved_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "knowledge_entries": [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.knowledge_entries],
            "experiences": [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.experiences],
            "solutions": [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.solutions],
            "relevance_score": self.relevance_score,
            "retrieved_at": self.retrieved_at
        }


class KnowledgeRetriever:
    """知识检索器
    
    从知识库中检索相关知识。
    """
    
    def __init__(self, knowledge_base=None, experience_store=None, solution_library=None):
        """初始化知识检索器
        
        Args:
            knowledge_base: 知识库实例
            experience_store: 经验存储实例
            solution_library: 解决方案库实例
        """
        self.knowledge_base = knowledge_base
        self.experience_store = experience_store
        self.solution_library = solution_library
        self.logger = logging.getLogger("OPC-Agents.KnowledgeRetriever")
        
        # 缓存
        self._cache: Dict[str, Tuple[float, RetrievalResult]] = {}
        self._cache_lock = threading.Lock()
        self._cache_ttl = 300  # 5分钟
    
        self.logger.info("KnowledgeRetriever initialized")
    
    def retrieve(self, query: str, context: Dict[str, Any] = None,
                include_knowledge: bool = True,
                include_experience: bool = True,
                include_solutions: bool = True,
                max_results: int = 10) -> RetrievalResult:
        """检索相关知识
        
        Args:
            query: 查询字符串
            context: 上下文信息
            include_knowledge: 是否包含知识条目
            include_experience: 是否包含经验
            include_solutions: 是否包含解决方案
            max_results: 最大结果数
            
        Returns:
            检索结果
        """
        # 检查缓存
        cache_key = self._make_cache_key(query, context)
        cached_result = self._get_cached(cache_key)
        if cached_result:
            self.logger.debug(f"Using cached result for: {query}")
            return cached_result
        
        result = RetrievalResult(query=query)
        
        # 检索知识条目
        if include_knowledge and self.knowledge_base:
            entries = self.knowledge_base.search_by_content(query, limit=max_results)
            result.knowledge_entries.extend(entries)
        
        # 检索经验
        if include_experience and self.experience_store:
            experiences = self.experience_store.search_by_description(query, limit=max_results)
            result.experiences.extend(experiences)
        
        # 检索解决方案
        if include_solutions and self.solution_library:
            solutions = self.solution_library.search_solutions(query, limit=max_results)
            result.solutions.extend(solutions)
        
        # 计算相关性分数
        result.relevance_score = self._calculate_relevance(query, result)
        
        # 缓存结果
        self._set_cached(cache_key, result)
        
        self.logger.info(f"Retrieved {len(result.knowledge_entries)} knowledge, "
                       f"{len(result.experiences)} experiences, "
                       f"{len(result.solutions)} solutions for: {query}")
        
        return result
    
    def retrieve_for_task(self, task_type: str, task_description: str,
                         max_results: int = 5) -> RetrievalResult:
        """为任务检索相关知识
        
        Args:
            task_type: 任务类型
            task_description: 任务描述
            max_results: 最大结果数
            
        Returns:
            检索结果
        """
        result = RetrievalResult(query=task_description)
        
        # 检索任务类型相关的经验
        if self.experience_store:
            experiences = self.experience_store.get_task_type_experiences(task_type)
            result.experiences.extend(experiences[:max_results])
        
        # 检索任务类型相关的解决方案
        if self.solution_library:
            solutions = self.solution_library.get_solutions_by_task_type(task_type)
            result.solutions.extend(solutions[:max_results])
        
        # 检索相似问题的解决方案
        if self.solution_library and task_description:
            similar = self.solution_library.get_similar_solutions(task_description, limit=max_results)
            result.solutions.extend(similar)
        
        # 计算相关性分数
        result.relevance_score = self._calculate_relevance(task_description, result)
        
        return result
    
    def retrieve_for_agent(self, agent_name: str, query: str,
                         max_results: int = 5) -> RetrievalResult:
        """为Agent检索相关知识
        
        Args:
            agent_name: Agent名称
            query: 查询字符串
            max_results: 最大结果数
            
        Returns:
            检索结果
        """
        result = RetrievalResult(query=query)
        
        # 检索Agent的经验
        if self.experience_store:
            experiences = self.experience_store.get_agent_experiences(agent_name)
            result.experiences.extend(experiences[:max_results])
        
        # 检索相关知识
        if self.knowledge_base:
            entries = self.knowledge_base.search_by_content(query, limit=max_results)
            result.knowledge_entries.extend(entries)
        
        # 讣算相关性分数
        result.relevance_score = self._calculate_relevance(query, result)
        
        return result
    
    def get_recommended_approach(self, task_type: str, task_description: str) -> Dict[str, Any]:
        """获取推荐的方法
        
        Args:
            task_type: 任务类型
            task_description: 任务描述
            
        Returns:
            推荐的方法
        """
        result = self.retrieve_for_task(task_type, task_description)
        
        recommendations = {
            "similar_solutions": [],
            "successful_experiences": [],
            "lessons_learned": [],
            "confidence": 0.0
        }
        
        # 收集成功经验
        for exp in result.experiences:
            if exp.success:
                recommendations["successful_experiences"].append({
                    "approach": exp.approach,
                    "outcome": exp.outcome,
                    "confidence": exp.confidence
                })
                for lesson in exp.lessons_learned:
                    recommendations["lessons_learned"].append(lesson)
        
        # 收集相似解决方案
        for sol in result.solutions:
            recommendations["similar_solutions"].append({
                "name": sol.name,
                "steps": sol.steps,
                "confidence": sol.confidence * sol.success_rate
            })
        
        # 计算总体置信度
        if recommendations["successful_experiences"] or recommendations["similar_solutions"]:
            exp_conf = sum(e["confidence"] for e in recommendations["successful_experiences"])
            sol_conf = sum(s["confidence"] for s in recommendations["similar_solutions"])
            total_items = len(recommendations["successful_experiences"]) + len(recommendations["similar_solutions"])
            
            recommendations["confidence"] = (exp_conf + sol_conf) / total_items if total_items > 0 else 0
        
        return recommendations
    
    def _calculate_relevance(self, query: str, result: RetrievalResult) -> float:
        """计算相关性分数"""
        score = 0.0
        
        query_words = set(query.lower().split())
        
        # 知识条目相关性
        for entry in result.knowledge_entries:
            if hasattr(entry, 'content'):
                entry_words = set(entry.content.lower().split())
                score += len(query_words & entry_words) * entry.confidence
        
        # 经验相关性
        for exp in result.experiences:
            if hasattr(exp, 'description'):
                exp_words = set(exp.description.lower().split())
                score += len(query_words & exp_words) * exp.confidence
        
        # 解决方案相关性
        for sol in result.solutions:
            if hasattr(sol, 'problem_description'):
                sol_words = set(sol.problem_description.lower().split())
                score += len(query_words & sol_words) * sol.confidence * sol.success_rate
        
        # 归一化
        total_items = len(result.knowledge_entries) + len(result.experiences) + len(result.solutions)
        if total_items > 0:
            score = score / total_items
        
        return score
    
    def _make_cache_key(self, query: str, context: Dict[str, Any] = None) -> str:
        """生成缓存键"""
        import hashlib
        
        key_parts = [query]
        if context:
            key_parts.append(str(sorted(context.items())))
        
        key_str = "|".join(key_parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[RetrievalResult]:
        """获取缓存结果"""
        with self._cache_lock:
            if key in self._cache:
                timestamp, result = self._cache[key]
                if time.time() - timestamp < self._cache_ttl:
                    return result
                else:
                    del self._cache[key]
        return None
    
    def _set_cached(self, key: str, result: RetrievalResult):
        """设置缓存结果"""
        with self._cache_lock:
            self._cache[key] = (time.time(), result)
            
            # 清理过期缓存
            self._cleanup_cache()
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        now = time.time()
        expired_keys = [
            k for k, (t, _) in self._cache.items()
            if now - t >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._cache[key]
    
    def clear_cache(self):
        """清除所有缓存"""
        with self._cache_lock:
            self._cache.clear()
        self.logger.info("Cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
            "has_knowledge_base": self.knowledge_base is not None,
            "has_experience_store": self.experience_store is not None,
            "has_solution_library": self.solution_library is not None
        }
