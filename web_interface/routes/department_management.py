from flask import Blueprint, request, jsonify

# 创建蓝图
dept_bp = Blueprint('department', __name__, url_prefix='/api')

# 注册路由
def register_routes(manager):
    # 获取部门代理
    @dept_bp.route('/department/<department>')
    def get_department_agents(department):
        agents = manager.get_official_agent_by_department(department)
        agent_list = []
        for agent in agents:
            agent_info = {
                'name': agent.get('frontmatter', {}).get('name', agent.get('name')),
                'description': agent.get('frontmatter', {}).get('description', '')
            }
            agent_list.append(agent_info)
        return jsonify(agent_list)
    
    # 获取所有部门
    @dept_bp.route('/departments')
    def get_departments():
        departments = manager.get_departments()
        return jsonify(departments)
    
    # 启动共识过程
    @dept_bp.route('/consensus', methods=['POST'])
    def start_consensus():
        data = request.json
        issue = data.get('issue')
        agents = data.get('agents')
        voting_method = data.get('voting_method', 'majority')
        decision_threshold = data.get('decision_threshold', 0.6)
        
        if not issue or not agents:
            return jsonify({'error': 'Issue and agents are required'}), 400
        
        result = manager.start_consensus(issue, agents, voting_method, decision_threshold)
        return jsonify(result)
    
    # 获取总裁办代理
    @dept_bp.route('/executive_office')
    def get_executive_office():
        agents = manager.get_executive_office_agents()
        return jsonify(agents)
    
    # 获取三贤者
    @dept_bp.route('/three_sages')
    def get_three_sages():
        sages = manager.get_three_sages()
        return jsonify(sages)
    
    # 获取三层架构信息
    @dept_bp.route('/three_layer_architecture')
    def get_three_layer_architecture():
        # 检查manager是否有three_layer_architecture属性
        if hasattr(manager, 'three_layer_architecture'):
            return jsonify(manager.three_layer_architecture)
        else:
            return jsonify({'error': 'Three layer architecture not initialized'}), 500
    
    return dept_bp