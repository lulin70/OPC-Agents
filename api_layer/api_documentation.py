#!/usr/bin/env python3
"""
API文档生成器

生成API接口文档。
"""

import json
from typing import List, Dict, Any

class APIDocumentation:
    """API文档生成器类"""
    
    def __init__(self):
        """初始化API文档生成器"""
        self.documents = {
            'info': {
                'title': 'OPC-Agents API',
                'version': '1.0.0',
                'description': 'OPC-Agents系统的RESTful API接口文档'
            },
            'endpoints': []
        }
    
    def add_endpoint(self, path: str, methods: List[str], description: str, request_schema: Dict[str, Any] = None, response_schema: Dict[str, Any] = None):
        """
        添加API端点文档
        
        Args:
            path: API路径
            methods: HTTP方法列表
            description: API描述
            request_schema: 请求参数模式
            response_schema: 响应参数模式
        """
        endpoint = {
            'path': path,
            'methods': methods,
            'description': description,
            'request_schema': request_schema,
            'response_schema': response_schema
        }
        self.documents['endpoints'].append(endpoint)
    
    def generate_json(self) -> str:
        """
        生成JSON格式的文档
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.documents, ensure_ascii=False, indent=2)
    
    def generate_markdown(self) -> str:
        """
        生成Markdown格式的文档
        
        Returns:
            Markdown字符串
        """
        markdown = f"# {self.documents['info']['title']}\n"
        markdown += f"## 版本: {self.documents['info']['version']}\n"
        markdown += f"## 描述: {self.documents['info']['description']}\n\n"
        
        markdown += "## API端点\n\n"
        
        for endpoint in self.documents['endpoints']:
            markdown += f"### {endpoint['path']}\n"
            markdown += f"**方法:** {', '.join(endpoint['methods'])}\n"
            markdown += f"**描述:** {endpoint['description']}\n"
            
            if endpoint['request_schema']:
                markdown += "**请求参数:**\n"
                markdown += "```json\n"
                markdown += json.dumps(endpoint['request_schema'], ensure_ascii=False, indent=2)
                markdown += "\n```\n"
            
            if endpoint['response_schema']:
                markdown += "**响应参数:**\n"
                markdown += "```json\n"
                markdown += json.dumps(endpoint['response_schema'], ensure_ascii=False, indent=2)
                markdown += "\n```\n"
            
            markdown += "\n"
        
        return markdown
    
    def save_to_file(self, file_path: str, format: str = 'json'):
        """
        保存文档到文件
        
        Args:
            file_path: 文件路径
            format: 文档格式，支持 'json' 和 'markdown'
        """
        if format == 'json':
            content = self.generate_json()
        elif format == 'markdown':
            content = self.generate_markdown()
        else:
            raise ValueError("不支持的文档格式")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

def generate_api_docs(api_manager) -> APIDocumentation:
    """
    生成API文档
    
    Args:
        api_manager: APIManager实例
        
    Returns:
        APIDocumentation实例
    """
    docs = APIDocumentation()
    
    # 添加默认的API端点文档
    default_endpoints = [
        {
            'path': '/api/health',
            'methods': ['GET'],
            'description': '健康检查',
            'response_schema': {
                'status': 'ok'
            }
        },
        {
            'path': '/api/tasks',
            'methods': ['GET'],
            'description': '获取所有任务',
            'response_schema': {
                'task_id': {
                    'task_name': '任务名称',
                    'agent': '负责代理',
                    'status': '状态',
                    'progress': '进度',
                    'created_at': '创建时间',
                    'updated_at': '更新时间'
                }
            }
        },
        {
            'path': '/api/tasks',
            'methods': ['POST'],
            'description': '创建任务',
            'request_schema': {
                'task_name': '任务名称',
                'agent': '负责代理',
                'status': '状态'
            },
            'response_schema': {
                'task_id': '任务ID'
            }
        },
        {
            'path': '/api/tasks/<task_id>',
            'methods': ['GET'],
            'description': '获取任务详情',
            'response_schema': {
                'task_name': '任务名称',
                'agent': '负责代理',
                'status': '状态',
                'progress': '进度',
                'created_at': '创建时间',
                'updated_at': '更新时间'
            }
        },
        {
            'path': '/api/tasks/<task_id>',
            'methods': ['PUT'],
            'description': '更新任务',
            'request_schema': {
                'status': '状态',
                'progress': '进度'
            },
            'response_schema': {
                'success': '是否成功'
            }
        },
        {
            'path': '/api/tasks/<task_id>',
            'methods': ['DELETE'],
            'description': '删除任务',
            'response_schema': {
                'success': '是否成功'
            }
        },
        {
            'path': '/api/agents',
            'methods': ['GET'],
            'description': '获取所有代理',
            'response_schema': [
                {
                    'name': '代理名称',
                    'type': '代理类型',
                    'expertise': '专业领域'
                }
            ]
        },
        {
            'path': '/api/agents',
            'methods': ['POST'],
            'description': '创建代理',
            'request_schema': {
                'name': '代理名称',
                'type': '代理类型',
                'expertise': '专业领域'
            },
            'response_schema': {
                'success': '是否成功',
                'agent_name': '代理名称'
            }
        },
        {
            'path': '/api/agents/<agent_name>',
            'methods': ['GET'],
            'description': '获取代理详情',
            'response_schema': {
                'name': '代理名称',
                'type': '代理类型',
                'expertise': '专业领域'
            }
        },
        {
            'path': '/api/agents/<agent_name>',
            'methods': ['PUT'],
            'description': '更新代理',
            'request_schema': {
                'type': '代理类型',
                'expertise': '专业领域'
            },
            'response_schema': {
                'success': '是否成功',
                'agent_name': '代理名称'
            }
        },
        {
            'path': '/api/agents/<agent_name>',
            'methods': ['DELETE'],
            'description': '删除代理',
            'response_schema': {
                'success': '是否成功',
                'agent_name': '代理名称'
            }
        },
        {
            'path': '/api/departments',
            'methods': ['GET'],
            'description': '获取所有部门',
            'response_schema': ['部门名称']
        },
        {
            'path': '/api/department/<department>',
            'methods': ['GET'],
            'description': '获取部门代理',
            'response_schema': [
                {
                    'name': '代理名称',
                    'description': '代理描述',
                    'expertise': '专业领域',
                    'skill_level': '技能等级'
                }
            ]
        }
    ]
    
    for endpoint in default_endpoints:
        docs.add_endpoint(
            path=endpoint['path'],
            methods=endpoint['methods'],
            description=endpoint['description'],
            request_schema=endpoint.get('request_schema'),
            response_schema=endpoint.get('response_schema')
        )
    
    return docs