#!/usr/bin/env python3
"""
A2A Protocol API Endpoints
为OPC-Agents系统提供A2A协议的REST API接口
"""

from flask import Blueprint, request, jsonify, Response, stream_with_context
from typing import Dict, Any, Optional
import json
import time
from a2a_protocol import (
    A2AProtocol, TaskState, Part, AuthScheme,
    AgentCard, AgentSkill, AgentCapability
)
from a2a_integration import OPCA2AIntegration

# 创建蓝图
a2a_bp = Blueprint('a2a', __name__, url_prefix='/a2a')

# 全局A2A集成实例
a2a_integration: Optional[OPCA2AIntegration] = None


def init_a2a_api(opc_manager):
    """初始化A2A API"""
    global a2a_integration
    a2a_integration = OPCA2AIntegration(opc_manager)
    print("[A2A API] 初始化完成")


# ==================== AgentCard API ====================

@a2a_bp.route('/.well-known/agent-card.json', methods=['GET'])
def get_agent_card_discovery():
    """A2A标准发现端点 - 返回系统AgentCard"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    # 返回系统级AgentCard
    system_card = AgentCard(
        name="OPC-Agents System",
        description="One Person Company Multi-Agent System with A2A Protocol support",
        url=request.host_url.rstrip('/'),
        version="2.0.0",
        authentication={
            "schemes": ["api_key", "jwt"],
            "api_key": {"header": "X-API-Key"}
        },
        capabilities=["task_management", "agent_discovery", "workflow_orchestration", "streaming"],
        metadata={
            "total_agents": len(a2a_integration.a2a.agent_cards),
            "departments": list(set(
                card.metadata.get("department", "unknown")
                for card in a2a_integration.a2a.agent_cards.values()
            ))
        }
    )
    
    return jsonify(system_card.to_dict())


@a2a_bp.route('/agents/<agent_id>/card', methods=['GET'])
def get_agent_card(agent_id: str):
    """获取指定Agent的AgentCard"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    agent_card = a2a_integration.get_agent_card(agent_id)
    if not agent_card:
        return jsonify({"error": f"Agent {agent_id} not found"}), 404
    
    return jsonify(agent_card.to_dict())


@a2a_bp.route('/agents', methods=['GET'])
def list_agents():
    """列出所有Agent"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    capability = request.args.get('capability')
    agents = a2a_integration.discover_agents_by_capability(capability) if capability else \
             list(a2a_integration.a2a.agent_cards.values())
    
    return jsonify({
        "agents": [card.to_dict() for card in agents],
        "total": len(agents)
    })


# ==================== Task API ====================

@a2a_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建新任务"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('name')
    description = data.get('description', '')
    agent_id = data.get('agent_id')
    parent_task_id = data.get('parent_task_id')
    
    if not name or not agent_id:
        return jsonify({"error": "name and agent_id are required"}), 400
    
    try:
        task = a2a_integration.create_a2a_task(
            name=name,
            description=description,
            agent_id=agent_id,
            parent_task_id=parent_task_id
        )
        
        return jsonify({
            "success": True,
            "task": task.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@a2a_bp.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """获取任务详情"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    task = a2a_integration.a2a.get_task(task_id)
    if not task:
        return jsonify({"error": f"Task {task_id} not found"}), 404
    
    return jsonify(task.to_dict())


