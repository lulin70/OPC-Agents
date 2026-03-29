#!/usr/bin/env python3
"""
Alert Manager for OPC-Agents

Manages system alerts, notifications, and alert rules.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警对象"""
    level: AlertLevel
    source: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: f"alert_{int(time.time() * 1000)}")
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at
        }


class AlertRule:
    """告警规则"""
    
    def __init__(self, name: str, condition: Callable[[Any], bool],
                 level: AlertLevel, message_template: str,
                 cooldown: int = 300):
        """初始化告警规则
        
        Args:
            name: 规则名称
            condition: 条件函数
            level: 告警级别
            message_template: 消息模板
            cooldown: 冷却时间（秒）
        """
        self.name = name
        self.condition = condition
        self.level = level
        self.message_template = message_template
        self.cooldown = cooldown
        self.last_triggered = 0


class AlertManager:
    """告警管理器
    
    管理告警的生命周期，包括创建、确认、解决和通知。
    """
    
    def __init__(self, max_alerts: int = 1000):
        """初始化告警管理器
        
        Args:
            max_alerts: 最大保留告警数
        """
        self.max_alerts = max_alerts
        self.logger = logging.getLogger("OPC-Agents.Alerts")
        
        # 告警存储
        self._alerts: Dict[str, Alert] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        
        # 告警规则
        self._rules: Dict[str, AlertRule] = {}
        
        # 锁
        self._lock = threading.Lock()
        
        # 回调函数
        self.on_alert_created: Optional[Callable] = None
        self.on_alert_resolved: Optional[Callable] = None
        
        # 初始化默认规则
        self._init_default_rules()
        
        self.logger.info("AlertManager initialized")
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        # CPU告警规则
        self.add_rule(AlertRule(
            name="high_cpu",
            condition=lambda s: getattr(s, 'cpu_usage', 0) > 80,
            level=AlertLevel.WARNING,
            message_template="CPU使用率过高: {cpu_usage:.1f}%",
            cooldown=300
        ))
        
        # 内存告警规则
        self.add_rule(AlertRule(
            name="high_memory",
            condition=lambda s: getattr(s, 'memory_usage', 0) > 80,
            level=AlertLevel.WARNING,
            message_template="内存使用率过高: {memory_usage:.1f}%",
            cooldown=300
        ))
        
        # 任务失败告警规则
        self.add_rule(AlertRule(
            name="task_failures",
            condition=lambda s: getattr(s, 'failed_tasks', 0) > 5,
            level=AlertLevel.WARNING,
            message_template="失败任务过多: {failed_tasks}",
            cooldown=600
        ))
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则
        
        Args:
            rule: 告警规则
        """
        with self._lock:
            self._rules[rule.name] = rule
        self.logger.info(f"Alert rule added: {rule.name}")
    
    def remove_rule(self, name: str):
        """移除告警规则
        
        Args:
            name: 规则名称
        """
        with self._lock:
            if name in self._rules:
                del self._rules[name]
        self.logger.info(f"Alert rule removed: {name}")
    
    def check_rules(self, status: Any) -> List[Alert]:
        """检查所有规则
        
        Args:
            status: 系统状态
            
        Returns:
            触发的告警列表
        """
        triggered_alerts = []
        now = time.time()
        
        with self._lock:
            for name, rule in self._rules.items():
                # 检查冷却时间
                if now - rule.last_triggered < rule.cooldown:
                    continue
                
                # 检查条件
                try:
                    if rule.condition(status):
                        alert = Alert(
                            level=rule.level,
                            source=f"rule:{name}",
                            message=rule.message_template.format(**status.__dict__ if hasattr(status, '__dict__') else {})
                        )
                        triggered_alerts.append(alert)
                        rule.last_triggered = now
                except Exception as e:
                    self.logger.error(f"Error checking rule {name}: {e}")
        
        # 添加触发的告警
        for alert in triggered_alerts:
            self.add_alert(alert)
        
        return triggered_alerts
    
    def add_alert(self, alert: Alert):
        """添加告警
        
        Args:
            alert: 告警对象
        """
        with self._lock:
            self._alerts[alert.id] = alert
            self._active_alerts[alert.id] = alert
            
            # 限制历史大小
            if len(self._alert_history) >= self.max_alerts:
                self._alert_history.pop(0)
            self._alert_history.append(alert)
        
        self.logger.warning(f"Alert created: [{alert.level.value}] {alert.message}")
        
        # 回调
        if self.on_alert_created:
            self.on_alert_created(alert)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警
        
        Args:
            alert_id: 告警ID
            
        Returns:
            是否成功
        """
        with self._lock:
            if alert_id in self._alerts:
                self._alerts[alert_id].acknowledged = True
                self.logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警
        
        Args:
            alert_id: 告警ID
            
        Returns:
            是否成功
        """
        with self._lock:
            if alert_id in self._alerts:
                alert = self._alerts[alert_id]
                alert.resolved = True
                alert.resolved_at = time.time()
                
                if alert_id in self._active_alerts:
                    del self._active_alerts[alert_id]
                
                self.logger.info(f"Alert resolved: {alert_id}")
                
                # 回调
                if self.on_alert_resolved:
                    self.on_alert_resolved(alert)
                
                return True
        return False
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """获取告警
        
        Args:
            alert_id: 告警ID
            
        Returns:
            告警对象
        """
        return self._alerts.get(alert_id)
    
    def get_active_alerts(self, level: AlertLevel = None) -> List[Alert]:
        """获取活跃告警
        
        Args:
            level: 过滤级别（可选）
            
        Returns:
            活跃告警列表
        """
        with self._lock:
            alerts = list(self._active_alerts.values())
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_alert_history(self, limit: int = 100, level: AlertLevel = None) -> List[Alert]:
        """获取告警历史
        
        Args:
            limit: 返回数量限制
            level: 过滤级别（可选）
            
        Returns:
            告警历史列表
        """
        with self._lock:
            alerts = self._alert_history.copy()
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            return alerts[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        with self._lock:
            level_counts = {}
            for level in AlertLevel:
                level_counts[level.value] = sum(
                    1 for a in self._alert_history if a.level == level
                )
            
            return {
                "total_alerts": len(self._alert_history),
                "active_alerts": len(self._active_alerts),
                "acknowledged": sum(1 for a in self._alerts.values() if a.acknowledged),
                "resolved": sum(1 for a in self._alerts.values() if a.resolved),
                "by_level": level_counts
            }
    
    def clear_resolved(self):
        """清除已解决的告警"""
        with self._lock:
            resolved_ids = [
                aid for aid, alert in self._alerts.items()
                if alert.resolved
            ]
            for aid in resolved_ids:
                del self._alerts[aid]
            
            self.logger.info(f"Cleared {len(resolved_ids)} resolved alerts")
    
    def clear_all(self):
        """清除所有告警"""
        with self._lock:
            self._alerts.clear()
            self._active_alerts.clear()
            self._alert_history.clear()
        
        self.logger.info("All alerts cleared")
