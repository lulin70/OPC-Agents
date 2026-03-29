#!/usr/bin/env python3
"""
Core OPC Manager functionality
"""

from typing import Dict, List, Optional, Any

from .log_config import LogConfig, log_config
from .config import ConfigManager
from .agent_manager import AgentManager
from .architecture import ArchitectureManager
from .task_manager import TaskManager
from .three_sages import ThreeSagesManager
from .personal_assistant import PersonalAssistantManager
from .task_executor import TaskExecutor, TaskExecutorManager, TaskPriority
from communication_manager import CommunicationManager, ContextManager
from data_storage.dao import DatabaseManager

class OPCManager:
    """Manager class for the OPC-Agents system"""
    
    def __init__(self, config_path: str = "config.toml", debug_mode: bool = False, db_path: str = None):
        """Initialize the OPC Manager"""
        # 初始化日志配置
        global log_config
        log_config = LogConfig(debug_mode=debug_mode)
        self.logger = log_config.logger
        
        # 初始化配置管理器
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # 初始化数据库管理器
        if db_path is None:
            db_path = "data_storage/opc_agents.db"
        self.db_manager = DatabaseManager(db_path)
        self.logger.info(f"数据库管理器已初始化: {db_path}")
        
        # 初始化通信管理器和上下文管理器
        self.communication_manager = CommunicationManager(debug_mode=debug_mode, db_manager=self.db_manager)
        self.context_manager = ContextManager()
        
        # 初始化各功能模块
        self.agent_manager = AgentManager(self.config.get('agents', {}))
        self.architecture_manager = ArchitectureManager(self.agent_manager)
        self.task_manager = TaskManager(self.communication_manager, db_manager=self.db_manager)
        self.three_sages_manager = ThreeSagesManager()
        self.personal_assistant_manager = PersonalAssistantManager()
        
        # 初始化任务执行器
        self.task_executor = TaskExecutor(
            opc_manager=self,
            max_workers=5,
            progress_streamer=None,
            db_manager=self.db_manager
        )
        self.executor_manager = TaskExecutorManager(self)
        self.executor_manager.executors.append(self.task_executor)
        
        self.logger.info(f"OPC Manager initialized in {'debug' if debug_mode else 'normal'} mode")
    
    # 配置相关方法
    def get_model_config(self, model_name: str = None) -> Dict[str, Any]:
        """Get model configuration"""
        return self.config_manager.get_model_config(model_name)
    
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return self.config_manager.get_available_models()
    
    # 代理相关方法
    def get_agent_by_department(self, department: str) -> List[str]:
        """Get agents by department"""
        return self.agent_manager.get_agent_by_department(department)
    
    def get_official_agent_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get official agents by department"""
        return self.agent_manager.get_official_agent_by_department(department)
    
    def get_all_agents(self) -> List[str]:
        """Get all agents"""
        return self.agent_manager.get_all_agents()
    
    def get_all_official_agents(self) -> List[Dict[str, Any]]:
        """Get all official agents"""
        return self.agent_manager.get_all_official_agents()
    
    def get_departments(self) -> List[str]:
        """Get all departments"""
        return self.agent_manager.get_departments()
    
    def get_executive_office_agents(self) -> Dict[str, str]:
        """Get executive office agents"""
        return self.agent_manager.get_executive_office_agents()
    
    def get_three_sages(self) -> Dict[str, str]:
        """Get three sages agents"""
        return self.agent_manager.get_three_sages()
    
    # 架构相关方法
    def get_three_layer_architecture(self) -> Dict[str, Any]:
        """Get the three-layer architecture"""
        return self.architecture_manager.get_architecture()
    
    # 任务相关方法
    def decompose_task(self, task: str, time_horizon: str = "medium") -> List[Dict[str, str]]:
        """Decompose a task into smaller tasks based on time horizon"""
        return self.task_manager.decompose_task(task, time_horizon)
    
    def track_progress(self, tasks: List[str] = None) -> Dict[str, Any]:
        """Track progress of tasks"""
        return self.task_manager.track_progress(tasks)
    
    def generate_report(self, period: str = "weekly") -> Dict[str, Any]:
        """Generate report for a specific period"""
        return self.task_manager.generate_report(period, self.config)
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态"""
        self.task_manager.create_task(task_id, task_name, agent, initial_status)
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态"""
        self.task_manager.update_task_status(task_id, status, progress)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.task_manager.get_task_status(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态"""
        return self.task_manager.get_all_tasks()
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务"""
        return self.task_manager.get_tasks_by_agent(agent)
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务"""
        return self.task_manager.get_tasks_by_status(status)
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的历史记录"""
        return self.task_manager.get_task_history(task_id)
    
    def get_all_task_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务的历史记录"""
        return self.task_manager.get_all_task_history()
    
    # 三贤者决策相关方法
    def start_three_sages_decision(self, issue: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Start three sages decision process"""
        return self.three_sages_manager.start_three_sages_decision(issue, context)
    
    # 个人助理相关方法
    def add_todo_item(self, content: str, priority: str = "medium", due_date: str = None) -> str:
        """添加待办事项"""
        return self.personal_assistant_manager.add_todo_item(content, priority, due_date)
    
    def get_todo_items(self, status: str = None) -> List[Dict[str, Any]]:
        """获取待办事项列表"""
        return self.personal_assistant_manager.get_todo_items(status)
    
    def update_todo_status(self, todo_id: str, status: str) -> bool:
        """更新待办事项状态"""
        return self.personal_assistant_manager.update_todo_status(todo_id, status)
    
    def add_hobby(self, hobby: str, description: str = "") -> str:
        """添加兴趣爱好"""
        return self.personal_assistant_manager.add_hobby(hobby, description)
    
    def get_hobbies(self) -> List[Dict[str, Any]]:
        """获取兴趣爱好列表"""
        return self.personal_assistant_manager.get_hobbies()
    
    def plan_trip(self, destination: str, start_date: str, end_date: str, preferences: Dict[str, Any] = None) -> Dict[str, Any]:
        """规划出行"""
        return self.personal_assistant_manager.plan_trip(destination, start_date, end_date, preferences)
    
    def get_trip_plans(self) -> List[Dict[str, Any]]:
        """获取出行计划列表"""
        return self.personal_assistant_manager.get_trip_plans()
    
    def get_weather(self, location: str) -> Dict[str, Any]:
        """获取天气信息"""
        return self.personal_assistant_manager.get_weather(location)
    
    # 通信相关方法
    def send_message(self, sender: str, receiver: str, message_type: str, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息给指定代理"""
        return self.communication_manager.send_message(sender, receiver, message_type, content, context)
    
    def start_consensus(self, issue: str, agents: List[str], voting_method: str = "majority", decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识过程"""
        return self.communication_manager.start_consensus(issue, agents, voting_method, decision_threshold)
    
    def get_message_history(self, agent: str) -> List[Dict[str, Any]]:
        """获取代理的消息历史"""
        return self.communication_manager.get_message_history(agent)
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用情况"""
        return self.communication_manager.get_token_usage()
    
    # 上下文相关方法
    def set_context(self, key: str, value: Any):
        """设置上下文"""
        self.context_manager.set_context(key, value)
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取上下文"""
        return self.context_manager.get_context(key)
