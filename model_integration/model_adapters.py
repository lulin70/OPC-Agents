#!/usr/bin/env python3
"""
模型适配器

实现各种AI模型的适配器，统一接口。
"""

import logging
from typing import List, Dict, Any, Optional

class BaseModel:
    """基础模型类"""
    
    def __init__(self, **kwargs):
        """初始化模型"""
        self.logger = logging.getLogger(f'OPC-Agents.ModelAdapter.{self.__class__.__name__}')
        self.config = kwargs
    
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本
        
        Args:
            prompt: 提示词
            **kwargs: 额外参数
            
        Returns:
            生成的文本
        """
        raise NotImplementedError
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        聊天对话
        
        Args:
            messages: 消息列表
            **kwargs: 额外参数
            
        Returns:
            模型回复
        """
        raise NotImplementedError

class OpenAIModel(BaseModel):
    """OpenAI模型适配器"""
    
    def __init__(self, api_key: str, model: str = 'gpt-3.5-turbo', **kwargs):
        """
        初始化OpenAI模型
        
        Args:
            api_key: OpenAI API密钥
            model: 模型名称
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化OpenAI客户端"""
        try:
            import openai
            openai.api_key = self.api_key
            self.client = openai
            self.logger.info(f"初始化OpenAI客户端成功: {self.model}")
        except ImportError:
            self.logger.warning("OpenAI库未安装，将使用模拟实现")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.client:
            return f"[OpenAI模拟] 生成文本: {prompt}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI生成失败: {e}")
            return f"[OpenAI错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.client:
            return f"[OpenAI模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI聊天失败: {e}")
            return f"[OpenAI错误] {str(e)}"

class AnthropicModel(BaseModel):
    """Anthropic模型适配器"""
    
    def __init__(self, api_key: str, model: str = 'claude-3-sonnet-20240229', **kwargs):
        """
        初始化Anthropic模型
        
        Args:
            api_key: Anthropic API密钥
            model: 模型名称
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Anthropic客户端"""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.logger.info(f"初始化Anthropic客户端成功: {self.model}")
        except ImportError:
            self.logger.warning("Anthropic库未安装，将使用模拟实现")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.client:
            return f"[Anthropic模拟] 生成文本: {prompt}"
        
        try:
            response = self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Anthropic生成失败: {e}")
            return f"[Anthropic错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.client:
            return f"[Anthropic模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            response = self.client.messages.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return response.content[0].text
        except Exception as e:
            self.logger.error(f"Anthropic聊天失败: {e}")
            return f"[Anthropic错误] {str(e)}"

class GoogleModel(BaseModel):
    """Google模型适配器"""
    
    def __init__(self, api_key: str, model: str = 'gemini-1.0-pro', **kwargs):
        """
        初始化Google模型
        
        Args:
            api_key: Google API密钥
            model: 模型名称
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Google客户端"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai
            self.logger.info(f"初始化Google客户端成功: {self.model}")
        except ImportError:
            self.logger.warning("Google Generative AI库未安装，将使用模拟实现")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.client:
            return f"[Google模拟] 生成文本: {prompt}"
        
        try:
            model = self.client.GenerativeModel(self.model)
            response = model.generate_content(prompt, **kwargs)
            return response.text
        except Exception as e:
            self.logger.error(f"Google生成失败: {e}")
            return f"[Google错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.client:
            return f"[Google模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            model = self.client.GenerativeModel(self.model)
            chat = model.start_chat()
            response = chat.send_message(messages[-1]['content'], **kwargs)
            return response.text
        except Exception as e:
            self.logger.error(f"Google聊天失败: {e}")
            return f"[Google错误] {str(e)}"

class AzureModel(BaseModel):
    """Azure模型适配器"""
    
    def __init__(self, api_key: str, endpoint: str, deployment_name: str, **kwargs):
        """
        初始化Azure模型
        
        Args:
            api_key: Azure API密钥
            endpoint: Azure端点
            deployment_name: 部署名称
        """
        super().__init__(api_key=api_key, endpoint=endpoint, deployment_name=deployment_name, **kwargs)
        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment_name = deployment_name
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化Azure客户端"""
        try:
            import openai
            openai.api_type = "azure"
            openai.api_key = self.api_key
            openai.api_base = self.endpoint
            openai.api_version = "2023-05-15"
            self.client = openai
            self.logger.info(f"初始化Azure客户端成功: {self.deployment_name}")
        except ImportError:
            self.logger.warning("OpenAI库未安装，将使用模拟实现")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.client:
            return f"[Azure模拟] 生成文本: {prompt}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Azure生成失败: {e}")
            return f"[Azure错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.client:
            return f"[Azure模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Azure聊天失败: {e}")
            return f"[Azure错误] {str(e)}"

class GLMModel(BaseModel):
    """GLM模型适配器"""
    
    def __init__(self, api_key: str, model: str = 'glm-4', **kwargs):
        """
        初始化GLM模型
        
        Args:
            api_key: GLM API密钥
            model: 模型名称
        """
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.api_key = api_key
        self.model = model
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化GLM客户端"""
        try:
            import zhipuai
            zhipuai.api_key = self.api_key
            self.client = zhipuai
            self.logger.info(f"初始化GLM客户端成功: {self.model}")
        except ImportError:
            self.logger.warning("ZhipuAI库未安装，将使用模拟实现")
            self.client = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.client:
            return f"[GLM模拟] 生成文本: {prompt}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"GLM生成失败: {e}")
            return f"[GLM错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.client:
            return f"[GLM模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"GLM聊天失败: {e}")
            return f"[GLM错误] {str(e)}"

class LocalModel(BaseModel):
    """本地模型适配器"""
    
    def __init__(self, model_path: str = '', **kwargs):
        """
        初始化本地模型
        
        Args:
            model_path: 模型路径
        """
        super().__init__(model_path=model_path, **kwargs)
        self.model_path = model_path
        self._initialize_model()
    
    def _initialize_model(self):
        """初始化本地模型"""
        try:
            # 尝试导入transformers
            from transformers import pipeline
            self.pipeline = pipeline("text-generation", model="gpt2")
            self.logger.info("初始化本地模型成功: gpt2")
        except ImportError:
            self.logger.warning("Transformers库未安装，将使用模拟实现")
            self.pipeline = None
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        if not self.pipeline:
            return f"[本地模型模拟] 生成文本: {prompt}"
        
        try:
            response = self.pipeline(prompt, max_length=100, **kwargs)
            return response[0]['generated_text']
        except Exception as e:
            self.logger.error(f"本地模型生成失败: {e}")
            return f"[本地模型错误] {str(e)}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天对话"""
        if not self.pipeline:
            return f"[本地模型模拟] 聊天对话: {messages[-1]['content']}"
        
        try:
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            response = self.pipeline(prompt, max_length=100, **kwargs)
            return response[0]['generated_text'].split("assistant:")[-1].strip()
        except Exception as e:
            self.logger.error(f"本地模型聊天失败: {e}")
            return f"[本地模型错误] {str(e)}"