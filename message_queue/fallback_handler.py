#!/usr/bin/env python3
"""
降级处理器

提供多级降级策略和重试机制，确保系统在AI服务不可用时仍能正常工作。
"""

import time
import logging
from typing import Optional, Dict, Any, Callable
from enum import Enum
import random


class FallbackLevel(Enum):
    """降级级别枚举"""
    PRIMARY = "primary"  # 主要服务（ZeroClaw Gateway）
    SECONDARY = "secondary"  # 次要服务（GLM API直接调用）
    TERTIARY = "tertiary"  # 第三级（预设响应模板）
    FALLBACK = "fallback"  # 最终降级（友好错误提示）


class RetryStrategy:
    """重试策略"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
        """初始化重试策略
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟时间（秒）
            max_delay: 最大延迟时间（秒）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """计算指数退避延迟
        
        Args:
            attempt: 当前尝试次数
            
        Returns:
            延迟时间（秒）
        """
        # 指数退避 + 随机抖动
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, 0.1 * delay)  # 添加10%的随机抖动
        return delay + jitter
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """判断是否应该重试
        
        Args:
            attempt: 当前尝试次数
            error: 错误异常
            
        Returns:
            是否应该重试
        """
        if attempt >= self.max_retries:
            return False
        
        # 某些错误不应该重试
        non_retryable_errors = [
            "Invalid pairing code",
            "Unauthorized",
            "Bad request"
        ]
        
        error_str = str(error).lower()
        for non_retryable in non_retryable_errors:
            if non_retryable.lower() in error_str:
                return False
        
        return True


