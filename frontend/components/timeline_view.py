"""操作时间线可视化组件

提供用户操作历史的可视化展示，支持：
- 多数据源集成（deliverables、UndoManager、AuditLog、ProgressEmitter）
- 时间线垂直布局展示
- 多维度筛选（时间、类别、状态、关键词）
- 统计摘要和分组显示
- 导出功能（PNG/PDF/CSV）
- 响应式设计（移动端适配）

=== 核心数据结构 ===
TimelineEvent: 单个时间线事件的数据模型
EVENT_TYPE_CONFIG: 事件类型配置（图标、颜色、分类）

=== 主要函数 ===
render_timeline_view(): 主渲染器
build_timeline_from_session(): 从session状态构建时间线
"""

import streamlit as st
import time
import logging
import csv
import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_TIMELINE_EVENTS = 500
TIMELINE_BUILD_TIMEOUT_MS = 200


@dataclass
class TimelineEvent:
    """时间线事件数据模型

    Attributes:
        id: 事件唯一标识符
        timestamp: Unix时间戳
        event_type: 事件类型（task_complete/income_recorded/email_sent等）
        title: 简短标题（<50字符）
        description: 详细描述
        icon: emoji图标
        category: 分类（work/finance/communication/system）
        metadata: 附加元数据
        duration_ms: 操作耗时（毫秒）
        status: 状态（success/error/pending/cancelled）
        related_ids: 相关事件ID列表（用于连线）
    """
    id: str
    timestamp: float
    event_type: str
    title: str
    description: str
    icon: str
    category: str
    metadata: dict = field(default_factory=dict)
    duration_ms: float = 0
    status: str = "success"
    related_ids: list = field(default_factory=list)

    def __post_init__(self):
        if len(self.title) > 50:
            self.title = self.title[:47] + "..."


EVENT_TYPE_CONFIG = {
    "task_complete": {
        "icon": "✅",
        "color": "#10B981",
        "category": "work",
        "label": "任务完成",
    },
    "income_recorded": {
        "icon": "💰",
        "color": "#F59E0B",
        "category": "finance",
        "label": "收入记录",
    },
    "expense_recorded": {
        "icon": "💸",
        "color": "#EF4444",
        "category": "finance",
        "label": "支出记录",
    },
    "email_sent": {
        "icon": "📧",
        "color": "#3B82F6",
        "category": "communication",
        "label": "邮件发送",
    },
    "proposal_created": {
        "icon": "📋",
        "color": "#8B5CF6",
        "category": "work",
        "label": "方案创建",
    },
    "error_occurred": {
        "icon": "❌",
        "color": "#EF4444",
        "category": "system",
        "label": "错误",
    },
    "undo_action": {
        "icon": "↩️",
        "color": "#6B7280",
        "category": "system",
        "label": "撤销操作",
    },
    "confirmation_required": {
        "icon": "⚠️",
        "color": "#F59E0B",
        "category": "system",
        "label": "待确认",
    },
    "skill_executed": {
        "icon": "🛠️",
        "color": "#06B6D4",
        "category": "work",
        "label": "技能执行",
    },
    "dashboard_viewed": {
        "icon": "📊",
        "color": "#3B82F6",
        "category": "work",
        "label": "查看仪表盘",
    },
}

CATEGORY_LABELS = {
    "work": "工作",
    "finance": "财务",
    "communication": "沟通",
    "system": "系统",
}

STATUS_LABELS = {
    "success": "成功",
    "error": "错误",
    "pending": "待处理",
    "cancelled": "已取消",
    "undone": "已撤销",
}


