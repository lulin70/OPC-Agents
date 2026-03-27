#!/usr/bin/env python3
"""
Task management for OPC Manager
"""

import time
from typing import Dict, List, Optional, Any

class TaskManager:
    """Task manager for OPC-Agents system"""
    
    def __init__(self, communication_manager):
        """Initialize the Task Manager"""
        self.communication_manager = communication_manager
    
    def decompose_task(self, task: str, time_horizon: str = "medium") -> List[Dict[str, str]]:
        """Decompose a task into smaller tasks based on time horizon
        
        Args:
            task: The task to decompose
            time_horizon: Time horizon, can be "short", "medium", or "long"
            
        Returns:
            List of decomposed tasks
        """
        print(f"[总裁办] 分解任务: {task} (时间范围: {time_horizon})")
        
        # 增强的任务分解逻辑
        decomposed_tasks = []
        
        # 战略规划阶段
        decomposed_tasks.append({
            "task": f"{task} - 战略规划",
            "department": "executive_office",
            "agent": "strategy_planner",
            "priority": "high",
            "time_horizon": "short",
            "description": "制定详细的战略计划，包括目标、资源需求和时间线"
        })
        
        # 资源评估阶段
        decomposed_tasks.append({
            "task": f"{task} - 资源评估",
            "department": "executive_office",
            "agent": "resource_optimizer",
            "priority": "high",
            "time_horizon": "short",
            "description": "评估所需的人力、财力和技术资源，确保资源充足"
        })
        
        # 风险评估阶段
        decomposed_tasks.append({
            "task": f"{task} - 风险评估",
            "department": "executive_office",
            "agent": "risk_manager",
            "priority": "medium",
            "time_horizon": "short",
            "description": "识别潜在风险并制定应对策略"
        })
        
        # 执行阶段
        decomposed_tasks.append({
            "task": f"{task} - 执行实施",
            "department": "operations",
            "agent": "project_coordinator",
            "priority": "high",
            "time_horizon": "medium",
            "description": "协调各部门执行任务，确保按计划进行"
        })
        
        # 外部关系协调
        decomposed_tasks.append({
            "task": f"{task} - 外部关系协调",
            "department": "executive_office",
            "agent": "external_relations_officer",
            "priority": "medium",
            "time_horizon": "medium",
            "description": "协调与外部合作伙伴的关系，确保资源和支持"
        })
        
        # 监控与调整
        decomposed_tasks.append({
            "task": f"{task} - 监控与调整",
            "department": "executive_office",
            "agent": "operations_coordinator",
            "priority": "medium",
            "time_horizon": "medium",
            "description": "实时监控任务进展，根据实际情况调整计划"
        })
        
        # 评估与总结
        decomposed_tasks.append({
            "task": f"{task} - 评估与总结",
            "department": "executive_office",
            "agent": "report_specialist",
            "priority": "medium",
            "time_horizon": "long",
            "description": "评估任务完成情况，总结经验教训，形成报告"
        })
        
        for decomposed_task in decomposed_tasks:
            print(f"[总裁办] 分解任务: {decomposed_task['task']} (部门: {decomposed_task['department']}, 代理: {decomposed_task['agent']}, 优先级: {decomposed_task['priority']})")
        
        return decomposed_tasks
    
    def track_progress(self, tasks: List[str] = None) -> Dict[str, Any]:
        """Track progress of tasks
        
        Args:
            tasks: List of task IDs (if None, track all tasks)
            
        Returns:
            Progress information
        """
        print("[总裁办] 跟踪任务进度")
        
        progress_info = {
            "overview": {},
            "tasks": {},
            "by_department": {},
            "by_priority": {},
            "by_time_horizon": {},
            "insights": [],
            "recommendations": []
        }
        
        # 获取任务列表
        if tasks:
            task_list = tasks
        else:
            all_tasks = self.get_all_tasks()
            task_list = list(all_tasks.keys())
        
        total_progress = 0
        task_count = 0
        status_counts = {}
        department_progress = {}
        priority_progress = {}
        time_horizon_progress = {}
        delayed_tasks = []
        at_risk_tasks = []
        
        for task_id in task_list:
            task_status = self.get_task_status(task_id)
            if task_status:
                status = task_status.get("status")
                progress = task_status.get("progress", 0)
                department = task_status.get("department", "unknown")
                priority = task_status.get("priority", "medium")
                time_horizon = task_status.get("time_horizon", "medium")
                created_at = task_status.get("created_at")
                updated_at = task_status.get("updated_at")
                
                # 任务详情
                progress_info["tasks"][task_id] = {
                    "status": status,
                    "progress": progress,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "department": department,
                    "priority": priority,
                    "time_horizon": time_horizon
                }
                
                # 统计状态
                if status not in status_counts:
                    status_counts[status] = 0
                status_counts[status] += 1
                
                # 部门进度
                if department not in department_progress:
                    department_progress[department] = {"total": 0, "progress": 0, "tasks": []}
                department_progress[department]["total"] += 1
                department_progress[department]["progress"] += progress
                department_progress[department]["tasks"].append({
                    "task_id": task_id,
                    "status": status,
                    "progress": progress,
                    "priority": priority
                })
                
                # 优先级进度
                if priority not in priority_progress:
                    priority_progress[priority] = {"total": 0, "progress": 0}
                priority_progress[priority]["total"] += 1
                priority_progress[priority]["progress"] += progress
                
                # 时间范围进度
                if time_horizon not in time_horizon_progress:
                    time_horizon_progress[time_horizon] = {"total": 0, "progress": 0}
                time_horizon_progress[time_horizon]["total"] += 1
                time_horizon_progress[time_horizon]["progress"] += progress
                
                # 识别延迟任务
                if status == "in_progress" and progress < 50:
                    # 检查任务是否长时间未更新
                    if updated_at:
                        time_since_update = time.time() - updated_at
                        if time_since_update > 86400:  # 超过24小时
                            delayed_tasks.append({
                                "task_id": task_id,
                                "progress": progress,
                                "time_since_update": time_since_update
                            })
                
                # 识别高风险任务
                if priority == "high" and status != "completed" and progress < 30:
                    at_risk_tasks.append({
                        "task_id": task_id,
                        "progress": progress,
                        "status": status
                    })
                
                total_progress += progress
                task_count += 1
                
                print(f"[总裁办] 任务 {task_id} 进度: {progress}%, 状态: {status}, 部门: {department}")
            else:
                progress_info["tasks"][task_id] = {
                    "status": "not_found",
                    "progress": 0
                }
                print(f"[总裁办] 任务 {task_id} 未找到")
        
        # 计算平均进度
        average_progress = total_progress / task_count if task_count > 0 else 0
        
        # 计算部门平均进度
        for department, data in department_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
            # 按优先级排序任务
            data["tasks"].sort(key=lambda x: (x["priority"] == "high", x["progress"]))
        
        # 计算优先级平均进度
        for priority, data in priority_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
        
        # 计算时间范围平均进度
        for time_horizon, data in time_horizon_progress.items():
            data["average_progress"] = data["progress"] / data["total"] if data["total"] > 0 else 0
        
        # 填充概览信息
        progress_info["overview"] = {
            "total_tasks": task_count,
            "completed_tasks": status_counts.get("completed", 0),
            "in_progress_tasks": status_counts.get("in_progress", 0),
            "pending_tasks": status_counts.get("pending", 0),
            "average_progress": average_progress,
            "status_counts": status_counts,
            "delayed_tasks": len(delayed_tasks),
            "at_risk_tasks": len(at_risk_tasks)
        }
        
        # 生成智能洞察
        if delayed_tasks:
            progress_info["insights"].append(f"发现 {len(delayed_tasks)} 个任务进度延迟，需要关注")
        
        if at_risk_tasks:
            progress_info["insights"].append(f"发现 {len(at_risk_tasks)} 个高优先级任务进度低于30%，存在风险")
        
        # 分析部门表现
        if department_progress:
            lowest_dept = min(department_progress.items(), key=lambda x: x[1]["average_progress"])
            if lowest_dept[1]["average_progress"] < 0.5:
                progress_info["insights"].append(f"部门 '{lowest_dept[0]}' 平均进度较低 ({lowest_dept[1]['average_progress']:.1f}%)，需要支持")
        
        # 分析优先级任务
        high_priority_progress = priority_progress.get("high", {}).get("average_progress", 0)
        if high_priority_progress < 0.6:
            progress_info["insights"].append("高优先级任务平均进度较低，建议优先资源投入")
        
        # 生成建议
        if delayed_tasks:
            progress_info["recommendations"].append("及时跟进延迟任务，分析原因并提供必要支持")
        
        if at_risk_tasks:
            progress_info["recommendations"].append("重点关注高优先级任务，确保资源充足")
        
        if average_progress < 0.5:
            progress_info["recommendations"].append("整体进度偏低，建议调整工作计划和资源分配")
        
        progress_info["recommendations"].extend([
            "定期召开进度评审会议，及时解决问题",
            "建立任务预警机制，提前识别风险",
            "优化任务分解，确保任务可执行性",
            "加强跨部门协作，提高整体效率"
        ])
        
        progress_info["by_department"] = department_progress
        progress_info["by_priority"] = priority_progress
        progress_info["by_time_horizon"] = time_horizon_progress
        
        return progress_info
    
    def generate_report(self, period: str = "weekly", config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate report for a specific period
        
        Args:
            period: Report period, can be "daily", "weekly", or "monthly"
            config: Configuration dictionary
            
        Returns:
            Report information
        """
        print(f"[总裁办] 生成 {period} 报告")
        
        # 获取所有任务
        all_tasks = self.get_all_tasks()
        
        # 统计任务状态
        status_counts = {}
        department_tasks = {}
        priority_tasks = {}
        time_horizon_tasks = {}
        
        total_progress = 0
        task_count = 0
        
        for task_id, task_info in all_tasks.items():
            status = task_info.get("status", "unknown")
            progress = task_info.get("progress", 0)
            department = task_info.get("department", "unknown")
            priority = task_info.get("priority", "medium")
            time_horizon = task_info.get("time_horizon", "medium")
            
            # 状态统计
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
            
            # 部门统计
            if department not in department_tasks:
                department_tasks[department] = {"count": 0, "progress": 0}
            department_tasks[department]["count"] += 1
            department_tasks[department]["progress"] += progress
            
            # 优先级统计
            if priority not in priority_tasks:
                priority_tasks[priority] = {"count": 0, "progress": 0}
            priority_tasks[priority]["count"] += 1
            priority_tasks[priority]["progress"] += progress
            
            # 时间范围统计
            if time_horizon not in time_horizon_tasks:
                time_horizon_tasks[time_horizon] = {"count": 0, "progress": 0}
            time_horizon_tasks[time_horizon]["count"] += 1
            time_horizon_tasks[time_horizon]["progress"] += progress
            
            total_progress += progress
            task_count += 1
        
        # 计算平均进度
        average_progress = total_progress / task_count if task_count > 0 else 0
        
        # 计算部门平均进度
        department_averages = {}
        for department, data in department_tasks.items():
            department_averages[department] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 计算优先级平均进度
        priority_averages = {}
        for priority, data in priority_tasks.items():
            priority_averages[priority] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 计算时间范围平均进度
        time_horizon_averages = {}
        for time_horizon, data in time_horizon_tasks.items():
            time_horizon_averages[time_horizon] = data["progress"] / data["count"] if data["count"] > 0 else 0
        
        # 生成智能洞察
        insights = []
        if task_count > 0:
            # 识别瓶颈部门
            bottleneck_department = min(department_averages.items(), key=lambda x: x[1]) if department_averages else None
            if bottleneck_department:
                insights.append(f"部门 '{bottleneck_department[0]}' 进度较低 ({bottleneck_department[1]:.1f}%)，可能需要额外支持")
            
            # 识别高优先级任务状态
            high_priority_progress = priority_averages.get("high", 0)
            if high_priority_progress < 50:
                insights.append("高优先级任务进度落后，建议优先关注")
            
            # 识别时间范围分布
            short_term_progress = time_horizon_averages.get("short", 0)
            if short_term_progress < 70:
                insights.append("短期任务进度不足，可能影响整体计划")
        
        # 生成建议
        recommendations = []
        if insights:
            recommendations.append("根据瓶颈分析，调整资源分配")
        recommendations.extend([
            "建立更频繁的进度检查机制",
            "优化任务分解和分配流程",
            "加强跨部门协作和沟通",
            "建立明确的任务优先级体系",
            "定期评估和调整战略目标"
        ])
        
        report = {
            "period": period,
            "generated_at": time.time(),
            "company_name": config.get('core', {}).get('name', 'OPC Agency') if config else 'OPC Agency',
            "task_summary": {
                "total_tasks": task_count,
                "status_counts": status_counts,
                "average_progress": average_progress
            },
            "department_analysis": {
                "department_tasks": department_tasks,
                "department_averages": department_averages
            },
            "priority_analysis": {
                "priority_tasks": priority_tasks,
                "priority_averages": priority_averages
            },
            "time_horizon_analysis": {
                "time_horizon_tasks": time_horizon_tasks,
                "time_horizon_averages": time_horizon_averages
            },
            "key_achievements": [
                "完成项目规划和启动",
                "建立有效的任务管理体系",
                "优化资源分配和利用",
                "提高团队协作效率"
            ],
            "challenges": [
                "资源有限，需要更高效利用",
                "市场竞争激烈，需要差异化策略",
                "技术更新迭代快，需要持续学习",
                "一人公司的管理复杂度增加"
            ],
            "insights": insights,
            "recommendations": recommendations,
            "next_steps": [
                "实施资源优化计划",
                "加强高优先级任务监控",
                "推进跨部门协作机制",
                "定期回顾和调整战略"
            ]
        }
        
        print(f"[总裁办] 报告生成完成，共 {task_count} 个任务，平均进度: {average_progress:.1f}%")
        print(f"[总裁办] 智能洞察: {insights}")
        
        return report
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            agent: 负责的代理
            initial_status: 初始状态，默认为"pending"
        """
        self.communication_manager.create_task(task_id, task_name, agent, initial_status)
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
        """
        self.communication_manager.update_task_status(task_id, status, progress)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        return self.communication_manager.get_task_status(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态
        
        Returns:
            所有任务的状态信息
        """
        return self.communication_manager.get_all_tasks()
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务
        
        Args:
            agent: 代理名称
            
        Returns:
            代理的任务列表
        """
        return self.communication_manager.get_tasks_by_agent(agent)
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务
        
        Args:
            status: 任务状态
            
        Returns:
            指定状态的任务列表
        """
        return self.communication_manager.get_tasks_by_status(status)
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的历史记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务历史记录列表
        """
        return self.communication_manager.get_task_history(task_id)
    
    def get_all_task_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务的历史记录
        
        Returns:
            所有任务的历史记录
        """
        return self.communication_manager.get_all_task_history()
