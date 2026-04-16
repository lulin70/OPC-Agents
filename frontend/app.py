"""Streamlit 前端 - OPC-Agents v3.0 (用户中心版)

设计原则：
1. 首屏即对话 — 不强制选择类型，后台自动识别
2. 场景快捷入口 — "我能帮你做什么"而非"请选类型"
3. 后台静默检测 — 业务类型对用户透明
4. 仪表盘真实联动 — 基于实际对话数据
5. 设置极简化 — 只保留用户关心的选项
"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="一人公司助手",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.messages = []
    st.session_state.scenario_count = 0
    st.session_state.detected_type = None
    st.session_state.detected_name = None
    st.session_state.flywheel_scores = {
        "内容质量": 0, "受众增长": 0, "变现能力": 0,
        "跨域推广": 0, "生态协同": 0,
    }
    st.session_state.flywheel_level = 1
    st.session_state.achievements = []

PERSONA_MAP = {
    "content_creator": ("✍️ 内容小助理", "轻松活泼"),
    "digital_product": ("💰 产品顾问", "专业亲切"),
    "ai_tool_builder": ("🤖 技术合伙人", "技术专业"),
    "consultant": ("💼 咨询顾问", "正式严谨"),
    "ecommerce": ("🛒 电商小管家", "干练务实"),
    "creative_work": ("🎨 创意搭子", "文艺优雅"),
}

SCENARIOS = [
    {"id": "content_calendar", "icon": "📅", "title": "内容日历规划",
     "desc": "帮你规划下周的选题和发布节奏", "type": "content_creator"},
    {"id": "digital_product_launch", "icon": "🚀", "title": "数字产品发布",
     "desc": "从定价到上线的完整方案", "type": "digital_product"},
    {"id": "feedback_analysis", "icon": "📊", "title": "用户反馈分析",
     "desc": "从用户声音中提炼行动项", "type": "ai_tool_builder"},
    {"id": "consulting_proposal", "icon": "📋", "title": "咨询提案撰写",
     "desc": "专业提案框架+行业洞察", "type": "consultant"},
    {"id": "ecommerce_ops", "icon": "🛍️", "title": "电商运营优化",
     "desc": "GMV提升策略与执行清单", "type": "ecommerce"},
    {"id": "project_deliverable", "icon": "📦", "title": "项目交付物整理",
     "desc": "交付物清单+质量检查", "type": "creative_work"},
    {"id": "launch_product", "icon": "🎯", "title": "新产品发布",
     "desc": "发布计划+推广策略", "type": "content_creator"},
    {"id": "write_report", "icon": "📝", "title": "报告撰写",
     "desc": "结构化报告+数据支撑", "type": "consultant"},
    {"id": "organize_meeting", "icon": "🤝", "title": "会议组织",
     "desc": "议程+纪要+跟进清单", "type": "consultant"},
]

with st.sidebar:
    st.markdown("### 🚀 一人公司助手")

    page = st.radio(
        "",
        ["💬 对话", "📊 成长", "⚙️ 设置"],
        label_visibility="collapsed",
    )

    if st.session_state.detected_type:
        persona_info = PERSONA_MAP.get(st.session_state.detected_type, ("智能助手", "专业"))
        st.divider()
        st.markdown(f"**当前人格**")
        st.markdown(f"{persona_info[0]}")
        st.caption(f"风格：{persona_info[1]}")

    st.divider()
    st.caption("OPC-Agents v3.0")


# ═══════════════════════════════════════════
# 页面1: 对话 — 首屏即对话，场景快捷入口
# ═══════════════════════════════════════════
if page == "💬 对话":
    if len(st.session_state.messages) == 0:
        st.markdown("## 👋 你好，一人公司创业者！")
        st.markdown(
            "我是你的**智能工作助手**，可以帮你规划内容、分析数据、撰写方案、优化运营。"
            "直接告诉我你在做什么，或者从下方选择一个场景开始 👇"
        )

        st.markdown("### 🎯 我能帮你做什么？")
        cols = st.columns(3)
        for i, sc in enumerate(SCENARIOS):
            with cols[i % 3]:
                if st.button(
                    f"{sc['icon']} {sc['title']}\n{sc['desc']}",
                    key=f"sc_{sc['id']}",
                    use_container_width=True,
                ):
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"帮我执行「{sc['title']}」场景",
                    })
                    st.rerun()

        st.divider()
        st.markdown(
            "<div style='text-align:center; color:#888; font-size:0.9em;'>"
            "💡 也可以直接在下方输入你的问题，我会自动识别你的业务类型"
            "</div>",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("告诉我你在做什么，或者需要什么帮助..."):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2
                    from opc_manager.persona_manager import PersonaManager
                    from opc_manager.flywheel_tracker import FlywheelTracker

                    detector = BusinessTypeDetectorV2()
                    result = detector.detect(prompt)

                    if not st.session_state.detected_type:
                        st.session_state.detected_type = result.business_type.value
                        persona_info = PERSONA_MAP.get(
                            result.business_type.value, ("智能助手", "专业")
                        )
                        st.session_state.detected_name = persona_info[0]

                    pm = PersonaManager()
                    persona = pm.get_persona(result.business_type.value)

                    tracker = FlywheelTracker()
                    tracker.record_scenario_completion(
                        "web_user", "chat_interaction", result.business_type
                    )
                    st.session_state.scenario_count += 1

                    scores = st.session_state.flywheel_scores
                    dim_map = {
                        "content_creator": "内容质量",
                        "digital_product": "变现能力",
                        "ai_tool_builder": "跨域推广",
                        "consultant": "受众增长",
                        "ecommerce": "变现能力",
                        "creative_work": "内容质量",
                    }
                    dim_key = dim_map.get(result.business_type.value, "内容质量")
                    scores[dim_key] = min(100, scores.get(dim_key, 0) + 8)
                    avg = sum(scores.values()) / len(scores) if scores else 0
                    st.session_state.flywheel_level = (
                        3 if avg >= 60 else (2 if avg >= 35 else 1)
                    )

                    greeting = ""
                    if st.session_state.scenario_count == 1:
                        greeting = f"\n\n🎉 **已为你激活专属人格：{persona.display_name}**\n"

                    scenario_hints = [
                        s for s in SCENARIOS
                        if s["type"] == result.business_type.value
                    ][:2]
                    hint_text = ""
                    if scenario_hints:
                        hints = "、".join(
                            [f"「{s['title']}」" for s in scenario_hints]
                        )
                        hint_text = f"\n\n💡 **推荐场景**：{hints}"

                    response = (
                        f"{greeting}"
                        f"你好！我是**{persona.display_name}**，"
                        f"专注于{result.business_type.display_name}领域。\n\n"
                        f"关于「{prompt[:40]}{'...' if len(prompt) > 40 else ''}」，"
                        f"我来帮你分析：\n\n"
                        f"📌 **核心要点**\n"
                        f"基于你的需求，我建议从以下角度入手：\n"
                        f"1. 明确当前阶段的目标和优先级\n"
                        f"2. 制定可执行的行动清单\n"
                        f"3. 设定可衡量的验收标准\n"
                        f"{hint_text}\n\n"
                        f"你可以继续告诉我更多细节，我会给出更具体的方案！"
                    )

                    st.markdown(response)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                    })

                except Exception as e:
                    error_msg = f"抱歉，处理时遇到了问题。请换个方式描述你的需求。"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })


# ═══════════════════════════════════════════
# 页面2: 成长 — 真实联动的飞轮仪表盘
# ═══════════════════════════════════════════
elif page == "📊 成长":
    st.markdown("## 📊 我的成长飞轮")

    scores = st.session_state.flywheel_scores
    level = st.session_state.flywheel_level
    count = st.session_state.scenario_count

    level_info = {
        1: ("🌱 探索者", "专注单一业务类型，持续深耕", "#4CAF50"),
        2: ("🔗 连接者", "双类型组合，产生协同效应", "#FF9800"),
        3: ("🌍 生态构建者", "全生态系统，商业闭环运转", "#E91E63"),
    }
    lv_name, lv_desc, lv_color = level_info.get(level, level_info[1])

    col_level, col_count = st.columns([2, 1])
    with col_level:
        st.markdown(
            f"<div style='padding:20px; border-radius:12px; "
            f"background:linear-gradient(135deg, {lv_color}22, {lv_color}08); "
            f"border:2px solid {lv_color}66;'>"
            f"<h2 style='color:{lv_color}; margin:0;'>{lv_name}</h2>"
            f"<p style='color:#666; margin:4px 0 0 0;'>{lv_desc}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with col_count:
        st.metric("互动次数", count)
        if count > 0:
            st.metric("当前等级", f"Lv.{level}")

    st.divider()

    st.markdown("### 五维健康度")
    dims = ["内容质量", "受众增长", "变现能力", "跨域推广", "生态协同"]
    dim_icons = ["📝", "👥", "💰", "🔗", "🌍"]

    for icon, dim in zip(dim_icons, dims):
        score = scores.get(dim, 0)
        col_label, col_bar, col_score = st.columns([1.5, 6, 1])
        with col_label:
            st.markdown(f"{icon} **{dim}**")
        with col_bar:
            st.progress(score / 100)
        with col_score:
            color = "#4CAF50" if score >= 60 else ("#FF9800" if score >= 30 else "#ccc")
            st.markdown(
                f"<span style='color:{color}; font-weight:bold; font-size:1.1em;'>"
                f"{score}</span>",
                unsafe_allow_html=True,
            )

    if count == 0:
        st.info("💡 开始与助手对话，你的成长数据会自动记录在这里！")
    elif level < 3:
        next_level = level + 1
        next_info = level_info.get(next_level, level_info[3])
        st.success(
            f"🎯 **升级提示**：继续互动可以提升各维度分数，"
            f"向 **{next_info[0]}** 进发！"
        )

    if st.session_state.achievements:
        st.divider()
        st.markdown("### 🏆 成就")
        for ach in st.session_state.achievements:
            st.markdown(f"- {ach}")


# ═══════════════════════════════════════════
# 页面3: 设置 — 极简化，只留用户关心的
# ═══════════════════════════════════════════
elif page == "⚙️ 设置":
    st.markdown("## ⚙️ 设置")

    st.markdown("### 🤖 AI 助手")
    st.markdown("选择你偏好的AI风格：")
    style = st.selectbox(
        "回复风格",
        ["自动识别", "轻松活泼", "专业严谨", "简洁高效"],
        index=0,
    )

    st.markdown("### 🔔 通知")
    show_tips = st.checkbox("显示场景推荐提示", value=True)
    show_growth = st.checkbox("对话中显示成长进度", value=True)

    st.markdown("### 📊 数据")
    if st.button("重置所有对话和成长数据"):
        st.session_state.messages = []
        st.session_state.scenario_count = 0
        st.session_state.detected_type = None
        st.session_state.detected_name = None
        st.session_state.flywheel_scores = {
            "内容质量": 0, "受众增长": 0, "变现能力": 0,
            "跨域推广": 0, "生态协同": 0,
        }
        st.session_state.flywheel_level = 1
        st.session_state.achievements = []
        st.success("✅ 已重置所有数据")
        st.rerun()

    with st.expander("🔧 高级设置（开发者）"):
        provider = st.selectbox("LLM 后端", ["mock（无需API Key）", "openai", "ollama"], index=0)
        if "openai" in provider:
            st.text_input("API Key", type="password", key="api_key_input")
        st.text_input("模型", value="gpt-4o-mini", key="model_input")

    st.divider()
    st.caption("OPC-Agents v3.0 | 一人公司智能助手")
