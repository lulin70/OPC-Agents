"""Streamlit 前端 - OPC-Agents v3.0"""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="OPC-Agents 一人公司助手",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚀 OPC-Agents 一人公司智能助手 v3.0")

PAGES = {
    "💬 对话助手": "chat",
    "📊 飞轮仪表盘": "dashboard",
    "⚙️ 设置": "settings",
}

selection = st.sidebar.radio("导航", list(PAGES.keys()))

if selection == "💬 对话助手":
    st.header("💬 智能对话助手")
    st.markdown("""
    **选择你的业务类型**，开始与专属AI助手对话：
    """)
    
    business_types = [
        ("✍️ 内容创作者", "content_creator", "写文章、拍视频、做自媒体"),
        ("💰 数字产品开发者", "digital_product", "卖课程、电子书、模板"),
        ("🤖 AI工具开发者", "ai_tool_builder", "做SaaS、API、插件"),
        ("💼 咨询顾问", "consultant", "企业培训、1v1咨询"),
        ("🛒 电商运营者", "ecommerce", "卖实物商品、闲鱼、抖音小店"),
        ("🎨 创意工作者", "creative_work", "设计、摄影、翻译"),
    ]
    
    cols = st.columns(3)
    for i, (icon_name, btype, desc) in enumerate(business_types):
        with cols[i % 3]:
            if st.button(f"{icon_name}\n{desc}", key=f"btn_{btype}", use_container_width=True):
                st.session_state["selected_type"] = btype
                st.session_state["selected_name"] = icon_name
                st.rerun()

    if "selected_type" in st.session_state:
        st.success(f"已选择: {st.session_state.get('selected_name')}")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("输入你的问题或需求..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                try:
                    from opc_manager.business_type_detector_v2 import BusinessTypeDetectorV2
                    detector = BusinessTypeDetectorV2()
                    result = detector.detect(prompt)
                    
                    from opc_manager.persona_manager import PersonaManager
                    pm = PersonaManager()
                    persona = pm.get_persona(result.business_type.value)
                    
                    response_text = f"""**[{persona.display_name}]**

你好！我理解你正在：{prompt[:50]}...

📌 **检测结果**
- 业务类型：**{result.business_type.display_name}**
- 置信度：**{result.confidence:.0%}**
- 检测方式：{result.method}

🎯 **建议下一步**
让我帮你规划具体的行动方案。你可以告诉我更多细节，我会根据你的业务类型提供个性化建议。

> 💡 *提示：飞轮追踪器会记录你的每次互动，帮助你看到成长轨迹！*
"""
                    
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                
                except Exception as e:
                    error_msg = f"抱歉，处理请求时出错：{str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

elif selection == "📊 飞轮仪表盘":
    st.header("📊 飞轮成长仪表盘")
    st.markdown("""
    可视化你的**混合生态飞轮**状态和成长轨迹。
    """)
    
    user_id = st.text_input("用户ID（用于加载你的数据）", value="demo_user_v3")
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("当前等级")
        
        level_data = {
            1: {"name": "Lv.1 探索者", "color": "#4CAF50", "desc": "单一业务类型 - 专注深耕"},
            2: {"name": "Lv.2 连接者", "color": "#FF9800", "desc": "双类型组合 - 协同效应"},
            3: {"name": "Lv.3 生态构建者", "color": "#F44336", "desc": "全生态系统 - 商业闭环"},
        }
        
        for lv, info in level_data.items():
            st.markdown(f"""
            <div style="padding:10px; border-left:4px solid {info['color']}; margin:5px 0;">
                <strong>{info['name']}</strong><br/>
                <small>{info['desc']}</small>
            </div>
            """, unsafe_allow_html=True)
    
    with col_right:
        st.subheader("五维健康度")
        
        dimensions = ["内容质量", "受众增长", "变现能力", "跨域推广", "生态协同"]
        scores = [65, 45, 30, 20, 15]
        colors = ["#4CAF50", "#8BC34A", "#FFC107", "#FF9800", "#F44336"]
        
        for dim, score, color in zip(dimensions, scores, colors):
            st.progress(score / 100, text=f"{dim}: {score}分")

elif selection == "⚙️ 设置":
    st.header("⚙️ 系统设置")
    
    st.subheader("LLM 配置")
    provider = st.selectbox("LLM 提供商", ["mock", "openai", "ollama"], index=0)
    model = st.text_input("模型名称", value="gpt-4o-mini")
    
    if provider == "openai":
        api_key = st.text_input("API Key", type="password")
        base_url = st.text_input("Base URL", value="https://api.openai.com/v1")
    
    st.subheader("数据库")
    db_url = st.text_input("数据库连接", value="sqlite:///./opc_agents_v3.db")
    
    if st.button("保存设置"):
        st.success("设置已保存！（实际实现中会写入 .env 文件）")
    
    st.divider()
    st.caption("OPC-Agents v3.0 | Phase 3 MVP | Powered by FastAPI + Streamlit")
