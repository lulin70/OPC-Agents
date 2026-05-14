import logging
import re
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import encrypt_field, decrypt_field, execute_query, execute_write, execute_transaction, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

SILENT_THRESHOLD_DAYS = 30


def _encrypt_customer_fields(customer: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(customer)
    if result.get("phone"):
        result["phone"] = encrypt_field(result["phone"])
    if result.get("email"):
        result["email"] = encrypt_field(result["email"])
    return result


def _decrypt_customer_fields(customer: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(customer)
    if result.get("phone"):
        decrypted = decrypt_field(result["phone"])
        result["phone"] = decrypted if decrypted is not None else "[DECRYPT_FAILED]"
    if result.get("email"):
        decrypted = decrypt_field(result["email"])
        result["email"] = decrypted if decrypted is not None else "[DECRYPT_FAILED]"
    return result


def add_customer(name: str, company: str = "", title: str = "",
                 phone: str = "", email: str = "", source: str = "",
                 tags: str = "") -> Dict[str, Any]:
    if not name.strip():
        return {"success": False, "error": "客户姓名不能为空"}
    if phone and not re.match(r'^1[3-9]\d{9}$', phone) and not re.match(r'^\+\d{7,15}$', phone):
        return {"success": False, "error": f"手机号格式无效: {phone}"}
    if email and not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        return {"success": False, "error": f"邮箱格式无效: {email}"}

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    customer_id = gen_id()
    encrypted_phone = encrypt_field(phone) if phone else ""
    encrypted_email = encrypt_field(email) if email else ""
    try:
        execute_write(
            "INSERT INTO customers (id,name,company,title,phone,email,source,tags,status,created_at,last_contact) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (customer_id, name, company, title, encrypted_phone, encrypted_email, source, tags, "potential", now, now),
        )
        AuditLogger.log("crm_customer_added", {"id": customer_id, "name": name})
        return {"success": True, "id": customer_id, "message": f"客户已录入: {name} ({company})" if company else f"客户已录入: {name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_customer(customer_id: str = "", name: str = "") -> Dict[str, Any]:
    if customer_id:
        rows = execute_query("SELECT * FROM customers WHERE id=?", (customer_id,))
    elif name:
        rows = execute_query("SELECT * FROM customers WHERE name LIKE ?", (f"%{name}%",))
    else:
        return {"success": False, "error": "请提供客户ID或姓名"}
    if not rows:
        return {"success": False, "error": "未找到客户"}
    customer = _decrypt_customer_fields(rows[0])
    deals = execute_query("SELECT * FROM deals WHERE customer_id=? ORDER BY date DESC", (customer["id"],))
    customer["deals"] = deals
    return {"success": True, "customer": customer}


_CRM_WHERE_COLUMNS = {"company", "tags", "status", "source"}


def search_customers(company: str = "", tags: str = "",
                     status: str = "", source: str = "") -> Dict[str, Any]:
    conditions = []
    params: list = []
    if company:
        conditions.append(("company", "LIKE", f"%{company}%"))
    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                conditions.append(("tags", "LIKE", f"%{tag}%"))
    if status:
        conditions.append(("status", "=", status))
    if source:
        conditions.append(("source", "=", source))

    where_parts = []
    for col, op, val in conditions:
        if col not in _CRM_WHERE_COLUMNS:
            continue
        where_parts.append(f"{col} {op} ?")
        params.append(val)
    where = " AND ".join(where_parts) if where_parts else "1=1"
    rows = execute_query(f"SELECT * FROM customers WHERE {where} ORDER BY last_contact DESC", tuple(params))
    decrypted_rows = [_decrypt_customer_fields(r) for r in rows]
    return {"success": True, "customers": decrypted_rows, "count": len(decrypted_rows)}


def add_deal(customer_id: str, description: str, amount: float = 0,
             date: str = "", status: str = "negotiating") -> Dict[str, Any]:
    if not date:
        date = time.strftime("%Y-%m-%d")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    deal_id = gen_id()
    try:
        stmts = [
            ("INSERT INTO deals (id,customer_id,date,description,amount,status,created_at) VALUES (?,?,?,?,?,?,?)",
             (deal_id, customer_id, date, description, amount, status, now)),
        ]
        if status == "closed_won":
            customer_rows = execute_query("SELECT status FROM customers WHERE id=?", (customer_id,))
            current_status = customer_rows[0]["status"] if customer_rows else None
            new_status = "first_deal" if current_status == "potential" else "active"
            stmts.append(
                ("UPDATE customers SET status=?, last_contact=? WHERE id=?",
                 (new_status, now, customer_id)),
            )
        else:
            stmts.append(
                ("UPDATE customers SET last_contact=? WHERE id=?",
                 (now, customer_id)),
            )
        ok = execute_transaction(stmts)
        if not ok:
            return {"success": False, "error": "事务执行失败"}
        if status == "closed_won":
            try:
                from opc_manager.finance_skill import record_income
                record_income(amount, description, date=date)
            except Exception as e:
                logger.warning("auto record_income failed: %s", e)
        AuditLogger.log("crm_deal_added", {"id": deal_id, "customer_id": customer_id, "amount": amount})
        return {"success": True, "id": deal_id, "message": f"合作记录已添加: {description}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_silent_customers(days: int = SILENT_THRESHOLD_DAYS) -> Dict[str, Any]:
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - days * 86400))
    rows = execute_query(
        "SELECT * FROM customers WHERE last_contact<? AND status NOT IN ('lost') ORDER BY last_contact ASC",
        (cutoff,),
    )
    decrypted_rows = [_decrypt_customer_fields(r) for r in rows]
    return {"success": True, "customers": decrypted_rows, "count": len(decrypted_rows), "silent_days": days}


def update_customer_status(customer_id: str, status: str) -> Dict[str, Any]:
    valid = ("potential", "first_deal", "active", "silent", "lost")
    if status not in valid:
        return {"success": False, "error": f"无效状态: {status}, 有效值: {valid}"}
    try:
        execute_write("UPDATE customers SET status=? WHERE id=?", (status, customer_id))
        return {"success": True, "message": f"客户状态已更新为: {status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_customer_stats() -> Dict[str, Any]:
    rows = execute_query(
        "SELECT status, COUNT(*) as cnt FROM customers GROUP BY status"
    )
    stats = {r["status"]: r["cnt"] for r in rows}
    total = sum(stats.values())
    return {
        "success": True,
        "total": total,
        "potential": stats.get("potential", 0),
        "first_deal": stats.get("first_deal", 0),
        "active": stats.get("active", 0),
        "silent": stats.get("silent", 0),
        "lost": stats.get("lost", 0),
    }


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["沉默", "没联系", "超过"]):
        return get_silent_customers()

    if any(kw in goal for kw in ["统计", "多少客户", "客户数"]):
        return get_customer_stats()

    if any(kw in goal for kw in ["查", "找", "联系方式"]):
        name = goal
        for kw in ["帮我查", "帮我找", "的联系方式", "客户"]:
            name = name.replace(kw, "")
        name = name.strip().strip("，。、的")
        if name:
            return get_customer(name=name)
        return {"success": False, "error": "请提供客户姓名"}

    if any(kw in goal for kw in ["记", "录入", "添加客户", "新建客户"]):
        return add_customer(name=goal)

    if any(kw in goal for kw in ["合作", "成交", "签约"]):
        return {"success": False, "error": "请指定客户ID和合作详情"}

    return search_customers()
