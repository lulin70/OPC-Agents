from flask import Blueprint, request, jsonify

# 创建蓝图
auto_opt_bp = Blueprint('auto_optimizer', __name__, url_prefix='/api/auto_optimizer')

# 注册路由
def register_routes():
    # 自动优化配置
    @auto_opt_bp.route('/config', methods=['GET', 'POST'])
    def auto_optimizer_config():
        from opc_hr.auto_optimizer import AutoOptimizer
        auto_optimizer = AutoOptimizer()
        
        if request.method == 'GET':
            return jsonify(auto_optimizer.config)
        else:
            new_config = request.json
            auto_optimizer.update_config(new_config)
            return jsonify({'message': '配置已更新'})
    
    # 获取自动优化统计
    @auto_opt_bp.route('/statistics')
    def auto_optimizer_statistics():
        from opc_hr.auto_optimizer import AutoOptimizer
        auto_optimizer = AutoOptimizer()
        stats = auto_optimizer.get_optimization_statistics()
        return jsonify(stats)
    
    # 手动触发自动优化
    @auto_opt_bp.route('/run', methods=['POST'])
    def run_auto_optimizer():
        from opc_hr.auto_optimizer import AutoOptimizer
        auto_optimizer = AutoOptimizer()
        result = auto_optimizer.run_optimization()
        return jsonify(result)
    
    return auto_opt_bp