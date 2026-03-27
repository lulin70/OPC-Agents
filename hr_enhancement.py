#!/usr/bin/env python3
"""
人事部增强功能模块
实现Agent招聘、Skill管理、生命周期管理等功能
"""

import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# 导入自动优化器
try:
    from auto_optimizer import AutoOptimizer
except ImportError:
    AutoOptimizer = None


class AgentStatus(Enum):
    """Agent状态"""
    RECRUITING = "recruiting"  # 招聘中
    ONBOARDING = "onboarding"  # 入职中
    ACTIVE = "active"          # 活跃
    TRAINING = "training"      # 培训中
    PERFORMANCE_REVIEW = "performance_review"  # 绩效评估中
    PROMOTED = "promoted"      # 已晋升
    RESIGNED = "resigned"      # 已离职


class SkillLevel(Enum):
    """技能水平"""
    BEGINNER = "beginner"      # 初级
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"      # 高级
    EXPERT = "expert"          # 专家


class DepartmentType(Enum):
    """部门类型"""
    EXECUTIVE = "executive"    # 总裁办
    DESIGN = "design"          # 设计部门
    DEVELOPMENT = "development"  # 开发部门
    MARKETING = "marketing"    # 市场部门
    RESEARCH = "research"      # 调研部门
    TESTING = "testing"        # 测试部门
    OPERATION = "operation"    # 运营部门
    FINANCE = "finance"        # 财务部门
    HR = "hr"                  # 人事部门
    OTHER = "other"            # 其他部门


@dataclass
class Skill:
    """技能定义"""
    id: str
    name: str
    description: str
    category: str
    level: SkillLevel
    related_skills: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class AgentProfile:
    """Agent档案"""
    id: str
    name: str
    department: str
    role: str
    status: AgentStatus
    skills: Dict[str, SkillLevel] = field(default_factory=dict)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    performance: List[Dict[str, Any]] = field(default_factory=list)
    hire_date: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JobRequirement:
    """职位需求"""
    id: str
    title: str
    department: str
    description: str
    required_skills: Dict[str, SkillLevel] = field(default_factory=dict)
    preferred_skills: Dict[str, SkillLevel] = field(default_factory=dict)
    responsibilities: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "open"  # open, closed, filled


