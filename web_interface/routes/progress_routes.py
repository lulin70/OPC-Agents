#!/usr/bin/env python3
"""
实时进度反馈路由

提供Server-Sent Events (SSE)端点，用于实时进度反馈。
"""

from flask import Blueprint, request, jsonify
from message_queue import get_progress_streamer
import uuid
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('progress', __name__, url_prefix='/api/progress')


@bp.route('/stream/<task_id>')
def progress_stream(task_id):
    """SSE进度流端点
    
    Args:
        task_id: 任务ID
        
    Returns:
        SSE流响应
    """
    # 生成客户端ID
    client_id = request.args.get('client_id', str(uuid.uuid4()))
    
    # 获取进度流式传输器
    streamer = get_progress_streamer()
    
    # 生成SSE流
    return streamer.generate_stream(client_id, task_id)


@bp.route('/status')
def progress_status():
    """获取进度状态
    
    Returns:
        进度状态信息
    """
    streamer = get_progress_streamer()
    
    return jsonify({
        "connected_clients": len(streamer.clients),
        "active_tasks": len(streamer.task_clients)
    })
