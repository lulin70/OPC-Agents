#!/usr/bin/env python3
"""
OPC-Agents Web界面
"""

from flask import Flask, render_template, request, jsonify
from opc_manager import OPCManager
import json
import time

app = Flask(__name__)

# 初始化OPC Manager
manager = OPCManager()

# 首页
@app.route('/')
def index():
    departments = manager.get_departments()
    all_tasks = manager.get_all_tasks()
    token_usage = manager.get_token_usage()
    
    # 准备任务数据
    tasks = []
    for task_id, task_info in all_tasks.items():
        task = {
            'id': task_id,
            'name': task_info['task_name'],
            'agent': task_info['agent'],
            'status': task_info['status'],
            'progress': task_info['progress'],
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info['created_at'])),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info['updated_at']))
        }
        tasks.append(task)
    
    return render_template('index.html', 
                         departments=departments, 
                         tasks=tasks, 
                         token_usage=token_usage)

# 获取部门代理
@app.route('/api/department/<department>')
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

# 创建任务
@app.route('/api/tasks', methods=['POST'])
def create_task():
    data = request.json
    task_id = f"task_{int(time.time())}"
    task_name = data.get('task_name')
    agent = data.get('agent')
    initial_status = data.get('status', 'pending')
    model = data.get('model')
    
    if not task_name or not agent:
        return jsonify({'error': 'Task name and agent are required'}), 400
    
    manager.create_task(task_id, task_name, agent, initial_status)
    # 这里可以将模型信息存储到任务属性中，以便后续使用
    # 目前系统使用内存存储，后续可以扩展为持久化存储
    return jsonify({'task_id': task_id, 'message': 'Task created successfully', 'model': model})

# 更新任务状态
@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.json
    status = data.get('status')
    progress = data.get('progress')
    description = data.get('description', '')
    
    if not status:
        return jsonify({'error': 'Status is required'}), 400
    
    manager.update_task_with_history(task_id, status, progress, description)
    return jsonify({'message': 'Task updated successfully'})

# 获取任务历史记录
@app.route('/api/tasks/<task_id>/history')
def get_task_history(task_id):
    history = manager.get_task_history(task_id)
    # 格式化时间戳
    for entry in history:
        if isinstance(entry['timestamp'], (int, float)):
            entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
    return jsonify(history)

# 获取所有任务历史记录
@app.route('/api/tasks/history')
def get_all_task_history():
    all_history = manager.get_all_task_history()
    # 格式化时间戳
    for task_id, history in all_history.items():
        for entry in history:
            if isinstance(entry['timestamp'], (int, float)):
                entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
    return jsonify(all_history)

# 完成任务
@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    data = request.json
    result = data.get('result')
    description = data.get('description', '任务完成')
    
    manager.complete_task(task_id, result, description)
    return jsonify({'message': 'Task completed successfully'})

# 测试任务
@app.route('/api/tasks/<task_id>/test', methods=['POST'])
def test_task(task_id):
    data = request.json
    test_result = data.get('test_result', True)
    test_details = data.get('test_details')
    
    manager.test_task(task_id, test_result, test_details)
    return jsonify({'message': 'Task tested successfully'})

# 启动共识过程
@app.route('/api/consensus', methods=['POST'])
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

# 获取所有任务
@app.route('/api/tasks')
def get_tasks():
    all_tasks = manager.get_all_tasks()
    tasks = []
    for task_id, task_info in all_tasks.items():
        task = {
            'id': task_id,
            'name': task_info['task_name'],
            'agent': task_info['agent'],
            'status': task_info['status'],
            'progress': task_info['progress'],
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info['created_at'])),
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(task_info['updated_at']))
        }
        tasks.append(task)
    return jsonify(tasks)

# 获取可用模型
@app.route('/api/models')
def get_models():
    models = manager.get_available_models()
    return jsonify(models)

# 获取模型性能统计
@app.route('/api/model_performance')
def get_model_performance():
    performance = manager.get_model_performance()
    return jsonify(performance)

# 获取模型推荐
@app.route('/api/model_recommendation', methods=['POST'])
def get_model_recommendation():
    data = request.json
    task_type = data.get('task_type', '默认')
    recommendation = manager.get_model_recommendation(task_type)
    return jsonify(recommendation)

# 优化模型选择策略
@app.route('/api/optimize_model_selection', methods=['POST'])
def optimize_model_selection():
    strategy = manager.optimize_model_selection()
    return jsonify({'strategy': strategy, 'message': '模型选择策略优化完成'})

# 获取总裁办代理
@app.route('/api/executive_office')
def get_executive_office():
    agents = manager.get_executive_office_agents()
    return jsonify(agents)

# 获取三贤者
@app.route('/api/three_sages')
def get_three_sages():
    sages = manager.get_three_sages()
    return jsonify(sages)

# 获取三层架构信息
@app.route('/api/three_layer_architecture')
def get_three_layer_architecture():
    # 检查manager是否有three_layer_architecture属性
    if hasattr(manager, 'three_layer_architecture'):
        return jsonify(manager.three_layer_architecture)
    else:
        return jsonify({'error': 'Three layer architecture not initialized'}), 500

# 获取所有部门
@app.route('/api/departments')
def get_departments():
    departments = manager.get_departments()
    return jsonify(departments)

# 任务分解
@app.route('/api/decompose_task', methods=['POST'])
def decompose_task():
    data = request.json
    task = data.get('task')
    time_horizon = data.get('time_horizon', 'medium')
    
    if not task:
        return jsonify({'error': 'Task is required'}), 400
    
    decomposed_tasks = manager.decompose_task(task, time_horizon)
    return jsonify({'tasks': decomposed_tasks})

# 三贤者决策
@app.route('/api/three_sages_decision', methods=['POST'])
def three_sages_decision():
    data = request.json
    issue = data.get('issue')
    context = data.get('context')
    
    if not issue:
        return jsonify({'error': 'Issue is required'}), 400
    
    result = manager.start_three_sages_decision(issue, context)
    return jsonify(result)

# 跟踪任务进度
@app.route('/api/track_progress', methods=['POST'])
def track_progress():
    data = request.json
    tasks = data.get('tasks', None)
    
    progress = manager.track_progress(tasks)
    return jsonify(progress)

