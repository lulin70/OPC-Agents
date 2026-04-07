#!/usr/bin/env python3
"""
场景 2: 经验库学习与复用

用户旅程：
1. 完成第一个任务，积累经验
2. 完成第二个类似任务，积累经验
3. 第三个任务自动复用历史经验
4. 验证系统越用越聪明

验证点：
- 经验正确分类和存储
- 经验权重计算准确
- 冲突经验正确处理
- 高价值经验优先检索
- 遗忘机制正常工作
"""

import pytest
from datetime import datetime, timedelta
from opc_manager.context_manager import ExperienceItem, ExperienceType


class TestExperienceLibraryLearning:
    """经验库学习与复用测试"""
    
    def test_experience_accumulation(self, clean_context):
        """测试经验积累"""
        
        # 任务 1: Web 开发任务
        exp1 = ExperienceItem(
            task_type="web_development",
            task_description="开发电商网站",
            success=True,
            experience_type=ExperienceType.TASK_PATTERN.value,
            lessons_learned=["使用响应式设计", "实现购物车功能"],
            best_practices=["移动端优先", "使用组件库"],
            confidence=0.9,
            source="task_completion"
        )
        
        clean_context.global_context.add_experience(exp1)
        
        # 任务 2: 另一个 Web 开发任务
        exp2 = ExperienceItem(
            task_type="web_development",
            task_description="开发博客平台",
            success=True,
            experience_type=ExperienceType.SKILL_USAGE.value,
            lessons_learned=["使用 Markdown 编辑器", "实现评论系统"],
            best_practices=["SEO 优化", "性能优化"],
            confidence=0.85,
            source="task_completion"
        )
        
        clean_context.global_context.add_experience(exp2)
        
        # 验证经验积累
        assert len(clean_context.global_context.experiences) == 2
        
        print("✅ 经验积累测试通过")
    
    def test_experience_weight_calculation(self, clean_context):
        """测试经验权重计算"""
        
        # 创建不同来源的经验
        exp_user = ExperienceItem(
            task_type="test",
            success=True,
            source="user_feedback",
            confidence=1.0,
            usage_count=10
        )
        
        exp_auto = ExperienceItem(
            task_type="test",
            success=True,
            source="auto_optimization",
            confidence=0.7,
            usage_count=1
        )
        
        # 计算权重
        weight_user = clean_context.global_context._calculate_experience_weight(exp_user)
        weight_auto = clean_context.global_context._calculate_experience_weight(exp_auto)
        
        # 验证：用户反馈权重更高
        assert weight_user > weight_auto
        print(f"用户反馈权重：{weight_user:.3f}, 自动推断权重：{weight_auto:.3f}")
        
        print("✅ 经验权重计算测试通过")
    
    def test_experience_retrieval_priority(self, clean_context):
        """测试高价值经验优先检索"""
        
        # 添加多个经验
        for i in range(5):
            exp = ExperienceItem(
                task_type="web_development",
                task_description=f"Web 开发任务{i}",
                success=True,
                experience_type=ExperienceType.AGENT_OPTIMIZATION.value,
                confidence=0.5 + i * 0.1,  # 递增置信度
                usage_count=i * 2
            )
            clean_context.global_context.add_experience(exp)
        
        # 检索经验
        results = clean_context.global_context.find_similar_experiences(
            task_description="Web 开发",
            min_weight=0.3
        )
        
        # 验证：高权重经验排在前面
        assert len(results) > 0
        
        # 验证权重递减
        weights = [clean_context.global_context._calculate_experience_weight(exp) 
                   for exp in results]
        assert weights == sorted(weights, reverse=True)
        
        print("✅ 高价值经验优先检索测试通过")
    
    def test_experience_conflict_detection(self, clean_context):
        """测试经验冲突检测"""
        
        # 经验 1: 推荐使用 React
        exp1 = ExperienceItem(
            task_type="frontend_selection",
            task_description="选择前端框架",
            success=True,
            lessons_learned=["应该使用 React", "React 生态丰富"],
            best_practices=["推荐组件化开发"],
            confidence=0.9
        )
        
        # 经验 2: 不推荐使用 React（冲突）
        exp2 = ExperienceItem(
            task_type="frontend_selection",
            task_description="前端框架选择建议",
            success=False,
            lessons_learned=["不应该使用 React", "React 太重了"],
            best_practices=["避免复杂框架"],
            confidence=0.8
        )
        
        clean_context.global_context.add_experience(exp1)
        clean_context.global_context.add_experience(exp2)
        
        # 验证冲突检测
        assert exp2.conflict_status == "pending"
        assert exp1.id in exp2.conflict_with
        
        print("✅ 经验冲突检测测试通过")
    
    def test_experience_forgetting_mechanism(self, clean_context):
        """测试遗忘机制"""
        
        # 设置经验库容量限制
        clean_context.global_context.MAX_EXPERIENCE = 3
        
        # 添加 5 个经验
        for i in range(5):
            exp = ExperienceItem(
                task_type=f"task_{i}",
                task_description=f"任务{i}",
                success=True,
                confidence=0.3 + i * 0.1  # 递增置信度
            )
            clean_context.global_context.add_experience(exp)
        
        # 验证：只保留 3 个经验
        assert len(clean_context.global_context.experiences) <= 3
        
        # 验证：保留的是高权重的
        for exp_id in clean_context.global_context.experiences:
            exp = clean_context.global_context.experiences[exp_id]
            weight = clean_context.global_context._calculate_experience_weight(exp)
            assert weight > 0.2  # 低权重的已被淘汰
        
        print("✅ 遗忘机制测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
