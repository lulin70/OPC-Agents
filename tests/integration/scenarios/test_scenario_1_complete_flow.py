#!/usr/bin/env python3
"""
场景 1: 完整任务流程 - 从用户指令到交付

用户旅程：
1. 用户提交任务指令
2. 总裁办意图判断
3. 三贤者决策和任务分解
4. 智能角色匹配
5. Agent 执行任务
6. 完成校验
7. 经验沉淀
8. 结果交付

验证点：
- 任务正确分解
- Agent 匹配准确
- 上下文正确传递
- 经验库更新
- 交付物生成
"""

import pytest
import time
from pathlib import Path
from datetime import datetime


class TestCompleteTaskFlow:
    """完整任务流程集成测试"""
    
    def test_task_decomposition_and_execution(self, opc_manager, clean_context):
        """测试任务从分解到执行的完整流程"""
        
        # 1. 用户提交任务
        user_request = "帮我创建一个简单的待办事项 Web 应用，需要前端和后端"
        
        # 2. 任务分解
        decomposition_result = opc_manager.decompose_task(
            task=user_request,
            synthesis=None,
            user_request=user_request
        )
        
        # 验证任务分解
        assert "execution_steps" in decomposition_result
        assert len(decomposition_result["execution_steps"]) > 0
        
        # 验证步骤包含必要信息
        for step in decomposition_result["execution_steps"]:
            assert "task" in step
            assert "department" in step
            assert "deliverable" in step
            assert "acceptance_criteria" in step
        
        # 3. 验证上下文注入
        task_context = clean_context.get_task_context()
        assert task_context is not None
        
        # 4. 验证经验沉淀（任务完成后）
        # 模拟任务完成
        experience_item = {
            "task_type": "web_development",
            "task_description": "创建待办事项应用",
            "success": True,
            "lessons_learned": ["使用响应式设计", "实现 RESTful API"],
            "best_practices": ["先设计数据库模型", "编写单元测试"],
            "experience_type": "agent_optimization",
            "confidence": 0.9,
            "source": "task_completion"
        }
        
        # 添加到经验库
        from opc_manager.context_manager import ExperienceItem
        exp = ExperienceItem(**experience_item)
        clean_context.global_context.add_experience(exp)
        
        # 验证经验已保存
        assert len(clean_context.global_context.experiences) > 0
        
        # 5. 验证经验检索
        similar_exps = clean_context.global_context.find_similar_experiences(
            task_description="创建 Web 应用",
            experience_type="agent_optimization",
            min_weight=0.3
        )
        
        assert len(similar_exps) > 0
        assert similar_exps[0].experience_type == "agent_optimization"
        
        print("✅ 完整任务流程测试通过")
    
    def test_context_injection_and_retrieval(self, clean_context):
        """测试上下文注入和检索"""
        
        # 1. 添加知识到全局上下文
        from opc_manager.context_manager import KnowledgeItem
        
        knowledge = KnowledgeItem(
            domain="web_development",
            content="React 最佳实践：组件化、状态管理、性能优化",
            keywords=["react", "frontend", "best practices"],
            source="expert_knowledge"
        )
        
        clean_context.global_context.add_knowledge(knowledge)
        
        # 2. 验证知识检索
        retrieved = clean_context.global_context.search_knowledge(
            keywords=["react", "frontend"],
            limit=5
        )
        
        assert len(retrieved) > 0
        assert "react" in retrieved[0].keywords
        
        print("✅ 上下文注入和检索测试通过")
    
    def test_multi_agent_collaboration(self, opc_manager, clean_context):
        """测试多 Agent 协作"""
        
        # 1. 创建多步骤任务
        task_steps = [
            {"step": 1, "task": "需求分析", "department": "product"},
            {"step": 2, "task": "UI 设计", "department": "design"},
            {"step": 3, "task": "前端开发", "department": "engineering"},
            {"step": 4, "task": "后端开发", "department": "engineering"}
        ]
        
        # 2. 验证 Agent 匹配
        for step in task_steps:
            matched_agent = opc_manager.hr_enhancement.match_role(
                task_description=step["task"],
                department=step["department"]
            )
            
            assert matched_agent is not None
            print(f"步骤 {step['step']}: 匹配到 Agent - {matched_agent.get('name', 'Unknown')}")
        
        print("✅ 多 Agent 协作测试通过")
    
    def test_task_completion_validation(self, opc_manager, tmp_path):
        """测试任务完成校验"""
        
        # 1. 创建临时交付物
        deliverable_path = tmp_path / "test_deliverable.md"
        deliverable_path.write_text("# 测试文档\n\n这是一个测试交付物。\n\n## 功能\n- 功能 1\n- 功能 2")
        
        # 2. 创建验收标准
        acceptance_criteria = [
            "包含标题",
            "包含功能描述",
            "内容非空"
        ]
        
        # 3. 验证交付物
        from opc_manager.completion_checker import CompletionChecker
        
        checker = CompletionChecker()
        validation_result = checker.validate_deliverable(
            deliverable_path=str(deliverable_path),
            acceptance_criteria=acceptance_criteria
        )
        
        # 验证结果
        assert validation_result["passed"] is True
        assert validation_result["checks"]["file_exists"] is True
        assert validation_result["checks"]["non_empty"] is True
        
        print("✅ 任务完成校验测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
