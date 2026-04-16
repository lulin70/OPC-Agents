"""Streamlit 前端 - OPC-Agents v3.0 (用户中心版 - 稳定版)

设计原则：
1. 首屏即对话 — 不强制选择类型，后台自动识别
2. 场景快捷入口 — "我能帮你做什么"而非"请选类型"
3. 后台静默检测 — 业务类型对用户透明
4. 仪表盘真实联动 — 基于实际对话数据
5. 设置极简化 — 只保留用户关心的选项
6. 零崩溃保证 — 任何异常都有优雅降级
"""
import streamlit as st
import sys
import os
import traceback

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

TYPE_DISPLAY = {
    "content_creator": "内容创作者",
    "digital_product": "数字产品开发者",
    "ai_tool_builder": "AI工具开发者",
    "consultant": "咨询顾问",
    "ecommerce": "电商运营者",
    "creative_work": "创意工作者",
}

SCENARIOS = [
    {"id": "content_calendar", "icon": "📅", "title": "内容日历规划",
     "desc": "帮你规划下周的选题和发布节奏"},
    {"id": "digital_product_launch", "icon": "🚀", "title": "数字产品发布",
     "desc": "从定价到上线的完整方案"},
    {"id": "feedback_analysis", "icon": "📊", "title": "用户反馈分析",
     "desc": "从用户声音中提炼行动项"},
    {"id": "consulting_proposal", "icon": "📋", "title": "咨询提案撰写",
     "desc": "专业提案框架+行业洞察"},
    {"id": "ecommerce_ops", "icon": "🛍️", "title": "电商运营优化",
     "desc": "GMV提升策略与执行清单"},
    {"id": "project_deliverable", "icon": "📦", "title": "项目交付物整理",
     "desc": "交付物清单+质量检查"},
    {"id": "launch_product", "icon": "🎯", "title": "新产品发布",
     "desc": "发布计划+推广策略"},
    {"id": "write_report", "icon": "📝", "title": "报告撰写",
     "desc": "结构化报告+数据支撑"},
    {"id": "organize_meeting", "icon": "🤝", "title": "会议组织",
     "desc": "议程+纪要+跟进清单"},
]


def safe_detect(prompt_text):
    """安全检测业务类型，任何异常都返回默认值"""
    try:
        from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2
        detector = BusinessTypeDetectorV2()
        result = detector.detect(prompt_text)
        if result and result.business_type:
            return result.business_type.value, result.confidence, result.method
        return "content_creator", 0.5, "default"
    except Exception as e:
        print(f"[frontend] detect error: {e}")
        return "content_creator", 0.5, "fallback"


def safe_get_persona(type_value):
    """安全获取人格配置"""
    try:
        from opc_manager.persona_manager import PersonaManager
        pm = PersonaManager()
        persona = pm.get_persona(business_type=__import__("opc_manager.business_types", fromlist=["BusinessType"]).BusinessType(type_value))
        if persona:
            return persona.display_name, persona.style_overrides.get("tone", "专业温暖")
        return "智能助手", "专业温暖"
    except Exception as e:
        print(f"[frontend] persona error: {e}")
        name = PERSONA_MAP.get(type_value, ("智能助手", "专业"))[0]
        return name, "专业"


def safe_track_flywheel(type_value):
    """安全记录飞轮数据"""
    try:
        from opc_manager.flywheel_tracker import FlywheelTracker
        from opc_manager.business_types import BusinessType
        tracker = FlywheelTracker()
        bt = BusinessType(type_value)
        tracker.record_scenario_completion("web_user", "chat_interaction", bt)
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
        dim_key = dim_map.get(type_value, "内容质量")
        scores[dim_key] = min(100, scores.get(dim_key, 0) + 8)

        avg = sum(scores.values()) / len(scores) if scores else 0
        st.session_state.flywheel_level = 3 if avg >= 60 else (2 if avg >= 35 else 1)
        return True
    except Exception as e:
        print(f"[frontend] flywheel error: {e}")
        st.session_state.scenario_count += 1
        return False


def build_response(prompt, type_value, persona_name, is_first_chat):
    """构建回复内容"""
    type_display = TYPE_DISPLAY.get(type_value, "创业者")

    greeting = ""
    if is_first_chat:
        greeting = f"\n\n🎉 **已为你激活专属助手：{persona_name}**\n"

    scenario_hints = [s for s in SCENARIOS if s.get("type") == type_value][:2]
    hint_text = ""
    if scenario_hints:
        hints = "、".join([f"「{s['title']}」" for s in scenario_hints])
        hint_text = f"\n\n💡 **推荐场景**：{hints}"

    return (
        f"{greeting}"
        f"你好！我是**{persona_name}**，专注于**{type_display}**领域。\n\n"
        f"关于「{prompt[:50]}{'...' if len(prompt) > 50 else ''}」，"
        f"我来帮你分析：\n\n"
        f"📌 **核心建议**\n"
        f"1. 明确当前阶段的目标和优先级\n"
        f"2. 制定可执行的行动清单（3-5项）\n"
        f"3. 设定可衡量的验收标准\n"
        f"{hint_text}\n\n"
        f"你可以继续告诉我更多细节，我会给出更具体的方案！"
    )


