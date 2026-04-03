"""
通知分级系统

实现 4 级通知：
- P0 - 紧急：任务失败且需用户决策 → 实时推送（站内 + 邮件/微信）
- P1 - 重要：任务完成（用户等待中） → 实时推送（站内消息）
- P2 - 普通：任务完成（非紧急） → 批量汇总（每日报告）
- P3 - 低优先级：后台任务完成 → 不通知（可查询）
"""

from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class NotificationLevel(Enum):
    """通知级别"""
    P0_URGENT = "p0_urgent"        # 紧急 - 实时推送
    P1_IMPORTANT = "p1_important"  # 重要 - 实时推送
    P2_NORMAL = "p2_normal"        # 普通 - 批量汇总
    P3_LOW = "p3_low"              # 低优先级 - 不通知


class NotificationChannel(Enum):
    """通知渠道"""
    IN_APP = "in_app"      # 站内消息
    EMAIL = "email"        # 邮件
    WECHAT = "wechat"      # 微信
    DINGTALK = "dingtalk"  # 钉钉
    CONSOLE = "console"    # 控制台（调试用）


@dataclass
class Notification:
    """通知对象"""
    level: NotificationLevel
    title: str
    message: str
    task_id: Optional[str] = None
    task_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    channels: List[NotificationChannel] = field(default_factory=list)
    read: bool = False
    id: str = field(default_factory=lambda: f"notif_{datetime.now().timestamp()}")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'task_id': self.task_id,
            'task_name': self.task_name,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'channels': [c.value for c in self.channels],
            'read': self.read
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Notification':
        """从字典创建"""
        return cls(
            id=data.get('id', f"notif_{datetime.now().timestamp()}"),
            level=NotificationLevel(data['level']),
            title=data['title'],
            message=data['message'],
            task_id=data.get('task_id'),
            task_name=data.get('task_name'),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            metadata=data.get('metadata', {}),
            channels=[NotificationChannel(c) for c in data.get('channels', [])],
            read=data.get('read', False)
        )


@dataclass
class NotificationPreferences:
    """用户通知偏好"""
    # P0 紧急通知
    p0_in_app: bool = True
    p0_email: bool = True
    p0_wechat: bool = False
    
    # P1 重要通知
    p1_in_app: bool = True
    p1_email: bool = False
    
    # P2 普通通知
    p2_daily_digest: bool = True
    p2_instant: bool = False
    
    # P3 低优先级
    p3_enabled: bool = False
    
    # 免打扰时段
    quiet_hours_start: int = 22  # 22:00
    quiet_hours_end: int = 8     # 08:00
    
    def get_channels_for_level(self, level: NotificationLevel) -> List[NotificationChannel]:
        """获取指定级别的通知渠道"""
        channels = []
        
        if level == NotificationLevel.P0_URGENT:
            if self.p0_in_app:
                channels.append(NotificationChannel.IN_APP)
            if self.p0_email:
                channels.append(NotificationChannel.EMAIL)
            if self.p0_wechat:
                channels.append(NotificationChannel.WECHAT)
        
        elif level == NotificationLevel.P1_IMPORTANT:
            if self.p1_in_app:
                channels.append(NotificationChannel.IN_APP)
            if self.p1_email:
                channels.append(NotificationChannel.EMAIL)
        
        elif level == NotificationLevel.P2_NORMAL:
            # P2 默认只添加到每日汇总
            pass
        
        elif level == NotificationLevel.P3_LOW:
            if self.p3_enabled:
                channels.append(NotificationChannel.IN_APP)
        
        return channels


class NotificationSender:
    """通知发送器（接口）"""
    
    def send(self, notification: Notification, user_id: str):
        """发送通知（子类实现）"""
        raise NotImplementedError


