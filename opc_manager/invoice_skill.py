import json
import logging
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger
from opc_manager.utils import load_json_data

logger = logging.getLogger(__name__)

_DEFAULT_TAX_CALENDAR = [
    {"month": 1, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 2, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 3, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 4, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 4, "deadline": 30, "task": "企业所得税汇算清缴", "type": "企业所得税"},
    {"month": 5, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 6, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 7, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 8, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 9, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 10, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 10, "deadline": 31, "task": "个人所得税汇算清缴", "type": "个人所得税"},
    {"month": 11, "deadline": 15, "task": "增值税申报", "type": "增值税"},
    {"month": 12, "deadline": 15, "task": "增值税申报", "type": "增值税"},
]

try:
    TAX_CALENDAR = load_json_data("data/knowledge/tax_calendar.json")
except Exception:
    TAX_CALENDAR = _DEFAULT_TAX_CALENDAR


def create_invoice(client_name: str, amount: float, item: str = "服务费",
                   tax_rate: float = 0.06, invoice_type: str = "增值税普通发票") -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not client_name.strip():
        return {"success": False, "error": "客户名称不能为空"}

    tax_amount = round(amount * tax_rate, 2)
    total_with_tax = round(amount + tax_amount, 2)
    invoice_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    invoice_no = f"OPC{time.strftime('%Y%m%d')}{invoice_id}"

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
            "INSERT INTO invoices (id,invoice_no,client_name,amount,item,tax_rate,tax_amount,total_with_tax,status,markdown,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (invoice_id, invoice_no, client_name, amount, item, tax_rate, tax_amount, total_with_tax, "pending", markdown, now),
        )
    except Exception as e:
        logger.warning("invoice_skill.create_invoice write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("invoice_created", {"no": invoice_no, "client": client_name, "amount": amount})

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


def get_tax_calendar(month: int = 0) -> Dict[str, Any]:
    if month == 0:
        month = int(time.strftime("%m"))
    entries = [e for e in TAX_CALENDAR if e["month"] == month]
    upcoming = []
    for e in entries:
        deadline_str = f"{time.strftime('%Y')}-{month:02d}-{e['deadline']:02d}"
        remaining = (time.strptime(deadline_str, "%Y-%m-%d").tm_yday - time.localtime().tm_yday)
        upcoming.append({**e, "deadline_date": deadline_str, "days_remaining": remaining})

    next_month = month + 1 if month < 12 else 1
    next_entries = [e for e in TAX_CALENDAR if e["month"] == next_month]

    return {
        "success": True,
        "current_month": month,
        "this_month": upcoming,
        "next_month": next_entries,
    }


def _render_invoice_md(invoice: dict) -> str:
    md = f"# {invoice['invoice_type']}\n\n"
    md += f"**发票号码**: {invoice['invoice_no']}  \n"
    md += f"**购方名称**: {invoice['client_name']}  \n"
    md += f"**开票日期**: {invoice['created_at'][:10]}  \n\n"
    md += f"| 项目 | 金额 | 税率 | 税额 | 价税合计 |\n"
    md += f"|------|------|------|------|--------|\n"
    md += f"| {invoice['item']} | ¥{invoice['amount']:.2f} | {invoice['tax_rate']*100:.0f}% | ¥{invoice['tax_amount']:.2f} | ¥{invoice['total_with_tax']:.2f} |\n\n"
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
