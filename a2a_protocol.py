#!/usr/bin/env python3
"""
A2A (Agent-to-Agent) Protocol Implementation
基于Google主导的A2A协议标准实现

A2A核心概念：
- AgentCard: Agent的"名片"，描述能力、技能和认证方式
- Task: 任务执行单元，支持9种状态流转
- Message/Part: Agent间通信的消息载体
- 安全认证: 支持API Key、JWT、OAuth 2.0 + PKCE、OIDC、双向TLS
"""

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime


class TaskState(Enum):
    """A2A任务状态 - 9种标准状态"""
    SUBMITTED = "submitted"           # 已提交
    WORKING = "working"               # 执行中
    INPUT_REQUIRED = "input_required" # 需要输入
    COMPLETED = "completed"           # 已完成
    FAILED = "failed"                 # 失败
    CANCELLED = "cancelled"           # 已取消
    PAUSED = "paused"                 # 已暂停
    PENDING = "pending"               # 待处理
    RETRYING = "retrying"             # 重试中


class PartType(Enum):
    """消息部分内容类型"""
    TEXT = "text"
    BINARY = "binary"
    URL = "url"
    STRUCTURED = "structured"


class AuthScheme(Enum):
    """认证方案"""
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    MTLS = "mtls"


@dataclass
class AgentCapability:
    """Agent能力描述"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    returns: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentSkill:
    """Agent技能描述"""
    id: str
    name: str
    description: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class AgentCard:
    """
    AgentCard - Agent的"名片"
    通过 /.well-known/agent-card.json 发布
    """
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    authentication: Dict[str, Any] = field(default_factory=dict)
    skills: List[AgentSkill] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "authentication": self.authentication,
            "skills": [asdict(skill) for skill in self.skills],
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class Part:
    """
    Message/Part - Agent间通信的消息载体
    支持文本、二进制、URL、结构化数据
    """
    type: PartType
    content: Union[str, bytes, Dict[str, Any]]
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def text(cls, text: str, metadata: Dict[str, Any] = None) -> 'Part':
        """创建文本部分"""
        return cls(
            type=PartType.TEXT,
            content=text,
            mime_type="text/plain",
            metadata=metadata or {}
        )
    
    @classmethod
    def binary(cls, data: bytes, mime_type: str = "application/octet-stream", 
               metadata: Dict[str, Any] = None) -> 'Part':
        """创建二进制部分"""
        return cls(
            type=PartType.BINARY,
            content=data,
            mime_type=mime_type,
            metadata=metadata or {}
        )
    
    @classmethod
    def url(cls, url: str, title: str = "", metadata: Dict[str, Any] = None) -> 'Part':
        """创建URL部分"""
        return cls(
            type=PartType.URL,
            content={"url": url, "title": title},
            mime_type="text/uri-list",
            metadata=metadata or {}
        )
    
    @classmethod
    def structured(cls, data: Dict[str, Any], 
                   mime_type: str = "application/json",
                   metadata: Dict[str, Any] = None) -> 'Part':
        """创建结构化数据部分"""
        return cls(
            type=PartType.STRUCTURED,
            content=data,
            mime_type=mime_type,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "content": self.content if isinstance(self.content, (str, dict)) else "<binary>",
            "mime_type": self.mime_type,
            "metadata": self.metadata
        }


@dataclass
class Message:
    """A2A消息"""
    id: str
    sender: str
    receiver: str
    parts: List[Part]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None  # 父消息ID，用于对话线程
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "parts": [part.to_dict() for part in self.parts],
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "parent_id": self.parent_id
        }


@dataclass
class Task:
    """
    Task - 任务执行单元
    支持9种状态：SUBMITTED → WORKING → COMPLETED/FAILED/INPUT_REQUIRED
    """
    id: str
    name: str
    description: str
    agent: str
    state: TaskState = TaskState.SUBMITTED
    messages: List[Message] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
    
    def update_state(self, new_state: TaskState, message: str = ""):
        """更新任务状态"""
        old_state = self.state
        self.state = new_state
        self.updated_at = time.time()
        
        if new_state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            self.completed_at = time.time()
        
        # 记录状态变更
        if "state_history" not in self.metadata:
            self.metadata["state_history"] = []
        
        self.metadata["state_history"].append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": time.time(),
            "message": message
        })
    
    def add_message(self, message: Message):
        """添加消息到任务"""
        self.messages.append(message)
        self.updated_at = time.time()
    
    def add_artifact(self, name: str, data: Any, mime_type: str = "application/json"):
        """添加任务产物"""
        self.artifacts[name] = {
            "data": data,
            "mime_type": mime_type,
            "created_at": time.time()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "state": self.state.value,
            "messages": [msg.to_dict() for msg in self.messages],
            "artifacts": self.artifacts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
            "parent_task_id": self.parent_task_id,
            "subtasks": self.subtasks
        }


class A2AProtocol:
    """
    A2A协议核心实现
    提供Agent间通信的标准接口
    """
    
    def __init__(self):
        """初始化A2A协议"""
        self.agent_cards: Dict[str, AgentCard] = {}
        self.tasks: Dict[str, Task] = {}
        self.subscribers: Dict[str, List[callable]] = {}
        self.auth_handlers: Dict[AuthScheme, callable] = {}
    
    def register_agent(self, agent_id: str, agent_card: AgentCard):
        """注册Agent"""
        self.agent_cards[agent_id] = agent_card
        print(f"[A2A] 注册Agent: {agent_id}")
    
    def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """获取AgentCard"""
        return self.agent_cards.get(agent_id)
    
    def create_task(self, name: str, description: str, agent_id: str,
                   parent_task_id: Optional[str] = None) -> Task:
        """创建任务"""
        task = Task(
            name=name,
            description=description,
            agent=agent_id,
            parent_task_id=parent_task_id
        )
        
        self.tasks[task.id] = task
        
        # 如果有父任务，添加到父任务的子任务列表
        if parent_task_id and parent_task_id in self.tasks:
            self.tasks[parent_task_id].subtasks.append(task.id)
        
        print(f"[A2A] 创建任务: {task.id} - {name}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def update_task_state(self, task_id: str, new_state: TaskState, message: str = ""):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if task:
            task.update_state(new_state, message)
            print(f"[A2A] 任务 {task_id} 状态更新: {new_state.value}")
            
            # 通知订阅者
            self._notify_subscribers(task_id, "state_changed", {
                "task_id": task_id,
                "new_state": new_state.value,
                "message": message
            })
    
    def send_message(self, sender_id: str, receiver_id: str, 
                    parts: List[Part], parent_message_id: Optional[str] = None,
                    task_id: Optional[str] = None) -> Message:
        """
        SendMessage - A2A核心操作
        发送消息给指定Agent
        """
        message = Message(
            sender=sender_id,
            receiver=receiver_id,
            parts=parts,
            parent_id=parent_message_id
        )
        
        # 如果指定了任务，添加到任务的消息列表
        if task_id and task_id in self.tasks:
            self.tasks[task_id].add_message(message)
        
        print(f"[A2A] 消息从 {sender_id} 发送到 {receiver_id}")
        return message
    
    def send_streaming_message(self, sender_id: str, receiver_id: str,
                              parts_generator, task_id: Optional[str] = None):
        """
        SendStreamingMessage - A2A核心操作
        发送流式消息
        """
        print(f"[A2A] 开始流式消息: {sender_id} -> {receiver_id}")
        
        for part in parts_generator:
            message = self.send_message(sender_id, receiver_id, [part], task_id=task_id)
            yield message
    
    def subscribe_to_task(self, task_id: str, callback: callable):
        """
        SubscribeToTask - A2A核心操作
        订阅任务事件
        """
        if task_id not in self.subscribers:
            self.subscribers[task_id] = []
        
        self.subscribers[task_id].append(callback)
        print(f"[A2A] 订阅任务: {task_id}")
    
    def _notify_subscribers(self, task_id: str, event_type: str, data: Dict[str, Any]):
        """通知订阅者"""
        if task_id in self.subscribers:
            for callback in self.subscribers[task_id]:
                try:
                    callback(event_type, data)
                except Exception as e:
                    print(f"[A2A] 通知订阅者失败: {e}")
    
    def register_auth_handler(self, scheme: AuthScheme, handler: callable):
        """注册认证处理器"""
        self.auth_handlers[scheme] = handler
    
    def authenticate(self, scheme: AuthScheme, credentials: Dict[str, Any]) -> bool:
        """执行认证"""
        handler = self.auth_handlers.get(scheme)
        if handler:
            return handler(credentials)
        return False
    
    def discover_agents(self, capability: Optional[str] = None) -> List[AgentCard]:
        """发现Agent"""
        if capability:
            return [
                card for card in self.agent_cards.values()
                if capability in card.capabilities
            ]
        return list(self.agent_cards.values())


class A2AWorkflow:
    """
    A2A工作流管理器
    实现复杂的Agent协作流程
    """
    
    def __init__(self, a2a_protocol: A2AProtocol):
        """初始化工作流管理器"""
        self.a2a = a2a_protocol
        self.workflows: Dict[str, Dict[str, Any]] = {}
    
    def create_workflow(self, workflow_id: str, name: str, 
                       steps: List[Dict[str, Any]]) -> str:
        """创建工作流定义"""
        self.workflows[workflow_id] = {
            "id": workflow_id,
            "name": name,
            "steps": steps,
            "created_at": time.time()
        }
        print(f"[A2A工作流] 创建工作流: {workflow_id}")
        return workflow_id
    
    def execute_workflow(self, workflow_id: str, 
                        initial_data: Dict[str, Any]) -> Task:
        """执行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        # 创建工作流主任务
        main_task = self.a2a.create_task(
            name=workflow["name"],
            description=f"工作流执行: {workflow['name']}",
            agent_id="workflow_orchestrator"
        )
        
        print(f"[A2A工作流] 开始执行工作流: {workflow_id}")
        
        # 按顺序执行步骤
        for i, step in enumerate(workflow["steps"]):
            step_task = self._execute_step(main_task.id, step, initial_data)
            
            # 等待步骤完成
            while step_task.state not in [TaskState.COMPLETED, TaskState.FAILED]:
                time.sleep(0.1)
            
            if step_task.state == TaskState.FAILED:
                self.a2a.update_task_state(main_task.id, TaskState.FAILED, 
                                         f"步骤 {i+1} 失败")
                return main_task
        
        self.a2a.update_task_state(main_task.id, TaskState.COMPLETED, 
                                 "所有步骤完成")
        return main_task
    
    def _execute_step(self, parent_task_id: str, step: Dict[str, Any],
                     data: Dict[str, Any]) -> Task:
        """执行单个步骤"""
        agent_id = step.get("agent_id")
        action = step.get("action")
        
        # 创建步骤任务
        step_task = self.a2a.create_task(
            name=step.get("name", "未命名步骤"),
            description=step.get("description", ""),
            agent_id=agent_id,
            parent_task_id=parent_task_id
        )
        
        # 发送消息给Agent执行任务
        parts = [Part.structured({
            "action": action,
            "data": data,
            "step_config": step
        })]
        
        self.a2a.send_message(
            sender_id="workflow_orchestrator",
            receiver_id=agent_id,
            parts=parts,
            task_id=step_task.id
        )
        
        self.a2a.update_task_state(step_task.id, TaskState.WORKING)
        
        return step_task


