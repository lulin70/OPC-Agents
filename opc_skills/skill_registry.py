"""
OPC-Agents 技能搜索基础架构

功能：
- 技能注册中心
- 技能元数据管理
- 技能搜索 API
- 技能分类和标签
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime


class SkillRegistry:
    """技能注册中心"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化技能注册中心
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.skills_dir = self.config.get('skills_dir', './opc_skills')
        self.registry_file = self.config.get('registry_file', './data/skill_registry.json')
        self.skills: Dict[str, Dict] = {}
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
        
        # 加载已注册的技能
        self._load_registry()
    
    def register_skill(self, skill_class: type) -> Dict:
        """
        注册技能
        
        Args:
            skill_class: 技能类
            
        Returns:
            Dict: 注册结果
        """
        if not hasattr(skill_class, 'METADATA'):
            return {
                'success': False,
                'error': '技能类缺少 METADATA 属性'
            }
        
        metadata = skill_class.METADATA
        skill_name = metadata.get('name', skill_class.__name__)
        
        # 构建技能信息
        skill_info = {
            'name': skill_name,
            'version': metadata.get('version', '1.0.0'),
            'description': metadata.get('description', ''),
            'author': metadata.get('author', 'Unknown'),
            'category': metadata.get('category', 'general'),
            'tags': metadata.get('tags', []),
            'permissions': metadata.get('permissions', []),
            'class_name': skill_class.__name__,
            'module': skill_class.__module__,
            'file_path': self._get_skill_file_path(skill_class),
            'registered_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'enabled': True,
            'usage_count': metadata.get('usage_count', 0),
            'rating': metadata.get('rating', 0.0),
        }
        
        # 注册技能
        self.skills[skill_name] = skill_info
        
        # 保存到注册表
        self._save_registry()
        
        return {
            'success': True,
            'skill_name': skill_name,
            'message': f'技能 {skill_name} 注册成功'
        }
    
    def unregister_skill(self, skill_name: str) -> Dict:
        """
        注销技能
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Dict: 注销结果
        """
        if skill_name not in self.skills:
            return {
                'success': False,
                'error': f'技能 {skill_name} 不存在'
            }
        
        del self.skills[skill_name]
        self._save_registry()
        
        return {
            'success': True,
            'message': f'技能 {skill_name} 已注销'
        }
    
    def get_skill(self, skill_name: str) -> Optional[Dict]:
        """
        获取技能信息
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Dict: 技能信息
        """
        return self.skills.get(skill_name)
    
    def list_skills(self, 
                    category: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    enabled_only: bool = True) -> List[Dict]:
        """
        列出技能
        
        Args:
            category: 分类过滤
            tags: 标签过滤
            enabled_only: 只列出启用的技能
            
        Returns:
            List[Dict]: 技能列表
        """
        skills = list(self.skills.values())
        
        # 过滤启用的技能
        if enabled_only:
            skills = [s for s in skills if s.get('enabled', True)]
        
        # 按分类过滤
        if category:
            skills = [s for s in skills if s.get('category') == category]
        
        # 按标签过滤
        if tags:
            filtered_skills = []
            for skill in skills:
                skill_tags = set(skill.get('tags', []))
                if any(tag in skill_tags for tag in tags):
                    filtered_skills.append(skill)
            skills = filtered_skills
        
        return skills
    
    def search_skills(self, 
                      query: str,
                      search_in: List[str] = None,
                      limit: int = 10) -> List[Dict]:
        """
        搜索技能
        
        Args:
            query: 搜索词
            search_in: 搜索字段 ['name', 'description', 'tags']
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 匹配的技能列表
        """
        search_in = search_in or ['name', 'description', 'tags']
        query_lower = query.lower()
        
        results = []
        scores = {}
        
        for skill_name, skill_info in self.skills.items():
            score = 0.0
            
            # 在名称中搜索
            if 'name' in search_in:
                name = skill_info.get('name', '').lower()
                if query_lower in name:
                    score += 10.0
                elif any(word in name for word in query_lower.split()):
                    score += 5.0
            
            # 在描述中搜索
            if 'description' in search_in:
                desc = skill_info.get('description', '').lower()
                if query_lower in desc:
                    score += 5.0
                elif any(word in desc for word in query_lower.split()):
                    score += 2.0
            
            # 在标签中搜索
            if 'tags' in search_in:
                tags = ' '.join(skill_info.get('tags', [])).lower()
                if query_lower in tags:
                    score += 3.0
            
            # 在分类中搜索
            if 'category' in search_in:
                category = skill_info.get('category', '').lower()
                if query_lower in category:
                    score += 2.0
            
            # 如果有匹配，添加到结果
            if score > 0:
                scores[skill_name] = score
                results.append(skill_info)
        
        # 按评分排序
        results.sort(key=lambda x: scores.get(x['name'], 0), reverse=True)
        
        # 限制返回数量
        return results[:limit]
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set()
        for skill_info in self.skills.values():
            category = skill_info.get('category', 'general')
            categories.add(category)
        return sorted(list(categories))
    
    def get_tags(self) -> List[str]:
        """获取所有标签"""
        tags = set()
        for skill_info in self.skills.values():
            for tag in skill_info.get('tags', []):
                tags.add(tag)
        return sorted(list(tags))
    
    def update_skill_usage(self, skill_name: str) -> Dict:
        """
        更新技能使用计数
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Dict: 更新结果
        """
        if skill_name not in self.skills:
            return {
                'success': False,
                'error': f'技能 {skill_name} 不存在'
            }
        
        self.skills[skill_name]['usage_count'] = self.skills[skill_name].get('usage_count', 0) + 1
        self.skills[skill_name]['updated_at'] = datetime.now().isoformat()
        self._save_registry()
        
        return {
            'success': True,
            'usage_count': self.skills[skill_name]['usage_count']
        }
    
    def rate_skill(self, skill_name: str, rating: float) -> Dict:
        """
        评分技能
        
        Args:
            skill_name: 技能名称
            rating: 评分（0-5）
            
        Returns:
            Dict: 评分结果
        """
        if skill_name not in self.skills:
            return {
                'success': False,
                'error': f'技能 {skill_name} 不存在'
            }
        
        if not 0 <= rating <= 5:
            return {
                'success': False,
                'error': '评分必须在 0-5 之间'
            }
        
        # 简单平均（实际应该用更复杂的算法）
        current_rating = self.skills[skill_name].get('rating', 0.0)
        usage_count = self.skills[skill_name].get('usage_count', 0)
        
        # 防止除零错误，如果是第一次评分，直接使用评分值
        if usage_count == 0:
            new_rating = rating
        else:
            new_rating = ((current_rating * usage_count) + rating) / (usage_count + 1)
        
        self.skills[skill_name]['rating'] = round(new_rating, 2)
        self.skills[skill_name]['usage_count'] = usage_count + 1
        self._save_registry()
        
        return {
            'success': True,
            'rating': self.skills[skill_name]['rating']
        }
    
    def _load_registry(self):
        """加载注册表"""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.skills = data.get('skills', {})
            except Exception as e:
                print(f"加载注册表失败：{e}")
                self.skills = {}
        else:
            self.skills = {}
    
    def _save_registry(self):
        """保存注册表"""
        try:
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'skills': self.skills,
                    'updated_at': datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存注册表失败：{e}")
    
    def _get_skill_file_path(self, skill_class: type) -> str:
        """获取技能文件路径"""
        module = skill_class.__module__
        return f"{module.replace('.', '/')}.py"


