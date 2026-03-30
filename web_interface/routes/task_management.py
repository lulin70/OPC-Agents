from flask import Blueprint, request, jsonify
import time
import os
import subprocess
import sys

# 创建蓝图
task_bp = Blueprint('task', __name__, url_prefix='/api/tasks')

# 注册路由
def register_routes(manager):
    # 创建任务
    @task_bp.route('', methods=['POST'])
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
        return jsonify({'task_id': task_id, 'message': 'Task created successfully', 'model': model})
    
    # 更新任务状态
    @task_bp.route('/<task_id>', methods=['PUT'])
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
    @task_bp.route('/<task_id>/history')
    def get_task_history(task_id):
        history = manager.get_task_history(task_id)
        # 格式化时间戳
        for entry in history:
            if isinstance(entry['timestamp'], (int, float)):
                entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
        return jsonify(history)
    
    # 获取所有任务历史记录
    @task_bp.route('/history')
    def get_all_task_history():
        all_history = manager.get_all_task_history()
        # 格式化时间戳
        for task_id, history in all_history.items():
            for entry in history:
                if isinstance(entry['timestamp'], (int, float)):
                    entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
        return jsonify(all_history)
    
    # 完成任务
    @task_bp.route('/<task_id>/complete', methods=['POST'])
    def complete_task(task_id):
        data = request.json
        result = data.get('result')
        description = data.get('description', '任务完成')
        
        manager.complete_task(task_id, result, description)
        return jsonify({'message': 'Task completed successfully'})
    
    # 测试任务
    @task_bp.route('/<task_id>/test', methods=['POST'])
    def test_task(task_id):
        data = request.json
        test_result = data.get('test_result', True)
        test_details = data.get('test_details')
        
        manager.test_task(task_id, test_result, test_details)
        return jsonify({'message': 'Task tested successfully'})
    
    # 获取所有任务
    @task_bp.route('')
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
    
    # 任务分解
    @task_bp.route('/decompose', methods=['POST'])
    def decompose_task():
        data = request.json
        task = data.get('task')
        time_horizon = data.get('time_horizon', 'medium')
        
        if not task:
            return jsonify({'error': 'Task is required'}), 400
        
        decomposed_tasks = manager.decompose_task(task, time_horizon)
        return jsonify({'tasks': decomposed_tasks})
    
    # 跟踪任务进度
    @task_bp.route('/track_progress', methods=['POST'])
    def track_progress():
        data = request.json
        tasks = data.get('tasks', None)
        
        progress = manager.track_progress(tasks)
        return jsonify(progress)
    
    # 生成报告
    @task_bp.route('/generate_report', methods=['POST'])
    def generate_report():
        data = request.json
        period = data.get('period', 'weekly')
        
        report = manager.generate_report(period)
        return jsonify(report)
    
    # 分配任务
    @task_bp.route('/assign', methods=['POST'])
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
    
    # 自动分配任务
    @task_bp.route('/auto_assign', methods=['POST'])
    def auto_assign_tasks():
        data = request.json
        tasks = data.get('tasks')
        
        if not tasks or not isinstance(tasks, list):
            return jsonify({'error': 'Tasks list is required'}), 400
        
        assignment_results = manager.auto_assign_tasks(tasks)
        return jsonify({'assignments': assignment_results})
    
    # 查找最佳Agent
    @task_bp.route('/find_agent', methods=['POST'])
    def find_best_agent():
        data = request.json
        task_name = data.get('task_name')
        task_type = data.get('task_type')
        priority = data.get('priority', 'medium')
        deadline = data.get('deadline')
        
        if not task_name:
            return jsonify({'error': 'Task name is required'}), 400
        
        best_agent = manager.find_best_agent_for_task(task_name, task_type, priority, deadline)
        return jsonify(best_agent)
    
    @task_bp.route('/<task_id>/rename', methods=['PUT'])
    def rename_task(task_id):
        data = request.json
        new_name = data.get('name', '').strip()
        if not new_name:
            return jsonify({'error': 'New name is required'}), 400
        ok = manager.rename_task(task_id, new_name)
        if ok:
            return jsonify({'message': f'Task renamed to: {new_name}'})
        return jsonify({'error': 'Task not found'}), 404
    
    @task_bp.route('/<task_id>', methods=['DELETE'])
    def delete_task(task_id):
        ok = manager.delete_task(task_id)
        if ok:
            return jsonify({'message': 'Task deleted'})
        return jsonify({'error': 'Task not found'}), 404
    
    @task_bp.route('/<task_id>/workdir')
    def get_work_dir(task_id):
        work_dir = manager.get_work_dir(task_id)
        if work_dir:
            return jsonify({'work_dir': work_dir})
        return jsonify({'error': 'Task not found or no work dir'}), 404
    
    @task_bp.route('/<task_id>/open_workdir', methods=['POST'])
    def open_work_dir(task_id):
        work_dir = manager.get_work_dir(task_id)
        if not work_dir or not os.path.isdir(work_dir):
            return jsonify({'error': 'Work directory not found'}), 404
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', work_dir])
            elif sys.platform == 'win32':
                subprocess.Popen(['explorer', work_dir])
            else:
                subprocess.Popen(['xdg-open', work_dir])
            return jsonify({'message': f'Opened: {work_dir}'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return task_bp