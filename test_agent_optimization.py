#!/usr/bin/env python3
"""
测试Agent自我优化迭代功能
"""

from opc_manager import OPCManager
import time

def test_agent_optimization():
    """测试Agent自我优化功能"""
    print("=== 测试Agent自我优化迭代功能 ===")
    
    manager = OPCManager()
    
    # 测试1: 优化所有Agent
    print("\n1. 测试优化所有Agent")
    result = manager.optimize_agents(iterations=2)
    
    print(f"总迭代次数: {result['summary']['total_iterations']}")
    print(f"优化的Agent数量: {len(result['summary']['optimized_agents'])}")
    print("改进总结:")
    for improvement in result['summary']['improvements']:
        print(f"  - {improvement}")
    
    # 测试2: 优化特定Agent
    print("\n2. 测试优化特定Agent")
    specific_agents = ["project_coordinator", "strategy_planner"]
    result2 = manager.optimize_agents(agent_ids=specific_agents, iterations=1)
    
    print(f"总迭代次数: {result2['summary']['total_iterations']}")
    print(f"优化的Agent: {result2['summary']['optimized_agents']}")
    print("改进总结:")
    for improvement in result2['summary']['improvements']:
        print(f"  - {improvement}")
    
    # 测试3: 检查优化记录是否生成
    print("\n3. 检查优化记录")
    import os
    records_dir = "optimization_records"
    if os.path.exists(records_dir):
        records = os.listdir(records_dir)
        print(f"生成的优化记录数量: {len(records)}")
        for record in records:
            print(f"  - {record}")
    else:
        print("优化记录目录不存在")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_agent_optimization()
