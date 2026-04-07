"""
场景引擎 - 核心工作流管理

实现"一人公司"典型场景的自动化工作流
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta


class ScenarioWorkflow:
    """场景工作流定义"""
    
    def __init__(self):
        self.workflows = self._init_workflows()
    
    def _init_workflows(self) -> Dict[str, Dict]:
        """初始化所有场景工作流"""
        return {
            "launch_product": self._launch_product_workflow(),
            "write_report": self._write_report_workflow(),
            "organize_meeting": self._organize_meeting_workflow()
        }
    
    def _launch_product_workflow(self) -> Dict:
        """发布新产品场景"""
        return {
            "id": "launch_product",
            "name": "新产品发布",
            "description": "完整的新产品发布流程，从市场调研到最终发布",
            "trigger_phrases": [
                "发布新产品",
                "推出新品", 
                "新产品上线",
                "产品发布"
            ],
            "total_duration": "1 个工作日",
            "workflow": [
                {
                    "step": 1,
                    "name": "市场调研",
                    "type": "research",
                    "description": "分析目标市场、竞争对手和目标用户",
                    "estimated_duration": "2 小时",
                    "output": {
                        "name": "市场调研报告",
                        "format": "PDF/Word",
                        "includes": [
                            "市场规模分析",
                            "竞争对手分析",
                            "目标用户画像",
                            "市场机会点"
                        ]
                    }
                },
                {
                    "step": 2,
                    "name": "产品设计方案",
                    "type": "design",
                    "description": "基于调研结果设计产品方案",
                    "estimated_duration": "3 小时",
                    "depends_on": [1],
                    "output": {
                        "name": "产品需求文档",
                        "format": "PDF/Word",
                        "includes": [
                            "产品定位",
                            "功能列表",
                            "技术方案",
                            "原型设计"
                        ]
                    }
                },
                {
                    "step": 3,
                    "name": "营销推广计划",
                    "type": "marketing",
                    "description": "制定产品营销和推广策略",
                    "estimated_duration": "2 小时",
                    "depends_on": [2],
                    "output": {
                        "name": "营销推广方案",
                        "format": "PDF/Word",
                        "includes": [
                            "营销策略",
                            "推广渠道",
                            "预算估算",
                            "时间规划"
                        ]
                    }
                },
                {
                    "step": 4,
                    "name": "汇总评审",
                    "type": "review",
                    "description": "汇总所有文档，进行最终评审",
                    "estimated_duration": "1 小时",
                    "depends_on": [1, 2, 3],
                    "output": {
                        "name": "新产品发布方案（完整版）",
                        "format": "PDF",
                        "includes": [
                            "市场调研报告",
                            "产品需求文档",
                            "营销推广方案",
                            "发布预算总表",
                            "时间规划总表"
                        ]
                    }
                }
            ],
            "final_deliverable": {
                "title": "新产品发布完整方案",
                "description": "包含从市场调研到营销推广的全套方案",
                "sections": [
                    "执行摘要",
                    "市场分析",
                    "产品方案",
                    "营销策略",
                    "财务预测",
                    "风险评估",
                    "时间规划"
                ]
            }
        }
    
    def _write_report_workflow(self) -> Dict:
        """撰写报告场景"""
        return {
            "id": "write_report",
            "name": "报告撰写",
            "description": "自动收集数据、分析并生成专业报告",
            "trigger_phrases": [
                "写报告",
                "写总结",
                "分析报告",
                "工作汇报",
                "月度报告",
                "季度总结"
            ],
            "total_duration": "2-4 小时",
            "workflow": [
                {
                    "step": 1,
                    "name": "数据收集",
                    "type": "data_collection",
                    "description": "收集相关数据和资料",
                    "estimated_duration": "1 小时",
                    "output": {
                        "name": "数据资料包",
                        "format": "文件夹",
                        "includes": [
                            "历史数据",
                            "行业数据",
                            "相关资料"
                        ]
                    }
                },
                {
                    "step": 2,
                    "name": "数据分析",
                    "type": "analysis",
                    "description": "分析收集的数据，提取关键信息",
                    "estimated_duration": "1 小时",
                    "depends_on": [1],
                    "output": {
                        "name": "分析结果",
                        "format": "Excel/图表",
                        "includes": [
                            "数据图表",
                            "趋势分析",
                            "关键发现"
                        ]
                    }
                },
                {
                    "step": 3,
                    "name": "报告撰写",
                    "type": "writing",
                    "description": "基于分析结果撰写报告",
                    "estimated_duration": "1-2 小时",
                    "depends_on": [2],
                    "output": {
                        "name": "完整报告",
                        "format": "Word/PDF",
                        "includes": [
                            "摘要",
                            "正文",
                            "结论",
                            "建议",
                            "附录"
                        ]
                    }
                }
            ],
            "final_deliverable": {
                "title": "专业分析报告",
                "description": "结构完整、数据详实的专业报告"
            }
        }
    
    def _organize_meeting_workflow(self) -> Dict:
        """组织会议场景"""
        return {
            "id": "organize_meeting",
            "name": "会议组织",
            "description": "自动协调时间、发送邀请、准备材料",
            "trigger_phrases": [
                "组织会议",
                "开会",
                "团队讨论",
                "项目会议",
                "碰头会"
            ],
            "total_duration": "30 分钟 - 1 小时",
            "workflow": [
                {
                    "step": 1,
                    "name": "时间协调",
                    "type": "scheduling",
                    "description": "协调参会人员时间",
                    "estimated_duration": "15 分钟",
                    "output": {
                        "name": "会议时间安排",
                        "format": "日历邀请",
                        "includes": [
                            "建议时间",
                            "备选时间",
                            "参会人员"
                        ]
                    }
                },
                {
                    "step": 2,
                    "name": "发送邀请",
                    "type": "invitation",
                    "description": "发送会议邀请给所有参会人员",
                    "estimated_duration": "5 分钟",
                    "depends_on": [1],
                    "output": {
                        "name": "会议邀请",
                        "format": "邮件/消息",
                        "includes": [
                            "会议主题",
                            "时间地点",
                            "议程",
                            "参会人员"
                        ]
                    }
                },
                {
                    "step": 3,
                    "name": "材料准备",
                    "type": "preparation",
                    "description": "准备会议相关材料",
                    "estimated_duration": "30 分钟",
                    "depends_on": [1],
                    "output": {
                        "name": "会议材料包",
                        "format": "文件夹",
                        "includes": [
                            "会议议程",
                            "背景资料",
                            "讨论要点",
                            "决策事项"
                        ]
                    }
                }
            ],
            "final_deliverable": {
                "title": "会议组织完成",
                "description": "时间确定、邀请发送、材料准备就绪"
            }
        }
    
    def match_scenario(self, user_input: str) -> Dict[str, Any]:
        """
        匹配用户输入到场景
        
        Args:
            user_input: 用户输入
            
        Returns:
            匹配的场景信息，包括置信度
        """
        matched = None
        max_confidence = 0
        
        for workflow_id, workflow in self.workflows.items():
            confidence = self._calculate_confidence(user_input, workflow)
            if confidence > max_confidence:
                max_confidence = confidence
                matched = workflow
        
        if max_confidence > 0.5:
            return {
                "matched": True,
                "workflow": matched,
                "confidence": max_confidence,
                "workflow_id": matched["id"]
            }
        else:
            return {
                "matched": False,
                "confidence": max_confidence
            }
    
    def _calculate_confidence(self, user_input: str, workflow: Dict) -> float:
        """计算用户输入与工作流的匹配度"""
        trigger_phrases = workflow.get("trigger_phrases", [])
        user_input_lower = user_input.lower()
        
        # 精确匹配
        for phrase in trigger_phrases:
            if phrase in user_input_lower:
                return 0.9
        
        # 部分匹配
        keywords = workflow["id"].split("_")
        match_count = sum(1 for keyword in keywords if keyword in user_input_lower)
        
        return match_count / len(keywords) * 0.7
    
    def get_workflow(self, workflow_id: str) -> Dict:
        """获取指定工作流"""
        return self.workflows.get(workflow_id, {})
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        return [
            {
                "id": w["id"],
                "name": w["name"],
                "description": w["description"],
                "total_duration": w["total_duration"]
            }
            for w in self.workflows.values()
        ]


# 单例模式
scenario_engine = ScenarioWorkflow()


def get_scenario_engine() -> ScenarioWorkflow:
    """获取场景引擎实例"""
    return scenario_engine
