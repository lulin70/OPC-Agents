"""
错误分类与处理策略模块

实现 4 类错误处理：
1. 可重试 - 自动：网络超时、API 限流 → 自动重试（≤3 次）
2. 可重试 - 建议：资源不足、依赖缺失 → 提供方案，用户确认
3. 不可重试：代码 bug、权限不足 → 停止执行，报告用户
4. 高风险：付费 API 失败、数据丢失 → 立即停止，等待指示
"""

from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """错误分类"""
    RETRYABLE_AUTO = "retryable_auto"      # 可重试 - 自动
    RETRYABLE_ADVISED = "retryable_advised"  # 可重试 - 建议
    NON_RETRYABLE = "non_retryable"         # 不可重试
    HIGH_RISK = "high_risk"                 # 高风险


class ErrorType(Enum):
    """错误类型"""
    # 网络相关
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_ERROR = "network_error"
    API_RATE_LIMIT = "api_rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # 资源相关
    RESOURCE_INSUFFICIENT = "resource_insufficient"
    MEMORY_LOW = "memory_low"
    DISK_FULL = "disk_full"
    
    # 依赖相关
    DEPENDENCY_MISSING = "dependency_missing"
    FILE_NOT_FOUND = "file_not_found"
    
    # 代码/权限相关
    CODE_BUG = "code_bug"
    PERMISSION_DENIED = "permission_denied"
    INVALID_INPUT = "invalid_input"
    SYNTAX_ERROR = "syntax_error"
    
    # 高风险
    PAYMENT_FAILED = "payment_failed"
    DATA_LOSS = "data_loss"
    SECURITY_VIOLATION = "security_violation"
    
    # 未知
    UNKNOWN = "unknown"


@dataclass
class ErrorInfo:
    """错误信息"""
    error_type: ErrorType
    category: ErrorCategory
    message: str
    task_id: str
    agent: str
    timestamp: datetime
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class RetryStrategy:
    """重试策略"""
    should_retry: bool
    retry_type: str  # 'auto' | 'advised' | 'none'
    delay_seconds: int
    max_retries: int
    backoff_multiplier: float = 2.0
    suggestion: Optional[str] = None


