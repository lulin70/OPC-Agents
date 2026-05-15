import logging
import re
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)


def record_income(amount: float, source: str, category: str = "咨询费",
                  date: str = "", note: str = "") -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not date:
        date = time.strftime("%Y-%m-%d")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    record_id = gen_id()
    try:
        execute_write(
            "INSERT INTO finance_records (id,type,amount,category,source,date,note,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (record_id, "income", amount, category, source, date, note, now),
        )
        AuditLogger.log("finance_income", {"id": record_id, "amount": amount, "source": source})
        return {"success": True, "id": record_id, "message": f"已记录收入 ¥{amount:.2f} ({source})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def record_expense(amount: float, source: str, category: str = "其他支出",
                   date: str = "", note: str = "") -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not date:
        date = time.strftime("%Y-%m-%d")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    record_id = gen_id()
    try:
        execute_write(
            "INSERT INTO finance_records (id,type,amount,category,source,date,note,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (record_id, "expense", amount, category, source, date, note, now),
        )
        AuditLogger.log("finance_expense", {"id": record_id, "amount": amount, "source": source})
        return {"success": True, "id": record_id, "message": f"已记录支出 ¥{amount:.2f} ({source})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_monthly_report(year_month: str = "") -> Dict[str, Any]:
    if not year_month:
        year_month = time.strftime("%Y-%m")
    rows = execute_query(
        "SELECT type, category, amount FROM finance_records WHERE date LIKE ?",
        (f"{year_month}%",),
    )
    if not rows:
        return {"success": True, "year_month": year_month, "income": 0, "expense": 0, "profit": 0, "details": []}

    income = 0.0
    expense = 0.0
    income_by_cat: Dict[str, float] = {}
    expense_by_cat: Dict[str, float] = {}

    for r in rows:
        if r["type"] == "income":
            income += r["amount"]
            income_by_cat[r["category"]] = income_by_cat.get(r["category"], 0) + r["amount"]
        else:
            expense += r["amount"]
            expense_by_cat[r["category"]] = expense_by_cat.get(r["category"], 0) + r["amount"]

    prev_month_rows = execute_query(
        "SELECT type, amount FROM finance_records WHERE date LIKE ?",
        (_prev_month(year_month),),
    )
    prev_income = sum(r["amount"] for r in prev_month_rows if r["type"] == "income")
    prev_expense = sum(r["amount"] for r in prev_month_rows if r["type"] == "expense")

    return {
        "success": True,
        "year_month": year_month,
        "income": round(income, 2),
        "expense": round(expense, 2),
        "profit": round(income - expense, 2),
        "income_change": round(income - prev_income, 2) if prev_income else None,
        "expense_change": round(expense - prev_expense, 2) if prev_expense else None,
        "income_by_category": {k: round(v, 2) for k, v in sorted(income_by_cat.items(), key=lambda x: -x[1])},
        "expense_by_category": {k: round(v, 2) for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])},
    }


def get_trend(months: int = 6) -> List[Dict[str, Any]]:
    init_db()
    from datetime import datetime
    results = []
    now = datetime.now()
    for i in range(months - 1, -1, -1):
        target_month = now.month - i
        target_year = now.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        ym = f"{target_year}-{target_month:02d}"
        rows = execute_query(
            "SELECT type, SUM(amount) as total FROM finance_records WHERE date LIKE ? GROUP BY type",
            (f"{ym}%",),
        )
        income = sum(r["total"] for r in rows if r["type"] == "income")
        expense = sum(r["total"] for r in rows if r["type"] == "expense")
        results.append({"year_month": ym, "income": round(income, 2), "expense": round(expense, 2), "profit": round(income - expense, 2)})
    return results


def list_categories(record_type: str = "") -> List[Dict[str, Any]]:
    if record_type:
        return execute_query("SELECT * FROM finance_categories WHERE type=? ORDER BY name", (record_type,))
    return execute_query("SELECT * FROM finance_categories ORDER BY type, name")


def _prev_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m -= 1
    if m == 0:
        m = 12
        y -= 1
    return f"{y}-{m:02d}"


