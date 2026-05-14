import json
import logging
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

SERVICE_TEMPLATES = {
    "咨询": {"items": [{"name": "咨询诊断", "unit": "次", "price": 2000}, {"name": "方案交付", "unit": "份", "price": 5000}, {"name": "后续跟进", "unit": "月", "price": 3000}]},
    "培训": {"items": [{"name": "培训课程", "unit": "天", "price": 5000}, {"name": "教材资料", "unit": "套", "price": 500}, {"name": "答疑支持", "unit": "月", "price": 2000}]},
    "设计": {"items": [{"name": "需求分析", "unit": "次", "price": 3000}, {"name": "设计交付", "unit": "稿", "price": 8000}, {"name": "修改迭代", "unit": "轮", "price": 2000}]},
    "开发": {"items": [{"name": "需求梳理", "unit": "次", "price": 3000}, {"name": "开发实施", "unit": "人天", "price": 2000}, {"name": "测试上线", "unit": "次", "price": 5000}, {"name": "维护支持", "unit": "月", "price": 3000}]},
    "通用": {"items": [{"name": "服务内容", "unit": "项", "price": 5000}]},
}


def create_proposal(client_name: str, service_type: str = "通用",
                    items: List[Dict[str, Any]] = None,
                    valid_days: int = 30,
                    note: str = "") -> Dict[str, Any]:
    if not client_name.strip():
        return {"success": False, "error": "客户名称不能为空"}

    if items is None:
        tpl = SERVICE_TEMPLATES.get(service_type, SERVICE_TEMPLATES["通用"])
        items = [{"name": it["name"], "quantity": 1, "unit": it["unit"], "price": it.get("price", 0)} for it in tpl["items"]]

    total = sum(it.get("quantity", 1) * it.get("price", 0) for it in items)
    proposal_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    valid_until = time.strftime("%Y-%m-%d", time.localtime(time.time() + valid_days * 86400))

    proposal = {
        "id": proposal_id,
        "client_name": client_name,
        "service_type": service_type,
        "items": items,
        "total": total,
        "valid_until": valid_until,
        "note": note,
        "status": "draft",
        "created_at": now,
    }

    markdown = _render_proposal_md(proposal)

    try:
        execute_write(
            "INSERT INTO proposals (id,client_name,service_type,items,total,valid_days,valid_until,status,markdown,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, client_name, service_type, json.dumps(items, ensure_ascii=False), total, valid_days, valid_until, "draft", markdown, now),
        )
    except Exception as e:
        logger.warning("proposal_skill.create_proposal write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("proposal_created", {"id": proposal_id, "client": client_name, "total": total})

    return {
        "success": True,
        "id": proposal_id,
        "total": total,
        "valid_until": valid_until,
        "markdown": markdown,
        "message": f"报价单已生成: {client_name}，总计 ¥{total:.2f}",
    }


def list_proposals(status: str = "") -> Dict[str, Any]:
    try:
        if status:
            rows = execute_query(
                "SELECT * FROM proposals WHERE status=? ORDER BY created_at DESC",
                (status,),
            )
        else:
            rows = execute_query("SELECT * FROM proposals ORDER BY created_at DESC")
    except Exception as e:
        logger.warning("proposal_skill.list_proposals query failed: %s", e)
        return {"success": True, "proposals": [], "count": 0}

    proposals = []
    for row in rows:
        p = dict(row)
        try:
            p["items"] = json.loads(p.get("items", "[]"))
        except (json.JSONDecodeError, TypeError):
            p["items"] = []
        proposals.append(p)

    return {"success": True, "proposals": proposals, "count": len(proposals)}


def update_proposal_status(proposal_id: str, status: str) -> Dict[str, Any]:
    valid = ("draft", "sent", "accepted", "rejected", "expired")
    if status not in valid:
        return {"success": False, "error": f"无效状态: {status}"}

    rows = execute_query("SELECT id FROM proposals WHERE id=?", (proposal_id,))
    if not rows:
        return {"success": False, "error": f"报价单不存在: {proposal_id}"}

    try:
        execute_write(
            "UPDATE proposals SET status=? WHERE id=?",
            (status, proposal_id),
        )
    except Exception as e:
        logger.warning("proposal_skill.update_proposal_status failed: %s", e)
        return {"success": False, "error": f"更新失败: {e}"}

    AuditLogger.log("proposal_status_changed", {"id": proposal_id, "status": status})
    return {"success": True, "message": f"报价单状态已更新为: {status}"}


def _render_proposal_md(proposal: dict) -> str:
    md = f"# 服务报价单\n\n"
    md += f"**客户**: {proposal['client_name']}  \n"
    md += f"**服务类型**: {proposal['service_type']}  \n"
    md += f"**有效期至**: {proposal['valid_until']}  \n"
    md += f"**日期**: {proposal['created_at'][:10]}\n\n"
    md += "| 序号 | 服务项目 | 数量 | 单位 | 单价 | 小计 |\n"
    md += "|------|---------|------|------|------|------|\n"
    for i, item in enumerate(proposal["items"], 1):
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        subtotal = qty * price
        md += f"| {i} | {item['name']} | {qty} | {item.get('unit', '项')} | ¥{price:.2f} | ¥{subtotal:.2f} |\n"
    md += f"\n**合计: ¥{proposal['total']:.2f}**\n\n"
    if proposal.get("note"):
        md += f"**备注**: {proposal['note']}\n\n"
    md += "---\n*本报价单由OPC-Agents生成*\n"
    return md


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["列表", "查看", "有哪些"]):
        return list_proposals()

    client_name = ""
    service_type = "通用"
    for st in ["咨询", "培训", "设计", "开发"]:
        if st in goal:
            service_type = st
            break

    import re
    m = re.search(r"给(.+?)(的|做|出|写)", goal)
    if m:
        client_name = m.group(1).strip()
    if not client_name:
        m = re.search(r"为(.+?)(的|做|出|写)", goal)
        if m:
            client_name = m.group(1).strip()
    if not client_name:
        return {"success": False, "error": "请指定客户名称（如：给张总出个报价）"}

    return create_proposal(client_name, service_type)
