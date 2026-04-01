#!/usr/bin/env python3

from typing import Dict, List, Callable, Any
import threading


class EventBus:
    """事件总线
    
    用于解耦模块间的依赖关系，支持事件的发布和订阅。
    """
    
    def __init__(self):
        """初始化事件总线"""
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """订阅事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """取消订阅
        
        Args:
            event_type: 事件类型
            callback: 回调函数
        """
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass
    
    def publish(self, event_type: str, **kwargs) -> List[Any]:
        """发布事件
        
        Args:
            event_type: 事件类型
            **kwargs: 事件数据
            
        Returns:
            所有回调函数的返回值列表
        """
        results = []
        with self._lock:
            if event_type in self._subscribers:
                for callback in self._subscribers[event_type]:
                    try:
                        result = callback(**kwargs)
                        results.append(result)
                    except Exception as e:
                        print(f"[EventBus] 执行回调失败: {e}")
        return results
    
    def get_subscribers(self, event_type: str) -> List[Callable]:
        """获取指定事件类型的所有订阅者
        
        Args:
            event_type: 事件类型
            
        Returns:
            订阅者列表
        """
        with self._lock:
            return self._subscribers.get(event_type, [])
    
    def clear(self, event_type: str = None) -> None:
        """清除订阅者
        
        Args:
            event_type: 事件类型，如果为None则清除所有事件的订阅者
        """
        with self._lock:
            if event_type:
                if event_type in self._subscribers:
                    del self._subscribers[event_type]
            else:
                self._subscribers.clear()
    
    def has_subscribers(self, event_type: str) -> bool:
        """检查指定事件类型是否有订阅者
        
        Args:
            event_type: 事件类型
            
        Returns:
            是否有订阅者
        """
        with self._lock:
            return event_type in self._subscribers and len(self._subscribers[event_type]) > 0