def undo_record_income(record_id=None, **kwargs):
    init_db()
    if record_id:
        execute_write("UPDATE finances SET status='voided' WHERE id=? AND type='income'", (record_id,))
    else:
        latest = execute_query("SELECT id FROM finances WHERE type='income' ORDER BY created_at DESC LIMIT 1")
        if latest:
            execute_write("UPDATE finances SET status='voided' WHERE id=?", (latest[0]["id"],))
    return {"success": True, "message": "收入记录已撤销"}


def undo_record_expense(record_id=None, **kwargs):
    init_db()
    if record_id:
        execute_write("UPDATE finances SET status='voided' WHERE id=? AND type='expense'", (record_id,))
    else:
        latest = execute_query("SELECT id FROM finances WHERE type='expense' ORDER BY created_at DESC LIMIT 1")
        if latest:
            execute_write("UPDATE finances SET status='voided' WHERE id=?", (latest[0]["id"],))
    return {"success": True, "message": "支出记录已撤销"}


def parse_amount_from_text(text: str) -> Optional[float]:
    patterns = [
        r'[¥￥]\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*元',
        r'(\d+\.?\d*)\s*块',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return float(m.group(1))
    m = re.search(r'(\d+\.?\d*)', text)
    if m:
        after = text[m.end():].lstrip()
        if after and after[0] in '月年号日':
            return None
        return float(m.group(1))
    return None


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    amount = parse_amount_from_text(goal)

    if any(kw in goal for kw in ["记账", "记一笔", "入账"]):
        if amount and amount > 0:
            source = re.sub(r'[¥￥]?\s*\d+\.?\d*\s*[元块]?', '', goal)
            is_expense = any(kw in goal for kw in ["支出", "花费", "开销", "成本", "费用"])
            if is_expense:
                for kw in ["记账", "记一笔", "入账", "支出", "花费", "开销", "成本", "费用", "帮我", "的"]:
                    source = source.replace(kw, "")
                source = source.strip().strip("，。、的") or "未注明用途"
                return record_expense(amount, source)
            else:
                for kw in ["记账", "记一笔", "入账", "收入", "帮我", "的"]:
                    source = source.replace(kw, "")
                source = source.strip().strip("，。、的") or "未注明来源"
                return record_income(amount, source)
        return {"success": False, "error": "请指定记账金额，如：记账3000元咨询费"}

    if any(kw in goal for kw in ["收入", "赚", "收到", "到账", "付款"]):
        if amount:
            source = re.sub(r'[¥￥]?\s*\d+\.?\d*\s*[元块]?', '', goal)
            for kw in ["收入", "赚了", "收到", "到账", "付款", "帮我记一笔", "元", "块", "¥", "￥"]:
                source = source.replace(kw, "")
            source = source.strip().strip("，。、的") or "未注明来源"
            return record_income(amount, source)
        return {"success": False, "error": "未能识别金额，请明确指定（如：记一笔收入3000元）"}

    if any(kw in goal for kw in ["支出", "花了", "买了", "花费"]):
        if amount:
            source = re.sub(r'[¥￥]?\s*\d+\.?\d*\s*[元块]?', '', goal)
            for kw in ["支出", "花了", "买了", "花费", "帮我记一笔", "元", "块", "¥", "￥"]:
                source = source.replace(kw, "")
            source = source.strip().strip("，。、的") or "未注明用途"
            return record_expense(amount, source)
        return {"success": False, "error": "未能识别金额"}

    if any(kw in goal for kw in ["报表", "月报", "赚了多少", "花了多少", "利润", "经营"]):
        year_month = ""
        m = re.search(r'(\d{4})年(\d{1,2})月', goal)
        if m:
            year_month = f"{m.group(1)}-{int(m.group(2)):02d}"
        else:
            m = re.search(r'(\d{1,2})月', goal)
            if m:
                month = int(m.group(1))
                if 1 <= month <= 12:
                    year_month = f"{time.strftime('%Y')}-{month:02d}"
        return get_monthly_report(year_month)

    if any(kw in goal for kw in ["趋势", "走势", "近"]):
        return {"success": True, "trend": get_trend()}

    if any(kw in goal for kw in ["分类", "类别"]):
        cats = list_categories()
        return {"success": True, "categories": cats}

    return {"success": False, "error": "未能识别财务操作，请说'记一笔收入/支出'或'看月度报表'"}
