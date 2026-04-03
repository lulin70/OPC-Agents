"""
任务历史增强模块

实现：
- 搜索：全文搜索任务名称/描述/结果
- 归档：自动归档旧任务（>100 个或>7 天）
- 导出：JSON/CSV 格式
- 分层存储：活跃任务（内存）+ 归档任务（文件）
"""

import json
import os
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    task_name: str
    agent: str
    priority: str
    status: str  # completed/failed/cancelled
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    archived: bool = False
    archive_path: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'agent': self.agent,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error': self.error,
            'metadata': self.metadata,
            'archived': self.archived,
            'archive_path': self.archive_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskRecord':
        return cls(
            task_id=data['task_id'],
            task_name=data['task_name'],
            agent=data['agent'],
            priority=data['priority'],
            status=data['status'],
            created_at=datetime.fromisoformat(data['created_at']),
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            result=data.get('result'),
            error=data.get('error'),
            metadata=data.get('metadata', {}),
            archived=data.get('archived', False),
            archive_path=data.get('archive_path')
        )


class TaskHistoryManager:
    """任务历史管理器"""
    
    def __init__(self, storage_dir: str = 'task_history', 
                 active_limit: int = 100,
                 archive_after_days: int = 7):
        """
        初始化
        
        Args:
            storage_dir: 存储目录
            active_limit: 活跃任务数量限制
            archive_after_days: 多少天后归档
        """
        self.storage_dir = storage_dir
        self.active_limit = active_limit
        self.archive_after_days = archive_after_days
        
        # 活跃任务（内存）
        self.active_tasks: Dict[str, TaskRecord] = {}
        
        # 归档索引（内存）
        self.archive_index: Dict[str, str] = {}  # {task_id: archive_path}
        
        # 创建存储目录
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(os.path.join(storage_dir, 'archives'), exist_ok=True)
        
        # 加载已有数据
        self._load_data()
        
        logger.info(f"任务历史管理器初始化完成 (活跃限制：{active_limit}, 归档：{archive_after_days}天)")
    
    def add_task(self, task: TaskRecord):
        """添加任务"""
        self.active_tasks[task.task_id] = task
        logger.debug(f"添加任务：{task.task_id}")
        
        # 检查是否需要归档
        self._auto_archive()
    
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取任务（活跃或归档）"""
        # 先查活跃
        if task_id in self.active_tasks:
            return self.active_tasks[task_id]
        
        # 再查归档
        if task_id in self.archive_index:
            return self._load_archived_task(task_id)
        
        return None
    
    def search(self, keyword: str, 
               status: Optional[str] = None,
               date_from: Optional[datetime] = None,
               date_to: Optional[datetime] = None,
               limit: int = 50) -> List[TaskRecord]:
        """
        搜索任务
        
        Args:
            keyword: 关键词（任务名称/描述）
            status: 状态过滤
            date_from: 起始日期
            date_to: 结束日期
            limit: 结果数量限制
        
        Returns:
            List[TaskRecord]: 搜索结果
        """
        results = []
        keyword_lower = keyword.lower()
        
        # 搜索活跃任务
        for task in self.active_tasks.values():
            if self._matches_filters(task, keyword_lower, status, date_from, date_to):
                results.append(task)
                if len(results) >= limit:
                    return results
        
        # 搜索归档任务
        for task_id, archive_path in self.archive_index.items():
            if len(results) >= limit:
                break
            
            task = self._load_archived_task(task_id)
            if task and self._matches_filters(task, keyword_lower, status, date_from, date_to):
                results.append(task)
        
        # 按时间排序
        results.sort(key=lambda t: t.created_at, reverse=True)
        
        return results
    
    def _matches_filters(self, task: TaskRecord, keyword: str,
                        status: Optional[str],
                        date_from: Optional[datetime],
                        date_to: Optional[datetime]) -> bool:
        """检查任务是否匹配过滤条件"""
        # 关键词匹配
        if keyword:
            if not (keyword in task.task_name.lower() or 
                    keyword in task.agent.lower() or
                    (task.result and keyword in str(task.result))):
                return False
        
        # 状态匹配
        if status and task.status != status:
            return False
        
        # 日期范围
        if date_from and task.created_at < date_from:
            return False
        if date_to and task.created_at > date_to:
            return False
        
        return True
    
    def export_tasks(self, task_ids: List[str], format: str = 'json', 
                    output_path: Optional[str] = None) -> str:
        """
        导出任务
        
        Args:
            task_ids: 任务 ID 列表
            format: 导出格式（json/csv）
            output_path: 输出路径（可选）
        
        Returns:
            str: 导出内容或文件路径
        """
        tasks = []
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task:
                tasks.append(task.to_dict())
        
        if format == 'json':
            content = json.dumps(tasks, indent=2, ensure_ascii=False)
            
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return output_path
            else:
                return content
        
        elif format == 'csv':
            if not tasks:
                return ""
            
            # CSV 头部
            fieldnames = ['task_id', 'task_name', 'agent', 'priority', 'status', 
                         'created_at', 'completed_at', 'error']
            
            if output_path:
                with open(output_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for task in tasks:
                        writer.writerow({k: task.get(k, '') for k in fieldnames})
                return output_path
            else:
                # 返回 CSV 字符串
                import io
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                for task in tasks:
                    writer.writerow({k: task.get(k, '') for k in fieldnames})
                return output.getvalue()
        
        else:
            raise ValueError(f"不支持的格式：{format}")
    
    def export_all(self, format: str = 'json', output_path: Optional[str] = None) -> str:
        """导出所有任务"""
        all_task_ids = list(self.active_tasks.keys()) + list(self.archive_index.keys())
        return self.export_tasks(all_task_ids, format, output_path)
    
    def _auto_archive(self):
        """自动归档旧任务"""
        # 检查数量
        if len(self.active_tasks) <= self.active_limit:
            return
        
        # 找出最早的任务
        sorted_tasks = sorted(self.active_tasks.values(), 
                             key=lambda t: t.created_at)
        
        # 归档多余的任务
        tasks_to_archive = sorted_tasks[:len(self.active_tasks) - self.active_limit]
        
        for task in tasks_to_archive:
            self._archive_task(task)
        
        logger.info(f"自动归档 {len(tasks_to_archive)} 个任务")
    
    def _archive_task(self, task: TaskRecord):
        """归档单个任务"""
        task.archived = True
        
        # 生成归档文件名
        date_str = task.created_at.strftime('%Y%m%d')
        archive_filename = f"{date_str}_{task.task_id}.json"
        archive_path = os.path.join(self.storage_dir, 'archives', archive_filename)
        
        # 保存到文件
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)
        
        task.archive_path = archive_path
        
        # 更新索引
        self.archive_index[task.task_id] = archive_path
        
        # 从活跃任务中移除
        del self.active_tasks[task.task_id]
        
        logger.debug(f"归档任务：{task.task_id} -> {archive_path}")
    
    def _load_archived_task(self, task_id: str) -> Optional[TaskRecord]:
        """加载归档任务"""
        if task_id not in self.archive_index:
            return None
        
        archive_path = self.archive_index[task_id]
        
        if not os.path.exists(archive_path):
            logger.warning(f"归档文件不存在：{archive_path}")
            return None
        
        with open(archive_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return TaskRecord.from_dict(data)
    
    def _load_data(self):
        """加载已有数据"""
        # 加载归档索引
        archives_dir = os.path.join(self.storage_dir, 'archives')
        if not os.path.exists(archives_dir):
            return
        
        for filename in os.listdir(archives_dir):
            if filename.endswith('.json'):
                archive_path = os.path.join(archives_dir, filename)
                
                try:
                    with open(archive_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    task_id = data['task_id']
                    self.archive_index[task_id] = archive_path
                    
                except Exception as e:
                    logger.error(f"加载归档文件失败：{filename}, {e}")
        
        logger.info(f"加载 {len(self.archive_index)} 个归档任务索引")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'active_count': len(self.active_tasks),
            'archived_count': len(self.archive_index),
            'total_count': len(self.active_tasks) + len(self.archive_index),
            'active_limit': self.active_limit,
            'archive_after_days': self.archive_after_days
        }
    
    def cleanup_old_archives(self, days: int = 30):
        """清理旧归档"""
        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0
        
        for task_id, archive_path in list(self.archive_index.items()):
            try:
                task = self._load_archived_task(task_id)
                if task and task.created_at < cutoff_date:
                    # 删除文件
                    if os.path.exists(archive_path):
                        os.remove(archive_path)
                    
                    # 移除索引
                    del self.archive_index[task_id]
                    removed_count += 1
                    
            except Exception as e:
                logger.error(f"清理归档失败：{archive_path}, {e}")
        
        logger.info(f"清理了 {removed_count} 个旧归档（>{days}天）")


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    manager = TaskHistoryManager(storage_dir='test_task_history')
    
    print("\n=== 测试 1: 添加任务 ===")
    for i in range(5):
        task = TaskRecord(
            task_id=f'task_{i:03d}',
            task_name=f'任务 {i}',
            agent='test_agent',
            priority='MEDIUM',
            status='completed',
            created_at=datetime.now() - timedelta(hours=i),
            completed_at=datetime.now(),
            result={'success': True, 'data': f'result_{i}'}
        )
        manager.add_task(task)
    
    print(f"添加 5 个任务，当前活跃：{manager.get_stats()['active_count']}")
    
    print("\n=== 测试 2: 搜索任务 ===")
    results = manager.search('任务')
    print(f"搜索 '任务'，找到 {len(results)} 个结果")
    for task in results:
        print(f"  - {task.task_name} ({task.status})")
    
    print("\n=== 测试 3: 导出任务 ===")
    json_output = manager.export_tasks(['task_000', 'task_001'], format='json')
    print(f"导出 JSON（前 100 字符）：{json_output[:100]}...")
    
    print("\n=== 测试 4: 统计信息 ===")
    stats = manager.get_stats()
    print(f"活跃任务：{stats['active_count']}")
    print(f"归档任务：{stats['archived_count']}")
    print(f"总计：{stats['total_count']}")
