"""[FROZEN v0.3.0] This skill is frozen and not actively maintained.

Frozen on: 2026-06-19
Reason: v0.3.0 product focus contraction (13→3 core skills)
Revival: See docs/spec/SKILL_FREEZE_LIST.md for revival conditions
"""

import logging
import time
from typing import Any, Dict, Optional, cast

from opc_manager.data_manager import execute_query, execute_write, gen_id, init_db
from opc_manager.skill_models import SkillContext
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

PRICING_METHODS = {
    "成本定价": {
        "formula": "价格 = 成本 × (1 + 利润率)",
        "description": "基于成本加成，适合成本结构清晰的服务",
        "default_margin": 0.3,
    },
    "价值定价": {
        "formula": "价格 = 客户感知价值 × 折扣系数",
        "description": "基于客户获得的价值，适合差异化服务",
        "default_margin": 0.5,
    },
    "竞争定价": {
        "formula": "价格 = 市场均价 × 定位系数",
        "description": "基于竞品定价，适合同质化市场",
        "default_margin": 0.0,
    },
    "小时费率": {
        "formula": "价格 = 时薪 × 预估工时",
        "description": "基于时间投入，适合咨询/培训/开发",
        "default_margin": 0.0,
    },
}

_DEFAULT_HOURLY_RATES = {
    "咨询": {"junior": 200, "mid": 500, "senior": 1000, "expert": 2000},
    "设计": {"junior": 150, "mid": 400, "senior": 800, "expert": 1500},
    "开发": {"junior": 200, "mid": 500, "senior": 1000, "expert": 2000},
    "培训": {"junior": 300, "mid": 800, "senior": 1500, "expert": 3000},
    "通用": {"junior": 200, "mid": 500, "senior": 1000, "expert": 2000},
}


def _load_hourly_benchmarks() -> dict:
    try:
        from opc_manager.utils import load_json_data

        return load_json_data("data/knowledge/pricing_benchmarks.json")
    except Exception as e:
        logger.debug("[PricingSkill] Load pricing benchmarks failed: %s", e)
        return dict(_DEFAULT_HOURLY_RATES)


HOURLY_RATE_BENCHMARKS = _load_hourly_benchmarks()


def calculate_pricing(
    method: str,
    service_type: str = "通用",
    cost: float = 0,
    hours: float = 0,
    market_avg: float = 0,
    level: str = "mid",
) -> Dict[str, Any]:
    if method not in PRICING_METHODS:
        return {
            "success": False,
            "error": f"不支持的方法: {method}，可选: {list(PRICING_METHODS.keys())}",
        }

    cfg = PRICING_METHODS[method]
    result = {"method": method, "formula": cfg["formula"]}

    if method == "成本定价":
        if cost <= 0:
            return {"success": False, "error": "成本定价法需要提供cost参数"}
        margin = cfg["default_margin"]
        price = cost * (1 + cast(float, margin))
        result.update(
            {
                "cost": cost,
                "margin": f"{cast(float, margin)*100:.0f}%",
                "price": round(price, 2),
            }
        )

    elif method == "价值定价":
        if cost <= 0:
            return {
                "success": False,
                "error": "价值定价法需要提供cost参数(作为最低参考)",
            }
        value_multiplier = cast(float, cfg["default_margin"]) + 1.0
        perceived_value = cost * 2.5
        price = perceived_value * value_multiplier
        result.update(
            {
                "base_cost": cost,
                "perceived_value": round(perceived_value, 2),
                "value_multiplier": f"{value_multiplier:.1f}x",
                "price": round(price, 2),
            }
        )

    elif method == "竞争定价":
        if market_avg <= 0:
            return {"success": False, "error": "竞争定价法需要提供market_avg参数"}
        position_factor = 1.0
        price = market_avg * position_factor
        result.update(
            {"market_avg": market_avg, "position": "市场均价", "price": round(price, 2)}
        )

    elif method == "小时费率":
        if hours <= 0:
            return {"success": False, "error": "小时费率法需要提供hours参数"}
        rates = HOURLY_RATE_BENCHMARKS.get(service_type, HOURLY_RATE_BENCHMARKS["通用"])
        rate = rates.get(level, rates["mid"])
        price = rate * hours
        result.update(
            {
                "hourly_rate": rate,
                "hours": hours,
                "level": level,
                "service_type": service_type,
                "price": round(price, 2),
            }
        )

    AuditLogger.log(
        "pricing_calculated", {"method": method, "price": result.get("price", 0)}
    )

    return {
        "success": True,
        "method": method,
        "formula": cfg["formula"],
        "description": cfg["description"],
        "price": result.get("price", 0),
        "detail": result,
        "message": f"建议定价: ¥{result.get('price', 0):.2f}（{method}法）",
    }


