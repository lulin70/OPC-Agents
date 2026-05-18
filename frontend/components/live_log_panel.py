"""SSE流式实时日志查看器面板

提供实时流式显示各类日志的前端面板组件，支持：
- 多源日志聚合（应用日志、引擎日志、审计日志、进度事件、系统日志）
- 实时轮询更新（Streamlit兼容的轮询+缓存模式）
- 级别/来源/关键词过滤
- 颜色编码和图标展示
- 日志导出（TXT/JSON/CSV格式）
- 敏感信息自动脱敏

架构：
┌──────────┐    轮询(1-2s)    ┌──────────────┐    读取    ┌─────────────┐
│  前端UI  │ ◄──────────► │ 日志缓存层   │ ◄──────── │ 各日志源     │
│ Panel    │              │ (内存+文件)  │          │ logging/Audit │
└──────────┘              └──────────────┘          └─────────────┘
"""

import streamlit as st
import time
import json
import os
import re
import random
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from collections import deque
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_WORKSPACE_DIR = os.environ.get("OPC_WORKSPACE", os.getcwd())
CACHE_DIR = os.path.join(_WORKSPACE_DIR, "data", "logs")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_FILE = Path(CACHE_DIR) / "live_logs_cache.json"
MAX_CACHE_ENTRIES = 500
CACHE_TTL_SECONDS = 5
DEFAULT_DISPLAY_LIMIT = 100
MIN_POLL_INTERVAL = 1


@dataclass
class LogEntry:
    """单条日志条目数据结构"""
    timestamp: float
    level: str
    source: str
    message: str
    module: str
    extra: dict = field(default_factory=dict)

    def to_display(self) -> str:
        """格式化为单行显示文本"""
        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        level_icon = LOG_LEVEL_CONFIG.get(self.level, {}).get("icon", "📝")
        source_label = LOG_SOURCE_CONFIG.get(self.source, {}).get("label", self.source)
        return f"{ts} {level_icon} [{source_label}] {self.message}"

    def to_html(self, colorized: bool = True) -> str:
        """格式化为HTML（带颜色编码）"""
        if not colorized:
            return self.to_display()

        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        level_cfg = LOG_LEVEL_CONFIG.get(self.level, {})
        icon = level_cfg.get("icon", "📝")
        color = level_cfg.get("color", "#6B7280")
        bg_color = level_cfg.get("bg_color", "#F3F4F6")

        source_cfg = LOG_SOURCE_CONFIG.get(self.source, {})
        source_icon = source_cfg.get("icon", "📌")
        source_label = source_cfg.get("label", self.source)

        message_escaped = self.message.replace("<", "&lt;").replace(">", "&gt;")
        if self.extra.get("traceback"):
            traceback_escaped = self.extra["traceback"].replace("<", "&lt;").replace(">", "&gt;")
            return (
                f'<div style="background:{bg_color};padding:8px;border-radius:4px;margin:2px 0;">'
                f'<span style="color:#9CA3AF;font-family:monospace">{ts}</span> '
                f'<span style="font-size:16px">{icon}</span> '
                f'<span style="background:#E5E7EB;padding:2px 6px;border-radius:3px;'
                f'font-size:12px;margin:0 4px">{source_icon} {source_label}</span> '
                f'<span style="color:{color}">{message_escaped}</span>'
                f'<details style="margin-top:4px"><summary style="cursor:pointer;color:#EF4444">'
                f'查看错误详情</summary>'
                f'<pre style="background:#FEF2F2;padding:8px;border-radius:4px;overflow:auto;'
                f'max-height:200px">{traceback_escaped}</pre></details></div>'
            )
        return (
            f'<div style="background:{bg_color};padding:8px;border-radius:4px;margin:2px 0;">'
            f'<span style="color:#9CA3AF;font-family:monospace">{ts}</span> '
            f'<span style="font-size:16px">{icon}</span> '
            f'<span style="background:#E5E7EB;padding:2px 6px;border-radius:3px;'
            f'font-size:12px;margin:0 4px">{source_icon} {source_label}</span> '
            f'<span style="color:{color}">{message_escaped}</span></div>'
        )

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return asdict(self)