with st.sidebar:
    st.markdown("### 🚀 一人公司助手")
    page = st.radio("", ["💬 对话", "📊 成长", "⚙️ 设置"], label_visibility="collapsed")

    if st.session_state.detected_type:
        pinfo = PERSONA_MAP.get(st.session_state.detected_type, ("助手", ""))
        st.divider()
        st.markdown(f"**当前人格**\n{pinfo[0]}")
        st.caption(f"风格：{pinfo[1]}")
    st.divider()
    st.caption("OPC-Agents v3.0")


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
                if st.button(f"{sc['icon']} {sc['title']}\n_{sc['desc']}", key=f"sc_{sc['id']}",
                           use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": f"帮我执行「{sc['title']}」场景"})
                    st.rerun()

        st.divider()
        st.markdown("<div style='text-align:center; color:#888;'>"
                    "💡 直接输入问题也行，我会自动识别你的业务类型</div>", unsafe_allow_html=True)

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
                    type_val, conf, method = safe_detect(prompt)
                    is_first = not st.session_state.detected_type
                    if is_first or not st.session_state.detected_type:
                        st.session_state.detected_type = type_val
                        pinfo = PERSONA_MAP.get(type_val, ("智能助手", ""))
                        st.session_state.detected_name = pinfo[0]

                    persona_name, tone = safe_get_persona(type_val)
                    safe_track_flywheel(type_val)

                    response = build_response(prompt, type_val, persona_name, is_first)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"[frontend] FATAL: {tb}")

                    fallback = (
                        f"你好！我是你的一人公司智能助手 🚀\n\n"
                        f"关于「**{prompt[:40]}{'...' if len(prompt) > 40 else ''}**」，"
                        f"让我来帮你梳理一下思路：\n\n"
                        f"📌 **建议下一步**\n"
                        f"1. 先明确你的核心目标是什么\n"
                        f"2. 列出你目前已有的资源和条件\n"
                        f"3. 找出最大的瓶颈或障碍\n\n"
                        f"你可以把这些信息告诉我，我会给出更精准的建议！"
                    )
                    st.markdown(fallback)
                    st.session_state.messages.append({"role": "assistant", "content": fallback})


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
            f"<div style='padding:20px;border-radius:12px;"
            f"background:linear-gradient(135deg,{lv_color}22,{lv_color}08);"
            f"border:2px solid {lv_color}66;'>"
            f"<h2 style='color:{lv_color};margin:0;'>{lv_name}</h2>"
            f"<p style='color:#666;margin:4px 0 0 0;'>{lv_desc}</p></div>",
            unsafe_allow_html=True,
        )
    with col_count:
        st.metric("互动次数", count)
        if count > 0:
            st.metric("当前等级", f"Lv.{level}")

    st.divider()
    st.markdown("### 五维健康度")
    dims = [("📝", "内容质量"), ("👥", "受众增长"), ("💰", "变现能力"),
             ("🔗", "跨域推广"), ("🌍", "生态协同")]
    for icon, dim in dims:
        score = scores.get(dim, 0)
        c1, c2, c3 = st.columns([1.5, 6, 1])
        with c1:
            st.markdown(f"{icon} **{dim}**")
        with c2:
            st.progress(score / 100)
        with c3:
            color = "#4CAF50" if score >= 60 else ("#FF9800" if score >= 30 else "#ccc")
            st.markdown(f"<span style='color:{color};font-weight:bold;font-size:1.1em;'>{score}</span>",
                        unsafe_allow_html=True)

    if count == 0:
        st.info("💡 开始与助手对话，你的成长数据会自动记录在这里！")
    elif level < 3:
        ni = level_info.get(level + 1, level_info[1])
        st.success(f"🎯 继续互动可以升级到 **{ni[0]}**！")


elif page == "⚙️ 设置":
    st.markdown("## ⚙️ 设置")
    st.markdown("### 🤖 AI 助手")
    st.selectbox("回复风格", ["自动识别", "轻松活泼", "专业严谨", "简洁高效"], index=0)
    st.markdown("### 🔔 通知")
    st.checkbox("显示场景推荐提示", value=True)
    st.checkbox("对话中显示成长进度", value=True)
    st.markdown("### 📊 数据")
    if st.button("重置所有数据"):
        for key in list(st.session_state.keys()):
            if key != "initialized":
                del st.session_state[key]
        st.session_state.messages = []
        st.session_state.scenario_count = 0
        st.session_state.detected_type = None
        st.session_state.detected_name = None
        st.session_state.flywheel_scores = {d: 0 for d in ["内容质量", "受众增长", "变现能力", "跨域推广", "生态协同"]}
        st.session_state.flywheel_level = 1
        st.session_state.achievements = []
        st.success("✅ 已重置")
        st.rerun()

    with st.expander("🔧 高级设置（开发者）"):
        st.selectbox("LLM 后端", ["mock（无需API Key）", "openai", "ollama"], index=0)
    st.divider()
    st.caption("OPC-Agents v3.0 | 一人公司智能助手")
