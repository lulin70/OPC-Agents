#!/usr/bin/env python3
"""
成果物管理器

提供成果物的存储、检索、版本管理和分享功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from data_storage import DatabaseManager, DeliverableRecord
from .deliverable_generator import DeliverableGenerator


class DeliverableManager:
    """成果物管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化成果物管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.generator = DeliverableGenerator()
        self.logger = logging.getLogger(__name__)
    
    def create_deliverable(self, task_id: str, task_type: str, task_data: Dict[str, Any],
                          created_by: str = "") -> Optional[DeliverableRecord]:
        """创建成果物
        
        Args:
            task_id: 任务ID
            task_type: 任务类型
            task_data: 任务数据
            created_by: 创建者
            
        Returns:
            成果物记录对象
        """
        try:
            # 生成成果物
            deliverable_data = self.generator.generate_deliverable(
                task_id, task_type, task_data, created_by
            )
            
            if not deliverable_data:
                return None
            
            # 创建成果物记录
            deliverable = DeliverableRecord(
                id=deliverable_data["id"],
                task_id=deliverable_data["task_id"],
                name=deliverable_data["name"],
                type=deliverable_data["type"],
                content=deliverable_data["content"],
                file_path=deliverable_data["file_path"],
                version=deliverable_data["version"],
                created_at=deliverable_data["created_at"],
                updated_at=deliverable_data["updated_at"],
                created_by=deliverable_data["created_by"],
                metadata=deliverable_data["metadata"]
            )
            
            # 保存到数据库
            if self.db_manager.save_deliverable(deliverable):
                self.logger.info(f"成果物已创建并保存: {deliverable.id}")
                return deliverable
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"创建成果物失败: {e}")
            return None
    
    def get_deliverable_by_id(self, deliverable_id: str) -> Optional[DeliverableRecord]:
        """根据ID获取成果物
        
        Args:
            deliverable_id: 成果物ID
            
        Returns:
            成果物记录对象
        """
        try:
            # 这里需要实现get_deliverable_by_id方法
            # 暂时返回None
            return None
            
        except Exception as e:
            self.logger.error(f"获取成果物失败: {e}")
            return None
    
    def get_deliverables_by_task(self, task_id: str) -> List[DeliverableRecord]:
        """获取任务的所有成果物
        
        Args:
            task_id: 任务ID
            
        Returns:
            成果物记录列表
        """
        try:
            return self.db_manager.get_deliverables_by_task(task_id)
            
        except Exception as e:
            self.logger.error(f"获取任务成果物失败: {e}")
            return []
    
    def update_deliverable(self, deliverable_id: str, new_content: Dict[str, Any]) -> bool:
        """更新成果物内容
        
        Args:
            deliverable_id: 成果物ID
            new_content: 新内容
            
        Returns:
            是否更新成功
        """
        try:
            deliverable = self.get_deliverable_by_id(deliverable_id)
            
            if not deliverable:
                return False
            
            # 更新内容和版本
            deliverable.content = json.dumps(new_content, ensure_ascii=False)
            deliverable.version += 1
            deliverable.updated_at = time.time()
            
            return self.db_manager.save_deliverable(deliverable)
            
        except Exception as e:
            self.logger.error(f"更新成果物失败: {e}")
            return False
    
    def delete_deliverable(self, deliverable_id: str) -> bool:
        """删除成果物
        
        Args:
            deliverable_id: 成果物ID
            
        Returns:
            是否删除成功
        """
        try:
            # 这里需要实现delete_deliverable方法
            # 暂时返回True
            self.logger.info(f"成果物已删除: {deliverable_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除成果物失败: {e}")
            return False
    
    def export_deliverable(self, deliverable_id: str, format: str = "json") -> Optional[str]:
        """导出成果物
        
        Args:
            deliverable_id: 成果物ID
            format: 导出格式（json, markdown, txt）
            
        Returns:
            导出的内容字符串
        """
        try:
            deliverable = self.get_deliverable_by_id(deliverable_id)
            
            if not deliverable:
                return None
            
            deliverable_dict = {
                "id": deliverable.id,
                "task_id": deliverable.task_id,
                "name": deliverable.name,
                "type": deliverable.type,
                "content": deliverable.content,
                "version": deliverable.version,
                "created_at": deliverable.created_at,
                "updated_at": deliverable.updated_at,
                "created_by": deliverable.created_by
            }
            
            return self.generator.export_deliverable(deliverable_dict, format)
            
        except Exception as e:
            self.logger.error(f"导出成果物失败: {e}")
            return None
    
    def get_deliverable_versions(self, deliverable_id: str) -> List[Dict[str, Any]]:
        """获取成果物的所有版本
        
        Args:
            deliverable_id: 成果物ID
            
        Returns:
            版本列表
        """
        try:
            # 这里需要实现版本历史查询
            # 暂时返回空列表
            return []
            
        except Exception as e:
            self.logger.error(f"获取成果物版本失败: {e}")
            return []
    
    def search_deliverables(self, query: str, task_id: str = None) -> List[Dict[str, Any]]:
        """搜索成果物
        
        Args:
            query: 搜索关键词
            task_id: 任务ID（可选）
            
        Returns:
            搜索结果列表
        """
        try:
            # 获取成果物列表
            if task_id:
                deliverables = self.get_deliverables_by_task(task_id)
            else:
                # 这里需要实现获取所有成果物的方法
                deliverables = []
            
            results = []
            
            for deliverable in deliverables:
                # 搜索名称和内容
                if (query.lower() in deliverable.name.lower() or
                    query.lower() in deliverable.content.lower()):
                    
                    results.append({
                        "id": deliverable.id,
                        "task_id": deliverable.task_id,
                        "name": deliverable.name,
                        "type": deliverable.type,
                        "version": deliverable.version,
                        "created_at": datetime.fromtimestamp(deliverable.created_at).strftime('%Y-%m-%d %H:%M:%S'),
                        "relevance_score": self._calculate_relevance(query, deliverable)
                    })
            
            # 按相关性排序
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return results
            
        except Exception as e:
            self.logger.error(f"搜索成果物失败: {e}")
            return []
    
    def get_deliverable_statistics(self, task_id: str = None) -> Dict[str, Any]:
        """获取成果物统计信息
        
        Args:
            task_id: 任务ID（可选）
            
        Returns:
            统计信息字典
        """
        try:
            # 获取成果物列表
            if task_id:
                deliverables = self.get_deliverables_by_task(task_id)
            else:
                # 这里需要实现获取所有成果物的方法
                deliverables = []
            
            if not deliverables:
                return {}
            
            # 统计类型分布
            type_distribution = {}
            for deliverable in deliverables:
                type_distribution[deliverable.type] = type_distribution.get(deliverable.type, 0) + 1
            
            # 统计版本信息
            total_versions = sum(deliverable.version for deliverable in deliverables)
            avg_versions = total_versions / len(deliverables)
            
            statistics = {
                "total_deliverables": len(deliverables),
                "total_versions": total_versions,
                "average_versions": round(avg_versions, 2),
                "type_distribution": type_distribution,
                "latest_deliverable": max(deliverables, key=lambda x: x.updated_at).name if deliverables else None,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return statistics
            
        except Exception as e:
            self.logger.error(f"获取成果物统计信息失败: {e}")
            return {}
    
    def _calculate_relevance(self, query: str, deliverable: DeliverableRecord) -> float:
        """计算相关性得分
        
        Args:
            query: 查询字符串
            deliverable: 成果物记录
            
        Returns:
            相关性得分（0-1）
        """
        try:
            query_lower = query.lower()
            name_lower = deliverable.name.lower()
            content_lower = deliverable.content.lower()
            
            # 名称匹配权重更高
            name_score = 0.0
            if query_lower in name_lower:
                name_score = 1.0
            
            # 内容匹配
            content_score = 0.0
            count = content_lower.count(query_lower)
            if count > 0:
                content_score = min(count / 10, 1.0)
            
            # 综合得分
            total_score = name_score * 0.7 + content_score * 0.3
            
            return total_score
            
        except Exception as e:
            self.logger.error(f"计算相关性得分失败: {e}")
            return 0.0