LOG_LEVEL_CONFIG = {
    "DEBUG": {"icon": "🔧", "color": "#6B7280", "bg_color": "#F3F4F6"},
    "INFO": {"icon": "ℹ️", "color": "#3B82F6", "bg_color": "#EFF6FF"},
    "WARNING": {"icon": "⚠️", "color": "#F59E0B", "bg_color": "#FFFBEB"},
    "ERROR": {"icon": "❌", "color": "#EF4444", "bg_color": "#FEF2F2"},
    "CRITICAL": {"icon": "🚨", "color": "#DC2626", "bg_color": "#FEE2E2"},
}

LOG_SOURCE_CONFIG = {
    "app": {"label": "应用", "icon": "🖥️"},
    "engine": {"label": "引擎", "icon": "⚙️"},
    "audit": {"label": "审计", "icon": "📋"},
    "progress": {"label": "进度", "icon": "📊"},
    "system": {"label": "系统", "icon": "🔧"},
}

LOG_LEVEL_ORDER = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

SENSITIVE_PATTERNS = [
    r'api[_\-]?key\s*[:=]\s*\S+',
    r'password\s*[:=]\s*\S+',
    r'token\s*[:=]\s*\S+',
    r'secret\s*[:=]\s*\S+',
    r'sk-[a-zA-Z0-9]{20,}',
]


def sanitize_log_message(message: str) -> str:
    """脱敏处理：移除敏感信息"""
    for pattern in SENSITIVE_PATTERNS:
        message = re.sub(pattern, "***REDACTED***", message, flags=re.IGNORECASE)
    return message