class HREnhancement:
    """人事部增强功能"""
    
    def __init__(self, opc_manager):
        """初始化人事部增强功能"""
        self.opc_manager = opc_manager
        self.agent_profiles: Dict[str, AgentProfile] = {}
        self.skills: Dict[str, Skill] = {}
        self.job_requirements: Dict[str, JobRequirement] = {}
        self.agent_marketplace: List[Dict[str, Any]] = []
        self.auto_optimizer = None
        
        # 初始化技能库
        self._initialize_skill_library()
        # 初始化现有Agent档案
        self._initialize_agent_profiles()
        # 初始化自动优化器
        self._initialize_auto_optimizer()
        
        print("[HR增强] 人事部增强功能初始化完成")
    
    def _initialize_skill_library(self):
        """初始化技能库"""
        # 核心技能
        core_skills = [
            Skill(
                id="skill_1",
                name="项目管理",
                description="项目规划、执行和监控",
                category="管理",
                level=SkillLevel.INTERMEDIATE
            ),
            Skill(
                id="skill_2",
                name="编程",
                description="软件开发和编程",
                category="技术",
                level=SkillLevel.INTERMEDIATE
            ),
            Skill(
                id="skill_3",
                name="设计",
                description="UI/UX设计",
                category="创意",
                level=SkillLevel.INTERMEDIATE
            ),
            Skill(
                id="skill_4",
                name="市场分析",
                description="市场调研和分析",
                category="市场",
                level=SkillLevel.INTERMEDIATE
            ),
            Skill(
                id="skill_5",
                name="沟通协调",
                description="跨部门沟通和协调",
                category="软技能",
                level=SkillLevel.INTERMEDIATE
            )
        ]
        
        for skill in core_skills:
            self.skills[skill.id] = skill
        
        print(f"[HR增强] 初始化技能库，共 {len(self.skills)} 个技能")
    
    def _initialize_agent_profiles(self):
        """初始化现有Agent档案"""
        # 从OPC Manager获取现有Agent
        departments = self.opc_manager.get_departments()
        
        for department in departments:
            agents = self.opc_manager.get_official_agent_by_department(department)
            
            for agent_info in agents:
                agent_id = agent_info.get('name', f"agent_{uuid.uuid4()}")
                agent_name = agent_info.get('frontmatter', {}).get('name', agent_id)
                
                # 创建Agent档案
                profile = AgentProfile(
                    id=agent_id,
                    name=agent_name,
                    department=department,
                    role=agent_info.get('frontmatter', {}).get('description', '未指定'),
                    status=AgentStatus.ACTIVE,
                    metadata=agent_info
                )
                
                # 自动分析技能
                self._analyze_agent_skills(profile)
                
                self.agent_profiles[agent_id] = profile
        
        print(f"[HR增强] 初始化Agent档案，共 {len(self.agent_profiles)} 个Agent")
    
    def _analyze_agent_skills(self, profile: AgentProfile):
        """分析Agent技能"""
        # 基于部门和角色分析技能
        department_skills = {
            "design": ["设计", "创意", "用户体验"],
            "development": ["编程", "软件开发", "测试"],
            "marketing": ["市场分析", "营销", "沟通协调"],
            "research": ["研究", "数据分析", "报告撰写"],
            "finance": ["财务分析", "预算管理", "报表制作"],
            "hr": ["人才招聘", "培训管理", "绩效评估"]
        }
        
        skills = department_skills.get(profile.department, [])
        
        for skill_name in skills:
            # 查找或创建技能
            skill_id = f"skill_{skill_name.lower().replace(' ', '_')}"
            if skill_id not in self.skills:
                self.skills[skill_id] = Skill(
                    id=skill_id,
                    name=skill_name,
                    description=f"{skill_name}相关技能",
                    category="通用",
                    level=SkillLevel.BEGINNER
                )
            
            # 分配技能水平
            profile.skills[skill_id] = SkillLevel.INTERMEDIATE
    
    def create_job_requirement(self, title: str, department: str, 
                             description: str, required_skills: Dict[str, str],
                             responsibilities: List[str]) -> JobRequirement:
        """创建职位需求"""
        job_id = f"job_{int(time.time())}"
        
        # 转换技能水平
        required_skill_levels = {}
        for skill_name, level in required_skills.items():
            # 查找或创建技能
            skill_id = f"skill_{skill_name.lower().replace(' ', '_')}"
            if skill_id not in self.skills:
                self.skills[skill_id] = Skill(
                    id=skill_id,
                    name=skill_name,
                    description=f"{skill_name}相关技能",
                    category="通用",
                    level=SkillLevel.BEGINNER
                )
            
            # 转换技能水平
            try:
                skill_level = SkillLevel(level.lower())
                required_skill_levels[skill_id] = skill_level
            except ValueError:
                required_skill_levels[skill_id] = SkillLevel.BEGINNER
        
        job = JobRequirement(
            id=job_id,
            title=title,
            department=department,
            description=description,
            required_skills=required_skill_levels,
            responsibilities=responsibilities
        )
        
        self.job_requirements[job_id] = job
        print(f"[HR增强] 创建职位需求: {title} (ID: {job_id})")
        
        # 自动寻找匹配的Agent
        self.find_matching_agents(job_id)
        
        return job
    
    def find_matching_agents(self, job_id: str) -> List[Dict[str, Any]]:
        """寻找匹配的Agent"""
        job = self.job_requirements.get(job_id)
        if not job:
            return []
        
        matches = []
        
        # 搜索现有Agent
        for agent_id, profile in self.agent_profiles.items():
            if profile.department != job.department:
                continue
            
            # 计算技能匹配度
            match_score = self._calculate_skill_match(profile, job)
            
            if match_score > 0.5:
                matches.append({
                    "agent_id": agent_id,
                    "agent_name": profile.name,
                    "match_score": match_score,
                    "status": profile.status.value
                })
        
        # 从外部市场寻找Agent
        marketplace_matches = self._search_agent_marketplace(job)
        matches.extend(marketplace_matches)
        
        # 按匹配度排序
        matches.sort(key=lambda x: x["match_score"], reverse=True)
        
        print(f"[HR增强] 为职位 {job.title} 找到 {len(matches)} 个匹配的Agent")
        return matches
    
    def _calculate_skill_match(self, profile: AgentProfile, 
                              job: JobRequirement) -> float:
        """计算技能匹配度"""
        if not job.required_skills:
            return 0.0
        
        total_skills = len(job.required_skills)
        matched_skills = 0
        
        for skill_id, required_level in job.required_skills.items():
            if skill_id in profile.skills:
                agent_level = profile.skills[skill_id]
                # 技能水平匹配度
                level_match = self._calculate_level_match(agent_level, required_level)
                if level_match >= 0.5:
                    matched_skills += 1
        
        return matched_skills / total_skills if total_skills > 0 else 0.0
    
    def _calculate_level_match(self, agent_level: SkillLevel, 
                              required_level: SkillLevel) -> float:
        """计算技能水平匹配度"""
        level_values = {
            SkillLevel.BEGINNER: 1,
            SkillLevel.INTERMEDIATE: 2,
            SkillLevel.ADVANCED: 3,
            SkillLevel.EXPERT: 4
        }
        
        agent_value = level_values.get(agent_level, 1)
        required_value = level_values.get(required_level, 1)
        
        # 技能水平达到或超过要求为1.0，否则按比例计算
        if agent_value >= required_value:
            return 1.0
        return agent_value / required_value
    
    def _search_agent_marketplace(self, job: JobRequirement) -> List[Dict[str, Any]]:
        """从外部市场搜索Agent"""
        # 模拟外部Agent市场
        marketplace_agents = [
            {
                "id": "market_agent_1",
                "name": "高级前端开发",
                "department": "development",
                "skills": {
                    "编程": "advanced",
                    "前端框架": "expert",
                    "UI设计": "intermediate"
                },
                "experience": 3,
                "match_score": 0.85
            },
            {
                "id": "market_agent_2",
                "name": "市场分析师",
                "department": "marketing",
                "skills": {
                    "市场分析": "advanced",
                    "数据可视化": "intermediate",
                    "报告撰写": "expert"
                },
                "experience": 2,
                "match_score": 0.75
            },
            {
                "id": "market_agent_3",
                "name": "UI/UX设计师",
                "department": "design",
                "skills": {
                    "设计": "expert",
                    "用户体验": "advanced",
                    "原型制作": "expert"
                },
                "experience": 4,
                "match_score": 0.9
            }
        ]
        
        # 过滤匹配的Agent
        matches = []
        for agent in marketplace_agents:
            if agent["department"] == job.department:
                matches.append({
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "match_score": agent["match_score"],
                    "status": "available",
                    "source": "marketplace"
                })
        
        return matches
    
    def hire_agent(self, agent_id: str, job_id: str) -> AgentProfile:
        """招聘Agent"""
        # 检查是否是市场Agent
        if agent_id.startswith("market_"):
            # 从市场招聘新Agent
            return self._hire_from_marketplace(agent_id, job_id)
        else:
            # 内部调动
            return self._internal_transfer(agent_id, job_id)
    
    def _hire_from_marketplace(self, agent_id: str, job_id: str) -> AgentProfile:
        """从市场招聘新Agent"""
        job = self.job_requirements.get(job_id)
        if not job:
            raise ValueError(f"职位需求不存在: {job_id}")
        
        # 模拟市场Agent详情
        marketplace_agent = next(
            (agent for agent in self._search_agent_marketplace(job) 
             if agent["agent_id"] == agent_id),
            None
        )
        
        if not marketplace_agent:
            raise ValueError(f"市场Agent不存在: {agent_id}")
        
        # 创建新Agent档案
        new_agent_id = f"agent_{int(time.time())}"
        profile = AgentProfile(
            id=new_agent_id,
            name=marketplace_agent["agent_name"],
            department=job.department,
            role=job.title,
            status=AgentStatus.ONBOARDING
        )
        
        # 转换技能
        for skill_name, level_str in marketplace_agent.get("skills", {}).items():
            skill_id = f"skill_{skill_name.lower().replace(' ', '_')}"
            if skill_id not in self.skills:
                self.skills[skill_id] = Skill(
                    id=skill_id,
                    name=skill_name,
                    description=f"{skill_name}相关技能",
                    category="市场",
                    level=SkillLevel.BEGINNER
                )
            
            try:
                profile.skills[skill_id] = SkillLevel(level_str)
            except ValueError:
                profile.skills[skill_id] = SkillLevel.BEGINNER
        
        # 添加到Agent档案
        self.agent_profiles[new_agent_id] = profile
        
        # 更新职位状态
        job.status = "filled"
        
        print(f"[HR增强] 从市场招聘Agent: {profile.name} (ID: {new_agent_id})")
        return profile
    
    def _internal_transfer(self, agent_id: str, job_id: str) -> AgentProfile:
        """内部调动Agent"""
        profile = self.agent_profiles.get(agent_id)
        job = self.job_requirements.get(job_id)
        
        if not profile:
            raise ValueError(f"Agent不存在: {agent_id}")
        if not job:
            raise ValueError(f"职位需求不存在: {job_id}")
        
        # 记录调动历史
        profile.experience.append({
            "type": "transfer",
            "from_department": profile.department,
            "to_department": job.department,
            "from_role": profile.role,
            "to_role": job.title,
            "timestamp": time.time()
        })
        
        # 更新Agent信息
        profile.department = job.department
        profile.role = job.title
        profile.status = AgentStatus.ONBOARDING
        profile.last_updated = time.time()
        
        # 更新职位状态
        job.status = "filled"
        
        print(f"[HR增强] 内部调动Agent: {profile.name} 到 {job.department} 部门")
        return profile
    
    def train_agent(self, agent_id: str, skills: Dict[str, str]) -> Dict[str, Any]:
        """培训Agent"""
        profile = self.agent_profiles.get(agent_id)
        if not profile:
            raise ValueError(f"Agent不存在: {agent_id}")
        
        # 更新状态
        profile.status = AgentStatus.TRAINING
        
        # 记录培训
        training_record = {
            "type": "training",
            "skills": skills,
            "timestamp": time.time(),
            "status": "in_progress"
        }
        
        # 更新技能
        for skill_name, level_str in skills.items():
            skill_id = f"skill_{skill_name.lower().replace(' ', '_')}"
            if skill_id not in self.skills:
                self.skills[skill_id] = Skill(
                    id=skill_id,
                    name=skill_name,
                    description=f"{skill_name}相关技能",
                    category="培训",
                    level=SkillLevel.BEGINNER
                )
            
            try:
                profile.skills[skill_id] = SkillLevel(level_str)
            except ValueError:
                profile.skills[skill_id] = SkillLevel.BEGINNER
        
        # 完成培训
        training_record["status"] = "completed"
        profile.experience.append(training_record)
        profile.status = AgentStatus.ACTIVE
        profile.last_updated = time.time()
        
        print(f"[HR增强] 培训Agent: {profile.name}，更新技能: {list(skills.keys())}")
        return {
            "success": True,
            "agent_id": agent_id,
            "training_record": training_record
        }
    
    def evaluate_performance(self, agent_id: str, 
                           rating: float, 
                           feedback: str) -> Dict[str, Any]:
        """评估Agent绩效"""
        profile = self.agent_profiles.get(agent_id)
        if not profile:
            raise ValueError(f"Agent不存在: {agent_id}")
        
        # 更新状态
        profile.status = AgentStatus.PERFORMANCE_REVIEW
        
        # 记录绩效评估
        performance_record = {
            "rating": rating,
            "feedback": feedback,
            "timestamp": time.time(),
            "reviewer": "HR"
        }
        
        profile.performance.append(performance_record)
        profile.status = AgentStatus.ACTIVE
        profile.last_updated = time.time()
        
        print(f"[HR增强] 评估Agent绩效: {profile.name}，评分: {rating}")
        return {
            "success": True,
            "agent_id": agent_id,
            "performance_record": performance_record
        }
    
    def get_agent_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """获取Agent档案"""
        return self.agent_profiles.get(agent_id)
    
    def get_all_agents(self, department: Optional[str] = None) -> List[AgentProfile]:
        """获取所有Agent"""
        agents = list(self.agent_profiles.values())
        if department:
            agents = [agent for agent in agents if agent.department == department]
        return agents
    
    def get_all_skills(self, category: Optional[str] = None) -> List[Skill]:
        """获取所有技能"""
        skills = list(self.skills.values())
        if category:
            skills = [skill for skill in skills if skill.category == category]
        return skills
    
    def get_job_requirements(self, status: Optional[str] = None) -> List[JobRequirement]:
        """获取职位需求"""
        jobs = list(self.job_requirements.values())
        if status:
            jobs = [job for job in jobs if job.status == status]
        return jobs
    
    def _initialize_auto_optimizer(self):
        """初始化自动优化器"""
        if AutoOptimizer:
            try:
                self.auto_optimizer = AutoOptimizer()
                print("[HR增强] 自动优化器初始化完成")
            except Exception as e:
                print(f"[HR增强] 自动优化器初始化失败: {e}")
        else:
            print("[HR增强] 自动优化器模块未找到")
    
    def optimize_agent(self, agent_id: str) -> Dict[str, Any]:
        """优化单个Agent"""
        profile = self.agent_profiles.get(agent_id)
        if not profile:
            raise ValueError(f"Agent不存在: {agent_id}")
        
        # 更新状态
        profile.status = AgentStatus.TRAINING
        
        # 记录优化历史
        optimization_record = {
            "type": "optimization",
            "agent_id": agent_id,
            "timestamp": time.time(),
            "status": "in_progress"
        }
        
        # 执行优化
        try:
            if hasattr(self.opc_manager, 'optimize_agents'):
                result = self.opc_manager.optimize_agents(agent_ids=[agent_id], iterations=1)
                optimization_record["status"] = "completed"
                optimization_record["result"] = result
                
                # 更新Agent状态
                profile.status = AgentStatus.ACTIVE
                profile.last_updated = time.time()
                
                print(f"[HR增强] 优化Agent: {profile.name} 完成")
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "result": result
                }
            else:
                raise ValueError("OPC Manager不支持Agent优化")
        except Exception as e:
            optimization_record["status"] = "failed"
            optimization_record["error"] = str(e)
            profile.status = AgentStatus.ACTIVE
            profile.last_updated = time.time()
            print(f"[HR增强] 优化Agent失败: {e}")
            return {
                "success": False,
                "agent_id": agent_id,
                "error": str(e)
            }
        finally:
            profile.experience.append(optimization_record)
    
    def optimize_agents_by_department(self, department: str) -> Dict[str, Any]:
        """优化指定部门的所有Agent"""
        agents = self.get_all_agents(department)
        agent_ids = [agent.id for agent in agents]
        
        if not agent_ids:
            return {
                "success": False,
                "error": f"部门 {department} 没有Agent"
            }
        
        # 执行优化
        try:
            if hasattr(self.opc_manager, 'optimize_agents'):
                result = self.opc_manager.optimize_agents(agent_ids=agent_ids, iterations=1)
                
                # 更新Agent状态
                for agent in agents:
                    agent.status = AgentStatus.ACTIVE
                    agent.last_updated = time.time()
                    
                    # 记录优化历史
                    optimization_record = {
                        "type": "optimization",
                        "agent_id": agent.id,
                        "timestamp": time.time(),
                        "status": "completed",
                        "result": "部门批量优化"
                    }
                    agent.experience.append(optimization_record)
                
                print(f"[HR增强] 优化部门 {department} 的 {len(agents)} 个Agent完成")
                return {
                    "success": True,
                    "department": department,
                    "agent_count": len(agents),
                    "result": result
                }
            else:
                raise ValueError("OPC Manager不支持Agent优化")
        except Exception as e:
            print(f"[HR增强] 优化部门Agent失败: {e}")
            return {
                "success": False,
                "department": department,
                "error": str(e)
            }
    
    def start_auto_optimization(self) -> Dict[str, Any]:
        """启动自动优化"""
        if not self.auto_optimizer:
            return {
                "success": False,
                "error": "自动优化器未初始化"
            }
        
        try:
            self.auto_optimizer.start_scheduler()
            next_time = self.auto_optimizer.get_next_optimization_time()
            print("[HR增强] 自动优化已启动")
            return {
                "success": True,
                "next_optimization_time": next_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"[HR增强] 启动自动优化失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_auto_optimization(self) -> Dict[str, Any]:
        """停止自动优化"""
        if not self.auto_optimizer:
            return {
                "success": False,
                "error": "自动优化器未初始化"
            }
        
        try:
            self.auto_optimizer.stop_scheduler()
            print("[HR增强] 自动优化已停止")
            return {
                "success": True
            }
        except Exception as e:
            print(f"[HR增强] 停止自动优化失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        if not self.auto_optimizer:
            return {
                "success": False,
                "error": "自动优化器未初始化"
            }
        
        try:
            stats = self.auto_optimizer.get_optimization_statistics()
            return {
                "success": True,
                "statistics": stats
            }
        except Exception as e:
            print(f"[HR增强] 获取优化统计信息失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def export_agent_profiles(self, output_file: str):
        """导出Agent档案"""
        profiles_data = {}
        for agent_id, profile in self.agent_profiles.items():
            profiles_data[agent_id] = {
                "name": profile.name,
                "department": profile.department,
                "role": profile.role,
                "status": profile.status.value,
                "skills": {k: v.value for k, v in profile.skills.items()},
                "experience": profile.experience,
                "performance": profile.performance,
                "hire_date": profile.hire_date,
                "last_updated": profile.last_updated
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
        
        print(f"[HR增强] 导出Agent档案到: {output_file}")


# 使用示例
if __name__ == "__main__":
    # 模拟OPC Manager
    class MockOPCManager:
        def get_departments(self):
            return ["design", "development", "marketing", "research", "finance", "hr"]
        
        def get_official_agent_by_department(self, department):
            agents = {
                "design": [
                    {"name": "designer_1", "frontmatter": {"name": "UI设计师", "description": "负责用户界面设计"}}
                ],
                "development": [
                    {"name": "developer_1", "frontmatter": {"name": "前端开发", "description": "负责前端开发"}}
                ],
                "marketing": [
                    {"name": "marketer_1", "frontmatter": {"name": "市场专员", "description": "负责市场推广"}}
                ]
            }
            return agents.get(department, [])
    
    # 创建HR增强实例
    opc_manager = MockOPCManager()
    hr = HREnhancement(opc_manager)
    
    # 创建职位需求
    job = hr.create_job_requirement(
        title="高级前端开发",
        department="development",
        description="负责复杂Web应用的前端开发",
        required_skills={
            "编程": "advanced",
            "前端框架": "expert",
            "UI设计": "intermediate"
        },
        responsibilities=[
            "开发高质量的前端代码",
            "与设计团队协作",
            "优化前端性能"
        ]
    )
    
    # 寻找匹配的Agent
    matches = hr.find_matching_agents(job.id)
    print(f"找到 {len(matches)} 个匹配的Agent")
    for match in matches[:3]:
        print(f"  {match['agent_name']} - 匹配度: {match['match_score']:.2f}")
    
    # 从市场招聘Agent
    if matches and 'source' in matches[0] and matches[0]['source'] == 'marketplace':
        new_agent = hr.hire_agent(matches[0]['agent_id'], job.id)
        print(f"招聘新Agent: {new_agent.name}")
    
    # 培训Agent
    if hr.agent_profiles:
        agent_id = list(hr.agent_profiles.keys())[0]
        training_result = hr.train_agent(
            agent_id=agent_id,
            skills={
                "前端框架": "expert",
                "响应式设计": "advanced"
            }
        )
        print(f"培训完成: {training_result['success']}")
    
    # 评估绩效
    if hr.agent_profiles:
        agent_id = list(hr.agent_profiles.keys())[0]
        eval_result = hr.evaluate_performance(
            agent_id=agent_id,
            rating=4.5,
            feedback="表现优秀，技术能力强"
        )
        print(f"绩效评估完成: {eval_result['success']}")
    
    # 导出Agent档案
    hr.export_agent_profiles("agent_profiles.json")
    print("HR增强功能演示完成")