def build_timeline_from_session(session_id: str = "") -> List[TimelineEvent]:
    """从当前session状态构建完整时间线

    集成多个数据源：
    1. deliverables_records → task_complete事件
    2. UndoManager records → undo_action/task_complete事件
    3. AuditLog entries → email_sent, income_recorded等
    4. ProgressEmitter history → confirmation_required, error_occurred
    5. Chat history → dashboard_viewed, skill_executed（启发式推断）

    Args:
        session_id: 会话标识符

    Returns:
        按时间戳降序排列的事件列表（最新在前）
    """
    start_time = time.time()
    events = []

    try:
        events.extend(_build_from_deliverables())
    except Exception as e:
        logger.warning("[timeline] 构建deliverables事件失败: %s", e)

    try:
        events.extend(_build_from_undo_manager(session_id))
    except Exception as e:
        logger.warning("[timeline] 构建undo_manager事件失败: %s", e)

    try:
        events.extend(_build_from_audit_log())
    except Exception as e:
        logger.warning("[timeline] 构建audit_log事件失败: %s", e)

    try:
        events.extend(_build_from_progress_emitter(session_id))
    except Exception as e:
        logger.warning("[timeline] 构建progress_emitter事件失败: %s", e)

    try:
        events.extend(_build_from_chat_history())
    except Exception as e:
        logger.warning("[timeline] 构建chat_history事件失败: %s", e)

    events.sort(key=lambda x: x.timestamp, reverse=True)

    if len(events) > MAX_TIMELINE_EVENTS:
        events = events[:MAX_TIMELINE_EVENTS]

    elapsed_ms = (time.time() - start_time) * 1000
    if elapsed_ms > TIMELINE_BUILD_TIMEOUT_MS:
        logger.warning("[timeline] 构建耗时%.1fms（超过%dms限制）", elapsed_ms, TIMELINE_BUILD_TIMEOUT_MS)

    return events


def _build_from_deliverables() -> List[TimelineEvent]:
    """从deliverables记录构建task_complete事件"""
    events = []
    deliverables = st.session_state.get("deliverables", [])

    for record in deliverables:
        if not isinstance(record, dict):
            continue

        created_at = record.get("created_at", 0)
        if isinstance(created_at, str):
            try:
                created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                created_at = 0

        events.append(TimelineEvent(
            id=record.get("id", f"del_{hash(str(record))}"),
            timestamp=created_at,
            event_type="task_complete",
            title=record.get("prompt", "任务完成")[:50],
            description=f"生成 {record.get('task_type', '文档')}",
            icon="✅",
            category="work",
            metadata={
                "filepath": record.get("filepath", ""),
                "filename": record.get("filename", ""),
                "task_type": record.get("task_type", ""),
                "size_kb": record.get("size_kb", 0),
            },
            status="success",
        ))

    return events


def _build_from_undo_manager(session_id: str) -> List[TimelineEvent]:
    """从UndoManager记录构建undo_action/task_complete事件"""
    events = []

    try:
        from opc_manager.undo_manager import get_undo_manager
        undo_mgr = get_undo_manager()

        if not undo_mgr or not session_id:
            return events

        records = undo_mgr.list_records(session_id)

        for record in records:
            if not hasattr(record, 'operation_id'):
                continue

            is_undone = getattr(record, 'status', '') == 'undone'
            operation_type = getattr(record, 'operation_type', None)
            op_type_str = operation_type.value if operation_type else "unknown"

            events.append(TimelineEvent(
                id=getattr(record, 'operation_id', ''),
                timestamp=getattr(record, 'created_at', 0),
                event_type="undo_action" if is_undone else "task_complete",
                title=_get_undo_description(record),
                description=f"{op_type_str} 操作",
                icon="↩️" if is_undone else "✅",
                category="system",
                metadata={
                    "operation_type": op_type_str,
                    "inverse_func": getattr(record, 'inverse_func_name', ''),
                },
                status="undone" if is_undone else "success",
            ))
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] UndoManager集成异常: %s", e)

    return events


def _get_undo_description(record) -> str:
    """生成撤销操作的描述文本"""
    op_type = getattr(record, 'operation_type', None)
    op_str = op_type.value if op_type else "操作"

    type_labels = {
        "email_send": "发送邮件",
        "record_income": "记录收入",
        "record_expense": "记录支出",
        "add_event": "添加日程",
        "add_deal": "添加商机",
        "create_proposal": "创建方案",
        "create_invoice": "创建发票",
        "add_customer": "添加客户",
        "add_follow_up": "添加跟进",
        "social_publish": "发布内容",
    }

    label = type_labels.get(op_str, op_str)
    status = getattr(record, 'status', '')

    if status == 'undone':
        return f"撤销了{label}"
    return f"执行了{label}"


