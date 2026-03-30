from flask import Blueprint, request, jsonify
import time

# 创建蓝图
agent_bp = Blueprint('agent', __name__, url_prefix='/api/agents')

# 注册路由
def register_routes(manager):
    # 获取所有代理
    @agent_bp.route('/')
    def get_all_agents():
        agents = manager.get_all_agents()
        return jsonify(agents)
    
    # 获取指定代理
    @agent_bp.route('/<agent_name>')
    def get_agent(agent_name):
        agent = manager.get_agent(agent_name)
        if agent:
            return jsonify(agent)
        return jsonify({'error': 'Agent not found'}), 404
    
    # 创建代理
    @agent_bp.route('/', methods=['POST'])
    def create_agent():
        data = request.json
        agent_name = data.get('name')
        agent_type = data.get('type', 'general')
        expertise = data.get('expertise', 'general')
        
        if not agent_name:
            return jsonify({'error': 'Agent name is required'}), 400
        
        try:
            manager.create_agent(agent_name, agent_type, expertise)
            return jsonify({'success': True, 'agent_name': agent_name})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # 更新代理
    @agent_bp.route('/<agent_name>', methods=['PUT'])
    def update_agent(agent_name):
        data = request.json
        agent_type = data.get('type')
        expertise = data.get('expertise')
        
        try:
            manager.update_agent(agent_name, agent_type, expertise)
            return jsonify({'success': True, 'agent_name': agent_name})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # 删除代理
    @agent_bp.route('/<agent_name>', methods=['DELETE'])
    def delete_agent(agent_name):
        try:
            manager.delete_agent(agent_name)
            return jsonify({'success': True, 'agent_name': agent_name})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # 获取代理活动状态
    @agent_bp.route('/activity')
    def get_agent_activity():
        activity = manager.get_agent_activity()
        return jsonify(activity)
    
    # 分配任务给代理
    @agent_bp.route('/<agent_name>/assign_task', methods=['POST'])
    def assign_task_to_agent(agent_name):
        data = request.json
        task_name = data.get('task_name')
        task_description = data.get('task_description')
        
        if not task_name:
            return jsonify({'error': 'Task name is required'}), 400
        
        try:
            task_id = manager.create_task(f"task-{agent_name}-{int(time.time())}", task_name, agent_name, "pending")
            return jsonify({'success': True, 'task_id': task_id, 'agent_name': agent_name})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return agent_bp