class FallbackHandler:
    """降级处理器"""
    
    def __init__(self, primary_client=None, secondary_client=None):
        """初始化降级处理器
        
        Args:
            primary_client: 主要AI客户端（ZeroClaw Gateway）
            secondary_client: 次要AI客户端（GLM API直接调用）
        """
        self.primary_client = primary_client
        self.secondary_client = secondary_client
        self.retry_strategy = RetryStrategy()
        self.logger = logging.getLogger(__name__)
        
        # 预设响应模板
        self.response_templates = {
            "planning": "我理解您需要制定一个计划。让我为您提供一个基本的规划框架：\n\n1. 明确目标和范围\n2. 分析现状和资源\n3. 制定具体步骤\n4. 设置时间节点\n5. 分配责任和资源\n\n请告诉我更多细节，我可以提供更具体的建议。",
            "analysis": "我理解您需要进行数据分析。让我为您提供一个分析框架：\n\n1. 收集相关数据\n2. 数据清洗和整理\n3. 统计分析\n4. 可视化呈现\n5. 结论和建议\n\n请提供具体的数据或问题，我可以进行更深入的分析。",
            "design": "我理解您需要设计方案。让我为您提供一个设计框架：\n\n1. 需求分析\n2. 方案构思\n3. 可行性评估\n4. 详细设计\n5. 实施计划\n\n请告诉我更多具体需求，我可以提供更针对性的设计方案。",
            "general": "收到您的消息。虽然目前AI服务暂时不可用，但我会尽力为您提供帮助。请告诉我您的具体需求，我会尝试给出建议或解决方案。"
        }
        
        # 错误计数器
        self.error_counts = {
            FallbackLevel.PRIMARY: 0,
            FallbackLevel.SECONDARY: 0,
            FallbackLevel.TERTIARY: 0,
            FallbackLevel.FALLBACK: 0
        }
    
    def process_with_fallback(self, prompt: str, intent: str = "general") -> Dict[str, Any]:
        """使用降级策略处理请求
        
        Args:
            prompt: 提示词
            intent: 意图类型
            
        Returns:
            处理结果字典，包含response、level、attempts等信息
        """
        result = {
            "response": None,
            "level": None,
            "attempts": 0,
            "success": False,
            "error": None
        }
        
        # 尝试主要服务
        response = self._try_primary(prompt)
        if response:
            result.update({
                "response": response,
                "level": FallbackLevel.PRIMARY.value,
                "success": True
            })
            return result
        
        result["attempts"] += 1
        
        # 尝试次要服务
        response = self._try_secondary(prompt)
        if response:
            result.update({
                "response": response,
                "level": FallbackLevel.SECONDARY.value,
                "success": True
            })
            return result
        
        result["attempts"] += 1
        
        # 尝试预设响应模板
        response = self._try_template(intent)
        if response:
            result.update({
                "response": response,
                "level": FallbackLevel.TERTIARY.value,
                "success": True
            })
            return result
        
        result["attempts"] += 1
        
        # 最终降级：友好错误提示
        response = self._get_fallback_response()
        result.update({
            "response": response,
            "level": FallbackLevel.FALLBACK.value,
            "success": False,
            "error": "所有AI服务均不可用"
        })
        
        return result
    
    def _try_primary(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """尝试主要服务（ZeroClaw Gateway）
        
        Args:
            prompt: 提示词
            retry_count: 重试次数
            
        Returns:
            响应文本，如果失败则返回None
        """
        if not self.primary_client:
            return None
        
        try:
            self.logger.info(f"尝试主要服务（ZeroClaw Gateway），重试次数: {retry_count}")
            response = self.primary_client.call_llm(prompt)
            
            if response:
                self.logger.info("主要服务调用成功")
                return response
            else:
                raise Exception("主要服务返回空响应")
                
        except Exception as e:
            self.logger.error(f"主要服务调用失败: {e}")
            self.error_counts[FallbackLevel.PRIMARY] += 1
            
            # 检查是否应该重试
            if self.retry_strategy.should_retry(retry_count, e):
                delay = self.retry_strategy.calculate_delay(retry_count)
                self.logger.info(f"等待 {delay:.2f} 秒后重试...")
                time.sleep(delay)
                return self._try_primary(prompt, retry_count + 1)
            
            return None
    
    def _try_secondary(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """尝试次要服务（GLM API直接调用）
        
        Args:
            prompt: 提示词
            retry_count: 重试次数
            
        Returns:
            响应文本，如果失败则返回None
        """
        if not self.secondary_client:
            return None
        
        try:
            self.logger.info(f"尝试次要服务（GLM API直接调用），重试次数: {retry_count}")
            # 这里可以调用GLM API的SDK
            # response = self.secondary_client.call(prompt)
            
            # 暂时返回None，等待实现
            self.logger.warning("次要服务尚未实现")
            return None
                
        except Exception as e:
            self.logger.error(f"次要服务调用失败: {e}")
            self.error_counts[FallbackLevel.SECONDARY] += 1
            
            # 检查是否应该重试
            if self.retry_strategy.should_retry(retry_count, e):
                delay = self.retry_strategy.calculate_delay(retry_count)
                self.logger.info(f"等待 {delay:.2f} 秒后重试...")
                time.sleep(delay)
                return self._try_secondary(prompt, retry_count + 1)
            
            return None
    
    def _try_template(self, intent: str) -> Optional[str]:
        """尝试预设响应模板
        
        Args:
            intent: 意图类型
            
        Returns:
            响应文本
        """
        self.logger.info(f"使用预设响应模板，意图: {intent}")
        self.error_counts[FallbackLevel.TERTIARY] += 1
        
        return self.response_templates.get(intent, self.response_templates["general"])
    
    def _get_fallback_response(self) -> str:
        """获取最终降级响应
        
        Returns:
            友好的错误提示
        """
        self.logger.warning("所有服务均不可用，返回友好错误提示")
        self.error_counts[FallbackLevel.FALLBACK] += 1
        
        return (
            "抱歉，目前AI服务暂时不可用。这可能是由于以下原因：\n\n"
            "1. ZeroClaw Gateway未启动或未配对\n"
            "2. 网络连接问题\n"
            "3. AI服务正在维护中\n\n"
            "请稍后重试，或联系系统管理员获取帮助。"
        )
    
    def get_error_statistics(self) -> Dict[str, int]:
        """获取错误统计信息
        
        Returns:
            错误统计字典
        """
        return {level.value: count for level, count in self.error_counts.items()}
    
    def reset_error_counts(self):
        """重置错误计数器"""
        for level in self.error_counts:
            self.error_counts[level] = 0
        self.logger.info("错误计数器已重置")
