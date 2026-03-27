#!/usr/bin/env python3
"""
OPC-Agents Web Interface Application
"""

from flask import Flask, render_template
from opc_manager import OPCManager
import argparse
import os
import logging
import time

# 解析命令行参数
parser = argparse.ArgumentParser(description='OPC-Agents Web Interface')
parser.add_argument('--debug', action='store_true', help='Run in debug mode')
parser.add_argument('--gateway-pid', type=int, help='ZeroClaw Gateway process ID')
args = parser.parse_args()

# 存储gateway pid
gateway_pid = args.gateway_pid

# 自动配对功能
def auto_pair():
    """自动从gateway.log文件中读取配对码并更新config.toml文件"""
    import re
    
    # gateway.log文件路径
    gateway_log_path = "/Users/lin/zeroclaw/gateway.log"
    config_path = "config.toml"
    
    if not os.path.exists(gateway_log_path):
        print("[自动配对] gateway.log文件不存在")
        return False
    
    try:
        # 读取gateway.log文件
        with open(gateway_log_path, 'r') as f:
            log_content = f.read()
        
        # 搜索配对码
        match = re.search(r'Pairing code: (\w+)', log_content)
        if match:
            pairing_code = match.group(1)
            print(f"[自动配对] 找到配对码: {pairing_code}")
            
            # 读取config.toml文件
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_content = f.read()
                
                # 更新配对码
                new_config_content = re.sub(r'pairing_code\s*=\s*"[^"]*"', f'pairing_code = "{pairing_code}"', config_content)
                
                # 写入更新后的配置
                with open(config_path, 'w') as f:
                    f.write(new_config_content)
                
                print("[自动配对] 配对码已更新到config.toml文件")
                return True
            else:
                print("[自动配对] config.toml文件不存在")
                return False
        else:
            print("[自动配对] 未找到配对码")
            return False
    except Exception as e:
        print(f"[自动配对] 错误: {e}")
        return False

# 执行自动配对
if gateway_pid:
    print(f"[Web界面] 收到Gateway PID: {gateway_pid}")
    # 等待一段时间让gateway生成配对码
    import time
    time.sleep(5)
    auto_pair()

# 初始化OPC Manager
manager = OPCManager(debug_mode=args.debug)

# 创建Flask应用
app = Flask(__name__)

# 设置debug模式
log_level = logging.DEBUG if args.debug else logging.INFO
for handler in logging.getLogger().handlers:
    handler.setLevel(log_level)

# 注册路由模块
from web_interface.routes.executive_office import register_routes as register_executive_office_routes
from web_interface.routes.task_management import register_routes as register_task_routes
from web_interface.routes.department_management import register_routes as register_dept_routes
from web_interface.routes.personal_assistant import register_routes as register_pa_routes
from web_interface.routes.model_management import register_routes as register_model_routes
from web_interface.routes.auto_optimizer import register_routes as register_auto_opt_routes

# 注册各模块路由
try:
    exec_office_bp = register_executive_office_routes(manager)
    app.register_blueprint(exec_office_bp)
    
    task_bp = register_task_routes(manager)
    app.register_blueprint(task_bp)
    
    dept_bp = register_dept_routes(manager)
    app.register_blueprint(dept_bp)
    
    pa_bp = register_pa_routes(manager)
    app.register_blueprint(pa_bp)
    
    model_bp = register_model_routes(manager)
    app.register_blueprint(model_bp)
    
    auto_opt_bp = register_auto_opt_routes()
    app.register_blueprint(auto_opt_bp)
    
    print("[Web界面] 路由蓝图已加载")
except Exception as e:
    print(f"[Web界面] 路由蓝图加载失败: {e}")

# 初始化A2A API
try:
    from opc_hr.a2a_api import a2a_bp, init_a2a_api
    init_a2a_api(manager)
    app.register_blueprint(a2a_bp)
    print("[Web界面] A2A API已加载")
except Exception as e:
    print(f"[Web界面] A2A API加载失败: {e}")

# 初始化HR增强API
try:
    from opc_hr.hr_api import hr_bp, init_hr_api
    init_hr_api(manager)
    app.register_blueprint(hr_bp)
    print("[Web界面] HR API已加载")
except Exception as e:
    print(f"[Web界面] HR API加载失败: {e}")

# 首页 - 对话中心
@app.route('/')
def index():
    # 获取所有任务
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
    
    # 获取所有部门
    departments = manager.get_departments()
    
    # 获取Token使用情况
    token_usage = manager.get_token_usage()
    
    return render_template('index.html', tasks=tasks, departments=departments, token_usage=token_usage)

