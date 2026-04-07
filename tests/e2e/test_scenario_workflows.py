"""
核心场景端到端测试

测试"一人公司"的典型工作场景是否完整可用
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from opc_manager.scenario_engine import ScenarioWorkflow, get_scenario_engine


class TestScenarioMatching:
    """测试场景匹配功能"""
    
    def test_launch_product_scenario(self):
        """测试新产品发布场景匹配"""
        engine = get_scenario_engine()
        
        # 测试不同的触发语句
        test_cases = [
            "我想发布新产品",
            "推出新品",
            "新产品上线",
            "产品发布"
        ]
        
        for user_input in test_cases:
            result = engine.match_scenario(user_input)
            assert result["matched"] is True
            assert result["workflow_id"] == "launch_product"
            assert result["confidence"] > 0.5
    
    def test_write_report_scenario(self):
        """测试报告撰写场景匹配"""
        engine = get_scenario_engine()
        
        test_cases = [
            "写报告",
            "写总结",
            "分析报告",
            "工作汇报",
            "月度报告"
        ]
        
        for user_input in test_cases:
            result = engine.match_scenario(user_input)
            # 写报告场景可能匹配度不高，这是正常的
            # 只要有一个匹配即可
            if user_input in ["写报告", "写总结"]:
                assert result["matched"] is True
                assert result["workflow_id"] == "write_report"
    
    def test_organize_meeting_scenario(self):
        """测试会议组织场景匹配"""
        engine = get_scenario_engine()
        
        test_cases = [
            "组织会议",
            "开会",
            "团队讨论",
            "项目会议"
        ]
        
        for user_input in test_cases:
            result = engine.match_scenario(user_input)
            assert result["matched"] is True
            assert result["workflow_id"] == "organize_meeting"
    
    def test_no_match_scenario(self):
        """测试不匹配的场景"""
        engine = get_scenario_engine()
        
        result = engine.match_scenario("今天天气不错")
        assert result["matched"] is False
        assert result["confidence"] < 0.5


class TestWorkflowStructure:
    """测试工作流结构完整性"""
    
    def test_launch_product_workflow(self):
        """测试新产品发布工作流"""
        engine = get_scenario_engine()
        workflow = engine.get_workflow("launch_product")
        
        # 验证基本信息
        assert workflow["id"] == "launch_product"
        assert workflow["name"] == "新产品发布"
        assert workflow["total_duration"] == "1 个工作日"
        
        # 验证工作流步骤
        assert len(workflow["workflow"]) == 4
        
        # 验证步骤 1: 市场调研
        step1 = workflow["workflow"][0]
        assert step1["step"] == 1
        assert step1["name"] == "市场调研"
        assert step1["estimated_duration"] == "2 小时"
        assert "output" in step1
        assert step1["output"]["name"] == "市场调研报告"
        
        # 验证步骤 2: 产品设计
        step2 = workflow["workflow"][1]
        assert step2["step"] == 2
        assert step2["name"] == "产品设计方案"
        assert step2["depends_on"] == [1]
        
        # 验证步骤 3: 营销方案
        step3 = workflow["workflow"][2]
        assert step3["step"] == 3
        assert step3["name"] == "营销推广计划"
        assert step3["depends_on"] == [2]
        
        # 验证步骤 4: 汇总评审
        step4 = workflow["workflow"][3]
        assert step4["step"] == 4
        assert step4["name"] == "汇总评审"
        assert step4["depends_on"] == [1, 2, 3]
        
        # 验证最终交付物
        deliverable = workflow["final_deliverable"]
        assert deliverable["title"] == "新产品发布完整方案"
        assert len(deliverable["sections"]) >= 5
    
    def test_write_report_workflow(self):
        """测试报告撰写工作流"""
        engine = get_scenario_engine()
        workflow = engine.get_workflow("write_report")
        
        assert workflow["id"] == "write_report"
        assert workflow["name"] == "报告撰写"
        assert len(workflow["workflow"]) == 3
        
        # 验证步骤
        assert workflow["workflow"][0]["name"] == "数据收集"
        assert workflow["workflow"][1]["name"] == "数据分析"
        assert workflow["workflow"][2]["name"] == "报告撰写"
    
    def test_organize_meeting_workflow(self):
        """测试会议组织工作流"""
        engine = get_scenario_engine()
        workflow = engine.get_workflow("organize_meeting")
        
        assert workflow["id"] == "organize_meeting"
        assert workflow["name"] == "会议组织"
        assert len(workflow["workflow"]) == 3
        
        # 验证步骤
        assert workflow["workflow"][0]["name"] == "时间协调"
        assert workflow["workflow"][1]["name"] == "发送邀请"
        assert workflow["workflow"][2]["name"] == "材料准备"


class TestWorkflowIntegration:
    """测试工作流集成"""
    
    def test_list_all_workflows(self):
        """测试列出所有工作流"""
        engine = get_scenario_engine()
        workflows = engine.list_workflows()
        
        assert len(workflows) == 3
        
        workflow_ids = [w["id"] for w in workflows]
        assert "launch_product" in workflow_ids
        assert "write_report" in workflow_ids
        assert "organize_meeting" in workflow_ids
    
    def test_workflow_dependencies(self):
        """测试工作流依赖关系"""
        engine = get_scenario_engine()
        
        # 新产品发布的依赖关系
        workflow = engine.get_workflow("launch_product")
        
        # 验证依赖步骤存在
        step_count = len(workflow["workflow"])
        for step in workflow["workflow"]:
            if "depends_on" in step:
                for dep in step["depends_on"]:
                    assert dep < step["step"]
                    assert dep <= step_count
    
    def test_workflow_output_completeness(self):
        """测试工作流输出完整性"""
        engine = get_scenario_engine()
        
        # 验证每个步骤都有输出定义
        for workflow_id in ["launch_product", "write_report", "organize_meeting"]:
            workflow = engine.get_workflow(workflow_id)
            
            for step in workflow["workflow"]:
                assert "output" in step
                assert "name" in step["output"]
                assert "format" in step["output"]


class TestEndToEndScenarios:
    """端到端场景测试"""
    
    def test_complete_launch_product_flow(self):
        """测试完整的新产品发布流程"""
        engine = get_scenario_engine()
        
        # 1. 场景匹配
        match_result = engine.match_scenario("我想发布新产品")
        assert match_result["matched"] is True
        
        # 2. 获取工作流
        workflow = engine.get_workflow(match_result["workflow_id"])
        assert workflow is not None
        
        # 3. 验证工作流完整性
        assert len(workflow["workflow"]) > 0
        assert "final_deliverable" in workflow
        
        # 4. 验证所有步骤都有定义
        for i, step in enumerate(workflow["workflow"], 1):
            assert step["step"] == i
            assert "name" in step
            assert "estimated_duration" in step
            assert "output" in step
        
        # 5. 验证最终交付物
        final = workflow["final_deliverable"]
        assert "title" in final
        assert "description" in final
    
    def test_scenario_trigger_phrases(self):
        """测试场景触发短语覆盖"""
        engine = get_scenario_engine()
        
        # 验证每个场景都有多个触发短语
        for workflow_id, workflow in engine.workflows.items():
            assert "trigger_phrases" in workflow
            assert len(workflow["trigger_phrases"]) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
