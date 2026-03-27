#!/usr/bin/env python3
"""
人事部增强功能API端点
为HR增强功能提供REST API接口
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional
import time
from hr_enhancement import HREnhancement, AgentStatus, SkillLevel

# 创建蓝图
hr_bp = Blueprint('hr', __name__, url_prefix='/api/hr')

# 全局HR增强实例
hr_enhancement: Optional[HREnhancement] = None


def init_hr_api(opc_manager):
    """初始化HR API"""
    global hr_enhancement
    hr_enhancement = HREnhancement(opc_manager)
    print("[HR API] 初始化完成")


# ==================== Agent管理 ====================

@hr_bp.route('/agents', methods=['GET'])
def get_agents():
    """获取Agent列表"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    department = request.args.get('department')
    agents = hr_enhancement.get_all_agents(department)
    
    return jsonify({
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "department": agent.department,
                "role": agent.role,
                "status": agent.status.value,
                "skills": {k: v.value for k, v in agent.skills.items()},
                "hire_date": agent.hire_date,
                "last_updated": agent.last_updated
            }
            for agent in agents
        ],
        "total": len(agents)
    })


@hr_bp.route('/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id: str):
    """获取Agent详情"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    agent = hr_enhancement.get_agent_profile(agent_id)
    if not agent:
        return jsonify({"error": f"Agent {agent_id} not found"}), 404
    
    return jsonify({
        "id": agent.id,
        "name": agent.name,
        "department": agent.department,
        "role": agent.role,
        "status": agent.status.value,
        "skills": {k: v.value for k, v in agent.skills.items()},
        "experience": agent.experience,
        "performance": agent.performance,
        "hire_date": agent.hire_date,
        "last_updated": agent.last_updated,
        "metadata": agent.metadata
    })


# ==================== 技能管理 ====================

@hr_bp.route('/skills', methods=['GET'])
def get_skills():
    """获取技能列表"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    category = request.args.get('category')
    skills = hr_enhancement.get_all_skills(category)
    
    return jsonify({
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
                "level": skill.level.value,
                "related_skills": skill.related_skills,
                "created_at": skill.created_at
            }
            for skill in skills
        ],
        "total": len(skills)
    })


# ==================== 职位需求 ====================

@hr_bp.route('/jobs', methods=['POST'])
def create_job():
    """创建职位需求"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    title = data.get('title')
    department = data.get('department')
    description = data.get('description', '')
    required_skills = data.get('required_skills', {})
    responsibilities = data.get('responsibilities', [])
    
    if not title or not department:
        return jsonify({"error": "title and department are required"}), 400
    
    try:
        job = hr_enhancement.create_job_requirement(
            title=title,
            department=department,
            description=description,
            required_skills=required_skills,
            responsibilities=responsibilities
        )
        
        return jsonify({
            "success": True,
            "job": {
                "id": job.id,
                "title": job.title,
                "department": job.department,
                "description": job.description,
                "required_skills": {k: v.value for k, v in job.required_skills.items()},
                "responsibilities": job.responsibilities,
                "status": job.status,
                "created_at": job.created_at
            }
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hr_bp.route('/jobs', methods=['GET'])
def get_jobs():
    """获取职位需求列表"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    status = request.args.get('status')
    jobs = hr_enhancement.get_job_requirements(status)
    
    return jsonify({
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "department": job.department,
                "description": job.description,
                "required_skills": {k: v.value for k, v in job.required_skills.items()},
                "responsibilities": job.responsibilities,
                "status": job.status,
                "created_at": job.created_at
            }
            for job in jobs
        ],
        "total": len(jobs)
    })


@hr_bp.route('/jobs/<job_id>/match', methods=['GET'])
def find_matching_agents(job_id: str):
    """寻找匹配的Agent"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        matches = hr_enhancement.find_matching_agents(job_id)
        return jsonify({
            "matches": matches,
            "total": len(matches)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 招聘管理 ====================

@hr_bp.route('/hire', methods=['POST'])
def hire_agent():
    """招聘Agent"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    agent_id = data.get('agent_id')
    job_id = data.get('job_id')
    
    if not agent_id or not job_id:
        return jsonify({"error": "agent_id and job_id are required"}), 400
    
    try:
        new_agent = hr_enhancement.hire_agent(agent_id, job_id)
        return jsonify({
            "success": True,
            "agent": {
                "id": new_agent.id,
                "name": new_agent.name,
                "department": new_agent.department,
                "role": new_agent.role,
                "status": new_agent.status.value,
                "skills": {k: v.value for k, v in new_agent.skills.items()}
            }
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 培训管理 ====================

@hr_bp.route('/train', methods=['POST'])
def train_agent():
    """培训Agent"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    agent_id = data.get('agent_id')
    skills = data.get('skills', {})
    
    if not agent_id or not skills:
        return jsonify({"error": "agent_id and skills are required"}), 400
    
    try:
        result = hr_enhancement.train_agent(agent_id, skills)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 绩效评估 ====================

@hr_bp.route('/performance', methods=['POST'])
def evaluate_performance():
    """评估Agent绩效"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    agent_id = data.get('agent_id')
    rating = data.get('rating')
    feedback = data.get('feedback', '')
    
    if not agent_id or rating is None:
        return jsonify({"error": "agent_id and rating are required"}), 400
    
    try:
        result = hr_enhancement.evaluate_performance(agent_id, rating, feedback)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 导出功能 ====================

@hr_bp.route('/export/profiles', methods=['GET'])
def export_profiles():
    """导出Agent档案"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        filename = f"agent_profiles_{int(time.time())}.json"
        hr_enhancement.export_agent_profiles(filename)
        return jsonify({
            "success": True,
            "filename": filename,
            "message": "Agent profiles exported successfully"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 自动优化 ====================

@hr_bp.route('/optimize/agent/<agent_id>', methods=['POST'])
def optimize_agent(agent_id: str):
    """优化单个Agent"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        result = hr_enhancement.optimize_agent(agent_id)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hr_bp.route('/optimize/department/<department>', methods=['POST'])
def optimize_department(department: str):
    """优化指定部门的所有Agent"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        result = hr_enhancement.optimize_agents_by_department(department)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hr_bp.route('/optimize/auto/start', methods=['POST'])
def start_auto_optimization():
    """启动自动优化"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        result = hr_enhancement.start_auto_optimization()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hr_bp.route('/optimize/auto/stop', methods=['POST'])
def stop_auto_optimization():
    """停止自动优化"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        result = hr_enhancement.stop_auto_optimization()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@hr_bp.route('/optimize/statistics', methods=['GET'])
def get_optimization_statistics():
    """获取优化统计信息"""
    if not hr_enhancement:
        return jsonify({"error": "HR enhancement not initialized"}), 500
    
    try:
        result = hr_enhancement.get_optimization_statistics()
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== 健康检查 ====================

@hr_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    if not hr_enhancement:
        return jsonify({
            "status": "not_initialized",
            "timestamp": time.time()
        }), 503
    
    agents_count = len(hr_enhancement.get_all_agents())
    skills_count = len(hr_enhancement.get_all_skills())
    jobs_count = len(hr_enhancement.get_job_requirements())
    
    return jsonify({
        "status": "healthy",
        "agents_count": agents_count,
        "skills_count": skills_count,
        "jobs_count": jobs_count,
        "timestamp": time.time()
    })


# 错误处理
@hr_bp.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@hr_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