class LogCache:
    """内存+文件的日志缓存系统"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache: deque = deque(maxlen=MAX_CACHE_ENTRIES)
                    cls._instance._last_update = 0.0
                    cls._instance._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="log_cache")
        return cls._instance

    def update(self, new_entries: List[LogEntry]):
        """添加新条目并裁剪到上限"""
        with self._lock:
            for entry in new_entries:
                self._cache.append(entry)
            self._last_update = time.time()

        if random.random() < 0.1:
            try:
                self._executor.submit(self._persist)
            except Exception:
                pass

    def get_recent(self, limit: int = DEFAULT_DISPLAY_LIMIT) -> List[LogEntry]:
        """获取最近的日志条目"""
        with self._lock:
            cache_list = list(self._cache)
        return cache_list[-limit:]

    def get_since(self, since_timestamp: float) -> List[LogEntry]:
        """获取指定时间戳之后的日志"""
        with self._lock:
            return [e for e in self._cache if e.timestamp >= since_timestamp]

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._last_update = 0.0

    @property
    def last_update(self) -> float:
        return self._last_update

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def _persist(self):
        """异步持久化到JSON文件"""
        try:
            with self._lock:
                data = [e.to_dict() for e in list(self._cache)[-200:]]
            temp_file = CACHE_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_file.replace(CACHE_FILE)
        except Exception as e:
            logger.debug("[LogCache] 持久化失败: %s", e)

    @classmethod
    def load(cls) -> 'LogCache':
        """从文件加载缓存"""
        instance = cls()
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                entries = [LogEntry(**d) for d in data]
                with instance._lock:
                    instance._cache = deque(entries, maxlen=MAX_CACHE_ENTRIES)
                    instance._last_update = time.time()
                logger.info("[LogCache] 从文件加载了 %d 条日志", len(entries))
            except Exception as e:
                logger.warning("[LogCache] 加载缓存文件失败: %s", e)
        return instance

    def shutdown(self):
        """关闭缓存线程池"""
        try:
            self._persist()
            self._executor.shutdown(wait=False)
        except Exception:
            pass


_log_cache_instance = None


def _get_log_cache() -> LogCache:
    """获取全局LogCache单例（延迟初始化）"""
    global _log_cache_instance
    if _log_cache_instance is None:
        _log_cache_instance = LogCache.load()
    return _log_cache_instance


def collect_app_logs(since_timestamp: float = None) -> List[LogEntry]:
    """收集应用日志（Python logging FileHandler输出）"""
    entries = []
    log_files = [
        Path(_WORKSPACE_DIR) / "logs" / "app.log",
        Path(_WORKSPACE_DIR) / "logs" / "opc_manager.log",
    ]

    for log_file in log_files:
        if not log_file.exists():
            continue
        try:
            mtime = log_file.stat().st_mtime
            if since_timestamp and mtime < since_timestamp - 60:
                continue

            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-500:]

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    match = re.match(
                        r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}[,.]?\d*)\s*-?\s*(\w+)\s*-?\s*(\w+)\s*-?\s*(.*)',
                        line,
                    )
                    if match:
                        ts_str, name, level, message = match.groups()
                        try:
                            ts = datetime.strptime(ts_str.split(",")[0], "%Y-%m-%d %H:%M:%S").timestamp()
                        except ValueError:
                            ts = time.time()

                        if since_timestamp and ts < since_timestamp:
                            continue

                        level = level.upper()
                        if level not in LOG_LEVEL_CONFIG:
                            level = "INFO"

                        entries.append(LogEntry(
                            timestamp=ts,
                            level=level,
                            source="app",
                            message=sanitize_log_message(message),
                            module=name,
                        ))
                except Exception:
                    continue
        except Exception as e:
            logger.debug("[collect_app_logs] 读取 %s 失败: %s", log_file, e)

    return entries


def collect_engine_logs(since_timestamp: float = None) -> List[LogEntry]:
    """收集引擎日志（TaskEngineV3/AgentLoop debug日志）"""
    entries = []
    engine_log_files = [
        Path(_WORKSPACE_DIR) / "logs" / "engine.log",
        Path(_WORKSPACE_DIR) / "logs" / "task_engine.log",
        Path(_WORKSPACE_DIR) / "logs" / "agent_loop.log",
    ]

    for log_file in engine_log_files:
        if not log_file.exists():
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-300:]
            for line in lines:
                line = line.strip()
                if not line or "opc_manager" not in line.lower():
                    continue
                try:
                    match = re.match(r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})\s*[|-]\s*(\w+)\s*[|-]\s*(.*)', line)
                    if match:
                        ts_str, level, message = match.groups()
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                        except ValueError:
                            ts = time.time()

                        if since_timestamp and ts < since_timestamp:
                            continue

                        level = level.upper()
                        if level not in LOG_LEVEL_CONFIG:
                            level = "DEBUG"

                        entries.append(LogEntry(
                            timestamp=ts,
                            level=level,
                            source="engine",
                            message=sanitize_log_message(message),
                            module="task_engine",
                        ))
                except Exception:
                    continue
        except Exception as e:
            logger.debug("[collect_engine_logs] 读取失败: %s", e)

    return entries


def collect_audit_logs(since_timestamp: float = None) -> List[LogEntry]:
    """收集审计日志（AuditLog查询）"""
    entries = []
    try:
        from opc_manager.audit_log import AuditLog

        audit = AuditLog()
        records = audit.query(limit=30, since=since_timestamp)

        for record in records:
            status = record.get("status", "success")
            level = "ERROR" if status == "failed" else ("WARNING" if status == "cancelled" else "INFO")

            op_type = record.get("operation_type", "unknown")
            skill_id = record.get("skill_id", "unknown")
            duration = record.get("duration_ms", 0)

            message = f"[{op_type}] skill={skill_id} duration={duration}ms status={status}"
            if record.get("error_msg"):
                message += f" error={record['error_msg'][:100]}"

            entries.append(LogEntry(
                timestamp=record.get("timestamp", time.time()),
                level=level,
                source="audit",
                message=sanitize_log_message(message),
                module="audit_log",
                extra={"record_id": record.get("id", "")},
            ))
    except ImportError:
        logger.debug("[collect_audit_logs] AuditLog模块未安装")
    except Exception as e:
        logger.debug("[collect_audit_logs] 查询失败: %s", e)

    return entries


def collect_progress_logs(session_id: str = None, since_timestamp: float = None) -> List[LogEntry]:
    """收集进度事件日志（ProgressEmitter历史）"""
    entries = []
    try:
        from opc_manager.progress_emitter import ProgressEmitter, EventType

        emitter = ProgressEmitter()

        if session_id:
            history = emitter.get_history(session_id)
        else:
            all_events = []
            for sid in list(emitter._history.keys()):
                all_events.extend(emitter.get_history(sid))
            history = all_events

        for event_dict in history[-50:]:
            event_ts = event_dict.get("timestamp", time.time())
            if since_timestamp and event_ts < since_timestamp:
                continue

            event_type_str = event_dict.get("event", "unknown")
            message = event_dict.get("message", "")
            progress_pct = event_dict.get("progress")

            try:
                event_type = EventType(event_type_str)
                if event_type == EventType.ERROR:
                    level = "ERROR"
                elif event_type in (EventType.COMPLETE, EventType.CONFIRMED):
                    level = "INFO"
                else:
                    level = "INFO"
            except ValueError:
                level = "INFO"

            progress_str = f" ({progress_pct}%)" if progress_pct is not None else ""
            display_msg = f"[{event_type_str.upper()}]{progress_str} {message}"

            entries.append(LogEntry(
                timestamp=event_ts,
                level=level,
                source="progress",
                message=sanitize_log_message(display_msg),
                module="progress_emitter",
                extra={
                    "event_type": event_type_str,
                    "progress_pct": progress_pct,
                    "session_id": event_dict.get("session_id", ""),
                },
            ))
    except ImportError:
        logger.debug("[collect_progress_logs] ProgressEmitter模块未安装")
    except Exception as e:
        logger.debug("[collect_progress_logs] 获取历史失败: %s", e)

    return entries


def collect_system_logs(since_timestamp: float = None) -> List[LogEntry]:
    """收集系统日志（资源使用率等）"""
    entries = []
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(_WORKSPACE_DIR)

        entries.append(LogEntry(
            timestamp=time.time(),
            level="DEBUG",
            source="system",
            message=f"CPU: {cpu_percent}% | Memory: {memory.percent}% ({memory.used // 1024 // 1024}MB/{memory.total // 1024 // 1024}MB) | Disk: {disk.percent}%",
            module="system_monitor",
            extra={
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
            },
        ))
    except ImportError:
        entries.append(LogEntry(
            timestamp=time.time(),
            level="INFO",
            source="system",
            message="psutil未安装，系统监控不可用",
            module="system_monitor",
        ))
    except Exception as e:
        logger.debug("[collect_system_logs] 收集失败: %s", e)

    return entries


def collect_all_logs(since_timestamp: float = None, session_id: str = None) -> List[LogEntry]:
    """收集所有来源的最新日志条目

    Args:
        since_timestamp: 只收集此时间戳之后的日志
        session_id: 用于收集特定会话的进度事件

    Returns:
        合并并按时间排序的日志条目列表
    """
    all_entries = []

    all_entries.extend(collect_app_logs(since_timestamp))
    all_entries.extend(collect_engine_logs(since_timestamp))
    all_entries.extend(collect_audit_logs(since_timestamp))
    all_entries.extend(collect_progress_logs(session_id, since_timestamp))

    if random.random() < 0.05:
        all_entries.extend(collect_system_logs(since_timestamp))

    all_entries.sort(key=lambda x: x.timestamp)

    cache = _get_log_cache()
    if all_entries:
        cache.update(all_entries)

    return all_entries[-DEFAULT_DISPLAY_LIMIT:]


def _render_log_entry(entry: LogEntry, index: int):
    """渲染单条日志条目"""
    ts_str = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S.%f")[:-3]

    level_cfg = LOG_LEVEL_CONFIG.get(entry.level, LOG_LEVEL_CONFIG["INFO"])
    source_cfg = LOG_SOURCE_CONFIG.get(entry.source, {"label": entry.source, "icon": "📌"})

    col_time, col_icon, col_source, col_msg = st.columns([1.2, 0.6, 1.2, 6])

    with col_time:
        st.markdown(f'<span style="color:#9CA3AF;font-family:monospace;font-size:13px">'
                   f'{ts_str}</span>', unsafe_allow_html=True)

    with col_icon:
        st.markdown(f'<span style="font-size:18px">{level_cfg["icon"]}</span>',
                   unsafe_allow_html=True)

    with col_source:
        st.markdown(
            f'<span style="background:#E5E7EB;color:#374151;padding:2px 8px;'
            f'border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap">'
            f'{source_cfg["icon"]} {source_cfg["label"]}</span>',
            unsafe_allow_html=True,
        )

    with col_msg:
        st.markdown(
            f'<span style="color:{level_cfg["color"]};font-size:13px">'
            f'{entry.message.replace("<", "&lt;").replace(">", "&gt;")}</span>',
            unsafe_allow_html=True,
        )

        if entry.extra.get("traceback"):
            with st.expander("🔍 错误堆栈"):
                st.code(entry.extra["traceback"], language="python")


def _render_filter_bar(logs: List[LogEntry]) -> Tuple[List[LogEntry], Dict[str, Any]]:
    """渲染过滤器栏并返回过滤后的日志和过滤状态"""
    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 3])

    with filter_col1:
        min_level_index = st.selectbox(
            "最低级别",
            options=["全部", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1,
            key="log_level_filter",
            help="只显示此级别及以上的日志",
        )

    with filter_col2:
        sources = list(LOG_SOURCE_CONFIG.keys())
        selected_sources = st.multiselect(
            "日志来源",
            options=sources,
            default=sources,
            key="log_source_filter",
            help="选择要显示的日志来源",
        )

    with filter_col3:
        search_keyword = st.text_input(
            "搜索关键词",
            placeholder="输入关键词过滤...",
            key="log_search_keyword",
        )

    filtered_logs = logs

    if min_level_index != "全部":
        min_level_pos = LOG_LEVEL_ORDER.index(min_level_index)
        allowed_levels = set(LOG_LEVEL_ORDER[min_level_pos:])
        filtered_logs = [l for l in filtered_logs if l.level in allowed_levels]

    if selected_sources:
        filtered_logs = [l for l in filtered_logs if l.source in selected_sources]

    if search_keyword:
        keyword_lower = search_keyword.lower()
        filtered_logs = [l for l in filtered_logs if keyword_lower in l.message.lower()]

    filter_state = {
        "min_level": min_level_index,
        "sources": selected_sources,
        "keyword": search_keyword,
        "total_before": len(logs),
        "total_after": len(filtered_logs),
    }

    return filtered_logs, filter_state


def _render_stats_summary(logs: List[LogEntry]):
    """渲染底部统计摘要栏"""
    stats = {
        "DEBUG": 0,
        "INFO": 0,
        "WARNING": 0,
        "ERROR": 0,
        "CRITICAL": 0,
    }

    sources_count = {}
    for entry in logs:
        stats[entry.level] = stats.get(entry.level, 0) + 1
        sources_count[entry.source] = sources_count.get(entry.source, 0) + 1

    total = len(logs)
    now = datetime.now().strftime("%H:%M:%S")

    st.markdown("---")
    stat_cols = st.columns(7)

    with stat_cols[0]:
        st.metric("总计", total)

    with stat_cols[1]:
        st.metric("ℹ️ INFO", stats["INFO"])

    with stat_cols[2]:
        st.metric("⚠️ WARN", stats["WARNING"])

    with stat_cols[3]:
        st.metric("❌ ERROR", stats["ERROR"])

    with stat_cols[4]:
        st.metric("🚨 CRIT", stats["CRITICAL"])

    with stat_cols[5]:
        source_summary = ", ".join([f"{k}:{v}" for k, v in sorted(sources_count.items())])
        st.caption(f"来源: {source_summary}")

    with stat_cols[6]:
        st.caption(f"更新: {now}")


def export_logs(logs: List[LogEntry], format: str = "txt") -> bytes:
    """导出当前视图的日志

    Args:
        logs: 要导出的日志条目列表
        format: 导出格式 ('txt', 'json', 'csv')

    Returns:
        编码后的字节数据
    """
    format = format.lower()

    if format == "txt":
        lines = []
        for entry in logs:
            lines.append(entry.to_display())
        content = "\n".join(lines)
        return content.encode("utf-8")

    elif format == "json":
        data = [e.to_dict() for e in logs]
        content = json.dumps(data, ensure_ascii=False, indent=2)
        return content.encode("utf-8")

    elif format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "level", "source", "message", "module"])

        for entry in logs:
            ts_str = datetime.fromtimestamp(entry.timestamp).isoformat()
            writer.writerow([
                ts_str,
                entry.level,
                entry.source,
                entry.message,
                entry.module,
            ])

        return output.getvalue().encode("utf-8")

    else:
        raise ValueError(f"不支持的导出格式: {format}. 支持: txt, json, csv")


def render_live_log_panel(auto_refresh: bool = True, refresh_interval: int = 2):
    """主面板渲染函数：实时日志监控界面

    Args:
        auto_refresh: 是否启用自动刷新
        refresh_interval: 刷新间隔（秒），最小值为MIN_POLL_INTERVAL
    """
    refresh_interval = max(refresh_interval, MIN_POLL_INTERVAL)

    st.markdown("### 📡 实时日志监控")

    control_col1, control_col2, control_col3, control_col4 = st.columns([2, 1.5, 1.5, 1.5])

    with control_col1:
        auto_refresh = st.checkbox("▶️ 自动刷新", value=auto_refresh, key="log_auto_refresh")

    with control_col2:
        if st.button("🔄 刷新", use_container_width=True, key="log_manual_refresh"):
            st.rerun()

    with control_col3:
        if st.button("🗑️ 清空缓存", use_container_width=True, key="log_clear_cache"):
            cache = _get_log_cache()
            cache.clear()
            st.success("✅ 日志缓存已清空")
            st.rerun()

    with control_col4:
        export_format = st.selectbox(
            "导出格式",
            options=["txt", "json", "csv"],
            key="log_export_format",
        )

    session_ctx = st.session_state.get("session_ctx", None)
    if session_ctx is not None:
        if hasattr(session_ctx, '_session_id'):
            session_id = getattr(session_ctx, '_session_id', None)
        elif isinstance(session_ctx, dict):
            session_id = session_ctx.get("_session_id", None)
        else:
            session_id = str(session_ctx) if session_ctx else None
    else:
        session_id = None

    logs = collect_all_logs(session_id=session_id)

    if not logs:
        st.info("💡 暂无日志数据。执行任务后日志会自动显示在这里。")
        return

    filtered_logs, filter_state = _render_filter_bar(logs)

    if not filtered_logs:
        st.warning(f"⚠️ 无匹配日志（共 {filter_state['total_before']} 条，筛选后为0）")
        return

    st.caption(f"显示 {len(filtered_logs)} / {len(logs)} 条日志" +
               ("（已过滤）" if filter_state['total_after'] < filter_state['total_before'] else ""))

    st.markdown("""
    <style>
    .log-container {
        background: #FAFAFA;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 12px;
        max-height: 500px;
        overflow-y: auto;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .log-entry {
        padding: 6px 8px;
        border-bottom: 1px solid #F3F4F6;
        font-size: 13px;
        line-height: 1.5;
    }
    .log-entry:hover {
        background: #F9FAFB;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        with st.expander("📋 日志详情（点击展开）", expanded=True):
            for idx, entry in enumerate(filtered_logs[-100:]):
                _render_log_entry(entry, idx)

    _render_stats_summary(filtered_logs)

    if st.button(f"📥 导出日志 ({export_format.upper()})", use_container_width=True, key="log_export_btn"):
        try:
            export_data = export_logs(filtered_logs, format=export_format)
            mime_types = {"txt": "text/plain", "json": "application/json", "csv": "text/csv"}
            st.download_button(
                label=f"下载 {export_format.upper()} 文件",
                data=export_data,
                file_name=f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}",
                mime=mime_types.get(export_format, "application/octet-stream"),
                key=f"log_dl_{int(time.time())}",
            )
        except Exception as e:
            st.error(f"❌ 导出失败: {e}")

    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
