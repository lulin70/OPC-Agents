#!/usr/bin/env python3
"""
Agency-Agents Manager

Core management script for the Agency-Agents system, integrating with TRAE.
"""

import os
import sys
import json
import toml
import requests
from typing import Dict, List, Optional, Any

from communication_manager import CommunicationManager, ContextManager

class OPCManager:
    """Manager class for the OPC-Agents system"""
    
    def __init__(self, config_path: str = "config.toml"):
        """Initialize the OPC Manager"""
        self.config_path = config_path
        self.config = self._load_config()
        self.agents = self._load_agents()
        self.official_agents = self._load_official_agents()
        # 初始化通信管理器和上下文管理器
        self.communication_manager = CommunicationManager()
        self.context_manager = ContextManager()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from TOML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return toml.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def _load_agents(self) -> Dict[str, List[str]]:
        """Load agent configurations"""
        return self.config.get('agents', {})
    
    def _load_official_agents(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load official agents from extracted JSON files with caching and deduplication"""
        official_agents = {}
        official_agents_dir = "official_agents"
        cache_file = os.path.join(official_agents_dir, "agents_cache.json")
        
        # Try to load from cache first
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    print("Loading agents from cache...")
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        if not os.path.exists(official_agents_dir):
            print(f"Official agents directory {official_agents_dir} not found")
            return official_agents
        
        print("Loading agents from JSON files...")
        agent_ids = set()  # To track unique agent IDs
        
        for filename in os.listdir(official_agents_dir):
            if filename.endswith('.json') and filename != "agents_cache.json":
                file_path = os.path.join(official_agents_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        agents = json.load(f)
                        for agent in agents:
                            agent_id = agent.get('name')
                            if agent_id and agent_id not in agent_ids:
                                agent_ids.add(agent_id)
                                department = agent.get('department', 'unknown')
                                if department not in official_agents:
                                    official_agents[department] = []
                                official_agents[department].append(agent)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        
        # Save to cache for future use
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(official_agents, f, ensure_ascii=False, indent=2)
            print("Agents cached successfully")
        except Exception as e:
            print(f"Error saving cache: {e}")
        
        return official_agents
    
    def get_agent_by_department(self, department: str) -> List[str]:
        """Get agents by department"""
        return self.agents.get(department, [])
    
    def get_official_agent_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get official agents by department"""
        return self.official_agents.get(department, [])
    
    def get_all_agents(self) -> List[str]:
        """Get all agents"""
        all_agents = []
        for department_agents in self.agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_all_official_agents(self) -> List[Dict[str, Any]]:
        """Get all official agents"""
        all_agents = []
        for department_agents in self.official_agents.values():
            all_agents.extend(department_agents)
        return all_agents
    
    def get_departments(self) -> List[str]:
        """Get all departments"""
        departments = set(self.agents.keys())
        departments.update(self.official_agents.keys())
        return sorted(list(departments))
    
    def send_message(self, sender: str, receiver: str, message_type: str, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息给指定代理
        
        Args:
            sender: 发送者名称
            receiver: 接收者名称
            message_type: 消息类型
            content: 消息内容
            context: 上下文信息
            
        Returns:
            消息传递结果
        """
        return self.communication_manager.send_message(sender, receiver, message_type, content, context)
    
    def start_consensus(self, issue: str, agents: List[str], voting_method: str = "majority", decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识过程
        
        Args:
            issue: 需要达成共识的问题
            agents: 参与共识的代理列表
            voting_method: 投票方式，支持 "majority" (多数决) 和 "unanimous" (一致通过)
            decision_threshold: 决策阈值，默认为0.6 (60%)
            
        Returns:
            共识结果
        """
        return self.communication_manager.start_consensus(issue, agents, voting_method, decision_threshold)
    
    def get_message_history(self, agent: str) -> List[Dict[str, Any]]:
        """获取代理的消息历史
        
        Args:
            agent: 代理名称
            
        Returns:
            消息历史列表
        """
        return self.communication_manager.get_message_history(agent)
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用情况
        
        Returns:
            各代理的Token使用量
        """
        return self.communication_manager.get_token_usage()
    
    def set_context(self, key: str, value: Any):
        """设置上下文
        
        Args:
            key: 上下文键
            value: 上下文值
        """
        self.context_manager.set_context(key, value)
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取上下文
        
        Args:
            key: 上下文键
            
        Returns:
            上下文值
        """
        return self.context_manager.get_context(key)
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            agent: 负责的代理
            initial_status: 初始状态，默认为"pending"
        """
        self.communication_manager.create_task(task_id, task_name, agent, initial_status)
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
        """
        self.communication_manager.update_task_status(task_id, status, progress)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        return self.communication_manager.get_task_status(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态
        
        Returns:
            所有任务的状态信息
        """
        return self.communication_manager.get_all_tasks()
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务
        
        Args:
            agent: 代理名称
            
        Returns:
            代理的任务列表
        """
        return self.communication_manager.get_tasks_by_agent(agent)
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务
        
        Args:
            status: 任务状态
            
        Returns:
            指定状态的任务列表
        """
        return self.communication_manager.get_tasks_by_status(status)
    
    def trae_request(self, prompt: str, agent_type: str) -> Optional[str]:
        """Send request to TRAE API or use local simulation"""
        # Use local simulation since TRAE API is not accessible
        print(f"[Local Simulation] Processing request for {agent_type}...")
        
        # Simulate agent responses based on agent type
        agent_responses = {
            'ui_designer': '''I've designed a modern UI for the task management app with a clean, minimalist interface. The design includes:
1. A dashboard with task cards in a kanban-style layout
2. Color-coded priority indicators (red for high, yellow for medium, green for low)
3. Responsive design that works on desktop and mobile
4. Smooth animations for task transitions
5. Dark mode support for better usability in low-light environments

The UI uses a neutral color palette with accent colors for important actions, ensuring good accessibility and visual hierarchy.''',
            'frontend_developer': '''I've implemented the login page using React with the following features:
1. Responsive design using Tailwind CSS
2. Form validation with react-hook-form
3. Password strength indicator
4. Social login options (Google, Facebook)
5. JWT authentication flow
6. Error handling and loading states
7. Accessibility compliance (ARIA labels, keyboard navigation)

The component is structured with proper separation of concerns and follows React best practices.''',
            'digital_marketer': '''I've created a comprehensive marketing campaign for the new login system:
1. Campaign theme: 'Secure Access, Seamless Experience'
2. Target audience: Existing users and potential new customers
3. Channels: Email, social media, in-app notifications
4. Key messaging: Highlighting enhanced security features and user-friendly design
5. Call-to-action: 'Update Your Login Experience Today'
6. Metrics to track: Click-through rate, conversion rate, user feedback

The campaign will run for 4 weeks with a budget allocation across different channels.''',
            'default': f"This is a simulated response from the {agent_type} agent. In a real implementation, this would be generated by the TRAE API based on the prompt: {prompt[:100]}..."
        }
        
        return agent_responses.get(agent_type, agent_responses['default'])
    
    def assign_task(self, task: str, department: str, agent: Optional[str] = None) -> Optional[str]:
        """Assign a task to an agent"""
        # First check official agents
        official_agents = self.official_agents.get(department, [])
        custom_agents = self.agents.get(department, [])
        
        if not official_agents and not custom_agents:
            print(f"错误: 部门 '{department}' 不存在或没有代理")
            print("请使用 '查看所有部门' 命令查看可用部门")
            return None
        
        selected_agent = None
        
        if agent:
            # Find agent by name or ID in official agents
            for official_agent in official_agents:
                agent_id = official_agent.get('name')
                agent_name = official_agent.get('frontmatter', {}).get('name')
                if agent_id == agent or agent_name == agent:
                    selected_agent = official_agent
                    break
            
            # If not found, check custom agents
            if not selected_agent and agent in custom_agents:
                selected_agent = agent
            
            if not selected_agent:
                print(f"错误: 在部门 '{department}' 中未找到代理 '{agent}'")
                print(f"该部门可用的代理有:")
                if official_agents:
                    print("官方代理:")
                    for official_agent in official_agents[:5]:
                        agent_name = official_agent.get('frontmatter', {}).get('name', official_agent.get('name'))
                        print(f"- {agent_name}")
                    if len(official_agents) > 5:
                        print(f"... 还有 {len(official_agents) - 5} 个代理")
                if custom_agents:
                    print("自定义代理:")
                    for custom_agent in custom_agents:
                        print(f"- {custom_agent}")
                return None
        else:
            # Assign to first agent in department
            if official_agents:
                selected_agent = official_agents[0]
                agent_name = selected_agent.get('frontmatter', {}).get('name', selected_agent.get('name'))
                print(f"自动分配任务给部门 '{department}' 的第一个代理: {agent_name}")
            elif custom_agents:
                selected_agent = custom_agents[0]
                print(f"自动分配任务给部门 '{department}' 的第一个代理: {selected_agent}")
            else:
                print(f"错误: 部门 '{department}' 没有可用的代理")
                return None
        
        # Create prompt for the agent
        if isinstance(selected_agent, dict):
            agent_name = selected_agent.get('frontmatter', {}).get('name', selected_agent.get('name', 'Agent'))
            agent_description = selected_agent.get('frontmatter', {}).get('description', '')
            prompt = f"""You are {agent_name}, {agent_description}
You work in the {department} department of TRAE Agency.
Your task is to: {task}

Please provide a detailed response addressing this task."""
            agent_type = agent_name
        else:
            prompt = f"""You are a {selected_agent} in the {department} department of TRAE Agency.
Your task is to: {task}

Please provide a detailed response addressing this task."""
            agent_type = selected_agent
        
        # Send to TRAE
        print(f"正在处理任务: {task[:50]}...")
        print(f"分配给: {agent_type}")
        return self.trae_request(prompt, agent_type)
    
    def run_project(self, project_name: str, tasks: List[Dict[str, str]]) -> Dict[str, str]:
        """Run a project with multiple tasks"""
        results = {}
        
        for task_info in tasks:
            department = task_info.get('department')
            task = task_info.get('task')
            agent = task_info.get('agent')
            
            if not department or not task:
                continue
            
            result = self.assign_task(task, department, agent)
            results[f"{department}:{agent or 'default'}"] = result
        
        return results

def main():
    """Main function"""
    manager = OPCManager()
    
    # Example usage
    print("=== Agency-Agents System ===")
    print(f"Agency: {manager.config.get('core', {}).get('name', 'TRAE Agency')}")
    print(f"Version: {manager.config.get('core', {}).get('version', '1.0.0')}")
    print()
    
    # List all departments
    print("Available Departments:")
    departments = manager.get_departments()
    for department in departments:
        # Get official agents
        official_agents = manager.get_official_agent_by_department(department)
        official_agent_names = [agent.get('frontmatter', {}).get('name', agent.get('name')) for agent in official_agents]
        
        # Get custom agents
        custom_agents = manager.get_agent_by_department(department)
        
        all_agents = official_agent_names + custom_agents
        if all_agents:
            print(f"- {department}: {', '.join(all_agents[:5])}{'...' if len(all_agents) > 5 else ''}")
            if len(all_agents) > 5:
                print(f"  Total: {len(all_agents)} agents")
    print()
    
    # Example task assignment with official agent
    print("=== Example Task Assignment ===")
    result = manager.assign_task(
        "Design a modern UI for a task management app",
        "design"
    )
    print(f"Design Agent response: {result}")
    
    # Example task assignment with engineering agent
    print("\n=== Engineering Task Assignment ===")
    result = manager.assign_task(
        "Optimize database performance for a high-traffic application",
        "engineering",
        "Database Optimizer"
    )
    print(f"Database Optimizer response: {result}")

if __name__ == "__main__":
    main()