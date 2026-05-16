"""
Error Handler — v0.2.0 User-friendly error translation system.

Translates technical exceptions into user-understandable Chinese messages.
Provides centralized error mapping and context-aware message formatting.
"""

import logging
import traceback
from typing import Optional, Dict, Any, Type, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    NETWORK = "network"
    PERMISSION = "permission"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    LLM = "llm"
    DATABASE = "database"
    FILE_IO = "file_io"
    EMAIL = "email"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


ERROR_MAP: Dict[Tuple[Type, ...], Dict[str, Any]] = {
    # Permission errors (must come before network errors since PermissionError is OSError subclass)
    (PermissionError,): {
        "category": ErrorCategory.PERMISSION,
        "user_message": "权限不足，无法完成此操作",
        "suggestion": "请检查文件或目录的访问权限",
        "severity": ErrorSeverity.ERROR,
    },
    # Network errors
    (ConnectionError, TimeoutError, OSError): {
        "category": ErrorCategory.NETWORK,
        "user_message": "网络连接失败，请检查网络后重试",
        "suggestion": "检查网络连接是否正常，或稍后再试",
        "severity": ErrorSeverity.WARNING,
    },
    # Configuration errors
    (KeyError, ValueError): {
        "category": ErrorCategory.CONFIGURATION,
        "user_message": "配置信息不完整或有误",
        "suggestion": "请在设置页面检查相关配置项",
        "severity": ErrorSeverity.WARNING,
    },
    # Validation errors
    (AttributeError, TypeError): {
        "category": ErrorCategory.VALIDATION,
        "user_message": "输入数据格式有误",
        "suggestion": "请检查输入内容是否符合要求",
        "severity": ErrorSeverity.WARNING,
    },
    # LLM errors
    ("LLMError",): {
        "category": ErrorCategory.LLM,
        "user_message": "AI服务暂时不可用",
        "suggestion": "AI服务可能正在维护中，请稍后重试",
        "severity": ErrorSeverity.ERROR,
    },
    # Database errors
    ("DatabaseError",): {
        "category": ErrorCategory.DATABASE,
        "user_message": "数据存储出错",
        "suggestion": "数据可能未保存成功，建议重试操作",
        "severity": ErrorSeverity.CRITICAL,
    },
}


class UserFriendlyError(Exception):
    """Wraps an exception with user-friendly metadata."""

    def __init__(self, original_exception: Exception,
                 user_message: str = "",
                 suggestion: str = "",
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.ERROR):
        super().__init__(user_message)
        self.original = original_exception
        self.user_message = user_message or "操作未能完成，请重试"
        self.suggestion = suggestion
        self.category = category
        self.severity = severity
        self.traceback_str = traceback.format_exc()

    def __str__(self):
        return self.user_message


class ErrorHandler:
    """Central error handler for translating tech errors to user messages."""

    @staticmethod
    def translate(exception: Exception, context: str = "") -> UserFriendlyError:
        """Translate any exception into a user-friendly error.

        Args:
            exception: The caught exception
            context: Optional context string (e.g., "发送邮件时", "保存设置时")

        Returns:
            UserFriendlyError with translated message
        """
        exc_type = type(exception)

        for exc_types, mapping in ERROR_MAP.items():
            if exc_type in exc_types:
                msg = mapping["user_message"]
                if context:
                    msg = f"{context}：{msg}"
                return UserFriendlyError(
                    original_exception=exception,
                    user_message=msg,
                    suggestion=mapping.get("suggestion", ""),
                    category=mapping["category"],
                    severity=mapping["severity"],
                )
            if isinstance(exc_types, tuple) and any(
                issubclass(exc_type, t) if isinstance(t, type) else False
                for t in exc_types
            ):
                msg = mapping["user_message"]
                if context:
                    msg = f"{context}：{msg}"
                return UserFriendlyError(
                    original_exception=exception,
                    user_message=msg,
                    suggestion=mapping.get("suggestion", ""),
                    category=mapping["category"],
                    severity=mapping["severity"],
                )

        logger.warning("Unhandled exception type: %s - %s", exc_type.__name__, str(exception))
        fallback_msg = f"操作出现意外错误({exc_type.__name__})"
        if context:
            fallback_msg = f"{context}：{fallback_msg}"
        return UserFriendlyError(
            original_exception=exception,
            user_message=fallback_msg,
            category=ErrorCategory.UNKNOWN,
        )

    @staticmethod
    def safe_execute(func, *args, on_error=None, context="", **kwargs):
        """Execute a function with automatic error translation.

        Args:
            func: Function to execute
            on_error: Callback receiving UserFriendlyError on failure
            context: Context description for error messages

        Returns:
            Function result or None if failed
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            friendly = ErrorHandler.translate(e, context)
            logger.error("[%s] %s: %s", context, friendly.user_message, str(e))
            if on_error:
                on_error(friendly)
            raise friendly from e

    @staticmethod
    def get_severity_color(severity: ErrorSeverity) -> str:
        """Return Streamlit-compatible color name."""
        return {
            ErrorSeverity.INFO: "blue",
            ErrorSeverity.WARNING: "orange",
            ErrorSeverity.ERROR: "red",
            ErrorSeverity.CRITICAL: "red",
        }.get(severity, "gray")

    @staticmethod
    def get_emoji(severity: ErrorSeverity) -> str:
        return {
            ErrorSeverity.INFO: "ℹ️",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.CRITICAL: "🔴",
        }.get(severity, "❓")


def get_error_handler() -> ErrorHandler:
    return ErrorHandler()
