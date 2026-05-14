import json
import logging
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, execute_transaction, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)


def add_competitor(name: str, url: str = "", keywords: str = "",
                   note: str = "") -> Dict[str, Any]:
    if not name.strip():
        return {"success": False, "error": "竞品名称不能为空"}

    competitor_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO competitors (id,name,url,keywords,note,created_at) VALUES (?,?,?,?,?,?)",
            (competitor_id, name, url, keywords, note, now),
        )
    except Exception as e:
        logger.warning("competitor_skill.add_competitor write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("competitor_added", {"id": competitor_id, "name": name})

    return {
        "success": True,
        "id": competitor_id,
        "message": f"竞品已添加: {name}",
    }


def list_competitors() -> Dict[str, Any]:
    try:
        rows = execute_query(
            "SELECT c.*, COUNT(cs.id) as snapshot_count, MAX(cs.created_at) as last_snapshot "
            "FROM competitors c LEFT JOIN competitor_snapshots cs ON c.id=cs.competitor_id "
            "GROUP BY c.id ORDER BY c.created_at DESC"
        )
    except Exception as e:
        logger.warning("competitor_skill.list_competitors query failed: %s", e)
        return {"success": True, "competitors": [], "count": 0}

    competitors = []
    for row in rows:
        c = dict(row)
        keywords_str = c.get("keywords", "")
        c["keywords"] = keywords_str.split("、") if keywords_str else []
        competitors.append(c)

    return {"success": True, "competitors": competitors, "count": len(competitors)}


def record_snapshot(competitor_id: str, changes: str = "",
                    source: str = "手动记录") -> Dict[str, Any]:
    rows = execute_query("SELECT * FROM competitors WHERE id=?", (competitor_id,))
    if not rows:
        return {"success": False, "error": f"竞品不存在: {competitor_id}"}

    snapshot_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO competitor_snapshots (id,competitor_id,changes,source,created_at) VALUES (?,?,?,?,?)",
            (snapshot_id, competitor_id, changes, source, now),
        )
    except Exception as e:
        logger.warning("competitor_skill.record_snapshot write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    snapshot_count = len(execute_query(
        "SELECT id FROM competitor_snapshots WHERE competitor_id=?", (competitor_id,)
    ))

    record = dict(rows[0])
    AuditLogger.log("competitor_snapshot", {"id": competitor_id, "changes": changes[:50]})

    return {
        "success": True,
        "message": f"已记录 {record['name']} 的动态",
        "snapshot_count": snapshot_count,
    }


def get_competitor_report(competitor_id: str = "") -> Dict[str, Any]:
    if competitor_id:
        rows = execute_query("SELECT * FROM competitors WHERE id=?", (competitor_id,))
        if not rows:
            return {"success": False, "error": f"竞品不存在: {competitor_id}"}
        record = dict(rows[0])
        keywords_str = record.get("keywords", "")
        record["keywords"] = keywords_str.split("、") if keywords_str else []
        snapshots = execute_query(
            "SELECT * FROM competitor_snapshots WHERE competitor_id=? ORDER BY created_at DESC LIMIT 10",
            (competitor_id,),
        )
        record["snapshots"] = [dict(s) for s in snapshots]
        md = _render_competitor_md(record)
        return {"success": True, "competitor": record["name"], "markdown": md}

    all_competitors = list_competitors()
    if all_competitors["count"] == 0:
        return {"success": True, "markdown": "# 竞品监控报告\n\n暂无竞品数据，请先添加竞品。"}

    md = "# 竞品监控总览\n\n"
    md += "| 竞品 | 网址 | 动态数 | 最近更新 |\n"
    md += "|------|------|--------|----------|\n"
    for c in all_competitors["competitors"]:
        md += f"| {c['name']} | {c.get('url') or '—'} | {c.get('snapshot_count', 0)} | {c.get('last_snapshot') or '—'} |\n"
    md += f"\n---\n*由OPC-Agents生成 · {time.strftime('%Y-%m-%d')}*\n"

    return {"success": True, "markdown": md, "count": all_competitors["count"]}


def remove_competitor(competitor_id: str) -> Dict[str, Any]:
    rows = execute_query("SELECT id FROM competitors WHERE id=?", (competitor_id,))
    if not rows:
        return {"success": False, "error": f"竞品不存在: {competitor_id}"}

    try:
        execute_write("DELETE FROM competitors WHERE id=?", (competitor_id,))
    except Exception as e:
        logger.warning("competitor_skill.remove_competitor delete failed: %s", e)
        return {"success": False, "error": f"删除失败: {e}"}

    AuditLogger.log("competitor_removed", {"id": competitor_id})
    return {"success": True, "message": "竞品已移除"}


def _render_competitor_md(record: dict) -> str:
    md = f"# 竞品分析: {record['name']}\n\n"
    md += f"**网址**: {record.get('url', '—')}  \n"
    md += f"**关注关键词**: {'、'.join(record.get('keywords', [])) or '—'}  \n"
    if record.get("note"):
        md += f"**备注**: {record['note']}  \n"
    md += "\n## 动态记录\n\n"
    snapshots = record.get("snapshots", [])
    if snapshots:
        for s in reversed(snapshots[-10:]):
            created_at = s.get("created_at", "")
            md += f"- **{created_at[:10]}** ({s.get('source', '')}): {s.get('changes', '')}\n"
    else:
        md += "- 暂无动态记录\n"
    md += f"\n---\n*由OPC-Agents生成 · {time.strftime('%Y-%m-%d')}*\n"
    return md


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["列表", "查看", "有哪些", "所有竞品"]):
        return list_competitors()

    if any(kw in goal for kw in ["报告", "分析", "总览"]):
        return get_competitor_report()

    if any(kw in goal for kw in ["记录", "动态", "变化", "更新"]):
        return {"success": False, "error": "请指定竞品ID来记录动态"}

    if any(kw in goal for kw in ["删除", "移除"]):
        return {"success": False, "error": "请指定竞品ID来移除"}

    if any(kw in goal for kw in ["添加", "新增", "加上", "监控"]):
        name = goal
        for kw in ["帮我添加", "帮我新增", "帮我监控", "添加竞品", "新增竞品", "监控竞品", "竞品"]:
            name = name.replace(kw, "")
        name = name.strip().strip("，。、的")
        if name:
            return add_competitor(name)
        return {"success": False, "error": "请指定竞品名称"}

    return list_competitors()
