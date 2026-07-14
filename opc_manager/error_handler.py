"""
Error Handler — v0.3.28 User-friendly error translation system.

Translates technical exceptions into user-understandable Chinese messages.
Provides centralized error mapping and context-aware message formatting.
"""

import logging
import traceback
from typing import Any, Callable, Dict, Optional, Tuple, Type
from enum import Enum

logger = logging.getLogger(__name__)

# 显式注解为 Type[Exception]，使 import 成功时 (type[具体异常]，为其子类) 与
# import 失败时 (Exception) 均兼容，避免 mypy [assignment]/[misc] 错误。
_OpenAIAPIError: Type[Exception]
APIConnectionError: Type[Exception]
RateLimitError: Type[Exception]
APITimeoutError: Type[Exception]
_SQLiteDBError: Type[Exception]

try:
    from openai import (
        APIError as _OpenAIAPIError,
        APIConnectionError,
        RateLimitError,
        APITimeoutError,
    )
except ImportError:
    _OpenAIAPIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception

try:
    from sqlite3 import DatabaseError as _SQLiteDBError
except ImportError:
    _SQLiteDBError = Exception


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
    (PermissionError,): {
        "category": ErrorCategory.PERMISSION,
        "user_message": "权限不足，无法完成此操作",
        "suggestion": "请检查文件或目录的访问权限",
        "severity": ErrorSeverity.ERROR,
    },
    (ConnectionError, TimeoutError, OSError): {
        "category": ErrorCategory.NETWORK,
        "user_message": "网络连接失败，请检查网络后重试",
        "suggestion": "检查网络连接是否正常，或稍后再试",
        "severity": ErrorSeverity.WARNING,
    },
    (KeyError, ValueError): {
        "category": ErrorCategory.CONFIGURATION,
        "user_message": "配置信息不完整或有误",
        "suggestion": "请在设置页面检查相关配置项",
        "severity": ErrorSeverity.WARNING,
    },
    (AttributeError, TypeError): {
        "category": ErrorCategory.VALIDATION,
        "user_message": "输入数据格式有误",
        "suggestion": "请检查输入内容是否符合要求",
        "severity": ErrorSeverity.WARNING,
    },
    (_OpenAIAPIError, APIConnectionError, RateLimitError, APITimeoutError): {
        "category": ErrorCategory.LLM,
        "user_message": "AI服务暂时不可用",
        "suggestion": "AI服务可能正在维护中，请稍后重试",
        "severity": ErrorSeverity.ERROR,
    },
    (_SQLiteDBError,): {
        "category": ErrorCategory.DATABASE,
        "user_message": "数据存储出错",
        "suggestion": "数据可能未保存成功，建议重试操作",
        "severity": ErrorSeverity.CRITICAL,
    },
}


class UserFriendlyError(Exception):
    def __init__(
        self,
        original_exception: Exception,
        user_message: str = "",
        suggestion: str = "",
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ):
        super().__init__(user_message)
        self.original = original_exception
        self.user_message = user_message or "操作未能完成，请重试"
        self.suggestion = suggestion
        self.category = category
        self.severity = severity
        self.traceback_str = traceback.format_exc()

    def __str__(self) -> str:
        return self.user_message


class ErrorHandler:
    @staticmethod
    def translate(exception: Exception, context: str = "") -> UserFriendlyError:
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

        logger.warning(
            "Unhandled exception type: %s - %s", exc_type.__name__, str(exception)
        )
        fallback_msg = f"操作出现意外错误({exc_type.__name__})"
        if context:
            fallback_msg = f"{context}：{fallback_msg}"
        return UserFriendlyError(
            original_exception=exception,
            user_message=fallback_msg,
            category=ErrorCategory.UNKNOWN,
        )

    @staticmethod
    def safe_execute(
        func: Callable[..., Any],
        *args: Any,
        on_error: Optional[Callable[["UserFriendlyError"], None]] = None,
        context: str = "",
        **kwargs: Any,
    ) -> Any:
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
        return {
            ErrorSeverity.INFO: "blue",
            ErrorSeverity.WARNING: "orange",
            ErrorSeverity.ERROR: "red",
            ErrorSeverity.CRITICAL: "red",
        }.get(severity, "gray")

    @staticmethod
    def get_emoji(severity: ErrorSeverity) -> str:
        return {
            ErrorSeverity.INFO: "",
            ErrorSeverity.WARNING: "",
            ErrorSeverity.ERROR: "",
            ErrorSeverity.CRITICAL: "",
        }.get(severity, "")


def get_error_handler() -> ErrorHandler:
    return ErrorHandler()
