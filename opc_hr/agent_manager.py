#!/usr/bin/env python3
"""
Agent档案管理器

提供Agent档案管理、绩效记录、能力评估等功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from data_storage import DatabaseManager, AgentRecord


class AgentManager:
    """Agent档案管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化Agent档案管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 绩效评估权重配置
        self.performance_weights = {
            "task_completion_rate": 0.4,  # 任务完成率权重
            "response_time": 0.2,  # 响应时间权重
            "quality_score": 0.3,  # 质量评分权重
            "collaboration_score": 0.1   # 协作评分权重
        }
    
    def create_agent_profile(self, agent_id: str, name: str, department: str, 
                            role: str = "", skills: List[str] = None) -> bool:
        """创建Agent档案
        
        Args:
            agent_id: Agent ID
            name: Agent名称
            department: 所属部门
            role: 角色
            skills: 技能列表
            
        Returns:
            是否创建成功
        """
        try:
            agent = AgentRecord(
                id=agent_id,
                name=name,
                department=department,
                role=role,
                skills=json.dumps(skills or []),
                performance_score=0.0,
                tasks_completed=0,
                tasks_in_progress=0,
                created_at=time.time(),
                updated_at=time.time()
            )
            
            if self.db_manager.save_agent(agent):
                self.logger.info(f"Agent档案已创建: {agent_id}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"创建Agent档案失败: {e}")
            return False
    
    def update_agent_performance(self, agent_id: str, task_completed: bool = False,
                                 response_time: float = None, quality_score: float = None,
                                 collaboration_score: float = None) -> bool:
        """更新Agent绩效记录
        
        Args:
            agent_id: Agent ID
            task_completed: 是否完成任务
            response_time: 响应时间（秒）
            quality_score: 质量评分（0-100）
            collaboration_score: 协作评分（0-100）
            
        Returns:
            是否更新成功
        """
        try:
            agent = self.db_manager.get_agent_by_id(agent_id)
            
            if not agent:
                self.logger.error(f"Agent不存在: {agent_id}")
                return False
            
            # 更新任务统计
            if task_completed:
                agent.tasks_completed += 1
                if agent.tasks_in_progress > 0:
                    agent.tasks_in_progress -= 1
            
            # 更新绩效评分
            new_score = self._calculate_performance_score(
                agent, task_completed, response_time, quality_score, collaboration_score
            )
            agent.performance_score = new_score
            
            # 更新时间戳
            agent.updated_at = time.time()
            
            # 保存更新
            if self.db_manager.save_agent(agent):
                self.logger.debug(f"Agent绩效已更新: {agent_id}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"更新Agent绩效失败: {e}")
            return False
    
    def assign_task_to_agent(self, agent_id: str) -> bool:
        """分配任务给Agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            是否分配成功
        """
        try:
            agent = self.db_manager.get_agent_by_id(agent_id)
            
            if not agent:
                self.logger.error(f"Agent不存在: {agent_id}")
                return False
            
            # 增加进行中任务数
            agent.tasks_in_progress += 1
            agent.updated_at = time.time()
            
            return self.db_manager.save_agent(agent)
            
        except Exception as e:
            self.logger.error(f"分配任务失败: {e}")
            return False
    
    def get_agent_performance_report(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取Agent绩效报告
        
        Args:
            agent_id: Agent ID
            
        Returns:
            绩效报告字典
        """
        try:
            agent = self.db_manager.get_agent_by_id(agent_id)
            
            if not agent:
                return None
            
            # 计算各项绩效指标
            total_tasks = agent.tasks_completed + agent.tasks_in_progress
            completion_rate = (agent.tasks_completed / total_tasks * 100) if total_tasks > 0 else 0
            
            # 获取技能列表
            skills = json.loads(agent.skills) if agent.skills else []
            
            # 构建报告
            report = {
                "agent_id": agent.id,
                "name": agent.name,
                "department": agent.department,
                "role": agent.role,
                "skills": skills,
                "performance_score": agent.performance_score,
                "tasks_completed": agent.tasks_completed,
                "tasks_in_progress": agent.tasks_in_progress,
                "completion_rate": round(completion_rate, 2),
                "performance_level": self._get_performance_level(agent.performance_score),
                "created_at": datetime.fromtimestamp(agent.created_at).strftime('%Y-%m-%d %H:%M:%S'),
                "updated_at": datetime.fromtimestamp(agent.updated_at).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"获取Agent绩效报告失败: {e}")
            return None
    
    def get_department_agents_report(self, department: str) -> List[Dict[str, Any]]:
        """获取部门所有Agent的绩效报告
        
        Args:
            department: 部门名称
            
        Returns:
            Agent绩效报告列表
        """
        try:
            agents = self.db_manager.get_agents_by_department(department)
            
            reports = []
            for agent in agents:
                report = self.get_agent_performance_report(agent.id)
                if report:
                    reports.append(report)
            
            # 按绩效评分排序
            reports.sort(key=lambda x: x["performance_score"], reverse=True)
            
            return reports
            
        except Exception as e:
            self.logger.error(f"获取部门Agent报告失败: {e}")
            return []
    
    def get_top_performers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取绩效最高的Agent
        
        Args:
            limit: 返回数量限制
            
        Returns:
            Agent绩效报告列表
        """
        try:
            # 这里需要实现获取所有Agent的方法
            # 暂时返回空列表
            return []
            
        except Exception as e:
            self.logger.error(f"获取顶级Agent失败: {e}")
            return []
    
    def evaluate_agent_capability(self, agent_id: str, task_type: str) -> float:
        """评估Agent对特定任务的能力
        
        Args:
            agent_id: Agent ID
            task_type: 任务类型
            
        Returns:
            能力评分（0-100）
        """
        try:
            agent = self.db_manager.get_agent_by_id(agent_id)
            
            if not agent:
                return 0.0
            
            # 基础能力评分（基于绩效评分）
            base_score = agent.performance_score * 0.6
            
            # 技能匹配评分
            skills = json.loads(agent.skills) if agent.skills else []
            skill_match_score = self._calculate_skill_match(skills, task_type) * 0.3
            
            # 负载评分（任务越少越好）
            load_score = max(0, 100 - agent.tasks_in_progress * 10) * 0.1
            
            total_score = base_score + skill_match_score + load_score
            
            return min(total_score, 100.0)
            
        except Exception as e:
            self.logger.error(f"评估Agent能力失败: {e}")
            return 0.0
    
    def recommend_agent_for_task(self, task_type: str, department: str = None) -> Optional[str]:
        """为任务推荐最合适的Agent
        
        Args:
            task_type: 任务类型
            department: 部门限制（可选）
            
        Returns:
            推荐的Agent ID
        """
        try:
            # 获取候选Agent列表
            if department:
                agents = self.db_manager.get_agents_by_department(department)
            else:
                # 这里需要实现获取所有Agent的方法
                agents = []
            
            if not agents:
                return None
            
            # 评估每个Agent的能力
            best_agent_id = None
            best_score = 0.0
            
            for agent in agents:
                score = self.evaluate_agent_capability(agent.id, task_type)
                if score > best_score:
                    best_score = score
                    best_agent_id = agent.id
            
            return best_agent_id
            
        except Exception as e:
            self.logger.error(f"推荐Agent失败: {e}")
            return None
    
    def _calculate_performance_score(self, agent: AgentRecord, task_completed: bool,
                                    response_time: float, quality_score: float,
                                    collaboration_score: float) -> float:
        """计算综合绩效评分
        
        Args:
            agent: Agent记录对象
            task_completed: 是否完成任务
            response_time: 响应时间
            quality_score: 质量评分
            collaboration_score: 协作评分
            
        Returns:
            综合绩效评分（0-100）
        """
        try:
            # 任务完成率评分
            total_tasks = agent.tasks_completed + agent.tasks_in_progress
            if task_completed:
                total_tasks += 1
            completion_rate = (agent.tasks_completed / total_tasks) if total_tasks > 0 else 0
            completion_score = completion_rate * 100
            
            # 响应时间评分（响应时间越短越好）
            if response_time is not None:
                # 假设最佳响应时间为1秒，最差为60秒
                time_score = max(0, 100 - (response_time / 60) * 100)
            else:
                time_score = 50  # 默认中等评分
            
            # 质量评分
            quality = quality_score if quality_score is not None else 70
            
            # 协作评分
            collaboration = collaboration_score if collaboration_score is not None else 70
            
            # 加权计算总分
            total_score = (
                completion_score * self.performance_weights["task_completion_rate"] +
                time_score * self.performance_weights["response_time"] +
                quality * self.performance_weights["quality_score"] +
                collaboration * self.performance_weights["collaboration_score"]
            )
            
            return min(total_score, 100.0)
            
        except Exception as e:
            self.logger.error(f"计算绩效评分失败: {e}")
            return 0.0
    
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
    
    def _calculate_skill_match(self, skills: List[str], task_type: str) -> float:
        """计算技能匹配度
        
        Args:
            skills: 技能列表
            task_type: 任务类型
            
        Returns:
            匹配度评分（0-100）
        """
        try:
            if not skills:
                return 50.0  # 没有技能信息，返回中等评分
            
            # 简单的关键词匹配
            task_keywords = task_type.lower().split()
            match_count = 0
            
            for skill in skills:
                skill_lower = skill.lower()
                for keyword in task_keywords:
                    if keyword in skill_lower:
                        match_count += 1
                        break
            
            match_rate = match_count / len(task_keywords) if task_keywords else 0
            return match_rate * 100
            
        except Exception as e:
            self.logger.error(f"计算技能匹配度失败: {e}")
            return 0.0
