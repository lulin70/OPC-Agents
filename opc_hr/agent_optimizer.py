#!/usr/bin/env python3
"""
AgentOptimizer模块

实现代理自我优化功能，用于自动性能改进。
"""

import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

class AgentOptimizer:
    """代理优化器类"""
    
    def __init__(self):
        """初始化代理优化器"""
        self.logger = logging.getLogger('OPC-Agents.AgentOptimizer')
        self.optimization_history = []
        self.performance_metrics = {}
        
    def analyze_performance(self, agent_name: str, agent_data: Dict[str, Any]) -> Dict[str, float]:
        """
        分析代理性能
        
        Args:
            agent_name: 代理名称
            agent_data: 代理数据
            
        Returns:
            性能指标字典
        """
        try:
            # 计算性能指标
            performance = {
                'response_time': self._calculate_response_time(agent_data),
                'accuracy': self._calculate_accuracy(agent_data),
                'completeness': self._calculate_completeness(agent_data),
                'relevance': self._calculate_relevance(agent_data),
                'user_satisfaction': self._calculate_user_satisfaction(agent_data)
            }
            
            # 存储性能指标
            self.performance_metrics[agent_name] = performance
            
            self.logger.info(f"分析代理性能: {agent_name}, 性能指标: {performance}")
            return performance
        except Exception as e:
            self.logger.error(f"分析代理性能失败: {e}")
            return {
                'response_time': 0.5,
                'accuracy': 0.7,
                'completeness': 0.6,
                'relevance': 0.7,
                'user_satisfaction': 0.6
            }
    
    def _calculate_response_time(self, agent_data: Dict[str, Any]) -> float:
        """计算响应时间指标"""
        response_times = agent_data.get('response_times', [1.0])
        avg_time = sum(response_times) / len(response_times) if response_times else 1.0
        # 响应时间越短越好，转换为0-1的分数
        return max(0.0, min(1.0, 1.0 - (avg_time / 5.0)))
    
    def _calculate_accuracy(self, agent_data: Dict[str, Any]) -> float:
        """计算准确性指标"""
        feedbacks = agent_data.get('feedbacks', [])
        if not feedbacks:
            return 0.7
        
        correct_feedbacks = [f for f in feedbacks if f.get('correct', True)]
        return len(correct_feedbacks) / len(feedbacks)
    
    def _calculate_completeness(self, agent_data: Dict[str, Any]) -> float:
        """计算完整性指标"""
        tasks = agent_data.get('tasks', [])
        if not tasks:
            return 0.6
        
        completed_tasks = [t for t in tasks if t.get('status') == 'completed']
        return len(completed_tasks) / len(tasks)
    
    def _calculate_relevance(self, agent_data: Dict[str, Any]) -> float:
        """计算相关性指标"""
        # 基于任务类型和代理专业领域的匹配度
        expertise = agent_data.get('expertise', '')
        tasks = agent_data.get('tasks', [])
        
        if not tasks:
            return 0.7
        
        relevant_tasks = 0
        for task in tasks:
            task_description = task.get('description', '')
            if expertise.lower() in task_description.lower():
                relevant_tasks += 1
        
        return relevant_tasks / len(tasks)
    
    def _calculate_user_satisfaction(self, agent_data: Dict[str, Any]) -> float:
        """计算用户满意度指标"""
        ratings = agent_data.get('ratings', [3])
        avg_rating = sum(ratings) / len(ratings) if ratings else 3.0
        return avg_rating / 5.0
    
    def generate_improvement_plan(self, agent_name: str, performance: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        生成改进计划
        
        Args:
            agent_name: 代理名称
            performance: 性能指标
            
        Returns:
            改进计划列表
        """
        improvement_plan = []
        
        # 基于性能指标生成改进建议
        if performance['response_time'] < 0.7:
            improvement_plan.append({
                'area': '响应时间',
                'issue': '响应时间过长',
                'suggestion': '优化代理的思考过程，减少不必要的步骤',
                'priority': 'high'
            })
        
        if performance['accuracy'] < 0.7:
            improvement_plan.append({
                'area': '准确性',
                'issue': '回答准确性不足',
                'suggestion': '增加专业知识培训，提高信息验证能力',
                'priority': 'high'
            })
        
        if performance['completeness'] < 0.7:
            improvement_plan.append({
                'area': '完整性',
                'issue': '任务完成率低',
                'suggestion': '改进任务规划能力，确保任务的完整执行',
                'priority': 'medium'
            })
        
        if performance['relevance'] < 0.7:
            improvement_plan.append({
                'area': '相关性',
                'issue': '回答与问题相关性不足',
                'suggestion': '加强对问题的理解，确保回答直接针对问题',
                'priority': 'medium'
            })
        
        if performance['user_satisfaction'] < 0.7:
            improvement_plan.append({
                'area': '用户满意度',
                'issue': '用户满意度低',
                'suggestion': '改进沟通方式，提高服务态度',
                'priority': 'medium'
            })
        
        self.logger.info(f"为代理 {agent_name} 生成改进计划: {improvement_plan}")
        return improvement_plan
    
    def optimize_agent(self, agent_name: str, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化指定代理
        
        Args:
            agent_name: 代理名称
            agent_data: 代理数据
            
        Returns:
            优化结果
        """
        try:
            # 分析性能
            performance = self.analyze_performance(agent_name, agent_data)
            
            # 生成改进计划
            improvement_plan = self.generate_improvement_plan(agent_name, performance)
            
            # 执行优化
            optimized_agent = self._execute_optimization(agent_name, agent_data, improvement_plan)
            
            # 记录优化历史
            optimization_record = {
                'agent_name': agent_name,
                'timestamp': datetime.now().isoformat(),
                'performance_before': performance,
                'improvement_plan': improvement_plan,
                'optimization_actions': [item['suggestion'] for item in improvement_plan],
                'status': 'completed'
            }
            
            self.optimization_history.append(optimization_record)
            
            # 保存优化历史
            self._save_optimization_history()
            
            self.logger.info(f"优化代理成功: {agent_name}")
            return {
                'success': True,
                'agent_name': agent_name,
                'performance': performance,
                'improvement_plan': improvement_plan,
                'optimized_agent': optimized_agent
            }
        except Exception as e:
            self.logger.error(f"优化代理失败: {e}")
            return {
                'success': False,
                'agent_name': agent_name,
                'error': str(e)
            }
    
    def _execute_optimization(self, agent_name: str, agent_data: Dict[str, Any], improvement_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行优化操作
        
        Args:
            agent_name: 代理名称
            agent_data: 代理数据
            improvement_plan: 改进计划
            
        Returns:
            优化后的代理数据
        """
        # 基于改进计划执行优化
        optimized_agent = agent_data.copy()
        
        # 添加优化标记
        optimized_agent['last_optimized'] = datetime.now().isoformat()
        optimized_agent['optimization_count'] = optimized_agent.get('optimization_count', 0) + 1
        optimized_agent['improvement_plan'] = improvement_plan
        
        # 根据改进计划更新代理属性
        for item in improvement_plan:
            if item['area'] == '响应时间':
                # 优化响应时间
                optimized_agent['response_optimized'] = True
            elif item['area'] == '准确性':
                # 增加专业知识
                optimized_agent['knowledge_enhanced'] = True
            elif item['area'] == '完整性':
                # 改进任务规划
                optimized_agent['task_planning_improved'] = True
            elif item['area'] == '相关性':
                # 加强问题理解
                optimized_agent['question_understanding_improved'] = True
            elif item['area'] == '用户满意度':
                # 改进沟通方式
                optimized_agent['communication_improved'] = True
        
        return optimized_agent
    
    def optimize_all_agents(self, agents_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        优化所有代理
        
        Args:
            agents_data: 所有代理的数据
            
        Returns:
            优化结果
        """
        results = {
            'total_agents': len(agents_data),
            'optimized_agents': 0,
            'failed_agents': 0,
            'details': {}
        }
        
        for agent_name, agent_data in agents_data.items():
            result = self.optimize_agent(agent_name, agent_data)
            results['details'][agent_name] = result
            
            if result['success']:
                results['optimized_agents'] += 1
            else:
                results['failed_agents'] += 1
        
        self.logger.info(f"优化所有代理完成: {results}")
        return results
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """
        获取优化历史
        
        Returns:
            优化历史列表
        """
        return self.optimization_history
    
    def get_performance_metrics(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取性能指标
        
        Args:
            agent_name: 代理名称，None表示所有代理
            
        Returns:
            性能指标
        """
        if agent_name:
            return self.performance_metrics.get(agent_name, {})
        return self.performance_metrics
    
    def _save_optimization_history(self):
        """
        保存优化历史到文件
        """
        try:
            # 只保存最近100条历史记录，避免文件过大
            recent_history = self.optimization_history[-100:]
            with open('optimization_history.json', 'w', encoding='utf-8') as f:
                json.dump(recent_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存优化历史失败: {e}")
    
    def load_optimization_history(self):
        """
        从文件加载优化历史
        """
        try:
            # 检查文件大小，避免加载过大的文件
            import os
            if os.path.exists('optimization_history.json'):
                file_size = os.path.getsize('optimization_history.json')
                if file_size > 10 * 1024 * 1024:  # 10MB
                    self.logger.warning("优化历史文件过大，将重置")
                    self.optimization_history = []
                    return
            
            with open('optimization_history.json', 'r', encoding='utf-8') as f:
                self.optimization_history = json.load(f)
        except Exception as e:
            self.logger.error(f"加载优化历史失败: {e}")
            self.optimization_history = []

# 测试代码
if __name__ == "__main__":
    # 初始化日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建AgentOptimizer实例
    optimizer = AgentOptimizer()
    
    # 测试数据
    test_agent_data = {
        'name': '市场研究员',
        'expertise': '市场分析',
        'response_times': [1.2, 0.8, 1.5, 0.9, 1.1],
        'feedbacks': [
            {'correct': True, 'comment': '回答准确'}, 
            {'correct': False, 'comment': '数据过时'},
            {'correct': True, 'comment': '分析深入'}
        ],
        'tasks': [
            {'status': 'completed', 'description': '市场调研分析'},
            {'status': 'completed', 'description': '竞争对手分析'},
            {'status': 'in_progress', 'description': '市场趋势预测'}
        ],
        'ratings': [4, 3, 5, 4, 3]
    }
    
    # 测试性能分析
    print("测试性能分析:")
    performance = optimizer.analyze_performance('市场研究员', test_agent_data)
    print(f"性能指标: {performance}")
    
    # 测试改进计划生成
    print("\n测试改进计划生成:")
    improvement_plan = optimizer.generate_improvement_plan('市场研究员', performance)
    print(f"改进计划: {improvement_plan}")
    
    # 测试代理优化
    print("\n测试代理优化:")
    result = optimizer.optimize_agent('市场研究员', test_agent_data)
    print(f"优化结果: {result['success']}")
    if result['success']:
        print(f"优化后的代理: {result['optimized_agent'].keys()}")
    
    # 测试优化所有代理
    print("\n测试优化所有代理:")
    test_agents_data = {
        '市场研究员': test_agent_data,
        '产品经理': {
            'name': '产品经理',
            'expertise': '产品规划',
            'response_times': [0.9, 1.1, 0.8, 1.0, 0.9],
            'feedbacks': [{'correct': True}],
            'tasks': [{'status': 'completed', 'description': '产品功能规划'}],
            'ratings': [4, 5, 4]
        }
    }
    
    all_result = optimizer.optimize_all_agents(test_agents_data)
    print(f"优化所有代理结果: {all_result}")
    
    # 测试获取优化历史
    print("\n测试获取优化历史:")
    history = optimizer.get_optimization_history()
    print(f"优化历史数量: {len(history)}")
    
    print("\nAgentOptimizer测试完成！")
