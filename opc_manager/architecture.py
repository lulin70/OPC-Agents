#!/usr/bin/env python3
"""
Architecture management for OPC Manager
"""

from typing import Dict, List, Any

class ArchitectureManager:
    """Architecture manager for OPC-Agents system"""
    
    def __init__(self, agent_manager):
        """Initialize the Architecture Manager"""
        self.agent_manager = agent_manager
        self.three_layer_architecture = self._initialize_three_layer_architecture()
    
    def _initialize_three_layer_architecture(self) -> Dict[str, Any]:
        """Initialize the three-layer architecture: Executive Office Agents / Department Agents / Employee Agents"""
        print("[系统架构] 初始化三层架构...")
        
        # 构建三层架构
        architecture = {
            "executive_office": {
                "agents": self.agent_manager.get_executive_office_agents(),
                "description": "总裁办，负责战略决策、任务分配和全局协调",
                "authority": "最高决策机构，拥有对所有部门的指挥权",
                "responsibilities": [
                    "制定公司战略和目标",
                    "分配和协调跨部门任务",
                    "监控各部门工作进度",
                    "解决部门间冲突",
                    "资源分配和优化",
                    "最终决策和审批"
                ]
            },
            "departments": {},
            "employees": {}
        }
        
        # 加载部门和员工Agent
        departments = self.agent_manager.get_departments()
        for department in departments:
            if department != "executive_office":  # 总裁办单独处理
                department_agents = self.agent_manager.get_official_agent_by_department(department)
                custom_agents = self.agent_manager.get_agent_by_department(department)
                
                architecture["departments"][department] = {
                    "agents": department_agents,
                    "custom_agents": custom_agents,
                    "description": f"{department}部门，负责相关业务处理",
                    "report_to": "executive_office",
                    "coordination_with": [d for d in departments if d != department and d != "executive_office"],
                    "responsibilities": []
                }
                
                # 为每个部门创建员工Agent
                for agent in department_agents:
                    agent_id = agent.get('name')
                    architecture["employees"][agent_id] = {
                        "department": department,
                        "type": "official",
                        "info": agent,
                        "report_to": f"{department}_manager"
                    }
                
                for agent_name in custom_agents:
                    architecture["employees"][agent_name] = {
                        "department": department,
                        "type": "custom",
                        "report_to": f"{department}_manager"
                    }
        
        # 增强总裁办与部门之间的协作机制
        self._enhance_executive_office_coordination(architecture)
        
        print("[系统架构] 三层架构初始化完成")
        print(f"[系统架构] 总裁办Agent数量: {len(architecture['executive_office']['agents'])}")
        print(f"[系统架构] 部门数量: {len(architecture['departments'])}")
        print(f"[系统架构] 员工Agent数量: {len(architecture['employees'])}")
        print("[系统架构] 总裁办核心地位已强化，部门间协作机制已优化")
        
        return architecture
    
    def _enhance_executive_office_coordination(self, architecture: Dict[str, Any]):
        """增强总裁办与部门之间的协作机制"""
        print("[系统架构] 增强总裁办与部门之间的协作机制...")
        
        # 为每个部门添加具体职责
        department_responsibilities = {
            "design": ["UI/UX设计", "品牌设计", "视觉设计"],
            "development": ["软件开发", "系统架构", "代码维护"],
            "marketing": ["市场推广", "品牌建设", "客户获取"],
            "legal": ["法律咨询", "合同管理", "合规监督"],
            "hr": ["人才招聘", "员工培训", "绩效考核"],
            "finance": ["财务管理", "预算规划", "成本控制"],
            "operations": ["流程优化", "项目协调", "资源管理"],
            "research": ["市场调研", "数据分析", "趋势预测"],
            "sales": ["客户开发", "销售管理", " revenue generation"],
            "project_management": ["项目规划", "进度跟踪", "风险管理"],
            "customer_service": ["客户支持", "问题解决", "满意度管理"],
            "content": ["内容创作", "文案撰写", "内容策略"]
        }
        
        # 更新部门职责
        for department, responsibilities in department_responsibilities.items():
            if department in architecture["departments"]:
                architecture["departments"][department]["responsibilities"] = responsibilities
        
        # 建立跨部门协作流程
        architecture["cross_departmental_processes"] = {
            "new_product_development": {
                "description": "新产品开发流程",
                "participants": ["executive_office", "design", "development", "marketing", "research"],
                "stages": [
                    "需求分析",
                    "设计阶段",
                    "开发阶段",
                    "测试阶段",
                    "市场推广",
                    "发布阶段"
                ],
                "coordinator": "executive_office"
            },
            "marketing_campaign": {
                "description": "营销活动流程",
                "participants": ["executive_office", "marketing", "design", "content"],
                "stages": [
                    "活动策划",
                    "创意设计",
                    "内容创作",
                    "活动执行",
                    "效果评估"
                ],
                "coordinator": "marketing"
            },
            "budget_planning": {
                "description": "预算规划流程",
                "participants": ["executive_office", "finance", "hr", "operations"],
                "stages": [
                    "需求收集",
                    "预算编制",
                    "审核审批",
                    "执行监控"
                ],
                "coordinator": "finance"
            }
        }
        
        print("[系统架构] 跨部门协作流程已建立")
    
    def get_architecture(self) -> Dict[str, Any]:
        """Get the three-layer architecture"""
        return self.three_layer_architecture
