#!/usr/bin/env python3
"""
测试上下文管理器的增强功能
- 经验分类系统
- 权重计算
- 冲突检测
- 遗忘机制
"""

import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from opc_manager.context_manager import (
    GlobalContext,
    ExperienceItem,
    ExperienceType,
    ConflictType
)
import shutil


class TestExperienceTypes:
    """测试经验分类系统"""
    
    def test_experience_type_enum(self):
        """测试经验类型枚举"""
        assert ExperienceType.USER_PREFERENCE.value == "user_preference"
        assert ExperienceType.CORRECTION.value == "correction"
        assert ExperienceType.DECISION.value == "decision"
        assert ExperienceType.TASK_PATTERN.value == "task_pattern"
        assert ExperienceType.AGENT_OPTIMIZATION.value == "agent_optimization"
        assert ExperienceType.SKILL_USAGE.value == "skill_usage"
    
    def test_create_experience_with_type(self):
        """测试创建带类型的经验"""
        exp = ExperienceItem(
            task_type="web_development",
            task_description="开发待办事项应用",
            success=True,
            experience_type=ExperienceType.AGENT_OPTIMIZATION.value,
            confidence=0.9
        )
        
        assert exp.experience_type == "agent_optimization"
        assert exp.confidence == 0.9
        assert exp.weight == 1.0  # 初始权重


class TestWeightCalculation:
    """测试权重计算机制"""
    
    @pytest.fixture
    def context(self, tmp_path):
        """创建临时上下文"""
        ctx = GlobalContext(str(tmp_path / "context"))
        yield ctx
        # 清理
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    def test_initial_weight(self, context):
        """测试初始权重"""
        exp = ExperienceItem(
            task_type="test",
            success=True,
            confidence=1.0
        )
        
        weight = context._calculate_experience_weight(exp)
        assert 0.7 <= weight <= 1.0  # 新经验权重应该较高（约 0.78）
    
    def test_weight_with_usage(self, context):
        """测试使用次数对权重的影响"""
        exp1 = ExperienceItem(
            task_type="test",
            success=True,
            usage_count=0
        )
        
        exp2 = ExperienceItem(
            task_type="test",
            success=True,
            usage_count=10
        )
        
        weight1 = context._calculate_experience_weight(exp1)
        weight2 = context._calculate_experience_weight(exp2)
        
        assert weight2 > weight1  # 使用次数多的权重更高
    
    def test_weight_decay_over_time(self, context):
        """测试时间衰减"""
        from datetime import datetime, timedelta
        
        # 创建旧经验
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        exp_old = ExperienceItem(
            task_type="test",
            success=True,
            created_at=old_date,
            usage_count=0
        )
        
        # 创建新经验
        exp_new = ExperienceItem(
            task_type="test",
            success=True,
            usage_count=0
        )
        
        weight_old = context._calculate_experience_weight(exp_old)
        weight_new = context._calculate_experience_weight(exp_new)
        
        assert weight_new > weight_old  # 新经验权重更高
    
    def test_source_reliability(self, context):
        """测试来源可靠性对权重的影响"""
        exp_user = ExperienceItem(
            task_type="test",
            success=True,
            source="user_feedback"
        )
        
        exp_auto = ExperienceItem(
            task_type="test",
            success=True,
            source="auto_optimization"
        )
        
        weight_user = context._calculate_experience_weight(exp_user)
        weight_auto = context._calculate_experience_weight(exp_auto)
        
        assert weight_user > weight_auto  # 用户反馈权重更高