if __name__ == '__main__':
    # 创建templates目录
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 只有当index.html文件不存在时才创建
    if not os.path.exists('templates/index.html'):
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
        </div>
    </div>
    
    <script>
        // 页面加载完成后初始化
        $(document).ready(function() {
            // 导航切换
            $('.nav-link').click(function(e) {
                e.preventDefault();
                
                // 移除所有active类
                $('.nav-link').removeClass('active');
                $(this).addClass('active');
                
                // 显示对应的section
                var section = $(this).data('section');
                $('.section').removeClass('active');
                $('#' + section).addClass('active');
            });
            
            // 导航折叠/展开
            $('.nav-toggle').click(function(e) {
                e.preventDefault();
                $(this).toggleClass('collapsed');
                $(this).next('ul').toggle();
            });
            
            // 部门选择
            $('#department-select').change(function() {
                var department = $(this).val();
                if (department) {
                    $.get('/api/department/' + department, function(data) {
                        var html = '<ul class="list-group">';
                        data.forEach(function(agent) {
                            html += '<li class="list-group-item">' + agent.name + '<br><small class="text-muted">' + agent.description + '</small></li>';
                        });
                        html += '</ul>';
                        $('#agents-list').html(html);
                    });
                } else {
                    $('#agents-list').html('');
                }
            });
            
            // 创建任务
            $('#create-task-form').submit(function(e) {
                e.preventDefault();
                var task_name = $('#task-name').val();
                var task_agent = $('#task-agent').val();
                var task_status = $('#task-status').val();
                var task_model = $('#task-model').val();
                
                $.ajax({
                    url: '/api/tasks',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({task_name: task_name, agent: task_agent, status: task_status, model: task_model}),
                    success: function(data) {
                        alert('任务创建成功！');
                        location.reload();
                    }
                });
            });
            
            // 任务更新
            $('.update-task').click(function() {
                var task_id = $(this).data('task-id');
                var status = prompt('请输入新状态:', 'in_progress');
                var progress = prompt('请输入进度 (0-100):', '50');
                
                if (status) {
                    $.ajax({
                        url: '/api/tasks/' + task_id,
                        type: 'PUT',
                        contentType: 'application/json',
                        data: JSON.stringify({status: status, progress: parseInt(progress)}),
                        success: function(data) {
                            alert('任务更新成功！');
                            location.reload();
                        }
                    });
                }
            });
            
            // 任务历史
            $('.view-history').click(function() {
                var task_id = $(this).data('task-id');
                $.get('/api/tasks/' + task_id + '/history', function(data) {
                    var html = '<div class="list-group">';
                    data.forEach(function(entry) {
                        html += '<div class="list-group-item">' +
                            '<h6>' + entry.timestamp + '</h6>' +
                            '<p>状态: ' + entry.status + '</p>' +
                            '<p>进度: ' + entry.progress + '%</p>' +
                            '</div>';
                    });
                    html += '</div>';
                    $('#consensus-result').html(html);
                    $('#consensus').addClass('active').siblings('.section').removeClass('active');
                });
            });
            
            // 共识管理
            $('#consensus-form').submit(function(e) {
                e.preventDefault();
                var issue = $('#consensus-issue').val();
                var agents = $('#consensus-agents').val().split(',').map(function(agent) { return agent.trim(); });
                var voting_method = $('#voting-method').val();
                var decision_threshold = parseFloat($('#decision-threshold').val());
                
                $.ajax({
                    url: '/api/consensus',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({issue: issue, agents: agents, voting_method: voting_method, decision_threshold: decision_threshold}),
                    success: function(data) {
                        var html = '<div class="card">' +
                            '<div class="card-body">' +
                            '<h5 class="card-title">共识结果</h5>' +
                            '<p>决策: ' + data.decision + '</p>' +
                            '<p>得分: ' + data.total_score.toFixed(2) + '</p>' +
                            '<h6>参与者:</h6>' +
                            '<ul>';
                        data.participants.forEach(function(participant) {
                            html += '<li>' + participant.agent + ': ' + participant.vote + '</li>';
                        });
                        html += '</ul>' +
                            '</div>' +
                            '</div>';
                        $('#consensus-result').html(html);
                    }
                });
            });
            
            // 任务分解
            $('#decompose-task-form').submit(function(e) {
                e.preventDefault();
                var task = $('#decompose-task').val();
                var time_horizon = $('#time-horizon').val();
                
                $.ajax({
                    url: '/api/decompose_task',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({task: task, time_horizon: time_horizon}),
                    success: function(data) {
                        var html = '<div class="table-responsive">' +
                            '<table class="table table-striped">' +
                            '<thead>' +
                            '<tr>' +
                            '<th>任务</th>' +
                            '<th>部门</th>' +
                            '<th>代理</th>' +
                            '<th>优先级</th>' +
                            '<th>时间范围</th>' +
                            '<th>描述</th>' +
                            '</tr>' +
                            '</thead>' +
                            '<tbody>';
                        data.tasks.forEach(function(task) {
                            html += '<tr>' +
                                '<td>' + task.task + '</td>' +
                                '<td>' + task.department + '</td>' +
                                '<td>' + task.agent + '</td>' +
                                '<td>' + task.priority + '</td>' +
                                '<td>' + task.time_horizon + '</td>' +
                                '<td>' + task.description + '</td>' +
                                '</tr>';
                        });
                        html += '</tbody>' +
                            '</table>' +
                            '</div>';
                        $('#decompose-result').html(html);
                    }
                });
            });
            
            // 进度跟踪
            $('#track-progress-form').submit(function(e) {
                e.preventDefault();
                var task_ids = $('#task-ids').val().split(',').map(function(id) { return id.trim(); });
                
                $.ajax({
                    url: '/api/track_progress',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({tasks: task_ids}),
                    success: function(data) {
                        var html = '<div class="card">' +
                            '<div class="card-body">' +
                            '<h5 class="card-title">进度跟踪结果</h5>' +
                            '<p>总任务数: ' + data.overview.total_tasks + '</p>' +
                            '<p>平均进度: ' + (data.overview.average_progress * 100).toFixed(1) + '%</p>' +
                            '<h6>智能洞察:</h6>' +
                            '<ul>';
                        data.insights.forEach(function(insight) {
                            html += '<li>' + insight + '</li>';
                        });
                        html += '</ul>' +
                            '<h6>建议:</h6>' +
                            '<ul>';
                        data.recommendations.forEach(function(recommendation) {
                            html += '<li>' + recommendation + '</li>';
                        });
                        html += '</ul>' +
                            '</div>' +
                            '</div>';
                        $('#progress-result').html(html);
                    }
                });
            });
            
            // 生成报告
            $('#generate-report-form').submit(function(e) {
                e.preventDefault();
                var period = $('#report-period').val();
                
                $.ajax({
                    url: '/api/generate_report',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({period: period}),
                    success: function(data) {
                        var html = '<div class="card">' +
                            '<div class="card-body">' +
                            '<h5 class="card-title">' + data.period + ' 报告</h5>' +
                            '<p>生成时间: ' + new Date(data.generated_at * 1000).toLocaleString() + '</p>' +
                            '<p>总任务数: ' + data.task_summary.total_tasks + '</p>' +
                            '<p>平均进度: ' + data.task_summary.average_progress.toFixed(1) + '%</p>' +
                            '<h6>关键成就:</h6>' +
                            '<ul>';
                        data.key_achievements.forEach(function(achievement) {
                            html += '<li>' + achievement + '</li>';
                        });
                        html += '</ul>' +
                            '<h6>挑战:</h6>' +
                            '<ul>';
                        data.challenges.forEach(function(challenge) {
                            html += '<li>' + challenge + '</li>';
                        });
                        html += '</ul>' +
                            '<h6>智能洞察:</h6>' +
                            '<ul>';
                        data.insights.forEach(function(insight) {
                            html += '<li>' + insight + '</li>';
                        });
                        html += '</ul>' +
                            '<h6>建议:</h6>' +
                            '<ul>';
                        data.recommendations.forEach(function(recommendation) {
                            html += '<li>' + recommendation + '</li>';
                        });
                        html += '</ul>' +
                            '</div>' +
                            '</div>';
                        $('#report-result').html(html);
                    }
                });
            });
            
            // 三贤者决策
            $('#three-sages-form').submit(function(e) {
                e.preventDefault();
                var issue = $('#decision-issue').val();
                var context = $('#decision-context').val();
                
                $.ajax({
                    url: '/api/three_sages_decision',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({issue: issue, context: context}),
                    success: function(data) {
                        var html = '<div class="card">' +
                            '<div class="card-body">' +
                            '<h5 class="card-title">三贤者决策结果</h5>' +
                            '<p>决策: ' + data.decision + '</p>' +
                            '<p>综合得分: ' + data.total_score.toFixed(2) + '/1.0</p>' +
                            '<h6>决策依据:</h6>' +
                            '<p>战略价值(' + data.scores['战略价值'].toFixed(2) + ') × 0.4 + 执行可行性(' + data.scores['执行可行性'].toFixed(2) + ') × 0.3 + 创新潜力(' + data.scores['创新潜力'].toFixed(2) + ') × 0.3</p>' +
                            '<h6>三贤者意见:</h6>';
                        data.sages.forEach(function(sage) {
                            html += '<div class="mt-3">' +
                                '<h7>' + sage.name + ' (' + sage.title + '):</h7>' +
                                '<p>' + sage.opinion + '</p>' +
                                '</div>';
                        });
                        html += '<h6>决策建议:</h6>' +
                            '<p>' + data.advice + '</p>' +
                            '</div>' +
                            '</div>';
                        $('#three-sages-result').html(html);
                    }
                });
            });
            
            // 加载部门列表
            $.get('/api/departments', function(data) {
                var html = '<ul class="list-group">';
                data.forEach(function(department) {
                    html += '<li class="list-group-item department-item" data-department="' + department + '">' + department + '</li>';
                });
                html += '</ul>';
                $('#department-list').html(html);
                
                // 部门点击事件
                $('.department-item').click(function() {
                    var department = $(this).data('department');
                    $.get('/api/department/' + department, function(data) {
                        var html = '<ul class="list-group">';
                        data.forEach(function(agent) {
                            html += '<li class="list-group-item">' + agent.name + '<br><small class="text-muted">' + agent.description + '</small></li>';
                        });
                        html += '</ul>';
                        $('#agent-list').html(html);
                    });
                });
            });
            
            // 加载Agent活动状态
            function loadAgentActivity() {
                $.get('/api/agents/activity', function(data) {
                    var html = '';
                    data.forEach(function(activity) {
                        html += '<div class="mb-2">' +
                            '<span class="badge bg-primary">' + activity.agent + '</span> ' +
                            '<span>' + activity.action + '</span> ' +
                            '<span class="badge bg-success">' + activity.status + '</span>' +
                            '</div>';
                    });
                    $('#agent-activity').html(html || '<p class="text-muted">无Agent活动</p>');
                });
            }
            
            // 定时加载Agent活动状态
            setInterval(loadAgentActivity, 5000);
            loadAgentActivity();
            
            // 加载待办事项
            function loadTodoItems() {
                $.get('/api/personal_assistant/todo', function(data) {
                    var html = '<table class="table table-striped">' +
                        '<thead>' +
                        '<tr>' +
                        '<th>内容</th>' +
                        '<th>优先级</th>' +
                        '<th>截止日期</th>' +
                        '<th>状态</th>' +
                        '<th>操作</th>' +
                        '</tr>' +
                        '</thead>' +
                        '<tbody>';
                    data.forEach(function(todo) {
                        html += '<tr>' +
                            '<td>' + todo.content + '</td>' +
                            '<td>' + todo.priority + '</td>' +
                            '<td>' + (todo.due_date || '-') + '</td>' +
                            '<td>' + todo.status + '</td>' +
                            '<td><button class="btn btn-sm btn-success complete-todo" data-todo-id="' + todo.id + '">完成</button></td>' +
                            '</tr>';
                    });
                    html += '</tbody>' +
                        '</table>';
                    $('#todo-list').html(html);
                    
                    // 完成待办事项
                    $('.complete-todo').click(function() {
                        var todo_id = $(this).data('todo-id');
                        $.ajax({
                            url: '/api/personal_assistant/todo/' + todo_id,
                            type: 'PUT',
                            contentType: 'application/json',
                            data: JSON.stringify({status: 'completed'}),
                            success: function(data) {
                                loadTodoItems();
                            }
                        });
                    });
                });
            }
            
            // 加载待办事项
            loadTodoItems();
            
            // 添加待办事项
            $('#add-todo-form').submit(function(e) {
                e.preventDefault();
                var content = $('#todo-content').val();
                var priority = $('#todo-priority').val();
                var due_date = $('#todo-due-date').val();
                
                $.ajax({
                    url: '/api/personal_assistant/todo',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({content: content, priority: priority, due_date: due_date}),
                    success: function(data) {
                        loadTodoItems();
                        $('#add-todo-form')[0].reset();
                    }
                });
            });
        });
    </script>
</body>
</html>
'''
        with open('templates/index.html', 'w') as f:
            f.write(index_html)
        
    # 运行Flask应用
    app.run(host='0.0.0.0', port=5000, debug=args.debug)
