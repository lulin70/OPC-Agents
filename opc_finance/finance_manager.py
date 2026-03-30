#!/usr/bin/env python3
"""
财务部模块 - Token使用监控与消费报告

负责监控所有Agent的Token使用情况，计算消费成本，
生成定时报告，并在超出预算时发出告警。
"""

import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class FinanceManager:
    """财务部管理器"""
    
    PRICING = {
        "glm": {"input": 0.1, "output": 0.1},
        "openai": {"input": 2.5, "output": 10.0},
        "anthropic": {"input": 3.0, "output": 15.0},
        "google": {"input": 1.25, "output": 5.0},
        "local": {"input": 0.0, "output": 0.0},
    }
    
    def __init__(self, communication_manager=None):
        self.logger = logging.getLogger('OPC-Agents.Finance')
        self.communication_manager = communication_manager
        self.daily_budget = 50.0
        self.monthly_budget = 1000.0
        self.alert_threshold = 0.8
        self.cost_records: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self._last_report_time = 0
        self._report_interval = 3600
    
    def get_token_usage(self) -> Dict[str, Any]:
        """获取Token使用统计"""
        if self.communication_manager:
            raw_usage = self.communication_manager.get_token_usage()
        else:
            raw_usage = {}
        
        total_tokens = sum(raw_usage.values())
        estimated_cost = self._estimate_cost(total_tokens, "glm")
        
        return {
            "total_tokens": total_tokens,
            "by_agent": raw_usage,
            "estimated_cost_cny": round(estimated_cost, 4),
            "daily_budget": self.daily_budget,
            "monthly_budget": self.monthly_budget,
            "budget_usage_percent": round(estimated_cost / self.daily_budget * 100, 1) if self.daily_budget > 0 else 0
        }
    
    def get_consumption_report(self, period: str = "daily") -> Dict[str, Any]:
        """生成消费报告
        
        Args:
            period: 报告周期 daily/weekly/monthly
        """
        usage = self.get_token_usage()
        now = datetime.now()
        
        if period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = "今日"
        elif period == "weekly":
            start = now - timedelta(days=7)
            period_label = "本周"
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_label = "本月"
        
        period_records = [
            r for r in self.cost_records
            if r.get("timestamp", 0) >= start.timestamp()
        ]
        
        period_cost = sum(r.get("cost", 0) for r in period_records)
        period_tokens = sum(r.get("tokens", 0) for r in period_records)
        period_requests = len(period_records)
        
        top_agents = {}
        for r in period_records:
            agent = r.get("agent", "unknown")
            if agent not in top_agents:
                top_agents[agent] = {"tokens": 0, "cost": 0, "requests": 0}
            top_agents[agent]["tokens"] += r.get("tokens", 0)
            top_agents[agent]["cost"] += r.get("cost", 0)
            top_agents[agent]["requests"] += 1
        
        sorted_agents = sorted(
            top_agents.items(),
            key=lambda x: x[1]["cost"],
            reverse=True
        )[:10]
        
        budget_status = "正常"
        budget_limit = self.daily_budget if period == "daily" else self.monthly_budget
        if period_cost >= budget_limit:
            budget_status = "已超支"
        elif period_cost >= budget_limit * self.alert_threshold:
            budget_status = "接近预算"
        
        report = {
            "period": period,
            "period_label": period_label,
            "generated_at": now.isoformat(),
            "total_tokens": period_tokens + usage["total_tokens"],
            "total_cost_cny": round(period_cost + usage["estimated_cost_cny"], 4),
            "total_requests": period_requests,
            "budget_limit_cny": budget_limit,
            "budget_status": budget_status,
            "budget_usage_percent": round(
                (period_cost + usage["estimated_cost_cny"]) / budget_limit * 100, 1
            ) if budget_limit > 0 else 0,
            "top_agents": [
                {"agent": name, **stats}
                for name, stats in sorted_agents
            ],
            "alerts": self.alerts[-5:] if self.alerts else []
        }
        
        self._last_report_time = time.time()
        self.logger.info(f"生成{period_label}消费报告: {report['total_cost_cny']}元, {report['total_tokens']}tokens")
        return report
    
    def record_usage(self, agent: str, model: str, input_tokens: int, output_tokens: int):
        """记录一次使用"""
        total_tokens = input_tokens + output_tokens
        cost = self._estimate_cost(input_tokens, model) + self._estimate_cost(output_tokens, model, is_output=True)
        
        record = {
            "agent": agent,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "timestamp": time.time()
        }
        self.cost_records.append(record)
        
        recent_cost = sum(
            r.get("cost", 0) for r in self.cost_records
            if r.get("timestamp", 0) >= (time.time() - 86400)
        )
        
        if recent_cost >= self.daily_budget * self.alert_threshold and recent_cost < self.daily_budget:
            alert = {
                "type": "warning",
                "message": f"今日消费已达预算的{self.alert_threshold*100:.0f}%",
                "current_cost": round(recent_cost, 2),
                "budget": self.daily_budget,
                "timestamp": datetime.now().isoformat()
            }
            if not self.alerts or self.alerts[-1].get("message") != alert["message"]:
                self.alerts.append(alert)
                self.logger.warning(f"财务告警: {alert['message']}")
        elif recent_cost >= self.daily_budget:
            alert = {
                "type": "critical",
                "message": f"今日消费已超出预算！当前: {round(recent_cost,2)}元, 预算: {self.daily_budget}元",
                "current_cost": round(recent_cost, 2),
                "budget": self.daily_budget,
                "timestamp": datetime.now().isoformat()
            }
            if not self.alerts or self.alerts[-1].get("type") != "critical":
                self.alerts.append(alert)
                self.logger.error(f"财务严重告警: {alert['message']}")
    
    def _estimate_cost(self, tokens: int, model: str, is_output: bool = False) -> float:
        """估算Token成本（人民币）"""
        pricing = self.PRICING.get(model, self.PRICING["glm"])
        price_per_1k = pricing.get("output" if is_output else "input", 0.1)
        return tokens / 1000.0 * price_per_1k
    
    def set_budget(self, daily: Optional[float] = None, monthly: Optional[float] = None):
        """设置预算"""
        if daily is not None:
            self.daily_budget = daily
        if monthly is not None:
            self.monthly_budget = monthly
        self.logger.info(f"预算已更新: 日预算={self.daily_budget}元, 月预算={self.monthly_budget}元")
    
    def get_alerts(self) -> List[Dict[str, Any]]:
        """获取告警列表"""
        return self.alerts
    
    def get_finance_dashboard(self) -> Dict[str, Any]:
        """获取财务仪表盘数据"""
        daily_report = self.get_consumption_report("daily")
        monthly_report = self.get_consumption_report("monthly")
        
        return {
            "current_usage": self.get_token_usage(),
            "daily_report": daily_report,
            "monthly_report": monthly_report,
            "recent_alerts": self.alerts[-10:],
            "pricing": self.PRICING
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fm = FinanceManager()
    fm.record_usage("chief_executive", "glm", 500, 200)
    fm.record_usage("market_analyst", "glm", 300, 150)
    fm.record_usage("developer", "glm", 1000, 500)
    
    print("=== 财务仪表盘 ===")
    import json
    print(json.dumps(fm.get_finance_dashboard(), indent=2, default=str, ensure_ascii=False))
