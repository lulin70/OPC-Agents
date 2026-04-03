"""
场景化模式模块

实现两种模式：
- 简单模式（默认）：自动化程度高，适合新手
- 高级模式：完全控制，适合专家
"""

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """系统模式"""
    SIMPLE = "simple"      # 简单模式
    ADVANCED = "advanced"  # 高级模式


@dataclass
class ModeConfig:
    """模式配置"""
    # 优先级管理
    auto_priority: bool  # 自动优先级
    manual_priority_override: bool  # 允许手动覆盖
    
    # 错误处理
    auto_retry: bool  # 自动重试
    max_auto_retries: int  # 最大自动重试次数
    
    # 通知
    notification_level: str  # all/minimal/none
    instant_notifications: bool  # 实时通知
    daily_digest: bool  # 每日汇总
    
    # 调度透明化
    show_thinking_process: bool  # 显示思考过程
    thinking_detail_level: str  # full/simple
    
    # 资源管理
    auto_optimize_resources: bool  # 自动优化资源
    resource_monitoring: bool  # 资源监控
    
    # 任务历史
    auto_archive: bool  # 自动归档
    history_search: bool  # 历史搜索
    
    def to_dict(self) -> Dict:
        return {
            'auto_priority': self.auto_priority,
            'manual_priority_override': self.manual_priority_override,
            'auto_retry': self.auto_retry,
            'max_auto_retries': self.max_auto_retries,
            'notification_level': self.notification_level,
            'instant_notifications': self.instant_notifications,
            'daily_digest': self.daily_digest,
            'show_thinking_process': self.show_thinking_process,
            'thinking_detail_level': self.thinking_detail_level,
            'auto_optimize_resources': self.auto_optimize_resources,
            'resource_monitoring': self.resource_monitoring,
            'auto_archive': self.auto_archive,
            'history_search': self.history_search
        }


