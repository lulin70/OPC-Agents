#!/usr/bin/env python3
"""
模型管理器

管理多种AI模型的集成和切换。
"""

import logging
from typing import Dict, Any, Optional, List
from .model_adapters import OpenAIModel, AnthropicModel, GoogleModel, AzureModel, GLMModel, LocalModel
from .model_evaluator import ModelEvaluator

class ModelManager:
    """模型管理器类"""
    
    def __init__(self):
        """初始化模型管理器"""
        self.logger = logging.getLogger('OPC-Agents.ModelManager')
        self.models = {}
        self.current_model = None
        self.evaluator = ModelEvaluator()
        self.model_performance = {}
    
    def register_model(self, model_name: str, model_type: str, config: Dict[str, Any]):
        """
        注册模型
        
        Args:
            model_name: 模型名称
            model_type: 模型类型
            config: 模型配置
        """
        try:
            # 根据模型类型创建模型实例
            if model_type == 'openai':
                model = OpenAIModel(**config)
            elif model_type == 'anthropic':
                model = AnthropicModel(**config)
            elif model_type == 'google':
                model = GoogleModel(**config)
            elif model_type == 'azure':
                model = AzureModel(**config)
            elif model_type == 'glm':
                model = GLMModel(**config)
            elif model_type == 'local':
                model = LocalModel(**config)
            else:
                raise ValueError(f"不支持的模型类型: {model_type}")
            
            # 注册模型
            self.models[model_name] = model
            self.logger.info(f"注册模型成功: {model_name} ({model_type})")
            
            # 如果是第一个模型，设置为当前模型
            if not self.current_model:
                self.set_current_model(model_name)
                
        except Exception as e:
            self.logger.error(f"注册模型失败: {e}")
            raise
    
    def set_current_model(self, model_name: str):
        """
        设置当前模型
        
        Args:
            model_name: 模型名称
        """
        if model_name not in self.models:
            raise ValueError(f"模型不存在: {model_name}")
        
        self.current_model = model_name
        self.logger.info(f"设置当前模型: {model_name}")
    
    def get_current_model(self) -> Optional[Any]:
        """
        获取当前模型
        
        Returns:
            当前模型实例
        """
        if not self.current_model:
            return None
        return self.models.get(self.current_model)
    
    def list_models(self) -> List[str]:
        """
        列出所有模型
        
        Returns:
            模型名称列表
        """
        return list(self.models.keys())
    
    def remove_model(self, model_name: str):
        """
        移除模型
        
        Args:
            model_name: 模型名称
        """
        if model_name in self.models:
            del self.models[model_name]
            self.logger.info(f"移除模型: {model_name}")
            
            # 如果移除的是当前模型，设置第一个模型为当前模型
            if self.current_model == model_name:
                if self.models:
                    self.current_model = next(iter(self.models.keys()))
                else:
                    self.current_model = None
    
    def generate(self, prompt: str, model_name: Optional[str] = None, **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            model_name: 模型名称，None表示使用当前模型
            **kwargs: 额外参数
            
        Returns:
            生成的文本
        """
        try:
            # 选择模型
            if model_name:
                model = self.models.get(model_name)
                if not model:
                    raise ValueError(f"模型不存在: {model_name}")
            else:
                model = self.get_current_model()
                if not model:
                    raise ValueError("没有设置当前模型")
            
            # 生成文本
            start_time = time.time()
            result = model.generate(prompt, **kwargs)
            end_time = time.time()
            
            # 记录性能
            model_key = model_name or self.current_model
            self._record_performance(model_key, end_time - start_time, len(result))
            
            return result
        except Exception as e:
            self.logger.error(f"生成文本失败: {e}")
            raise
    
    def chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, **kwargs) -> str:
        """
        聊天对话
        
        Args:
            messages: 消息列表
            model_name: 模型名称，None表示使用当前模型
            **kwargs: 额外参数
            
        Returns:
            模型回复
        """
        try:
            # 选择模型
            if model_name:
                model = self.models.get(model_name)
                if not model:
                    raise ValueError(f"模型不存在: {model_name}")
            else:
                model = self.get_current_model()
                if not model:
                    raise ValueError("没有设置当前模型")
            
            # 聊天对话
            start_time = time.time()
            result = model.chat(messages, **kwargs)
            end_time = time.time()
            
            # 记录性能
            model_key = model_name or self.current_model
            self._record_performance(model_key, end_time - start_time, len(result))
            
            return result
        except Exception as e:
            self.logger.error(f"聊天对话失败: {e}")
            raise
    
    def evaluate_model(self, model_name: str, test_cases: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        评估模型性能
        
        Args:
            model_name: 模型名称
            test_cases: 测试用例列表
            
        Returns:
            评估结果
        """
        model = self.models.get(model_name)
        if not model:
            raise ValueError(f"模型不存在: {model_name}")
        
        return self.evaluator.evaluate(model, test_cases)
    
    def get_model_performance(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取模型性能
        
        Args:
            model_name: 模型名称，None表示所有模型
            
        Returns:
            性能数据
        """
        if model_name:
            return self.model_performance.get(model_name, {})
        return self.model_performance
    
    def _record_performance(self, model_name: str, time_taken: float, output_length: int):
        """
        记录模型性能
        
        Args:
            model_name: 模型名称
            time_taken: 执行时间
            output_length: 输出长度
        """
        if model_name not in self.model_performance:
            self.model_performance[model_name] = {
                'total_calls': 0,
                'total_time': 0,
                'total_output_length': 0,
                'avg_time': 0,
                'avg_output_length': 0
            }
        
        perf = self.model_performance[model_name]
        perf['total_calls'] += 1
        perf['total_time'] += time_taken
        perf['total_output_length'] += output_length
        perf['avg_time'] = perf['total_time'] / perf['total_calls']
        perf['avg_output_length'] = perf['total_output_length'] / perf['total_calls']
    
    def auto_select_model(self, task_type: str) -> str:
        """
        根据任务类型自动选择模型
        
        Args:
            task_type: 任务类型
            
        Returns:
            模型名称
        """
        # 基于任务类型选择模型的逻辑
        model_preferences = {
            'text_generation': ['openai', 'anthropic', 'google'],
            'chat': ['openai', 'anthropic', 'glm'],
            'coding': ['openai', 'google', 'local'],
            'translation': ['google', 'openai', 'anthropic'],
            'summarization': ['openai', 'anthropic', 'google']
        }
        
        preferred_models = model_preferences.get(task_type, ['openai'])
        
        # 选择第一个可用的模型
        for model_name in preferred_models:
            if model_name in self.models:
                self.set_current_model(model_name)
                self.logger.info(f"根据任务类型 {task_type} 自动选择模型: {model_name}")
                return model_name
        
        # 如果没有首选模型，使用当前模型
        if self.current_model:
            return self.current_model
        
        # 如果没有模型，返回None
        return None

# 导入time模块
import time