class ConsoleNotificationSender(NotificationSender):
    """控制台通知发送器（调试用）"""
    
    def send(self, notification: Notification, user_id: str):
        """在控制台打印通知"""
        emoji = {
            NotificationLevel.P0_URGENT: "🔴",
            NotificationLevel.P1_IMPORTANT: "🟡",
            NotificationLevel.P2_NORMAL: "🟢",
            NotificationLevel.P3_LOW: "⚪"
        }
        
        print(f"\n{emoji.get(notification.level, '📬')} [{notification.level.value.upper()}]")
        print(f"标题：{notification.title}")
        print(f"消息：{notification.message}")
        if notification.task_name:
            print(f"任务：{notification.task_name}")
        print(f"时间：{notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 60)


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, user_id: str = 'default'):
        self.user_id = user_id
        self.preferences = NotificationPreferences()
        
        # 通知存储
        self.notifications: List[Notification] = []
        self.daily_digest: List[Notification] = []
        
        # 通知发送器
        self.senders: Dict[NotificationChannel, NotificationSender] = {
            NotificationChannel.CONSOLE: ConsoleNotificationSender()
            # 可以添加 EmailSender, WeChatSender 等
        }
        
        # 每日汇总定时器
        self.digest_thread = None
        self.digest_time = "08:00"  # 默认早上 8 点发送每日汇总
        
        # 回调函数
        self.callbacks: Dict[NotificationLevel, List[Callable]] = defaultdict(list)
        
        # 锁
        self.lock = threading.Lock()
        
        logger.info(f"通知管理器初始化完成 (用户：{user_id})")
    
    def set_preferences(self, preferences: NotificationPreferences):
        """设置用户偏好"""
        self.preferences = preferences
        logger.info("更新用户通知偏好")
    
    def register_callback(self, level: NotificationLevel, callback: Callable):
        """注册通知回调"""
        self.callbacks[level].append(callback)
        logger.info(f"注册 {level.value} 通知回调")
    
    def notify(self, level: NotificationLevel, title: str, message: str,
               task_id: Optional[str] = None, task_name: Optional[str] = None,
               metadata: Optional[Dict] = None):
        """
        发送通知
        
        Args:
            level: 通知级别
            title: 标题
            message: 消息
            task_id: 任务 ID
            task_name: 任务名称
            metadata: 元数据
        """
        # 创建通知对象
        notification = Notification(
            level=level,
            title=title,
            message=message,
            task_id=task_id,
            task_name=task_name,
            metadata=metadata or {}
        )
        
        # 检查免打扰时段
        if self._is_quiet_hours():
            if level == NotificationLevel.P2_NORMAL or level == NotificationLevel.P3_LOW:
                logger.info(f"免打扰时段，延迟发送 {level.value} 通知")
                # 添加到待发送队列
                with self.lock:
                    self.daily_digest.append(notification)
                return
        
        # 获取通知渠道
        channels = self.preferences.get_channels_for_level(level)
        notification.channels = channels
        
        # 存储通知
        with self.lock:
            self.notifications.append(notification)
            
            # P2 级别添加到每日汇总
            if level == NotificationLevel.P2_NORMAL:
                self.daily_digest.append(notification)
        
        # 发送通知
        self._send_notification(notification)
        
        # 触发回调
        self._trigger_callbacks(level, notification)
        
        logger.info(f"发送 {level.value} 通知：{title}")
    
    def notify_task_complete(self, task_id: str, task_name: str, 
                            is_urgent: bool = False, user_waiting: bool = False):
        """
        通知任务完成
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            is_urgent: 是否紧急
            user_waiting: 用户是否正在等待
        """
        if is_urgent or user_waiting:
            # P1 重要
            self.notify(
                level=NotificationLevel.P1_IMPORTANT,
                title="✅ 任务完成",
                message=f"任务 '{task_name}' 已完成，请查看结果。",
                task_id=task_id,
                task_name=task_name
            )
        else:
            # P2 普通（添加到每日汇总）
            self.notify(
                level=NotificationLevel.P2_NORMAL,
                title="任务完成",
                message=f"任务 '{task_name}' 已完成",
                task_id=task_id,
                task_name=task_name
            )
    
    def notify_task_failed(self, task_id: str, task_name: str, 
                          error_message: str, requires_decision: bool = True,
                          suggestion: Optional[str] = None):
        """
        通知任务失败
        
        Args:
            task_id: 任务 ID
            task_name: 任务名称
            error_message: 错误消息
            requires_decision: 是否需要用户决策
            suggestion: 建议
        """
        if requires_decision:
            # P0 紧急
            title = "🔴 任务失败（需要确认）"
            message = f"任务 '{task_name}' 执行失败：{error_message}\n\n建议：{suggestion or '请检查后重试'}"
            
            self.notify(
                level=NotificationLevel.P0_URGENT,
                title=title,
                message=message,
                task_id=task_id,
                task_name=task_name,
                metadata={'error': error_message, 'suggestion': suggestion}
            )
        else:
            # P1 重要
            self.notify(
                level=NotificationLevel.P1_IMPORTANT,
                title="❌ 任务失败",
                message=f"任务 '{task_name}' 执行失败：{error_message}",
                task_id=task_id,
                task_name=task_name,
                metadata={'error': error_message}
            )
    
    def _send_notification(self, notification: Notification):
        """发送通知到各个渠道"""
        for channel in notification.channels:
            sender = self.senders.get(channel)
            if sender:
                try:
                    sender.send(notification, self.user_id)
                except Exception as e:
                    logger.error(f"发送 {channel.value} 通知失败：{e}")
    
    def _trigger_callbacks(self, level: NotificationLevel, notification: Notification):
        """触发回调函数"""
        for callback in self.callbacks[level]:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"通知回调执行失败：{e}")
    
    def _is_quiet_hours(self) -> bool:
        """检查是否在免打扰时段"""
        now = datetime.now()
        current_hour = now.hour
        
        # 跨天的免打扰时段（如 22:00 - 08:00）
        if self.preferences.quiet_hours_start > self.preferences.quiet_hours_end:
            return (current_hour >= self.preferences.quiet_hours_start or 
                    current_hour < self.preferences.quiet_hours_end)
        else:
            return self.preferences.quiet_hours_start <= current_hour < self.preferences.quiet_hours_end
    
    def get_unread_count(self) -> int:
        """获取未读通知数量"""
        return sum(1 for n in self.notifications if not n.read)
    
    def get_notifications(self, level: Optional[NotificationLevel] = None,
                         unread_only: bool = False, limit: int = 50) -> List[Notification]:
        """获取通知列表"""
        with self.lock:
            filtered = self.notifications
            
            if level:
                filtered = [n for n in filtered if n.level == level]
            
            if unread_only:
                filtered = [n for n in filtered if not n.read]
            
            # 按时间倒序
            filtered.sort(key=lambda n: n.timestamp, reverse=True)
            
            return filtered[:limit]
    
    def mark_as_read(self, notification_id: str):
        """标记通知为已读"""
        with self.lock:
            for notification in self.notifications:
                if notification.id == notification_id:
                    notification.read = True
                    logger.info(f"标记通知为已读：{notification_id}")
                    return True
        return False
    
    def mark_all_as_read(self):
        """标记所有通知为已读"""
        with self.lock:
            for notification in self.notifications:
                notification.read = True
            logger.info("标记所有通知为已读")
    
    def get_daily_digest(self) -> List[Notification]:
        """获取每日汇总"""
        with self.lock:
            return self.daily_digest.copy()
    
    def clear_daily_digest(self):
        """清除每日汇总"""
        with self.lock:
            self.daily_digest.clear()
            logger.info("清除每日汇总")
    
    def export_notifications(self, format: str = 'json') -> str:
        """导出通知"""
        with self.lock:
            if format == 'json':
                return json.dumps([n.to_dict() for n in self.notifications], indent=2, ensure_ascii=False)
            else:
                # 文本格式
                lines = []
                for n in self.notifications:
                    lines.append(f"[{n.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                               f"[{n.level.value}] {n.title}: {n.message}")
                return '\n'.join(lines)


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    manager = NotificationManager(user_id='user_001')
    
    # 设置偏好
    manager.preferences.p0_wechat = True
    
    print("\n=== 测试 1: P0 紧急通知 ===")
    manager.notify_task_failed(
        task_id='task_001',
        task_name='网页搜索',
        error_message='Connection timeout',
        requires_decision=True,
        suggestion='检查网络连接后重试'
    )
    
    print("\n=== 测试 2: P1 重要通知 ===")
    manager.notify_task_complete(
        task_id='task_002',
        task_name='产品方案讨论',
        user_waiting=True
    )
    
    print("\n=== 测试 3: P2 普通通知 ===")
    manager.notify_task_complete(
        task_id='task_003',
        task_name='市场分析',
        is_urgent=False,
        user_waiting=False
    )
    
    print("\n=== 测试 4: 查看通知列表 ===")
    notifications = manager.get_notifications(limit=10)
    print(f"总通知数：{len(notifications)}")
    for n in notifications:
        print(f"  - [{n.level.value}] {n.title} ({n.task_name})")
    
    print("\n=== 测试 5: 导出通知 ===")
    print(manager.export_notifications(format='text'))
