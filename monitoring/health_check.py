#!/usr/bin/env python3
"""
Health Check for OPC-Agents

Performs health checks on various system components.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "duration": self.duration
        }


class HealthChecker:
    """健康检查器
    
    检查系统各组件的健康状态。
    """
    
    def __init__(self, opc_manager=None):
        """初始化健康检查器
        
        Args:
            opc_manager: OPCManager实例
        """
        self.opc_manager = opc_manager
        self.logger = logging.getLogger("OPC-Agents.HealthCheck")
        
        # 检查结果缓存
        self._last_results: Dict[str, HealthCheckResult] = {}
        
        # 自定义检查函数
        self._custom_checks: Dict[str, Callable] = {}
        
        self.logger.info("HealthChecker initialized")
    
    def register_check(self, name: str, check_func: Callable[[], HealthCheckResult]):
        """注册自定义检查
        
        Args:
            name: 检查名称
            check_func: 检查函数
        """
        self._custom_checks[name] = check_func
        self.logger.info(f"Custom health check registered: {name}")
    
    def run_all_checks(self) -> Dict[str, Any]:
        """运行所有健康检查
        
        Returns:
            检查结果字典
        """
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        # 运行内置检查
        results["database"] = self.check_database()
        results["task_executor"] = self.check_task_executor()
        results["communication_manager"] = self.check_communication_manager()
        results["llm_service"] = self.check_llm_service()
        results["message_queue"] = self.check_message_queue()
        results["file_system"] = self.check_file_system()
        
        # 运行自定义检查
        for name, check_func in self._custom_checks.items():
            try:
                results[name] = check_func()
            except Exception as e:
                results[name] = HealthCheckResult(
                    component=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {e}"
                )
        
        # 计算整体状态
        for result in results.values():
            if result.status == HealthStatus.UNHEALTHY:
                overall_status = HealthStatus.UNHEALTHY
                break
            elif result.status == HealthStatus.DEGRADED:
                overall_status = HealthStatus.DEGRADED
        
        # 缓存结果
        self._last_results = results
        
        return {
            "overall_status": overall_status.value,
            "timestamp": time.time(),
            "checks": {k: v.to_dict() for k, v in results.items()}
        }
    
    def check_database(self) -> HealthCheckResult:
        """检查数据库健康状态"""
        start_time = time.time()
        
        try:
            if not self.opc_manager or not self.opc_manager.db_manager:
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.UNKNOWN,
                    message="Database manager not initialized"
                )
            
            # 尝试执行简单查询
            db = self.opc_manager.db_manager
            tasks = db.get_all_tasks()
            
            duration = time.time() - start_time
            
            return HealthCheckResult(
                component="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                details={"task_count": len(tasks)},
                duration=duration
            )
            
        except Exception as e:
            return HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {e}",
                duration=time.time() - start_time
            )
    
    def check_task_executor(self) -> HealthCheckResult:
        """检查任务执行器健康状态"""
        start_time = time.time()
        
        try:
            if not self.opc_manager or not self.opc_manager.task_executor:
                return HealthCheckResult(
                    component="task_executor",
                    status=HealthStatus.UNKNOWN,
                    message="Task executor not initialized"
                )
            
            executor = self.opc_manager.task_executor
            stats = executor.get_statistics()
            
            # 检查是否有过多失败任务
            failed_rate = 0
            total = stats.get("completed_tasks", 0) + stats.get("failed_tasks", 0)
            if total > 0:
                failed_rate = stats.get("failed_tasks", 0) / total
            
            if failed_rate > 0.5:
                status = HealthStatus.UNHEALTHY
                message = f"High failure rate: {failed_rate:.1%}"
            elif failed_rate > 0.2:
                status = HealthStatus.DEGRADED
                message = f"Elevated failure rate: {failed_rate:.1%}"
            else:
                status = HealthStatus.HEALTHY
                message = "Task executor running normally"
            
            return HealthCheckResult(
                component="task_executor",
                status=status,
                message=message,
                details=stats,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                component="task_executor",
                status=HealthStatus.UNHEALTHY,
                message=f"Task executor check failed: {e}",
                duration=time.time() - start_time
            )
    
    def check_communication_manager(self) -> HealthCheckResult:
        """检查通信管理器健康状态"""
        start_time = time.time()
        
        try:
            if not self.opc_manager or not self.opc_manager.communication_manager:
                return HealthCheckResult(
                    component="communication_manager",
                    status=HealthStatus.UNKNOWN,
                    message="Communication manager not initialized"
                )
            
            cm = self.opc_manager.communication_manager
            tasks = cm.get_all_tasks()
            
            return HealthCheckResult(
                component="communication_manager",
                status=HealthStatus.HEALTHY,
                message="Communication manager operational",
                details={"tracked_tasks": len(tasks)},
                duration=time.time() - start_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                component="communication_manager",
                status=HealthStatus.UNHEALTHY,
                message=f"Communication manager check failed: {e}",
                duration=time.time() - start_time
            )
    
    def check_llm_service(self) -> HealthCheckResult:
        """检查LLM服务健康状态"""
        start_time = time.time()
        
        try:
            from zeroclaw_integration import ZeroClawIntegration
            
            zc = ZeroClawIntegration()
            
            if not zc.auth_token:
                return HealthCheckResult(
                    component="llm_service",
                    status=HealthStatus.DEGRADED,
                    message="LLM service not configured",
                    details={"auth_status": "not_configured"},
                    duration=time.time() - start_time
                )
            
            return HealthCheckResult(
                component="llm_service",
                status=HealthStatus.HEALTHY,
                message="LLM service configured",
                details={"auth_status": "configured"},
                duration=time.time() - start_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                component="llm_service",
                status=HealthStatus.UNHEALTHY,
                message=f"LLM service check failed: {e}",
                duration=time.time() - start_time
            )
    
    def check_message_queue(self) -> HealthCheckResult:
        """检查消息队列健康状态"""
        start_time = time.time()
        
        try:
            if not self.opc_manager or not self.opc_manager.communication_manager:
                return HealthCheckResult(
                    component="message_queue",
                    status=HealthStatus.UNKNOWN,
                    message="Communication manager not available"
                )
            
            cm = self.opc_manager.communication_manager
            
            if not cm.message_queue:
                return HealthCheckResult(
                    component="message_queue",
                    status=HealthStatus.DEGRADED,
                    message="Message queue not enabled",
                    duration=time.time() - start_time
                )
            
            stats = cm.get_queue_statistics()
            
            return HealthCheckResult(
                component="message_queue",
                status=HealthStatus.HEALTHY,
                message="Message queue operational",
                details=stats,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            return HealthCheckResult(
                component="message_queue",
                status=HealthStatus.UNHEALTHY,
                message=f"Message queue check failed: {e}",
                duration=time.time() - start_time
            )
    
    def check_file_system(self) -> HealthCheckResult:
        """检查文件系统健康状态"""
        start_time = time.time()
        
        try:
            import os
            import shutil
            
            # 检查数据目录
            data_dir = "data_storage"
            if os.path.exists(data_dir):
                total, used, free = shutil.disk_usage(data_dir)
                free_percent = (free / total) * 100
                
                if free_percent < 5:
                    status = HealthStatus.UNHEALTHY
                    message = f"Disk space critical: {free_percent:.1f}% free"
                elif free_percent < 15:
                    status = HealthStatus.DEGRADED
                    message = f"Disk space low: {free_percent:.1f}% free"
                else:
                    status = HealthStatus.HEALTHY
                    message = f"Disk space adequate: {free_percent:.1f}% free"
                
                return HealthCheckResult(
                    component="file_system",
                    status=status,
                    message=message,
                    details={
                        "total_gb": total / (1024**3),
                        "used_gb": used / (1024**3),
                        "free_gb": free / (1024**3),
                        "free_percent": free_percent
                    },
                    duration=time.time() - start_time
                )
            else:
                return HealthCheckResult(
                    component="file_system",
                    status=HealthStatus.UNKNOWN,
                    message="Data directory not found",
                    duration=time.time() - start_time
                )
            
        except Exception as e:
            return HealthCheckResult(
                component="file_system",
                status=HealthStatus.UNHEALTHY,
                message=f"File system check failed: {e}",
                duration=time.time() - start_time
            )
    
    def get_last_results(self) -> Dict[str, HealthCheckResult]:
        """获取上次检查结果"""
        return self._last_results.copy()
    
    def get_component_status(self, component: str) -> Optional[HealthCheckResult]:
        """获取指定组件状态"""
        return self._last_results.get(component)
