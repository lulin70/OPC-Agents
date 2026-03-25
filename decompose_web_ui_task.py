#!/usr/bin/env python3
"""
分解Web界面优化任务并评估可行性
"""

from opc_manager import OPCManager

def main():
    # 初始化OPC管理器
    manager = OPCManager()
    
    # 分解Web界面优化任务
    print("=== 分解Web界面优化任务 ===")
    task = "Web界面优化，通过左侧选项展示不同界面，避免上下拖动的用户体验问题"
    decomposed_tasks = manager.decompose_task(task, "medium")
    
    print("分解的任务:")
    for i, decomposed_task in enumerate(decomposed_tasks):
        print(f"{i+1}. {decomposed_task['task']} (部门: {decomposed_task['department']}, 代理: {decomposed_task['agent']}, 优先级: {decomposed_task['priority']})")
    
    # 启动三贤者决策系统评估方案可行性
    print("\n=== 评估方案可行性 ===")
    issue = "是否将Web界面优化任务交给设计部门出方案，研发部门来修改"
    decision_result = manager.start_three_sages_decision(issue)
    
    print(f"决策结果: {decision_result['decision']}")
    print(f"综合得分: {decision_result['total_score']:.2f}/1.0")
    
    print("\n贤者意见:")
    for sage in decision_result['sages']:
        print(f"- {sage['name']} ({sage['title']}):")
        print(f"  {sage['opinion']}")

if __name__ == "__main__":
    main()
