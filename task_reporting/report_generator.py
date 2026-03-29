#!/usr/bin/env python3
"""
报告生成器

提供任务进度报告、日报、周报、月报的自动生成功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class ReportConfig:
    """报告配置"""
    report_type: str
    time_range: timedelta
    include_details: bool = True
    include_charts: bool = False
    format: str = "markdown"


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.logger = logging.getLogger(__name__)
        
        # 报告模板
        self.report_templates = {
            "daily": ReportConfig(
                report_type="daily",
                time_range=timedelta(days=1),
                include_details=True,
                include_charts=False,
                format="markdown"
            ),
            "weekly": ReportConfig(
                report_type="weekly",
                time_range=timedelta(weeks=1),
                include_details=True,
                include_charts=True,
                format="markdown"
            ),
            "monthly": ReportConfig(
                report_type="monthly",
                time_range=timedelta(days=30),
                include_details=True,
                include_charts=True,
                format="markdown"
            ),
            "task_completion": ReportConfig(
                report_type="task_completion",
                time_range=timedelta(days=7),
                include_details=True,
                include_charts=False,
                format="markdown"
            )
        }
    
    def generate_daily_report(self, tasks_data: List[Dict[str, Any]], 
                             date: datetime = None) -> Optional[str]:
        """生成日报
        
        Args:
            tasks_data: 任务数据列表
            date: 报告日期（默认为今天）
            
        Returns:
            日报内容
        """
        try:
            if date is None:
                date = datetime.now()
            
            config = self.report_templates["daily"]
            
            # 筛选当天的任务
            daily_tasks = self._filter_tasks_by_time(tasks_data, date, config.time_range)
            
            # 生成报告内容
            report_lines = [
                f"# 日报 - {date.strftime('%Y年%m月%d日')}\n",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            ]
            
            # 概览
            overview = self._generate_overview(daily_tasks)
            report_lines.extend(overview)
            
            # 任务详情
            if config.include_details:
                details = self._generate_task_details(daily_tasks)
                report_lines.extend(details)
            
            # 问题与风险
            issues = self._generate_issues_section(daily_tasks)
            report_lines.extend(issues)
            
            # 明日计划
            tomorrow_plan = self._generate_tomorrow_plan(daily_tasks)
            report_lines.extend(tomorrow_plan)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"生成日报失败: {e}")
            return None
    
    def generate_weekly_report(self, tasks_data: List[Dict[str, Any]],
                              week_start: datetime = None) -> Optional[str]:
        """生成周报
        
        Args:
            tasks_data: 任务数据列表
            week_start: 周开始日期（默认为本周一）
            
        Returns:
            周报内容
        """
        try:
            if week_start is None:
                # 获取本周一
                today = datetime.now()
                week_start = today - timedelta(days=today.weekday())
            
            config = self.report_templates["weekly"]
            
            # 筛选本周的任务
            weekly_tasks = self._filter_tasks_by_time(tasks_data, week_start, config.time_range)
            
            # 生成报告内容
            week_end = week_start + timedelta(days=6)
            report_lines = [
                f"# 周报 - {week_start.strftime('%Y年%m月%d日')} 至 {week_end.strftime('%Y年%m月%d日')}\n",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            ]
            
            # 本周概览
            overview = self._generate_weekly_overview(weekly_tasks)
            report_lines.extend(overview)
            
            # 任务完成情况
            completion_status = self._generate_completion_status(weekly_tasks)
            report_lines.extend(completion_status)
            
            # 任务详情
            if config.include_details:
                details = self._generate_task_details(weekly_tasks)
                report_lines.extend(details)
            
            # 问题与风险
            issues = self._generate_issues_section(weekly_tasks)
            report_lines.extend(issues)
            
            # 下周计划
            next_week_plan = self._generate_next_week_plan(weekly_tasks)
            report_lines.extend(next_week_plan)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"生成周报失败: {e}")
            return None
    
    def generate_monthly_report(self, tasks_data: List[Dict[str, Any]],
                               month_start: datetime = None) -> Optional[str]:
        """生成月报
        
        Args:
            tasks_data: 任务数据列表
            month_start: 月开始日期（默认为本月1日）
            
        Returns:
            月报内容
        """
        try:
            if month_start is None:
                # 获取本月1日
                today = datetime.now()
                month_start = today.replace(day=1)
            
            config = self.report_templates["monthly"]
            
            # 筛选本月的任务
            monthly_tasks = self._filter_tasks_by_time(tasks_data, month_start, config.time_range)
            
            # 生成报告内容
            month_end = month_start + timedelta(days=30)
            report_lines = [
                f"# 月报 - {month_start.strftime('%Y年%m月')}\n",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            ]
            
            # 本月概览
            overview = self._generate_monthly_overview(monthly_tasks)
            report_lines.extend(overview)
            
            # 任务完成情况
            completion_status = self._generate_completion_status(monthly_tasks)
            report_lines.extend(completion_status)
            
            # 绩效分析
            performance_analysis = self._generate_performance_analysis(monthly_tasks)
            report_lines.extend(performance_analysis)
            
            # 任务详情
            if config.include_details:
                details = self._generate_task_details(monthly_tasks)
                report_lines.extend(details)
            
            # 问题与风险
            issues = self._generate_issues_section(monthly_tasks)
            report_lines.extend(issues)
            
            # 下月计划
            next_month_plan = self._generate_next_month_plan(monthly_tasks)
            report_lines.extend(next_month_plan)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"生成月报失败: {e}")
            return None
    
    def generate_task_completion_report(self, task_data: Dict[str, Any]) -> Optional[str]:
        """生成任务完成报告
        
        Args:
            task_data: 任务数据
            
        Returns:
            任务完成报告
        """
        try:
            config = self.report_templates["task_completion"]
            
            # 生成报告内容
            report_lines = [
                f"# 任务完成报告 - {task_data.get('task_name', '未命名任务')}\n",
                f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            ]
            
            # 任务基本信息
            basic_info = self._generate_task_basic_info(task_data)
            report_lines.extend(basic_info)
            
            # 任务时间线
            timeline = self._generate_task_timeline(task_data)
            report_lines.extend(timeline)
            
            # 参与者贡献
            participants = self._generate_participants_contribution(task_data)
            report_lines.extend(participants)
            
            # 成果物列表
            deliverables = self._generate_deliverables_section(task_data)
            report_lines.extend(deliverables)
            
            # 经验总结
            lessons_learned = self._generate_lessons_learned(task_data)
            report_lines.extend(lessons_learned)
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"生成任务完成报告失败: {e}")
            return None
    
    def _filter_tasks_by_time(self, tasks_data: List[Dict[str, Any]], 
                              start_time: datetime, time_range: timedelta) -> List[Dict[str, Any]]:
        """按时间筛选任务
        
        Args:
            tasks_data: 任务数据列表
            start_time: 开始时间
            time_range: 时间范围
            
        Returns:
            筛选后的任务列表
        """
        try:
            end_time = start_time + time_range
            start_timestamp = start_time.timestamp()
            end_timestamp = end_time.timestamp()
            
            filtered_tasks = []
            
            for task in tasks_data:
                task_time = task.get("updated_at", 0)
                if isinstance(task_time, str):
                    task_time = datetime.strptime(task_time, '%Y-%m-%d %H:%M:%S').timestamp()
                
                if start_timestamp <= task_time <= end_timestamp:
                    filtered_tasks.append(task)
            
            return filtered_tasks
            
        except Exception as e:
            self.logger.error(f"筛选任务失败: {e}")
            return []
    
    def _generate_overview(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成概览"""
        lines = ["## 📊 概览\n"]
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        in_progress_tasks = sum(1 for t in tasks if t.get("status") == "in_progress")
        
        lines.append(f"- **总任务数**: {total_tasks}")
        lines.append(f"- **已完成**: {completed_tasks}")
        lines.append(f"- **进行中**: {in_progress_tasks}")
        lines.append(f"- **完成率**: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%")
        lines.append("")
        
        return lines
    
    def _generate_weekly_overview(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成周概览"""
        lines = ["## 📊 本周概览\n"]
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        
        # 按天统计
        daily_stats = {}
        for task in tasks:
            task_date = task.get("updated_at", "")
            if isinstance(task_date, str):
                date_key = task_date.split()[0] if task_date else "未知"
            else:
                date_key = datetime.fromtimestamp(task_date).strftime('%Y-%m-%d')
            
            daily_stats[date_key] = daily_stats.get(date_key, 0) + 1
        
        lines.append(f"- **本周总任务数**: {total_tasks}")
        lines.append(f"- **已完成任务**: {completed_tasks}")
        lines.append(f"- **完成率**: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%")
        lines.append("")
        
        if daily_stats:
            lines.append("### 每日任务分布")
            for date, count in sorted(daily_stats.items()):
                lines.append(f"- {date}: {count} 个任务")
            lines.append("")
        
        return lines
    
    def _generate_monthly_overview(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成月概览"""
        lines = ["## 📊 本月概览\n"]
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        
        # 按周统计
        weekly_stats = {}
        for task in tasks:
            task_date = task.get("updated_at", "")
            if isinstance(task_date, str):
                date_obj = datetime.strptime(task_date.split()[0], '%Y-%m-%d')
            else:
                date_obj = datetime.fromtimestamp(task_date)
            
            week_num = date_obj.isocalendar()[1]
            weekly_stats[week_num] = weekly_stats.get(week_num, 0) + 1
        
        lines.append(f"- **本月总任务数**: {total_tasks}")
        lines.append(f"- **已完成任务**: {completed_tasks}")
        lines.append(f"- **完成率**: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%")
        lines.append("")
        
        if weekly_stats:
            lines.append("### 每周任务分布")
            for week, count in sorted(weekly_stats.items()):
                lines.append(f"- 第{week}周: {count} 个任务")
            lines.append("")
        
        return lines
    
    def _generate_task_details(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成任务详情"""
        lines = ["## 📋 任务详情\n"]
        
        for i, task in enumerate(tasks, 1):
            status_emoji = {"completed": "✅", "in_progress": "🔄", "pending": "⏳"}.get(task.get("status", "pending"), "❓")
            
            lines.append(f"### {i}. {task.get('task_name', '未命名任务')} {status_emoji}")
            lines.append(f"- **状态**: {task.get('status', '未知')}")
            lines.append(f"- **进度**: {task.get('progress', 0)}%")
            lines.append(f"- **更新时间**: {task.get('updated_at', '未知')}")
            
            if task.get("participants"):
                participants_names = [p.get("name", "未知") for p in task["participants"]]
                lines.append(f"- **参与者**: {', '.join(participants_names)}")
            
            lines.append("")
        
        return lines
    
    def _generate_completion_status(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成完成状态"""
        lines = ["## 📈 完成情况\n"]
        
        completed_tasks = [t for t in tasks if t.get("status") == "completed"]
        in_progress_tasks = [t for t in tasks if t.get("status") == "in_progress"]
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        
        if completed_tasks:
            lines.append("### ✅ 已完成任务")
            for task in completed_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        if in_progress_tasks:
            lines.append("### 🔄 进行中任务")
            for task in in_progress_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')} ({task.get('progress', 0)}%)")
            lines.append("")
        
        if pending_tasks:
            lines.append("### ⏳ 待开始任务")
            for task in pending_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        return lines
    
    def _generate_issues_section(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成问题与风险部分"""
        lines = ["## ⚠️ 问题与风险\n"]
        
        # 检查延迟任务
        delayed_tasks = []
        for task in tasks:
            if task.get("status") == "in_progress" and task.get("progress", 0) < 50:
                delayed_tasks.append(task)
        
        if delayed_tasks:
            lines.append("### 延迟风险")
            for task in delayed_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')}: 进度较慢 ({task.get('progress', 0)}%)")
            lines.append("")
        else:
            lines.append("暂无明显问题和风险。\n")
        
        return lines
    
    def _generate_tomorrow_plan(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成明日计划"""
        lines = ["## 📅 明日计划\n"]
        
        in_progress_tasks = [t for t in tasks if t.get("status") == "in_progress"]
        
        if in_progress_tasks:
            lines.append("### 继续推进的任务")
            for task in in_progress_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')} (当前进度: {task.get('progress', 0)}%)")
            lines.append("")
        else:
            lines.append("暂无明确的明日计划。\n")
        
        return lines
    
    def _generate_next_week_plan(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成下周计划"""
        lines = ["## 📅 下周计划\n"]
        
        in_progress_tasks = [t for t in tasks if t.get("status") == "in_progress"]
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        
        if in_progress_tasks:
            lines.append("### 继续推进的任务")
            for task in in_progress_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        if pending_tasks:
            lines.append("### 计划启动的任务")
            for task in pending_tasks[:3]:  # 只显示前3个
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        return lines
    
    def _generate_next_month_plan(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成下月计划"""
        lines = ["## 📅 下月计划\n"]
        
        in_progress_tasks = [t for t in tasks if t.get("status") == "in_progress"]
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        
        if in_progress_tasks:
            lines.append("### 继续推进的任务")
            for task in in_progress_tasks:
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        if pending_tasks:
            lines.append("### 计划启动的任务")
            for task in pending_tasks[:5]:  # 只显示前5个
                lines.append(f"- {task.get('task_name', '未命名任务')}")
            lines.append("")
        
        return lines
    
    def _generate_performance_analysis(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """生成绩效分析"""
        lines = ["## 📊 绩效分析\n"]
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.get("status") == "completed")
        avg_progress = sum(t.get("progress", 0) for t in tasks) / total_tasks if total_tasks > 0 else 0
        
        lines.append(f"- **任务完成率**: {(completed_tasks/total_tasks*100) if total_tasks > 0 else 0:.1f}%")
        lines.append(f"- **平均进度**: {avg_progress:.1f}%")
        lines.append(f"- **任务总数**: {total_tasks}")
        lines.append("")
        
        return lines
    
    def _generate_task_basic_info(self, task_data: Dict[str, Any]) -> List[str]:
        """生成任务基本信息"""
        lines = ["## 📋 基本信息\n"]
        
        lines.append(f"- **任务名称**: {task_data.get('task_name', '未命名任务')}")
        lines.append(f"- **任务状态**: {task_data.get('status', '未知')}")
        lines.append(f"- **完成进度**: {task_data.get('progress', 0)}%")
        lines.append(f"- **创建时间**: {task_data.get('created_at', '未知')}")
        lines.append(f"- **开始时间**: {task_data.get('started_at', '未知')}")
        lines.append(f"- **完成时间**: {task_data.get('completed_at', '未知')}")
        lines.append("")
        
        return lines
    
    def _generate_task_timeline(self, task_data: Dict[str, Any]) -> List[str]:
        """生成任务时间线"""
        lines = ["## ⏱️ 任务时间线\n"]
        
        # 这里可以添加更详细的时间线信息
        lines.append("任务时间线记录了任务从创建到完成的所有重要事件。")
        lines.append("")
        
        return lines
    
    def _generate_participants_contribution(self, task_data: Dict[str, Any]) -> List[str]:
        """生成参与者贡献"""
        lines = ["## 👥 参与者贡献\n"]
        
        participants = task_data.get("participants", [])
        
        if participants:
            for participant in participants:
                lines.append(f"- **{participant.get('name', '未知')}** ({participant.get('role', '参与者')})")
        else:
            lines.append("暂无参与者信息。")
        
        lines.append("")
        
        return lines
    
    def _generate_deliverables_section(self, task_data: Dict[str, Any]) -> List[str]:
        """生成成果物部分"""
        lines = ["## 📦 成果物\n"]
        
        # 这里可以添加成果物列表
        lines.append("任务成果物将在任务完成后自动生成。")
        lines.append("")
        
        return lines
    
    def _generate_lessons_learned(self, task_data: Dict[str, Any]) -> List[str]:
        """生成经验总结"""
        lines = ["## 💡 经验总结\n"]
        
        lines.append("### 成功经验")
        lines.append("- 任务规划合理，执行顺利")
        lines.append("")
        
        lines.append("### 改进建议")
        lines.append("- 可以进一步优化任务分配和执行流程")
        lines.append("")
        
        return lines