def _build_from_audit_log() -> List[TimelineEvent]:
    """从AuditLog条目构建各类业务事件"""
    events = []

    try:
        from opc_manager.audit_log import AuditLog
        audit = AuditLog()

        entries = audit.get_recent_entries(limit=30) if hasattr(audit, 'get_recent_entries') else []

        for entry in entries:
            if not isinstance(entry, dict) and not hasattr(entry, 'operation_type'):
                continue

            op_type = getattr(entry, 'operation_type', '') if hasattr(entry, 'operation_type') else entry.get('operation_type', '')
            event_info = _map_audit_operation_to_event(op_type)

            if not event_info:
                continue

            event_type, icon, category = event_info

            timestamp = getattr(entry, 'timestamp', 0) if hasattr(entry, 'timestamp') else entry.get('timestamp', 0)
            input_summary = getattr(entry, 'input_summary', '') if hasattr(entry, 'input_summary') else entry.get('input_summary', '')
            output_summary = getattr(entry, 'output_summary', '') if hasattr(entry, 'output_summary') else entry.get('output_summary', '')
            duration = getattr(entry, 'duration_ms', 0) if hasattr(entry, 'duration_ms') else entry.get('duration_ms', 0)
            status = getattr(entry, 'status', 'success') if hasattr(entry, 'status') else entry.get('status', 'success')

            events.append(TimelineEvent(
                id=getattr(entry, 'id', f"audit_{hash(str(entry))}") if hasattr(entry, 'id') else entry.get('id', f"audit_{hash(str(entry))}"),
                timestamp=timestamp,
                event_type=event_type,
                title=input_summary[:50] if input_summary else event_type,
                description=output_summary[:100] if output_summary else op_type,
                icon=icon,
                category=category,
                metadata={
                    "operation_type": op_type,
                    "skill_id": getattr(entry, 'skill_id', '') if hasattr(entry, 'skill_id') else entry.get('skill_id', ''),
                },
                duration_ms=float(duration),
                status=status if status in STATUS_LABELS else "success",
            ))
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] AuditLog集成异常: %s", e)

    return events


def _map_audit_operation_to_event(operation_type: str) -> Optional[Tuple[str, str, str]]:
    """将AuditLog的operation_type映射到时间线事件类型"""
    mapping = {
        "email_send": ("email_sent", "📧", "communication"),
        "send_email": ("email_sent", "📧", "communication"),
        "record_income": ("income_recorded", "💰", "finance"),
        "income_record": ("income_recorded", "💰", "finance"),
        "record_expense": ("expense_recorded", "💸", "finance"),
        "expense_record": ("expense_recorded", "💸", "finance"),
        "create_proposal": ("proposal_created", "📋", "work"),
        "proposal_create": ("proposal_created", "📋", "work"),
        "execute_skill": ("skill_executed", "🛠️", "work"),
        "skill_run": ("skill_executed", "🛠️", "work"),
    }
    return mapping.get(operation_type.lower())


def _build_from_progress_emitter(session_id: str) -> List[TimelineEvent]:
    """从ProgressEmitter历史构建confirm_required和error_occurred事件"""
    events = []

    try:
        from opc_manager.progress_emitter import get_progress_emitter
        emitter = get_progress_emitter()

        if not emitter or not session_id:
            return events

        history = emitter.get_history(session_id)

        for evt in history:
            if not isinstance(evt, dict):
                continue

            event_val = evt.get("event", evt.get("event_type", ""))

            if event_val in ("confirm_requested", "CONFIRM_REQUESTED"):
                events.append(TimelineEvent(
                    id=f"prog_confirm_{evt.get('timestamp', 0)}",
                    timestamp=evt.get("timestamp", 0),
                    event_type="confirmation_required",
                    title=evt.get("message", "等待确认")[:50],
                    description="需要用户确认后继续",
                    icon="⚠️",
                    category="system",
                    metadata={"progress": evt.get("progress", 0)},
                    status="pending",
                ))

            elif event_val in ("error", "ERROR"):
                events.append(TimelineEvent(
                    id=f"prog_error_{evt.get('timestamp', 0)}",
                    timestamp=evt.get("timestamp", 0),
                    event_type="error_occurred",
                    title=evt.get("message", "发生错误")[:50],
                    description=evt.get("detail", {}).get("error_msg", "")[:100] if evt.get("detail") else "",
                    icon="❌",
                    category="system",
                    metadata={"detail": evt.get("detail", {})},
                    status="error",
                ))
    except ImportError:
        pass
    except Exception as e:
        logger.debug("[timeline] ProgressEmitter集成异常: %s", e)

    return events


