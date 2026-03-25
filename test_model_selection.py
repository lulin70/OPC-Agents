#!/usr/bin/env python3
"""
测试OPC-Agents模型选择功能
"""

from opc_manager import OPCManager

if __name__ == "__main__":
    print("=== OPC-Agents 模型选择功能测试 ===")
    
    # 初始化OPC Manager
    manager = OPCManager()
    
    print("\n1. 测试获取可用模型")
    print("-" * 50)
    
    # 获取可用模型
    available_models = manager.get_available_models()
    print(f"可用模型: {available_models}")
    
    print("\n2. 测试获取模型配置")
    print("-" * 50)
    
    # 获取默认模型配置
    default_model_config = manager.get_model_config()
    print(f"默认模型配置: {default_model_config}")
    
    # 获取特定模型配置
    trae_config = manager.get_model_config('trae')
    print(f"TRAE模型配置: {trae_config}")
    
    openai_config = manager.get_model_config('openai')
    print(f"OpenAI模型配置: {openai_config}")
    
    print("\n3. 测试使用不同模型分配任务")
    print("-" * 50)
    
    # 使用默认模型
    print("\n使用默认模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect"
    )
    print(f"结果: {result[:100]}...")
    
    # 使用OpenAI模型
    print("\n使用OpenAI模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect",
        model="openai"
    )
    print(f"结果: {result[:100]}...")
    
    # 使用Anthropic模型
    print("\n使用Anthropic模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect",
        model="anthropic"
    )
    print(f"结果: {result[:100]}...")
    
    # 使用Google模型
    print("\n使用Google模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect",
        model="google"
    )
    print(f"结果: {result[:100]}...")
    
    # 使用本地模型
    print("\n使用本地模型:")
    result = manager.assign_task(
        "设计一个企业官网首页",
        "design",
        "UX Architect",
        model="local"
    )
    print(f"结果: {result[:100]}...")
    
    print("\n4. 测试项目运行时指定模型")
    print("-" * 50)
    
    # 测试项目运行时指定模型
    project_tasks = [
        {
            "department": "design",
            "task": "设计企业logo",
            "agent": "UX Architect",
            "model": "openai"
        },
        {
            "department": "engineering",
            "task": "实现用户注册功能",
            "agent": "Backend Architect",
            "model": "anthropic"
        },
        {
            "department": "marketing",
            "task": "制定社交媒体营销策略",
            "agent": "digital_marketer",
            "model": "google"
        }
    ]
    
    project_results = manager.run_project("企业品牌建设", project_tasks)
    for task_key, result in project_results.items():
        print(f"\n任务: {task_key}")
        print(f"结果: {result[:100]}...")
    
    print("\n=== 模型选择功能测试完成 ===")
