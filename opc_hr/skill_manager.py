#!/usr/bin/env python3
"""
SkillManager模块

实现Skill注册和管理功能，支持Skill使用跟踪和优化建议。
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

class SkillManager:
    """技能管理器类"""
    
    def __init__(self):
        """初始化技能管理器"""
        self.logger = logging.getLogger('OPC-Agents.SkillManager')
        self.skills = {}
        self.skill_usage = {}
        self.skill_recommendations = {}
        
    def register_skill(self, skill_name: str, skill_data: Dict[str, Any]) -> bool:
        """
        注册新技能
        
        Args:
            skill_name: 技能名称
            skill_data: 技能数据
            
        Returns:
            是否注册成功
        """
        try:
            # 验证技能数据
            if not self._validate_skill_data(skill_data):
                self.logger.error(f"技能数据验证失败: {skill_name}")
                return False
            
            # 注册技能
            self.skills[skill_name] = {
                'name': skill_name,
                'description': skill_data.get('description', ''),
                'category': skill_data.get('category', 'general'),
                'version': skill_data.get('version', '1.0.0'),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'usage_count': 0,
                'last_used': None,
                **skill_data
            }
            
            # 初始化技能使用记录
            self.skill_usage[skill_name] = {
                'total_usage': 0,
                'success_count': 0,
                'failure_count': 0,
                'usage_history': [],
                'agents_used': {}
            }
            
            self.logger.info(f"注册技能成功: {skill_name}")
            return True
        except Exception as e:
            self.logger.error(f"注册技能失败: {e}")
            return False
    
    def _validate_skill_data(self, skill_data: Dict[str, Any]) -> bool:
        """
        验证技能数据
        
        Args:
            skill_data: 技能数据
            
        Returns:
            是否验证通过
        """
        required_fields = ['description']
        for field in required_fields:
            if field not in skill_data:
                return False
        return True
    
    def get_skill(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        获取技能信息
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能信息
        """
        return self.skills.get(skill_name)
    
    def list_skills(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有技能
        
        Args:
            category: 技能类别，None表示所有类别
            
        Returns:
            技能列表
        """
        skills_list = []
        for skill_name, skill_data in self.skills.items():
            if category and skill_data.get('category') != category:
                continue
            skills_list.append(skill_data)
        return skills_list
    
    def update_skill(self, skill_name: str, skill_data: Dict[str, Any]) -> bool:
        """
        更新技能信息
        
        Args:
            skill_name: 技能名称
            skill_data: 技能数据
            
        Returns:
            是否更新成功
        """
        try:
            if skill_name not in self.skills:
                self.logger.error(f"技能不存在: {skill_name}")
                return False
            
            # 更新技能数据
            self.skills[skill_name].update(skill_data)
            self.skills[skill_name]['updated_at'] = datetime.now().isoformat()
            
            self.logger.info(f"更新技能成功: {skill_name}")
            return True
        except Exception as e:
            self.logger.error(f"更新技能失败: {e}")
            return False
    
    def delete_skill(self, skill_name: str) -> bool:
        """
        删除技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            是否删除成功
        """
        try:
            if skill_name not in self.skills:
                self.logger.error(f"技能不存在: {skill_name}")
                return False
            
            # 删除技能
            del self.skills[skill_name]
            if skill_name in self.skill_usage:
                del self.skill_usage[skill_name]
            if skill_name in self.skill_recommendations:
                del self.skill_recommendations[skill_name]
            
            self.logger.info(f"删除技能成功: {skill_name}")
            return True
        except Exception as e:
            self.logger.error(f"删除技能失败: {e}")
            return False
    
    def record_skill_usage(self, skill_name: str, agent_name: str, success: bool, duration: float) -> bool:
        """
        记录技能使用情况
        
        Args:
            skill_name: 技能名称
            agent_name: 代理名称
            success: 是否成功
            duration: 执行时长
            
        Returns:
            是否记录成功
        """
        try:
            if skill_name not in self.skill_usage:
                self.skill_usage[skill_name] = {
                    'total_usage': 0,
                    'success_count': 0,
                    'failure_count': 0,
                    'usage_history': [],
                    'agents_used': {}
                }
            
            # 更新使用统计
            usage_data = self.skill_usage[skill_name]
            usage_data['total_usage'] += 1
            if success:
                usage_data['success_count'] += 1
            else:
                usage_data['failure_count'] += 1
            
            # 记录使用历史
            usage_record = {
                'timestamp': datetime.now().isoformat(),
                'agent_name': agent_name,
                'success': success,
                'duration': duration
            }
            usage_data['usage_history'].append(usage_record)
            
            # 更新代理使用统计
            if agent_name not in usage_data['agents_used']:
                usage_data['agents_used'][agent_name] = {
                    'total_usage': 0,
                    'success_count': 0,
                    'failure_count': 0
                }
            
            agent_usage = usage_data['agents_used'][agent_name]
            agent_usage['total_usage'] += 1
            if success:
                agent_usage['success_count'] += 1
            else:
                agent_usage['failure_count'] += 1
            
            # 更新技能的使用信息
            if skill_name in self.skills:
                self.skills[skill_name]['usage_count'] = usage_data['total_usage']
                self.skills[skill_name]['last_used'] = datetime.now().isoformat()
            
            self.logger.info(f"记录技能使用成功: {skill_name} by {agent_name}")
            return True
        except Exception as e:
            self.logger.error(f"记录技能使用失败: {e}")
            return False
    
    def get_skill_usage(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        获取技能使用情况
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能使用情况
        """
        return self.skill_usage.get(skill_name)
    
    def get_agent_skill_usage(self, agent_name: str) -> Dict[str, Any]:
        """
        获取代理的技能使用情况
        
        Args:
            agent_name: 代理名称
            
        Returns:
            代理的技能使用情况
        """
        agent_usage = {
            'total_usage': 0,
            'success_count': 0,
            'failure_count': 0,
            'skills_used': {}
        }
        
        for skill_name, usage_data in self.skill_usage.items():
            if agent_name in usage_data['agents_used']:
                agent_skill_usage = usage_data['agents_used'][agent_name]
                agent_usage['total_usage'] += agent_skill_usage['total_usage']
                agent_usage['success_count'] += agent_skill_usage['success_count']
                agent_usage['failure_count'] += agent_skill_usage['failure_count']
                agent_usage['skills_used'][skill_name] = agent_skill_usage
        
        return agent_usage
    
    def generate_skill_recommendations(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        生成技能推荐
        
        Args:
            agent_name: 代理名称
            
        Returns:
            技能推荐列表
        """
        try:
            recommendations = []
            
            # 获取代理的技能使用情况
            agent_usage = self.get_agent_skill_usage(agent_name)
            used_skills = set(agent_usage['skills_used'].keys())
            
            # 分析未使用的技能
            for skill_name, skill_data in self.skills.items():
                if skill_name not in used_skills:
                    # 基于技能类别和代理角色生成推荐
                    recommendation_score = self._calculate_recommendation_score(agent_name, skill_data)
                    if recommendation_score > 0.5:
                        recommendations.append({
                            'skill_name': skill_name,
                            'score': recommendation_score,
                            'reason': self._generate_recommendation_reason(agent_name, skill_data),
                            'skill_data': skill_data
                        })
            
            # 按推荐分数排序
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            
            # 存储推荐结果
            self.skill_recommendations[agent_name] = recommendations
            
            self.logger.info(f"生成技能推荐成功: {agent_name}, 推荐数量: {len(recommendations)}")
            return recommendations
        except Exception as e:
            self.logger.error(f"生成技能推荐失败: {e}")
            return []
    
    def _calculate_recommendation_score(self, agent_name: str, skill_data: Dict[str, Any]) -> float:
        """
        计算推荐分数
        
        Args:
            agent_name: 代理名称
            skill_data: 技能数据
            
        Returns:
            推荐分数
        """
        # 基于代理名称和技能类别计算推荐分数
        # 这里使用简单的规则，实际可以使用更复杂的算法
        score = 0.0
        
        # 基于技能类别
        category_score = {
            'marketing': 0.8,
            'product': 0.7,
            'engineering': 0.9,
            'design': 0.6,
            'sales': 0.7,
            'support': 0.5,
            'general': 0.4
        }
        
        category = skill_data.get('category', 'general')
        score += category_score.get(category, 0.4)
        
        # 基于技能使用频率
        usage_count = skill_data.get('usage_count', 0)
        if usage_count > 10:
            score += 0.2
        elif usage_count > 5:
            score += 0.1
        
        return min(1.0, score)
    
    def _generate_recommendation_reason(self, agent_name: str, skill_data: Dict[str, Any]) -> str:
        """
        生成推荐理由
        
        Args:
            agent_name: 代理名称
            skill_data: 技能数据
            
        Returns:
            推荐理由
        """
        category = skill_data.get('category', 'general')
        usage_count = skill_data.get('usage_count', 0)
        
        reasons = []
        
        if category == 'marketing' and '市场' in agent_name:
            reasons.append('该技能与您的市场相关工作高度相关')
        elif category == 'product' and '产品' in agent_name:
            reasons.append('该技能与您的产品相关工作高度相关')
        elif category == 'engineering' and '工程' in agent_name:
            reasons.append('该技能与您的工程相关工作高度相关')
        
        if usage_count > 10:
            reasons.append('该技能被其他代理广泛使用，效果良好')
        
        if not reasons:
            reasons.append('该技能可能对您的工作有所帮助')
        
        return ' '.join(reasons)
    
    def get_skill_recommendations(self, agent_name: str) -> List[Dict[str, Any]]:
        """
        获取技能推荐
        
        Args:
            agent_name: 代理名称
            
        Returns:
            技能推荐列表
        """
        if agent_name not in self.skill_recommendations:
            return self.generate_skill_recommendations(agent_name)
        return self.skill_recommendations[agent_name]
    
    def optimize_skill_usage(self, agent_name: str) -> Dict[str, Any]:
        """
        优化技能使用
        
        Args:
            agent_name: 代理名称
            
        Returns:
            优化结果
        """
        try:
            # 获取代理的技能使用情况
            agent_usage = self.get_agent_skill_usage(agent_name)
            
            # 分析技能使用效率
            optimization_result = {
                'agent_name': agent_name,
                'total_skills_used': len(agent_usage['skills_used']),
                'total_usage': agent_usage['total_usage'],
                'success_rate': 0.0,
                'recommendations': [],
                'improvements': []
            }
            
            # 计算成功率
            if agent_usage['total_usage'] > 0:
                optimization_result['success_rate'] = agent_usage['success_count'] / agent_usage['total_usage']
            
            # 分析低效率技能
            for skill_name, skill_usage in agent_usage['skills_used'].items():
                if skill_usage['total_usage'] > 0:
                    success_rate = skill_usage['success_count'] / skill_usage['total_usage']
                    if success_rate < 0.6:
                        optimization_result['improvements'].append({
                            'skill_name': skill_name,
                            'current_success_rate': success_rate,
                            'suggestion': '建议减少使用该技能，或寻求培训以提高使用效率'
                        })
            
            # 生成技能推荐
            optimization_result['recommendations'] = self.generate_skill_recommendations(agent_name)
            
            self.logger.info(f"优化技能使用成功: {agent_name}")
            return optimization_result
        except Exception as e:
            self.logger.error(f"优化技能使用失败: {e}")
            return {
                'agent_name': agent_name,
                'error': str(e)
            }
    
    def save_skills(self, file_path: str = 'skills.json') -> bool:
        """
        保存技能数据到文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否保存成功
        """
        try:
            data = {
                'skills': self.skills,
                'skill_usage': self.skill_usage,
                'skill_recommendations': self.skill_recommendations,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"保存技能数据成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存技能数据失败: {e}")
            return False
    
    def load_skills(self, file_path: str = 'skills.json') -> bool:
        """
        从文件加载技能数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否加载成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.skills = data.get('skills', {})
            self.skill_usage = data.get('skill_usage', {})
            self.skill_recommendations = data.get('skill_recommendations', {})
            
            self.logger.info(f"加载技能数据成功: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"加载技能数据失败: {e}")
            return False

# 测试代码
if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建SkillManager实例
    skill_manager = SkillManager()
    
    # 测试注册技能
    print("测试注册技能:")
    skills_to_register = [
        {
            'name': '市场分析',
            'description': '分析市场趋势和竞争情况',
            'category': 'marketing',
            'version': '1.0.0'
        },
        {
            'name': '产品规划',
            'description': '规划产品功能和路线图',
            'category': 'product',
            'version': '1.0.0'
        },
        {
            'name': '代码开发',
            'description': '编写和维护代码',
            'category': 'engineering',
            'version': '1.0.0'
        }
    ]
    
    for skill_data in skills_to_register:
        success = skill_manager.register_skill(skill_data['name'], skill_data)
        print(f"注册技能 {skill_data['name']}: {success}")
    
    # 测试列出技能
    print("\n测试列出技能:")
    all_skills = skill_manager.list_skills()
    print(f"所有技能: {[skill['name'] for skill in all_skills]}")
    
    marketing_skills = skill_manager.list_skills(category='marketing')
    print(f"市场类技能: {[skill['name'] for skill in marketing_skills]}")
    
    # 测试记录技能使用
    print("\n测试记录技能使用:")
    skill_manager.record_skill_usage('市场分析', '市场研究员', True, 1.2)
    skill_manager.record_skill_usage('产品规划', '产品经理', True, 0.8)
    skill_manager.record_skill_usage('代码开发', '工程师', False, 2.5)
    
    # 测试获取技能使用情况
    print("\n测试获取技能使用情况:")
    market_analysis_usage = skill_manager.get_skill_usage('市场分析')
    print(f"市场分析技能使用情况: {market_analysis_usage}")
    
    # 测试获取代理技能使用情况
    print("\n测试获取代理技能使用情况:")
    market_researcher_usage = skill_manager.get_agent_skill_usage('市场研究员')
    print(f"市场研究员技能使用情况: {market_researcher_usage}")
    
    # 测试生成技能推荐
    print("\n测试生成技能推荐:")
    recommendations = skill_manager.generate_skill_recommendations('市场研究员')
    print(f"市场研究员的技能推荐: {[rec['skill_name'] for rec in recommendations]}")
    
    # 测试优化技能使用
    print("\n测试优化技能使用:")
    optimization = skill_manager.optimize_skill_usage('市场研究员')
    print(f"市场研究员的技能使用优化: {optimization}")
    
    # 测试保存和加载技能数据
    print("\n测试保存和加载技能数据:")
    save_success = skill_manager.save_skills('test_skills.json')
    print(f"保存技能数据: {save_success}")
    
    # 创建新实例并加载数据
    new_skill_manager = SkillManager()
    load_success = new_skill_manager.load_skills('test_skills.json')
    print(f"加载技能数据: {load_success}")
    print(f"加载后技能数量: {len(new_skill_manager.list_skills())}")
    
    print("\nSkillManager测试完成！")