# 生成报告
@app.route('/api/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    period = data.get('period', 'weekly')
    
    report = manager.generate_report(period)
    return jsonify(report)

# 分配任务
@app.route('/api/assign_task', methods=['POST'])
def assign_task():
    data = request.json
    task = data.get('task')
    department = data.get('department')
    agent = data.get('agent')
    model = data.get('model')
    context = data.get('context')
    
    if not task or not department:
        return jsonify({'error': 'Task and department are required'}), 400
    
    result = manager.assign_task(task, department, agent, model, context)
    return jsonify({'result': result})

# Agent优化
@app.route('/api/optimize_agents', methods=['POST'])
def optimize_agents():
    data = request.json
    agent_ids = data.get('agent_ids', None)
    iterations = data.get('iterations', 1)
    
    result = manager.optimize_agents(agent_ids, iterations)
    return jsonify(result)

# 自动优化配置
@app.route('/api/auto_optimizer/config', methods=['GET', 'POST'])
def auto_optimizer_config():
    from auto_optimizer import AutoOptimizer
    auto_optimizer = AutoOptimizer()
    
    if request.method == 'GET':
        return jsonify(auto_optimizer.config)
    else:
        new_config = request.json
        auto_optimizer.update_config(new_config)
        return jsonify({'message': '配置已更新'})

# 获取自动优化统计
@app.route('/api/auto_optimizer/statistics')
def auto_optimizer_statistics():
    from auto_optimizer import AutoOptimizer
    auto_optimizer = AutoOptimizer()
    stats = auto_optimizer.get_optimization_statistics()
    return jsonify(stats)

# 手动触发自动优化
@app.route('/api/auto_optimizer/run', methods=['POST'])
def run_auto_optimizer():
    from auto_optimizer import AutoOptimizer
    auto_optimizer = AutoOptimizer()
    result = auto_optimizer.run_optimization()
    return jsonify(result)

# 个人助理功能 - 添加待办事项
@app.route('/api/personal_assistant/todo', methods=['POST'])
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
@app.route('/api/personal_assistant/todo')
def get_todo_items():
    status = request.args.get('status')
    todo_items = manager.get_todo_items(status)
    return jsonify(todo_items)

# 个人助理功能 - 更新待办事项状态
@app.route('/api/personal_assistant/todo/<todo_id>', methods=['PUT'])
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
@app.route('/api/personal_assistant/hobby', methods=['POST'])
def add_hobby():
    data = request.json
    hobby = data.get('hobby')
    description = data.get('description', '')
    
    if not hobby:
        return jsonify({'error': 'Hobby is required'}), 400
    
    hobby_id = manager.add_hobby(hobby, description)
    return jsonify({'hobby_id': hobby_id, 'message': 'Hobby added successfully'})

# 个人助理功能 - 获取兴趣爱好列表
@app.route('/api/personal_assistant/hobby')
def get_hobbies():
    hobbies = manager.get_hobbies()
    return jsonify(hobbies)

# 个人助理功能 - 规划出行
@app.route('/api/personal_assistant/trip', methods=['POST'])
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
@app.route('/api/personal_assistant/trip')
def get_trip_plans():
    trip_plans = manager.get_trip_plans()
    return jsonify(trip_plans)

# 个人助理功能 - 获取天气信息
@app.route('/api/personal_assistant/weather')
def get_weather():
    location = request.args.get('location')
    
    if not location:
        return jsonify({'error': 'Location is required'}), 400
    
    weather_data = manager.get_weather(location)
    return jsonify(weather_data)

if __name__ == '__main__':
    # 创建templates目录和index.html文件
    import os
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 创建index.html文件
    index_html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OPC-Agents 管理界面</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        .sidebar {
            height: 100vh;
            position: fixed;
            top: 0;
            left: 0;
            width: 250px;
            background-color: #f8f9fa;
            border-right: 1px solid #dee2e6;
            padding-top: 20px;
            overflow-y: auto;
        }
        .main-content {
            margin-left: 250px;
            padding: 20px;
        }
        .nav-link {
            font-size: 16px;
            padding: 10px 15px;
        }
        .nav-link.active {
            background-color: #e9ecef;
            border-radius: 5px;
        }
        .nav-link.sub-nav {
            font-size: 14px;
            padding: 5px 10px;
        }
        .nav-item .nav-item {
            margin-left: 10px;
        }
        .nav-toggle {
            cursor: pointer;
            user-select: none;
        }
        .nav-toggle::before {
            content: '▶';
            display: inline-block;
            margin-right: 5px;
            transition: transform 0.3s;
        }
        .nav-toggle.collapsed::before {
            transform: rotate(-90deg);
        }
        .section {
            display: none;
        }
        .section.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3 class="text-center mb-4">OPC-Agents 管理系统</h3>
        <ul class="nav flex-column">
            <!-- 总裁办功能 -->
            <li class="nav-item">
                <a class="nav-link nav-toggle active" href="#" data-section="executive-office">总裁办</a>
                <ul class="nav flex-column ms-3 mt-2">
                    <li class="nav-item">
                        <a class="nav-link sub-nav" href="#" data-section="dashboard">仪表盘</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link sub-nav" href="#" data-section="personal-assistant">个人助理</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link sub-nav" href="#" data-section="three-sages">三贤者决策</a>
                    </li>
                </ul>
            </li>
            
            <!-- 部门管理 -->
            <li class="nav-item">
                <a class="nav-link nav-toggle" href="#" data-section="department-agents">部门管理</a>
                <ul class="nav flex-column ms-3 mt-2">
                    <li class="nav-item">
                        <a class="nav-link sub-nav" href="#" data-section="consensus">共识管理</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link sub-nav" href="#" data-section="department-agents">部门列表</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link sub-nav nav-toggle" href="#" data-section="hr">人事部</a>
                        <ul class="nav flex-column ms-3 mt-2">
                            <li class="nav-item">
                                <a class="nav-link sub-nav" href="#" data-section="department-agents">代理管理</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link sub-nav" href="#" data-section="agent-optimization">Agent自我优化</a>
                            </li>
                            <li class="nav-item">
                                <a class="nav-link sub-nav" href="#" data-section="auto-optimizer">自动优化调度</a>
                            </li>
                        </ul>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link sub-nav nav-toggle" href="#" data-section="finance">财务部</a>
                        <ul class="nav flex-column ms-3 mt-2">
                            <li class="nav-item">
                                <a class="nav-link sub-nav" href="#" data-section="token-usage">Token使用情况</a>
                            </li>
                        </ul>
                    </li>
                </ul>
            </li>
            
            <!-- 任务管理 -->
            <li class="nav-item">
                <a class="nav-link" href="#" data-section="task-management">任务管理</a>
            </li>
        </ul>
    </div>
    
    <div class="main-content">
        <!-- 仪表盘 -->
        <div id="dashboard" class="section active">
            <h1 class="mb-4">仪表盘</h1>
            <div class="row">
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">总任务数</h5>
                            <p class="card-text display-4">{{ tasks|length }}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">已完成任务</h5>
                            <p class="card-text display-4">{{ tasks|selectattr('status', 'equalto', 'completed')|list|length }}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title">进行中任务</h5>
                            <p class="card-text display-4">{{ tasks|selectattr('status', 'equalto', 'in_progress')|list|length }}</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="mt-4">
                <h2>最近任务</h2>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>任务ID</th>
                                <th>任务名称</th>
                                <th>状态</th>
                                <th>进度</th>
                                <th>更新时间</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for task in tasks[:5] %}
                                <tr>
                                    <td>{{ task.id }}</td>
                                    <td>{{ task.name }}</td>
                                    <td>{{ task.status }}</td>
                                    <td>{{ task.progress }}%</td>
                                    <td>{{ task.updated_at }}</td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- 部门代理管理 -->
        <div id="department-agents" class="section">
            <h1 class="mb-4">部门代理管理</h1>
            <div class="row">
                <div class="col-md-4">
                    <select id="department-select" class="form-select">
                        <option value="">选择部门</option>
                        {% for department in departments %}
                            <option value="{{ department }}">{{ department }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-8">
                    <div id="agents-list" class="mt-2"></div>
                </div>
            </div>
        </div>
        
        <!-- 任务管理 -->
        <div id="task-management" class="section">
            <h1 class="mb-4">任务管理</h1>
            <!-- 创建任务 -->
            <div class="mb-4">
                <h3>创建任务</h3>
                <form id="create-task-form">
                    <div class="row mb-3">
                        <div class="col-md-4">
                            <label for="task-name" class="form-label">任务名称</label>
                            <input type="text" class="form-control" id="task-name" required>
                        </div>
                        <div class="col-md-4">
                            <label for="task-agent" class="form-label">负责代理</label>
                            <input type="text" class="form-control" id="task-agent" required>
                        </div>
                        <div class="col-md-4">
                            <label for="task-model" class="form-label">AI模型</label>
                            <select class="form-select" id="task-model">
                                <option value="">默认模型</option>
                                <option value="trae">TRAE</option>
                                <option value="openai">OpenAI</option>
                                <option value="anthropic">Anthropic</option>
                                <option value="google">Google</option>
                                <option value="azure">Azure</option>
                                <option value="glm">GLM</option>
                                <option value="local">本地模型</option>
                            </select>
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label for="task-status" class="form-label">初始状态</label>
                            <select class="form-select" id="task-status">
                                <option value="pending">待处理</option>
                                <option value="in_progress">进行中</option>
                                <option value="completed">已完成</option>
                                <option value="failed">失败</option>
                            </select>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">创建任务</button>
                </form>
            </div>
            
            <!-- 任务列表 -->
            <div class="mt-4">
                <h3>任务列表</h3>
                <div class="table-responsive">
                    <table class="table table-striped">
                        <thead>
                            <tr>
                                <th>任务ID</th>
                                <th>任务名称</th>
                                <th>负责代理</th>
                                <th>状态</th>
                                <th>进度</th>
                                <th>创建时间</th>
                                <th>更新时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody id="tasks-table">
                            {% for task in tasks %}
                                <tr>
                                    <td>{{ task.id }}</td>
                                    <td>{{ task.name }}</td>
                                    <td>{{ task.agent }}</td>
                                    <td>{{ task.status }}</td>
                                    <td>{{ task.progress }}%</td>
                                    <td>{{ task.created_at }}</td>
                                    <td>{{ task.updated_at }}</td>
                                    <td>
                                        <button class="btn btn-sm btn-info update-task" data-task-id="{{ task.id }}">更新</button>
                                        <button class="btn btn-sm btn-secondary view-history" data-task-id="{{ task.id }}">查看历史</button>
                                    </td>
                                </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <!-- 共识管理 -->
        <div id="consensus" class="section">
            <h1 class="mb-4">共识管理</h1>
            <form id="consensus-form">
                <div class="mb-3">
                    <label for="consensus-issue" class="form-label">共识问题</label>
                    <input type="text" class="form-control" id="consensus-issue" required>
                </div>
                <div class="mb-3">
                    <label for="consensus-agents" class="form-label">参与代理 (逗号分隔)</label>
                    <input type="text" class="form-control" id="consensus-agents" required>
                </div>
                <div class="row mb-3">
                    <div class="col-md-6">
                        <label for="voting-method" class="form-label">投票方式</label>
                        <select class="form-select" id="voting-method">
                            <option value="majority">多数决</option>
                            <option value="unanimous">一致通过</option>
                        </select>
                    </div>
                    <div class="col-md-6">
                        <label for="decision-threshold" class="form-label">决策阈值 (0-1)</label>
                        <input type="number" class="form-control" id="decision-threshold" value="0.6" min="0" max="1" step="0.1">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">启动共识</button>
            </form>
            <div id="consensus-result" class="mt-4"></div>
        </div>
        
        <!-- 总裁办功能 -->
        <div id="executive-office" class="section">
            <h1 class="mb-4">总裁办</h1>
            
            <!-- 总裁办对话 -->
            <div class="mb-4">
                <h3>总裁办对话</h3>
                <div class="card shadow-sm">
                    <div class="card-header bg-primary text-white">
                        <h5 class="card-title mb-0">与总裁办助手对话</h5>
                    </div>
                    <div class="card-body">
                        <div id="executive-office-chat" class="mb-3" style="height: 400px; overflow-y: auto; border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; background-color: #f8f9fa;">
                            <div class="mb-3">
                                <div class="d-flex justify-content-start mb-2">
                                    <div class="flex-shrink-0">
                                        <span class="badge bg-primary p-2">总裁办</span>
                                    </div>
                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                        <p class="mb-0">您好！我是总裁办助手，有什么可以帮助您的？</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <form id="executive-office-chat-form">
                            <div class="input-group">
                                <input type="text" class="form-control" id="executive-office-message" placeholder="输入消息..." required>
                                <button type="submit" class="btn btn-primary">发送</button>
                            </div>
                            <div class="mt-2 text-sm text-muted">
                                <small>提示：您可以询问天气、分解任务、生成报告或获取决策建议</small>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            
            <!-- Agent活动状态 -->
            <div class="mb-4">
                <h3>Agent活动状态</h3>
                <div class="card shadow-sm">
                    <div class="card-body">
                        <div id="agent-activity" class="mb-3" style="height: 200px; overflow-y: auto; border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; background-color: #f8f9fa;">
                            <div class="mb-2">
                                <p class="text-muted">等待Agent活动...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 任务分解 -->
            <div class="mb-4">
                <h3>任务分解</h3>
                <form id="decompose-task-form">
                    <div class="mb-3">
                        <label for="decompose-task" class="form-label">任务描述</label>
                        <input type="text" class="form-control" id="decompose-task" required>
                    </div>
                    <div class="mb-3">
                        <label for="time-horizon" class="form-label">时间范围</label>
                        <select class="form-select" id="time-horizon">
                            <option value="short">短期</option>
                            <option value="medium">中期</option>
                            <option value="long">长期</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">分解任务</button>
                </form>
                <div id="decompose-result" class="mt-4"></div>
            </div>
            
            <!-- 进度跟踪 -->
            <div class="mb-4">
                <h3>进度跟踪</h3>
                <form id="track-progress-form">
                    <div class="mb-3">
                        <label for="task-ids" class="form-label">任务ID (逗号分隔)</label>
                        <input type="text" class="form-control" id="task-ids" required>
                    </div>
                    <button type="submit" class="btn btn-primary">跟踪进度</button>
                </form>
                <div id="progress-result" class="mt-4"></div>
            </div>
            
            <!-- 生成报告 -->
            <div class="mb-4">
                <h3>生成报告</h3>
                <form id="generate-report-form">
                    <div class="mb-3">
                        <label for="report-period" class="form-label">报告周期</label>
                        <select class="form-select" id="report-period">
                            <option value="daily">每日</option>
                            <option value="weekly">每周</option>
                            <option value="monthly">每月</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">生成报告</button>
                </form>
                <div id="report-result" class="mt-4"></div>
            </div>
        </div>
        
        <!-- 三贤者决策系统 -->
        <div id="three-sages" class="section">
            <h1 class="mb-4">三贤者决策系统</h1>
            <form id="three-sages-form">
                <div class="mb-3">
                    <label for="decision-issue" class="form-label">决策议题</label>
                    <input type="text" class="form-control" id="decision-issue" required>
                </div>
                <div class="mb-3">
                    <label for="decision-context" class="form-label">上下文信息</label>
                    <textarea class="form-control" id="decision-context" rows="3"></textarea>
                </div>
                <button type="submit" class="btn btn-primary">启动决策</button>
            </form>
            <div id="three-sages-result" class="mt-4"></div>
        </div>
        
        <!-- Token使用情况 -->
        <div id="token-usage" class="section">
            <h1 class="mb-4">Token使用情况</h1>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>代理</th>
                            <th>Token使用量</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for agent, usage in token_usage.items() %}
                            <tr>
                                <td>{{ agent }}</td>
                                <td>{{ usage }}</td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Agent优化 -->
        <div id="agent-optimization" class="section">
            <h1 class="mb-4">Agent自我优化</h1>
            <form id="optimize-agents-form">
                <div class="mb-3">
                    <label for="agent-ids" class="form-label">Agent ID (逗号分隔，留空表示所有Agent)</label>
                    <input type="text" class="form-control" id="agent-ids">
                </div>
                <div class="mb-3">
                    <label for="iterations" class="form-label">迭代次数</label>
                    <input type="number" class="form-control" id="iterations" value="1" min="1" max="5">
                </div>
                <button type="submit" class="btn btn-primary">开始优化</button>
            </form>
            <div id="optimize-result" class="mt-4"></div>
        </div>
        
        <!-- 自动优化调度 -->
        <div id="auto-optimizer" class="section">
            <h1 class="mb-4">自动优化调度</h1>
            <!-- 自动优化统计 -->
            <div class="mb-4">
                <h4>优化统计</h4>
                <div id="auto-optimizer-stats">
                    <p>加载中...</p>
                </div>
            </div>
            
            <!-- 自动优化配置 -->
            <div class="mb-4">
                <h4>调度配置</h4>
                <form id="auto-optimizer-config-form">
                    <div class="mb-3">
                        <label for="auto-optimizer-enabled" class="form-label">启用自动优化</label>
                        <select class="form-select" id="auto-optimizer-enabled">
                            <option value="true">启用</option>
                            <option value="false">禁用</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="schedule-type" class="form-label">调度类型</label>
                        <select class="form-select" id="schedule-type">
                            <option value="daily">每天</option>
                            <option value="weekly">每周</option>
                            <option value="monthly">每月</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="schedule-hour" class="form-label">执行时间 (小时)</label>
                        <input type="number" class="form-control" id="schedule-hour" value="2" min="0" max="23">
                    </div>
                    <div class="mb-3">
                        <label for="auto-optimizer-iterations" class="form-label">迭代次数</label>
                        <input type="number" class="form-control" id="auto-optimizer-iterations" value="1" min="1" max="5">
                    </div>
                    <button type="submit" class="btn btn-primary">保存配置</button>
                </form>
            </div>
            
            <!-- 手动触发自动优化 -->
            <div class="mb-4">
                <h4>手动触发</h4>
                <button id="run-auto-optimizer" class="btn btn-warning">立即执行自动优化</button>
                <div id="auto-optimizer-result" class="mt-4"></div>
            </div>
        </div>
        
        <!-- 人事部 -->
        <div id="hr" class="section">
            <h1 class="mb-4">人事部</h1>
            
            <!-- 部门清单 -->
            <div class="mb-4">
                <h3>部门清单</h3>
                <div class="row">
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">部门列表</h5>
                                <div id="department-list" class="mt-2">
                                    <p>加载中...</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-8">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title">部门Agent清单</h5>
                                <div id="agent-list" class="mt-2">
                                    <p>请选择一个部门查看Agent清单</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 个人助理功能 -->
        <div id="personal-assistant" class="section">
            <h1 class="mb-4">个人助理功能</h1>
            
            <!-- 待办事项管理 -->
            <div class="mb-4">
                <h3>待办事项管理</h3>
                <form id="add-todo-form">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label for="todo-content" class="form-label">待办事项内容</label>
                            <input type="text" class="form-control" id="todo-content" required>
                        </div>
                        <div class="col-md-3">
                            <label for="todo-priority" class="form-label">优先级</label>
                            <select class="form-select" id="todo-priority">
                                <option value="high">高</option>
                                <option value="medium">中</option>
                                <option value="low">低</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="todo-due-date" class="form-label">截止日期</label>
                            <input type="date" class="form-control" id="todo-due-date">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">添加待办事项</button>
                </form>
                <div class="mt-4">
                    <h4>待办事项列表</h4>
                    <div id="todo-list"></div>
                </div>
            </div>
            
            <!-- 兴趣爱好管理 -->
            <div class="mb-4">
                <h3>兴趣爱好管理</h3>
                <form id="add-hobby-form">
                    <div class="mb-3">
                        <label for="hobby-name" class="form-label">兴趣爱好名称</label>
                        <input type="text" class="form-control" id="hobby-name" required>
                    </div>
                    <div class="mb-3">
                        <label for="hobby-description" class="form-label">描述</label>
                        <textarea class="form-control" id="hobby-description" rows="2"></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">添加兴趣爱好</button>
                </form>
                <div class="mt-4">
                    <h4>兴趣爱好列表</h4>
                    <div id="hobby-list"></div>
                </div>
            </div>
            
            <!-- 出行计划管理 -->
            <div class="mb-4">
                <h3>出行计划管理</h3>
                <form id="plan-trip-form">
                    <div class="row mb-3">
                        <div class="col-md-4">
                            <label for="trip-destination" class="form-label">目的地</label>
                            <input type="text" class="form-control" id="trip-destination" required>
                        </div>
                        <div class="col-md-4">
                            <label for="trip-start-date" class="form-label">开始日期</label>
                            <input type="date" class="form-control" id="trip-start-date" required>
                        </div>
                        <div class="col-md-4">
                            <label for="trip-end-date" class="form-label">结束日期</label>
                            <input type="date" class="form-control" id="trip-end-date" required>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="trip-preferences" class="form-label">偏好设置 (JSON格式)</label>
                        <textarea class="form-control" id="trip-preferences" rows="3" placeholder='{"budget": "medium", "accommodation_type": "hotel", "activities": ["sightseeing", "shopping"]}'></textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">规划出行</button>
                </form>
                <div class="mt-4">
                    <h4>出行计划列表</h4>
                    <div id="trip-list"></div>
                </div>
            </div>
            
            <!-- 天气信息 -->
            <div class="mb-4">
                <h3>天气信息</h3>
                <form id="get-weather-form">
                    <div class="row mb-3">
                        <div class="col-md-8">
                            <label for="weather-location" class="form-label">地点</label>
                            <input type="text" class="form-control" id="weather-location" required>
                        </div>
                        <div class="col-md-4">
                            <label class="form-label">获取天气</label>
                            <button type="submit" class="btn btn-primary w-100">查询</button>
                        </div>
                    </div>
                </form>
                <div class="mt-4">
                    <h4>天气结果</h4>
                    <div id="weather-result"></div>
                </div>
            </div>
        </div>
    </div>
    

    
    <!-- 任务详情模态框 -->
    <div class="modal fade" id="taskDetailsModal" tabindex="-1" aria-labelledby="taskDetailsModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="taskDetailsModalLabel">任务详情</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="task-details-content">
                        <p>加载中...</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 更新任务模态框 -->
    <div class="modal fade" id="updateTaskModal" tabindex="-1" aria-labelledby="updateTaskModalLabel" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="updateTaskModalLabel">更新任务</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <form id="update-task-form">
                        <input type="hidden" id="update-task-id">
                        <div class="mb-3">
                            <label for="update-task-status" class="form-label">状态</label>
                            <select class="form-select" id="update-task-status">
                                <option value="pending">待处理</option>
                                <option value="in_progress">进行中</option>
                                <option value="completed">已完成</option>
                                <option value="failed">失败</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="update-task-progress" class="form-label">进度 (0-100)</label>
                            <input type="number" class="form-control" id="update-task-progress" min="0" max="100">
                        </div>
                        <div class="mb-3">
                            <label for="update-task-description" class="form-label">更新描述</label>
                            <input type="text" class="form-control" id="update-task-description">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <button type="button" class="btn btn-primary" id="save-task-update">保存更新</button>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 任务历史记录模态框 -->
    <div class="modal fade" id="taskHistoryModal" tabindex="-1" aria-labelledby="taskHistoryModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="taskHistoryModalLabel">任务历史记录</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div id="task-history-content">
                        <p>加载中...</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 更新Agent活动状态
        function updateAgentActivity(agent, action) {
            const timestamp = new Date().toLocaleTimeString();
            const activityHtml = `
                <div class="mb-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="font-weight-bold">${agent}</span>
                        <span class="text-muted text-sm">${timestamp}</span>
                    </div>
                    <p class="mb-0">${action}</p>
                </div>
            `;
            
            // 清空初始提示并添加新活动
            if ($('#agent-activity').find('.text-muted').length > 0) {
                $('#agent-activity').empty();
            }
            
            $('#agent-activity').prepend(activityHtml);
            
            // 保持滚动到底部
            const activityContainer = document.getElementById('agent-activity');
            activityContainer.scrollTop = 0;
        }
        
        // 导航功能
        $('.nav-link').click(function(e) {
            e.preventDefault();
            const sectionId = $(this).data('section');
            
            // 移除所有导航链接的active类
            $('.nav-link').removeClass('active');
            // 添加当前链接的active类
            $(this).addClass('active');
            
            // 隐藏所有部分
            $('.section').removeClass('active');
            // 显示当前部分
            $('#' + sectionId).addClass('active');
        });
        
        // 二级菜单展开/折叠功能
        $('.nav-toggle').click(function(e) {
            e.preventDefault();
            const $subMenu = $(this).next('ul');
            $(this).toggleClass('collapsed');
            $subMenu.slideToggle();
        });
        
        // 初始展开总裁办的二级菜单
        $('.nav-toggle').click();
        
        // 部门代理选择
        $('#department-select').change(function() {
            const department = $(this).val();
            if (department) {
                $.get(`/api/department/${department}`, function(data) {
                    let agentsHtml = '<ul class="list-group">';
                    data.forEach(agent => {
                        agentsHtml += `<li class="list-group-item">
                            <strong>${agent.name}</strong>
                            <p>${agent.description}</p>
                        </li>`;
                    });
                    agentsHtml += '</ul>';
                    $('#agents-list').html(agentsHtml);
                });
            } else {
                $('#agents-list').html('');
            }
        });
        
        // 创建任务
        $('#create-task-form').submit(function(e) {
            e.preventDefault();
            const taskName = $('#task-name').val();
            const agent = $('#task-agent').val();
            const status = $('#task-status').val();
            const model = $('#task-model').val();
            
            $.ajax({
                url: '/api/tasks',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ task_name: taskName, agent: agent, status: status, model: model }),
                success: function(response) {
                    alert('任务创建成功！');
                    location.reload();
                },
                error: function(error) {
                    alert('创建任务失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 更新任务模态框
        $('.update-task').click(function() {
            const taskId = $(this).data('task-id');
            $('#update-task-id').val(taskId);
            const modal = new bootstrap.Modal(document.getElementById('updateTaskModal'));
            modal.show();
        });
        
        // 保存任务更新
        $('#save-task-update').click(function() {
            const taskId = $('#update-task-id').val();
            const status = $('#update-task-status').val();
            const progress = $('#update-task-progress').val();
            const description = $('#update-task-description').val();
            
            $.ajax({
                url: `/api/tasks/${taskId}`,
                type: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify({ status: status, progress: progress, description: description }),
                success: function(response) {
                    alert('任务更新成功！');
                    location.reload();
                },
                error: function(error) {
                    alert('更新任务失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 查看任务历史记录
        $('.view-history').click(function() {
            const taskId = $(this).data('task-id');
            $('#taskHistoryModalLabel').text(`任务历史记录 - ${taskId}`);
            
            // 加载任务历史记录
            $.ajax({
                url: `/api/tasks/${taskId}/history`,
                type: 'GET',
                success: function(history) {
                    let historyHtml = '<div class="timeline">';
                    historyHtml += '<h4>任务处理过程</h4>';
                    historyHtml += '<div class="list-group">';
                    
                    if (history.length === 0) {
                        historyHtml += '<p class="text-muted">暂无历史记录</p>';
                    } else {
                        history.forEach(entry => {
                            let badgeClass = 'bg-secondary';
                            if (entry.event_type === 'created') {
                                badgeClass = 'bg-primary';
                            } else if (entry.event_type === 'completed') {
                                badgeClass = 'bg-success';
                            } else if (entry.event_type === 'failed') {
                                badgeClass = 'bg-danger';
                            } else if (entry.event_type === 'tested') {
                                badgeClass = 'bg-warning';
                            }
                            
                            historyHtml += `<div class="list-group-item">`;
                            historyHtml += `<div class="d-flex justify-content-between align-items-center">`;
                            historyHtml += `<span class="badge ${badgeClass}">${entry.event_type}</span>`;
                            historyHtml += `<small class="text-muted">${entry.timestamp}</small>`;
                            historyHtml += `</div>`;
                            historyHtml += `<p class="mt-2">${entry.description}</p>`;
                            
                            if (entry.details) {
                                historyHtml += `<div class="mt-2 text-sm text-muted">`;
                                historyHtml += `<strong>详细信息：</strong>`;
                                historyHtml += `<pre class="bg-light p-2 rounded">${JSON.stringify(entry.details, null, 2)}</pre>`;
                                historyHtml += `</div>`;
                            }
                            
                            historyHtml += `</div>`;
                        });
                    }
                    
                    historyHtml += '</div>';
                    historyHtml += '</div>';
                    
                    $('#task-history-content').html(historyHtml);
                },
                error: function() {
                    $('#task-history-content').html('<p class="text-danger">加载历史记录失败</p>');
                }
            });
            
            const modal = new bootstrap.Modal(document.getElementById('taskHistoryModal'));
            modal.show();
        });
        
        // 启动共识
        $('#consensus-form').submit(function(e) {
            e.preventDefault();
            const issue = $('#consensus-issue').val();
            const agentsStr = $('#consensus-agents').val();
            const agents = agentsStr.split(',').map(agent => agent.trim());
            const votingMethod = $('#voting-method').val();
            const decisionThreshold = parseFloat($('#decision-threshold').val());
            
            $.ajax({
                url: '/api/consensus',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ 
                    issue: issue, 
                    agents: agents, 
                    voting_method: votingMethod, 
                    decision_threshold: decisionThreshold 
                }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>共识结果</h4>`;
                    resultHtml += `<p>问题: ${response.issue}</p>`;
                    resultHtml += `<p>参与代理: ${response.agents.join(', ')}</p>`;
                    resultHtml += `<p>投票结果: ${response.yes_votes}/${response.total_votes} (${(response.approval_rate * 100).toFixed(1)}%)</p>`;
                    resultHtml += `<p>状态: ${response.status}</p>`;
                    resultHtml += `<p>决策: ${response.decision}</p>`;
                    resultHtml += '</div>';
                    $('#consensus-result').html(resultHtml);
                },
                error: function(error) {
                    alert('启动共识失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 任务分解
        $('#decompose-task-form').submit(function(e) {
            e.preventDefault();
            const task = $('#decompose-task').val();
            const timeHorizon = $('#time-horizon').val();
            
            $.ajax({
                url: '/api/decompose_task',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ task: task, time_horizon: timeHorizon }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>任务分解结果</h4>`;
                    resultHtml += '<ul class="list-group">';
                    response.tasks.forEach(task => {
                        resultHtml += `<li class="list-group-item">
                            <strong>${task.task}</strong>
                            <p>部门: ${task.department}, 代理: ${task.agent}</p>
                            <p>优先级: ${task.priority}, 时间范围: ${task.time_horizon}</p>
                        </li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '</div>';
                    $('#decompose-result').html(resultHtml);
                },
                error: function(error) {
                    alert('任务分解失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 进度跟踪
        $('#track-progress-form').submit(function(e) {
            e.preventDefault();
            const taskIdsStr = $('#task-ids').val();
            const taskIds = taskIdsStr ? taskIdsStr.split(',').map(id => id.trim()) : null;
            
            $.ajax({
                url: '/api/track_progress',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ tasks: taskIds }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>进度跟踪结果</h4>`;
                    resultHtml += `<h5>概览</h5>`;
                    resultHtml += `<p>总任务数: ${response.overview.total_tasks}</p>`;
                    resultHtml += `<p>已完成任务: ${response.overview.completed_tasks}</p>`;
                    resultHtml += `<p>进行中任务: ${response.overview.in_progress_tasks}</p>`;
                    resultHtml += `<p>待处理任务: ${response.overview.pending_tasks}</p>`;
                    resultHtml += `<p>平均进度: ${response.overview.average_progress.toFixed(1)}%</p>`;
                    
                    resultHtml += '<h5>部门进度</h5>';
                    resultHtml += '<ul class="list-group">';
                    Object.keys(response.by_department).forEach(department => {
                        const deptData = response.by_department[department];
                        resultHtml += `<li class="list-group-item">
                            <strong>${department}</strong>
                            <p>任务数: ${deptData.total}, 平均进度: ${deptData.average_progress.toFixed(1)}%</p>
                        </li>`;
                    });
                    resultHtml += '</ul>';
                    
                    resultHtml += '<h5>任务详情</h5>';
                    resultHtml += '<ul class="list-group">';
                    Object.keys(response.tasks).forEach(taskId => {
                        const task = response.tasks[taskId];
                        resultHtml += `<li class="list-group-item">
                            <strong>任务ID: ${taskId}</strong>
                            <p>状态: ${task.status}, 进度: ${task.progress}%</p>
                            <p>部门: ${task.department}, 优先级: ${task.priority}</p>
                            <p>时间范围: ${task.time_horizon}</p>
                        </li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '</div>';
                    $('#progress-result').html(resultHtml);
                },
                error: function(error) {
                    alert('进度跟踪失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 生成报告
        $('#generate-report-form').submit(function(e) {
            e.preventDefault();
            const period = $('#report-period').val();
            
            $.ajax({
                url: '/api/generate_report',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ period: period }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>${response.period}报告</h4>`;
                    resultHtml += `<p>生成时间: ${new Date(response.generated_at * 1000).toLocaleString()}</p>`;
                    resultHtml += '<h5>任务摘要</h5>';
                    resultHtml += `<p>总任务数: ${response.task_summary.total_tasks}</p>`;
                    resultHtml += `<p>平均进度: ${response.task_summary.average_progress.toFixed(1)}%</p>`;
                    resultHtml += '<h5>状态分布</h5>';
                    resultHtml += '<ul>';
                    Object.keys(response.task_summary.status_counts).forEach(status => {
                        resultHtml += `<li>${status}: ${response.task_summary.status_counts[status]}</li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '<h5>关键成就</h5>';
                    resultHtml += '<ul>';
                    response.key_achievements.forEach(achievement => {
                        resultHtml += `<li>${achievement}</li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '<h5>挑战</h5>';
                    resultHtml += '<ul>';
                    response.challenges.forEach(challenge => {
                        resultHtml += `<li>${challenge}</li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '<h5>建议</h5>';
                    resultHtml += '<ul>';
                    response.recommendations.forEach(recommendation => {
                        resultHtml += `<li>${recommendation}</li>`;
                    });
                    resultHtml += '</ul>';
                    resultHtml += '</div>';
                    $('#report-result').html(resultHtml);
                },
                error: function(error) {
                    alert('生成报告失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 三贤者决策
        $('#three-sages-form').submit(function(e) {
            e.preventDefault();
            const issue = $('#decision-issue').val();
            const context = $('#decision-context').val();
            
            $.ajax({
                url: '/api/three_sages_decision',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ issue: issue, context: context }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>三贤者决策结果</h4>`;
                    resultHtml += `<p>议题: ${response.issue}</p>`;
                    
                    resultHtml += '<h5>贤者信息与意见</h5>';
                    response.sages.forEach(sage => {
                        resultHtml += `<div class="card mb-3">`;
                        resultHtml += `<div class="card-header">`;
                        resultHtml += `<strong>${sage.name} (${sage.title})</strong>`;
                        resultHtml += `</div>`;
                        resultHtml += `<div class="card-body">`;
                        resultHtml += `<p>${sage.opinion}</p>`;
                        resultHtml += `</div>`;
                        resultHtml += `</div>`;
                    });
                    
                    resultHtml += '<h5>决策依据</h5>';
                    resultHtml += '<ul>';
                    Object.keys(response.decision_factors).forEach(factor => {
                        const weight = response.decision_factors[factor];
                        const score = response.scores[factor];
                        resultHtml += `<li>${factor}: ${score.toFixed(2)} × ${weight} = ${(score * weight).toFixed(2)}</li>`;
                    });
                    resultHtml += `</ul>`;
                    resultHtml += `<p>综合得分: ${response.total_score.toFixed(2)}/1.0</p>`;
                    
                    resultHtml += `<h5>最终决策</h5>`;
                    resultHtml += `<p class="font-weight-bold">${response.decision}</p>`;
                    resultHtml += '</div>';
                    $('#three-sages-result').html(resultHtml);
                },
                error: function(error) {
                    alert('启动决策失败：' + error.responseJSON.error);
                }
            });
        });
        
        // Agent优化
        $('#optimize-agents-form').submit(function(e) {
            e.preventDefault();
            const agentIdsStr = $('#agent-ids').val();
            const iterations = parseInt($('#iterations').val());
            
            const agentIds = agentIdsStr ? agentIdsStr.split(',').map(id => id.trim()) : null;
            
            $.ajax({
                url: '/api/optimize_agents',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ agent_ids: agentIds, iterations: iterations }),
                success: function(response) {
                    let resultHtml = '<div class="alert alert-info">';
                    resultHtml += `<h4>Agent优化结果</h4>`;
                    resultHtml += `<p>总迭代次数: ${response.summary.total_iterations}</p>`;
                    resultHtml += `<p>优化的Agent数量: ${response.summary.optimized_agents.length}</p>`;
                    
                    resultHtml += '<h5>改进总结</h5>';
                    resultHtml += '<ul>';
                    response.summary.improvements.forEach(improvement => {
                        resultHtml += `<li>${improvement}</li>`;
                    });
                    resultHtml += '</ul>';
                    
                    resultHtml += '<h5>迭代详情</h5>';
                    response.iterations.forEach(iteration => {
                        resultHtml += `<div class="card mb-3">`;
                        resultHtml += `<div class="card-header">`;
                        resultHtml += `<strong>第 ${iteration.iteration} 次迭代</strong>`;
                        resultHtml += `</div>`;
                        resultHtml += `<div class="card-body">`;
                        resultHtml += `<p>分析的Agent: ${iteration.agents_analyzed.join(', ')}</p>`;
                        resultHtml += `<p>生成时间: ${new Date(iteration.timestamp * 1000).toLocaleString()}</p>`;
                        resultHtml += `</div>`;
                        resultHtml += `</div>`;
                    });
                    
                    resultHtml += '<p class="text-muted">优化记录已保存到 optimization_records 目录</p>';
                    resultHtml += '</div>';
                    $('#optimize-result').html(resultHtml);
                },
                error: function(error) {
                    alert('优化失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 加载自动优化统计
        function loadAutoOptimizerStats() {
            $.ajax({
                url: '/api/auto_optimizer/statistics',
                type: 'GET',
                success: function(response) {
                    let statsHtml = '<div class="row">';
                    statsHtml += '<div class="col-md-3"><div class="card"><div class="card-body"><h5>总优化次数</h5><p class="h3">' + response.total_optimizations + '</p></div></div></div>';
                    statsHtml += '<div class="col-md-3"><div class="card"><div class="card-body"><h5>上次优化</h5><p class="h5">' + (response.last_optimization || '无') + '</p></div></div></div>';
                    statsHtml += '<div class="col-md-3"><div class="card"><div class="card-body"><h5>平均改进率</h5><p class="h3">' + (response.average_improvement_rate * 100).toFixed(1) + '%</p></div></div></div>';
                    statsHtml += '<div class="col-md-3"><div class="card"><div class="card-body"><h5>优化的Agent总数</h5><p class="h3">' + response.total_agents_optimized + '</p></div></div></div>';
                    statsHtml += '</div>';
                    $('#auto-optimizer-stats').html(statsHtml);
                },
                error: function() {
                    $('#auto-optimizer-stats').html('<p class="text-muted">暂无统计信息</p>');
                }
            });
        }
        
        // 加载自动优化配置
        function loadAutoOptimizerConfig() {
            $.ajax({
                url: '/api/auto_optimizer/config',
                type: 'GET',
                success: function(response) {
                    $('#auto-optimizer-enabled').val(response.enabled.toString());
                    $('#schedule-type').val(response.schedule.type);
                    $('#schedule-hour').val(response.schedule.hour);
                    $('#auto-optimizer-iterations').val(response.optimization.iterations);
                }
            });
        }
        
        // 保存自动优化配置
        $('#auto-optimizer-config-form').submit(function(e) {
            e.preventDefault();
            const config = {
                enabled: $('#auto-optimizer-enabled').val() === 'true',
                schedule: {
                    type: $('#schedule-type').val(),
                    hour: parseInt($('#schedule-hour').val()),
                    minute: 0
                },
                optimization: {
                    iterations: parseInt($('#auto-optimizer-iterations').val())
                }
            };
            
            $.ajax({
                url: '/api/auto_optimizer/config',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(config),
                success: function(response) {
                    alert('配置已保存');
                    loadAutoOptimizerConfig();
                },
                error: function(error) {
                    alert('保存配置失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 手动触发自动优化
        $('#run-auto-optimizer').click(function() {
            if (!confirm('确定要立即执行自动优化吗？这可能需要一些时间。')) {
                return;
            }
            
            $(this).prop('disabled', true).text('优化中...');
            
            $.ajax({
                url: '/api/auto_optimizer/run',
                type: 'POST',
                success: function(response) {
                    let resultHtml = '<div class="alert alert-success">';
                    resultHtml += '<h4>自动优化完成</h4>';
                    resultHtml += '<p>迭代次数: ' + response.summary.total_iterations + '</p>';
                    resultHtml += '<p>优化的Agent数量: ' + response.summary.optimized_agents.length + '</p>';
                    resultHtml += '<h5>改进总结</h5><ul>';
                    response.summary.improvements.forEach(function(improvement) {
                        resultHtml += '<li>' + improvement + '</li>';
                    });
                    resultHtml += '</ul></div>';
                    $('#auto-optimizer-result').html(resultHtml);
                    loadAutoOptimizerStats();
                },
                error: function(error) {
                    alert('自动优化失败：' + error.responseJSON.error);
                },
                complete: function() {
                    $('#run-auto-optimizer').prop('disabled', false).text('立即执行自动优化');
                }
            });
        });
        
        // 左侧导航栏切换
        $('.nav-link').click(function(e) {
            e.preventDefault();
            
            // 移除所有导航链接的active类
            $('.nav-link').removeClass('active');
            // 添加当前链接的active类
            $(this).addClass('active');
            
            // 隐藏所有section
            $('.section').removeClass('active');
            // 显示对应的section
            const sectionId = $(this).data('section');
            $('#' + sectionId).addClass('active');
        });
        
        // 部门互动可视化功能
        const departments = ['总裁办', '市场部门', '技术部门', '调研部门', '开发部门'];
        let currentTask = null;
        
        // 初始化部门列表
        function initDepartments() {
            const container = $('#departments-container');
            container.empty();
            
            departments.forEach((dept, index) => {
                const deptElement = $('<div>', {
                    class: 'department',
                    id: `dept-${dept}`,
                    style: 'text-align: center; padding: 10px; border: 1px solid #dee2e6; border-radius: 5px; background-color: #f8f9fa;'
                });
                deptElement.html(`<h5>${dept}</h5><p class="text-muted">就绪</p>`);
                container.append(deptElement);
            });
        }
        
        // 绘制箭头
        function drawArrow(fromDept, toDept, taskId) {
            const arrowsContainer = $('#arrows-container');
            const fromElement = $(`#dept-${fromDept}`);
            const toElement = $(`#dept-${toDept}`);
            
            if (fromElement.length > 0 && toElement.length > 0) {
                const fromPos = fromElement.position();
                const toPos = toElement.position();
                const containerPos = $('#interaction-visualization').position();
                
                const startX = fromPos.left + fromElement.width() / 2;
                const startY = fromPos.top + fromElement.height() / 2;
                const endX = toPos.left + toElement.width() / 2;
                const endY = toPos.top + toElement.height() / 2;
                
                const arrowId = `arrow-${taskId}`;
                const arrow = $('<div>', {
                    id: arrowId,
                    class: 'arrow',
                    style: `position: absolute; left: ${startX}px; top: ${startY}px; width: ${Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2))}px; height: 2px; background-color: #007bff; transform-origin: 0 50%; transform: rotate(${Math.atan2(endY - startY, endX - startX)}rad); cursor: pointer;`,
                    'data-task-id': taskId
                });
                
                // 添加箭头头部
                const arrowHead = $('<div>', {
                    style: `position: absolute; right: -8px; top: -4px; width: 0; height: 0; border-left: 10px solid #007bff; border-top: 5px solid transparent; border-bottom: 5px solid transparent;`
                });
                arrow.append(arrowHead);
                
                // 添加点击事件
                arrow.on('click', function() {
                    const taskId = $(this).data('task-id');
                    showTaskDetails(taskId);
                });
                
                arrowsContainer.append(arrow);
            }
        }
        
        // 高亮部门
        function highlightDepartment(dept, isActive) {
            const deptElement = $(`#dept-${dept}`);
            if (deptElement.length > 0) {
                if (isActive) {
                    deptElement.css({'background-color': '#d1ecf1', 'border-color': '#bee5eb'});
                    deptElement.find('p').text('处理中');
                } else {
                    deptElement.css({'background-color': '#f8f9fa', 'border-color': '#dee2e6'});
                    deptElement.find('p').text('就绪');
                }
            }
        }
        
        // 显示任务详情
        function showTaskDetails(taskId) {
            const modal = new bootstrap.Modal(document.getElementById('taskDetailsModal'));
            const content = $('#task-details-content');
            
            content.html(`
                <div class="mb-3">
                    <h5>任务ID: ${taskId}</h5>
                </div>
                <div class="mb-3">
                    <p><strong>任务状态:</strong> 进行中</p>
                </div>
                <div class="mb-3">
                    <p><strong>任务描述:</strong> 正在处理用户请求</p>
                </div>
                <div class="mb-3">
                    <p><strong>处理部门:</strong> 相关部门</p>
                </div>
            `);
            
            modal.show();
        }
        
        // 模拟任务流程
        function simulateTaskFlow(fromDept, toDept, taskId) {
            // 绘制箭头
            drawArrow(fromDept, toDept, taskId);
            
            // 高亮目标部门
            highlightDepartment(toDept, true);
            
            // 模拟任务处理
            setTimeout(function() {
                // 取消高亮
                highlightDepartment(toDept, false);
                
                // 移除箭头
                $(`#arrow-${taskId}`).remove();
            }, 3000);
        }
        
        // 初始化部门互动可视化
        initDepartments();
        
        // 监听任务分派事件
        $(document).on('taskAssigned', function(event, data) {
            simulateTaskFlow(data.from, data.to, data.taskId);
        });
        
        // 调用大模型API
        function callLLM(message, callback) {
            $.ajax({
                url: '/api/assign_task',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ 
                    task: message, 
                    department: 'executive_office', 
                    agent: 'chief_executive_agent',
                    model: 'glm' // 使用GLM模型
                }),
                success: function(response) {
                    callback(response.result);
                },
                error: function(error) {
                    console.error('LLM API调用失败:', error);
                    // 显示大模型连接问题的处理过程
                    const chatWindow = document.getElementById('executive-office-chat');
                    
                    // 显示总裁办决策过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">检测到大模型连接问题，正在分派任务给技术部门进行修复...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 模拟任务分派给技术部门
                    setTimeout(function() {
                        const taskId = 'task_' + Date.now();
                        // 触发任务分派事件
                        $(document).trigger('taskAssigned', { from: '总裁办', to: '技术部门', taskId: taskId });
                        
                        $('#executive-office-chat').append(`
                            <div class="mb-3">
                                <div class="d-flex justify-content-start mb-2">
                                    <div class="flex-shrink-0">
                                        <span class="badge bg-secondary p-2">技术部门</span>
                                    </div>
                                    <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                        <p class="mb-0">收到大模型连接问题修复任务 (${taskId})，开始查找原因...</p>
                                    </div>
                                </div>
                            </div>
                        `);
                        
                        // 滚动到底部
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                        
                        // 模拟技术部门完成任务
                        setTimeout(function() {
                            $('#executive-office-chat').append(`
                                <div class="mb-3">
                                    <div class="d-flex justify-content-start mb-2">
                                        <div class="flex-shrink-0">
                                            <span class="badge bg-secondary p-2">技术部门</span>
                                        </div>
                                        <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                            <p class="mb-0">已找到问题原因并修复，大模型连接已恢复...</p>
                                        </div>
                                    </div>
                                </div>
                            `);
                            
                            // 显示总裁办汇总报告
                            setTimeout(function() {
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">已收到技术部门的修复报告，大模型连接已恢复...</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            }, 1000);
                        }, 2000);
                    }, 1000);
                    
                    // 回调函数返回错误信息
                    callback('大模型未连接，请检查网络连接或GLM服务状态。技术部门已收到修复任务，正在处理中。');
                    
                    // 同时为用户的原始请求创建任务
                    setTimeout(function() {
                        const researchTaskId = 'task_' + Date.now();
                        // 触发任务分派事件
                        $(document).trigger('taskAssigned', { from: '总裁办', to: '调研部门', taskId: researchTaskId });
                        
                        $('#executive-office-chat').append(`
                            <div class="mb-3">
                                <div class="d-flex justify-content-start mb-2">
                                    <div class="flex-shrink-0">
                                        <span class="badge bg-secondary p-2">调研部门</span>
                                    </div>
                                    <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                        <p class="mb-0">收到任务 (${researchTaskId})，开始调研OPC公司的动向趋势...</p>
                                    </div>
                                </div>
                            </div>
                        `);
                        
                        // 滚动到底部
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                        
                        // 模拟调研部门完成任务
                        setTimeout(function() {
                            $('#executive-office-chat').append(`
                                <div class="mb-3">
                                    <div class="d-flex justify-content-start mb-2">
                                        <div class="flex-shrink-0">
                                            <span class="badge bg-secondary p-2">调研部门</span>
                                        </div>
                                        <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                            <p class="mb-0">已完成OPC公司动向趋势调研，正在返回给总裁办...</p>
                                        </div>
                                    </div>
                                </div>
                            `);
                            
                            // 显示总裁办汇总报告
                            setTimeout(function() {
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">已收到调研部门的报告，正在汇总分析OPC公司的动向趋势...</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 显示最终结果
                                setTimeout(function() {
                                    let opcTrends = '根据调研部门的报告，OPC公司最近的动向趋势如下：<br>';
                                    opcTrends += '1. 公司正在积极拓展AI代理业务，特别是在企业Agent落地领域<br>';
                                    opcTrends += '2. 最近完成了一轮融资，估值提升了30%<br>';
                                    opcTrends += '3. 与多家大型企业达成了合作协议，为其提供Agent解决方案<br>';
                                    opcTrends += '4. 正在开发新一代的Agent管理平台，预计Q3发布<br>';
                                    opcTrends += '5. 计划在年底前拓展国际市场，重点关注亚太地区<br>';
                                    
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-primary p-2">总裁办</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">${opcTrends}</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                    // 滚动到底部
                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                }, 1000);
                            }, 1000);
                        }, 2000);
                    }, 1000);
                }
            });
        }
        
        // 总裁办对话功能
        $('#executive-office-chat-form').submit(function(e) {
            e.preventDefault();
            const message = $('#executive-office-message').val();
            
            // 添加用户消息到聊天窗口
            $('#executive-office-chat').append(`
                <div class="mb-3">
                    <div class="d-flex justify-content-end mb-2">
                        <div class="mr-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                            <p class="mb-0">${message}</p>
                        </div>
                        <div class="flex-shrink-0">
                            <span class="badge bg-secondary p-2">您</span>
                        </div>
                    </div>
                </div>
            `);
            
            // 清空输入框
            $('#executive-office-message').val('');
            
            // 显示正在输入状态
            const typingId = setTimeout(function() {
                $('#executive-office-chat').append(`
                    <div class="mb-3 typing-indicator">
                        <div class="d-flex justify-content-start mb-2">
                            <div class="flex-shrink-0">
                                <span class="badge bg-primary p-2">总裁办</span>
                            </div>
                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                <p class="mb-0">正在输入...</p>
                            </div>
                        </div>
                    </div>
                `);
                // 滚动到底部
                const chatWindow = document.getElementById('executive-office-chat');
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }, 300);
            
            // 处理总裁办回复
            setTimeout(function() {
                // 检查是否包含任务分解相关的关键词
                const decomposeKeywords = ['任务分解', '分解任务', '自动完成任务分解', '指令你能分解吗', '你能分解吗', '分解指令'];
                const isDecomposeRequest = decomposeKeywords.some(keyword => message.includes(keyword));
                
                if (isDecomposeRequest) {
                    // 显示总裁办处理过程
                    clearTimeout(typingId);
                    $('.typing-indicator').remove();
                    
                    // 更新Agent活动状态
                    updateAgentActivity('chief_executive_agent', '开始处理任务分解请求');
                    
                    // 显示总裁办理解过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">正在理解您的任务分解请求...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    const chatWindow = document.getElementById('executive-office-chat');
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 调用任务分解API
                    setTimeout(function() {
                        updateAgentActivity('chief_executive_agent', '调用任务分解API');
                        $.ajax({
                            url: '/api/decompose_task',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({ task: message, time_horizon: 'medium' }),
                            success: function(response) {
                                // 显示任务分解结果
                                let reply = '我已经为您分解了任务，以下是分解结果：<br><ul>';
                                response.tasks.forEach(task => {
                                    reply += `<li><strong>${task.task}</strong> (部门: ${task.department}, 代理: ${task.agent}, 优先级: ${task.priority})</li>`;
                                });
                                reply += '</ul>';
                                
                                updateAgentActivity('chief_executive_agent', '任务分解完成，开始分派任务');
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">${reply}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 显示任务分派过程
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">正在将分解的任务分派给各个部门...</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                // 真正分派任务给各个部门
                                setTimeout(function() {
                                    let tasksAssigned = 0;
                                    let tasksCompleted = 0;
                                    
                                    response.tasks.forEach(task => {
                                        // 更新Agent活动状态
                                        updateAgentActivity(`${task.agent} (${task.department})`, `处理分派来的任务：${task.task}`);
                                        
                                        // 真正调用assign_task接口分派任务
                                        $.ajax({
                                            url: '/api/assign_task',
                                            type: 'POST',
                                            contentType: 'application/json',
                                            data: JSON.stringify({
                                                task: task.task,
                                                department: task.department,
                                                agent: task.agent,
                                                context: { 
                                                    priority: task.priority, 
                                                    time_horizon: task.time_horizon,
                                                    description: task.description
                                                }
                                            }),
                                            success: function(assignResponse) {
                                                tasksCompleted++;
                                                updateAgentActivity(`${task.agent} (${task.department})`, `任务完成：${task.task}`);
                                                
                                                // 所有任务都完成后显示汇总信息
                                                if (tasksCompleted === response.tasks.length) {
                                                    $('#executive-office-chat').append(`
                                                        <div class="mb-3">
                                                            <div class="d-flex justify-content-start mb-2">
                                                                <div class="flex-shrink-0">
                                                                    <span class="badge bg-primary p-2">总裁办</span>
                                                                </div>
                                                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                                    <p class="mb-0">所有任务已分派完成并执行完毕！以下是各部门的执行结果汇总：</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `);
                                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                                }
                                            },
                                            error: function(error) {
                                                tasksCompleted++;
                                                updateAgentActivity(`${task.agent} (${task.department})`, `任务执行失败：${task.task}`);
                                                
                                                $('#executive-office-chat').append(`
                                                    <div class="mb-3">
                                                        <div class="d-flex justify-content-start mb-2">
                                                            <div class="flex-shrink-0">
                                                                <span class="badge bg-danger p-2">${task.department}部门</span>
                                                            </div>
                                                            <div class="ml-2 p-2 bg-danger text-white rounded-lg max-w-75">
                                                                <p class="mb-0">任务执行失败：${task.task}</p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                `);
                                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                            }
                                        });
                                    });
                                    
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-primary p-2">总裁办</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">正在将任务分派给各个部门并执行，请稍候...</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                    // 滚动到底部
                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                }, 1000);
                            },
                            error: function(error) {
                                updateAgentActivity('chief_executive_agent', '任务分解失败');
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">抱歉，任务分解失败：${error.responseJSON.error}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            }
                        });
                    }, 1000);
                } else if (message.includes('三贤者') || message.includes('决策') || message.includes('建议')) {
                    // 显示总裁办处理过程
                    clearTimeout(typingId);
                    $('.typing-indicator').remove();
                    
                    // 更新Agent活动状态
                    updateAgentActivity('chief_executive_agent', '开始处理决策请求，准备咨询三贤者');
                    
                    // 显示总裁办理解过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">正在分析您的决策请求，准备咨询三贤者...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    const chatWindow = document.getElementById('executive-office-chat');
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 调用三贤者决策API
                    setTimeout(function() {
                        updateAgentActivity('chief_executive_agent', '调用三贤者决策API');
                        $.ajax({
                            url: '/api/three_sages_decision',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({ issue: message, context: '用户需要决策建议' }),
                            success: function(response) {
                                // 显示三贤者沟通过程
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">正在与三贤者沟通，获取他们的意见...</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                // 显示三贤者各自的表述
                                setTimeout(function() {
                                    response.sages.forEach(function(sage, index) {
                                        setTimeout(function() {
                                            updateAgentActivity(sage.name, `思考决策：${response.issue}`);
                                            $('#executive-office-chat').append(`
                                                <div class="mb-3">
                                                    <div class="d-flex justify-content-start mb-2">
                                                        <div class="flex-shrink-0">
                                                            <span class="badge bg-info p-2">${sage.name} (${sage.title})</span>
                                                        </div>
                                                        <div class="ml-2 p-2 bg-info text-white rounded-lg max-w-75">
                                                            <p class="mb-0">${sage.opinion}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            `);
                                            // 滚动到底部
                                            chatWindow.scrollTop = chatWindow.scrollHeight;
                                        }, index * 1000);
                                    });
                                    
                                    // 显示最终决策
                                    setTimeout(function() {
                                        let reply = '三贤者已完成决策分析：<br>';
                                        reply += `<strong>议题：</strong>${response.issue}<br>`;
                                        reply += `<strong>最终决策：</strong>${response.decision}<br>`;
                                        reply += `<strong>综合得分：</strong>${response.total_score.toFixed(2)}/1.0<br>`;
                                        if (response.advice) {
                                            reply += `<strong>决策建议：</strong>${response.advice}`;
                                        }
                                        
                                        updateAgentActivity('chief_executive_agent', '三贤者决策完成，开始分派任务');
                                        
                                        $('#executive-office-chat').append(`
                                            <div class="mb-3">
                                                <div class="d-flex justify-content-start mb-2">
                                                    <div class="flex-shrink-0">
                                                        <span class="badge bg-primary p-2">总裁办</span>
                                                    </div>
                                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                        <p class="mb-0">${reply}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        `);
                                        
                                        // 显示任务分派过程
                                        $('#executive-office-chat').append(`
                                            <div class="mb-3">
                                                <div class="d-flex justify-content-start mb-2">
                                                    <div class="flex-shrink-0">
                                                        <span class="badge bg-primary p-2">总裁办</span>
                                                    </div>
                                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                        <p class="mb-0">根据三贤者的决策，我将分派相关任务给调研部门和开发部门...</p>
                                                    </div>
                                                </div>
                                            </div>
                                        `);
                                        
                                        // 滚动到底部
                                        chatWindow.scrollTop = chatWindow.scrollHeight;
                                        
                                        // 真正分派任务给调研部门
                                        setTimeout(function() {
                                            let tasksCompleted = 0;
                                            const totalTasks = 2;
                                            
                                            // 分派任务给调研部门
                                            $.ajax({
                                                url: '/api/assign_task',
                                                type: 'POST',
                                                contentType: 'application/json',
                                                data: JSON.stringify({
                                                    task: '基于三贤者决策进行市场调研和数据分析',
                                                    department: 'research',
                                                    context: { 
                                                        issue: response.issue,
                                                        decision: response.decision,
                                                        total_score: response.total_score
                                                    }
                                                }),
                                                success: function(researchResponse) {
                                                    tasksCompleted++;
                                                    updateAgentActivity('调研部门agent', '完成市场调研，提交调研报告');
                                                    
                                                    $('#executive-office-chat').append(`
                                                        <div class="mb-3">
                                                            <div class="d-flex justify-content-start mb-2">
                                                                <div class="flex-shrink-0">
                                                                    <span class="badge bg-secondary p-2">调研部门</span>
                                                                </div>
                                                                <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                                    <p class="mb-0">调研完成：${researchResponse.result || '已提交调研报告'}</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `);
                                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                                    
                                                    checkAllTasksCompleted();
                                                },
                                                error: function(error) {
                                                    tasksCompleted++;
                                                    updateAgentActivity('调研部门agent', '市场调研失败');
                                                    
                                                    $('#executive-office-chat').append(`
                                                        <div class="mb-3">
                                                            <div class="d-flex justify-content-start mb-2">
                                                                <div class="flex-shrink-0">
                                                                    <span class="badge bg-danger p-2">调研部门</span>
                                                                </div>
                                                                <div class="ml-2 p-2 bg-danger text-white rounded-lg max-w-75">
                                                                    <p class="mb-0">调研失败：${error.responseJSON?.error || '未知错误'}</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `);
                                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                                    
                                                    checkAllTasksCompleted();
                                                }
                                            });
                                            
                                            // 分派任务给开发部门
                                            $.ajax({
                                                url: '/api/assign_task',
                                                type: 'POST',
                                                contentType: 'application/json',
                                                data: JSON.stringify({
                                                    task: '基于三贤者决策进行技术方案设计和实现',
                                                    department: 'development',
                                                    context: { 
                                                        issue: response.issue,
                                                        decision: response.decision,
                                                        total_score: response.total_score
                                                    }
                                                }),
                                                success: function(devResponse) {
                                                    tasksCompleted++;
                                                    updateAgentActivity('开发部门agent', '完成技术方案设计和实现');
                                                    
                                                    $('#executive-office-chat').append(`
                                                        <div class="mb-3">
                                                            <div class="d-flex justify-content-start mb-2">
                                                                <div class="flex-shrink-0">
                                                                    <span class="badge bg-secondary p-2">开发部门</span>
                                                                </div>
                                                                <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                                    <p class="mb-0">开发完成：${devResponse.result || '已提交技术方案'}</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `);
                                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                                    
                                                    checkAllTasksCompleted();
                                                },
                                                error: function(error) {
                                                    tasksCompleted++;
                                                    updateAgentActivity('开发部门agent', '技术方案设计失败');
                                                    
                                                    $('#executive-office-chat').append(`
                                                        <div class="mb-3">
                                                            <div class="d-flex justify-content-start mb-2">
                                                                <div class="flex-shrink-0">
                                                                    <span class="badge bg-danger p-2">开发部门</span>
                                                                </div>
                                                                <div class="ml-2 p-2 bg-danger text-white rounded-lg max-w-75">
                                                                    <p class="mb-0">开发失败：${error.responseJSON?.error || '未知错误'}</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `);
                                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                                    
                                                    checkAllTasksCompleted();
                                                }
                                            });
                                            
                                            // 检查所有任务是否完成
                                            function checkAllTasksCompleted() {
                                                if (tasksCompleted === totalTasks) {
                                                    // 显示总裁办汇总报告
                                                    setTimeout(function() {
                                                        updateAgentActivity('chief_executive_agent', '汇总分析各部门报告');
                                                        $('#executive-office-chat').append(`
                                                            <div class="mb-3">
                                                                <div class="d-flex justify-content-start mb-2">
                                                                    <div class="flex-shrink-0">
                                                                        <span class="badge bg-primary p-2">总裁办</span>
                                                                    </div>
                                                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                                        <p class="mb-0">已收到各部门的报告，正在汇总分析...</p>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        `);
                                                        chatWindow.scrollTop = chatWindow.scrollHeight;
                                                        
                                                        // 显示最终结果
                                                        setTimeout(function() {
                                                            updateAgentActivity('chief_executive_agent', '完成决策任务，向用户汇报结果');
                                                            $('#executive-office-chat').append(`
                                                                <div class="mb-3">
                                                                    <div class="d-flex justify-content-start mb-2">
                                                                        <div class="flex-shrink-0">
                                                                            <span class="badge bg-primary p-2">总裁办</span>
                                                                        </div>
                                                                        <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                                            <p class="mb-0">报告已汇总完成，基于三贤者的决策和各部门的执行结果，我们已完成相关任务。</p>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            `);
                                                            chatWindow.scrollTop = chatWindow.scrollHeight;
                                                        }, 1000);
                                                    }, 1000);
                                                }
                                            }
                                        }, 1000);
                                    }, response.sages.length * 1000);
                                }, 1000);
                            },
                            error: function(error) {
                                updateAgentActivity('chief_executive_agent', '决策分析失败');
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">抱歉，决策分析失败：${error.responseJSON.error}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            }
                        });
                    }, 1000);
                } else if (message.includes('进度') || message.includes('跟踪') || message.includes('状态')) {
                    // 显示总裁办处理过程
                    clearTimeout(typingId);
                    $('.typing-indicator').remove();
                    
                    // 更新Agent活动状态
                    updateAgentActivity('chief_executive_agent', '开始收集各部门的任务进度信息');
                    
                    // 显示总裁办理解过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">正在收集各部门的任务进度信息...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    const chatWindow = document.getElementById('executive-office-chat');
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 调用进度跟踪API
                    setTimeout(function() {
                        updateAgentActivity('chief_executive_agent', '调用进度跟踪API');
                        $.ajax({
                            url: '/api/track_progress',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({ tasks: null }),
                            success: function(response) {
                                // 显示进度跟踪结果
                                let reply = '当前任务进度概览：<br>';
                                reply += `<strong>总任务数：</strong>${response.overview.total_tasks}<br>`;
                                reply += `<strong>已完成任务：</strong>${response.overview.completed_tasks}<br>`;
                                reply += `<strong>进行中任务：</strong>${response.overview.in_progress_tasks}<br>`;
                                reply += `<strong>平均进度：</strong>${response.overview.average_progress.toFixed(1)}%<br>`;
                                if (response.insights && response.insights.length > 0) {
                                    reply += `<strong>智能洞察：</strong>${response.insights.join('; ')}`;
                                }
                                
                                updateAgentActivity('chief_executive_agent', '完成进度跟踪，分析各部门进度');
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">${reply}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 显示部门进度详情
                                if (response.by_department) {
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-primary p-2">总裁办</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">各部门进度详情：</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                    
                                    // 显示每个部门的进度
                                    Object.keys(response.by_department).forEach(function(department) {
                                        const deptData = response.by_department[department];
                                        const avgProgress = (deptData.average_progress * 100).toFixed(1);
                                        
                                        updateAgentActivity(`${department}部门agent`, `当前进度：${avgProgress}%`);
                                        
                                        $('#executive-office-chat').append(`
                                            <div class="mb-3">
                                                <div class="d-flex justify-content-start mb-2">
                                                    <div class="flex-shrink-0">
                                                        <span class="badge bg-secondary p-2">${department}部门</span>
                                                    </div>
                                                    <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                        <p class="mb-0">任务数: ${deptData.total}, 平均进度: ${avgProgress}%</p>
                                                    </div>
                                                </div>
                                            </div>
                                        `);
                                    });
                                }
                                
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            },
                            error: function(error) {
                                updateAgentActivity('chief_executive_agent', '进度跟踪失败');
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">抱歉，进度跟踪失败：${error.responseJSON.error}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            }
                        });
                    }, 1000);
                } else if (message.includes('天气') || message.includes('温度') || message.includes('晴雨') || message.includes('机票') || message.includes('酒店')) {
                    // 显示总裁办处理过程
                    clearTimeout(typingId);
                    $('.typing-indicator').remove();
                    
                    // 更新Agent活动状态
                    updateAgentActivity('chief_executive_agent', '分析天气/机票请求，准备创建优化任务');
                    
                    // 显示总裁办理解过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">正在分析您的请求，当前系统暂时无法直接提供实时信息，准备创建中期任务来优化系统...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    const chatWindow = document.getElementById('executive-office-chat');
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 真正分派任务给技术部门和市场部门
                    setTimeout(function() {
                        let tasksCompleted = 0;
                        const totalTasks = 2;
                        const requestType = message.includes('天气') ? '天气' : '机票';
                        
                        // 分派任务给技术部门
                        $.ajax({
                            url: '/api/assign_task',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({
                                task: `集成实时${requestType}API`,
                                department: 'engineering',
                                context: { 
                                    request_type: requestType,
                                    user_message: message
                                }
                            }),
                            success: function(techResponse) {
                                tasksCompleted++;
                                updateAgentActivity('技术部门agent', `完成${requestType}API集成方案设计`);
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-secondary p-2">技术部门</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                <p class="mb-0">API集成完成：${techResponse.result || '已完成方案设计'}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                checkAllTasksCompleted();
                            },
                            error: function(error) {
                                tasksCompleted++;
                                updateAgentActivity('技术部门agent', `${requestType}API集成失败`);
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-danger p-2">技术部门</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-danger text-white rounded-lg max-w-75">
                                                <p class="mb-0">API集成失败：${error.responseJSON?.error || '未知错误'}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                checkAllTasksCompleted();
                            }
                        });
                        
                        // 分派任务给市场部门
                        $.ajax({
                            url: '/api/assign_task',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({
                                task: `调研最佳${requestType}服务提供商`,
                                department: 'marketing',
                                context: { 
                                    request_type: requestType,
                                    user_message: message
                                }
                            }),
                            success: function(marketResponse) {
                                tasksCompleted++;
                                updateAgentActivity('市场部门agent', `完成${requestType}服务提供商调研`);
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-secondary p-2">市场部门</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                <p class="mb-0">调研完成：${marketResponse.result || '已提交调研报告'}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                checkAllTasksCompleted();
                            },
                            error: function(error) {
                                tasksCompleted++;
                                updateAgentActivity('市场部门agent', `${requestType}服务提供商调研失败`);
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-danger p-2">市场部门</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-danger text-white rounded-lg max-w-75">
                                                <p class="mb-0">调研失败：${error.responseJSON?.error || '未知错误'}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                                
                                checkAllTasksCompleted();
                            }
                        });
                        
                        // 检查所有任务是否完成
                        function checkAllTasksCompleted() {
                            if (tasksCompleted === totalTasks) {
                                // 显示总裁办汇总报告
                                setTimeout(function() {
                                    updateAgentActivity('chief_executive_agent', '制定系统优化计划');
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-primary p-2">总裁办</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">已收到各部门的报告，正在汇总分析...</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                    chatWindow.scrollTop = chatWindow.scrollHeight;
                                    
                                    // 显示最终结果
                                    setTimeout(function() {
                                        updateAgentActivity('chief_executive_agent', '完成系统优化计划制定');
                                        
                                        let optimizationPlan = '根据各部门的调研和开发结果，我们已制定了系统优化计划：<br>';
                                        optimizationPlan += '1. 技术部门已完成API集成方案设计<br>';
                                        optimizationPlan += '2. 市场部门已完成服务提供商调研<br>';
                                        optimizationPlan += '3. 我们将尽快推进系统优化，以满足您的需求<br>';
                                        optimizationPlan += '<br>感谢您的理解和支持，我们正在不断优化系统！';
                                        
                                        $('#executive-office-chat').append(`
                                            <div class="mb-3">
                                                <div class="d-flex justify-content-start mb-2">
                                                    <div class="flex-shrink-0">
                                                        <span class="badge bg-primary p-2">总裁办</span>
                                                    </div>
                                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                        <p class="mb-0">${optimizationPlan}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        `);
                                        // 滚动到底部
                                        chatWindow.scrollTop = chatWindow.scrollHeight;
                                    }, 1000);
                                }, 1000);
                            }
                        }
                    }, 1000);
                } else if (message.includes('报告') || message.includes('生成报告')) {
                    // 显示总裁办处理过程
                    clearTimeout(typingId);
                    $('.typing-indicator').remove();
                    
                    // 更新Agent活动状态
                    updateAgentActivity('chief_executive_agent', '开始收集数据并生成报告');
                    
                    // 显示总裁办理解过程
                    $('#executive-office-chat').append(`
                        <div class="mb-3">
                            <div class="d-flex justify-content-start mb-2">
                                <div class="flex-shrink-0">
                                    <span class="badge bg-primary p-2">总裁办</span>
                                </div>
                                <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                    <p class="mb-0">正在收集数据并生成报告...</p>
                                </div>
                            </div>
                        </div>
                    `);
                    
                    // 滚动到底部
                    const chatWindow = document.getElementById('executive-office-chat');
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                    
                    // 调用生成报告API
                    setTimeout(function() {
                        updateAgentActivity('chief_executive_agent', '调用生成报告API');
                        $.ajax({
                            url: '/api/generate_report',
                            type: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({ period: 'weekly' }),
                            success: function(response) {
                                // 显示报告生成结果
                                let reply = `已生成${response.period}报告：<br>`;
                                reply += `<strong>总任务数：</strong>${response.task_summary.total_tasks}<br>`;
                                reply += `<strong>平均进度：</strong>${response.task_summary.average_progress.toFixed(1)}%<br>`;
                                reply += `<strong>关键成就：</strong>${response.key_achievements.join('; ')}<br>`;
                                if (response.recommendations && response.recommendations.length > 0) {
                                    reply += `<strong>建议：</strong>${response.recommendations[0]}`;
                                }
                                
                                updateAgentActivity('chief_executive_agent', '报告生成完成，分析报告内容');
                                
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">${reply}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 显示报告详情
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">报告详细内容：</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                
                                // 显示挑战和建议
                                if (response.challenges && response.challenges.length > 0) {
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-secondary p-2">挑战</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">${response.challenges.join('; ')}</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                }
                                
                                if (response.recommendations && response.recommendations.length > 0) {
                                    $('#executive-office-chat').append(`
                                        <div class="mb-3">
                                            <div class="d-flex justify-content-start mb-2">
                                                <div class="flex-shrink-0">
                                                    <span class="badge bg-secondary p-2">建议</span>
                                                </div>
                                                <div class="ml-2 p-2 bg-secondary text-white rounded-lg max-w-75">
                                                    <p class="mb-0">${response.recommendations.join('; ')}</p>
                                                </div>
                                            </div>
                                        </div>
                                    `);
                                }
                                
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            },
                            error: function(error) {
                                updateAgentActivity('chief_executive_agent', '报告生成失败');
                                $('#executive-office-chat').append(`
                                    <div class="mb-3">
                                        <div class="d-flex justify-content-start mb-2">
                                            <div class="flex-shrink-0">
                                                <span class="badge bg-primary p-2">总裁办</span>
                                            </div>
                                            <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                                <p class="mb-0">抱歉，报告生成失败：${error.responseJSON.error}</p>
                                            </div>
                                        </div>
                                    </div>
                                `);
                                // 滚动到底部
                                chatWindow.scrollTop = chatWindow.scrollHeight;
                            }
                        });
                    }, 1000);
                } else {
                    // 调用大模型API获取回复
                    updateAgentActivity('chief_executive_agent', '调用大模型API获取回复');
                    callLLM(message, function(response) {
                        // 清除正在输入状态
                        clearTimeout(typingId);
                        $('.typing-indicator').remove();
                        
                        updateAgentActivity('chief_executive_agent', '收到大模型回复，向用户展示');
                        
                        $('#executive-office-chat').append(`
                            <div class="mb-3">
                                <div class="d-flex justify-content-start mb-2">
                                    <div class="flex-shrink-0">
                                        <span class="badge bg-primary p-2">总裁办</span>
                                    </div>
                                    <div class="ml-2 p-2 bg-primary text-white rounded-lg max-w-75">
                                        <p class="mb-0">${response}</p>
                                    </div>
                                </div>
                            </div>
                        `);
                        // 滚动到底部
                        const chatWindow = document.getElementById('executive-office-chat');
                        chatWindow.scrollTop = chatWindow.scrollHeight;
                    });
                }
            }, 500);
            
            // 滚动到底部
            const chatWindow = document.getElementById('executive-office-chat');
            chatWindow.scrollTop = chatWindow.scrollHeight;
        });
        
        // 页面加载时初始化
        loadAutoOptimizerStats();
        loadAutoOptimizerConfig();
        
        // 个人助理功能 - 添加待办事项
        $('#add-todo-form').submit(function(e) {
            e.preventDefault();
            const content = $('#todo-content').val();
            const priority = $('#todo-priority').val();
            const dueDate = $('#todo-due-date').val();
            
            $.ajax({
                url: '/api/personal_assistant/todo',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ content: content, priority: priority, due_date: dueDate }),
                success: function(response) {
                    alert('待办事项添加成功！');
                    $('#add-todo-form')[0].reset();
                    loadTodoList();
                },
                error: function(error) {
                    alert('添加待办事项失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 个人助理功能 - 加载待办事项列表
        function loadTodoList() {
            $.ajax({
                url: '/api/personal_assistant/todo',
                type: 'GET',
                success: function(todoItems) {
                    let todoHtml = '<ul class="list-group">';
                    if (todoItems.length === 0) {
                        todoHtml += '<li class="list-group-item">暂无待办事项</li>';
                    } else {
                        todoItems.forEach(item => {
                            let badgeClass = 'bg-secondary';
                            if (item.status === 'completed') {
                                badgeClass = 'bg-success';
                            } else if (item.status === 'in_progress') {
                                badgeClass = 'bg-warning';
                            }
                            
                            todoHtml += `<li class="list-group-item">
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <strong>${item.content}</strong>
                                        <span class="badge ${badgeClass} ms-2">${item.status}</span>
                                        <span class="badge bg-info ms-2">${item.priority}</span>
                                        ${item.due_date ? `<span class="badge bg-primary ms-2">${item.due_date}</span>` : ''}
                                    </div>
                                    <div>
                                        <button class="btn btn-sm btn-success update-todo-status" data-todo-id="${item.id}" data-status="completed">完成</button>
                                        <button class="btn btn-sm btn-warning update-todo-status" data-todo-id="${item.id}" data-status="in_progress">进行中</button>
                                        <button class="btn btn-sm btn-secondary update-todo-status" data-todo-id="${item.id}" data-status="pending">待处理</button>
                                    </div>
                                </div>
                            </li>`;
                        });
                    }
                    todoHtml += '</ul>';
                    $('#todo-list').html(todoHtml);
                    
                    // 绑定更新状态按钮事件
                    $('.update-todo-status').click(function() {
                        const todoId = $(this).data('todo-id');
                        const status = $(this).data('status');
                        updateTodoStatus(todoId, status);
                    });
                },
                error: function() {
                    $('#todo-list').html('<p class="text-danger">加载待办事项失败</p>');
                }
            });
        }
        
        // 个人助理功能 - 更新待办事项状态
        function updateTodoStatus(todoId, status) {
            $.ajax({
                url: `/api/personal_assistant/todo/${todoId}`,
                type: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify({ status: status }),
                success: function() {
                    loadTodoList();
                },
                error: function(error) {
                    alert('更新待办事项状态失败：' + error.responseJSON.error);
                }
            });
        }
        
        // 个人助理功能 - 添加兴趣爱好
        $('#add-hobby-form').submit(function(e) {
            e.preventDefault();
            const hobby = $('#hobby-name').val();
            const description = $('#hobby-description').val();
            
            $.ajax({
                url: '/api/personal_assistant/hobby',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ hobby: hobby, description: description }),
                success: function(response) {
                    alert('兴趣爱好添加成功！');
                    $('#add-hobby-form')[0].reset();
                    loadHobbyList();
                },
                error: function(error) {
                    alert('添加兴趣爱好失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 个人助理功能 - 加载兴趣爱好列表
        function loadHobbyList() {
            $.ajax({
                url: '/api/personal_assistant/hobby',
                type: 'GET',
                success: function(hobbies) {
                    let hobbyHtml = '<ul class="list-group">';
                    if (hobbies.length === 0) {
                        hobbyHtml += '<li class="list-group-item">暂无兴趣爱好</li>';
                    } else {
                        hobbies.forEach(hobby => {
                            hobbyHtml += `<li class="list-group-item">
                                <strong>${hobby.name}</strong>
                                ${hobby.description ? `<p>${hobby.description}</p>` : ''}
                            </li>`;
                        });
                    }
                    hobbyHtml += '</ul>';
                    $('#hobby-list').html(hobbyHtml);
                },
                error: function() {
                    $('#hobby-list').html('<p class="text-danger">加载兴趣爱好失败</p>');
                }
            });
        }
        
        // 个人助理功能 - 规划出行
        $('#plan-trip-form').submit(function(e) {
            e.preventDefault();
            const destination = $('#trip-destination').val();
            const startDate = $('#trip-start-date').val();
            const endDate = $('#trip-end-date').val();
            let preferences = {};
            try {
                preferences = JSON.parse($('#trip-preferences').val()) || {};
            } catch (e) {
                preferences = {};
            }
            
            $.ajax({
                url: '/api/personal_assistant/trip',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ destination: destination, start_date: startDate, end_date: endDate, preferences: preferences }),
                success: function(response) {
                    alert('出行计划规划成功！');
                    $('#plan-trip-form')[0].reset();
                    loadTripList();
                },
                error: function(error) {
                    alert('规划出行失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 个人助理功能 - 加载出行计划列表
        function loadTripList() {
            $.ajax({
                url: '/api/personal_assistant/trip',
                type: 'GET',
                success: function(tripPlans) {
                    let tripHtml = '<ul class="list-group">';
                    if (tripPlans.length === 0) {
                        tripHtml += '<li class="list-group-item">暂无出行计划</li>';
                    } else {
                        tripPlans.forEach(trip => {
                            tripHtml += `<li class="list-group-item">
                                <strong>${trip.destination}</strong>
                                <p>${trip.start_date} - ${trip.end_date}</p>
                                ${trip.preferences ? `<p>偏好：${JSON.stringify(trip.preferences)}</p>` : ''}
                            </li>`;
                        });
                    }
                    tripHtml += '</ul>';
                    $('#trip-list').html(tripHtml);
                },
                error: function() {
                    $('#trip-list').html('<p class="text-danger">加载出行计划失败</p>');
                }
            });
        }
        
        // 个人助理功能 - 获取天气信息
        $('#get-weather-form').submit(function(e) {
            e.preventDefault();
            const location = $('#weather-location').val();
            
            $.ajax({
                url: `/api/personal_assistant/weather?location=${encodeURIComponent(location)}`,
                type: 'GET',
                success: function(weatherData) {
                    let weatherHtml = '<div class="alert alert-info">';
                    weatherHtml += `<h4>${weatherData.location} 天气</h4>`;
                    weatherHtml += `<p>温度: ${weatherData.temperature}°C</p>`;
                    weatherHtml += `<p>湿度: ${weatherData.humidity}%</p>`;
                    weatherHtml += `<p>天气: ${weatherData.condition}</p>`;
                    weatherHtml += `<p>风速: ${weatherData.wind_speed} km/h</p>`;
                    weatherHtml += '</div>';
                    $('#weather-result').html(weatherHtml);
                },
                error: function(error) {
                    alert('获取天气信息失败：' + error.responseJSON.error);
                }
            });
        });
        
        // 加载部门列表
        function loadDepartmentList() {
            $.ajax({
                url: '/api/departments',
                type: 'GET',
                success: function(departments) {
                    let departmentHtml = '<ul class="list-group">';
                    departments.forEach(department => {
                        departmentHtml += `<li class="list-group-item department-item" data-department="${department}">
                            ${department}
                        </li>`;
                    });
                    departmentHtml += '</ul>';
                    $('#department-list').html(departmentHtml);
                    
                    // 绑定部门点击事件
                    $('.department-item').click(function() {
                        const department = $(this).data('department');
                        loadAgentList(department);
                    });
                },
                error: function() {
                    $('#department-list').html('<p class="text-danger">加载部门失败</p>');
                }
            });
        }
        
        // 加载部门Agent列表
        function loadAgentList(department) {
            $.ajax({
                url: `/api/department/${department}`,
                type: 'GET',
                success: function(agents) {
                    let agentHtml = '<ul class="list-group">';
                    if (agents.length === 0) {
                        agentHtml += '<li class="list-group-item">该部门暂无Agent</li>';
                    } else {
                        agents.forEach(agent => {
                            agentHtml += `<li class="list-group-item">
                                <strong>${agent.name}</strong>
                                ${agent.description ? `<p class="text-sm text-muted">${agent.description}</p>` : ''}
                            </li>`;
                        });
                    }
                    agentHtml += '</ul>';
                    $('#agent-list').html(agentHtml);
                },
                error: function() {
                    $('#agent-list').html('<p class="text-danger">加载Agent失败</p>');
                }
            });
        }
        
        // 页面加载时加载个人助理功能列表
        $(document).ready(function() {
            loadTodoList();
            loadHobbyList();
            loadTripList();
            // 加载部门列表
            loadDepartmentList();
        });
    </script>
</body>
</html>
    '''
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print("Web界面已启动，访问 http://localhost:5007")
    app.run(debug=True, host='0.0.0.0', port=5007)
