"""[FROZEN v0.3.0] This skill is frozen and not actively maintained.

Frozen on: 2026-06-19
Reason: v0.3.0 product focus contraction (13→3 core skills)
Revival: See docs/spec/SKILL_FREEZE_LIST.md for revival conditions
"""

import logging
import time
from typing import Any, Dict

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger
from opc_manager.tax_reminder_skill import get_tax_calendar, TAX_CALENDAR  # noqa: F401
from opc_manager.utils import SECONDS_PER_DAY

logger = logging.getLogger(__name__)


def create_invoice(
    client_name: str,
    amount: float,
    item: str = "服务费",
    tax_rate: float = 0.06,
    invoice_type: str = "增值税普通发票",
    proposal_id: str = "",
) -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not client_name.strip():
        return {"success": False, "error": "客户名称不能为空"}

    tax_amount = round(amount * tax_rate, 2)
    total_with_tax = round(amount + tax_amount, 2)
    invoice_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    today_str = time.strftime("%Y%m%d")
    today_start = time.strftime("%Y-%m-%d")
    existing = execute_query(
        "SELECT invoice_no FROM invoices WHERE created_at >= ? AND created_at < ?",
        (
            today_start,
            time.strftime("%Y-%m-%d", time.localtime(time.time() + SECONDS_PER_DAY)),
        ),
    )
    seq = len(existing) + 1
    invoice_no = f"OPC{today_str}{seq:04d}"

    invoice = {
        "id": invoice_id,
        "invoice_no": invoice_no,
        "client_name": client_name,
        "item": item,
        "amount": amount,
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "total_with_tax": total_with_tax,
        "invoice_type": invoice_type,
        "status": "pending",
        "created_at": now,
    }

    markdown = _render_invoice_md(invoice)

    try:
        execute_write(
            "INSERT INTO invoices "
            "(id,invoice_no,client_name,amount,item,tax_rate,tax_amount,"
            "total_with_tax,proposal_id,status,markdown,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                invoice_id,
                invoice_no,
                client_name,
                amount,
                item,
                tax_rate,
                tax_amount,
                total_with_tax,
                proposal_id,
                "pending",
                markdown,
                now,
            ),
        )
    except Exception as e:
        logger.warning("invoice_skill.create_invoice write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log(
        "invoice_created", {"no": invoice_no, "client": client_name, "amount": amount}
    )

    return {
        "success": True,
        "id": invoice_id,
        "invoice_no": invoice_no,
        "amount": amount,
        "tax_amount": tax_amount,
        "total_with_tax": total_with_tax,
        "markdown": markdown,
        "message": f"发票已生成: {invoice_no}，金额 ¥{total_with_tax:.2f}（含税）",
    }


def update_invoice_status(invoice_id: str, status: str) -> Dict[str, Any]:
    valid_statuses = {"issued", "paid", "cancelled"}
    if status not in valid_statuses:
        return {
            "success": False,
            "error": f"无效状态: {status}，支持: {', '.join(sorted(valid_statuses))}",
        }
    rows = execute_query("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    if not rows:
        return {"success": False, "error": f"发票不存在: {invoice_id}"}
    try:
        execute_write(
            "UPDATE invoices SET status=? WHERE id=?",
            (status, invoice_id),
        )
    except Exception as e:
        logger.warning("invoice_skill.update_invoice_status update failed: %s", e)
        return {"success": False, "error": f"更新失败: {e}"}
    record = dict(rows[0])
    AuditLogger.log("invoice_status_updated", {"id": invoice_id, "status": status})
    return {
        "success": True,
        "message": f"发票 {record.get('invoice_no', invoice_id)} 状态已更新为: {status}",
    }


def list_invoices(status: str = "") -> Dict[str, Any]:
    try:
        if status:
            rows = execute_query(
                "SELECT * FROM invoices WHERE status=? ORDER BY created_at DESC",
                (status,),
            )
        else:
            rows = execute_query("SELECT * FROM invoices ORDER BY created_at DESC")
    except Exception as e:
        logger.warning("invoice_skill.list_invoices query failed: %s", e)
        return {"success": True, "invoices": [], "count": 0}

    invoices = [dict(row) for row in rows]
    return {"success": True, "invoices": invoices, "count": len(invoices)}


def _render_invoice_md(invoice: dict) -> str:
    md = f"# {invoice['invoice_type']}\n\n"
    md += f"**发票号码**: {invoice['invoice_no']}  \n"
    md += f"**购方名称**: {invoice['client_name']}  \n"
    md += f"**开票日期**: {invoice['created_at'][:10]}  \n\n"
    md += "| 项目 | 金额 | 税率 | 税额 | 价税合计 |\n"
    md += "|------|------|------|------|--------|\n"
    md += (
        f"| {invoice['item']} | ¥{invoice['amount']:.2f} | "
        f"{invoice['tax_rate']*100:.0f}% | ¥{invoice['tax_amount']:.2f} | "
        f"¥{invoice['total_with_tax']:.2f} |\n\n"
    )
    md += f"**价税合计: ¥{invoice['total_with_tax']:.2f}**\n\n"
    md += "---\n*本发票由OPC-Agents生成，仅供参考*\n"
    return md


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["税务", "报税", "税日历"]):
        return get_tax_calendar()

    if any(kw in goal for kw in ["列表", "查看"]):
        return list_invoices()

    from opc_manager.finance_skill import parse_amount_from_text

    amount = parse_amount_from_text(goal)
    if not amount:
        return {"success": False, "error": "请指定金额（如：给张总开一张3000元的发票）"}

    client_name = ""
    import re

    m = re.search(r"给(.+?)(开|出)", goal)
    if m:
        client_name = m.group(1).strip()
    if not client_name:
        return {"success": False, "error": "请指定客户名称"}

    return create_invoice(client_name, amount)


def undo_create_invoice(invoice_id=None, **kwargs):
    init_db()
    if invoice_id:
        rows = execute_query("SELECT * FROM invoices WHERE id=?", (invoice_id,))
    else:
        rows = execute_query("SELECT * FROM invoices ORDER BY created_at DESC LIMIT 1")
    if not rows:
        return {"success": False, "error": "未找到可撤销的发票"}
    target_id = invoice_id or rows[0]["id"]
    execute_write("UPDATE invoices SET status='cancelled' WHERE id=?", (target_id,))
    return {
        "success": True,
        "message": f"发票已撤销: {rows[0].get('invoice_no', target_id)}",
    }
