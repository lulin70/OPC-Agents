#!/usr/bin/env python3
"""
部门管理器

提供部门管理、绩效统计、资源优化等功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from data_storage import DatabaseManager


class DepartmentManager:
    """部门管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化部门管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 部门配置
        self.departments = {
            "总经办": {"description": "总裁办公室", "priority": 1},
            "人事部": {"description": "人力资源管理", "priority": 2},
            "财务部": {"description": "财务管理", "priority": 3},
            "市场部": {"description": "市场营销", "priority": 4},
            "产品部": {"description": "产品管理", "priority": 5},
            "技术部": {"description": "技术研发", "priority": 6},
            "运营部": {"description": "运营管理", "priority": 7},
            "客服部": {"description": "客户服务", "priority": 8}
        }
    
    def get_department_statistics(self, department: str) -> Optional[Dict[str, Any]]:
        """获取部门统计信息
        
        Args:
            department: 部门名称
            
        Returns:
            部门统计信息字典
        """
        try:
            # 获取部门所有Agent
            agents = self.db_manager.get_agents_by_department(department)
            
            if not agents:
                return None
            
            # 统计基本信息
            total_agents = len(agents)
            active_agents = sum(1 for agent in agents if agent.tasks_in_progress > 0)
            
            # 统计任务信息
            total_tasks_completed = sum(agent.tasks_completed for agent in agents)
            total_tasks_in_progress = sum(agent.tasks_in_progress for agent in agents)
            
            # 计算平均绩效
            avg_performance = sum(agent.performance_score for agent in agents) / total_agents
            
            # 统计技能分布
            all_skills = []
            for agent in agents:
                skills = json.loads(agent.skills) if agent.skills else []
                all_skills.extend(skills)
            
            skill_distribution = {}
            for skill in all_skills:
                skill_distribution[skill] = skill_distribution.get(skill, 0) + 1
            
            # 构建统计报告
            statistics = {
                "department": department,
                "description": self.departments.get(department, {}).get("description", ""),
                "priority": self.departments.get(department, {}).get("priority", 99),
                "total_agents": total_agents,
                "active_agents": active_agents,
                "inactive_agents": total_agents - active_agents,
                "total_tasks_completed": total_tasks_completed,
                "total_tasks_in_progress": total_tasks_in_progress,
                "avg_performance_score": round(avg_performance, 2),
                "performance_level": self._get_performance_level(avg_performance),
                "top_skills": sorted(skill_distribution.items(), key=lambda x: x[1], reverse=True)[:10],
                "agent_utilization": round((active_agents / total_agents * 100), 2) if total_agents > 0 else 0,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return statistics
            
        except Exception as e:
            self.logger.error(f"获取部门统计信息失败: {e}")
            return None
    
    def get_all_departments_report(self) -> List[Dict[str, Any]]:
        """获取所有部门的报告
        
        Returns:
            部门报告列表
        """
        try:
            reports = []
            
            for department in self.departments.keys():
                report = self.get_department_statistics(department)
                if report:
                    reports.append(report)
            
            # 按优先级排序
            reports.sort(key=lambda x: x["priority"])
            
            return reports
            
        except Exception as e:
            self.logger.error(f"获取所有部门报告失败: {e}")
            return []
    
    def analyze_department_efficiency(self, department: str) -> Optional[Dict[str, Any]]:
        """分析部门效率
        
        Args:
            department: 部门名称
            
        Returns:
            效率分析报告
        """
        try:
            stats = self.get_department_statistics(department)
            
            if not stats:
                return None
            
            # 计算效率指标
            efficiency_metrics = {
                "task_completion_rate": (
                    stats["total_tasks_completed"] / 
                    (stats["total_tasks_completed"] + stats["total_tasks_in_progress"]) * 100
                ) if (stats["total_tasks_completed"] + stats["total_tasks_in_progress"]) > 0 else 0,
                
                "agent_utilization": stats["agent_utilization"],
                
                "performance_score": stats["avg_performance_score"],
                
                "resource_efficiency": self._calculate_resource_efficiency(stats)
            }
            
            # 生成改进建议
            recommendations = self._generate_efficiency_recommendations(efficiency_metrics)
            
            analysis = {
                "department": department,
                "efficiency_metrics": efficiency_metrics,
                "recommendations": recommendations,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"分析部门效率失败: {e}")
            return None
    
    def get_cross_department_collaboration(self) -> List[Dict[str, Any]]:
        """获取跨部门协作统计
        
        Returns:
            跨部门协作统计列表
        """
        try:
            # 这里需要实现跨部门任务的统计
            # 暂时返回空列表
            return []
            
        except Exception as e:
            self.logger.error(f"获取跨部门协作统计失败: {e}")
            return []
    
    def optimize_department_resources(self, department: str) -> Optional[Dict[str, Any]]:
        """优化部门资源配置
        
        Args:
            department: 部门名称
            
        Returns:
            优化建议
        """
        try:
            stats = self.get_department_statistics(department)
            
            if not stats:
                return None
            
            optimization_suggestions = []
            
            # 检查Agent利用率
            if stats["agent_utilization"] < 50:
                optimization_suggestions.append({
                    "type": "underutilization",
                    "priority": "high",
                    "suggestion": f"部门Agent利用率较低（{stats['agent_utilization']}%），建议增加任务分配或调整人员配置",
                    "metric": stats["agent_utilization"]
                })
            elif stats["agent_utilization"] > 90:
                optimization_suggestions.append({
                    "type": "overutilization",
                    "priority": "high",
                    "suggestion": f"部门Agent利用率过高（{stats['agent_utilization']}%），建议增加人员或优化工作流程",
                    "metric": stats["agent_utilization"]
                })
            
            # 检查绩效评分
            if stats["avg_performance_score"] < 70:
                optimization_suggestions.append({
                    "type": "performance",
                    "priority": "medium",
                    "suggestion": f"部门平均绩效较低（{stats['avg_performance_score']}），建议进行培训或流程优化",
                    "metric": stats["avg_performance_score"]
                })
            
            # 检查技能分布
            if len(stats["top_skills"]) < 3:
                optimization_suggestions.append({
                    "type": "skill_diversity",
                    "priority": "low",
                    "suggestion": "部门技能多样性不足，建议培养或引入新技能",
                    "metric": len(stats["top_skills"])
                })
            
            optimization = {
                "department": department,
                "current_status": stats,
                "optimization_suggestions": optimization_suggestions,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return optimization
            
        except Exception as e:
            self.logger.error(f"优化部门资源配置失败: {e}")
            return None
    
    def get_department_workload_balance(self) -> Dict[str, Any]:
        """获取部门工作负载平衡情况
        
        Returns:
            工作负载平衡报告
        """
        try:
            departments_stats = []
            
            for department in self.departments.keys():
                stats = self.get_department_statistics(department)
                if stats:
                    departments_stats.append(stats)
            
            if not departments_stats:
                return {}
            
            # 计算平均负载
            avg_utilization = sum(d["agent_utilization"] for d in departments_stats) / len(departments_stats)
            
            # 识别负载不平衡的部门
            overloaded = [d for d in departments_stats if d["agent_utilization"] > avg_utilization * 1.2]
            underloaded = [d for d in departments_stats if d["agent_utilization"] < avg_utilization * 0.8]
            
            balance_report = {
                "avg_utilization": round(avg_utilization, 2),
                "overloaded_departments": [
                    {"department": d["department"], "utilization": d["agent_utilization"]}
                    for d in overloaded
                ],
                "underloaded_departments": [
                    {"department": d["department"], "utilization": d["agent_utilization"]}
                    for d in underloaded
                ],
                "balance_score": self._calculate_balance_score(departments_stats),
                "recommendations": self._generate_balance_recommendations(overloaded, underloaded),
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return balance_report
            
        except Exception as e:
            self.logger.error(f"获取部门工作负载平衡失败: {e}")
            return {}
    
    def _get_performance_level(self, score: float) -> str:
        """获取绩效等级
        
        Args:
            score: 绩效评分
            
        Returns:
            绩效等级描述
        """
        if score >= 90:
            return "优秀"
        elif score >= 80:
            return "良好"
        elif score >= 70:
            return "中等"
        elif score >= 60:
            return "及格"
        else:
            return "需改进"
    
    def _calculate_resource_efficiency(self, stats: Dict[str, Any]) -> float:
        """计算资源效率
        
        Args:
            stats: 部门统计信息
            
        Returns:
            资源效率评分（0-100）
        """
        try:
            # 综合考虑Agent利用率、绩效评分和任务完成率
            utilization_score = stats["agent_utilization"]
            performance_score = stats["avg_performance_score"]
            
            completion_rate = (
                stats["total_tasks_completed"] / 
                (stats["total_tasks_completed"] + stats["total_tasks_in_progress"]) * 100
            ) if (stats["total_tasks_completed"] + stats["total_tasks_in_progress"]) > 0 else 0
            
            # 加权计算
            efficiency = (
                utilization_score * 0.3 +
                performance_score * 0.4 +
                completion_rate * 0.3
            )
            
            return round(efficiency, 2)
            
        except Exception as e:
            self.logger.error(f"计算资源效率失败: {e}")
            return 0.0
    
    def _generate_efficiency_recommendations(self, metrics: Dict[str, float]) -> List[str]:
        """生成效率改进建议
        
        Args:
            metrics: 效率指标
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if metrics["task_completion_rate"] < 70:
            recommendations.append("任务完成率较低，建议优化任务分配和执行流程")
        
        if metrics["agent_utilization"] < 60:
            recommendations.append("Agent利用率不足，建议增加任务或调整人员配置")
        elif metrics["agent_utilization"] > 90:
            recommendations.append("Agent负载过高，建议增加人员或优化工作流程")
        
        if metrics["performance_score"] < 70:
            recommendations.append("绩效评分偏低，建议进行培训和流程优化")
        
        if metrics["resource_efficiency"] < 60:
            recommendations.append("整体资源效率较低，建议全面优化资源配置")
        
        if not recommendations:
            recommendations.append("部门运行状况良好，继续保持当前工作状态")
        
        return recommendations
    
    def _calculate_balance_score(self, departments_stats: List[Dict[str, Any]]) -> float:
        """计算负载平衡评分
        
        Args:
            departments_stats: 部门统计列表
            
        Returns:
            平衡评分（0-100）
        """
        try:
            if not departments_stats:
                return 0.0
            
            utilizations = [d["agent_utilization"] for d in departments_stats]
            avg_utilization = sum(utilizations) / len(utilizations)
            
            # 计算标准差
            variance = sum((u - avg_utilization) ** 2 for u in utilizations) / len(utilizations)
            std_dev = variance ** 0.5
            
            # 标准差越小，平衡越好
            # 假设标准差为0时得100分，标准差为50时得0分
            balance_score = max(0, 100 - std_dev * 2)
            
            return round(balance_score, 2)
            
        except Exception as e:
            self.logger.error(f"计算平衡评分失败: {e}")
            return 0.0
    
    def _generate_balance_recommendations(self, overloaded: List[Dict], underloaded: List[Dict]) -> List[str]:
        """生成负载平衡建议
        
        Args:
            overloaded: 负载过重的部门列表
            underloaded: 负载不足的部门列表
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if overloaded and underloaded:
            recommendations.append(
                f"建议将部分任务从{overloaded[0]['department']}转移到{underloaded[0]['department']}，以平衡工作负载"
            )
        
        if len(overloaded) > 1:
            recommendations.append(
                f"多个部门负载过重，建议考虑增加人员或优化流程"
            )
        
        if len(underloaded) > 1:
            recommendations.append(
                f"多个部门负载不足，建议重新评估人员配置或增加任务分配"
            )
        
        return recommendations