# 与MCP协议的集成
class MCPIntegration:
    """
    MCP (Model Context Protocol) 集成
    实现Agent与工具的垂直连接
    """
    
    def __init__(self, a2a_protocol: A2AProtocol):
        """初始化MCP集成"""
        self.a2a = a2a_protocol
        self.tools: Dict[str, Dict[str, Any]] = {}
    
    def register_tool(self, tool_id: str, name: str, 
                     description: str, parameters: Dict[str, Any],
                     handler: callable):
        """注册工具"""
        self.tools[tool_id] = {
            "id": tool_id,
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler
        }
        print(f"[MCP] 注册工具: {tool_id}")
    
    def execute_tool(self, tool_id: str, parameters: Dict[str, Any],
                    task_id: Optional[str] = None) -> Any:
        """执行工具"""
        tool = self.tools.get(tool_id)
        if not tool:
            raise ValueError(f"工具不存在: {tool_id}")
        
        print(f"[MCP] 执行工具: {tool_id}")
        
        try:
            result = tool["handler"](parameters)
            
            # 如果有任务ID，记录工具执行结果
            if task_id:
                task = self.a2a.get_task(task_id)
                if task:
                    task.add_artifact(f"tool_result_{tool_id}", result)
            
            return result
        except Exception as e:
            print(f"[MCP] 工具执行失败: {e}")
            raise
    
    def discover_tools(self, capability: Optional[str] = None) -> List[Dict[str, Any]]:
        """发现可用工具"""
        if capability:
            return [
                tool for tool in self.tools.values()
                if capability in tool.get("capabilities", [])
            ]
        return list(self.tools.values())


