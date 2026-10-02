"""CRM UI for the operator workflow."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from opc_manager.crm_skill import (
    add_customer,
    add_deal,
    add_follow_up,
    get_customer,
    get_follow_ups,
    get_silent_customers,
    init_db,
    lifecycle_tracker,
    search_customers,
)
from opc_manager.confirmer import ConfirmationResult
from opc_manager.email_skill import send_email
from opc_manager.morning_brief import (
    build_morning_brief_email_draft,
    deliver_morning_brief_email,
    ensure_morning_brief_task,
    get_morning_brief_status,
    run_morning_brief_now,
)
from opc_manager.settings import get_settings
from opc_manager.promiselink_client import ClientState, PromiseLinkClient

_STATUS_OPTIONS = ["potential", "first_deal", "active", "silent", "lost"]
_PROMISELINK_STATE_LABELS = {
    ClientState.DISABLED.value: ("未启用", "当前使用本地 CRM 数据"),
    ClientState.UNCONFIGURED.value: ("未配置", "请配置 Base URL 和 Token"),
    ClientState.AVAILABLE.value: ("可用", "PromiseLink 已连接"),
    ClientState.DEGRADED.value: ("降级", "PromiseLink 请求失败，当前使用本地 CRM 数据"),
    ClientState.CIRCUIT_OPEN.value: (
        "熔断",
        "连续失败后暂时停止请求，当前使用本地 CRM 数据",
    ),
    ClientState.SCHEMA_MISMATCH.value: (
        "协议不匹配",
        "返回数据不符合契约，当前使用本地 CRM 数据",
    ),
}
_STATUS_LABELS = {
    "potential": "潜在客户",
    "first_deal": "首次合作",
    "active": "活跃",
    "silent": "沉默",
    "lost": "流失",
}


def _selected_customer() -> Dict[str, Any] | None:
    customer_id = st.session_state.get("crm_selected_customer_id", "")
    if not customer_id:
        return None
    result = get_customer(customer_id=customer_id)
    if result.get("success"):
        return result["customer"]
    return None


def _render_customer_list() -> None:
    st.subheader("客户列表")
    with st.form("crm_search_form"):
        company = st.text_input("公司", key="crm_search_company")
        status = st.selectbox(
            "生命周期",
            ["全部"] + _STATUS_OPTIONS,
            format_func=lambda value: (
                "全部" if value == "全部" else _STATUS_LABELS[value]
            ),
            key="crm_search_status",
        )
        submitted = st.form_submit_button("搜索客户", type="primary")
    if submitted or "crm_search_results" not in st.session_state:
        result = search_customers(
            company=company,
            status="" if status == "全部" else status,
        )
        st.session_state.crm_search_results = result.get("customers", [])

    customers: List[Dict[str, Any]] = st.session_state.get("crm_search_results", [])
    if not customers:
        st.info("暂无客户记录")
        return
    for customer in customers:
        label = f"{customer.get('name', '')} · {customer.get('company', '') or '未填写公司'}"
        if st.button(
            label, key=f"crm_customer_{customer['id']}", use_container_width=True
        ):
            st.session_state.crm_selected_customer_id = customer["id"]
            st.rerun()
        st.caption(
            f"{_STATUS_LABELS.get(customer.get('status', ''), customer.get('status', ''))} · "
            f"最近联系 {customer.get('last_contact', '') or '暂无'}"
        )


def _render_add_customer() -> None:
    st.subheader("新增客户")
    with st.form("crm_add_customer_form", clear_on_submit=True):
        name = st.text_input("姓名", key="crm_add_name")
        company = st.text_input("公司", key="crm_add_company")
        title = st.text_input("职位", key="crm_add_title")
        phone = st.text_input("电话", key="crm_add_phone")
        email = st.text_input("邮箱", key="crm_add_email")
        submitted = st.form_submit_button("保存客户", type="primary")
    if submitted:
        result = add_customer(name, company, title, phone, email)
        if result.get("success"):
            st.session_state.crm_selected_customer_id = result["id"]
            st.session_state.pop("crm_search_results", None)
            st.success(result["message"])
            st.rerun()
        else:
            st.error(result.get("error", "保存客户失败"))


def _render_customer_detail(customer: Dict[str, Any]) -> None:
    customer_id = customer["id"]
    st.subheader("客户详情")
    st.markdown(f"### {customer.get('name', '')}")
    st.caption(customer.get("company", "") or "未填写公司")
    st.write(f"邮箱：{customer.get('email', '') or '未填写'}")
    st.write(f"电话：{customer.get('phone', '') or '未填写'}")

    draft_key = f"crm_follow_draft_{customer_id}"
    draft_revision_key = f"crm_follow_draft_revision_{customer_id}"
    draft_initialized_key = f"crm_follow_draft_initialized_{customer_id}"
    if draft_revision_key not in st.session_state:
        st.session_state[draft_revision_key] = 0
    if st.button("生成跟进草稿", key=f"crm_generate_draft_{customer_id}"):
        name = customer.get("name", "客户")
        company = customer.get("company", "")
        greeting = f"{company}的{name}" if company else name
        draft = (
            f"您好，想跟进一下{greeting}前次沟通的进展。"
            "如果近期有新的需求或时间安排，欢迎告诉我。"
        )
        st.session_state[draft_key] = draft
        st.session_state[draft_revision_key] += 1
        st.rerun()

    draft = st.session_state.get(draft_key, "")
    draft_revision = st.session_state[draft_revision_key]
    follow_content_key = f"crm_follow_content_{customer_id}_{draft_revision}"
    email_body_key = f"crm_email_body_{customer_id}_{draft_revision}"
    if draft:
        initialized_revision = st.session_state.get(draft_initialized_key)
        if initialized_revision != draft_revision:
            st.session_state[follow_content_key] = draft
            st.session_state[email_body_key] = draft
            st.session_state[draft_initialized_key] = draft_revision
        st.caption("已生成跟进草稿，请确认或修改后保存。")

    with st.expander("邮件交付", expanded=False):
        recipient = st.text_input(
            "收件人邮箱",
            value=customer.get("email", ""),
            key=f"crm_email_recipient_{customer_id}",
        )
        subject = st.text_input(
            "邮件主题",
            value=f"跟进 {customer.get('name', '客户')}",
            key=f"crm_email_subject_{customer_id}",
        )
        email_body = st.text_area(
            "邮件正文",
            value=draft,
            key=email_body_key,
        )
        if st.button("发送跟进邮件", key=f"crm_send_email_{customer_id}"):
            if not recipient or not email_body.strip():
                st.error("发送前必须填写收件人邮箱和邮件正文")
            else:
                st.session_state[f"crm_email_pending_{customer_id}"] = {
                    "recipient": recipient,
                    "subject": subject,
                    "body": email_body,
                }
                st.warning("邮件尚未发送，请再次点击确认发送")

        pending_email = st.session_state.get(f"crm_email_pending_{customer_id}")
        if pending_email:
            st.info(
                f"待确认邮件：{pending_email['recipient']} · "
                f"{pending_email['subject']}"
            )
            if st.button(
                "确认发送跟进邮件",
                key=f"crm_confirm_email_{customer_id}",
            ):
                result = send_email(
                    pending_email["recipient"],
                    pending_email["subject"],
                    pending_email["body"],
                )
                if result.get("success"):
                    add_follow_up(customer_id, pending_email["body"])
                    st.session_state.pop(f"crm_email_pending_{customer_id}", None)
                    st.success("跟进邮件已发送，并已记录跟进")
                    st.rerun()
                else:
                    st.error(f"邮件未发送：{result.get('error', '未知错误')}")

    lifecycle = lifecycle_tracker(customer_id=customer_id)
    if lifecycle.get("success"):
        cols = st.columns(4)
        cols[0].metric("生命周期", lifecycle["stage"])
        cols[1].metric("沉默天数", lifecycle["silent_days"])
        cols[2].metric("成交数", lifecycle["deal_count"])
        cols[3].metric("跟进数", lifecycle["follow_up_count"])

    with st.expander("记录跟进", expanded=True):
        with st.form(f"crm_follow_up_form_{customer_id}"):
            content = st.text_area(
                "跟进内容",
                key=follow_content_key,
            )
            follow_date = st.date_input(
                "跟进日期", key=f"crm_follow_date_{customer_id}"
            )
            submitted = st.form_submit_button("保存跟进", type="primary")
        if submitted:
            result = add_follow_up(customer_id, content, follow_date.isoformat())
            if result.get("success"):
                st.session_state.pop(draft_key, None)
                st.success(result["message"])
                st.rerun()
            else:
                st.error(result.get("error", "保存跟进失败"))

    with st.expander("记录合作", expanded=False):
        with st.form(f"crm_deal_form_{customer_id}"):
            description = st.text_input(
                "合作内容", key=f"crm_deal_description_{customer_id}"
            )
            amount = st.number_input(
                "金额", min_value=0.0, step=100.0, key=f"crm_deal_amount_{customer_id}"
            )
            deal_status = st.selectbox(
                "合作状态",
                ["negotiating", "closed_won"],
                format_func=lambda value: (
                    "已成交" if value == "closed_won" else "洽谈中"
                ),
                key=f"crm_deal_status_{customer_id}",
            )
            submitted = st.form_submit_button("保存合作记录", type="primary")
        if submitted:
            result = add_deal(customer_id, description, amount, status=deal_status)
            if result.get("success"):
                st.success(result["message"])
                st.rerun()
            else:
                st.error(result.get("error", "保存合作记录失败"))

    follow_ups = get_follow_ups(customer_id).get("follow_ups", [])
    if follow_ups:
        st.markdown("#### 跟进历史")
        for item in follow_ups:
            st.markdown(
                f"- **{item.get('follow_date', '')}**：{item.get('content', '')}"
            )

    deals = customer.get("deals", [])
    if deals:
        st.markdown("#### 合作记录")
        for deal in deals:
            st.markdown(
                f"- **{deal.get('date', '')}**：{deal.get('description', '')} "
                f"（{deal.get('amount', 0)}，{deal.get('status', '')}）"
            )


def _render_promiselink_status(client: PromiseLinkClient) -> None:
    state = client.state().value
    label, reason = _PROMISELINK_STATE_LABELS[state]
    st.subheader("PromiseLink 状态")
    st.metric("当前状态", label)
    st.caption(f"状态码：{state}")
    st.info(reason)


def _render_morning_brief_email_delivery() -> None:
    draft = st.session_state.get("crm_morning_brief_email_draft")
    if not draft:
        return
    st.markdown("#### 早报邮件草稿")
    st.caption("草稿已保存到本地；Scheduler 不会自动发送 SMTP。")
    recipient = st.text_input(
        "早报收件人",
        value=draft.get("recipient", ""),
        key="crm_morning_brief_email_recipient",
    )
    subject = st.text_input(
        "早报邮件主题",
        value=draft.get("subject", "每日经营早报"),
        key="crm_morning_brief_email_subject",
    )
    body = st.text_area(
        "早报邮件正文",
        value=draft.get("body", ""),
        height=240,
        key="crm_morning_brief_email_body",
    )
    if st.button("申请发送早报邮件", key="crm_request_morning_brief_email"):
        st.session_state.crm_morning_brief_email_pending = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
        }
        st.warning("早报邮件尚未发送，请再次点击确认发送")

    pending = st.session_state.get("crm_morning_brief_email_pending")
    if not pending:
        return
    st.info(f"待确认早报邮件：{pending['recipient']} · {pending['subject']}")
    if st.button("确认发送早报邮件", key="crm_confirm_morning_brief_email"):
        confirmation = ConfirmationResult(
            confirmed=True,
            method="user_confirmation",
            user_choice="approve",
        )
        result = deliver_morning_brief_email(pending, confirmation=confirmation)
        if result.get("success"):
            st.session_state.pop("crm_morning_brief_email_pending", None)
            st.success("早报邮件已发送")
        else:
            st.error(f"早报邮件未发送：{result.get('error', '未知错误')}")


def _register_deliverable(path: str) -> None:
    filename = Path(path).name
    deliverables = st.session_state.setdefault("deliverables", [])
    if any(item.get("filename") == filename for item in deliverables):
        return
    parts = filename.removesuffix(".md").split("_", 3)
    created_at = ""
    if len(parts) > 1 and len(parts[0]) >= 8 and len(parts[1]) >= 6:
        created_at = datetime.strptime(
            f"{parts[0]}_{parts[1]}", "%Y%m%d_%H%M%S"
        ).strftime("%Y-%m-%d %H:%M:%S")
    deliverables.insert(
        0,
        {
            "filename": filename,
            "filepath": path,
            "prompt": parts[3] if len(parts) > 3 else "经营早报",
            "task_type": "morning_brief",
            "created_at": created_at,
            "size_kb": round(os.path.getsize(path) / 1024, 1),
        },
    )


def _render_morning_brief(client: PromiseLinkClient) -> None:
    st.subheader("经营早报")
    status = get_morning_brief_status()
    if status.get("configured"):
        schedule_label = (
            "已启用每日 08:00 本地早报" if status.get("enabled") else "早报任务未启用"
        )
        st.caption(schedule_label)
        if status.get("last_run_at"):
            st.caption(f"最近生成：{status['last_run_at']}")
    else:
        st.caption("每日早报尚未配置")

    if st.button("启用每日早报", key="crm_enable_morning_brief"):
        try:
            ensure_morning_brief_task()
            st.success("已启用每日 08:00 本地早报")
            st.rerun()
        except Exception as exc:
            st.error(f"早报任务未启用：{exc}")

    if st.button("立即生成早报", key="crm_run_morning_brief"):
        result = run_morning_brief_now()
        if result.get("success"):
            _register_deliverable(result["path"])
            markdown = Path(result["path"]).read_text(encoding="utf-8")
            recipient = st.session_state.get(
                "crm_morning_brief_email_recipient",
                get_settings().briefing.recipient_email,
            )
            draft = build_morning_brief_email_draft(markdown, recipient)
            if draft.get("success"):
                st.session_state.crm_morning_brief_email_draft = draft
            st.success("经营早报已生成，可在成果物页面查看")
        else:
            st.error(f"经营早报生成失败：{result.get('error', '未知错误')}")

    _render_morning_brief_email_delivery()

    if not st.button("刷新早报", key="crm_refresh_morning_brief"):
        st.caption("点击刷新查看今日经营摘要")
        return

    if client.state() is ClientState.AVAILABLE:
        result = client.get_morning_brief()
        if result.success:
            st.success("PromiseLink 经营早报已同步")
            st.json(result.data)
            return
        st.warning(
            f"PromiseLink 早报暂不可用：{result.state.value}；已切换本地 CRM 汇总"
        )

    local_result = get_silent_customers()
    st.info(
        "本地早报：沉默客户 "
        f"{local_result.get('count', 0)} 个；当前未连接 PromiseLink"
    )


def _render_silent_customers() -> None:
    st.subheader("沉默客户")
    days = st.number_input(
        "超过多少天未联系", min_value=1, value=30, step=1, key="crm_silent_days"
    )
    if st.button("刷新沉默客户", key="crm_refresh_silent"):
        st.session_state.crm_silent_result = get_silent_customers(int(days))
    result = st.session_state.get("crm_silent_result")
    if not result:
        st.caption("点击刷新查看沉默客户")
        return
    state = result.get("promiselink_state")
    if state:
        st.info(f"PromiseLink 状态：{state}；当前展示本地 CRM 数据")
    elif result.get("source") == "promiselink":
        st.success("PromiseLink 沉默客户数据已同步")
    for customer in result.get("customers", []):
        if st.button(
            f"{customer.get('name', '')} · {customer.get('company', '') or '未填写公司'}",
            key=f"crm_silent_{customer['id']}",
        ):
            st.session_state.crm_selected_customer_id = customer["id"]
            st.rerun()


def render_crm_page() -> None:
    init_db()
    st.title("客户管理")
    st.caption("沉默客户 → 跟进动作 → 记录结果")

    client = PromiseLinkClient()
    _render_promiselink_status(client)

    left, right = st.columns([1, 1])
    with left:
        _render_customer_list()
        _render_add_customer()
    with right:
        customer = _selected_customer()
        if customer:
            _render_customer_detail(customer)
        else:
            st.subheader("客户详情")
            st.info("从左侧选择客户，或先新增客户")
        _render_morning_brief(client)
        _render_silent_customers()
