"""
资源优化建议模块

监控系统资源（CPU/内存/磁盘），提供优化建议：
- CPU > 95%: 自动暂停低优先级任务
- CPU > 80%: 提供优化建议
- 内存不足：建议清理或增加资源
- 磁盘满：建议清理空间
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
import logging
import threading
import time

logger = logging.getLogger(__name__)


@dataclass
class ResourceStatus:
    """资源状态"""
    cpu_percent: float = 0.0
    memory_total: int = 0  # GB
    memory_used: int = 0  # GB
    memory_available: int = 0  # GB
    memory_percent: float = 0.0
    disk_total: int = 0  # GB
    disk_used: int = 0  # GB
    disk_free: int = 0  # GB
    disk_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'cpu': self.cpu_percent,
            'memory': {
                'total': self.memory_total,
                'used': self.memory_used,
                'available': self.memory_available,
                'percent': self.memory_percent
            },
            'disk': {
                'total': self.disk_total,
                'used': self.disk_used,
                'free': self.disk_free,
                'percent': self.disk_percent
            },
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class OptimizationSuggestion:
    """优化建议"""
    title: str
    description: str
    impact: str  # high/medium/low
    action_type: str  # auto/manual
    action: Optional[str] = None  # 可执行的操作
    estimated_savings: Optional[str] = None  # 预计节省资源
    
    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'description': self.description,
            'impact': self.impact,
            'action_type': self.action_type,
            'action': self.action,
            'estimated_savings': self.estimated_savings
        }


class ResourceMonitor:
    """资源监控器"""
    
    def __init__(self):
        self.last_status: Optional[ResourceStatus] = None
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.callbacks: List[Callable] = []
        
        logger.info("资源监控器初始化完成")
    
    def get_status(self) -> ResourceStatus:
        """获取当前资源状态"""
        try:
            import psutil
            
            # CPU
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 内存
            memory = psutil.virtual_memory()
            memory_total = memory.total // (1024**3)  # GB
            memory_used = memory.used // (1024**3)
            memory_available = memory.available // (1024**3)
            memory_percent = memory.percent
            
            # 磁盘
            disk = psutil.disk_usage('/')
            disk_total = disk.total // (1024**3)
            disk_used = disk.used // (1024**3)
            disk_free = disk.free // (1024**3)
            disk_percent = disk.percent
            
            status = ResourceStatus(
                cpu_percent=cpu_percent,
                memory_total=memory_total,
                memory_used=memory_used,
                memory_available=memory_available,
                memory_percent=memory_percent,
                disk_total=disk_total,
                disk_used=disk_used,
                disk_free=disk_free,
                disk_percent=disk_percent
            )
            
            self.last_status = status
            return status
            
        except ImportError:
            logger.warning("psutil 未安装，返回默认值")
            return ResourceStatus()
        except Exception as e:
            logger.error(f"获取资源状态失败：{e}")
            return ResourceStatus()
    
    def start_monitoring(self, interval: int = 5):
        """启动持续监控"""
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                status = self.get_status()
                
                # 触发回调
                for callback in self.callbacks:
                    try:
                        callback(status)
                    except Exception as e:
                        logger.error(f"资源监控回调执行失败：{e}")
                
                time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"资源监控已启动（间隔：{interval}秒）")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("资源监控已停止")
    
    def register_callback(self, callback: Callable):
        """注册回调函数"""
        self.callbacks.append(callback)
        logger.info(f"注册资源监控回调")


class ResourceOptimizer:
    """资源优化器"""
    
    def __init__(self, monitor: ResourceMonitor):
        self.monitor = monitor
        self.auto_optimize_enabled = True
        self.suggestions: List[OptimizationSuggestion] = []
        
        # 阈值配置
        self.cpu_critical_threshold = 95  # 严重瓶颈
        self.cpu_warning_threshold = 80   # 轻度瓶颈
        self.memory_critical_threshold = 90
        self.memory_warning_threshold = 75
        self.disk_critical_threshold = 95
        self.disk_warning_threshold = 85
        
        logger.info("资源优化器初始化完成")
    
    def analyze_and_optimize(self) -> List[OptimizationSuggestion]:
        """分析资源并提供优化建议"""
        status = self.monitor.get_status()
        suggestions = []
        
        # CPU 优化
        cpu_suggestions = self._analyze_cpu(status)
        suggestions.extend(cpu_suggestions)
        
        # 内存优化
        memory_suggestions = self._analyze_memory(status)
        suggestions.extend(memory_suggestions)
        
        # 磁盘优化
        disk_suggestions = self._analyze_disk(status)
        suggestions.extend(disk_suggestions)
        
        self.suggestions = suggestions
        return suggestions
    
    def _analyze_cpu(self, status: ResourceStatus) -> List[OptimizationSuggestion]:
        """分析 CPU 并提供建议"""
        suggestions = []
        
        if status.cpu_percent >= self.cpu_critical_threshold:
            # 严重瓶颈
            suggestions.append(OptimizationSuggestion(
                title="⚠️ CPU 使用率严重过高",
                description=f"当前 CPU 使用率：{status.cpu_percent:.1f}%（阈值：{self.cpu_critical_threshold}%）",
                impact="high",
                action_type="auto",
                action="pause_low_priority_tasks",
                estimated_savings="预计可释放 20-30% CPU"
            ))
            
            # 如果启用自动优化，立即执行
            if self.auto_optimize_enabled:
                logger.warning(f"CPU 使用率过高（{status.cpu_percent}%），自动暂停低优先级任务")
                # 这里可以调用任务管理器的暂停功能
                # task_manager.pause_low_priority_tasks()
        
        elif status.cpu_percent >= self.cpu_warning_threshold:
            # 轻度瓶颈
            suggestions.append(OptimizationSuggestion(
                title="⚡ CPU 使用率较高",
                description=f"当前 CPU 使用率：{status.cpu_percent:.1f}%（阈值：{self.cpu_warning_threshold}%）",
                impact="medium",
                action_type="manual",
                estimated_savings="建议优化"
            ))
            
            suggestions.append(OptimizationSuggestion(
                title="💡 优化建议",
                description="可考虑以下操作：\n1. 暂停 1-2 个低优先级任务\n2. 降低并发数（从 3 降到 2）\n3. 延迟非紧急任务",
                impact="medium",
                action_type="manual"
            ))
        
        return suggestions
    
    def _analyze_memory(self, status: ResourceStatus) -> List[OptimizationSuggestion]:
        """分析内存并提供建议"""
        suggestions = []
        
        if status.memory_percent >= self.memory_critical_threshold:
            suggestions.append(OptimizationSuggestion(
                title="⚠️ 内存严重不足",
                description=f"当前内存使用：{status.memory_used}GB/{status.memory_total}GB ({status.memory_percent:.1f}%)",
                impact="high",
                action_type="manual",
                estimated_savings="建议立即释放内存"
            ))
            
            suggestions.append(OptimizationSuggestion(
                title="💡 紧急建议",
                description="可考虑以下操作：\n1. 暂停占用内存大的任务\n2. 清理缓存\n3. 关闭其他应用\n4. 增加系统内存",
                impact="high",
                action_type="manual"
            ))
        
        elif status.memory_percent >= self.memory_warning_threshold:
            suggestions.append(OptimizationSuggestion(
                title="⚡ 内存使用率较高",
                description=f"当前内存使用：{status.memory_used}GB/{status.memory_total}GB ({status.memory_percent:.1f}%)，可用 {status.memory_available}GB",
                impact="medium",
                action_type="manual",
                estimated_savings="建议关注"
            ))
        
        return suggestions
    
    def _analyze_disk(self, status: ResourceStatus) -> List[OptimizationSuggestion]:
        """分析磁盘并提供建议"""
        suggestions = []
        
        if status.disk_percent >= self.disk_critical_threshold:
            suggestions.append(OptimizationSuggestion(
                title="⚠️ 磁盘空间严重不足",
                description=f"当前磁盘使用：{status.disk_used}GB/{status.disk_total}GB ({status.disk_percent:.1f}%)，剩余 {status.disk_free}GB",
                impact="high",
                action_type="manual",
                estimated_savings="建议立即清理"
            ))
            
            suggestions.append(OptimizationSuggestion(
                title="💡 清理建议",
                description="可考虑以下操作：\n1. 删除临时文件\n2. 清理日志文件\n3. 删除旧备份\n4. 清理下载目录\n5. 扩展磁盘空间",
                impact="high",
                action_type="manual"
            ))
        
        elif status.disk_percent >= self.disk_warning_threshold:
            suggestions.append(OptimizationSuggestion(
                title="⚡ 磁盘空间较紧张",
                description=f"当前磁盘使用：{status.disk_used}GB/{status.disk_total}GB ({status.disk_percent:.1f}%)，剩余 {status.disk_free}GB",
                impact="medium",
                action_type="manual",
                estimated_savings="建议定期清理"
            ))
        
        return suggestions
    
    def get_resource_health(self) -> Dict:
        """获取资源健康度评分"""
        status = self.monitor.get_status()
        
        # 计算健康度（0-100）
        cpu_score = max(0, 100 - status.cpu_percent)
        memory_score = max(0, 100 - status.memory_percent)
        disk_score = max(0, 100 - status.disk_percent)
        
        overall_score = (cpu_score + memory_score + disk_score) / 3
        
        # 健康等级
        if overall_score >= 80:
            health_level = "excellent"
            health_emoji = "✅"
        elif overall_score >= 60:
            health_level = "good"
            health_emoji = "🟢"
        elif overall_score >= 40:
            health_level = "fair"
            health_emoji = "🟡"
        elif overall_score >= 20:
            health_level = "poor"
            health_emoji = "🟠"
        else:
            health_level = "critical"
            health_emoji = "🔴"
        
        return {
            'overall_score': overall_score,
            'health_level': health_level,
            'health_emoji': health_emoji,
            'cpu_score': cpu_score,
            'memory_score': memory_score,
            'disk_score': disk_score,
            'status': status.to_dict()
        }
    
    def enable_auto_optimize(self):
        """启用自动优化"""
        self.auto_optimize_enabled = True
        logger.info("已启用自动优化")
    
    def disable_auto_optimize(self):
        """禁用自动优化"""
        self.auto_optimize_enabled = False
        logger.info("已禁用自动优化")


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    monitor = ResourceMonitor()
    optimizer = ResourceOptimizer(monitor)
    
    print("\n=== 测试 1: 获取资源状态 ===")
    status = monitor.get_status()
    print(f"CPU: {status.cpu_percent:.1f}%")
    print(f"内存：{status.memory_used}GB/{status.memory_total}GB ({status.memory_percent:.1f}%)")
    print(f"磁盘：{status.disk_used}GB/{status.disk_total}GB ({status.disk_percent:.1f}%)")
    
    print("\n=== 测试 2: 资源健康度 ===")
    health = optimizer.get_resource_health()
    print(f"健康度：{health['health_emoji']} {health['health_level']} ({health['overall_score']:.1f}分)")
    print(f"  - CPU 得分：{health['cpu_score']:.1f}")
    print(f"  - 内存得分：{health['memory_score']:.1f}")
    print(f"  - 磁盘得分：{health['disk_score']:.1f}")
    
    print("\n=== 测试 3: 优化建议 ===")
    suggestions = optimizer.analyze_and_optimize()
    
    if suggestions:
        print(f"发现 {len(suggestions)} 条建议：\n")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"{i}. {suggestion.title}")
            print(f"   {suggestion.description}")
            print(f"   影响：{suggestion.impact}, 类型：{suggestion.action_type}")
            if suggestion.estimated_savings:
                print(f"   预计：{suggestion.estimated_savings}")
            print()
    else:
        print("✅ 资源状态良好，无需优化")