# 使用示例
if __name__ == "__main__":
    # 创建A2A协议实例
    a2a = A2AProtocol()
    
    # 创建AgentCard
    agent_card = AgentCard(
        name="Research Assistant",
        description="A research assistant agent that can search and analyze information",
        url="http://localhost:5000/agents/research",
        authentication={
            "schemes": ["api_key", "jwt"],
            "api_key": {"header": "X-API-Key"}
        },
        skills=[
            AgentSkill(
                id="web_search",
                name="Web Search",
                description="Search the web for information",
                capabilities=[
                    AgentCapability(
                        name="search",
                        description="Perform web search",
                        parameters={"query": "string"},
                        returns={"results": "array"}
                    )
                ],
                tags=["search", "web"]
            )
        ],
        capabilities=["streaming", "multi-turn"]
    )
    
    # 注册Agent
    a2a.register_agent("research_assistant", agent_card)
    
    # 创建任务
    task = a2a.create_task(
        name="Research Task",
        description="Research information about AI agents",
        agent_id="research_assistant"
    )
    
    # 发送消息
    message = a2a.send_message(
        sender_id="user",
        receiver_id="research_assistant",
        parts=[Part.text("Please research the latest developments in AI agents")],
        task_id=task.id
    )
    
    # 更新任务状态
    a2a.update_task_state(task.id, TaskState.WORKING)
    
    print("\nA2A Protocol Demo completed successfully!")