class SkillSearchEngine:
    """技能搜索引擎"""
    
    def __init__(self, registry: SkillRegistry):
        """
        初始化技能搜索引擎
        
        Args:
            registry: 技能注册中心
        """
        self.registry = registry
        self.search_history = []
    
    def search(self, 
               query: str,
               filters: Optional[Dict] = None,
               sort_by: str = 'relevance',
               limit: int = 10) -> Dict:
        """
        搜索技能
        
        Args:
            query: 搜索词
            filters: 过滤器 {category, tags, permissions}
            sort_by: 排序方式 (relevance/rating/usage_count/name)
            limit: 返回数量
            
        Returns:
            Dict: 搜索结果
        """
        start_time = datetime.now()
        
        # 搜索技能
        results = self.registry.search_skills(query, limit=limit * 2)
        
        # 应用过滤器
        if filters:
            results = self._apply_filters(results, filters)
        
        # 排序
        results = self._sort_results(results, sort_by)
        
        # 限制数量
        results = results[:limit]
        
        # 记录搜索历史
        self._record_search(query, len(results), (datetime.now() - start_time).total_seconds())
        
        return {
            'success': True,
            'query': query,
            'results': results,
            'total': len(results),
            'search_time_ms': (datetime.now() - start_time).total_seconds() * 1000,
        }
    
    def _apply_filters(self, 
                       results: List[Dict],
                       filters: Dict) -> List[Dict]:
        """应用过滤器"""
        filtered = results
        
        # 分类过滤
        if 'category' in filters:
            filtered = [r for r in filtered if r.get('category') == filters['category']]
        
        # 标签过滤
        if 'tags' in filters:
            tags = set(filters['tags'])
            filtered = [r for r in filtered if any(tag in r.get('tags', []) for tag in tags)]
        
        # 权限过滤
        if 'permissions' in filters:
            perms = set(filters['permissions'])
            filtered = [r for r in filtered if not perms - set(r.get('permissions', []))]
        
        # 启用状态过滤
        if 'enabled' in filters:
            if filters['enabled']:
                filtered = [r for r in filtered if r.get('enabled', True)]
        
        return filtered
    
    def _sort_results(self, 
                      results: List[Dict],
                      sort_by: str) -> List[Dict]:
        """排序结果"""
        if sort_by == 'relevance':
            # 按相关性（已经在搜索时排序）
            return results
        elif sort_by == 'rating':
            return sorted(results, key=lambda x: x.get('rating', 0), reverse=True)
        elif sort_by == 'usage_count':
            return sorted(results, key=lambda x: x.get('usage_count', 0), reverse=True)
        elif sort_by == 'name':
            return sorted(results, key=lambda x: x.get('name', ''))
        else:
            return results
    
    def _record_search(self, query: str, results_count: int, search_time: float):
        """记录搜索历史"""
        self.search_history.append({
            'query': query,
            'results_count': results_count,
            'search_time': search_time,
            'timestamp': datetime.now().isoformat()
        })
        
        # 只保留最近 100 次搜索
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]


