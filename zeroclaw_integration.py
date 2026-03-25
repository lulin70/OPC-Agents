#!/usr/bin/env python3
"""
ZeroClaw 框架集成模块

负责与 ZeroClaw 框架的交互，提供 API 调用和响应处理功能。
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any

class ZeroClawIntegration:
    """ZeroClaw 框架集成类"""
    
    def __init__(self, base_url: str = "http://localhost:8081", pairing_code: str = None):
        """初始化 ZeroClaw 集成
        
        Args:
            base_url: ZeroClaw 服务的基础 URL
            pairing_code: 配对代码
        """
        self.base_url = base_url
        self.api_endpoints = {
            "chat_completions": f"{base_url}/webhook",
            "pair": f"{base_url}/pair",
            "health": f"{base_url}/health"
        }
        self.paired = False
        self.pairing_code = pairing_code
        self.auth_token = None
        
        # 检查健康状态
        try:
            response = requests.get(self.api_endpoints["health"], timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("paired", False):
                    print("[ZeroClaw] Gateway 已配对，跳过配对步骤")
                    self.paired = True
                else:
                    # 如果未配对且提供了配对代码，自动进行配对
                    if pairing_code:
                        self.pair(pairing_code)
        except Exception as e:
            print(f"[ZeroClaw] 检查健康状态失败: {e}")
    
    def call_chat_completion(self, prompt: str, model: str = "zhipu/glm-4.7", temperature: float = 1.0, max_tokens: int = 65536) -> Optional[str]:
        """调用 ZeroClaw 的聊天完成 API
        
        Args:
            prompt: 提示词
            model: 使用的模型
            temperature: 温度参数
            max_tokens: 最大 tokens 数
            
        Returns:
            模型的响应
        """
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            # 尝试调用API，不依赖配对状态
            data = {
                "message": prompt
            }
            
            response = requests.post(self.api_endpoints["chat_completions"], headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                # 直接返回响应内容，因为 ZeroClaw Gateway 返回的是纯文本
                return response.text
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error calling chat completion API: {e}")
            return None
    
    def get_agents(self) -> Optional[List[Dict[str, Any]]]:
        """获取所有 Agent
        
        Returns:
            Agent 列表
        """
        try:
            response = requests.get(self.api_endpoints["agents"], timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error getting agents: {e}")
            return None
    
    def create_agent(self, name: str, role: str, instructions: str) -> Optional[Dict[str, Any]]:
        """创建新 Agent
        
        Args:
            name: Agent 名称
            role: Agent 角色
            instructions: Agent 指令
            
        Returns:
            创建的 Agent 信息
        """
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "name": name,
                "role": role,
                "instructions": instructions
            }
            
            response = requests.post(self.api_endpoints["agents"], headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error creating agent: {e}")
            return None
    
    def get_workflows(self) -> Optional[List[Dict[str, Any]]]:
        """获取所有工作流
        
        Returns:
            工作流列表
        """
        try:
            response = requests.get(self.api_endpoints["workflows"], timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error getting workflows: {e}")
            return None
    
    def create_workflow(self, name: str, description: str, phases: List[str]) -> Optional[Dict[str, Any]]:
        """创建新工作流
        
        Args:
            name: 工作流名称
            description: 工作流描述
            phases: 工作流阶段
            
        Returns:
            创建的工作流信息
        """
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "name": name,
                "description": description,
                "phases": phases
            }
            
            response = requests.post(self.api_endpoints["workflows"], headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error creating workflow: {e}")
            return None
    
    def get_files(self) -> Optional[List[Dict[str, Any]]]:
        """获取所有文件
        
        Returns:
            文件列表
        """
        try:
            response = requests.get(self.api_endpoints["files"], timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error getting files: {e}")
            return None
    
    def upload_file(self, file_path: str, file_name: str) -> Optional[Dict[str, Any]]:
        """上传文件
        
        Args:
            file_path: 文件路径
            file_name: 文件名称
            
        Returns:
            上传的文件信息
        """
        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (file_name, f)
                }
                
                response = requests.post(self.api_endpoints["files"], files=files, timeout=60)
                
                if response.status_code == 201:
                    return response.json()
                else:
                    print(f"[ZeroClaw] API returned error: {response.text}")
                    return None
        except Exception as e:
            print(f"[ZeroClaw] Error uploading file: {e}")
            return None
    
    def get_memory(self, query: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """获取内存中的信息
        
        Args:
            query: 查询语句
            limit: 返回结果数量限制
            
        Returns:
            内存中的信息列表
        """
        try:
            params = {
                "query": query,
                "limit": limit
            }
            
            response = requests.get(self.api_endpoints["memory"], params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error getting memory: {e}")
            return None
    
    def add_memory(self, content: str, tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """添加内存
        
        Args:
            content: 内存内容
            tags: 标签列表
            
        Returns:
            添加的内存信息
        """
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            data = {
                "content": content,
                "tags": tags or []
            }
            
            response = requests.post(self.api_endpoints["memory"], headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                return response.json()
            else:
                print(f"[ZeroClaw] API returned error: {response.text}")
                return None
        except Exception as e:
            print(f"[ZeroClaw] Error adding memory: {e}")
            return None
    
    def pair(self, pairing_code: str) -> bool:
        """与 ZeroClaw Gateway 进行配对
        
        Args:
            pairing_code: 配对代码
            
        Returns:
            是否配对成功
        """
        try:
            headers = {
                "X-Pairing-Code": pairing_code
            }
            
            response = requests.post(self.api_endpoints["pair"], headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if "token" in result:
                    self.auth_token = result["token"]
                    print("[ZeroClaw] 配对成功")
                    self.paired = True
                    self.pairing_code = pairing_code
                    return True
                else:
                    print(f"[ZeroClaw] 配对失败: 未返回令牌")
                    return False
            else:
                print(f"[ZeroClaw] 配对失败: {response.text}")
                return False
        except Exception as e:
            print(f"[ZeroClaw] 配对错误: {e}")
            return False
