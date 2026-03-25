#!/usr/bin/env python3
"""
测试OPC-Agents系统的所有功能
"""

import requests
import json
import time

BASE_URL = "http://localhost:5004"

def test_three_layer_architecture():
    """测试三层架构"""
    print("\n=== 测试三层架构 ===")
    response = requests.get(f"{BASE_URL}/api/three_layer_architecture")
    if response.status_code == 200:
        data = response.json()
        print(f"总裁办Agent数量: {len(data.get('executive_office', {}).get('agents', {}))}")
        print(f"部门数量: {len(data.get('departments', {}))}")
        print(f"员工Agent数量: {len(data.get('employees', {}))}")
        print("三层架构测试成功")
    else:
        print(f"三层架构测试失败: {response.status_code}")

def test_task_decomposition():
    """测试任务分解"""
    print("\n=== 测试任务分解 ===")
    data = {
        "task": "开发一个新的Web界面",
        "time_horizon": "medium"
    }
    response = requests.post(f"{BASE_URL}/api/decompose_task", json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"分解任务数: {len(result.get('tasks', []))}")
        for task in result.get('tasks', []):
            print(f"  - {task['task']} (部门: {task['department']}, 代理: {task['agent']})")
        print("任务分解测试成功")
    else:
        print(f"任务分解测试失败: {response.status_code}")

def test_three_sages_decision():
    """测试三贤者决策"""
    print("\n=== 测试三贤者决策 ===")
    data = {
        "issue": "是否应该扩展公司业务到海外市场",
        "context": "公司目前业务稳定，有一定的资金储备"
    }
    response = requests.post(f"{BASE_URL}/api/three_sages_decision", json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"决策议题: {result.get('issue')}")
        print(f"最终决策: {result.get('decision')}")
        print(f"综合得分: {result.get('total_score', 0):.2f}/1.0")
        if result.get('advice'):
            print(f"决策建议: {result.get('advice')[:100]}...")
        print("三贤者决策测试成功")
    else:
        print(f"三贤者决策测试失败: {response.status_code}")

def test_progress_tracking():
    """测试进度跟踪"""
    print("\n=== 测试进度跟踪 ===")
    data = {
        "tasks": None
    }
    response = requests.post(f"{BASE_URL}/api/track_progress", json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"总任务数: {result.get('overview', {}).get('total_tasks', 0)}")
        print(f"平均进度: {result.get('overview', {}).get('average_progress', 0):.1f}%")
        if result.get('insights'):
            print("智能洞察:")
            for insight in result.get('insights', []):
                print(f"  - {insight}")
        print("进度跟踪测试成功")
    else:
        print(f"进度跟踪测试失败: {response.status_code}")

def test_model_performance():
    """测试模型性能监控"""
    print("\n=== 测试模型性能监控 ===")
    response = requests.get(f"{BASE_URL}/api/model_performance")
    if response.status_code == 200:
        result = response.json()
        print(f"监控的模型数量: {len(result)}")
        for model, performance in result.items():
            print(f"\n模型: {model}")
            print(f"  总调用次数: {performance.get('total_calls', 0)}")
            print(f"  成功调用次数: {performance.get('successful_calls', 0)}")
            print(f"  错误次数: {performance.get('error_count', 0)}")
        print("模型性能监控测试成功")
    else:
        print(f"模型性能监控测试失败: {response.status_code}")

def test_model_recommendation():
    """测试模型推荐"""
    print("\n=== 测试模型推荐 ===")
    data = {
        "task_type": "战略规划"
    }
    response = requests.post(f"{BASE_URL}/api/model_recommendation", json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"推荐模型: {result.get('recommended_model')}")
        print(f"评分: {result.get('score', 0):.2f}")
        print("模型推荐测试成功")
    else:
        print(f"模型推荐测试失败: {response.status_code}")

def test_optimize_model_selection():
    """测试模型选择优化"""
    print("\n=== 测试模型选择优化 ===")
    response = requests.post(f"{BASE_URL}/api/optimize_model_selection")
    if response.status_code == 200:
        result = response.json()
        print(f"优化后的策略: {result.get('message')}")
        print("模型选择优化测试成功")
    else:
        print(f"模型选择优化测试失败: {response.status_code}")

def test_executive_office_chat():
    """测试总裁办对话"""
    print("\n=== 测试总裁办对话 ===")
    # 这里可以测试与总裁办的对话功能
    # 由于需要模拟用户输入，这里只做简单测试
    print("总裁办对话功能需要手动测试")
    print("请在Web界面中测试与总裁办的对话功能")

def main():
    """主测试函数"""
    print("开始测试OPC-Agents系统...")
    
    # 测试三层架构
    test_three_layer_architecture()
    
    # 测试任务分解
    test_task_decomposition()
    
    # 测试三贤者决策
    test_three_sages_decision()
    
    # 测试进度跟踪
    test_progress_tracking()
    
    # 测试模型性能监控
    test_model_performance()
    
    # 测试模型推荐
    test_model_recommendation()
    
    # 测试模型选择优化
    test_optimize_model_selection()
    
    # 测试总裁办对话
    test_executive_office_chat()
    
    print("\n所有测试完成！")
    print("请访问 http://localhost:5004 进行手动测试和验证")

if __name__ == "__main__":
    main()
