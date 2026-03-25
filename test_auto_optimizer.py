#!/usr/bin/env python3
"""
测试自动优化功能
"""

from auto_optimizer import AutoOptimizer
import time

def test_auto_optimizer():
    """测试自动优化器功能"""
    print("=== 测试自动优化功能 ===")
    
    # 创建自动优化器
    auto_optimizer = AutoOptimizer()
    
    # 测试1: 显示配置
    print("\n1. 测试配置加载")
    print(f"启用状态: {auto_optimizer.config['enabled']}")
    print(f"调度类型: {auto_optimizer.config['schedule']['type']}")
    print(f"执行时间: {auto_optimizer.config['schedule']['hour']}:00")
    print(f"迭代次数: {auto_optimizer.config['optimization']['iterations']}")
    
    # 测试2: 计算下次优化时间
    print("\n2. 测试下次优化时间计算")
    next_time = auto_optimizer.get_next_optimization_time()
    print(f"下次优化时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 测试3: 选择Agent
    print("\n3. 测试Agent选择")
    agents = auto_optimizer.select_agents_for_optimization()
    print(f"选择的Agent数量: {len(agents)}")
    print(f"前5个Agent: {agents[:5]}")
    
    # 测试4: 手动执行优化
    print("\n4. 测试手动执行优化")
    result = auto_optimizer.run_optimization()
    print(f"优化完成，迭代次数: {result['summary']['total_iterations']}")
    print(f"优化的Agent数量: {len(result['summary']['optimized_agents'])}")
    print("改进总结:")
    for improvement in result['summary']['improvements']:
        print(f"  - {improvement}")
    
    # 测试5: 获取统计信息
    print("\n5. 测试统计信息")
    stats = auto_optimizer.get_optimization_statistics()
    print(f"总优化次数: {stats['total_optimizations']}")
    print(f"上次优化: {stats['last_optimization']}")
    print(f"平均改进率: {stats['average_improvement_rate']:.2f}")
    print(f"优化的Agent总数: {stats['total_agents_optimized']}")
    
    # 测试6: 更新配置
    print("\n6. 测试配置更新")
    new_config = {
        "schedule": {
            "type": "daily",
            "hour": 3,
            "minute": 0
        },
        "optimization": {
            "iterations": 2
        }
    }
    auto_optimizer.update_config(new_config)
    print(f"新调度类型: {auto_optimizer.config['schedule']['type']}")
    print(f"新执行时间: {auto_optimizer.config['schedule']['hour']}:00")
    print(f"新迭代次数: {auto_optimizer.config['optimization']['iterations']}")
    
    # 测试7: 检查通知文件
    print("\n7. 检查通知文件")
    import os
    notification_dir = "optimization_notifications"
    if os.path.exists(notification_dir):
        notifications = os.listdir(notification_dir)
        print(f"生成的通知文件数量: {len(notifications)}")
        for notification in notifications[:3]:  # 只显示前3个
            print(f"  - {notification}")
    else:
        print("通知目录不存在")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_auto_optimizer()
