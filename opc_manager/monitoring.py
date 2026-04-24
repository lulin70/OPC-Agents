"""OPC-Agents 错误监控和日志系统

Beta阶段核心功能：
1. 结构化日志（loguru）
2. Sentry错误追踪（可选）
3. 事件追踪（任务完成/失败/取消）
"""

import os
import logging

_logger = logging.getLogger(__name__)


def init_monitoring():
    """初始化监控系统

    优先级：
    1. Sentry DSN配置 → 启用远程错误追踪
    2. 本地日志 → 始终启用
    """
    try:
        from loguru import logger

        log_dir = os.environ.get("LOG_DIR", "logs")
        os.makedirs(log_dir, exist_ok=True)

        logger.add(
            os.path.join(log_dir, "opc_beta_{time:YYYY-MM-DD}.log"),
            rotation="1 day",
            retention="30 days",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        )
        logger.info("日志系统已启用")
    except ImportError:
        _logger.info("loguru未安装，使用标准日志")

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            from opc_manager.version import get_version

            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.1,
                environment="beta",
                release=get_version(),
            )
            _logger.info("Sentry监控已启用")
        except ImportError:
            _logger.warning("sentry-sdk未安装，错误追踪未启用。pip install sentry-sdk")
    else:
        _logger.info("SENTRY_DSN未配置，错误追踪未启用")


def track_event(event_name: str, properties: dict = None):
    """追踪用户事件

    Args:
        event_name: 事件名称（如 task_completed, task_failed）
        properties: 事件属性
    """
    props_str = f" | {properties}" if properties else ""
    _logger.info(f"[Event] {event_name}{props_str}")

    try:
        import sentry_sdk

        if os.getenv("SENTRY_DSN"):
            with sentry_sdk.push_scope() as scope:
                if properties:
                    for k, v in properties.items():
                        scope.set_tag(k, str(v))
                sentry_sdk.capture_message(event_name, level="info")
    except ImportError:
        pass


def track_error(error: Exception, context: dict = None):
    """追踪错误

    Args:
        error: 异常对象
        context: 错误上下文
    """
    _logger.error(f"[Error] {type(error).__name__}: {error} | context={context}")

    try:
        import sentry_sdk

        if os.getenv("SENTRY_DSN"):
            with sentry_sdk.push_scope() as scope:
                if context:
                    for k, v in context.items():
                        scope.set_context(k, v)
                sentry_sdk.capture_exception(error)
    except ImportError:
        pass
