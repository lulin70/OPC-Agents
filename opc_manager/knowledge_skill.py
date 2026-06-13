import json
import logging
import time
from typing import Any, Dict

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)


def create_article(
    title: str, content: str, tags: str = "", category: str = ""
) -> Dict[str, Any]:
    if not title.strip():
        return {"success": False, "error": "文章标题不能为空"}
    if not content.strip():
        return {"success": False, "error": "文章内容不能为空"}

    article_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    tag_list = [t.strip() for t in tags.split("、") if t.strip()] if tags else []
    tags_json = json.dumps(tag_list, ensure_ascii=False)

    try:
        execute_write(
            "INSERT INTO knowledge_articles (id,title,content,tags,category,status,word_count,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                article_id,
                title,
                content,
                tags_json,
                category,
                "draft",
                len(content),
                now,
                now,
            ),
        )
    except Exception as e:
        logger.warning("knowledge_skill.create_article write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("knowledge_created", {"id": article_id, "title": title[:30]})

    return {
        "success": True,
        "id": article_id,
        "message": f"知识文章已创建: {title}",
        "word_count": len(content),
    }


def get_article(article_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM knowledge_articles WHERE id=?", (article_id,))
    if not rows:
        return {"success": False, "error": f"文章不存在: {article_id}"}

    article = dict(rows[0])
    try:
        article["tags"] = json.loads(article.get("tags", "[]"))
    except (json.JSONDecodeError, TypeError):
        article["tags"] = []

    return {"success": True, "article": article}


_KNOWLEDGE_UPDATEABLE_COLUMNS = {
    "title",
    "content",
    "word_count",
    "tags",
    "category",
    "updated_at",
}


def update_article(
    article_id: str,
    title: str = "",
    content: str = "",
    tags: str = "",
    category: str = "",
) -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM knowledge_articles WHERE id=?", (article_id,))
    if not rows:
        return {"success": False, "error": f"文章不存在: {article_id}"}

    existing = dict(rows[0])
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    updates = []

    if title:
        updates.append(("title", title))
    if content:
        updates.append(("content", content))
        updates.append(("word_count", len(content)))
    if tags:
        tag_list = [t.strip() for t in tags.split("、") if t.strip()]
        updates.append(("tags", json.dumps(tag_list, ensure_ascii=False)))
    if category:
        updates.append(("category", category))

    updates.append(("updated_at", now))

    if len(updates) == 1:
        return {"success": True, "message": f"文章无变更: {existing['title']}"}

    set_clauses = []
    set_params = []
    for col, val in updates:
        if col not in _KNOWLEDGE_UPDATEABLE_COLUMNS:
            continue
        set_clauses.append(f"{col}=?")
        set_params.append(val)

    set_params.append(article_id)
    sql = f"UPDATE knowledge_articles SET {','.join(set_clauses)} WHERE id=?"

    try:
        execute_write(sql, tuple(set_params))
    except Exception as e:
        logger.warning("knowledge_skill.update_article write failed: %s", e)
        return {"success": False, "error": f"更新失败: {e}"}

    AuditLogger.log("knowledge_updated", {"id": article_id})
    return {"success": True, "message": f"文章已更新: {title or existing['title']}"}


def delete_article(article_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT id FROM knowledge_articles WHERE id=?", (article_id,))
    if not rows:
        return {"success": False, "error": f"文章不存在: {article_id}"}

    try:
        execute_write("DELETE FROM knowledge_articles WHERE id=?", (article_id,))
    except Exception as e:
        logger.warning("knowledge_skill.delete_article delete failed: %s", e)
        return {"success": False, "error": f"删除失败: {e}"}

    AuditLogger.log("knowledge_deleted", {"id": article_id})
    return {"success": True, "message": "文章已删除"}


def search_articles(
    query: str = "", tags: str = "", category: str = ""
) -> Dict[str, Any]:
    conditions = []
    params = []

    if category:
        conditions.append("category=?")
        params.append(category)

    if tags:
        tag_list = [t.strip() for t in tags.split("、") if t.strip()]
        tag_conditions = []
        for t in tag_list:
            tag_conditions.append("tags LIKE ?")
            params.append(f"%{t}%")
        if tag_conditions:
            conditions.append(f"({' OR '.join(tag_conditions)})")

    if query:
        query.lower()
        conditions.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT id,title,tags,category,word_count,updated_at FROM knowledge_articles WHERE {where_clause} ORDER BY updated_at DESC"

    try:
        rows = execute_query(sql, tuple(params))
    except Exception as e:
        logger.warning("knowledge_skill.search_articles query failed: %s", e)
        return {"success": True, "articles": [], "count": 0}

    results = []
    for row in rows:
        a = dict(row)
        try:
            a["tags"] = json.loads(a.get("tags", "[]"))
        except (json.JSONDecodeError, TypeError):
            a["tags"] = []
        results.append(a)

    return {"success": True, "articles": results, "count": len(results)}


def list_categories() -> Dict[str, Any]:
    try:
        rows = execute_query(
            "SELECT category, COUNT(*) as count FROM knowledge_articles GROUP BY category ORDER BY category"
        )
    except Exception as e:
        logger.warning("knowledge_skill.list_categories query failed: %s", e)
        return {"success": True, "categories": [], "count": 0}

    categories = [
        {"name": row["category"] or "未分类", "count": row["count"]} for row in rows
    ]
    return {"success": True, "categories": categories, "count": len(categories)}


def get_stats() -> Dict[str, Any]:
    try:
        total_row = execute_query(
            "SELECT COUNT(*) as total, SUM(word_count) as total_words FROM knowledge_articles"
        )
        cat_row = execute_query(
            "SELECT COUNT(DISTINCT category) as categories FROM knowledge_articles"
        )
    except Exception as e:
        logger.warning("knowledge_skill.get_stats query failed: %s", e)
        return {"success": True, "total": 0, "total_words": 0, "categories": 0}

    total = total_row[0]["total"] if total_row else 0
    total_words = (
        total_row[0]["total_words"] if total_row and total_row[0]["total_words"] else 0
    )
    categories = cat_row[0]["categories"] if cat_row else 0

    return {
        "success": True,
        "total": total,
        "total_words": total_words,
        "categories": categories,
    }


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["统计", "多少", "概况"]):
        return get_stats()

    if any(kw in goal for kw in ["分类", "类别"]):
        return list_categories()

    if any(kw in goal for kw in ["搜索", "查找", "找"]):
        query = goal
        for kw in ["帮我搜索", "帮我查找", "帮我找", "搜索", "查找"]:
            query = query.replace(kw, "")
        query = query.strip().strip("，。、的")
        if not query:
            query = goal
        return search_articles(query=query)

    if any(kw in goal for kw in ["删除"]):
        return {"success": False, "error": "请提供文章ID来删除"}

    if any(kw in goal for kw in ["写", "创建", "添加", "新建", "记录"]):
        title = goal
        for kw in [
            "帮我写",
            "帮我创建",
            "帮我记录",
            "写",
            "创建",
            "添加",
            "新建",
            "笔记",
            "知识库",
            "文档",
        ]:
            title = title.replace(kw, "")
        title = title.strip().strip("，。、的")
        if title:
            return {
                "success": True,
                "message": f"请提供'{title}'的具体内容，我将为你保存到知识库",
                "title": title,
                "needs_content": True,
            }
        return {"success": False, "error": "请指定文章标题"}

    return search_articles()
