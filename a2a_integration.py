#!/usr/bin/env python3
"""
A2A Protocol Integration for OPC-Agents
将A2A协议集成到现有的OPC-Agents系统中
"""

import json
import os
from typing import Dict, List, Optional, Any
from a2a_protocol import (
    A2AProtocol, A2AWorkflow, MCPIntegration,
    AgentCard, AgentSkill, AgentCapability,
    Task, TaskState, Part, Message,
    AuthScheme
)
from opc_manager import OPCManager


class OPCA2AIntegration:
    """
    OPC-Agents与A2A协议的集成器
    将现有Agent系统升级为符合A2A标准的系统
    """
    
    def __init__(self, opc_manager: OPCManager):
        """初始化集成器"""
        self.opc = opc_manager
        self.a2a = A2AProtocol()
        self.workflow = A2AWorkflow(self.a2a)
        self.mcp = MCPIntegration(self.a2a)
        
        # 初始化：将现有Agent转换为A2A格式
        self._initialize_agents()
        self._initialize_workflows()
    
    def _initialize_agents(self):
        """初始化Agent，创建AgentCard"""
        print("[A2A集成] 初始化Agent...")
        
        # 遍历所有部门，为每个Agent创建AgentCard
        for department in self.opc.get_departments():
            official_agents = self.opc.get_official_agent_by_department(department)
            
            for agent_info in official_agents:
                agent_id = agent_info.get('name', 'unknown')
                agent_name = agent_info.get('frontmatter', {}).get('name', agent_id)
                description = agent_info.get('frontmatter', {}).get('description', '')
                
                # 创建AgentCard
                agent_card = self._create_agent_card(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    description=description,
                    department=department,
                    agent_info=agent_info
                )
                
                # 注册到A2A协议
                self.a2a.register_agent(agent_id, agent_card)
        
        print(f"[A2A集成] 已注册 {len(self.a2a.agent_cards)} 个Agent")
    
    def _create_agent_card(self, agent_id: str, agent_name: str,
                          description: str, department: str,
                          agent_info: Dict[str, Any]) -> AgentCard:
        """为Agent创建AgentCard"""
        
        # 根据部门确定技能
        skills = self._determine_skills(department, agent_info)
        
        # 构建AgentCard
        return AgentCard(
            name=agent_name,
            description=description,
            url=f"http://localhost:5007/api/agents/{agent_id}",
            version="1.0.0",
            authentication={
                "schemes": ["api_key"],
                "api_key": {"header": "X-API-Key"}
            },
            skills=skills,
            capabilities=["task_execution", "message_handling", "streaming"],
            metadata={
                "department": department,
                "agent_id": agent_id,
                "original_info": agent_info
            }
        )
    
    def _determine_skills(self, department: str, agent_info: Dict[str, Any]) -> List[AgentSkill]:
        """根据部门和Agent信息确定技能"""
        skills = []
        
        # 基础技能
        base_capabilities = [
            AgentCapability(
                name="execute_task",
                description="Execute assigned tasks",
                parameters={"task": "object"},
                returns={"result": "any"}
            ),
            AgentCapability(
                name="send_message",
                description="Send messages to other agents",
                parameters={"message": "object"},
                returns={"status": "string"}
            )
        ]
        
        # 部门特定技能
        if department == "design":
            skills.append(AgentSkill(
                id="design_work",
                name="Design Work",
                description="Create designs and UI/UX",
                capabilities=base_capabilities + [
                    AgentCapability(
                        name="create_design",
                        description="Create visual designs",
                        parameters={"requirements": "string"},
                        returns={"design": "object"}
                    )
                ],
                tags=["design", "ui", "ux"]
            ))
        
        elif department == "development":
            skills.append(AgentSkill(
                id="development_work",
                name="Development Work",
                description="Write and review code",
                capabilities=base_capabilities + [
                    AgentCapability(
                        name="write_code",
                        description="Write software code",
                        parameters={"specification": "string"},
                        returns={"code": "string"}
                    )
                ],
                tags=["coding", "development", "engineering"]
            ))
        
        elif department == "marketing":
            skills.append(AgentSkill(
                id="marketing_work",
                name="Marketing Work",
                description="Create marketing content and strategies",
                capabilities=base_capabilities + [
                    AgentCapability(
                        name="create_campaign",
                        description="Create marketing campaigns",
                        parameters={"goal": "string"},
                        returns={"campaign": "object"}
                    )
                ],
                tags=["marketing", "content", "strategy"]
            ))
        
        else:
            # 通用技能
            skills.append(AgentSkill(
                id=f"{department}_work",
                name=f"{department.title()} Work",
                description=f"Perform {department} related tasks",
                capabilities=base_capabilities,
                tags=[department]
            ))
        
        return skills
    
    def _initialize_workflows(self):
        """初始化A2A工作流"""
        print("[A2A集成] 初始化工作流...")
        
        # 创建跨部门协作工作流
        self.workflow.create_workflow(
            workflow_id="cross_department_project",
            name="跨部门项目协作",
            steps=[
                {
                    "name": "需求分析",
                    "description": "分析项目需求",
                    "agent_id": "research_department",
                    "action": "analyze_requirements"
                },
                {
                    "name": "设计方案",
                    "description": "创建设计方案",
                    "agent_id": "design_department",
                    "action": "create_design"
                },
                {
                    "name": "开发实现",
                    "description": "开发功能实现",
                    "agent_id": "development_department",
                    "action": "implement_feature"
                },
                {
                    "name": "测试验证",
                    "description": "测试功能",
                    "agent_id": "testing_department",
                    "action": "test_feature"
                }
            ]
        )
        
        print("[A2A集成] 工作流初始化完成")
    
    def create_a2a_task(self, name: str, description: str, 
                       agent_id: str, parent_task_id: Optional[str] = None) -> Task:
        """创建A2A格式的任务"""
        return self.a2a.create_task(name, description, agent_id, parent_task_id)
    
    def send_a2a_message(self, sender_id: str, receiver_id: str,
                        content: str, task_id: Optional[str] = None) -> Message:
        """发送A2A格式的消息"""
        parts = [Part.text(content)]
        return self.a2a.send_message(sender_id, receiver_id, parts, task_id=task_id)
    
    def execute_cross_department_workflow(self, project_data: Dict[str, Any]) -> Task:
        """执行跨部门协作工作流"""
        return self.workflow.execute_workflow("cross_department_project", project_data)
    
    def register_mcp_tool(self, tool_id: str, name: str, 
                         description: str, handler: callable):
        """注册MCP工具"""
        self.mcp.register_tool(
            tool_id=tool_id,
            name=name,
            description=description,
            parameters={},
            handler=handler
        )
    
    def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """获取AgentCard"""
        return self.a2a.get_agent_card(agent_id)
    
    def discover_agents_by_capability(self, capability: str) -> List[AgentCard]:
        """根据能力发现Agent"""
        return self.a2a.discover_agents(capability)
    
    def export_agent_card(self, agent_id: str, output_path: str):
        """导出AgentCard到JSON文件"""
        agent_card = self.a2a.get_agent_card(agent_id)
        if agent_card:
            # 确保目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(agent_card.to_json())
            
            print(f"[A2A集成] AgentCard已导出: {output_path}")
            return True
        return False
    
    def export_all_agent_cards(self, output_dir: str = ".well-known"):
        """导出所有AgentCard"""
        print(f"[A2A集成] 导出所有AgentCard到 {output_dir}")
        
        for agent_id in self.a2a.agent_cards:
            output_path = os.path.join(output_dir, f"{agent_id}-card.json")
            self.export_agent_card(agent_id, output_path)
        
        print(f"[A2A集成] 已导出 {len(self.a2a.agent_cards)} 个AgentCard")


