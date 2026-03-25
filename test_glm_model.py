#!/usr/bin/env python3
"""
测试OPC-Agents GLM模型功能
"""

from opc_manager import OPCManager

if __name__ == "__main__":
    print("=== OPC-Agents GLM模型测试 ===")
    
    # 初始化OPC Manager
    manager = OPCManager()
    
    print("\n1. 测试GLM模型配置")
    print("-" * 50)
    
    # 获取GLM模型配置
    glm_config = manager.get_model_config('glm')
    print(f"GLM模型配置: {glm_config}")
    
    print("\n2. 测试使用GLM模型分配任务")
    print("-" * 50)
    
    # 使用GLM模型
    print("\n使用GLM模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect",
        model="glm"
    )
    print(f"结果: {result[:100]}...")
    
    # 使用GLM模型处理不同类型的任务
    print("\n使用GLM模型处理技术任务:")
    result = manager.assign_task(
        "实现一个用户认证系统",
        "engineering",
        "Backend Architect",
        model="glm"
    )
    print(f"结果: {result[:100]}...")
    
    print("\n使用GLM模型处理营销任务:")
    result = manager.assign_task(
        "制定社交媒体营销策略",
        "marketing",
        "digital_marketer",
        model="glm"
    )
    print(f"结果: {result[:100]}...")
    
    print("\n3. 测试项目运行时使用GLM模型")
    print("-" * 50)
    
    # 测试项目运行时使用GLM模型
    project_tasks = [
        {
            "department": "design",
            "task": "设计企业logo",
            "agent": "UX Architect",
            "model": "glm"
        },
        {
            "department": "engineering",
            "task": "实现用户注册功能",
            "agent": "Backend Architect",
            "model": "glm"
        },
        {
            "department": "marketing",
            "task": "制定社交媒体营销策略",
            "agent": "digital_marketer",
            "model": "glm"
        }
    ]
    
    project_results = manager.run_project("企业品牌建设", project_tasks)
    for task_key, result in project_results.items():
        print(f"\n任务: {task_key}")
        print(f"结果: {result[:100]}...")
    
    print("\n=== GLM模型测试完成 ===")