class TestConflictDetection:
    """测试冲突检测机制"""
    
    @pytest.fixture
    def context(self, tmp_path):
        """创建临时上下文"""
        ctx = GlobalContext(str(tmp_path / "context"))
        yield ctx
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    def test_detect_contradictory_experiences(self, context):
        """检测矛盾经验"""
        exp1 = ExperienceItem(
            task_type="code_review",
            task_description="代码审查最佳实践",
            success=True,
            lessons_learned=["应该编写单元测试"],
            best_practices=["推荐 TDD 开发"]
        )
        
        exp2 = ExperienceItem(
            task_type="code_review",
            task_description="代码审查方法",
            success=False,
            lessons_learned=["不应该花费太多时间在测试上"],
            best_practices=["避免过度测试"]
        )
        
        # 添加第一个经验
        context.add_experience(exp1)
        
        # 检测第二个经验是否冲突
        conflicts = context._detect_conflicts(exp2)
        assert len(conflicts) > 0
        assert conflicts[0].id == exp1.id
    
    def test_no_conflict_different_types(self, context):
        """不同类型经验不冲突"""
        exp1 = ExperienceItem(
            task_type="web_dev",
            success=True,
            lessons_learned=["应该使用 React"]
        )
        
        exp2 = ExperienceItem(
            task_type="data_analysis",
            success=True,
            lessons_learned=["应该使用 Pandas"]
        )
        
        context.add_experience(exp1)
        conflicts = context._detect_conflicts(exp2)
        
        assert len(conflicts) == 0


class TestExperienceRetrieval:
    """测试经验检索增强"""
    
    @pytest.fixture
    def context(self, tmp_path):
        """创建临时上下文"""
        ctx = GlobalContext(str(tmp_path / "context"))
        yield ctx
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    def test_retrieve_by_type(self, context):
        """按类型检索经验"""
        # 添加不同类型经验
        exp1 = ExperienceItem(
            task_type="web_dev",
            task_description="开发网站",
            experience_type=ExperienceType.TASK_PATTERN.value,
            success=True
        )
        
        exp2 = ExperienceItem(
            task_type="web_dev",
            task_description="网站优化",
            experience_type=ExperienceType.SKILL_USAGE.value,
            success=True
        )
        
        context.add_experience(exp1)
        context.add_experience(exp2)
        
        # 按类型过滤
        results = context.find_similar_experiences(
            "开发网站",
            experience_type=ExperienceType.TASK_PATTERN.value
        )
        
        assert len(results) > 0
        assert results[0].experience_type == "task_pattern"
    
    def test_retrieve_by_weight(self, context):
        """按权重过滤经验"""
        # 添加低权重经验
        exp_low = ExperienceItem(
            task_type="test",
            task_description="低质量经验",
            confidence=0.3
        )
        
        # 添加高权重经验
        exp_high = ExperienceItem(
            task_type="test",
            task_description="高质量经验",
            confidence=0.9
        )
        
        context.add_experience(exp_low)
        context.add_experience(exp_high)
        
        # 只检索高权重经验
        results = context.find_similar_experiences(
            "test",
            min_weight=0.5
        )
        
        # 应该只返回高权重经验
        for exp in results:
            assert exp.confidence > 0.5


class TestForgettingMechanism:
    """测试遗忘机制"""
    
    @pytest.fixture
    def context(self, tmp_path):
        """创建临时上下文"""
        # 设置很小的容量以触发驱逐
        ctx = GlobalContext(str(tmp_path / "context"))
        ctx.MAX_EXPERIENCE = 3
        yield ctx
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    def test_evict_low_weight_experiences(self, context):
        """测试驱逐低权重经验"""
        # 添加多个经验
        for i in range(5):
            exp = ExperienceItem(
                task_type=f"task_{i}",
                task_description=f"任务{i}",
                confidence=0.3  # 低置信度
            )
            context.add_experience(exp)
        
        # 应该只保留 3 个经验
        assert len(context.experiences) <= 3
        
        # 保留的应该是权重较高的
        for exp in context.experiences.values():
            assert exp.weight > 0.2


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    @pytest.fixture
    def context(self, tmp_path):
        """创建临时上下文"""
        ctx = GlobalContext(str(tmp_path / "context"))
        yield ctx
        shutil.rmtree(tmp_path, ignore_errors=True)
    
    def test_old_experience_format(self, context):
        """测试旧格式经验仍然可用"""
        # 创建不带新字段的老经验
        old_exp = ExperienceItem(
            task_type="old_task",
            task_description="老任务",
            success=True
        )
        
        # 应该有默认值
        assert old_exp.experience_type == "agent_optimization"
        assert old_exp.weight == 1.0
        assert old_exp.confidence == 1.0
        assert old_exp.conflict_status == "none"
        
        # 应该能正常添加
        context.add_experience(old_exp)
        assert old_exp.id in context.experiences


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
