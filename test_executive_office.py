#!/usr/bin/env python3
"""
测试OPC-Agents总裁办和三贤者决策系统功能
"""

from opc_manager import OPCManager

if __name__ == "__main__":
    print("=== OPC-Agents 总裁办和三贤者决策系统测试 ===")
    
    # 初始化OPC Manager
    manager = OPCManager()
    
    print("\n1. 测试总裁办代理获取")
    print("-" * 50)
    
    # 获取总裁办代理
    executive_office_agents = manager.get_executive_office_agents()
    print(f"总裁办代理: {executive_office_agents}")
    
    print("\n2. 测试三贤者获取")
    print("-" * 50)
    
    # 获取三贤者
    three_sages = manager.get_three_sages()
    print(f"三贤者: {three_sages}")
    
    print("\n3. 测试任务分解")
    print("-" * 50)
    
    # 测试任务分解
    decomposed_tasks = manager.decompose_task("开发一个企业官网", "medium")
    print("分解的任务:")
    for task in decomposed_tasks:
        print(f"- {task['task']} (部门: {task['department']}, 代理: {task['agent']})")
    
    print("\n4. 测试三贤者决策")
    print("-" * 50)
    
    # 测试三贤者决策
    decision_result = manager.start_three_sages_decision("是否扩展业务到新市场")
    print(f"决策议题: {decision_result['issue']}")
    print("贤者意见:")
    for sage, opinion in decision_result['opinions'].items():
        print(f"- {sage}: {opinion}")
    print("投票结果:")
    for sage, vote in decision_result['votes'].items():
        print(f"- {sage}: {'赞成' if vote else '反对'}")
    print(f"最终决策: {decision_result['decision']} (赞成票: {decision_result['yes_votes']}/3)")
    
    print("\n5. 测试进度跟踪")
    print("-" * 50)
    
    # 创建测试任务
    manager.create_task("task_001", "设计企业官网UI", "UX Architect")
    manager.create_task("task_002", "实现用户认证系统", "Backend Architect")
    manager.update_task_status("task_001", "in_progress", 30)
    manager.update_task_status("task_002", "in_progress", 15)
    
    # 测试进度跟踪
    progress = manager.track_progress(["task_001", "task_002", "task_003"])
    print("任务进度:")
    for task_id, status in progress.items():
        print(f"- {task_id}: 状态={status['status']}, 进度={status['progress']}%")
    
    print("\n6. 测试报告生成")
    print("-" * 50)
    
    # 测试报告生成
    report = manager.generate_report("weekly")
    print(f"报告周期: {report['period']}")
    print(f"生成时间: {report['generated_at']}")
    print("任务摘要:")
    print(f"- 总任务数: {report['task_summary']['total_tasks']}")
    print(f"- 平均进度: {report['task_summary']['average_progress']:.1f}%")
    print("- 状态分布:")
    for status, count in report['task_summary']['status_counts'].items():
        print(f"  - {status}: {count}")
    print("关键成就:")
    for achievement in report['key_achievements']:
        print(f"- {achievement}")
    print("挑战:")
    for challenge in report['challenges']:
        print(f"- {challenge}")
    print("建议:")
    for recommendation in report['recommendations']:
        print(f"- {recommendation}")
    
    print("\n=== 总裁办和三贤者决策系统测试完成 ===")
