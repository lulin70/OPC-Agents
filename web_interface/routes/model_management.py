from flask import Blueprint, request, jsonify

# 创建蓝图
model_bp = Blueprint('model', __name__, url_prefix='/api')

# 注册路由
def register_routes(manager):
    # 获取可用模型
    @model_bp.route('/models')
    def get_models():
        models = manager.get_available_models()
        return jsonify(models)
    
    # 获取模型性能统计
    @model_bp.route('/model_performance')
    def get_model_performance():
        performance = manager.get_model_performance()
        return jsonify(performance)
    
    # 获取模型推荐
    @model_bp.route('/model_recommendation', methods=['POST'])
    def get_model_recommendation():
        data = request.json
        task_type = data.get('task_type', '默认')
        recommendation = manager.get_model_recommendation(task_type)
        return jsonify(recommendation)
    
    # 优化模型选择策略
    @model_bp.route('/optimize_model_selection', methods=['POST'])
    def optimize_model_selection():
        strategy = manager.optimize_model_selection()
        return jsonify({'strategy': strategy, 'message': '模型选择策略优化完成'})
    
    # Agent优化
    @model_bp.route('/optimize_agents', methods=['POST'])
    def optimize_agents():
        data = request.json
        agent_ids = data.get('agent_ids', None)
        iterations = data.get('iterations', 1)
        
        result = manager.optimize_agents(agent_ids, iterations)
        return jsonify(result)
    
    return model_bp