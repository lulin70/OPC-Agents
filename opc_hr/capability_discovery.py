"""
HR 主动能力发现器
自动检测能力缺口，主动寻找并推荐安装新的 Agent/Skill
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from opc_skills import SkillRegistry, ClawHubIntegration


class CapabilityGap:
    """能力缺口定义"""
    
    def __init__(self, skill_name: str, required_by: str, priority: int = 5):
        self.skill_name = skill_name
        self.required_by = required_by  # 哪个任务需要
        self.priority = priority  # 1-10
        self.detected_at = datetime.now()


class CapabilityDiscovery:
    """能力发现器"""
    
    def __init__(self, skill_registry: SkillRegistry = None, 
                 clawhub: ClawHubIntegration = None):
        """
        初始化能力发现器
        
        Args:
            skill_registry: 技能注册表
            clawhub: ClawHub 集成
        """
        self.skill_registry = skill_registry or SkillRegistry()
        self.clawhub = clawhub or ClawHubIntegration()
        self.logger = logging.getLogger("OPC-Agents.CapabilityDiscovery")
        
        # 能力缺口队列
        self.gap_queue: List[CapabilityGap] = []
        
        # 已推荐的能力
        self.recommended_skills: Set[str] = set()
        
        # 关键词映射（用户需求→技能关键词）
        self.keyword_mapping = {
            '视频': ['video', 'media', 'ffmpeg'],
            '图片': ['image', 'picture', 'photo', 'pillow'],
            '音频': ['audio', 'sound', 'music'],
            'PDF': ['pdf', 'document'],
            'Excel': ['excel', 'spreadsheet', 'xlsx'],
            'Word': ['word', 'docx', 'document'],
            '搜索': ['search', 'web', 'internet'],
            '翻译': ['translate', 'language'],
            '摘要': ['summary', 'summarize', 'extract'],
            '分析': ['analyze', 'analytics', 'statistics'],
            '图表': ['chart', 'graph', 'plot', 'visualization'],
            '邮件': ['email', 'smtp', 'mail'],
            '日历': ['calendar', 'schedule', 'event'],
            '会议': ['meeting', 'conference', 'zoom'],
        }
        
        self.logger.info("能力发现器初始化完成")
    
    def analyze_user_request(self, user_request: str) -> List[str]:
        """
        分析用户需求，提取所需技能关键词
        
        Args:
            user_request: 用户需求描述
            
        Returns:
            技能关键词列表
        """
        required_keywords = []
        
        # 提取关键词
        for keyword, related_skills in self.keyword_mapping.items():
            if keyword.lower() in user_request.lower():
                required_keywords.extend(related_skills)
        
        self.logger.info(f"从用户需求提取关键词：{required_keywords}")
        return required_keywords
    
    def detect_capability_gap(self, required_keywords: List[str], 
                            context: str = "") -> List[CapabilityGap]:
        """
        检测能力缺口
        
        Args:
            required_keywords: 所需技能关键词
            context: 上下文（哪个任务需要）
            
        Returns:
            能力缺口列表
        """
        # 获取当前所有技能
        current_skills = self.skill_registry.list_skills()
        current_skill_names = {skill['name'].lower() for skill in current_skills}
        current_tags = set()
        for skill in current_skills:
            current_tags.update(tag.lower() for tag in skill.get('tags', []))
        
        gaps = []
        
        # 检测缺失的技能
        for keyword in required_keywords:
            keyword_lower = keyword.lower()
            
            # 检查是否已有相关技能
            has_capability = any(
                keyword_lower in name or keyword_lower in ' '.join(current_tags)
                for name in current_skill_names
            )
            
            if not has_capability and keyword not in [g.skill_name for g in gaps]:
                # 发现能力缺口
                gap = CapabilityGap(
                    skill_name=keyword,
                    required_by=context or "用户需求分析",
                    priority=self._calculate_priority(keyword, context)
                )
                gaps.append(gap)
        
        self.logger.info(f"检测到 {len(gaps)} 个能力缺口")
        return gaps
    
    def _calculate_priority(self, skill_name: str, context: str) -> int:
        """计算技能优先级"""
        priority = 5  # 基础优先级
        
        # 根据技能类型调整
        high_priority_keywords = ['pdf', 'excel', 'word', 'document']
        medium_priority_keywords = ['search', 'analyze', 'summary']
        
        if any(k in skill_name.lower() for k in high_priority_keywords):
            priority += 2
        
        if any(k in skill_name.lower() for k in medium_priority_keywords):
            priority += 1
        
        # 根据上下文调整
        if '紧急' in context or 'urgent' in context.lower():
            priority += 2
        
        return min(10, priority)
    
    def search_alternatives(self, gap: CapabilityGap) -> List[Dict]:
        """
        搜索替代技能（支持 ClawHub 和 MCP GitHub）
        
        Args:
            gap: 能力缺口
            
        Returns:
            候选技能列表
        """
        all_candidates = []
        
        # 1. 尝试从 ClawHub 搜索
        if hasattr(self.clawhub, 'execute'):
            try:
                search_result = self.clawhub.execute(
                    'search_packages',
                    query=gap.skill_name,
                    limit=10
                )
                
                if search_result.get('success'):
                    candidates = search_result.get('packages', [])
                    self.logger.info(f"ClawHub 找到 {len(candidates)} 个候选技能")
                    all_candidates.extend(candidates)
            except Exception as e:
                self.logger.warning(f"ClawHub 搜索失败：{e}")
        
        # 2. 尝试从 MCP GitHub 搜索（新增）
        if hasattr(self.clawhub, 'search_skills'):
            try:
                mcp_skills = self.clawhub.search_skills(gap.skill_name, limit=10)
                if mcp_skills:
                    self.logger.info(f"MCP GitHub 找到 {len(mcp_skills)} 个候选技能")
                    all_candidates.extend(mcp_skills)
            except Exception as e:
                self.logger.warning(f"MCP GitHub 搜索失败：{e}")
        
        self.logger.info(f"总共找到 {len(all_candidates)} 个候选技能")
        return all_candidates
    
    def evaluate_and_test(self, candidates: List[Dict], 
                         gap: CapabilityGap) -> Optional[Dict]:
        """
        评估和测试候选技能
        
        Args:
            candidates: 候选技能列表
            gap: 能力缺口
            
        Returns:
            最佳候选技能
        """
        if not candidates:
            return None
        
        best_candidate = None
        best_score = 0
        
        for candidate in candidates:
            score = self._evaluate_candidate(candidate, gap)
            
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        if best_score > 60:  # 阈值
            self.logger.info(f"选择最佳候选：{best_candidate.get('name')} (评分：{best_score})")
            return best_candidate
        
        self.logger.warning("没有合适的候选技能")
        return None
    
    def _evaluate_candidate(self, candidate: Dict, gap: CapabilityGap) -> float:
        """评估候选技能"""
        score = 0.0
        
        # 名称匹配度 (40 分)
        name = candidate.get('name', '').lower()
        if gap.skill_name.lower() in name:
            score += 40
        
        # 分类匹配度 (20 分)
        category = candidate.get('category', '')
        if category in ['document', 'productivity', 'utility']:
            score += 20
        
        # 评分 (20 分)
        rating = candidate.get('rating', 0)
        score += rating * 4  # 最高 5 分 * 4 = 20 分
        
        # 下载量 (10 分)
        downloads = candidate.get('download_count', 0)
        if downloads > 10000:
            score += 10
        elif downloads > 1000:
            score += 5
        
        # 安全评分 (10 分)
        security_score = candidate.get('security_score', 50)
        score += security_score / 10
        
        return score
    
    def recommend_to_user(self, candidate: Dict, gap: CapabilityGap, 
                         user: Dict) -> Dict:
        """
        向用户推荐技能
        
        Args:
            candidate: 候选技能
            gap: 能力缺口
            user: 用户信息
            
        Returns:
            推荐结果
        """
        # 检查是否已推荐过
        if candidate['name'] in self.recommended_skills:
            return {
                'success': False,
                'reason': '已推荐过该技能'
            }
        
        recommendation = {
            'skill': candidate,
            'reason': f"检测到您需要处理 {gap.required_by}，当前系统缺少 '{gap.skill_name}' 相关能力",
            'priority': gap.priority,
            'benefits': self._generate_benefits(candidate),
            'risks': self._generate_risks(candidate),
            'action_required': '安装此技能后，系统将能够处理相关任务'
        }
        
        # 添加到已推荐列表
        self.recommended_skills.add(candidate['name'])
        
        # 添加到缺口队列
        self.gap_queue.append(gap)
        
        self.logger.info(f"向用户推荐技能：{candidate['name']}")
        
        return {
            'success': True,
            'recommendation': recommendation
        }
    
    def _generate_benefits(self, candidate: Dict) -> List[str]:
        """生成安装好处"""
        benefits = []
        
        category = candidate.get('category', '')
        if category == 'document':
            benefits.append('支持更多文档格式处理')
        elif category == 'productivity':
            benefits.append('提升工作效率')
        
        rating = candidate.get('rating', 0)
        if rating >= 4.5:
            benefits.append(f'高评分技能 ({rating}分)，用户反馈良好')
        
        downloads = candidate.get('download_count', 0)
        if downloads > 10000:
            benefits.append(f'热门技能，下载量 {downloads/10000:.1f}万+')
        
        return benefits
    
    def _generate_risks(self, candidate: Dict) -> List[str]:
        """生成潜在风险"""
        risks = []
        
        security_score = candidate.get('security_score', 50)
        if security_score < 70:
            risks.append(f'安全评分较低 ({security_score}分)，建议审查后安装')
        
        permissions = candidate.get('permissions', [])
        high_risk_perms = ['execute_command', 'delete_file', 'write_environment']
        if any(p in permissions for p in high_risk_perms):
            risks.append('需要高风险权限，请确认必要性')
        
        version = candidate.get('version', 'unknown')
        if version == '0.x.x':
            risks.append('早期版本，可能存在不稳定因素')
        
        return risks
    
    def auto_install(self, candidate: Dict, user_config: Dict) -> Dict:
        """
        自动安装技能（需用户授权）
        
        Args:
            candidate: 候选技能
            user_config: 用户配置（包含自动安装策略）
            
        Returns:
            安装结果
        """
        # 检查自动安装策略
        auto_install_policy = user_config.get('auto_install', False)
        if not auto_install_policy:
            return {
                'success': False,
                'reason': '需要用户手动确认',
                'requires_user_action': True
            }
        
        # 检查安全评分
        min_security_score = user_config.get('min_security_score', 70)
        security_score = candidate.get('security_score', 50)
        if security_score < min_security_score:
            return {
                'success': False,
                'reason': f'安全评分 {security_score} 低于阈值 {min_security_score}',
                'requires_user_action': True
            }
        
        # 执行安装
        try:
            result = self.clawhub.execute(
                'install_package',
                package_name=candidate['name'],
                version=candidate.get('version')
            )
            
            if result.get('success'):
                # 注册到技能注册表
                self._register_installed_skill(candidate)
                
                self.logger.info(f"自动安装技能成功：{candidate['name']}")
                return {
                    'success': True,
                    'message': f'技能 {candidate["name"]} 安装成功'
                }
            
        except Exception as e:
            self.logger.error(f"自动安装失败：{e}")
        
        return {
            'success': False,
            'error': str(e)
        }
    
    def _register_installed_skill(self, candidate: Dict):
        """注册已安装的技能"""
        # 这里应该调用技能注册表的注册方法
        # 由于是动态安装，需要重新加载技能模块
        pass
    
    def get_gap_queue(self) -> List[CapabilityGap]:
        """获取能力缺口队列"""
        return self.gap_queue
    
    def clear_gap(self, skill_name: str):
        """清除已解决的能力缺口"""
        self.gap_queue = [
            gap for gap in self.gap_queue 
            if gap.skill_name != skill_name
        ]
        self.logger.info(f"清除能力缺口：{skill_name}")


# 使用示例
if __name__ == '__main__':
    # 创建发现器
    discovery = CapabilityDiscovery()
    
    # 场景 1: 用户提交视频处理任务
    print("\n[场景 1] 用户需要处理视频")
    user_request = "帮我剪辑这个产品宣传视频"
    
    # 分析需求
    keywords = discovery.analyze_user_request(user_request)
    print(f"提取关键词：{keywords}")
    
    # 检测缺口
    gaps = discovery.detect_capability_gap(keywords, user_request)
    print(f"发现 {len(gaps)} 个能力缺口:")
    for gap in gaps:
        print(f"  - {gap.skill_name} (优先级：{gap.priority})")
    
    # 搜索替代
    for gap in gaps:
        candidates = discovery.search_alternatives(gap)
        print(f"\n为 '{gap.skill_name}' 找到 {len(candidates)} 个候选")
        
        # 评估
        best = discovery.evaluate_and_test(candidates, gap)
        if best:
            print(f"最佳候选：{best['name']} (评分：best.get('rating', 'N/A'))")
            
            # 推荐
            user = {'name': '张三', 'config': {}}
            result = discovery.recommend_to_user(best, gap, user)
            if result['success']:
                rec = result['recommendation']
                print(f"\n推荐理由：{rec['reason']}")
                print(f"好处:")
                for benefit in rec['benefits']:
                    print(f"  ✓ {benefit}")
                print(f"风险:")
                for risk in rec['risks']:
                    print(f"  ⚠ {risk}")