class ErrorClassifier:
    """错误分类器"""
    
    # 错误模式匹配规则
    ERROR_PATTERNS = {
        # 网络相关
        ErrorType.NETWORK_TIMEOUT: [
            r'timeout', r'timed out', r'connection timeout', r'read timeout'
        ],
        ErrorType.NETWORK_ERROR: [
            r'connection error', r'network error', r'connection refused',
            r'connection reset', r'broken pipe'
        ],
        ErrorType.API_RATE_LIMIT: [
            r'rate limit', r'too many requests', r'429', r'quota exceeded'
        ],
        ErrorType.SERVICE_UNAVAILABLE: [
            r'service unavailable', r'503', r'502', r'bad gateway'
        ],
        
        # 资源相关
        ErrorType.RESOURCE_INSUFFICIENT: [
            r'insufficient resources', r'not enough memory', r'no space left'
        ],
        ErrorType.MEMORY_LOW: [
            r'memory error', r'out of memory', r'MemoryError'
        ],
        ErrorType.DISK_FULL: [
            r'disk full', r'no space', r'ENOSPC'
        ],
        
        # 依赖相关
        ErrorType.DEPENDENCY_MISSING: [
            r'module not found', r'import error', r'dependency missing',
            r'No module named'
        ],
        ErrorType.FILE_NOT_FOUND: [
            r'file not found', r'No such file', r'FileNotFoundError'
        ],
        
        # 代码/权限相关
        ErrorType.CODE_BUG: [
            r'assertion error', r'attribute error', r'type error',
            r'name error', r'index error', r'key error', r'null pointer'
        ],
        ErrorType.PERMISSION_DENIED: [
            r'permission denied', r'access denied', r'unauthorized',
            r'forbidden', r'401', r'403'
        ],
        ErrorType.INVALID_INPUT: [
            r'invalid input', r'invalid argument', r'validation error',
            r'bad request', r'400'
        ],
        ErrorType.SYNTAX_ERROR: [
            r'syntax error', r'parse error', r'invalid syntax'
        ],
        
        # 高风险
        ErrorType.PAYMENT_FAILED: [
            r'payment failed', r'payment required', r'billing error',
            r'credit card', r'402'
        ],
        ErrorType.DATA_LOSS: [
            r'data loss', r'data corrupted', r'data missing',
            r'checksum error'
        ],
        ErrorType.SECURITY_VIOLATION: [
            r'security violation', r'security error', r'malware detected',
            r'virus detected'
        ]
    }
    
    # 错误分类映射
    CATEGORY_MAPPING = {
        # 可重试 - 自动
        ErrorCategory.RETRYABLE_AUTO: [
            ErrorType.NETWORK_TIMEOUT,
            ErrorType.NETWORK_ERROR,
            ErrorType.API_RATE_LIMIT,
            ErrorType.SERVICE_UNAVAILABLE
        ],
        
        # 可重试 - 建议
        ErrorCategory.RETRYABLE_ADVISED: [
            ErrorType.RESOURCE_INSUFFICIENT,
            ErrorType.MEMORY_LOW,
            ErrorType.DISK_FULL,
            ErrorType.DEPENDENCY_MISSING,
            ErrorType.FILE_NOT_FOUND
        ],
        
        # 不可重试
        ErrorCategory.NON_RETRYABLE: [
            ErrorType.CODE_BUG,
            ErrorType.PERMISSION_DENIED,
            ErrorType.INVALID_INPUT,
            ErrorType.SYNTAX_ERROR
        ],
        
        # 高风险
        ErrorCategory.HIGH_RISK: [
            ErrorType.PAYMENT_FAILED,
            ErrorType.DATA_LOSS,
            ErrorType.SECURITY_VIOLATION
        ]
    }
    
    def classify(self, error_message: str, exception: Optional[Exception] = None) -> ErrorInfo:
        """
        分类错误
        
        Args:
            error_message: 错误消息
            exception: 异常对象（可选）
        
        Returns:
            ErrorInfo: 错误信息
        """
        # 检测错误类型
        error_type = self._detect_error_type(error_message)
        
        # 获取错误分类
        category = self._get_category(error_type)
        
        # 创建错误信息
        error_info = ErrorInfo(
            error_type=error_type,
            category=category,
            message=error_message,
            task_id='',
            agent='',
            timestamp=datetime.now()
        )
        
        logger.info(f"错误分类：{error_type.value} -> {category.value}")
        return error_info
    
    def _detect_error_type(self, error_message: str) -> ErrorType:
        """检测错误类型"""
        error_message_lower = error_message.lower()
        
        # 遍历所有错误模式
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_message_lower, re.IGNORECASE):
                    return error_type
        
        # 未知错误
        return ErrorType.UNKNOWN
    
    def _get_category(self, error_type: ErrorType) -> ErrorCategory:
        """获取错误分类"""
        for category, error_types in self.CATEGORY_MAPPING.items():
            if error_type in error_types:
                return category
        
        # 默认不可重试
        return ErrorCategory.NON_RETRYABLE


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.classifier = ErrorClassifier()
        self.error_handlers: Dict[ErrorCategory, Callable] = {
            ErrorCategory.RETRYABLE_AUTO: self._handle_auto_retry,
            ErrorCategory.RETRYABLE_ADVISED: self._handle_advised_retry,
            ErrorCategory.NON_RETRYABLE: self._handle_non_retryable,
            ErrorCategory.HIGH_RISK: self._handle_high_risk
        }
    
    def handle_error(self, error_info: ErrorInfo) -> RetryStrategy:
        """
        处理错误
        
        Args:
            error_info: 错误信息
        
        Returns:
            RetryStrategy: 重试策略
        """
        # 获取对应的处理器
        handler = self.error_handlers.get(error_info.category)
        
        if handler:
            return handler(error_info)
        else:
            # 默认不重试
            return RetryStrategy(
                should_retry=False,
                retry_type='none',
                delay_seconds=0,
                max_retries=0
            )
    
    def _handle_auto_retry(self, error_info: ErrorInfo) -> RetryStrategy:
        """处理可重试 - 自动"""
        # 检查是否超过最大重试次数
        if error_info.retry_count >= error_info.max_retries:
            logger.warning(f"任务 {error_info.task_id} 达到最大重试次数")
            return RetryStrategy(
                should_retry=False,
                retry_type='none',
                delay_seconds=0,
                max_retries=error_info.max_retries,
                suggestion=f"已自动重试{error_info.max_retries}次，仍失败"
            )
        
        # 计算延迟时间（指数退避）
        delay = 2 * (2.0 ** error_info.retry_count)  # 2, 4, 8, ...
        
        logger.info(f"任务 {error_info.task_id} 自动重试 #{error_info.retry_count + 1}，延迟 {delay}秒")
        
        return RetryStrategy(
            should_retry=True,
            retry_type='auto',
            delay_seconds=int(delay),
            max_retries=error_info.max_retries,
            suggestion=f"自动重试中（第{error_info.retry_count + 1}/{error_info.max_retries}次）"
        )
    
    def _handle_advised_retry(self, error_info: ErrorInfo) -> RetryStrategy:
        """处理可重试 - 建议"""
        # 生成建议
        suggestion = self._generate_suggestion(error_info)
        
        logger.info(f"任务 {error_info.task_id} 需要用户确认重试：{suggestion}")
        
        return RetryStrategy(
            should_retry=False,  # 需要用户确认
            retry_type='advised',
            delay_seconds=0,
            max_retries=error_info.max_retries,
            suggestion=suggestion
        )
    
    def _handle_non_retryable(self, error_info: ErrorInfo) -> RetryStrategy:
        """处理不可重试"""
        logger.error(f"任务 {error_info.task_id} 不可重试：{error_info.message}")
        
        return RetryStrategy(
            should_retry=False,
            retry_type='none',
            delay_seconds=0,
            max_retries=0,
            suggestion=f"错误无法自动修复：{error_info.message}。需要人工干预。"
        )
    
    def _handle_high_risk(self, error_info: ErrorInfo) -> RetryStrategy:
        """处理高风险"""
        logger.critical(f"任务 {error_info.task_id} 高风险错误：{error_info.message}")
        
        return RetryStrategy(
            should_retry=False,
            retry_type='none',
            delay_seconds=0,
            max_retries=0,
            suggestion=f"⚠️ 高风险错误：{error_info.message}。已停止执行，等待您的指示。"
        )
    
    def _generate_suggestion(self, error_info: ErrorInfo) -> str:
        """生成建议"""
        suggestions = {
            ErrorType.RESOURCE_INSUFFICIENT: "系统资源不足，建议：1) 暂停低优先级任务 2) 关闭其他应用 3) 增加系统资源",
            ErrorType.MEMORY_LOW: "内存不足，建议：1) 暂停其他任务 2) 清理内存 3) 增加内存",
            ErrorType.DISK_FULL: "磁盘空间不足，建议：1) 清理磁盘空间 2) 删除旧文件 3) 扩展存储",
            ErrorType.DEPENDENCY_MISSING: f"缺少依赖，建议运行：pip install <missing_package>",
            ErrorType.FILE_NOT_FOUND: "文件未找到，请检查文件路径是否正确",
        }
        
        return suggestions.get(error_info.error_type, "建议检查系统状态后重试")


