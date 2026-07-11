import logging
import re
import time
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)


def record_income(
    amount: float, source: str, category: str = "咨询费", date: str = "", note: str = ""
) -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not date:
        date = time.strftime("%Y-%m-%d")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    record_id = gen_id()
    try:
        execute_write(
            "INSERT INTO finance_records "
            "(id,type,amount,category,source,date,note,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (record_id, "income", amount, category, source, date, note, now),
        )
        AuditLogger.log(
            "finance_income", {"id": record_id, "amount": amount, "source": source}
        )
        return {
            "success": True,
            "id": record_id,
            "message": f"已记录收入 ¥{amount:.2f} ({source})",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def record_expense(
    amount: float,
    source: str,
    category: str = "其他支出",
    date: str = "",
    note: str = "",
) -> Dict[str, Any]:
    if amount <= 0:
        return {"success": False, "error": "金额必须大于0"}
    if not date:
        date = time.strftime("%Y-%m-%d")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    record_id = gen_id()
    try:
        execute_write(
            "INSERT INTO finance_records "
            "(id,type,amount,category,source,date,note,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (record_id, "expense", amount, category, source, date, note, now),
        )
        AuditLogger.log(
            "finance_expense", {"id": record_id, "amount": amount, "source": source}
        )
        return {
            "success": True,
            "id": record_id,
            "message": f"已记录支出 ¥{amount:.2f} ({source})",
        }
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
        return {
            "success": True,
            "year_month": year_month,
            "income": 0,
            "expense": 0,
            "profit": 0,
            "details": [],
        }

    income = 0.0
    expense = 0.0
    income_by_cat: Dict[str, float] = {}
    expense_by_cat: Dict[str, float] = {}

    for r in rows:
        if r["type"] == "income":
            income += r["amount"]
            income_by_cat[r["category"]] = (
                income_by_cat.get(r["category"], 0) + r["amount"]
            )
        else:
            expense += r["amount"]
            expense_by_cat[r["category"]] = (
                expense_by_cat.get(r["category"], 0) + r["amount"]
            )

    prev_month_rows = execute_query(
        "SELECT type, amount FROM finance_records WHERE date LIKE ?",
        (f"{_prev_month(year_month)}%",),
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
        "income_by_category": {
            k: round(v, 2)
            for k, v in sorted(income_by_cat.items(), key=lambda x: -x[1])
        },
        "expense_by_category": {
            k: round(v, 2)
            for k, v in sorted(expense_by_cat.items(), key=lambda x: -x[1])
        },
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
        results.append(
            {
                "year_month": ym,
                "income": round(income, 2),
                "expense": round(expense, 2),
                "profit": round(income - expense, 2),
            }
        )
    return results


def list_categories(record_type: str = "") -> List[Dict[str, Any]]:
    if record_type:
        return execute_query(
            "SELECT * FROM finance_categories WHERE type=? ORDER BY name",
            (record_type,),
        )
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
        rows = execute_write(
            "DELETE FROM finance_records WHERE id=? AND type='income'", (record_id,)
        )
    else:
        latest = execute_query(
            "SELECT id FROM finance_records WHERE type='income' ORDER BY created_at DESC LIMIT 1"
        )
        if latest:
            rows = execute_write(
                "DELETE FROM finance_records WHERE id=?", (latest[0]["id"],)
            )
        else:
            rows = 0
    if rows == 0:
        logger.warning("[finance] undo_record_income: no record found to delete")
    return {
        "success": rows > 0,
        "message": "收入记录已撤销" if rows > 0 else "未找到可撤销的记录",
    }


def undo_record_expense(record_id=None, **kwargs):
    init_db()
    if record_id:
        rows = execute_write(
            "DELETE FROM finance_records WHERE id=? AND type='expense'", (record_id,)
        )
    else:
        latest = execute_query(
            "SELECT id FROM finance_records WHERE type='expense' ORDER BY created_at DESC LIMIT 1"
        )
        if latest:
            rows = execute_write(
                "DELETE FROM finance_records WHERE id=?", (latest[0]["id"],)
            )
        else:
            rows = 0
    if rows == 0:
        logger.warning("[finance] undo_record_expense: no record found to delete")
    return {
        "success": rows > 0,
        "message": "支出记录已撤销" if rows > 0 else "未找到可撤销的记录",
    }


def parse_amount_from_text(text: str) -> Optional[float]:
    patterns = [
        r"[¥￥]\s*(\d+\.?\d*)",
        r"(\d+\.?\d*)\s*元",
        r"(\d+\.?\d*)\s*块",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return float(m.group(1))
    m = re.search(r"(\d+\.?\d*)", text)
    if m:
        after = text[m.end() :].lstrip()
        if after and after[0] in "月年号日":
            return None
        return float(m.group(1))
    return None


_AMOUNT_RE = r"[¥￥]?\s*\d+\.?\d*\s*[元块]?"


def _clean_source(text: str, keywords: list) -> str:
    """Remove keywords and surrounding punctuation from source text."""
    for kw in keywords:
        text = text.replace(kw, "")
    return text.strip().strip("，。、的")


def _handle_accounting(goal: str, amount: Optional[float]) -> Dict[str, Any]:
    """Handle 记账/记一笔/入账 intent."""
    if not amount or amount <= 0:
        return {"success": False, "error": "请指定记账金额，如：记账3000元咨询费"}
    source = re.sub(_AMOUNT_RE, "", goal)
    if any(kw in goal for kw in ["支出", "花费", "开销", "成本", "费用"]):
        source = _clean_source(
            source,
            [
                "记账",
                "记一笔",
                "入账",
                "支出",
                "花费",
                "开销",
                "成本",
                "费用",
                "帮我",
                "的",
            ],
        )
        return record_expense(amount, source or "未注明用途")
    source = _clean_source(source, ["记账", "记一笔", "入账", "收入", "帮我", "的"])
    return record_income(amount, source or "未注明来源")


def _handle_income(goal: str, amount: Optional[float]) -> Dict[str, Any]:
    """Handle 收入/赚/收到/到账/付款 intent."""
    if not amount:
        return {
            "success": False,
            "error": "未能识别金额，请明确指定（如：记一笔收入3000元）",
        }
    source = re.sub(_AMOUNT_RE, "", goal)
    source = _clean_source(
        source,
        ["收入", "赚了", "收到", "到账", "付款", "帮我记一笔", "元", "块", "¥", "￥"],
    )
    return record_income(amount, source or "未注明来源")


def _handle_expense(goal: str, amount: Optional[float]) -> Dict[str, Any]:
    """Handle 支出/花了/买了/花费 intent."""
    if not amount:
        return {"success": False, "error": "未能识别金额"}
    source = re.sub(_AMOUNT_RE, "", goal)
    source = _clean_source(
        source,
        ["支出", "花了", "买了", "花费", "帮我记一笔", "元", "块", "¥", "￥"],
    )
    return record_expense(amount, source or "未注明用途")


def _parse_year_month(goal: str) -> str:
    """Extract YYYY-MM from goal text, return empty string if not found."""
    m = re.search(r"(\d{4})年(\d{1,2})月", goal)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"(\d{1,2})月", goal)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return f"{time.strftime('%Y')}-{month:02d}"
    return ""


def _handle_report(goal: str, _amount: Optional[float] = None) -> Dict[str, Any]:
    """Handle 报表/月报 intent."""
    return get_monthly_report(_parse_year_month(goal))


def _handle_trend(_goal: str, _amount: Optional[float] = None) -> Dict[str, Any]:
    """Handle 趋势/走势 intent."""
    return {"success": True, "trend": get_trend()}


def _handle_categories(_goal: str, _amount: Optional[float] = None) -> Dict[str, Any]:
    """Handle 分类/类别 intent."""
    return {"success": True, "categories": list_categories()}


# Intent dispatch table: (keywords, handler)
_FINANCE_INTENT_DISPATCH: List[tuple] = [
    (["记账", "记一笔", "入账"], _handle_accounting),
    (["收入", "赚", "收到", "到账", "付款"], _handle_income),
    (["支出", "花了", "买了", "花费"], _handle_expense),
    (["报表", "月报", "赚了多少", "花了多少", "利润", "经营"], _handle_report),
    (["趋势", "走势", "近"], _handle_trend),
    (["分类", "类别"], _handle_categories),
]


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    amount = parse_amount_from_text(goal)
    for keywords, handler in _FINANCE_INTENT_DISPATCH:
        if any(kw in goal for kw in keywords):
            return handler(goal, amount)
    return {
        "success": False,
        "error": "未能识别财务操作，请说'记一笔收入/支出'或'看月度报表'",
    }