class ModeManager:
    """模式管理器"""
    
    # 预定义模式配置
    MODE_CONFIGS: Dict[SystemMode, ModeConfig] = {
        SystemMode.SIMPLE: ModeConfig(
            # 简单模式：自动化程度高
            auto_priority=True,           # 自动管理优先级
            manual_priority_override=True, # 但允许手动覆盖
            auto_retry=True,              # 自动重试失败任务
            max_auto_retries=3,
            notification_level='minimal',  # 仅显示重要通知
            instant_notifications=True,    # P0/P1 实时通知
            daily_digest=True,            # 每日汇总
            show_thinking_process=True,    # 显示思考过程
            thinking_detail_level='simple', # 简化版
            auto_optimize_resources=True,  # 自动优化资源
            resource_monitoring=True,
            auto_archive=True,            # 自动归档
            history_search=True           # 历史搜索
        ),
        
        SystemMode.ADVANCED: ModeConfig(
            # 高级模式：完全控制
            auto_priority=False,          # 手动优先级
            manual_priority_override=True,
            auto_retry=False,             # 建议重试（用户确认）
            max_auto_retries=0,
            notification_level='all',      # 所有通知
            instant_notifications=True,    # 所有通知实时
            daily_digest=False,           # 不需要汇总
            show_thinking_process=True,    # 显示思考过程
            thinking_detail_level='full',  # 完整版
            auto_optimize_resources=False, # 手动优化
            resource_monitoring=True,
            auto_archive=False,           # 手动归档
            history_search=True           # 历史搜索
        )
    }
    
    def __init__(self, default_mode: SystemMode = SystemMode.SIMPLE):
        """
        初始化
        
        Args:
            default_mode: 默认模式
        """
        self.current_mode = default_mode
        self.custom_config: Optional[ModeConfig] = None
        
        logger.info(f"模式管理器初始化完成（默认：{default_mode.value}）")
    
    def set_mode(self, mode: SystemMode):
        """设置系统模式"""
        self.current_mode = mode
        self.custom_config = None  # 清除自定义配置
        logger.info(f"切换到 {mode.value} 模式")
    
    def get_mode(self) -> SystemMode:
        """获取当前模式"""
        return self.current_mode
    
    def get_config(self) -> ModeConfig:
        """获取当前模式配置"""
        if self.custom_config:
            return self.custom_config
        return self.MODE_CONFIGS[self.current_mode]
    
    def customize_setting(self, setting_name: str, value):
        """
        自定义设置
        
        Args:
            setting_name: 设置名称
            value: 设置值
        """
        config = self.get_config()
        
        if hasattr(config, setting_name):
            # 如果有自定义配置，修改它
            if self.custom_config:
                setattr(self.custom_config, setting_name, value)
            else:
                # 否则创建基于当前模式的自定义配置
                import copy
                self.custom_config = copy.deepcopy(config)
                setattr(self.custom_config, setting_name, value)
            
            logger.info(f"自定义设置：{setting_name} = {value}")
        else:
            logger.warning(f"未知设置：{setting_name}")
    
    def get_feature_description(self, feature: str) -> Dict:
        """
        获取功能说明
        
        Args:
            feature: 功能名称
        
        Returns:
            Dict: 功能说明
        """
        simple_config = self.MODE_CONFIGS[SystemMode.SIMPLE]
        advanced_config = self.MODE_CONFIGS[SystemMode.ADVANCED]
        
        simple_value = getattr(simple_config, feature, None)
        advanced_value = getattr(advanced_config, feature, None)
        
        return {
            'feature': feature,
            'simple_mode': simple_value,
            'advanced_mode': advanced_value
        }
    
    def list_all_features(self) -> Dict:
        """列出所有功能配置"""
        features = {}
        
        simple_config = self.MODE_CONFIGS[SystemMode.SIMPLE]
        advanced_config = self.MODE_CONFIGS[SystemMode.ADVANCED]
        
        # 获取所有配置项
        for key in simple_config.__dict__.keys():
            features[key] = {
                'simple': getattr(simple_config, key),
                'advanced': getattr(advanced_config, key)
            }
        
        return features
    
    def explain_mode_difference(self) -> str:
        """解释两种模式的区别"""
        lines = [
            "📊 简单模式 vs 高级模式",
            "=" * 60,
            "",
            "🟢 简单模式（推荐新手）:",
            "  ✓ 自动管理任务优先级",
            "  ✓ 自动重试失败任务（最多 3 次）",
            "  ✓ 仅显示重要通知（P0/P1）",
            "  ✓ 简化思考过程展示",
            "  ✓ 自动优化系统资源",
            "  ✓ 自动归档旧任务",
            "",
            "🔵 高级模式（适合专家）:",
            "  ✎ 手动设置任务优先级",
            "  ⚠️ 建议重试（需要确认）",
            "  📬 显示所有通知（P0-P3）",
            "  📝 完整思考过程展示",
            "  🔧 手动优化系统资源",
            "  📁 手动管理任务归档",
            "",
            "=" * 60,
            "💡 建议：新手从简单模式开始，熟悉后可切换到高级模式"
        ]
        
        return '\n'.join(lines)


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    manager = ModeManager(default_mode=SystemMode.SIMPLE)
    
    print("\n=== 测试 1: 获取当前模式 ===")
    print(f"当前模式：{manager.get_mode().value}")
    
    print("\n=== 测试 2: 获取配置 ===")
    config = manager.get_config()
    print(f"自动优先级：{config.auto_priority}")
    print(f"自动重试：{config.auto_retry}")
    print(f"通知级别：{config.notification_level}")
    
    print("\n=== 测试 3: 切换到高级模式 ===")
    manager.set_mode(SystemMode.ADVANCED)
    config = manager.get_config()
    print(f"自动优先级：{config.auto_priority}")
    print(f"自动重试：{config.auto_retry}")
    print(f"通知级别：{config.notification_level}")
    
    print("\n=== 测试 4: 自定义设置 ===")
    manager.customize_setting('auto_retry', True)
    config = manager.get_config()
    print(f"高级模式但启用自动重试：{config.auto_retry}")
    
    print("\n=== 测试 5: 列出所有功能 ===")
    features = manager.list_all_features()
    for feature, values in features.items():
        print(f"{feature}: 简单={values['simple']}, 高级={values['advanced']}")
    
    print("\n=== 测试 6: 模式说明 ===")
    print(manager.explain_mode_difference())