# 便捷函数
def create_registry(config: Optional[Dict] = None) -> SkillRegistry:
    """创建技能注册中心"""
    return SkillRegistry(config)


def create_search_engine(registry: SkillRegistry) -> SkillSearchEngine:
    """创建技能搜索引擎"""
    return SkillSearchEngine(registry)


# 测试
if __name__ == '__main__':
    print("=" * 60)
    print("技能搜索基础架构测试")
    print("=" * 60)
    
    # 创建注册中心
    registry = SkillRegistry({
        'registry_file': './data/test_skill_registry.json'
    })
    
    # 测试技能注册
    print("\n1. 测试技能注册")
    
    # 导入技能类
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from opc_skills.web_search import WebSearchSkill
    from opc_skills.document_processor import DocumentProcessorSkill
    from opc_skills.content_summary import ContentSummarySkill
    
    # 注册技能
    result = registry.register_skill(WebSearchSkill)
    print(f"注册 WebSearchSkill: {result['success']}")
    
    result = registry.register_skill(DocumentProcessorSkill)
    print(f"注册 DocumentProcessorSkill: {result['success']}")
    
    result = registry.register_skill(ContentSummarySkill)
    print(f"注册 ContentSummarySkill: {result['success']}")
    
    # 测试列出技能
    print("\n2. 测试列出技能")
    skills = registry.list_skills()
    print(f"已注册技能数：{len(skills)}")
    
    for skill in skills:
        print(f"  - {skill['name']} ({skill['category']})")
    
    # 测试搜索技能
    print("\n3. 测试搜索技能")
    search_engine = SkillSearchEngine(registry)
    
    result = search_engine.search('搜索', limit=5)
    print(f"搜索'搜索': 找到 {result['total']} 个结果")
    for r in result['results']:
        print(f"  - {r['name']}: {r['description'][:50]}...")
    
    result = search_engine.search('文档', limit=5)
    print(f"\n搜索'文档': 找到 {result['total']} 个结果")
    for r in result['results']:
        print(f"  - {r['name']}: {r['description'][:50]}...")
    
    result = search_engine.search('摘要', limit=5)
    print(f"\n搜索'摘要': 找到 {result['total']} 个结果")
    for r in result['results']:
        print(f"  - {r['name']}: {r['description'][:50]}...")
    
    # 测试分类和标签
    print("\n4. 测试分类和标签")
    categories = registry.get_categories()
    print(f"分类：{categories}")
    
    tags = registry.get_tags()
    print(f"标签：{tags}")
    
    # 测试技能使用计数
    print("\n5. 测试技能使用计数")
    result = registry.update_skill_usage('web_search')
    print(f"web_search 使用次数：{result.get('usage_count', 0)}")
    
    result = registry.update_skill_usage('web_search')
    print(f"web_search 使用次数：{result.get('usage_count', 0)}")
    
    # 测试技能评分
    print("\n6. 测试技能评分")
    result = registry.rate_skill('web_search', 4.5)
    print(f"web_search 评分：{result.get('rating', 0)}")
    
    result = registry.rate_skill('web_search', 5.0)
    print(f"web_search 评分：{result.get('rating', 0)}")
    
    # 测试获取技能
    print("\n7. 测试获取技能详情")
    skill = registry.get_skill('web_search')
    if skill:
        print(f"技能名称：{skill['name']}")
        print(f"技能描述：{skill['description']}")
        print(f"技能分类：{skill['category']}")
        print(f"技能标签：{skill['tags']}")
        print(f"使用次数：{skill['usage_count']}")
        print(f"技能评分：{skill['rating']}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
