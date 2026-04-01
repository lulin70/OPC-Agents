#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class TaskScheduler(ABC):
    """任务调度器抽象基类
    
    定义统一的调度接口，支持任务的调度、取消、暂停和恢复。
    """
    
    @abstractmethod
    def schedule(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """调度任务
        
        Args:
            task_id: 任务ID
            task_data: 任务数据
            
        Returns:
            是否成功调度
        """
        pass
    
    @abstractmethod
    def cancel(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        pass
    
    @abstractmethod
    def pause(self, task_id: str) -> bool:
        """暂停任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功暂停
        """
        pass
    
    @abstractmethod
    def resume(self, task_id: str) -> bool:
        """恢复任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功恢复
        """
        pass
    
    @abstractmethod
    def get_ready_tasks(self) -> List[str]:
        """获取就绪的任务
        
        Returns:
            就绪任务的ID列表
        """
        pass
    
    @abstractmethod
    def on_task_completed(self, task_id: str) -> List[str]:
        """任务完成回调
        
        Args:
            task_id: 任务ID
            
        Returns:
            新就绪的任务ID列表
        """
        pass
    
    @abstractmethod
    def on_task_failed(self, task_id: str) -> List[str]:
        """任务失败回调
        
        Args:
            task_id: 任务ID
            
        Returns:
            被阻塞的任务ID列表
        """
        pass
    
    @abstractmethod
    def get_progress(self) -> Dict[str, Any]:
        """获取调度进度
        
        Returns:
            进度信息
        """
        pass
    
    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """获取调度器状态
        
        Returns:
            状态信息
        """
        pass
