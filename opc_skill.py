#!/usr/bin/env python3
"""
OPC-Agents Skill

Integration of Agency-Agents system
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add the agency-agents directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from opc_manager import OPCManager

def list_departments():
    """List all departments"""
    manager = OPCManager()
    departments = manager.get_departments()
    
    print("=== 可用部门 ===")
    for dept in departments:
        official_agents = manager.get_official_agent_by_department(dept)
        custom_agents = manager.get_agent_by_department(dept)
        total_agents = len(official_agents) + len(custom_agents)
        print(f"- {dept} ({total_agents} 个代理)")

def list_agents_in_department(department):
    """List agents in a specific department"""
    manager = OPCManager()
    official_agents = manager.get_official_agent_by_department(department)
    custom_agents = manager.get_agent_by_department(department)
    
    print(f"=== {department} 部门的代理 ===")
    
    if official_agents:
        print("\n官方代理:")
        for agent in official_agents[:10]:  # Limit to first 10
            agent_name = agent.get('frontmatter', {}).get('name', agent.get('name'))
            agent_desc = agent.get('frontmatter', {}).get('description', '')
            print(f"- {agent_name}: {agent_desc[:100]}...")
        if len(official_agents) > 10:
            print(f"... 还有 {len(official_agents) - 10} 个代理")
    
    if custom_agents:
        print("\n自定义代理:")
        for agent in custom_agents:
            print(f"- {agent}")

def assign_task(department, task, agent=None):
    """Assign a task to an agent"""
    manager = OPCManager()
    result = manager.assign_task(task, department, agent)
    
    if result:
        print("=== 任务分配结果 ===")
        print(result)
    else:
        print("任务分配失败，请检查部门和代理名称是否正确。")

def create_project(project_name, tasks):
    """Create and run a project"""
    manager = OPCManager()
    
    # Parse tasks
    task_list = []
    for task_info in tasks:
        # Format: "department:task:agent"
        parts = task_info.split(':', 2)
        if len(parts) >= 2:
            task_dict = {
                'department': parts[0],
                'task': parts[1]
            }
            if len(parts) == 3:
                task_dict['agent'] = parts[2]
            task_list.append(task_dict)
    
    results = manager.run_project(project_name, task_list)
    
    print(f"=== 项目: {project_name} ===")
    for key, result in results.items():
        print(f"\n{key}:")
        print(result)

def send_message(sender, receiver, message_type, content):
    """发送消息给指定代理"""
    manager = OPCManager()
    result = manager.send_message(sender, receiver, message_type, content)
    
    if result.get('success'):
        print("=== 消息发送成功 ===")
        print(f"消息ID: {result.get('message_id')}")
        print(f"发送时间: {result.get('timestamp')}")
    else:
        print("消息发送失败")

def start_consensus(issue, agents):
    """启动共识过程"""
    manager = OPCManager()
    result = manager.start_consensus(issue, agents)
    
    print("=== 共识结果 ===")
    print(f"问题: {result.get('issue')}")
    print(f"参与代理: {', '.join(result.get('agents', []))}")
    print(f"决策: {result.get('decision')}")
    print(f"状态: {result.get('status')}")

def get_token_usage():
    """获取Token使用情况"""
    manager = OPCManager()
    usage = manager.get_token_usage()
    
    print("=== Token使用情况 ===")
    for agent, count in usage.items():
        print(f"{agent}: {count} tokens")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='OPC-Agents Skill')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List departments
    subparsers.add_parser('查看所有部门', help='List all departments')
    
    # List agents in department
    list_agents_parser = subparsers.add_parser('查看部门', help='List agents in a department')
    list_agents_parser.add_argument('department', help='Department name')
    
    # Assign task
    assign_task_parser = subparsers.add_parser('安排任务', help='Assign a task to an agent')
    assign_task_parser.add_argument('department', help='Department name')
    assign_task_parser.add_argument('task', nargs='+', help='Task description')
    assign_task_parser.add_argument('--agent', help='Agent name (optional)')
    
    # Create project
    create_project_parser = subparsers.add_parser('创建项目', help='Create and run a project')
    create_project_parser.add_argument('project_name', help='Project name')
    create_project_parser.add_argument('tasks', nargs='+', help='Tasks in format "department:task:agent"')
    
    # Send message
    send_message_parser = subparsers.add_parser('发送消息', help='Send message to an agent')
    send_message_parser.add_argument('sender', help='Sender name')
    send_message_parser.add_argument('receiver', help='Receiver name')
    send_message_parser.add_argument('message_type', help='Message type')
    send_message_parser.add_argument('content', nargs='+', help='Message content')
    
    # Start consensus
    start_consensus_parser = subparsers.add_parser('启动共识', help='Start consensus process')
    start_consensus_parser.add_argument('issue', nargs='+', help='Issue to reach consensus on')
    start_consensus_parser.add_argument('agents', nargs='+', help='Agents to participate in consensus')
    
    # Get token usage
    subparsers.add_parser('查看Token使用', help='Get token usage statistics')
    
    args = parser.parse_args()
    
    if args.command == '查看所有部门':
        list_departments()
    elif args.command == '查看部门':
        list_agents_in_department(args.department)
    elif args.command == '安排任务':
        task = ' '.join(args.task)
        assign_task(args.department, task, args.agent)
    elif args.command == '创建项目':
        create_project(args.project_name, args.tasks)
    elif args.command == '发送消息':
        content = ' '.join(args.content)
        send_message(args.sender, args.receiver, args.message_type, content)
    elif args.command == '启动共识':
        issue = ' '.join(args.issue)
        start_consensus(issue, args.agents)
    elif args.command == '查看Token使用':
        get_token_usage()
    else:
        print("OPC-Agents Skill")
        print("Commands: 安排任务, 创建项目, 查看部门, 查看所有部门, 发送消息, 启动共识, 查看Token使用")

if __name__ == "__main__":
    main()