def get_hourly_benchmarks(service_type: str = "") -> Dict[str, Any]:
    if service_type and service_type in HOURLY_RATE_BENCHMARKS:
        return {
            "success": True,
            "service_type": service_type,
            "rates": HOURLY_RATE_BENCHMARKS[service_type],
        }
    return {
        "success": True,
        "all_rates": HOURLY_RATE_BENCHMARKS,
        "service_types": list(HOURLY_RATE_BENCHMARKS.keys()),
    }


def save_pricing_record(
    name: str, method: str, price: float, note: str = ""
) -> Dict[str, Any]:
    if not name.strip():
        return {"success": False, "error": "定价记录名称不能为空"}
    if price <= 0:
        return {"success": False, "error": "价格必须大于0"}

    record_id = gen_id()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        execute_write(
            "INSERT INTO pricing_records (id,name,method,price,note,created_at) VALUES (?,?,?,?,?,?)",
            (record_id, name, method, price, note, now),
        )
    except Exception as e:
        logger.warning("pricing_skill.save_pricing_record write failed: %s", e)
        return {"success": False, "error": f"保存失败: {e}"}

    AuditLogger.log("pricing_saved", {"id": record_id, "name": name, "price": price})
    return {
        "success": True,
        "id": record_id,
        "message": f"定价记录已保存: {name} ¥{price:.2f}",
    }


def list_pricing_records() -> Dict[str, Any]:
    try:
        rows = execute_query("SELECT * FROM pricing_records ORDER BY created_at DESC")
    except Exception as e:
        logger.warning("pricing_skill.list_pricing_records query failed: %s", e)
        return {"success": True, "records": [], "count": 0}

    records = [dict(row) for row in rows]
    return {"success": True, "records": records, "count": len(records)}


def suggest_pricing(
    service_type: str = "通用", cost: float = 0, hours: float = 0
) -> Dict[str, Any]:
    suggestions = []
    if cost > 0:
        r = calculate_pricing("成本定价", cost=cost)
        if r["success"]:
            suggestions.append(
                {"method": "成本定价", "price": r["price"], "formula": r["formula"]}
            )
        r = calculate_pricing("价值定价", cost=cost)
        if r["success"]:
            suggestions.append(
                {"method": "价值定价", "price": r["price"], "formula": r["formula"]}
            )
    if hours > 0:
        for level in ["mid", "senior"]:
            r = calculate_pricing(
                "小时费率", service_type=service_type, hours=hours, level=level
            )
            if r["success"]:
                suggestions.append(
                    {
                        "method": f"小时费率({level})",
                        "price": r["price"],
                        "detail": r["detail"],
                    }
                )

    if not suggestions:
        rates = HOURLY_RATE_BENCHMARKS.get(service_type, HOURLY_RATE_BENCHMARKS["通用"])
        suggestions.append(
            {
                "method": "行业参考",
                "mid_rate": f"¥{rates['mid']}/小时",
                "senior_rate": f"¥{rates['senior']}/小时",
                "expert_rate": f"¥{rates['expert']}/小时",
            }
        )

    return {
        "success": True,
        "service_type": service_type,
        "suggestions": suggestions,
        "message": f"为{service_type}服务提供{len(suggestions)}种定价建议",
    }


def execute_goal(
    goal: str, _context: Optional[SkillContext] = None, **kwargs: Any
) -> Dict[str, Any]:
    init_db()
    if any(kw in goal for kw in ["参考", "行业", "费率", "时薪"]):
        return get_hourly_benchmarks()

    if any(kw in goal for kw in ["记录", "列表", "历史"]):
        return list_pricing_records()

    if any(kw in goal for kw in ["建议", "怎么定", "如何定", "推荐"]):
        from opc_manager.finance_skill import parse_amount_from_text

        cost = parse_amount_from_text(goal) or 0
        service_type = "通用"
        for st in ["咨询", "培训", "设计", "开发"]:
            if st in goal:
                service_type = st
                break
        return suggest_pricing(service_type=service_type, cost=cost)

    method = "成本定价"
    for m in ["成本定价", "价值定价", "竞争定价", "小时费率"]:
        if m in goal:
            method = m
            break

    from opc_manager.finance_skill import parse_amount_from_text

    amount = parse_amount_from_text(goal) or 0
    if amount > 0:
        return calculate_pricing(method, cost=amount)

    return suggest_pricing()