def _build_from_chat_history() -> List[TimelineEvent]:
    """从聊天历史启发式推断dashboard_viewed和skill_executed事件"""
    events = []
    messages = st.session_state.get("messages", [])

    dashboard_keywords = ["仪表盘", "dashboard", "统计", "报表", "数据概览"]
    skill_keywords = ["执行技能", "运行技能", "skill", "调用"]

    for msg in messages[-20:]:
        if not isinstance(msg, dict):
            continue

        content = msg.get("content", "")
        timestamp = msg.get("timestamp", time.time())

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").timestamp()
            except (ValueError, TypeError):
                timestamp = time.time()

        role = msg.get("role", "")

        if any(kw in content.lower() for kw in dashboard_keywords):
            events.append(TimelineEvent(
                id=f"chat_dash_{timestamp}",
                timestamp=timestamp,
                event_type="dashboard_viewed",
                title="查看仪表盘",
                description="查看了数据统计或报表",
                icon="📊",
                category="work",
                status="success",
            ))

        elif role == "assistant" and any(kw in content.lower() for kw in skill_keywords):
            events.append(TimelineEvent(
                id=f"chat_skill_{timestamp}",
                timestamp=timestamp,
                event_type="skill_executed",
                title="技能执行",
                description=content[:80],
                icon="🛠️",
                category="work",
                status="success",
            ))

    return events


def render_timeline_view(events: List[TimelineEvent], title: str = "操作时间线"):
    """主渲染器：渲染完整的时间线视图

    UI布局：
    - 顶部：标题 + 统计摘要 + 筛选器
    - 中部：按时间分组的事件列表（垂直时间线）
    - 底部：加载更多 + 导出按钮

    Args:
        events: TimelineEvent列表
        title: 视图标题
    """
    if not events:
        st.info("📭 暂无操作记录")
        return

    st.markdown(f"### 🕐 {title}")

    _render_timeline_stats(events)

    filtered_events, filters = _render_timeline_filters(events)

    if not filtered_events:
        st.warning("⚠️ 没有符合筛选条件的事件")
        return

    group_by = filters.get("group_by", "hour")
    grouped = _group_events_by_time(filtered_events, group_by)

    _inject_timeline_css()

    container = st.container()

    with container:
        for group_label, group_events in grouped.items():
            st.markdown(f"#### 📅 {group_label}")

            for i, event in enumerate(group_events):
                is_latest = (i == 0 and group_label == list(grouped.keys())[0])
                _render_timeline_event(event, is_latest)

            st.markdown("---")

    if len(filtered_events) < len(events):
        col_load, col_info = st.columns([1, 3])
        with col_load:
            if st.button("加载更早记录...", key="load_more_timeline"):
                st.session_state.timeline_limit = (
                    st.session_state.get("timeline_limit", 50) + 50
                )
                st.rerun()
        with col_info:
            st.caption(f"显示 {len(filtered_events)} / {len(events)} 条")

    _render_export_section(events)


def _render_timeline_stats(events: List[TimelineEvent]):
    """渲染时间线顶部统计摘要

    显示：
    - 总操作数
    - 各状态计数（成功/错误/撤销/待确认）
    - 总工作时长估算
    - 最活跃时段
    """
    total = len(events)
    success_count = sum(1 for e in events if e.status == "success")
    error_count = sum(1 for e in events if e.status == "error")
    undone_count = sum(1 for e in events if e.status in ("undone", "cancelled"))
    pending_count = sum(1 for e in events if e.status == "pending")

    total_duration = sum(e.duration_ms for e in events if e.duration_ms > 0)
    duration_min = total_duration / 60000 if total_duration > 0 else 0

    hour_counts = defaultdict(int)
    for e in events:
        try:
            dt = datetime.fromtimestamp(e.timestamp)
            hour_counts[dt.hour] += 1
        except (ValueError, OSError):
            pass

    peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
    peak_range = f"{peak_hour:02d}:00-{(peak_hour+1)%24:02d}:00"

    cols = st.columns(5)
    with cols[0]:
        st.metric("总操作", f"{total}次")
    with cols[1]:
        st.metric("成功", f"{success_count}", delta_color="normal")
    with cols[2]:
        if error_count > 0:
            st.metric("错误", f"{error_count}", delta_color="inverse")
        else:
            st.metric("错误", "0")
    with cols[3]:
        st.metric("撤销/取消", f"{undone_count}")
    with cols[4]:
        if duration_min > 0:
            st.metric("工作时长", f"~{duration_min:.0f}分钟")
        else:
            st.metric("工作时长", "-")

    st.caption(f"📊 最活跃时段: {peak_range} | 成功率: {(success_count/total*100):.1f}%" if total > 0 else "")


