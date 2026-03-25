#!/usr/bin/env python3
"""
测试增强后的总裁办和三贤者系统功能
"""

from opc_manager import OPCManager
import time

def test_executive_office_enhanced():
    """测试增强后的总裁办功能"""
    print("=== 测试增强后的总裁办功能 ===")
    
    manager = OPCManager()
    
    # 测试1: 任务分解
    print("\n1. 测试任务分解功能")
    task = "帮助企业实施Agent落地项目"
    decomposed_tasks = manager.decompose_task(task, "medium")
    print(f"分解任务数: {len(decomposed_tasks)}")
    for i, decomposed_task in enumerate(decomposed_tasks):
        print(f"  {i+1}. {decomposed_task['task']} (部门: {decomposed_task['department']}, 代理: {decomposed_task['agent']}, 优先级: {decomposed_task['priority']})")
    
    # 测试2: 三贤者决策
    print("\n2. 测试三贤者决策系统")
    issue = "是否应该投资开发新的AI代理产品"
    decision_result = manager.start_three_sages_decision(issue)
    print(f"决策结果: {decision_result['decision']}")
    print(f"综合得分: {decision_result['total_score']:.2f}/1.0")
    
    # 测试3: 进度跟踪
    print("\n3. 测试进度跟踪功能")
    # 先创建一些测试任务
    test_tasks = []
    for i in range(5):
        task_id = f"test_task_{i+1}"
        task_name = f"测试任务 {i+1}"
        agent = "project_coordinator"
        manager.create_task(task_id, task_name, agent, "in_progress")
        manager.update_task_status(task_id, "in_progress", (i+1) * 20)
        test_tasks.append(task_id)
    
    # 跟踪进度
    progress = manager.track_progress()
    print(f"总任务数: {progress['overview']['total_tasks']}")
    print(f"平均进度: {progress['overview']['average_progress']:.1f}%")
    print("部门进度:")
    for department, data in progress['by_department'].items():
        print(f"  {department}: {data['average_progress']:.1f}% (共{data['total']}个任务)")
    
    # 测试4: 生成报告
    print("\n4. 测试报告生成功能")
    report = manager.generate_report("weekly")
    print(f"报告周期: {report['period']}")
    print(f"总任务数: {report['task_summary']['total_tasks']}")
    print(f"平均进度: {report['task_summary']['average_progress']:.1f}%")
    print("智能洞察:")
    for insight in report['insights']:
        print(f"  - {insight}")
    print("建议:")
    for recommendation in report['recommendations']:
        print(f"  - {recommendation}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_executive_office_enhanced()
