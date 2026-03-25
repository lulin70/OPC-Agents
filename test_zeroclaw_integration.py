#!/usr/bin/env python3
"""
测试 ZeroClaw 框架集成

测试 OPC-Agents 系统通过 ZeroClaw 框架调用 LLM 的功能。
"""

import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opc_manager import OPCManager

class ZeroClawIntegrationTest:
    """ZeroClaw 集成测试类"""
    
    def __init__(self):
        """初始化测试"""
        self.manager = OPCManager()
    
    def test_zeroclaw_connection(self):
        """测试 ZeroClaw 连接"""
        print("\n=== 测试 ZeroClaw 连接 ===")
        
        # 测试直接调用 ZeroClaw 集成
        try:
            # 测试聊天完成 API
            prompt = "你好，我是 OPC-Agents 系统，测试 ZeroClaw 集成"
            response = self.manager.zeroclaw.call_chat_completion(prompt)
            
            if response:
                print("✅ ZeroClaw 聊天完成 API 调用成功")
                print(f"响应: {response[:100]}...")
            else:
                print("❌ ZeroClaw 聊天完成 API 调用失败")
        except Exception as e:
            print(f"❌ ZeroClaw 连接测试失败: {e}")
    
    def test_opc_manager_llm_call(self):
        """测试 OPC Manager 的 LLM 调用"""
        print("\n=== 测试 OPC Manager 的 LLM 调用 ===")
        
        try:
            # 测试通过 OPC Manager 调用 LLM
            prompt = "描述 OPC-Agents 系统的主要功能"
            response = self.manager.call_llm_api(prompt, model_name="zeroclaw")
            
            if response:
                print("✅ OPC Manager LLM 调用成功")
                print(f"响应: {response[:100]}...")
            else:
                print("❌ OPC Manager LLM 调用失败")
        except Exception as e:
            print(f"❌ OPC Manager LLM 调用测试失败: {e}")
    
    def test_three_sages_decision(self):
        """测试三贤者决策系统"""
        print("\n=== 测试三贤者决策系统 ===")
        
        try:
            # 测试三贤者决策系统
            issue = "OPC-Agents 系统是否应该集成 ZeroClaw 框架"
            decision_result = self.manager.start_three_sages_decision(issue)
            
            if decision_result:
                print("✅ 三贤者决策系统测试成功")
                print(f"决策结果: {decision_result['decision']}")
                print(f"综合得分: {decision_result['total_score']:.2f}")
            else:
                print("❌ 三贤者决策系统测试失败")
        except Exception as e:
            print(f"❌ 三贤者决策系统测试失败: {e}")
    
    def test_task_decomposition(self):
        """测试任务分解功能"""
        print("\n=== 测试任务分解功能 ===")
        
        try:
            # 测试任务分解
            task = "集成 ZeroClaw 框架到 OPC-Agents 系统"
            decomposed_tasks = self.manager.decompose_task(task)
            
            if decomposed_tasks:
                print("✅ 任务分解功能测试成功")
                print(f"分解出 {len(decomposed_tasks)} 个子任务")
                for i, sub_task in enumerate(decomposed_tasks, 1):
                    print(f"{i}. {sub_task['task']} (部门: {sub_task['department']})")
            else:
                print("❌ 任务分解功能测试失败")
        except Exception as e:
            print(f"❌ 任务分解功能测试失败: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始测试 ZeroClaw 框架集成...")
        
        self.test_zeroclaw_connection()
        self.test_opc_manager_llm_call()
        self.test_three_sages_decision()
        self.test_task_decomposition()
        
        print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test = ZeroClawIntegrationTest()
    test.run_all_tests()
