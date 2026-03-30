from flask import Blueprint, request, jsonify

finance_bp = Blueprint('finance', __name__, url_prefix='/api/finance')


def register_routes(manager):
    @finance_bp.route('/dashboard')
    def get_dashboard():
        return jsonify(manager.finance_manager.get_finance_dashboard())
    
    @finance_bp.route('/token_usage')
    def get_token_usage():
        return jsonify(manager.finance_manager.get_token_usage())
    
    @finance_bp.route('/report')
    def get_report():
        period = request.args.get('period', 'daily')
        if period not in ('daily', 'weekly', 'monthly'):
            return jsonify({"error": "period must be daily/weekly/monthly"}), 400
        return jsonify(manager.finance_manager.get_consumption_report(period))
    
    @finance_bp.route('/alerts')
    def get_alerts():
        return jsonify({"alerts": manager.finance_manager.get_alerts()})
    
    @finance_bp.route('/budget', methods=['POST'])
    def set_budget():
        data = request.json or {}
        daily = data.get('daily')
        monthly = data.get('monthly')
        manager.finance_manager.set_budget(daily=daily, monthly=monthly)
        return jsonify({"success": True, "daily_budget": manager.finance_manager.daily_budget, "monthly_budget": manager.finance_manager.monthly_budget})
    
    return finance_bp