def _render_timeline_filters(events: List[TimelineEvent]) -> Tuple[List[TimelineEvent], Dict]:
    """渲染筛选控制面板

    提供：
    - 时间范围选择（今天/本周/本月/全部）
    - 类别筛选（复选框）
    - 状态筛选（复选框）
    - 关键词搜索

    Returns:
        (过滤后的事件列表, 当前筛选参数字典)
    """
    with st.expander("🔍 筛选与搜索", expanded=False):

        col_time, col_search = st.columns([1, 1])

        with col_time:
            time_range = st.selectbox(
                "时间范围",
                options=["all", "today", "week", "month"],
                format_func=lambda x: {
                    "all": "全部时间",
                    "today": "今天",
                    "week": "本周",
                    "month": "本月",
                }.get(x, x),
                key="timeline_time_range",
            )

        with col_search:
            keyword = st.text_input(
                "关键词搜索",
                placeholder="搜索标题或描述...",
                key="timeline_keyword",
        )

        col_cat, col_status = st.columns(2)

        with col_cat:
            categories = st.multiselect(
                "事件类别",
                options=list(CATEGORY_LABELS.keys()),
                format_func=lambda x: CATEGORY_LABELS.get(x, x),
                default=list(CATEGORY_LABELS.keys()),
                key="timeline_categories",
            )

        with col_status:
            statuses = st.multiselect(
                "事件状态",
                options=list(STATUS_LABELS.keys()),
                format_func=lambda x: STATUS_LABELS.get(x, x),
                default=list(STATUS_LABELS.keys()),
                key="timeline_statuses",
            )

        group_by = st.selectbox(
            "分组方式",
            options=["hour", "day"],
            format_func=lambda x: {"hour": "按小时", "day": "按天"}.get(x, x),
            index=0,
            key="timeline_group_by",
        )

    filters = {
        "time_range": time_range,
        "keyword": keyword,
        "categories": categories,
        "statuses": statuses,
        "group_by": group_by,
    }

    filtered = _apply_filters(events, filters)

    return filtered, filters


def _apply_filters(events: List[TimelineEvent], filters: Dict) -> List[TimelineEvent]:
    """应用筛选条件到事件列表

    Args:
        events: 原始事件列表
        filters: 筛选参数字典

    Returns:
        过滤后的事件列表
    """
    result = events.copy()

    time_range = filters.get("time_range", "all")
    now = datetime.now()

    if time_range == "today":
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        result = [e for e in result if e.timestamp >= today_start]

    elif time_range == "week":
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        result = [e for e in result if e.timestamp >= week_start]

    elif time_range == "month":
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        result = [e for e in result if e.timestamp >= month_start]

    keyword = filters.get("keyword", "").strip()
    if keyword:
        keyword_lower = keyword.lower()
        result = [
            e for e in result
            if keyword_lower in e.title.lower()
            or keyword_lower in e.description.lower()
        ]

    categories = filters.get("categories", [])
    if categories and set(categories) != set(CATEGORY_LABELS.keys()):
        result = [e for e in result if e.category in categories]

    statuses = filters.get("statuses", [])
    if statuses and set(statuses) != set(STATUS_LABELS.keys()):
        result = [e for e in result if e.status in statuses]

    limit = st.session_state.get("timeline_limit", 50)
    if len(result) > limit:
        result = result[:limit]

    return result


