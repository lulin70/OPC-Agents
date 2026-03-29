#!/usr/bin/env python3
"""
Knowledge Base for OPC-Agents

Central knowledge storage and retrieval system.
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
class KnowledgeEntry:
    """知识条目"""
    id: str
    title: str
    content: str
    category: str
    tags: List[str] = field(default_factory=list)
    source: str = ""
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count
        }


    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeEntry':
        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            category=data.get("category", "general"),
            tags=data.get("tags", []),
            source=data.get("source", ""),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            access_count=data.get("access_count", 0)
        )


    
    def update_timestamp(self):
        self.updated_at = time.time()
    
    def increment_access(self):
        self.access_count += 1
        self.update_timestamp()


class KnowledgeBase:
    """知识库
    
    存储和管理知识条目，支持分类、标签、搜索。
    """
    
    def __init__(self, storage_path: str = "knowledge_storage"):
        """初始化知识库
        
        Args:
            storage_path: 存储路径
        """
        self.storage_path = storage_path
        self.logger = logging.getLogger("OPC-Agents.KnowledgeBase")
        
        # 内存缓存
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        
        # 锁
        self._lock = threading.Lock()
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 加载已有知识
        self._load_all()
        
        self.logger.info(f"KnowledgeBase initialized at {storage_path}")
    
    def _load_all(self):
        """加载所有知识条目"""
        index_file = os.path.join(self.storage_path, "index.json")
        if not os.path.exists(index_file):
            return
        
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for entry_data in data.get("entries", []):
                entry = KnowledgeEntry.from_dict(entry_data)
                self._entries[entry.id] = entry
                
                # 更新索引
                self._update_indexes(entry)
            
            self.logger.info(f"Loaded {len(self._entries)} knowledge entries")
        except Exception as e:
            self.logger.error(f"Failed to load knowledge: {e}")
    
    def _update_indexes(self, entry: KnowledgeEntry):
        """更新索引"""
        # 分类索引
        if entry.category not in self._category_index:
            self._category_index[entry.category] = []
        if entry.id not in self._category_index[entry.category]:
            self._category_index[entry.category].append(entry.id)
        
        # 标签索引
        for tag in entry.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if entry.id not in self._tag_index[tag]:
                self._tag_index[tag].append(entry.id)
    
    def _save_index(self):
        """保存索引到文件"""
        index_file = os.path.join(self.storage_path, "index.json")
        try:
            data = {
                "entries": [e.to_dict() for e in self._entries.values()],
                "updated_at": time.time()
            }
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")
    
    def add_entry(self, entry: KnowledgeEntry) -> bool:
        """添加知识条目
        
        Args:
            entry: 知识条目
            
        Returns:
            是否成功
        """
        with self._lock:
            if entry.id in self._entries:
                self.logger.warning(f"Entry already exists: {entry.id}")
                return False
            
            self._entries[entry.id] = entry
            self._update_indexes(entry)
            self._save_index()
            
            self.logger.info(f"Added knowledge entry: {entry.id}")
            return True
    
    def update_entry(self, entry: KnowledgeEntry) -> bool:
        """更新知识条目
        
        Args:
            entry: 知识条目
            
        Returns:
            是否成功
        """
        with self._lock:
            if entry.id not in self._entries:
                self.logger.warning(f"Entry not found: {entry.id}")
                return False
            
            
            old_entry = self._entries[entry.id]
            
            # 更新索引（移除旧的)
            if old_entry.category != entry.category:
                if old_entry.id in self._category_index.get(old_entry.category, []):
                    self._category_index[old_entry.category].remove(old_entry.id)
            
            for old_tag in old_entry.tags:
                if old_tag in self._tag_index and old_entry.id in self._tag_index[old_tag]:
                    self._tag_index[old_tag].remove(old_entry.id)
            
            # 更新条目
            entry.updated_at = time.time()
            self._entries[entry.id] = entry
            self._update_indexes(entry)
            self._save_index()
            
            self.logger.info(f"Updated knowledge entry: {entry.id}")
            return True
    
    def delete_entry(self, entry_id: str) -> bool:
        """删除知识条目
        
        Args:
            entry_id: 条目ID
            
        Returns:
            是否成功
        """
        with self._lock:
            if entry_id not in self._entries:
                return False
            
            entry = self._entries[entry_id]
            
            # 从索引中移除
            if entry.category in self._category_index and entry.id in self._category_index[entry.category]:
                self._category_index[entry.category].remove(entry.id)
            
            for tag in entry.tags:
                if tag in self._tag_index and entry.id in self._tag_index[tag]:
                    self._tag_index[tag].remove(entry.id)
            
            # 删除条目
            del self._entries[entry_id]
            self._save_index()
            
            self.logger.info(f"Deleted knowledge entry: {entry_id}")
            return True
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目
        
        Args:
            entry_id: 条目ID
            
        Returns:
            知识条目
        """
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry:
                entry.increment_access()
            return entry
    
    def search_by_category(self, category: str) -> List[KnowledgeEntry]:
        """按分类搜索
        
        Args:
            category: 分类名称
            
        Returns:
            知识条目列表
        """
        with self._lock:
            entry_ids = self._category_index.get(category, [])
            return [self._entries[eid] for eid in entry_ids if eid in self._entries]
    
    def search_by_tags(self, tags: List[str], match_all: bool = False) -> List[KnowledgeEntry]:
        """按标签搜索
        
        Args:
            tags: 标签列表
            match_all: 是否匹配所有标签
            
        Returns:
            知识条目列表
        """
        with self._lock:
            if not tags:
                return []
            
            if match_all:
                # 必须匹配所有标签
                matching_ids = None
                for tag in tags:
                    tag_entries = set(self._tag_index.get(tag, []))
                    if matching_ids is None:
                        matching_ids = tag_entries
                    else:
                        matching_ids = matching_ids & tag_entries
                
                    if not matching_ids:
                        return []
                
                return [self._entries[eid] for eid in matching_ids if eid in self._entries]
            else:
                # 匹配任一标签
                matching_ids = set()
                for tag in tags:
                    for eid in self._tag_index.get(tag, []):
                        matching_ids.add(eid)
                
                return [self._entries[eid] for eid in matching_ids if eid in self._entries]
    
    def search_by_content(self, query: str, limit: int = 10) -> List[KnowledgeEntry]:
        """按内容搜索
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
            
        Returns:
            知识条目列表
        """
        query_lower = query.lower()
        
        with self._lock:
            results = []
            for entry in self._entries.values():
                if (query_lower in entry.title.lower() or 
                    query_lower in entry.content.lower()):
                    results.append(entry)
                    if len(results) >= limit:
                        break
            
            return results
    
    def get_all_entries(self) -> List[KnowledgeEntry]:
        """获取所有知识条目"""
        with self._lock:
            return list(self._entries.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "categories": len(self._category_index),
                "tags": len(self._tag_index),
                "total_access": sum(e.access_count for e in self._entries.values())
            }
    
    def export_to_file(self, file_path: str):
        """导出知识库到文件
        
        Args:
            file_path: 目标文件路径
        """
        with self._lock:
            data = {
                "entries": [e.to_dict() for e in self._entries.values()],
                "exported_at": time.time()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Exported knowledge base to {file_path}")
    
    def import_from_file(self, file_path: str, merge: bool = False):
        """从文件导入知识库
        
        Args:
            file_path: 源文件路径
            merge: 是否合并（不覆盖现有条目）
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported_count = 0
            for entry_data in data.get("entries", []):
                entry = KnowledgeEntry.from_dict(entry_data)
                
                if merge and entry.id in self._entries:
                    continue
                
                if entry.id in self._entries:
                    self.update_entry(entry)
                else:
                    self.add_entry(entry)
                
                imported_count += 1
            
            self.logger.info(f"Imported {imported_count} entries from {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to import from {file_path}: {e}")
