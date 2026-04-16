"""Streamlit 前端 - OPC-Agents v3.2 (成果物交付版)

核心改变：从"屏幕上显示文字"变为"交付可下载的文件"
- 每次任务执行都会生成真实的文件（保存在 deliverables/ 目录）
- 提供下载按钮，客户可以直接下载成果物
- 支持历史交付物查看和管理
- 不是聊天记录，是真正的文件资产
"""
import streamlit as st
import sys
import os
import traceback
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DELIVERABLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deliverables")
os.makedirs(DELIVERABLES_DIR, exist_ok=True)

st.set_page_config(
    page_title="一人公司助手",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.messages = []
    st.session_state.deliverables = []
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


def generate_filename(prompt: str, task_type: str) -> str:
    safe_name = prompt[:30].replace(" ", "_").replace("/", "-").replace("\\", "-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{task_type}_{safe_name}.md"


def save_deliverable(content: str, prompt: str, task_type: str, meta: dict = None) -> str:
    filename = generate_filename(prompt, task_type)
    filepath = os.path.join(DELIVERABLES_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    deliverable_record = {
        "filename": filename,
        "filepath": filepath,
        "prompt": prompt[:50],
        "task_type": task_type,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size_kb": round(len(content.encode('utf-8')) / 1024, 1),
        "meta": meta or {},
    }
    st.session_state.deliverables.insert(0, deliverable_record)

    print(f"[frontend] 成果物已保存: {filepath} ({deliverable_record['size_kb']}KB)")
    return filepath


def execute_task_and_deliver(prompt):
    """执行任务并生成交付物文件"""
    try:
        print(f"[frontend] 开始执行任务: {prompt[:50]}")
        from opc_manager.task_engine_v3 import TaskEngineV3, TaskType
        engine = TaskEngineV3()
        print(f"[frontend] TaskEngineV3 初始化完成")
        result = engine.execute(prompt)
        print(f"[frontend] 任务执行完成: success={result.success}, content_len={len(result.content) if result.content else 0}")

        if not result.success:
            print(f"[frontend] 任务标记为失败: {result.error}")
            return None, False, None, None

        if not result.content:
            print(f"[frontend] 内容为空!")
            return None, False, None, None

        meta_lines = []
        if result.execution_time_ms:
            meta_lines.append(f"⏱️ 执行耗时: {result.execution_time_ms:.0f}ms")
        type_labels = {
            TaskType.INFO_COLLECTION: "🔍 信息收集",
            TaskType.CONTENT_GENERATION: "✍️ 内容生成",
            TaskType.DATA_ANALYSIS: "📊 数据分析",
            TaskType.TASK_EXECUTION: "📋 任务执行",
            TaskType.SCENARIO_BASED: "🎯 场景工作流",
            TaskType.GENERAL_CHAT: "💬 智能对话",
        }
        task_type_label = type_labels.get(result.task_type, "通用")
        meta_lines.append(f"📌 任务类型: {task_type_label}")
        if result.sources:
            meta_lines.append(f"🔗 信息来源: {len(result.sources)} 条")
        if result.deliverable_format:
            meta_lines.append(f"📦 格式: {result.deliverable_format}")

        meta_str = "\n".join(meta_lines)

        content_with_meta = f"{result.content}\n\n---\n*{meta_str}*"

        print(f"[frontend] 准备保存文件...")
        filepath = save_deliverable(
            content=content_with_meta,
            prompt=prompt,
            task_type=result.task_type.value,
            meta={
                "sources_count": len(result.sources) if result.sources else 0,
                "format": result.deliverable_format,
                "execution_time_ms": result.execution_time_ms,
                "success": result.success,
            }
        )
        print(f"[frontend] 文件已保存: {filepath}")

        return content_with_meta, result.success, filepath, result.task_type.value

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[frontend] execute_task_and_deliver error: {e}\n{tb}")
        return None, False, None, None


with st.sidebar:
    st.markdown("### 🚀 一人公司助手")
    page = st.radio("", ["💬 对话", "📁 成果物", "📊 成长", "⚙️ 设置"], label_visibility="collapsed")

    if st.session_state.detected_type:
        pinfo = PERSONA_MAP.get(st.session_state.detected_type, ("助手", ""))
        st.divider()
        st.markdown(f"**当前人格**\n{pinfo[0]}")
        st.caption(f"风格：{pinfo[1]}")

    if st.session_state.deliverables:
        st.divider()
        st.markdown(f"**📦 已生成 {len(st.session_state.deliverables)} 个成果物**")

    st.divider()
    st.caption("OPC-Agents v3.2")


if page == "💬 对话":
    if len(st.session_state.messages) == 0:
        st.markdown("## 👋 你好，一人公司创业者！")
        st.markdown(
            "我是你的**任务执行与成果交付助手**。"
            "**告诉我你要什么结果，我直接做完并交付文件给你** — 可下载、可保存、可复用。"
        )
        st.markdown("### 🎯 我能直接帮你完成并交付：")
        cols = st.columns(3)
        for i, sc in enumerate(SCENARIOS):
            with cols[i % 3]:
                if st.button(f"{sc['icon']} {sc['title']}\n_{sc['desc']}", key=f"sc_{sc['id']}",
                           use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": f"帮我执行「{sc['title']}」场景"})
                    st.rerun()

        st.divider()
        st.markdown("<div style='text-align:center; color:#888;'>"
                    "💡 输入需求 → 执行任务 → 生成文件 → 立即下载</div>", unsafe_allow_html=True)

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("deliverable_path") and os.path.exists(msg["deliverable_path"]):
                col_dl, col_info = st.columns([1, 3])
                with col_dl:
                    with open(msg["deliverable_path"], 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    st.download_button(
                        label="📥 下载文件",
                        data=file_content,
                        file_name=os.path.basename(msg["deliverable_path"]),
                        mime="text/markdown",
                        key=f"dl_{msg.get('deliverable_id', id(msg))}",
                        use_container_width=True,
                    )
                with col_info:
                    size_kb = round(len(file_content.encode('utf-8')) / 1024, 1)
                    st.caption(f"📄 {os.path.basename(msg['deliverable_path'])} ({size_kb}KB)")

    if prompt := st.chat_input("告诉我你需要什么结果，我直接做完并交付文件..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("⚡ 正在执行任务并生成交付物..."):
                try:
                    type_val, conf, method = safe_detect(prompt)
                    is_first = not st.session_state.detected_type
                    if is_first or not st.session_state.detected_type:
                        st.session_state.detected_type = type_val
                        pinfo = PERSONA_MAP.get(type_val, ("智能助手", ""))
                        st.session_state.detected_name = pinfo[0]

                    safe_track_flywheel(type_val)

                    response, success, filepath, task_type_val = execute_task_and_deliver(prompt)

                    if response and filepath:
                        st.markdown(response)

                        col_dl, col_info = st.columns([1, 3])
                        with col_dl:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            st.download_button(
                                label="📥 下载成果物",
                                data=file_content,
                                file_name=os.path.basename(filepath),
                                mime="text/markdown",
                                key=f"dl_main_{int(time.time()*1000)}",
                                use_container_width=True,
                                type="primary",
                            )
                        with col_info:
                            size_kb = round(len(file_content.encode('utf-8')) / 1024, 1)
                            st.success(f"✅ 已生成: {os.path.basename(filepath)} ({size_kb}KB)")

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response,
                            "deliverable_path": filepath,
                            "deliverable_id": f"{int(time.time()*1000)}",
                        })
                    else:
                        raise RuntimeError("任务执行未返回结果")

                except Exception as e:
                    tb = traceback.format_exc()
                    print(f"[frontend] FATAL: {tb}")

                    fallback = (
                        f"⚠️ 任务执行遇到问题\n\n"
                        f"关于「**{prompt[:40]}{'...' if len(prompt) > 40 else ''}**」\n\n"
                        f"*错误信息*: `{str(e)}`\n\n"
                        f"**技术详情**:\n```\n{tb[:1000]}\n```\n\n"
                        f"请稍后重试或换个方式描述需求。"
                    )
                    st.markdown(fallback)
                    st.session_state.messages.append({"role": "assistant", "content": fallback})


elif page == "📁 成果物":
    st.markdown("## 📁 我的成果物")

    if not st.session_state.deliverables:
        st.info("💡 还没有生成任何成果物。去「对话」页面执行一个任务吧！")
    else:
        for i, d in enumerate(st.session_state.deliverables):
            with st.expander(f"📄 {d['filename']}", expanded=(i == 0)):
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.markdown(f"**任务**: `{d['prompt']}`")
                    st.markdown(f"**类型**: {d['task_type']}")
                    st.markdown(f"**时间**: {d['created_at']}")
                with col2:
                    st.metric("大小", f"{d['size_kb']} KB")
                with col3:
                    if os.path.exists(d['filepath']):
                        with open(d['filepath'], 'r', encoding='utf-8') as f:
                            content = f.read()
                        st.download_button(
                            "📥 下载",
                            data=content,
                            file_name=d['filename'],
                            mime="text/markdown",
                            key=f"dl_lib_{i}",
                            use_container_width=True,
                        )

                with st.container():
                    st.markdown("**预览（前500字）**:")
                    if os.path.exists(d['filepath']):
                        with open(d['filepath'], 'r', encoding='utf-8') as f:
                            preview = f.read()[:500]
                        st.code(preview, language="markdown")


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
    st.markdown("### 📦 成果物设置")
    st.text_input("成果物保存路径", value=DELIVERABLES_DIR, disabled=True)
    st.caption("所有生成的文件都保存在此目录下")
    st.markdown("### 🔔 通知")
    st.checkbox("显示场景推荐提示", value=True)
    st.checkbox("对话中显示成长进度", value=True)
    st.markdown("### 📊 数据")
    if st.button("重置所有数据"):
        for key in list(st.session_state.keys()):
            if key != "initialized":
                del st.session_state[key]
        st.session_state.messages = []
        st.session_state.deliverables = []
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

    existing_files = [f for f in os.listdir(DELIVERABLES_DIR) if f.endswith('.md')] if os.path.exists(DELIVERABLES_DIR) else []
    if existing_files:
        st.markdown(f"### 📂 成果物目录中的文件 ({len(existing_files)} 个)")
        for f in sorted(existing_files)[-5:]:
            fp = os.path.join(DELIVERABLES_DIR, f)
            size = round(os.path.getsize(fp) / 1024, 1)
            st.caption(f"📄 {f} ({size}KB)")

    st.caption("OPC-Agents v3.2 | 成果物交付版")
