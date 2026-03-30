#!/usr/bin/env python3
"""
API管理器

管理所有RESTful API接口的注册和处理。
"""

import logging
from typing import Dict, Any, List, Callable
from flask import Blueprint, request, jsonify

class APIManager:
    """API管理器类"""
    
    def __init__(self):
        """初始化API管理器"""
        self.logger = logging.getLogger('OPC-Agents.APIManager')
        self.api_blueprint = Blueprint('api', __name__, url_prefix='/api')
        self.routes = []
        self.middlewares = []
    
    def register_route(self, path: str, methods: List[str], handler: Callable, description: str = ''):
        """
        注册API路由
        
        Args:
            path: API路径
            methods: HTTP方法列表
            handler: 处理函数
            description: API描述
        """
        def wrapped_handler():
            try:
                # 执行中间件
                for middleware in self.middlewares:
                    result = middleware(request)
                    if result is not None:
                        return result
                
                # 执行处理函数
                return handler()
            except Exception as e:
                self.logger.error(f"API处理失败: {e}")
                return jsonify({'error': str(e)}), 500
        
        # 注册路由
        self.api_blueprint.route(path, methods=methods)(wrapped_handler)
        
        # 记录路由信息
        self.routes.append({
            'path': path,
            'methods': methods,
            'description': description
        })
        
        self.logger.info(f"注册API路由: {path} [{', '.join(methods)}]")
    
    def add_middleware(self, middleware: Callable):
        """
        添加中间件
        
        Args:
            middleware: 中间件函数
        """
        self.middlewares.append(middleware)
        self.logger.info("添加API中间件")
    
    def get_blueprint(self) -> Blueprint:
        """
        获取Flask蓝图
        
        Returns:
            Flask蓝图
        """
        return self.api_blueprint
    
    def get_routes(self) -> List[Dict[str, Any]]:
        """
        获取所有注册的路由
        
        Returns:
            路由列表
        """
        return self.routes
    
    def register_default_routes(self, manager):
        """
        注册默认路由
        
        Args:
            manager: OPCManager实例
        """
        # 健康检查
        self.register_route('/health', ['GET'], lambda: jsonify({'status': 'ok'}), '健康检查')
        
        # 任务管理
        def get_tasks():
            tasks = manager.get_all_tasks()
            return jsonify(tasks)
        
        def create_task():
            data = request.json
            task_name = data.get('task_name')
            agent = data.get('agent')
            status = data.get('status', 'pending')
            
            if not task_name or not agent:
                return jsonify({'error': 'Task name and agent are required'}), 400
            
            task_id = manager.create_task(f"task-{int(time.time())}", task_name, agent, status)
            return jsonify({'task_id': task_id})
        
        def get_task():
            task_id = request.view_args.get('task_id')
            task = manager.get_task(task_id)
            if task:
                return jsonify(task)
            return jsonify({'error': 'Task not found'}), 404
        
        def update_task():
            task_id = request.view_args.get('task_id')
            data = request.json
            status = data.get('status')
            progress = data.get('progress')
            
            if status:
                manager.update_task_status(task_id, status, progress)
            return jsonify({'success': True})
        
        def delete_task():
            task_id = request.view_args.get('task_id')
            manager.delete_task(task_id)
            return jsonify({'success': True})
        
        # 注册任务路由
        self.register_route('/tasks', ['GET'], get_tasks, '获取所有任务')
        self.register_route('/tasks', ['POST'], create_task, '创建任务')
        self.register_route('/tasks/<task_id>', ['GET'], get_task, '获取任务详情')
        self.register_route('/tasks/<task_id>', ['PUT'], update_task, '更新任务')
        self.register_route('/tasks/<task_id>', ['DELETE'], delete_task, '删除任务')
        
        # 代理管理
        def get_agents():
            agents = manager.get_all_agents()
            return jsonify(agents)
        
        def create_agent():
            data = request.json
            agent_name = data.get('name')
            agent_type = data.get('type', 'general')
            expertise = data.get('expertise', 'general')
            
            if not agent_name:
                return jsonify({'error': 'Agent name is required'}), 400
            
            manager.create_agent(agent_name, agent_type, expertise)
            return jsonify({'success': True, 'agent_name': agent_name})
        
        def get_agent():
            agent_name = request.view_args.get('agent_name')
            agent = manager.get_agent(agent_name)
            if agent:
                return jsonify(agent)
            return jsonify({'error': 'Agent not found'}), 404
        
        def update_agent():
            agent_name = request.view_args.get('agent_name')
            data = request.json
            agent_type = data.get('type')
            expertise = data.get('expertise')
            
            manager.update_agent(agent_name, agent_type, expertise)
            return jsonify({'success': True, 'agent_name': agent_name})
        
        def delete_agent():
            agent_name = request.view_args.get('agent_name')
            manager.delete_agent(agent_name)
            return jsonify({'success': True, 'agent_name': agent_name})
        
        # 注册代理路由
        self.register_route('/agents', ['GET'], get_agents, '获取所有代理')
        self.register_route('/agents', ['POST'], create_agent, '创建代理')
        self.register_route('/agents/<agent_name>', ['GET'], get_agent, '获取代理详情')
        self.register_route('/agents/<agent_name>', ['PUT'], update_agent, '更新代理')
        self.register_route('/agents/<agent_name>', ['DELETE'], delete_agent, '删除代理')
        
        # 部门管理
        def get_departments():
            departments = manager.get_departments()
            return jsonify(departments)
        
        def get_department_agents():
            department = request.view_args.get('department')
            agents = manager.get_official_agent_by_department(department)
            return jsonify(agents)
        
        # 注册部门路由
        self.register_route('/departments', ['GET'], get_departments, '获取所有部门')
        self.register_route('/department/<department>', ['GET'], get_department_agents, '获取部门代理')

# 导入time模块
import time