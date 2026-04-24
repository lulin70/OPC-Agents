"""Streamlit 前端 - OPC-Agents (成果物交付版)

=== 产品定位 ===
"告诉系统你要什么结果，它直接做完并交付文件给你"

=== 核心设计改变（从v3.0到v3.4）===
v3.0: "屏幕上显示文字" — AI助手聊天模式
v3.4: "交付可下载的文件" — 任务执行+成果物交付模式

每次任务执行都会：
1. 调用TaskEngineV3执行真实搜索和内容生成
2. 将结果保存为.md文件到deliverables/目录
3. 在界面上显示下载按钮
4. 用户可直接下载、保存、复用

=== 页面结构（4个Tab）===
1. 💬 对话: 主交互界面，输入需求→执行→下载
2. 📁 成果物: 历史文件库，预览+重新下载
3. 📊 成长: 五维飞轮仪表盘，等级系统
4. ⚙️ 设置: 风格/路径/数据重置/高级选项

=== 会话管理策略 ===
- 使用Streamlit session_state存储所有状态
- 刷新页面会丢失历史（已知限制，后续迭代DB持久化）
- 每次页面加载时初始化默认状态（if "initialized" not in st.session_state）

=== 错误处理策略 ===
- safe_detect/safe_get_persona/safe_track_flywheel: 三层防御包装器，
  确保后端模块异常不会导致前端崩溃
- execute_task_and_deliver: 顶层try-except，失败时返回友好错误提示
- 超时检测: 通过error_msg关键词匹配判断是否为网络超时，
  给出不同的降级提示和CLI备选方案

=== 版本历史 ===
v3.0: 初始Streamlit UI
v3.1: 增加成果物下载功能
v3.2: 增加成果物库页面
v3.3: st.spinner → st.status进度反馈，超时友好提示
v3.4: 代码走读注释完善
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
    """首次访问初始化所有session_state变量

    设计意图：Streamlit的session_state在页面刷新后会重置，
    此处用"initialized"标志位避免重复初始化覆盖已有数据。
    """
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
    from opc_manager.async_executor import AsyncTaskExecutor
    st.session_state.async_executor = AsyncTaskExecutor(max_concurrent=3, default_timeout=120)
    print("[frontend] AsyncTaskExecutor 初始化完成 (max_concurrent=3)")

    if os.path.exists(DELIVERABLES_DIR):
        disk_files = [f for f in os.listdir(DELIVERABLES_DIR) if f.endswith('.md')]
        existing_names = {d.get('filename', '') for d in st.session_state.deliverables}
        for f in sorted(disk_files, reverse=True):
            if f not in existing_names:
                fp = os.path.join(DELIVERABLES_DIR, f)
                size_kb = round(os.path.getsize(fp) / 1024, 1)
                parts = f.replace('.md', '').split('_', 2)
                st.session_state.deliverables.append({
                    'filename': f,
                    'filepath': fp,
                    'prompt': parts[2] if len(parts) > 2 else '历史任务',
                    'task_type': parts[1] if len(parts) > 1 else 'unknown',
                    'created_at': f'{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:8]}' if len(parts) > 0 and len(parts[0]) >= 8 else '',
                    'size_kb': size_kb,
                })
        if disk_files:
            print(f"[frontend] 从磁盘恢复了 {len(disk_files)} 个成果物记录")

PERSONA_MAP = {
    """业务类型 → (显示名称, 风格描述) 映射表
    
    用于侧边栏展示当前识别到的用户业务类型对应的人格名称。
    与PersonaManager.get_persona()的结果配合使用。
    """
    "content_creator": ("✍️ 内容小助理", "轻松活泼"),
    "digital_product": ("💰 产品顾问", "专业亲切"),
    "ai_tool_builder": ("🤖 技术合伙人", "技术专业"),
    "consultant": ("💼 咨询顾问", "正式严谨"),
    "ecommerce": ("🛒 电商小管家", "干练务实"),
    "creative_work": ("🎨 创意搭子", "文艺优雅"),
}

TYPE_DISPLAY = {
    """业务类型中文显示名映射 — 用于成果物页面的类型标签展示"""
    "content_creator": "内容创作者",
    "digital_product": "数字产品开发者",
    "ai_tool_builder": "AI工具开发者",
    "consultant": "咨询顾问",
    "ecommerce": "电商运营者",
    "creative_work": "创意工作者",
}

# 9个预设场景快捷按钮配置
# 每个场景点击后会在对话中插入对应的自然语言指令，
# 由TaskEngineV3的IntentClassifier识别为SCENARIO_BASED类型，
# 再由ScenarioEngineV2编排多步骤工作流执行。
# 扩展方式：在此列表中添加新条目即可自动渲染按钮。
# 场景的具体工作流定义在scenario_engine_v2.py中。

SCENARIOS_CORE = [
    {"id": "content_creation", "icon": "✍️", "title": "内容创作",
     "desc": "文章/报告/日历规划", "coverage": ["内容日历规划", "报告撰写"]},
    {"id": "product_launch", "icon": "🚀", "title": "产品发布",
     "desc": "定价/上线/推广方案", "coverage": ["数字产品发布", "新产品发布"]},
    {"id": "data_analysis", "icon": "📊", "title": "数据分析",
     "desc": "反馈分析/运营优化", "coverage": ["用户反馈分析", "电商运营优化"]},
    {"id": "project_mgmt", "icon": "📋", "title": "项目管理",
     "desc": "提案/交付/会议组织", "coverage": ["咨询提案撰写", "项目交付物整理", "会议组织"]},
]

SCENARIOS_MORE = [
    {"id": "content_calendar", "icon": "📅", "title": "内容日历规划",
     "desc": "帮你规划下周的选题和发布节奏"},
    {"id": "digital_product_launch", "icon": "🎯", "title": "数字产品发布",
     "desc": "从定价到上线的完整方案"},
    {"id": "feedback_analysis", "icon": "💬", "title": "用户反馈分析",
     "desc": "从用户声音中提炼行动项"},
    {"id": "consulting_proposal", "icon": "📝", "title": "咨询提案撰写",
     "desc": "专业提案框架+行业洞察"},
    {"id": "ecommerce_ops", "icon": "🛒", "title": "电商运营优化",
     "desc": "GMV提升策略与执行清单"},
    {"id": "project_deliverable", "icon": "📦", "title": "项目交付物整理",
     "desc": "交付物清单+质量检查"},
    {"id": "write_report", "icon": "📄", "title": "报告撰写",
     "desc": "结构化报告+数据支撑"},
    {"id": "organize_meeting", "icon": "🤝", "title": "会议组织",
     "desc": "议程+纪要+跟进清单"},
]


def safe_detect(prompt_text):
    """安全包装的业务类型检测 — 防止后端异常导致前端崩溃
    
    设计意图：
    BusinessTypeDetectorV2.detect()可能因模型未初始化等原因抛出异常，
    如果直接调用会导致整个Streamlit回调崩溃（WebSocket断连）。
    此函数捕获所有异常并返回安全的默认值(content_creator)。
    
    Returns:
        (type_value, confidence, method): 业务类型枚举值/置信度/检测方法名
    """
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
    """安全包装的人格信息获取 — 防止get_persona返回None导致AttributeError
    
    v3.0历史问题：当confidence较低时get_persona()返回None，
    直接访问persona.display_name会导致AttributeError崩溃。
    此函数确保始终返回有效的(name, tone)元组。
    
    Fallback策略:
    1. 尝试从PersonaManager获取完整persona对象
    2. 失败则从PERSONA_MAP静态映射获取名称
    3. 最终fallback为"智能助手"
    """
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
    """安全包装的成长飞轮记录 — 记录用户互动并更新飞轮分数
    
    功能说明：
    - 每次用户输入后调用，记录到FlywheelTracker
    - 根据业务类型增加对应维度分数（每次+8分）
    - 根据平均分数计算飞轮等级（L1探索者/L2连接者/L3生态构建者）
    - 分数上限100，等级根据阈值35/60判定
    
    维度映射规则：
    - content_creator/creative_work → 内容质量
    - digital_product/ecommerce → 变现能力
    - ai_tool_builder → 跨域推广
    - consultant → 受众增长
    - 其他 → 默认内容质量
    """
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
    """生成唯一的成果物文件名
    
    格式: {YYYYMMDD_HHMMSS}_{task_type}_{prompt摘要30字符}.md
    
    安全措施：
    - prompt截取前30字符防止文件名过长
    - 替换空格/斜杠/反斜杠为下划线/横杠防止路径穿越
    - 使用时间戳保证唯一性（同一秒内多次请求仍可区分）
    """
    safe_name = prompt[:30].replace(" ", "_").replace("/", "-").replace("\\", "-")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{task_type}_{safe_name}.md"


def save_deliverable(content: str, prompt: str, task_type: str, meta: dict = None) -> str:
    """将生成的成果物内容写入文件系统并注册到session_state
    
    双写操作：
    1. 文件系统: 写入deliverables/{filename}.md（持久化，刷新不丢失）
    2. 内存: 插入st.session_state.deliverables列表头部（用于UI展示）
    
    元数据记录：
    - filename/filepath: 文件标识
    - prompt: 用户原始输入（截取50字符）
    - task_type: 任务类型（用于分类筛选）
    - created_at: 生成时间
    - size_kb: 文件大小（KB，用于展示）
    - meta: 扩展元数据（来源数量/格式/耗时等）
    
    Returns:
        filepath: 生成的文件的绝对路径
    """
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
    """执行任务的完整流水线 — 从用户输入到文件交付的核心函数
    
    执行流程：
    1. 创建TaskEngineV3实例（懒初始化WebSearch和ScenarioEngine）
    2. engine.execute(prompt) → 内部流程：校验→分类→搜索(缓存)→生成
    3. 构建元数据信息（耗时/类型/来源数/格式）
    4. 将元数据追加到内容末尾（作为文档尾部注释）
    5. save_deliverable() 写入文件系统 + 注册到session_state
    6. 返回四元组供前端展示
    
    Returns:
        (content_with_meta, success, filepath, task_type_value):
        - content_with_meta: 含元数据的完整Markdown文本
        - success: 是否成功
        - filepath: 文件绝对路径（用于下载按钮）
        - task_type_value: 任务类型字符串值
    
    错误处理：
    - TaskResult.success=False → 返回(None, False, None, None)
    - TaskResult.content为空 → 返回(None, False, None, None)
    - 任何Exception → 打印完整堆栈，返回(None, False, None, None)
    """
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


def _async_execute_task(prompt: str, cancel_event) -> dict:
    """异步执行包装函数 — 供AsyncTaskExecutor后台线程调用

    设计意图：
    将原有的execute_task_and_deliver()逻辑包装为返回字典的格式，
    使其兼容AsyncTaskExecutor._run_worker()的调用约定。

    Args:
        prompt: 用户输入文本
        cancel_event: threading.Event对象，用于响应取消请求

    Returns:
        dict: {
            'content': str or None,
            'success': bool,
            'filepath': str or None,
            'task_type': str or None,
            'error': str or None,
        }
    """
    try:
        print(f"[frontend-async] 开始后台执行: {prompt[:50]}")
        content, success, filepath, task_type = execute_task_and_deliver(prompt)
        print(f"[frontend-async] 执行完成: success={success}, has_content={bool(content)}")

        if content and success:
            return {
                'content': content,
                'success': True,
                'filepath': filepath,
                'task_type': task_type,
                'error': None,
            }
        else:
            return {
                'content': None,
                'success': False,
                'filepath': None,
                'task_type': None,
                'error': '任务执行未返回有效结果',
            }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[frontend-async] 执行异常: {e}\n{tb}")
        return {
            'content': None,
            'success': False,
            'filepath': None,
            'task_type': None,
            'error': str(e),
        }


with st.sidebar:
    """侧边栏 — 导航+状态展示"""
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
    from opc_manager.version import get_version
    st.caption(f"OPC-Agents v{get_version()}")


if page == "💬 对话":
    """主对话页面 — 用户交互的核心界面
    
    空状态: 展示欢迎语 + 9个场景快捷按钮
    有消息: 渲染历史消息（含下载按钮） + chat_input输入框
    输入后: 
      ① safe_detect → 意图识别（进度标签更新）
      ② 人格设置 + 飞轮追踪
      ③ execute_task_and_deliver → 核心执行
      ④ 成功: 显示结果 + 下载按钮 + 追加到消息历史
      ⑤ 失败: 区分超时/其他错误，给出不同提示
    """
    if len(st.session_state.messages) == 0:
        st.markdown("## 👋 你好，一人公司创业者！")
        st.markdown(
            "我是你的**任务执行与成果交付助手**。"
            "**告诉我你要什么结果，我直接做完并交付文件给你** — 可下载、可保存、可复用。"
        )
        st.markdown("### 🎯 我能直接帮你完成并交付：")

        st.markdown("**核心场景（最常用）**")
        core_cols = st.columns(2)
        for i, sc in enumerate(SCENARIOS_CORE):
            with core_cols[i % 2]:
                if st.button(
                    f"{sc['icon']} **{sc['title']}**\n\n📌 {sc['desc']}\n\n_涵盖: {', '.join(sc['coverage'])}_",
                    key=f"core_{sc['id']}",
                    use_container_width=True,
                ):
                    st.session_state.messages.append({
                        "role": "user",
                        "content": f"帮我执行「{sc['title']}」相关任务"
                    })
                    st.rerun()

        with st.expander("🔍 更多具体场景（8个）", expanded=False):
            st.markdown("**选择一个具体的场景模板：**")
            more_cols = st.columns(2)
            for i, sc in enumerate(SCENARIOS_MORE):
                with more_cols[i % 2]:
                    if st.button(f"{sc['icon']} {sc['title']}\n_{sc['desc']}", key=f"more_{sc['id']}",
                               use_container_width=True):
                        st.session_state.messages.append({
                            "role": "user",
                            "content": f"帮我执行「{sc['title']}」场景"
                        })
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

        executor = st.session_state.async_executor

        task_id = executor.submit(prompt, execute_func=_async_execute_task)

        if not task_id:
            st.error("⚠️ 系统繁忙，请稍后再试（并发任务已达上限）")
            st.stop()

        print(f"[frontend] 任务已提交: {task_id} (异步模式)")

        with st.chat_message("assistant"):
            status_container = st.status("🚀 任务已提交，正在后台执行...", expanded=True)

            cancel_col, _ = st.columns([1, 4])
            with cancel_col:
                if st.button("❌ 取消任务", key=f"cancel_{task_id}", use_container_width=True):
                    if executor.cancel(task_id):
                        st.warning("⏹️ 任务已取消")
                        st.stop()
                    else:
                        st.error("取消失败（任务可能已完成）")

            EXECUTION_PHASES = [
                (0, 3, "🔍 意图识别", "分析您的需求类型..."),
                (3, 8, "🔎 信息搜索", "搜索相关参考资料..."),
                (8, 25, "🤖 LLM生成", "AI正在撰写专业内容..."),
                (25, 50, "✍️ 内容润色", "优化输出质量..."),
                (50, 60, "📦 交付准备", "生成可下载文件..."),
            ]

            max_polls = 180
            poll_interval = 1.0
            start_time = time.time()

            for poll_count in range(max_polls):
                task_status = executor.get_status(task_id)
                current_status = task_status.get('status', 'unknown')
                elapsed = task_status.get('elapsed', 0)

                if current_status == 'pending':
                    if poll_count < 3:
                        status_container.update(label="⏳ 排队中，等待执行...")
                    time.sleep(poll_interval)
                    continue

                elif current_status == 'running':
                    phase_icon, phase_name, phase_hint = "⚡", "执行中", "处理中..."
                    for phase_start, phase_end, icon, hint in EXECUTION_PHASES:
                        if phase_start <= elapsed < phase_end:
                            phase_icon, phase_name, phase_hint = icon, hint.split("...")[0], hint
                            break
                    if elapsed >= 60:
                        phase_icon, phase_name, phase_hint = "🔄", "深度处理", "内容较长，请耐心等待..."

                    estimated_total = max(30, elapsed * 1.5) if elapsed < 10 else max(30, elapsed / 0.7)
                    remaining = max(0, estimated_total - elapsed)
                    progress_pct = min(int((elapsed / estimated_total) * 100), 95)

                    status_container.update(
                        label=f"{phase_icon} {phase_name} ({elapsed:.0f}s / 预计还需{remaining:.0f}s)",
                        state="running"
                    )
                    st.progress(progress_pct / 100.0, text=f"{phase_hint} — 已耗时 {elapsed:.0f}s")
                    time.sleep(poll_interval)
                    continue

                elif current_status == 'done':
                    status_container.update(label="✅ 任务完成", state="complete")

                    result_content = task_status.get('result_content')
                    result_filepath = task_status.get('result_filepath')

                    if result_content:
                        st.markdown(result_content)

                        if result_filepath and os.path.exists(result_filepath):
                            col_dl, col_info = st.columns([1, 3])
                            with col_dl:
                                with open(result_filepath, 'r', encoding='utf-8') as f:
                                    file_content = f.read()
                                st.download_button(
                                    label="📥 下载成果物",
                                    data=file_content,
                                    file_name=os.path.basename(result_filepath),
                                    mime="text/markdown",
                                    key=f"dl_async_{int(time.time()*1000)}",
                                    use_container_width=True,
                                    type="primary",
                                )
                            with col_info:
                                size_kb = round(len(file_content.encode('utf-8')) / 1024, 1)
                                st.success(f"✅ 已生成: {os.path.basename(result_filepath)} ({size_kb}KB)")

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": result_content,
                                "deliverable_path": result_filepath,
                                "deliverable_id": f"{int(time.time()*1000)}",
                            })
                    break

                elif current_status == 'failed':
                    error_msg = task_status.get('error_message', '未知错误')
                    status_container.update(label="❌ 任务执行失败", state="error")

                    is_timeout = any(kw in error_msg.lower() for kw in ['timeout', 'reset', 'connection', '超时'])

                    if is_timeout:
                        fallback = (
                            f"⏰ 任务执行时间较长，连接可能已中断\n\n"
                            f"关于「**{prompt[:40]}{'...' if len(prompt) > 40 else ''}**」\n\n"
                            f"**原因**: 网络搜索耗时超过了系统等待上限（约30秒）\n\n"
                            f"**建议操作**:\n"
                            f"1. 点击下方按钮重试（系统已缓存搜索结果，重试会更快）\n"
                            f"2. 或尝试更简短的需求描述\n"
                            f"3. 或在终端中直接运行: `python3 -c \"from opc_manager.task_engine_v3 import TaskEngineV3; print(TaskEngineV3().execute('{prompt[:30]}').content)\"`\n\n"
                            f"*技术详情*: `{error_msg[:200]}`"
                        )
                    else:
                        fallback = (
                            f"⚠️ 任务执行遇到问题\n\n"
                            f"关于「**{prompt[:40]}{'...' if len(prompt) > 40 else ''}**」\n\n"
                            f"*错误信息*: `{error_msg}`\n\n"
                            f"请稍后重试或换个方式描述需求。"
                        )

                    st.markdown(fallback)
                    st.session_state.messages.append({"role": "assistant", "content": fallback})
                    break

                elif current_status == 'cancelled':
                    status_container.update(label="⏹️ 任务已取消", state="complete")
                    st.info("任务已被用户取消")
                    break

                else:
                    time.sleep(poll_interval)
                    continue

            else:
                status_container.update(label="⏰ 任务执行超时", state="error")
                st.warning("任务执行时间过长，请查看历史记录或重新提交")


elif page == "📁 成果物":
    """成果物库页面 — 历史文件的管理中心
    
    功能：
    - 空状态提示引导用户去对话页执行任务
    - 列表展示每个成果物的元数据（任务/类型/时间/大小）
    - 每个文件独立下载按钮
    - 前500字Markdown预览（使用st.code语法高亮）
    """
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
    """成长飞轮页面 — 游戏化的用户激励系统
    
    数据来源：
    - flywheel_scores: 五维评分（内容质量/受众增长/变现能力/跨域推广/生态协同）
    - flywheel_level: 当前等级（L1探索者/L2连接者/L3生态构建者）
    - scenario_count: 累计互动次数
    
    等级晋升规则：
    - L1→L2: 平均分 ≥ 35
    - L2→L3: 平均分 ≥ 60
    - 每次互动对应维度 +8分（上限100）
    
    UI组件：
    - 等级卡片（渐变背景色随等级变化）
    - 互动次数指标
    - 五维进度条（颜色编码：绿≥60/橙≥30/灰<30）
    - 升级提示（未满级时显示下一级目标）
    """
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
    """设置页面 — 用户偏好和系统配置
    
    功能分区：
    1. AI助手: 回复风格选择（预留接口，当前仅影响展示）
    2. 成果物设置: 显示保存路径（只读）
    3. 通知: 场景推荐/成长进度开关
    4. 数据: 重置所有session_state数据（清空会话）
    5. 高级设置: LLM后端选择（开发者选项）
    6. 目录浏览: 展示deliverables/目录中的最近5个文件
    """
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
        llm_backend = st.selectbox("LLM 后端", ["moka（推荐）", "glm", "openai", "ollama"], index=0)
        if not os.environ.get('MOKA_API_KEY') and not os.environ.get('GLM_API_KEY') and not os.environ.get('OPENAI_API_KEY'):
            st.warning("⚠️ 未检测到API Key，当前为模板模式。配置MOKA_API_KEY可获得AI增强内容。")

    st.divider()

    existing_files = [f for f in os.listdir(DELIVERABLES_DIR) if f.endswith('.md')] if os.path.exists(DELIVERABLES_DIR) else []
    if existing_files:
        st.markdown(f"### 📂 成果物目录中的文件 ({len(existing_files)} 个)")
        for f in sorted(existing_files)[-5:]:
            fp = os.path.join(DELIVERABLES_DIR, f)
            size = round(os.path.getsize(fp) / 1024, 1)
            st.caption(f"📄 {f} ({size}KB)")

    from opc_manager.version import get_version
    st.caption(f"OPC-Agents v{get_version()} | 成果物交付版")
