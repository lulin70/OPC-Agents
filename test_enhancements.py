#!/usr/bin/env python3
"""
测试OPC-Agents增强功能
"""

from opc_manager import OPCManager

if __name__ == "__main__":
    print("=== OPC-Agents 增强功能测试 ===")
    
    # 初始化OPC Manager
    manager = OPCManager()
    
    print("\n1. 测试任务状态跟踪功能")
    print("-" * 50)
    
    # 创建任务
    manager.create_task("task_001", "设计企业官网UI", "UX Architect")
    manager.create_task("task_002", "实现用户认证系统", "Backend Architect")
    manager.create_task("task_003", "制定市场推广策略", "Digital Marketer")
    
    # 更新任务状态
    manager.update_task_status("task_001", "in_progress", 30)
    manager.update_task_status("task_002", "in_progress", 15)
    
    # 获取任务状态
    task1_status = manager.get_task_status("task_001")
    print(f"任务1状态: {task1_status['status']}, 进度: {task1_status['progress']}%")
    
    # 获取所有任务
    all_tasks = manager.get_all_tasks()
    print("\n所有任务:")
    for task_id, task_info in all_tasks.items():
        print(f"- {task_id}: {task_info['task_name']} (状态: {task_info['status']}, 进度: {task_info['progress']}%)")
    
    # 完成任务
    manager.update_task_status("task_001", "completed", 100)
    
    # 获取特定状态的任务
    completed_tasks = manager.get_tasks_by_status("completed")
    print("\n已完成的任务:")
    for task in completed_tasks:
        print(f"- {task['task_id']}: {task['task_name']}")
    
    print("\n2. 测试增强的共识机制")
    print("-" * 50)
    
    # 测试多数决投票
    print("\n测试多数决投票 (60%阈值):")
    agents = ["UX Architect", "Backend Architect", "Digital Marketer", "Project Manager", "QA Engineer"]
    consensus_result = manager.start_consensus("是否采用微服务架构", agents, voting_method="majority", decision_threshold=0.6)
    print(f"共识结果: {consensus_result['status']}")
    print(f"决策: {consensus_result['decision']}")
    
    # 测试一致通过投票
    print("\n测试一致通过投票:")
    consensus_result = manager.start_consensus("是否使用云服务", agents, voting_method="unanimous")
    print(f"共识结果: {consensus_result['status']}")
    print(f"决策: {consensus_result['decision']}")
    
    print("\n3. 测试Token消耗优化")
    print("-" * 50)
    
    # 发送长消息
    long_message = """这是一条很长的测试消息，用于测试消息压缩功能。这条消息包含了很多重复的内容，以及一些不必要的冠词和连接词。
    我们希望通过压缩算法来减少Token的使用，同时保持消息的核心内容不变。
    这样可以在保证通信质量的同时，降低系统的Token消耗，提高系统的运行效率。"""
    
    result = manager.send_message("Test Sender", "Test Receiver", "test", long_message)
    print(f"消息发送成功: {result['success']}")
    
    # 查看Token使用情况
    token_usage = manager.get_token_usage()
    print("\nToken使用情况:")
    for agent, usage in token_usage.items():
        print(f"- {agent}: {usage} tokens")
    
    print("\n=== 测试完成 ===")
