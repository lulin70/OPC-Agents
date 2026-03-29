#!/usr/bin/env python3
"""
System Monitor for OPC-Agents

Monitors system health, collects metrics, and provides status information.
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class MonitorState(Enum):
    """监控器状态"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SystemStatus:
    """系统状态"""
    timestamp: float
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    active_tasks: int = 0
    pending_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_agents: int = 0
    message_queue_size: int = 0
    database_status: str = "unknown"
    llm_status: str = "unknown"
    errors: List[str] = field(default_factory=list)


class SystemMonitor:
    """系统监控器
    
    负责监控系统整体状态，收集指标，触发告警。
    """
    
    def __init__(self, opc_manager=None, check_interval: int = 30):
        """初始化系统监控器
        
        Args:
            opc_manager: OPCManager实例
            check_interval: 检查间隔（秒）
        """
        self.opc_manager = opc_manager
        self.check_interval = check_interval
        self.logger = logging.getLogger("OPC-Agents.Monitor")
        
        # 监控状态
        self.state = MonitorState.STOPPED
        self.monitor_thread = None
        
        # 历史数据
        self.status_history: List[SystemStatus] = []
        self.max_history_size = 1000
        
        # 告警管理器
        from .alerts import AlertManager
        self.alert_manager = AlertManager()
        
        # 指标收集器
        from .metrics import MetricsCollector
        self.metrics_collector = MetricsCollector()
        
        # 健康检查器
        from .health_check import HealthChecker
        self.health_checker = HealthChecker(opc_manager)
        
        # 回调函数
        self.on_status_update: Optional[Callable] = None
        self.on_alert: Optional[Callable] = None
        
        self.logger.info("SystemMonitor initialized")
    
    def start(self):
        """启动监控"""
        if self.state == MonitorState.RUNNING:
            self.logger.warning("Monitor is already running")
            return
        
        self.state = MonitorState.RUNNING
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("SystemMonitor started")
    
    def stop(self):
        """停止监控"""
        self.state = MonitorState.STOPPED
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("SystemMonitor stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.state == MonitorState.RUNNING:
            try:
                # 收集系统状态
                status = self._collect_status()
                
                # 保存历史
                self.status_history.append(status)
                if len(self.status_history) > self.max_history_size:
                    self.status_history.pop(0)
                
                # 收集指标
                self.metrics_collector.collect(status)
                
                # 检查告警条件
                alerts = self._check_alerts(status)
                for alert in alerts:
                    self.alert_manager.add_alert(alert)
                    if self.on_alert:
                        self.on_alert(alert)
                
                # 回调
                if self.on_status_update:
                    self.on_status_update(status)
                
                # 等待下一次检查
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                self.state = MonitorState.ERROR
                time.sleep(5)
    
    def _collect_status(self) -> SystemStatus:
        """收集系统状态
        
        Returns:
            系统状态对象
        """
        status = SystemStatus(timestamp=time.time())
        
        try:
            # 收集系统资源使用情况
            status.cpu_usage = self._get_cpu_usage()
            status.memory_usage = self._get_memory_usage()
            status.disk_usage = self._get_disk_usage()
        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {e}")
        
        # 收集任务状态
        if self.opc_manager:
            try:
                task_stats = self.opc_manager.task_executor.get_statistics()
                status.active_tasks = task_stats.get("active_workers", 0)
                status.pending_tasks = task_stats.get("queue_size", 0)
                status.completed_tasks = task_stats.get("completed_tasks", 0)
                status.failed_tasks = task_stats.get("failed_tasks", 0)
            except Exception as e:
                self.logger.warning(f"Failed to collect task metrics: {e}")
            
            # 检查数据库状态
            try:
                if self.opc_manager.db_manager:
                    status.database_status = "healthy"
                else:
                    status.database_status = "unavailable"
            except Exception as e:
                status.database_status = "error"
                status.errors.append(f"Database error: {e}")
            
            # 检查LLM状态
            try:
                status.llm_status = self._check_llm_status()
            except Exception as e:
                status.llm_status = "error"
                status.errors.append(f"LLM error: {e}")
        
        return status
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            import psutil
            return psutil.cpu_percent(interval=1)
        except ImportError:
            return 0.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            return 0.0
    
    def _get_disk_usage(self) -> float:
        """获取磁盘使用率"""
        try:
            import psutil
            return psutil.disk_usage('/').percent
        except ImportError:
            return 0.0
    
    def _check_llm_status(self) -> str:
        """检查LLM服务状态"""
        try:
            from zeroclaw_integration import ZeroClawIntegration
            zc = ZeroClawIntegration()
            if zc.auth_token:
                return "healthy"
            else:
                return "not_configured"
        except Exception:
            return "unavailable"
    
    def _check_alerts(self, status: SystemStatus) -> List[Any]:
        """检查告警条件
        
        Args:
            status: 当前系统状态
            
        Returns:
            告警列表
        """
        from .alerts import Alert, AlertLevel
        
        alerts = []
        
        # CPU使用率告警
        if status.cpu_usage > 90:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                source="system_monitor",
                message=f"CPU使用率过高: {status.cpu_usage:.1f}%",
                details={"cpu_usage": status.cpu_usage}
            ))
        elif status.cpu_usage > 80:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                source="system_monitor",
                message=f"CPU使用率较高: {status.cpu_usage:.1f}%",
                details={"cpu_usage": status.cpu_usage}
            ))
        
        # 内存使用率告警
        if status.memory_usage > 90:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                source="system_monitor",
                message=f"内存使用率过高: {status.memory_usage:.1f}%",
                details={"memory_usage": status.memory_usage}
            ))
        elif status.memory_usage > 80:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                source="system_monitor",
                message=f"内存使用率较高: {status.memory_usage:.1f}%",
                details={"memory_usage": status.memory_usage}
            ))
        
        # 磁盘使用率告警
        if status.disk_usage > 90:
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                source="system_monitor",
                message=f"磁盘使用率过高: {status.disk_usage:.1f}%",
                details={"disk_usage": status.disk_usage}
            ))
        
        # 任务失败告警
        if status.failed_tasks > 10:
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                source="system_monitor",
                message=f"失败任务过多: {status.failed_tasks}",
                details={"failed_tasks": status.failed_tasks}
            ))
        
        # 数据库状态告警
        if status.database_status == "error":
            alerts.append(Alert(
                level=AlertLevel.CRITICAL,
                source="system_monitor",
                message="数据库连接异常",
                details={"database_status": status.database_status}
            ))
        
        # LLM状态告警
        if status.llm_status == "error":
            alerts.append(Alert(
                level=AlertLevel.WARNING,
                source="system_monitor",
                message="LLM服务异常",
                details={"llm_status": status.llm_status}
            ))
        
        return alerts
    
    def get_current_status(self) -> SystemStatus:
        """获取当前状态"""
        return self._collect_status()
    
    def get_status_history(self, limit: int = 100) -> List[SystemStatus]:
        """获取历史状态
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            历史状态列表
        """
        return self.status_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.status_history:
            return {"error": "No data available"}
        
        recent = self.status_history[-10:]
        
        return {
            "state": self.state.value,
            "check_interval": self.check_interval,
            "history_size": len(self.status_history),
            "avg_cpu": sum(s.cpu_usage for s in recent) / len(recent),
            "avg_memory": sum(s.memory_usage for s in recent) / len(recent),
            "total_completed": self.status_history[-1].completed_tasks if self.status_history else 0,
            "total_failed": self.status_history[-1].failed_tasks if self.status_history else 0,
            "active_alerts": len(self.alert_manager.active_alerts)
        }
    
    def run_health_check(self) -> Dict[str, Any]:
        """运行健康检查"""
        return self.health_checker.run_all_checks()
