from flask import Blueprint, request, jsonify

mcp_bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')


def register_routes(manager):
    @mcp_bp.route('/status')
    def get_mcp_status():
        status = manager.get_mcp_status()
        return jsonify(status)

    @mcp_bp.route('/agents/search')
    def search_agents():
        query = request.args.get('q', '')
        department = request.args.get('department', None)
        limit = request.args.get('limit', 10, type=int)
        if not query:
            return jsonify({"error": "请提供搜索关键词 q"}), 400
        results = manager.search_agents_in_mcp(query, department=department, limit=limit)
        return jsonify({"query": query, "department": department, "results": results, "count": len(results)})

    @mcp_bp.route('/agents/<path:repo_full_name>')
    def get_agent_details(repo_full_name):
        details = manager.fetch_agent_details_from_mcp(repo_full_name)
        if not details:
            return jsonify({"error": f"无法获取Agent详情: {repo_full_name}"}), 404
        return jsonify(details)

    @mcp_bp.route('/agents/<path:repo_full_name>/import', methods=['POST'])
    def import_agent(repo_full_name):
        data = request.json or {}
        target_department = data.get('department', None)
        result = manager.import_agent_from_mcp(repo_full_name, target_department=target_department)
        return jsonify(result)

    @mcp_bp.route('/skills/search')
    def search_skills():
        query = request.args.get('q', '')
        category = request.args.get('category', None)
        limit = request.args.get('limit', 10, type=int)
        if not query:
            return jsonify({"error": "请提供搜索关键词 q"}), 400
        results = manager.search_skills_in_mcp(query, category=category, limit=limit)
        return jsonify({"query": query, "category": category, "results": results, "count": len(results)})

    @mcp_bp.route('/skills/<path:repo_full_name>')
    def get_skill_details(repo_full_name):
        details = manager.fetch_skill_details_from_mcp(repo_full_name)
        if not details:
            return jsonify({"error": f"无法获取Skill详情: {repo_full_name}"}), 404
        return jsonify(details)

    @mcp_bp.route('/skills/<path:repo_full_name>/import', methods=['POST'])
    def import_skill(repo_full_name):
        result = manager.import_skill_from_mcp(repo_full_name)
        return jsonify(result)

    @mcp_bp.route('/categories')
    def get_categories():
        categories = manager.get_skill_categories_from_mcp()
        return jsonify({"categories": categories})

    @mcp_bp.route('/history')
    def get_history():
        mcp = manager.mcp_integration
        return jsonify({
            "imports": mcp.get_import_history(),
            "verifications": mcp.get_verification_history()
        })

    return mcp_bp
