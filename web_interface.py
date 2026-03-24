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
    
    if not task_name or not agent:
        return jsonify({'error': 'Task name and agent are required'}), 400
    
    manager.create_task(task_id, task_name, agent, initial_status)
    return jsonify({'task_id': task_id, 'message': 'Task created successfully'})

# 更新任务状态
@app.route('/api/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.json
    status = data.get('status')
    progress = data.get('progress')
    
    if not status:
        return jsonify({'error': 'Status is required'}), 400
    
    manager.update_task_status(task_id, status, progress)
    return jsonify({'message': 'Task updated successfully'})

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

# 分配任务
@app.route('/api/assign_task', methods=['POST'])
def assign_task():
    data = request.json
    task = data.get('task')
    department = data.get('department')
    agent = data.get('agent')
    
    if not task or not department:
        return jsonify({'error': 'Task and department are required'}), 400
    
    result = manager.assign_task(task, department, agent)
    return jsonify({'result': result})

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
</head>
<body>
    <div class="container mt-4">
        <h1 class="text-center mb-4">OPC-Agents 管理系统</h1>
        
        <!-- 部门代理管理 -->
        <div class="card mb-4">
            <div class="card-header">
                <h2>部门代理管理</h2>
            </div>
            <div class="card-body">
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
        </div>
        
        <!-- 任务管理 -->
        <div class="card mb-4">
            <div class="card-header">
                <h2>任务管理</h2>
            </div>
            <div class="card-body">
                <!-- 创建任务 -->
                <div class="mb-4">
                    <h3>创建任务</h3>
                    <form id="create-task-form">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <label for="task-name" class="form-label">任务名称</label>
                                <input type="text" class="form-control" id="task-name" required>
                            </div>
                            <div class="col-md-6">
                                <label for="task-agent" class="form-label">负责代理</label>
                                <input type="text" class="form-control" id="task-agent" required>
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
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 共识管理 -->
        <div class="card mb-4">
            <div class="card-header">
                <h2>共识管理</h2>
            </div>
            <div class="card-body">
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
        </div>
        
        <!-- Token使用情况 -->
        <div class="card mb-4">
            <div class="card-header">
                <h2>Token使用情况</h2>
            </div>
            <div class="card-body">
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
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <button type="button" class="btn btn-primary" id="save-task-update">保存更新</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
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
            
            $.ajax({
                url: '/api/tasks',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ task_name: taskName, agent: agent, status: status }),
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
            
            $.ajax({
                url: `/api/tasks/${taskId}`,
                type: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify({ status: status, progress: progress }),
                success: function(response) {
                    alert('任务更新成功！');
                    location.reload();
                },
                error: function(error) {
                    alert('更新任务失败：' + error.responseJSON.error);
                }
            });
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
    </script>
</body>
</html>
    '''
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)
    
    print("Web界面已启动，访问 http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
