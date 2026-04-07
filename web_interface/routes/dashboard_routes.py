#!/usr/bin/env python3
"""
实时监控仪表板 API 路由

提供系统监控、任务状态、Agent 状态等实时数据
"""

from flask import Blueprint, jsonify
from datetime import datetime, timedelta
import psutil
import json

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api')


@dashboard_bp.route('/stats')
def get_stats():
    """获取系统统计数据"""
    # TODO: 从数据库或缓存获取真实数据
    stats = {
        'running_tasks': 3,
        'completed_today': 12,
        'active_agents': 18,
        'health_score': 95
    }
    return jsonify(stats)


@dashboard_bp.route('/monitoring/resources')
def get_resources():
    """获取资源使用情况"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    resources = {
        'cpu_usage': cpu_percent,
        'memory_usage': memory.percent,
        'disk_usage': disk.percent,
        'cpu_count': psutil.cpu_count(),
        'memory_total': memory.total / (1024 ** 3),  # GB
        'memory_available': memory.available / (1024 ** 3),  # GB
        'disk_total': disk.total / (1024 ** 3),  # GB
        'disk_free': disk.free / (1024 ** 3)  # GB
    }
    
    return jsonify(resources)


@dashboard_bp.route('/tasks')
def get_tasks():
    """获取任务列表"""
    # TODO: 从数据库获取真实任务数据
    tasks = {
        'tasks': [
            {
                'id': 'task_001',
                'name': '市场分析',
                'status': 'running',
                'department': 'research',
                'agent_name': '市场分析师',
                'progress': 65,
                'created_at': (datetime.now() - timedelta(hours=2)).isoformat()
            },
            {
                'id': 'task_002',
                'name': '竞品调研',
                'status': 'running',
                'department': 'research',
                'agent_name': '竞品分析师',
                'progress': 30,
                'created_at': (datetime.now() - timedelta(hours=1)).isoformat()
            },
            {
                'id': 'task_003',
                'name': '产品方案设计',
                'status': 'pending',
                'department': 'product',
                'agent_name': '产品经理',
                'progress': 0,
                'created_at': datetime.now().isoformat()
            },
            {
                'id': 'task_004',
                'name': 'UI 设计',
                'status': 'completed',
                'department': 'design',
                'agent_name': 'UI 设计师',
                'progress': 100,
                'created_at': (datetime.now() - timedelta(hours=5)).isoformat()
            }
        ]
    }
    return jsonify(tasks)


@dashboard_bp.route('/agents/status')
def get_agents_status():
    """获取 Agent 状态"""
    # TODO: 从数据库获取真实 Agent 状态
    agents = {
        'agents': [
            {'name': '总裁办助理', 'status': 'busy', 'department': 'executive'},
            {'name': '市场分析师', 'status': 'busy', 'department': 'research'},
            {'name': '产品经理', 'status': 'idle', 'department': 'product'},
            {'name': 'UI 设计师', 'status': 'idle', 'department': 'design'},
            {'name': '前端工程师', 'status': 'busy', 'department': 'engineering'},
            {'name': '后端工程师', 'status': 'idle', 'department': 'engineering'},
            {'name': '测试工程师', 'status': 'idle', 'department': 'qa'},
            {'name': '财务分析师', 'status': 'idle', 'department': 'finance'},
        ]
    }
    return jsonify(agents)


@dashboard_bp.route('/logs/recent')
def get_recent_logs():
    """获取最近日志"""
    # TODO: 从日志系统获取真实日志
    now = datetime.now()
    logs = {
        'logs': [
            {
                'timestamp': (now - timedelta(seconds=10)).strftime('%H:%M:%S'),
                'level': 'INFO',
                'message': '任务 task_001 进度更新：65%'
            },
            {
                'timestamp': (now - timedelta(seconds=30)).strftime('%H:%M:%S'),
                'level': 'INFO',
                'message': 'Agent 市场分析师 开始执行竞品调研'
            },
            {
                'timestamp': (now - timedelta(minutes=2)).strftime('%H:%M:%S'),
                'level': 'WARNING',
                'message': 'CPU 使用率超过 75%，建议关注'
            },
            {
                'timestamp': (now - timedelta(minutes=5)).strftime('%H:%M:%S'),
                'level': 'INFO',
                'message': '任务 task_004 已完成，交付物：UI_design_v1.md'
            },
            {
                'timestamp': (now - timedelta(minutes=10)).strftime('%H:%M:%S'),
                'level': 'INFO',
                'message': '新用户任务提交：产品方案设计'
            }
        ]
    }
    return jsonify(logs)


@dashboard_bp.route('/notifications')
def get_notifications():
    """获取通知列表"""
    # TODO: 从通知系统获取真实通知
    notifications = {
        'notifications': [
            {
                'id': 'notif_001',
                'level': 'P1',
                'title': '任务完成',
                'message': 'UI 设计任务已完成',
                'timestamp': (datetime.now() - timedelta(minutes=5)).isoformat(),
                'read': False
            },
            {
                'id': 'notif_002',
                'level': 'P2',
                'title': '资源警告',
                'message': 'CPU 使用率较高，请注意',
                'timestamp': (datetime.now() - timedelta(minutes=2)).isoformat(),
                'read': False
            }
        ]
    }
    return jsonify(notifications)


@dashboard_bp.route('/system/health')
def get_system_health():
    """获取系统健康状态"""
    health = {
        'overall_score': 95,
        'components': [
            {'name': 'OPC Manager', 'status': 'healthy', 'latency_ms': 45},
            {'name': 'Database', 'status': 'healthy', 'latency_ms': 12},
            {'name': 'Message Queue', 'status': 'healthy', 'latency_ms': 8},
            {'name': 'Web Server', 'status': 'healthy', 'latency_ms': 23},
            {'name': 'Model API', 'status': 'healthy', 'latency_ms': 156}
        ],
        'last_check': datetime.now().isoformat()
    }
    return jsonify(health)