def _group_events_by_time(events: List[TimelineEvent], group_by: str = "hour") -> Dict[str, List[TimelineEvent]]:
    """按时间分组事件

    Args:
        events: 事件列表
        group_by: 分组方式（"hour"/"day"）

    Returns:
        分组后的字典 {组标签: 事件列表}
    """
    groups = defaultdict(list)
    now = datetime.now()

    for event in events:
        try:
            dt = datetime.fromtimestamp(event.timestamp)
        except (ValueError, OSError):
            dt = now

        if group_by == "hour":
            if dt.date() == now.date():
                label = f"{dt.strftime('%H:%M')} 今天"
            elif dt.date() == (now - timedelta(days=1)).date():
                label = f"{dt.strftime('%H:%M')} 昨天"
            else:
                label = dt.strftime("%m-%d %H:%M")

        elif group_by == "day":
            if dt.date() == now.date():
                label = "今天"
            elif dt.date() == (now - timedelta(days=1)).date():
                label = "昨天"
            elif (now - dt.date()).days <= 7:
                label = dt.strftime("%A")
            else:
                label = dt.strftime("%Y-%m-%d")
        else:
            label = dt.strftime("%Y-%m-%d %H:%M")

        groups[label].append(event)

    sorted_groups = dict(sorted(groups.items(), key=lambda x: x[1][0].timestamp if x[1] else 0, reverse=True))
    return sorted_groups


def _render_timeline_event(event: TimelineEvent, is_latest: bool = False):
    """渲染单个时间线事件节点

    根据event_type和status渲染不同样式：
    - 成功：绿色圆点 + 实线连接
    - 错误：红色圆点 + 虚线连接
    - 撤销：灰色圆点 + 删除线样式
    - 待确认：黄色闪烁效果

    UI结构：
    ┌─────────────────────────────────────┐
    │ 14:30  ✅ ───────●                  │
    │        │  标题                       │
    │        │  描述 | 耗时 | 元数据       │
    │        │  [展开详情]                 │
    └─────────────────────────────────────┘

    Args:
        event: TimelineEvent实例
        is_latest: 是否为最新事件（特殊标记）
    """
    config = EVENT_TYPE_CONFIG.get(event.event_type, {})
    color = config.get("color", "#6B7280")

    try:
        time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
    except (ValueError, OSError):
        time_str = "--:--"

    status_badge = STATUS_LABELS.get(event.status, event.status)
    cat_badge = CATEGORY_LABELS.get(event.category, event.category)

    line_style = "solid"
    opacity = "1"

    if event.status == "error":
        line_style = "dashed"
    elif event.status in ("undone", "cancelled"):
        opacity = "0.6"

    container_key = f"timeline_event_{event.id}"

    with st.container():
        col_time, col_content = st.columns([1, 5])

        with col_time:
            st.markdown(f"<div style='text-align:right; font-family:monospace; color:#6B7280; font-size:14px; padding-top:8px;'>{time_str}</div>", unsafe_allow_html=True)

        with col_content:
            event_html = f"""
            <div style="
                display: flex;
                align-items: flex-start;
                gap: 12px;
                margin-bottom: 16px;
                opacity: {opacity};
            ">
                <div style="
                    font-size: 24px;
                    min-width: 32px;
                    text-align: center;
                    line-height: 1;
                ">{event.icon}</div>

                <div style="
                    flex: 1;
                    background: white;
                    border-radius: 8px;
                    padding: 12px 16px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    border-left: 3px solid {color};
                    position: relative;
                ">
                    {'<div style="position:absolute;top:-8px;right:-8px;background:#10B981;color:white;font-size:10px;padding:2px 6px;border-radius:10px;">最新</div>' if is_latest else ''}

                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <strong style="font-size:15px;color:#1F2937;">{_escape_html(event.title)}</strong>
                        {f'<span style="font-size:11px;background:{color};color:white;padding:2px 8px;border-radius:10px;">{status_badge}</span>' if event.status != 'success' else ''}
                    </div>

                    <div style="font-size:13px;color:#6B7280;margin-bottom:8px;">
                        {_escape_html(event.description)}
                    </div>

                    <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:#9CA3AF;">
                        <span>📁 {cat_badge}</span>
                        {f'<span>⏱️ {event.duration_ms:.1f}s</span>' if event.duration_ms > 0 else ''}
                        {f'<span>🔗 {len(event.related_ids)}个相关</span>' if event.related_ids else ''}
                    </div>
                </div>
            </div>
            """

            st.markdown(event_html, unsafe_allow_html=True)

            with st.expander("查看详情", expanded=False):
                _render_event_detail_panel(event)


