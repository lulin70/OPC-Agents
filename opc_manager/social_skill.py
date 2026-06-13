import json
import logging
import re
import time
from typing import Any, Dict, List

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

_DEFAULT_PLATFORMS = {
    "小红书": {
        "max_title": 20,
        "max_body": 1000,
        "style": "种草风",
        "emoji": True,
        "tags": True,
    },
    "公众号": {
        "max_title": 64,
        "max_body": 20000,
        "style": "专业深度",
        "emoji": False,
        "tags": False,
    },
    "推特": {
        "max_title": 0,
        "max_body": 280,
        "style": "简洁有力",
        "emoji": True,
        "tags": True,
    },
    "微博": {
        "max_title": 0,
        "max_body": 2000,
        "style": "话题互动",
        "emoji": True,
        "tags": True,
    },
    "知乎": {
        "max_title": 50,
        "max_body": 50000,
        "style": "干货长文",
        "emoji": False,
        "tags": False,
    },
}


def _load_platforms() -> dict:
    try:
        from opc_manager.utils import load_json_data

        data = load_json_data("data/knowledge/social_platforms.json")
        for k, v in data.items():
            if "emoji" in v:
                v["emoji"] = bool(v["emoji"])
            if "tags" in v:
                v["tags"] = bool(v["tags"])
        return data
    except Exception as e:
        logger.debug("[SocialSkill] Load platforms failed: %s", e)
        return dict(_DEFAULT_PLATFORMS)


PLATFORMS = _load_platforms()


def _generate_with_llm(platform, topic, key_points, tone):
    try:
        from opc_manager.simple_llm_service import SimpleLLMService

        svc = SimpleLLMService()
        if not svc.is_available():
            return None

        platform_cfg = PLATFORMS.get(platform, {})
        max_body = platform_cfg.get("max_body", 2000)
        style = platform_cfg.get("style", "专业")

        prompt = f"""你是一位资深社交媒体运营专家。请为{platform}平台生成一篇关于"{topic}"的内容。

要求：
- 平台风格：{style}
- 字数限制：{max_body}字以内
- {"关键要点：" + key_points if key_points else ""}
- {"语调：" + tone if tone else "自然亲切"}
- 标题要吸引眼球
- 正文要有价值、有干货
- 不要使用"待补充"、"请根据实际"等占位符

请用JSON格式返回：{{"title": "标题", "body": "正文内容", "tags": ["标签1", "标签2"]}}"""

        result = svc.complete(prompt, max_tokens=1500)
        if result:
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict) and "body" in parsed:
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
    except Exception as e:
        logger.debug("[SocialSkill] Parse profile URL failed: %s", e)
    return None


def generate_content(
    platform: str, topic: str, key_points: str = "", tone: str = ""
) -> Dict[str, Any]:
    platform = platform.strip()
    if platform not in PLATFORMS:
        return {
            "success": False,
            "error": f"不支持的平台: {platform}，支持: {list(PLATFORMS.keys())}",
        }

    cfg = PLATFORMS[platform]
    style = tone or cfg["style"]

    llm_result = _generate_with_llm(platform, topic, key_points, tone)
    if llm_result:
        title = llm_result.get("title", _generate_title(platform, topic, cfg))
        body = llm_result.get(
            "body", _generate_body(platform, topic, key_points, style, cfg)
        )
        tags = (
            llm_result.get("tags", _generate_tags(platform, topic))
            if cfg["tags"]
            else []
        )
    else:
        title = _generate_title(platform, topic, cfg)
        body = _generate_body(platform, topic, key_points, style, cfg)
        tags = _generate_tags(platform, topic) if cfg["tags"] else []

    content_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO social_content (id,platform,topic,title,body,tags,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                content_id,
                platform,
                topic,
                title,
                body,
                json.dumps(tags, ensure_ascii=False),
                "draft",
                now,
            ),
        )
    except Exception as e:
        logger.warning("social_skill.generate_content write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log(
        "social_content_generated", {"platform": platform, "topic": topic[:30]}
    )

    return {
        "success": True,
        "id": content_id,
        "platform": platform,
        "title": title,
        "body": body,
        "tags": tags,
        "status": "draft",
        "message": f"{platform}内容已生成（草稿状态），请检查后发布",
        "publish_guide": _get_publish_guide(platform),
    }


