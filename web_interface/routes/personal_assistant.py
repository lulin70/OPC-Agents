from flask import Blueprint, request, jsonify

# 创建蓝图
pa_bp = Blueprint('personal_assistant', __name__, url_prefix='/api/personal_assistant')

# 注册路由
def register_routes(manager):
    # 个人助理功能 - 添加待办事项
    @pa_bp.route('/todo', methods=['POST'])
    def add_todo_item():
        data = request.json
        content = data.get('content')
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        
        if not content:
            return jsonify({'error': 'Content is required'}), 400
        
        todo_id = manager.add_todo_item(content, priority, due_date)
        return jsonify({'todo_id': todo_id, 'message': 'Todo item added successfully'})
    
    # 个人助理功能 - 获取待办事项列表
    @pa_bp.route('/todo')
    def get_todo_items():
        status = request.args.get('status')
        todo_items = manager.get_todo_items(status)
        return jsonify(todo_items)
    
    # 个人助理功能 - 更新待办事项状态
    @pa_bp.route('/todo/<todo_id>', methods=['PUT'])
    def update_todo_status(todo_id):
        data = request.json
        status = data.get('status')
        
        if not status:
            return jsonify({'error': 'Status is required'}), 400
        
        success = manager.update_todo_status(todo_id, status)
        if success:
            return jsonify({'message': 'Todo status updated successfully'})
        else:
            return jsonify({'error': 'Todo item not found'}), 404
    
    # 个人助理功能 - 添加兴趣爱好
    @pa_bp.route('/hobby', methods=['POST'])
    def add_hobby():
        data = request.json
        hobby = data.get('hobby')
        description = data.get('description', '')
        
        if not hobby:
            return jsonify({'error': 'Hobby is required'}), 400
        
        hobby_id = manager.add_hobby(hobby, description)
        return jsonify({'hobby_id': hobby_id, 'message': 'Hobby added successfully'})
    
    # 个人助理功能 - 获取兴趣爱好列表
    @pa_bp.route('/hobby')
    def get_hobbies():
        hobbies = manager.get_hobbies()
        return jsonify(hobbies)
    
    # 个人助理功能 - 规划出行
    @pa_bp.route('/trip', methods=['POST'])
    def plan_trip():
        data = request.json
        destination = data.get('destination')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        preferences = data.get('preferences')
        
        if not destination or not start_date or not end_date:
            return jsonify({'error': 'Destination, start_date, and end_date are required'}), 400
        
        trip_plan = manager.plan_trip(destination, start_date, end_date, preferences)
        return jsonify({'trip_plan': trip_plan, 'message': 'Trip planned successfully'})
    
    # 个人助理功能 - 获取出行计划列表
    @pa_bp.route('/trip')
    def get_trip_plans():
        trip_plans = manager.get_trip_plans()
        return jsonify(trip_plans)
    
    # 个人助理功能 - 获取天气信息
    @pa_bp.route('/weather')
    def get_weather():
        location = request.args.get('location')
        
        if not location:
            return jsonify({'error': 'Location is required'}), 400
        
        weather_data = manager.get_weather(location)
        return jsonify(weather_data)
    
    return pa_bp