def _render_event_detail_panel(event: TimelineEvent):
    """渲染事件详情面板

    显示完整的元数据和相关信息：
    - 执行耗时
    - 文件路径（如有）
    - 收件人/金额（如有）
    - 相关操作链接
    - 错误详情（如有）
    """
    col_meta, col_actions = st.columns([2, 1])

    with col_meta:
        st.markdown("**基本信息**")
        meta_data = {
            "事件ID": event.id[:16] + "..." if len(event.id) > 16 else event.id,
            "事件类型": event.event_type,
            "分类": CATEGORY_LABELS.get(event.category, event.category),
            "状态": STATUS_LABELS.get(event.status, event.status),
            "时间戳": datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "耗时": f"{event.duration_ms:.2f}秒" if event.duration_ms > 0 else "-",
        }

        for label, value in meta_data.items():
            st.markdown(f"- **{label}**: `{value}`")

        if event.metadata:
            st.markdown("**元数据**")
            st.json(event.metadata)

    with col_actions:
        st.markdown("**快速操作**")

        filepath = event.metadata.get("filepath", "")
        if filepath and os.path.exists(filepath):
            if st.button("📥 打开文件", key=f"open_file_{event.id}"):
                st.info(f"文件路径: {filepath}")

        if event.related_ids:
            if st.button("🔗 查看关联操作", key=f"related_{event.id}"):
                st.session_state.selected_related_ids = event.related_ids
                st.rerun()

        if event.status == "error" and event.metadata.get("detail"):
            st.markdown("**错误详情**")
            detail = event.metadata["detail"]
            if isinstance(detail, dict):
                st.json(detail)
            else:
                st.error(str(detail))


def _render_export_section(events: List[TimelineEvent]):
    """渲染导出功能区域

    支持3种导出格式：
    - PNG图片（HTML Canvas渲染）
    - CSV数据（电子表格友好）
    - Markdown报告（文字说明）
    """
    with st.expander("📤 导出时间线", expanded=False):
        export_format = st.selectbox(
            "选择导出格式",
            options=["csv", "markdown"],
            format_func=lambda x: {
                "csv": "CSV 数据表",
                "markdown": "Markdown 报告",
                "png": "PNG 图片",
            }.get(x, x.upper()),
            key="timeline_export_format",
        )

        if st.button("导出", key="export_timeline_btn", type="primary"):
            exported = export_timeline(events, export_format)

            if exported:
                file_ext = {"csv": "csv", "markdown": "md", "png": "png"}.get(export_format, "txt")
                mime_types = {"csv": "text/csv", "markdown": "text/markdown", "png": "image/png"}
                st.download_button(
                    label=f"⬇️ 下载 {export_format.upper()} 文件",
                    data=exported,
                    file_name=f"timeline_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_ext}",
                    mime=mime_types.get(export_format, "application/octet-stream"),
                    key=f"dl_timeline_{export_format}",
                )


def export_timeline(events: List[TimelineEvent], format: str = "csv") -> Optional[bytes]:
    """导出时间线数据

    Args:
        events: TimelineEvent列表
        format: 导出格式（csv/markdown/png）

    Returns:
        导出的字节数据，如果失败返回None
    """
    if not events:
        st.warning("没有可导出的数据")
        return None

    try:
        if format == "csv":
            return _export_to_csv(events)
        elif format == "markdown":
            return _export_to_markdown(events).encode("utf-8")
        elif format == "png":
            return _export_to_png(events)
        else:
            st.error(f"不支持的导出格式: {format}")
            return None
    except Exception as e:
        logger.error("[timeline] 导出失败: %s", e)
        st.error(f"导出失败: {e}")
        return None