def list_drafts(platform: str = "") -> Dict[str, Any]:
    try:
        if platform:
            rows = execute_query(
                "SELECT * FROM social_content WHERE status='draft' AND platform=? ORDER BY created_at DESC",
                (platform,),
            )
        else:
            rows = execute_query(
                "SELECT * FROM social_content WHERE status='draft' ORDER BY created_at DESC"
            )
    except Exception as e:
        logger.warning("social_skill.list_drafts query failed: %s", e)
        return {"success": True, "drafts": [], "count": 0}

    drafts = []
    for row in rows:
        d = dict(row)
        try:
            d["tags"] = json.loads(d.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
        drafts.append(d)

    return {"success": True, "drafts": drafts, "count": len(drafts)}


def mark_published(content_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM social_content WHERE id=?", (content_id,))
    if not rows:
        return {"success": False, "error": f"内容不存在: {content_id}"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        execute_write(
            "UPDATE social_content SET status='published', published_at=? WHERE id=?",
            (now, content_id),
        )
    except Exception as e:
        logger.warning("social_skill.mark_published update failed: %s", e)
        return {"success": False, "error": f"更新失败: {e}"}

    record = dict(rows[0])
    AuditLogger.log(
        "social_content_published",
        {"id": content_id, "platform": record.get("platform")},
    )
    return {
        "success": True,
        "message": f"内容已标记为已发布: {record.get('title', content_id)}",
    }


def _generate_title(platform: str, topic: str, cfg: dict) -> str:
    if platform == "小红书":
        return f"🔥 {topic}全攻略！一人公司必看"
    elif platform == "公众号":
        return f"深度解析：{topic}——一人公司实战指南"
    elif platform == "知乎":
        return f"一人公司如何做好{topic}？我的实战经验分享"
    elif platform == "推特":
        return ""
    elif platform == "微博":
        return ""
    return f"【{topic}】一人公司实战分享：请在此补充关于{topic}的核心观点、实操方法和注意事项。建议从以下角度展开：1) 为什么{topic}对一人公司重要；2) 具体执行步骤和工具推荐；3) 常见误区和避坑建议。"


def _generate_body(
    platform: str, topic: str, key_points: str, style: str, cfg: dict
) -> str:
    points = (
        key_points.split("、") if key_points else ["核心要点", "实操方法", "注意事项"]
    )

    if platform == "小红书":
        body = f"✨ {topic}干货来啦！\n\n"
        for i, p in enumerate(points[:5], 1):
            body += f"{i}️⃣ {p}\n\n"
        body += "💡 以上就是我的经验分享，觉得有用的话点个赞吧～\n\n"
        return body[: cfg["max_body"]]

    elif platform == "公众号":
        body = f"# {topic}\n\n"
        body += "## 背景\n\n作为一人公司经营者，{topic}是必须掌握的核心能力。\n\n"
        body += "## 核心要点\n\n"
        for p in points[:8]:
            body += f"- {p}\n\n"
        body += "## 实操建议\n\n"
        body += "1. 从小处着手，逐步优化\n2. 数据驱动决策\n3. 善用工具提升效率\n\n"
        body += "---\n*本文由OPC-Agents辅助生成*"
        return body[: cfg["max_body"]]

    elif platform == "推特":
        body = f"{topic} | 一人公司实战: {' / '.join(points[:3])}"
        return body[: cfg["max_body"]]

    elif platform == "微博":
        body = f"#{topic}# 一人公司实战分享：{'、'.join(points[:4])}。关注我，持续分享一人公司运营干货！"
        return body[: cfg["max_body"]]

    elif platform == "知乎":
        body = f"# {topic}\n\n"
        body += "作为经营一人公司多年的实践者，分享一些真实经验。\n\n"
        body += "## 核心观点\n\n"
        for p in points[:6]:
            body += f"### {p}\n\n基于实际运营经验的具体做法和分析。\n\n"
        body += "---\n*以上为个人实战经验，欢迎交流讨论。*"
        return body[: cfg["max_body"]]

    return topic


def _generate_tags(platform: str, topic: str) -> List[str]:
    base = [topic, "一人公司", "创业"]
    if platform == "小红书":
        base.extend(["创业日记", "副业", "自由职业"])
    elif platform == "微博":
        base = [f"#{t}#" for t in base]
    elif platform == "推特":
        base = [f"#{t.replace(' ', '')}" for t in base]
    return base[:6]


def _get_publish_guide(platform: str) -> str:
    guides = {
        "小红书": "1. 打开小红书App → 2. 点击+号 → 3. 粘贴标题和正文 → 4. 添加标签 → 5. 发布",
        "公众号": "1. 登录mp.weixin.qq.com → 2. 新建图文 → 3. 粘贴内容 → 4. 预览 → 5. 发布",
        "推特": "1. 打开twitter.com → 2. 粘贴内容 → 3. 发布",
        "微博": "1. 打开weibo.com → 2. 粘贴内容 → 3. 发布",
        "知乎": "1. 打开zhihu.com → 2. 写文章 → 3. 粘贴内容 → 4. 发布",
    }
    return guides.get(platform, "请手动发布到对应平台")


def _extract_topic(goal, platform_name):
    patterns = [
        r"(?:发|写|生成|发布)(?:一篇|一个)?(?:关于|论)?[「「](.+?)[」」](?:的|内容|文章|帖子)?",
        r"(?:发|写|生成|发布)(?:一篇|一个)?(?:关于|论)?[\"'](.+?)[\"'](?:的|内容|文章|帖子)?",
        r"(?:关于|论)[「「](.+?)[」」](?:的|内容|文章|帖子)",
        r"(?:关于|论)[\"'](.+?)[\"'](?:的|内容|文章|帖子)",
    ]
    for pat in patterns:
        m = re.search(pat, goal)
        if m:
            return m.group(1).strip()

    topic = goal
    for kw in [
        "帮我发",
        "帮我写",
        "生成",
        "发布",
        "内容",
        platform_name,
        "的",
        "到",
        "上",
        "一篇",
        "一个",
    ]:
        topic = topic.replace(kw, "")
    return topic.strip().strip("，。、") or "今日分享"


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    platform = ""
    for p in ["小红书", "公众号", "推特", "微博", "知乎"]:
        if p in goal:
            platform = p
            break
    if not platform:
        if any(kw in goal for kw in ["发帖", "发布", "发一条", "写一篇", "内容"]):
            return {
                "success": False,
                "error": "请指定发布平台",
                "available_platforms": list(PLATFORMS.keys()),
                "hint": "如：发一条小红书关于AI的内容",
            }

    if any(kw in goal for kw in ["草稿", "列表", "有哪些"]):
        return list_drafts(platform=platform)

    if any(kw in goal for kw in ["已发", "发布完成", "已发布"]):
        platform_name = platform
        name = goal
        for kw in [
            "已发",
            "发布完成",
            "已发布",
            platform_name,
            "的",
            "内容",
            "帖子",
            "文章",
        ]:
            name = name.replace(kw, "")
        name = name.strip().strip("，。、的")
        if name:
            rows = execute_query(
                "SELECT id FROM social_content WHERE platform=? AND topic LIKE ? AND status='draft' ORDER BY created_at DESC LIMIT 1",
                (platform_name, f"%{name}%"),
            )
            if rows:
                return mark_published(rows[0]["id"])
        return {
            "success": False,
            "error": "请提供内容ID来标记发布，或指定更明确的主题关键词",
        }

    topic = _extract_topic(goal, platform)

    return generate_content(platform, topic)


def undo_publish_content(content_id=None, **kwargs):
    init_db()
    if content_id:
        rows = execute_query(
            "SELECT * FROM social_content WHERE id=? AND status='published'",
            (content_id,),
        )
    else:
        rows = execute_query(
            "SELECT * FROM social_content WHERE status='published' ORDER BY created_at DESC LIMIT 1"
        )
    if not rows:
        return {"success": False, "error": "未找到可撤销的发布内容"}
    target_id = content_id or rows[0]["id"]
    execute_write(
        "UPDATE social_content SET status='draft', published_at=NULL WHERE id=?",
        (target_id,),
    )
    return {
        "success": True,
        "message": f"发布内容已撤回: {rows[0].get('title', target_id)}",
    }