class TaskErrorTracker:
    """任务错误跟踪器"""
    
    def __init__(self):
        self.error_history: Dict[str, List[ErrorInfo]] = {}  # {task_id: [errors]}
        self.handler = ErrorHandler()
    
    def track_error(self, task_id: str, error_message: str, 
                   agent: str, exception: Optional[Exception] = None) -> RetryStrategy:
        """
        跟踪任务错误
        
        Args:
            task_id: 任务 ID
            error_message: 错误消息
            agent: 执行 Agent
            exception: 异常对象
        
        Returns:
            RetryStrategy: 重试策略
        """
        # 分类错误
        error_info = self.handler.classifier.classify(error_message, exception)
        error_info.task_id = task_id
        error_info.agent = agent
        
        # 更新重试次数
        if task_id in self.error_history:
            error_info.retry_count = len(self.error_history[task_id])
        
        # 处理错误
        strategy = self.handler.handle_error(error_info)
        
        # 记录错误
        if task_id not in self.error_history:
            self.error_history[task_id] = []
        self.error_history[task_id].append(error_info)
        
        return strategy
    
    def get_error_history(self, task_id: str) -> List[ErrorInfo]:
        """获取任务错误历史"""
        return self.error_history.get(task_id, [])
    
    def clear_history(self, task_id: str):
        """清除任务错误历史"""
        if task_id in self.error_history:
            del self.error_history[task_id]


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    tracker = TaskErrorTracker()
    
    # 测试 1: 网络超时（自动重试）
    print("\n=== 测试 1: 网络超时 ===")
    strategy = tracker.track_error(
        task_id='task_001',
        error_message='Connection timeout after 30 seconds',
        agent='web_search'
    )
    print(f"重试：{strategy.should_retry}, 类型：{strategy.retry_type}, 延迟：{strategy.delay_seconds}s")
    print(f"建议：{strategy.suggestion}")
    
    # 测试 2: 内存不足（建议重试）
    print("\n=== 测试 2: 内存不足 ===")
    strategy = tracker.track_error(
        task_id='task_002',
        error_message='MemoryError: Unable to allocate memory',
        agent='data_processor'
    )
    print(f"重试：{strategy.should_retry}, 类型：{strategy.retry_type}")
    print(f"建议：{strategy.suggestion}")
    
    # 测试 3: 代码 bug（不可重试）
    print("\n=== 测试 3: 代码 bug ===")
    strategy = tracker.track_error(
        task_id='task_003',
        error_message='AttributeError: module has no attribute',
        agent='code_executor'
    )
    print(f"重试：{strategy.should_retry}, 类型：{strategy.retry_type}")
    print(f"建议：{strategy.suggestion}")
    
    # 测试 4: 支付失败（高风险）
    print("\n=== 测试 4: 支付失败 ===")
    strategy = tracker.track_error(
        task_id='task_004',
        error_message='Payment failed: Credit card declined',
        agent='payment_processor'
    )
    print(f"重试：{strategy.should_retry}, 类型：{strategy.retry_type}")
    print(f"建议：{strategy.suggestion}")
