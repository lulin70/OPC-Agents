from flask import Blueprint, request, jsonify
import os
import sys

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


def register_routes(manager):
    @settings_bp.route('/')
    def get_settings():
        config = manager.config
        settings = {
            "models": {},
            "mcp": {},
            "system": {}
        }
        
        models_config = config.get('models', {})
        for model_name in ['glm', 'openai', 'anthropic', 'google', 'local']:
            if model_name in models_config:
                m = models_config[model_name]
                settings["models"][model_name] = {
                    "api_key": m.get('api_key', '')[:8] + '***' if m.get('api_key') else '',
                    "base_url": m.get('base_url', ''),
                    "model": m.get('model', ''),
                    "has_key": bool(m.get('api_key'))
                }
        
        mcp_config = config.get('mcp', {})
        settings["mcp"] = {
            "github_token": mcp_config.get('github_token', '')[:8] + '***' if mcp_config.get('github_token') else '',
            "has_github_token": bool(mcp_config.get('github_token')),
            "agent_sources_count": len(manager.mcp_integration.agent_sources) if manager.mcp_integration else 0,
            "skill_sources_count": len(manager.mcp_integration.skill_sources) if manager.mcp_integration else 0
        }
        
        settings["system"] = {
            "name": config.get('core', {}).get('name', 'OPC Agency'),
            "version": config.get('core', {}).get('version', '1.0.0'),
            "web_port": 5009,
            "python_version": sys.version.split()[0],
            "working_directory": os.getcwd()
        }
        
        return jsonify(settings)
    
    @settings_bp.route('/models', methods=['POST'])
    def update_model_settings():
        data = request.json or {}
        model_name = data.get('model')
        api_key = data.get('api_key')
        base_url = data.get('base_url')
        model = data.get('model_name')
        
        if not model_name:
            return jsonify({"error": "model name is required"}), 400
        
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.toml')
        try:
            with open(config_path, 'r') as f:
                content = f.read()
            
            if api_key:
                import re
                pattern = rf'(\[models\.{model_name}\].*?api_key\s*=\s*)"([^"]*)"'
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    content = content[:match.start(2)] + api_key + content[match.end(2):]
            
            with open(config_path, 'w') as f:
                f.write(content)
            
            return jsonify({"success": True, "message": f"模型 {model_name} 配置已更新"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @settings_bp.route('/mcp', methods=['POST'])
    def update_mcp_settings():
        data = request.json or {}
        github_token = data.get('github_token')
        
        if github_token:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.toml')
            try:
                with open(config_path, 'r') as f:
                    content = f.read()
                
                import re
                pattern = r'(github_token\s*=\s*)"([^"]*)"'
                match = re.search(pattern, content)
                if match:
                    content = content[:match.start(2)] + github_token + content[match.end(2):]
                
                with open(config_path, 'w') as f:
                    f.write(content)
                
                if manager.mcp_integration and manager.mcp_integration.github:
                    from opc_hr.mcp_integration import MCPGitHubClient
                    new_client = MCPGitHubClient(github_token=github_token)
                    manager.mcp_integration.github = new_client
                
                return jsonify({"success": True, "message": "MCP GitHub Token已更新"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"error": "github_token is required"}), 400
    
    @settings_bp.route('/finance/budget', methods=['POST'])
    def update_budget():
        data = request.json or {}
        daily = data.get('daily')
        monthly = data.get('monthly')
        manager.finance_manager.set_budget(daily=daily, monthly=monthly)
        return jsonify({"success": True, "daily_budget": manager.finance_manager.daily_budget, "monthly_budget": manager.finance_manager.monthly_budget})
    
    @settings_bp.route('/test_model', methods=['POST'])
    def test_model():
        data = request.json or {}
        model_name = data.get('model', 'glm')
        test_prompt = data.get('prompt', '你好，请回复"连接成功"')
        
        try:
            from model_integration.model_manager import ModelManager
            mm = ModelManager()
            response = mm.generate_response(test_prompt, model=model_name)
            return jsonify({"success": True, "model": model_name, "response": response})
        except Exception as e:
            return jsonify({"success": False, "model": model_name, "error": str(e)})
    
    return settings_bp
