#!/usr/bin/env python3
"""
MCPIntegration模块

实现从MCP获取Skill的功能，支持Skill验证和安全性检查。
"""

import json
import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

class MCPIntegration:
    """MCP集成类"""
    
    def __init__(self, mcp_endpoint: str = 'https://mcp.example.com/api'):
        """
        初始化MCP集成
        
        Args:
            mcp_endpoint: MCP API端点
        """
        self.logger = logging.getLogger('OPC-Agents.MCPIntegration')
        self.mcp_endpoint = mcp_endpoint
        self.session = requests.Session()
        self.session.timeout = 30
        self.skill_cache = {}
        self.verification_history = []
    
    def fetch_skills(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        从MCP获取技能列表
        
        Args:
            category: 技能类别，None表示所有类别
            limit: 返回的技能数量限制
            
        Returns:
            技能列表
        """
        try:
            params = {'limit': limit}
            if category:
                params['category'] = category
            
            response = self.session.get(f'{self.mcp_endpoint}/skills', params=params)
            response.raise_for_status()
            
            skills = response.json().get('skills', [])
            
            # 缓存技能数据
            for skill in skills:
                self.skill_cache[skill.get('name')] = skill
            
            self.logger.info(f"从MCP获取技能成功，数量: {len(skills)}")
            return skills
        except Exception as e:
            self.logger.error(f"从MCP获取技能失败: {e}")
            return []
    
    def fetch_skill_details(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        从MCP获取技能详情
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能详情
        """
        try:
            # 先检查缓存
            if skill_name in self.skill_cache:
                return self.skill_cache[skill_name]
            
            response = self.session.get(f'{self.mcp_endpoint}/skills/{skill_name}')
            response.raise_for_status()
            
            skill_details = response.json()
            
            # 缓存技能详情
            self.skill_cache[skill_name] = skill_details
            
            self.logger.info(f"从MCP获取技能详情成功: {skill_name}")
            return skill_details
        except Exception as e:
            self.logger.error(f"从MCP获取技能详情失败: {e}")
            return None
    
    def verify_skill(self, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证技能的安全性和可靠性
        
        Args:
            skill_data: 技能数据
            
        Returns:
            验证结果
        """
        try:
            verification_result = {
                'skill_name': skill_data.get('name'),
                'verified': False,
                'security_score': 0.0,
                'reliability_score': 0.0,
                'issues': [],
                'recommendations': []
            }
            
            # 检查技能基本信息
            if not self._validate_skill_basic_info(skill_data):
                verification_result['issues'].append('技能基本信息不完整')
            
            # 检查技能代码安全性
            security_score = self._check_skill_security(skill_data)
            verification_result['security_score'] = security_score
            
            # 检查技能可靠性
            reliability_score = self._check_skill_reliability(skill_data)
            verification_result['reliability_score'] = reliability_score
            
            # 综合评估
            if security_score >= 0.8 and reliability_score >= 0.7:
                verification_result['verified'] = True
            else:
                if security_score < 0.8:
                    verification_result['issues'].append('技能安全性评分不足')
                if reliability_score < 0.7:
                    verification_result['issues'].append('技能可靠性评分不足')
            
            # 生成建议
            verification_result['recommendations'] = self._generate_verification_recommendations(skill_data, verification_result)
            
            # 记录验证历史
            verification_record = {
                'skill_name': skill_data.get('name'),
                'timestamp': datetime.now().isoformat(),
                'result': verification_result
            }
            self.verification_history.append(verification_record)
            
            self.logger.info(f"验证技能: {skill_data.get('name')}, 结果: {verification_result['verified']}")
            return verification_result
        except Exception as e:
            self.logger.error(f"验证技能失败: {e}")
            return {
                'skill_name': skill_data.get('name'),
                'verified': False,
                'error': str(e)
            }
    
    def _validate_skill_basic_info(self, skill_data: Dict[str, Any]) -> bool:
        """
        验证技能基本信息
        
        Args:
            skill_data: 技能数据
            
        Returns:
            是否验证通过
        """
        required_fields = ['name', 'description', 'version', 'author', 'category']
        for field in required_fields:
            if field not in skill_data:
                return False
        return True
    
    def _check_skill_security(self, skill_data: Dict[str, Any]) -> float:
        """
        检查技能安全性
        
        Args:
            skill_data: 技能数据
            
        Returns:
            安全性评分
        """
        score = 1.0
        
        # 检查是否有恶意代码
        code = skill_data.get('code', '')
        dangerous_patterns = ['eval(', 'exec(', 'import os', 'import subprocess']
        for pattern in dangerous_patterns:
            if pattern in code:
                score -= 0.2
        
        # 检查权限请求
        permissions = skill_data.get('permissions', [])
        dangerous_permissions = ['network', 'file_system', 'system']
        for perm in permissions:
            if perm in dangerous_permissions:
                score -= 0.1
        
        # 检查依赖项
        dependencies = skill_data.get('dependencies', [])
        if len(dependencies) > 10:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _check_skill_reliability(self, skill_data: Dict[str, Any]) -> float:
        """
        检查技能可靠性
        
        Args:
            skill_data: 技能数据
            
        Returns:
            可靠性评分
        """
        score = 0.7
        
        # 检查版本信息
        version = skill_data.get('version', '0.0.0')
        if version >= '1.0.0':
            score += 0.1
        
        # 检查作者信息
        author = skill_data.get('author', '')
        if author:
            score += 0.1
        
        # 检查使用次数
        usage_count = skill_data.get('usage_count', 0)
        if usage_count > 100:
            score += 0.1
        elif usage_count > 10:
            score += 0.05
        
        # 检查评分
        rating = skill_data.get('rating', 0.0)
        score += min(0.1, rating / 5.0 * 0.1)
        
        return max(0.0, min(1.0, score))
    
    def _generate_verification_recommendations(self, skill_data: Dict[str, Any], verification_result: Dict[str, Any]) -> List[str]:
        """
        生成验证建议
        
        Args:
            skill_data: 技能数据
            verification_result: 验证结果
            
        Returns:
            建议列表
        """
        recommendations = []
        
        if verification_result['security_score'] < 0.8:
            recommendations.append('建议审查技能代码，移除潜在的安全风险')
        
        if verification_result['reliability_score'] < 0.7:
            recommendations.append('建议在测试环境中充分测试技能，确保其可靠性')
        
        if not skill_data.get('documentation'):
            recommendations.append('建议添加详细的技能文档，包括使用方法和注意事项')
        
        return recommendations
    
    def import_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        导入技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            导入结果
        """
        try:
            # 获取技能详情
            skill_details = self.fetch_skill_details(skill_name)
            if not skill_details:
                return {
                    'success': False,
                    'error': '技能不存在'
                }
            
            # 验证技能
            verification_result = self.verify_skill(skill_details)
            if not verification_result['verified']:
                return {
                    'success': False,
                    'error': '技能验证失败',
                    'verification_result': verification_result
                }
            
            # 导入技能
            import_result = {
                'success': True,
                'skill_name': skill_name,
                'skill_data': skill_details,
                'verification_result': verification_result,
                'imported_at': datetime.now().isoformat()
            }
            
            self.logger.info(f"导入技能成功: {skill_name}")
            return import_result
        except Exception as e:
            self.logger.error(f"导入技能失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        更新技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            更新结果
        """
        try:
            # 获取最新技能详情
            skill_details = self.fetch_skill_details(skill_name)
            if not skill_details:
                return {
                    'success': False,
                    'error': '技能不存在'
                }
            
            # 验证技能
            verification_result = self.verify_skill(skill_details)
            if not verification_result['verified']:
                return {
                    'success': False,
                    'error': '技能验证失败',
                    'verification_result': verification_result
                }
            
            # 更新技能
            update_result = {
                'success': True,
                'skill_name': skill_name,
                'skill_data': skill_details,
                'verification_result': verification_result,
                'updated_at': datetime.now().isoformat()
            }
            
            # 更新缓存
            self.skill_cache[skill_name] = skill_details
            
            self.logger.info(f"更新技能成功: {skill_name}")
            return update_result
        except Exception as e:
            self.logger.error(f"更新技能失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_skills(self, query: str, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        搜索技能
        
        Args:
            query: 搜索关键词
            category: 技能类别，None表示所有类别
            
        Returns:
            搜索结果
        """
        try:
            params = {'q': query}
            if category:
                params['category'] = category
            
            response = self.session.get(f'{self.mcp_endpoint}/skills/search', params=params)
            response.raise_for_status()
            
            results = response.json().get('results', [])
            
            self.logger.info(f"搜索技能成功，结果数量: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"搜索技能失败: {e}")
            return []
    
    def get_skill_categories(self) -> List[str]:
        """
        获取技能类别列表
        
        Returns:
            技能类别列表
        """
        try:
            response = self.session.get(f'{self.mcp_endpoint}/skills/categories')
            response.raise_for_status()
            
            categories = response.json().get('categories', [])
            
            self.logger.info(f"获取技能类别成功，数量: {len(categories)}")
            return categories
        except Exception as e:
            self.logger.error(f"获取技能类别失败: {e}")
            return []
    
    def get_verification_history(self) -> List[Dict[str, Any]]:
        """
        获取验证历史
        
        Returns:
            验证历史列表
        """
        return self.verification_history
    
    def clear_cache(self):
        """
        清除缓存
        """
        self.skill_cache.clear()
        self.logger.info("清除技能缓存成功")

# 测试代码
if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建MCPIntegration实例
    mcp_integration = MCPIntegration(mcp_endpoint='https://mcp.example.com/api')
    
    # 测试获取技能列表
    print("测试获取技能列表:")
    skills = mcp_integration.fetch_skills(limit=5)
    print(f"获取技能数量: {len(skills)}")
    
    # 测试获取技能详情
    if skills:
        skill_name = skills[0].get('name')
        print(f"\n测试获取技能详情: {skill_name}")
        skill_details = mcp_integration.fetch_skill_details(skill_name)
        print(f"技能详情: {skill_details}")
    
    # 测试验证技能
    if skills:
        print("\n测试验证技能:")
        verification_result = mcp_integration.verify_skill(skills[0])
        print(f"验证结果: {verification_result}")
    
    # 测试导入技能
    if skills:
        skill_name = skills[0].get('name')
        print(f"\n测试导入技能: {skill_name}")
        import_result = mcp_integration.import_skill(skill_name)
        print(f"导入结果: {import_result['success']}")
    
    # 测试搜索技能
    print("\n测试搜索技能:")
    search_results = mcp_integration.search_skills('market')
    print(f"搜索结果数量: {len(search_results)}")
    
    # 测试获取技能类别
    print("\n测试获取技能类别:")
    categories = mcp_integration.get_skill_categories()
    print(f"技能类别: {categories}")
    
    print("\nMCPIntegration测试完成！")