# 与现有系统的适配器
class A2ACommunicationAdapter:
    """
    A2A通信适配器
    将现有的CommunicationManager适配到A2A协议
    """
    
    def __init__(self, opc_manager: OPCManager, a2a_integration: OPCA2AIntegration):
        """初始化适配器"""
        self.opc = opc_manager
        self.a2a = a2a_integration
    
    def send_message(self, sender: str, receiver: str, 
                    content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息（兼容现有接口）"""
        # 使用A2A协议发送消息
        message = self.a2a.send_a2a_message(sender, receiver, content)
        
        return {
            "success": True,
            "message_id": message.id,
            "timestamp": message.timestamp
        }
    
    def start_consensus(self, issue: str, agents: List[str],
                       voting_method: str = "majority", 
                       decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识（兼容现有接口，使用A2A协议增强）"""
        # 创建共识任务
        task = self.a2a.create_a2a_task(
            name="Consensus Decision",
            description=f"Consensus on: {issue}",
            agent_id="consensus_orchestrator"
        )
        
        # 收集每个Agent的意见
        opinions = {}
        for agent_id in agents:
            # 发送消息获取意见
            self.a2a.send_a2a_message(
                sender_id="consensus_orchestrator",
                receiver_id=agent_id,
                content=f"请对以下议题发表意见：{issue}",
                task_id=task.id
            )
            
            # 这里应该等待响应，简化处理
            opinions[agent_id] = "pending"
        
        return {
            "issue": issue,
            "agents": agents,
            "opinions": opinions,
            "task_id": task.id,
            "status": "consensus_initiated"
        }


# 使用示例
if __name__ == "__main__":
    # 创建OPC Manager
    opc_manager = OPCManager()
    
    # 创建A2A集成
    a2a_integration = OPCA2AIntegration(opc_manager)
    
    # 导出所有AgentCard
    a2a_integration.export_all_agent_cards()
    
    # 创建A2A任务
    task = a2a_integration.create_a2a_task(
        name="Research Project",
        description="Research AI agent developments",
        agent_id="research_department"
    )
    
    # 发送A2A消息
    message = a2a_integration.send_a2a_message(
        sender_id="user",
        receiver_id="research_department",
        content="Please research the latest AI agent technologies",
        task_id=task.id
    )
    
    print("\nA2A Integration Demo completed!")
    print(f"Task ID: {task.id}")
    print(f"Message ID: {message.id}")
