"""
任务标签系统配置

替代原有的部门管理，提供更灵活的任务分类方式
"""

# 任务标签体系
TASK_TAG_SYSTEM = {
    # ========== 任务类型标签 ==========
    "task_type": {
        "name": "任务类型",
        "icon": "📋",
        "options": [
            {"id": "research", "name": "调研", "icon": "🔍", "color": "blue"},
            {"id": "design", "name": "设计", "icon": "🎨", "color": "purple"},
            {"id": "development", "name": "开发", "icon": "💻", "color": "green"},
            {"id": "writing", "name": "文案", "icon": "📝", "color": "orange"},
            {"id": "analysis", "name": "分析", "icon": "📊", "color": "cyan"},
            {"id": "testing", "name": "测试", "icon": "🧪", "color": "yellow"},
            {"id": "meeting", "name": "会议", "icon": "👥", "color": "indigo"},
            {"id": "document", "name": "文档", "icon": "📄", "color": "gray"},
            {"id": "review", "name": "评审", "icon": "✅", "color": "green"},
            {"id": "planning", "name": "规划", "icon": "📅", "color": "blue"}
        ]
    },
    
    # ========== 优先级标签 ==========
    "priority": {
        "name": "优先级",
        "icon": "⚡",
        "options": [
            {"id": "urgent", "name": "紧急", "icon": "🔥", "color": "red", "sla": "2 小时"},
            {"id": "important", "name": "重要", "icon": "⭐", "color": "orange", "sla": "24 小时"},
            {"id": "normal", "name": "常规", "icon": "📌", "color": "blue", "sla": "3 个工作日"},
            {"id": "low", "name": "低优", "icon": "🐢", "color": "gray", "sla": "1 周"}
        ]
    },
    
    # ========== 技能标签 ==========
    "skill": {
        "name": "所需技能",
        "icon": "🛠️",
        "options": [
            {"id": "communication", "name": "沟通", "icon": "💬"},
            {"id": "writing", "name": "写作", "icon": "✍️"},
            {"id": "design", "name": "设计", "icon": "🎨"},
            {"id": "coding", "name": "编程", "icon": "👨‍💻"},
            {"id": "analysis", "name": "分析", "icon": "🔬"},
            {"id": "research", "name": "研究", "icon": "📚"},
            {"id": "presentation", "name": "演讲", "icon": "🎤"},
            {"id": "management", "name": "管理", "icon": "📊"}
        ]
    },
    
    # ========== 业务域标签 ==========
    "domain": {
        "name": "业务域",
        "icon": "🏢",
        "options": [
            {"id": "product", "name": "产品", "icon": "📦"},
            {"id": "marketing", "name": "营销", "icon": "📢"},
            {"id": "sales", "name": "销售", "icon": "💰"},
            {"id": "hr", "name": "人事", "icon": "👥"},
            {"id": "finance", "name": "财务", "icon": "💵"},
            {"id": "operations", "name": "运营", "icon": "📈"},
            {"id": "support", "name": "支持", "icon": "🛟"},
            {"id": "strategy", "name": "战略", "icon": "🎯"}
        ]
    }
}

# ========== 智能标签推荐规则 ==========
TAG_RECOMMENDATION_RULES = {
    # 根据任务名称关键词推荐标签
    "keywords": {
        "调研": {"task_type": "research", "skill": "research"},
        "报告": {"task_type": "writing", "skill": "writing"},
        "设计": {"task_type": "design", "skill": "design"},
        "开发": {"task_type": "development", "skill": "coding"},
        "会议": {"task_type": "meeting", "skill": "communication"},
        "分析": {"task_type": "analysis", "skill": "analysis"},
        "产品": {"domain": "product"},
        "市场": {"domain": "marketing"},
        "财务": {"domain": "finance"},
        "招聘": {"domain": "hr"},
    },
    
    # 根据时间段推荐优先级
    "time_based": {
        "morning": {"suggest_focus": True},  # 早上建议处理重要任务
        "friday_afternoon": {"suggest_wrap_up": True}  # 周五下午建议收尾
    }
}

# ========== 标签组合预设 ==========
TAG_PRESETS = {
    "新产品发布": {
        "tags": {
            "task_type": ["planning", "design", "writing"],
            "priority": "important",
            "domain": ["product", "marketing"]
        },
        "description": "新产品发布相关任务"
    },
    "报告撰写": {
        "tags": {
            "task_type": ["writing", "analysis"],
            "priority": "important",
            "skill": ["writing", "analysis"]
        },
        "description": "各类报告撰写任务"
    },
    "会议组织": {
        "tags": {
            "task_type": ["meeting"],
            "priority": "normal",
            "skill": ["communication", "management"]
        },
        "description": "会议相关任务"
    },
    "日常运营": {
        "tags": {
            "task_type": ["operations"],
            "priority": "normal",
            "domain": "operations"
        },
        "description": "日常运营工作"
    }
}


def get_all_tags():
    """获取所有标签"""
    return TASK_TAG_SYSTEM


def get_tag_options(category):
    """获取指定分类的标签选项"""
    return TASK_TAG_SYSTEM.get(category, {}).get("options", [])


def recommend_tags(task_name, task_description=""):
    """
    根据任务名称和描述推荐标签
    
    Args:
        task_name: 任务名称
        task_description: 任务描述
        
    Returns:
        推荐的标签字典
    """
    recommended = {
        "task_type": [],
        "priority": [],
        "skill": [],
        "domain": []
    }
    
    text = task_name + " " + task_description
    
    # 关键词匹配
    for keyword, tags in TAG_RECOMMENDATION_RULES["keywords"].items():
        if keyword in text:
            for tag_category, tag_id in tags.items():
                if tag_category in recommended:
                    recommended[tag_category].append(tag_id)
    
    # 去重
    for category in recommended:
        recommended[category] = list(set(recommended[category]))
    
    return recommended


def get_preset(scenario_name):
    """获取预设标签组合"""
    return TAG_PRESETS.get(scenario_name, {})


def list_presets():
    """列出所有预设"""
    return [
        {"name": name, "description": data["description"]}
        for name, data in TAG_PRESETS.items()
    ]