def _export_to_csv(events: List[TimelineEvent]) -> bytes:
    """导出为CSV格式"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "时间戳", "时间", "事件类型", "标题", "描述",
        "分类", "状态", "耗时(ms)", "图标", "事件ID"
    ])

    for event in events:
        try:
            time_str = datetime.fromtimestamp(event.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            time_str = ""

        writer.writerow([
            event.timestamp,
            time_str,
            event.event_type,
            event.title,
            event.description,
            event.category,
            event.status,
            event.duration_ms,
            event.icon,
            event.id,
        ])

    return output.getvalue().encode("utf-8-sig")


def _export_to_markdown(events: List[TimelineEvent]) -> str:
    """导出为Markdown格式的报告"""
    lines = []
    lines.append("# 操作时间线报告\n")
    lines.append(f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**事件总数**: {len(events)}\n")
    lines.append("---\n")

    current_date = None
    for event in events:
        try:
            dt = datetime.fromtimestamp(event.timestamp)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except (ValueError, OSError):
            date_str = ""
            time_str = ""

        if date_str != current_date:
            current_date = date_str
            lines.append(f"\n## {date_str}\n")

        config = EVENT_TYPE_CONFIG.get(event.event_type, {})
        lines.append(f"### {time_str} {event.icon} {event.title}\n")
        lines.append(f"- **类型**: {config.get('label', event.event_type)}\n")
        lines.append(f"- **描述**: {event.description}\n")
        lines.append(f"- **分类**: {CATEGORY_LABELS.get(event.category, event.category)}\n")
        lines.append(f"- **状态**: {STATUS_LABELS.get(event.status, event.status)}\n")

        if event.duration_ms > 0:
            lines.append(f"- **耗时**: {event.duration_ms:.2f}秒\n")

        if event.metadata:
            lines.append(f"- **元数据**: `{event.metadata}`\n")

        lines.append("\n---\n")

    return "\n".join(lines)


def _export_to_png(events: List[TimelineEvent]) -> bytes:
    """导出为PNG图片（使用HTML+CSS渲染）"""
    html_parts = ['''
    <html>
    <head><meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; background: #f9fafb; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #1f2937; margin-bottom: 8px; }
        .event { display: flex; align-items: flex-start; margin-bottom: 20px; position: relative; padding-left: 40px; }
        .event::before { content: ''; position: absolute; left: 15px; top: 30px; bottom: -20px; width: 2px; background: #e5e7eb; }
        .event:last-child::before { display: none; }
        .dot { position: absolute; left: 8px; top: 8px; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 0 2px #e5e7eb; }
        .time { font-family: monospace; color: #6b7280; font-size: 13px; min-width: 50px; }
        .card { flex: 1; background: white; border-radius: 8px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .card-title { font-weight: 600; color: #1f2937; margin-bottom: 4px; }
        .card-desc { font-size: 13px; color: #6b7280; }
    </style></head><body>
    ''']

    html_parts.append('<div class="header"><h1>🕐 操作时间线</h1>')
    html_parts.append(f'<p>共 {len(events)} 条记录 | 导出于 {datetime.now().strftime("%Y-%m-%d %H:%M")}</p></div>')

    for event in events[:50]:
        config = EVENT_TYPE_CONFIG.get(event.event_type, {})
        color = config.get("color", "#6b7280")

        try:
            time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M")
        except (ValueError, OSError):
            time_str = "--:--"

        escaped_title = event.title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        escaped_desc = event.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html_parts.append(f'''
        <div class="event">
            <div class="dot" style="background: {color};"></div>
            <div class="time">{time_str}</div>
            <div class="card">
                <div class="card-title">{event.icon} {escaped_title}</div>
                <div class="card-desc">{escaped_desc}</div>
            </div>
        </div>
        ''')

    html_parts.append('</body></html>')

    return "\n".join(html_parts).encode("utf-8")


def _inject_timeline_css():
    """注入时间线专用CSS样式"""
    st.markdown("""
    <style>
    .timeline-container {
        position: relative;
        padding-left: 20px;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .timeline-event-card {
        animation: fadeIn 0.3s ease-out forwards;
    }

    @media (max-width: 768px) {
        .timeline-mobile-time {
            text-align: left !important;
            margin-bottom: 4px;
            font-size: 12px !important;
        }

        .timeline-event-card {
            width: 100% !important;
            padding: 8px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def _escape_html(text: str) -> str:
    """转义HTML特殊字符"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;"))
