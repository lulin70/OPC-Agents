#!/usr/bin/env python3
"""
进度跟踪器

提供任务进度的实时跟踪、时间线记录和里程碑管理功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class ProgressEvent:
    """进度事件"""
    timestamp: float
    event_type: str
    description: str
    progress: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Milestone:
    """里程碑"""
    id: str
    name: str
    description: str
    target_progress: int
    actual_progress: int = 0
    target_date: Optional[float] = None
    completed_date: Optional[float] = None
    status: str = "pending"  # pending, in_progress, completed, delayed


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self):
        """初始化进度跟踪器"""
        self.logger = logging.getLogger(__name__)
        
        # 任务进度存储
        self.task_progress: Dict[str, Dict[str, Any]] = {}
        
        # 事件历史
        self.event_history: Dict[str, List[ProgressEvent]] = {}
        
        # 里程碑管理
        self.milestones: Dict[str, List[Milestone]] = {}
    
    def initialize_task_tracking(self, task_id: str, task_name: str, 
                                 estimated_duration: float = None) -> bool:
        """初始化任务跟踪
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            estimated_duration: 预估持续时间（秒）
            
        Returns:
            是否初始化成功
        """
        try:
            now = time.time()
            
            self.task_progress[task_id] = {
                "task_id": task_id,
                "task_name": task_name,
                "status": "pending",
                "progress": 0,
                "created_at": now,
                "updated_at": now,
                "started_at": None,
                "completed_at": None,
                "estimated_duration": estimated_duration,
                "actual_duration": None,
                "participants": [],
                "events_count": 0
            }
            
            self.event_history[task_id] = []
            self.milestones[task_id] = []
            
            # 记录初始化事件
            self._record_event(task_id, "initialized", f"任务 '{task_name}' 已初始化", 0)
            
            self.logger.info(f"任务跟踪已初始化: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化任务跟踪失败: {e}")
            return False
    
    def start_task(self, task_id: str) -> bool:
        """开始任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否开始成功
        """
        try:
            if task_id not in self.task_progress:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            now = time.time()
            
            self.task_progress[task_id]["status"] = "in_progress"
            self.task_progress[task_id]["started_at"] = now
            self.task_progress[task_id]["updated_at"] = now
            
            # 记录开始事件
            self._record_event(task_id, "started", "任务已开始", 0)
            
            self.logger.info(f"任务已开始: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"开始任务失败: {e}")
            return False
    
    def update_progress(self, task_id: str, progress: int, description: str = "") -> bool:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度（0-100）
            description: 进度描述
            
        Returns:
            是否更新成功
        """
        try:
            if task_id not in self.task_progress:
                self.logger.error(f"任务不存在: {task_id}")
                return False
            
            # 确保进度在有效范围内
            progress = max(0, min(100, progress))
            
            now = time.time()
            old_progress = self.task_progress[task_id]["progress"]
            
            self.task_progress[task_id]["progress"] = progress
            self.task_progress[task_id]["updated_at"] = now
            
            # 如果进度达到100%，标记任务完成
            if progress >= 100:
                self.task_progress[task_id]["status"] = "completed"
                self.task_progress[task_id]["completed_at"] = now
                
                # 计算实际持续时间
                started_at = self.task_progress[task_id]["started_at"]
                if started_at:
                    self.task_progress[task_id]["actual_duration"] = now - started_at
            
            # 记录进度更新事件
            event_description = description or f"进度更新: {old_progress}% -> {progress}%"
            self._record_event(task_id, "progress_update", event_description, progress)
            
            # 检查里程碑
            self._check_milestones(task_id, progress)
            
            self.logger.debug(f"任务进度已更新: {task_id} -> {progress}%")
            return True
            
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {e}")
            return False
    
    def add_participant(self, task_id: str, participant_id: str, 
                       participant_name: str, role: str = "") -> bool:
        """添加任务参与者
        
        Args:
            task_id: 任务ID
            participant_id: 参与者ID
            participant_name: 参与者名称
            role: 角色
            
        Returns:
            是否添加成功
        """
        try:
            if task_id not in self.task_progress:
                return False
            
            participant = {
                "id": participant_id,
                "name": participant_name,
                "role": role,
                "joined_at": time.time()
            }
            
            self.task_progress[task_id]["participants"].append(participant)
            
            # 记录参与者加入事件
            self._record_event(
                task_id, 
                "participant_joined", 
                f"参与者 '{participant_name}' 已加入任务", 
                self.task_progress[task_id]["progress"],
                {"participant_id": participant_id, "role": role}
            )
            
            self.logger.info(f"参与者已添加: {participant_name} -> {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加参与者失败: {e}")
            return False
    
    def add_milestone(self, task_id: str, milestone_id: str, name: str, 
                     description: str, target_progress: int, 
                     target_date: float = None) -> bool:
        """添加里程碑
        
        Args:
            task_id: 任务ID
            milestone_id: 里程碑ID
            name: 里程碑名称
            description: 描述
            target_progress: 目标进度
            target_date: 目标日期（时间戳）
            
        Returns:
            是否添加成功
        """
        try:
            if task_id not in self.milestones:
                self.milestones[task_id] = []
            
            milestone = Milestone(
                id=milestone_id,
                name=name,
                description=description,
                target_progress=target_progress,
                target_date=target_date
            )
            
            self.milestones[task_id].append(milestone)
            
            # 记录里程碑添加事件
            self._record_event(
                task_id,
                "milestone_added",
                f"里程碑 '{name}' 已添加",
                self.task_progress[task_id]["progress"],
                {"milestone_id": milestone_id, "target_progress": target_progress}
            )
            
            self.logger.info(f"里程碑已添加: {name} -> {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加里程碑失败: {e}")
            return False
    
    def get_task_timeline(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务时间线
        
        Args:
            task_id: 任务ID
            
        Returns:
            时间线事件列表
        """
        try:
            if task_id not in self.event_history:
                return []
            
            timeline = []
            for event in self.event_history[task_id]:
                timeline.append({
                    "timestamp": event.timestamp,
                    "datetime": datetime.fromtimestamp(event.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
                    "event_type": event.event_type,
                    "description": event.description,
                    "progress": event.progress,
                    "metadata": event.metadata
                })
            
            return timeline
            
        except Exception as e:
            self.logger.error(f"获取任务时间线失败: {e}")
            return []
    
    def get_task_progress_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务进度报告
        
        Args:
            task_id: 任务ID
            
        Returns:
            进度报告字典
        """
        try:
            if task_id not in self.task_progress:
                return None
            
            task_data = self.task_progress[task_id]
            
            # 计算持续时间
            duration_info = self._calculate_duration_info(task_data)
            
            # 获取里程碑状态
            milestones_status = self._get_milestones_status(task_id)
            
            # 构建报告
            report = {
                "task_id": task_id,
                "task_name": task_data["task_name"],
                "status": task_data["status"],
                "progress": task_data["progress"],
                "created_at": datetime.fromtimestamp(task_data["created_at"]).strftime('%Y-%m-%d %H:%M:%S'),
                "started_at": datetime.fromtimestamp(task_data["started_at"]).strftime('%Y-%m-%d %H:%M:%S') if task_data["started_at"] else None,
                "completed_at": datetime.fromtimestamp(task_data["completed_at"]).strftime('%Y-%m-%d %H:%M:%S') if task_data["completed_at"] else None,
                "updated_at": datetime.fromtimestamp(task_data["updated_at"]).strftime('%Y-%m-%d %H:%M:%S'),
                "duration_info": duration_info,
                "participants": task_data["participants"],
                "milestones": milestones_status,
                "events_count": task_data["events_count"],
                "progress_percentage": f"{task_data['progress']}%"
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"获取任务进度报告失败: {e}")
            return None
    
    def get_all_active_tasks(self) -> List[Dict[str, Any]]:
        """获取所有活动任务
        
        Returns:
            活动任务列表
        """
        try:
            active_tasks = []
            
            for task_id, task_data in self.task_progress.items():
                if task_data["status"] in ["pending", "in_progress"]:
                    report = self.get_task_progress_report(task_id)
                    if report:
                        active_tasks.append(report)
            
            # 按更新时间排序
            active_tasks.sort(key=lambda x: x["updated_at"], reverse=True)
            
            return active_tasks
            
        except Exception as e:
            self.logger.error(f"获取活动任务失败: {e}")
            return []
    
    def _record_event(self, task_id: str, event_type: str, description: str, 
                     progress: int, metadata: Dict[str, Any] = None):
        """记录事件
        
        Args:
            task_id: 任务ID
            event_type: 事件类型
            description: 描述
            progress: 进度
            metadata: 元数据
        """
        try:
            event = ProgressEvent(
                timestamp=time.time(),
                event_type=event_type,
                description=description,
                progress=progress,
                metadata=metadata or {}
            )
            
            if task_id not in self.event_history:
                self.event_history[task_id] = []
            
            self.event_history[task_id].append(event)
            
            # 更新事件计数
            if task_id in self.task_progress:
                self.task_progress[task_id]["events_count"] += 1
            
        except Exception as e:
            self.logger.error(f"记录事件失败: {e}")
    
    def _check_milestones(self, task_id: str, current_progress: int):
        """检查里程碑
        
        Args:
            task_id: 任务ID
            current_progress: 当前进度
        """
        try:
            if task_id not in self.milestones:
                return
            
            for milestone in self.milestones[task_id]:
                if (milestone.status == "pending" and 
                    current_progress >= milestone.target_progress):
                    
                    milestone.status = "completed"
                    milestone.actual_progress = current_progress
                    milestone.completed_date = time.time()
                    
                    # 记录里程碑完成事件
                    self._record_event(
                        task_id,
                        "milestone_completed",
                        f"里程碑 '{milestone.name}' 已完成",
                        current_progress,
                        {"milestone_id": milestone.id}
                    )
                    
                    self.logger.info(f"里程碑已完成: {milestone.name}")
            
        except Exception as e:
            self.logger.error(f"检查里程碑失败: {e}")
    
    def _calculate_duration_info(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算持续时间信息
        
        Args:
            task_data: 任务数据
            
        Returns:
            持续时间信息
        """
        try:
            duration_info = {
                "estimated": None,
                "actual": None,
                "remaining": None
            }
            
            # 预估持续时间
            if task_data["estimated_duration"]:
                estimated_minutes = task_data["estimated_duration"] / 60
                duration_info["estimated"] = f"{estimated_minutes:.1f} 分钟"
            
            # 实际持续时间
            if task_data["actual_duration"]:
                actual_minutes = task_data["actual_duration"] / 60
                duration_info["actual"] = f"{actual_minutes:.1f} 分钟"
            elif task_data["started_at"]:
                elapsed = time.time() - task_data["started_at"]
                elapsed_minutes = elapsed / 60
                duration_info["actual"] = f"{elapsed_minutes:.1f} 分钟 (进行中)"
            
            # 剩余时间估算
            if (task_data["estimated_duration"] and task_data["started_at"] and 
                task_data["progress"] > 0 and task_data["progress"] < 100):
                
                elapsed = time.time() - task_data["started_at"]
                estimated_total = elapsed / (task_data["progress"] / 100)
                remaining = estimated_total - elapsed
                remaining_minutes = remaining / 60
                duration_info["remaining"] = f"{remaining_minutes:.1f} 分钟 (估算)"
            
            return duration_info
            
        except Exception as e:
            self.logger.error(f"计算持续时间信息失败: {e}")
            return {}
    
    def _get_milestones_status(self, task_id: str) -> List[Dict[str, Any]]:
        """获取里程碑状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            里程碑状态列表
        """
        try:
            if task_id not in self.milestones:
                return []
            
            milestones_status = []
            
            for milestone in self.milestones[task_id]:
                status = {
                    "id": milestone.id,
                    "name": milestone.name,
                    "description": milestone.description,
                    "target_progress": milestone.target_progress,
                    "actual_progress": milestone.actual_progress,
                    "status": milestone.status,
                    "target_date": datetime.fromtimestamp(milestone.target_date).strftime('%Y-%m-%d') if milestone.target_date else None,
                    "completed_date": datetime.fromtimestamp(milestone.completed_date).strftime('%Y-%m-%d %H:%M:%S') if milestone.completed_date else None
                }
                milestones_status.append(status)
            
            return milestones_status
            
        except Exception as e:
            self.logger.error(f"获取里程碑状态失败: {e}")
            return []