@a2a_bp.route('/tasks/<task_id>/state', methods=['PUT'])
def update_task_state(task_id: str):
    """更新任务状态"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    new_state = data.get('state')
    message = data.get('message', '')
    
    if not new_state:
        return jsonify({"error": "state is required"}), 400
    
    try:
        state = TaskState(new_state)
        a2a_integration.a2a.update_task_state(task_id, state, message)
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "new_state": new_state
        })
    
    except ValueError:
        return jsonify({"error": f"Invalid state: {new_state}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@a2a_bp.route('/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    agent_id = request.args.get('agent_id')
    state = request.args.get('state')
    
    tasks = list(a2a_integration.a2a.tasks.values())
    
    # 过滤
    if agent_id:
        tasks = [t for t in tasks if t.agent == agent_id]
    if state:
        tasks = [t for t in tasks if t.state.value == state]
    
    return jsonify({
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks)
    })


# ==================== Message API ====================

@a2a_bp.route('/messages', methods=['POST'])
def send_message():
    """发送消息"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    task_id = data.get('task_id')
    
    if not sender_id or not receiver_id or not content:
        return jsonify({"error": "sender_id, receiver_id, and content are required"}), 400
    
    try:
        message = a2a_integration.send_a2a_message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            task_id=task_id
        )
        
        return jsonify({
            "success": True,
            "message": message.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@a2a_bp.route('/messages/stream', methods=['POST'])
def send_streaming_message():
    """发送流式消息"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    content_parts = data.get('content_parts', [])
    task_id = data.get('task_id')
    
    if not sender_id or not receiver_id:
        return jsonify({"error": "sender_id and receiver_id are required"}), 400
    
    def generate():
        """生成流式响应"""
        for part_data in content_parts:
            part_type = part_data.get('type', 'text')
            content = part_data.get('content', '')
            
            if part_type == 'text':
                part = Part.text(content)
            elif part_type == 'structured':
                part = Part.structured(content)
            else:
                part = Part.text(str(content))
            
            message = a2a_integration.a2a.send_message(
                sender_id=sender_id,
                receiver_id=receiver_id,
                parts=[part],
                task_id=task_id
            )
            
            yield f"data: {json.dumps(message.to_dict())}\n\n"
            time.sleep(0.1)  # 模拟流式延迟
        
        yield "data: [DONE]\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# ==================== Workflow API ====================

@a2a_bp.route('/workflows', methods=['POST'])
def create_workflow():
    """创建工作流"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    workflow_id = data.get('workflow_id')
    name = data.get('name')
    steps = data.get('steps', [])
    
    if not workflow_id or not name:
        return jsonify({"error": "workflow_id and name are required"}), 400
    
    try:
        a2a_integration.workflow.create_workflow(workflow_id, name, steps)
        
        return jsonify({
            "success": True,
            "workflow_id": workflow_id,
            "name": name
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@a2a_bp.route('/workflows/<workflow_id>/execute', methods=['POST'])
def execute_workflow(workflow_id: str):
    """执行工作流"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json() or {}
    
    try:
        task = a2a_integration.workflow.execute_workflow(workflow_id, data)
        
        return jsonify({
            "success": True,
            "task": task.to_dict()
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== Subscription API ====================

@a2a_bp.route('/tasks/<task_id>/subscribe', methods=['POST'])
def subscribe_to_task(task_id: str):
    """订阅任务事件"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json() or {}
    webhook_url = data.get('webhook_url')
    
    def callback(event_type: str, event_data: Dict[str, Any]):
        """事件回调"""
        if webhook_url:
            import requests
            try:
                requests.post(webhook_url, json={
                    "event_type": event_type,
                    "data": event_data,
                    "timestamp": time.time()
                }, timeout=5)
            except Exception as e:
                print(f"[A2A API] Webhook failed: {e}")
    
    try:
        a2a_integration.a2a.subscribe_to_task(task_id, callback)
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Subscribed successfully"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== MCP Tool API ====================

@a2a_bp.route('/tools', methods=['GET'])
def list_tools():
    """列出所有MCP工具"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    capability = request.args.get('capability')
    tools = a2a_integration.mcp.discover_tools(capability)
    
    return jsonify({
        "tools": tools,
        "total": len(tools)
    })


@a2a_bp.route('/tools/<tool_id>/execute', methods=['POST'])
def execute_tool(tool_id: str):
    """执行MCP工具"""
    if not a2a_integration:
        return jsonify({"error": "A2A not initialized"}), 500
    
    data = request.get_json() or {}
    parameters = data.get('parameters', {})
    task_id = data.get('task_id')
    
    try:
        result = a2a_integration.mcp.execute_tool(tool_id, parameters, task_id)
        
        return jsonify({
            "success": True,
            "result": result
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== Authentication ====================

@a2a_bp.route('/auth/token', methods=['POST'])
def get_auth_token():
    """获取认证令牌"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    scheme = data.get('scheme', 'api_key')
    credentials = data.get('credentials', {})
    
    # 这里应该实现真实的认证逻辑
    # 简化处理，返回模拟令牌
    token = f"mock_token_{int(time.time())}"
    
    return jsonify({
        "success": True,
        "token": token,
        "expires_in": 3600
    })


# ==================== Health Check ====================

@a2a_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    if not a2a_integration:
        return jsonify({
            "status": "not_initialized",
            "timestamp": time.time()
        }), 503
    
    return jsonify({
        "status": "healthy",
        "agents_count": len(a2a_integration.a2a.agent_cards),
        "tasks_count": len(a2a_integration.a2a.tasks),
        "timestamp": time.time()
    })


# 错误处理
@a2a_bp.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404


@a2a_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
