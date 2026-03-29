#!/usr/bin/env python3
"""
Metrics Collector for OPC-Agents

Collects and aggregates system metrics for monitoring and analysis.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class MetricPoint:
    """指标数据点"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器
    
    收集、聚合和存储系统指标。
    """
    
    def __init__(self, max_points: int = 10000):
        """初始化指标收集器
        
        Args:
            max_points: 每个指标保留的最大数据点数
        """
        self.max_points = max_points
        self.logger = logging.getLogger("OPC-Agents.Metrics")
        
        # 指标存储
        self._metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # 聚合统计
        self._aggregations: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        self.logger.info("MetricsCollector initialized")
    
    def collect(self, status: Any):
        """从系统状态收集指标
        
        Args:
            status: 系统状态对象
        """
        timestamp = time.time()
        
        # 收集系统指标
        self.record("system.cpu_usage", status.cpu_usage, timestamp)
        self.record("system.memory_usage", status.memory_usage, timestamp)
        self.record("system.disk_usage", status.disk_usage, timestamp)
        
        # 收集任务指标
        self.record("tasks.active", status.active_tasks, timestamp)
        self.record("tasks.pending", status.pending_tasks, timestamp)
        self.record("tasks.completed", status.completed_tasks, timestamp)
        self.record("tasks.failed", status.failed_tasks, timestamp)
        
        # 收集队列指标
        self.record("queue.size", status.message_queue_size, timestamp)
    
    def record(self, name: str, value: float, timestamp: float = None, 
               tags: Dict[str, str] = None):
        """记录指标数据点
        
        Args:
            name: 指标名称
            value: 指标值
            timestamp: 时间戳（可选）
            tags: 标签（可选）
        """
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=timestamp,
            tags=tags or {}
        )
        
        with self._lock:
            self._metrics[name].append(point)
            
            # 限制数据点数量
            if len(self._metrics[name]) > self.max_points:
                self._metrics[name].pop(0)
            
            # 更新聚合统计
            self._update_aggregation(name, value)
    
    def _update_aggregation(self, name: str, value: float):
        """更新聚合统计
        
        Args:
            name: 指标名称
            value: 新值
        """
        agg = self._aggregations[name]
        
        if "count" not in agg:
            agg["count"] = 0
            agg["sum"] = 0.0
            agg["min"] = float("inf")
            agg["max"] = float("-inf")
        
        agg["count"] += 1
        agg["sum"] += value
        agg["min"] = min(agg["min"], value)
        agg["max"] = max(agg["max"], value)
        agg["avg"] = agg["sum"] / agg["count"]
        agg["last"] = value
        agg["last_updated"] = time.time()
    
    def get_metric(self, name: str, limit: int = 100) -> List[MetricPoint]:
        """获取指标数据点
        
        Args:
            name: 指标名称
            limit: 返回的最大数据点数
            
        Returns:
            数据点列表
        """
        with self._lock:
            return self._metrics[name][-limit:]
    
    def get_aggregation(self, name: str) -> Dict[str, float]:
        """获取指标聚合统计
        
        Args:
            name: 指标名称
            
        Returns:
            聚合统计字典
        """
        with self._lock:
            return self._aggregations.get(name, {}).copy()
    
    def get_all_metrics(self) -> Dict[str, List[MetricPoint]]:
        """获取所有指标"""
        with self._lock:
            return {k: v.copy() for k, v in self._metrics.items()}
    
    def get_all_aggregations(self) -> Dict[str, Dict[str, float]]:
        """获取所有聚合统计"""
        with self._lock:
            return {k: v.copy() for k, v in self._aggregations.items()}
    
    def get_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        with self._lock:
            summary = {}
            for name, agg in self._aggregations.items():
                summary[name] = {
                    "count": agg.get("count", 0),
                    "avg": agg.get("avg", 0),
                    "min": agg.get("min", 0),
                    "max": agg.get("max", 0),
                    "last": agg.get("last", 0)
                }
            return summary
    
    def clear_metric(self, name: str):
        """清除指定指标"""
        with self._lock:
            if name in self._metrics:
                del self._metrics[name]
            if name in self._aggregations:
                del self._aggregations[name]
    
    def clear_all(self):
        """清除所有指标"""
        with self._lock:
            self._metrics.clear()
            self._aggregations.clear()
    
    def export_prometheus(self) -> str:
        """导出Prometheus格式指标
        
        Returns:
            Prometheus格式的指标字符串
        """
        lines = []
        
        with self._lock:
            for name, agg in self._aggregations.items():
                # 转换指标名称
                prom_name = name.replace(".", "_")
                
                # 添加帮助和类型
                lines.append(f"# HELP {prom_name} Metric {name}")
                lines.append(f"# TYPE {prom_name} gauge")
                
                # 添加值
                lines.append(f"{prom_name} {agg.get('last', 0)}")
        
        return "\n".join(lines)
    
    def get_time_series(self, name: str, start_time: float = None, 
                        end_time: float = None) -> List[Dict[str, Any]]:
        """获取时间序列数据
        
        Args:
            name: 指标名称
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            时间序列数据列表
        """
        with self._lock:
            points = self._metrics.get(name, [])
            
            result = []
            for point in points:
                if start_time and point.timestamp < start_time:
                    continue
                if end_time and point.timestamp > end_time:
                    continue
                
                result.append({
                    "timestamp": point.timestamp,
                    "value": point.value,
                    "tags": point.tags
                })
            
            return result
