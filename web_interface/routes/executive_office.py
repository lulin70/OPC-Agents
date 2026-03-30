#!/usr/bin/env python3
"""
Executive Office routes for OPC-Agents Web Interface
"""

from flask import Blueprint, jsonify, request
import time

# 创建蓝图
bp = Blueprint('executive_office', __name__, url_prefix='/api')

# 注册路由
def register_routes(manager):
    # 对话中心API - 获取对话历史
    @bp.route('/chat/history')
    def get_chat_history():
        # 从任务管理获取实际任务作为对话历史
        tasks = manager.get_all_tasks()
        history = []
        
        for task_id, task_info in tasks.items():
            chat_item = {
                "id": task_id,
                "title": task_info.get("task_name", "未命名任务"),
                "status": task_info.get("status", "pending"),
                "last_activity": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(task_info.get("updated_at", time.time()))),
                "message_count": 0,  # 可以从消息历史计算
                "progress": task_info.get("progress", 0)
            }
            history.append(chat_item)
        
        return jsonify(history)
    
    # 对话中心API - 获取对话详情
    @bp.route('/chat/<chat_id>')
    def get_chat_details(chat_id):
        # 从任务管理获取实际任务信息
        task_info = manager.get_task_status(chat_id)
        messages = []
        
        if task_info:
            # 创建任务相关的消息
            messages.append({
                "id": f"msg_{int(time.time())}_1",
                "type": "user",
                "content": f"任务：{task_info.get('task_name', '未命名任务')}",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(task_info.get('created_at', time.time())))
            })
            
            messages.append({
                "id": f"msg_{int(time.time())}_2",
                "type": "executive",
                "content": f"收到您的任务请求，正在处理中。任务状态：{task_info.get('status', 'pending')}",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(task_info.get('updated_at', time.time())))
            })
            
            # 分解任务
            decomposed_tasks = manager.decompose_task(task_info.get('task_name', ''))
            if decomposed_tasks:
                messages.append({
                    "id": f"msg_{int(time.time())}_3",
                    "type": "system",
                    "content": "总裁办正在分析任务需求...",
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                })
                
                # 添加分解后的任务信息
                decomposition_content = "我需要分解这个任务：\n"
                for i, task in enumerate(decomposed_tasks, 1):
                    decomposition_content += f"{i}. {task.get('task', '')}\n"
                
                decomposition_content += "\n我将分派给以下部门：\n"
                for task in decomposed_tasks:
                    decomposition_content += f"- {task.get('department', '')}：{task.get('task', '')}\n"
                
                messages.append({
                    "id": f"msg_{int(time.time())}_4",
                    "type": "executive",
                    "content": decomposition_content,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                })
                
                # 添加分解后的任务
                for task in decomposed_tasks:
                    messages.append({
                        "id": f"msg_{int(time.time())}_{task.get('agent', '').replace(' ', '_')}",
                        "type": "task",
                        "content": task.get('task', ''),
                        "department": task.get('department', ''),
                        "agent": task.get('agent', ''),
                        "status": "pending",
                        "progress": 0,
                        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                    })
        else:
            # 任务不存在时的消息
            messages.append({
                "id": f"msg_{int(time.time())}_1",
                "type": "system",
                "content": "任务不存在或已删除",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
            })
        
        return jsonify({"messages": messages})
    
    # 对话中心API - 发送消息（智能任务处理链）
    @bp.route('/chat/<chat_id>/message', methods=['POST'])
    def send_chat_message(chat_id):
        data = request.json
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        try:
            from model_integration.model_manager import ModelManager
            model_manager = ModelManager()
            
            # 步骤1: 用GLM判断消息意图（是闲聊还是任务指令）
            intent_prompt = (
                f"判断以下用户消息的意图，只回复一个词：\n"
                f"如果是闲聊、问候、提问，回复「chat」\n"
                f"如果是需要执行的任务、工作安排、项目需求，回复「task」\n"
                f"如果需要搜索互联网获取最新信息（如新闻、技术文档、市场数据等），回复「search」\n\n"
                f"用户消息：{message}"
            )
            intent_response = model_manager.generate_response(intent_prompt, model="glm")
            intent_lower = intent_response.lower()
            
            if "search" in intent_lower and "task" not in intent_lower:
                search_results = manager.web_search_query(message, max_results=3)
                if search_results:
                    context = "\n".join([f"- {r.get('title','')}: {r.get('body','')}" for r in search_results[:3]])
                    search_prompt = f"用户问题：{message}\n\n搜索到的信息：\n{context}\n\n请根据以上搜索结果，用中文回答用户的问题。"
                    ai_response = model_manager.generate_response(search_prompt, model="glm")
                    response = {
                        "id": f"msg_{int(time.time())}",
                        "type": "executive",
                        "content": ai_response,
                        "has_search": True,
                        "search_results": len(search_results),
                        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                    }
                    return jsonify(response)
            
            is_task = "task" in intent_lower
            
            if not is_task:
                chat_prompt = f"你是总裁办助理，收到用户的消息：{message}\n请友好地回复。"
                ai_response = model_manager.generate_response(chat_prompt, model="glm")
                response = {
                    "id": f"msg_{int(time.time())}",
                    "type": "executive",
                    "content": ai_response,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
                return jsonify(response)
            
            # 任务模式：启动完整处理链
            # 步骤1.5: 搜索相关信息辅助决策
            search_context = ""
            try:
                search_results = manager.web_search_query(message, max_results=2)
                if search_results:
                    search_context = "\n".join([f"- {r.get('title','')}: {r.get('body','')[:100]}" for r in search_results])
                    search_context = f"\n\n[互联网搜索参考]\n{search_context}"
            except Exception as e:
                print(f"[网页搜索] 失败: {e}")
            
            # 步骤2: 调用三贤者进行决策分析（含搜索上下文）
            decision = manager.start_three_sages_decision(message + search_context)
            decision_advice = decision.get('decision_advice', '三贤者建议：需要进一步分析')
            
            # 步骤3: 任务分解
            decomposed = manager.decompose_task(message)
            
            # 步骤4: 请求人事部评估本地Agent资源，搜寻合适Agent/Skill
            hr_assessment = {}
            hr_recommendations = []
            for sub in decomposed:
                dept = sub.get('department', 'development')
                task_name = sub.get('task', '')
                try:
                    job_id = manager.hr_enhancement.create_job_requirement(
                        title=task_name,
                        department=dept,
                        description=f"任务: {task_name}",
                        required_skills=list(sub.get('skills', []))
                    )
                    matching = manager.hr_enhancement.find_matching_agents(job_id)
                    local_agents = [m for m in matching if m.get('source') != 'github_mcp']
                    external_agents = [m for m in matching if m.get('source') == 'github_mcp']
                    
                    if not local_agents and external_agents:
                        hr_recommendations.append({
                            "task": task_name,
                            "department": dept,
                            "job_id": job_id,
                            "local_available": False,
                            "external_candidates": external_agents[:3]
                        })
                    elif local_agents:
                        sub['agent'] = local_agents[0].get('agent_name', '')
                        sub['agent_id'] = local_agents[0].get('agent_id', '')
                    
                    hr_assessment[task_name] = {
                        "department": dept,
                        "local_agents": len(local_agents),
                        "external_candidates": len(external_agents),
                        "best_match": local_agents[0] if local_agents else None
                    }
                except Exception as hr_err:
                    print(f"[人事部评估] 失败: {hr_err}")
            
            # 步骤5: 创建主任务
            main_task_id = f"task-{int(time.time())}"
            manager.create_task(
                task_id=main_task_id,
                task_name=message[:50],
                agent="executive_office",
                initial_status="in_progress"
            )
            
            # 步骤6: 分发子任务到各部门
            dispatched = []
            if decomposed:
                for sub in decomposed:
                    dept = sub.get('department', 'development')
                    agent = sub.get('agent', '')
                    sub_task_name = sub.get('task', '')
                    if sub_task_name:
                        sub_task_id = f"task-{int(time.time())}-{len(dispatched)}"
                        manager.create_task(
                            task_id=sub_task_id,
                            task_name=sub_task_name,
                            agent=agent or dept,
                            initial_status="pending"
                        )
                        if agent:
                            manager.task_manager.assign_task_to_agent(sub_task_id, agent, dept)
                        dispatched.append({
                            "task_id": sub_task_id,
                            "task_name": sub_task_name,
                            "department": dept,
                            "agent": agent
                        })
            
            # 步骤7: 触发任务执行（异步）
            for d in dispatched:
                try:
                    manager.task_executor.execute_task(
                        d["task_id"],
                        {
                            "task_name": d["task_name"],
                            "description": f"父任务: {message[:50]}",
                            "department": d["department"],
                            "assigned_agent": d["agent"]
                        }
                    )
                except Exception as exec_err:
                    print(f"[任务执行] 启动失败 {d['task_id']}: {exec_err}")
            
            # 步骤8: 构建综合回复
            dispatch_text = ""
            if dispatched:
                dispatch_text = "\n\n**任务已分派：**\n"
                for d in dispatched:
                    dispatch_text += f"- {d['task_name']} → {d['department']}"
                    if d['agent']:
                        dispatch_text += f" ({d['agent']})"
                    dispatch_text += "\n"
            
            hr_text = ""
            if hr_recommendations:
                hr_text = "\n\n**⚠️ 人事部报告 - 需要补充资源：**\n"
                for rec in hr_recommendations:
                    hr_text += f"- [{rec['department']}] {rec['task']}：本地无合适Agent"
                    if rec['external_candidates']:
                        best = rec['external_candidates'][0]
                        hr_text += f"，建议从GitHub引入: {best.get('agent_name', '')} ({best.get('stars', 0)}⭐)"
                    hr_text += "\n"
                hr_text += "\n任务执行中，如失败将自动为您推荐外部Agent/Skill。"
            
            ai_response = (
                f"**收到您的任务指令，已启动处理流程：**\n\n"
                f"1. **三贤者决策分析**：\n{decision_advice}\n\n"
                f"2. **人事部资源评估**：\n"
            )
            for task_name, assessment in hr_assessment.items():
                status = f"✅ 本地{assessment['local_agents']}个Agent可用" if assessment['local_agents'] > 0 else f"⚠️ 本地无合适Agent"
                ai_response += f"   - {task_name}({assessment['department']}): {status}\n"
            
            ai_response += (
                f"\n3. **任务分解与分派**：共 {len(dispatched)} 个子任务\n"
                f"{dispatch_text}"
                f"4. **执行中**：各部门Agent正在处理\n"
                f"{hr_text}\n"
                f"主任务ID: {main_task_id}"
            )
            
            response = {
                "id": f"msg_{int(time.time())}",
                "type": "executive",
                "content": ai_response,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "task_id": main_task_id,
                "dispatched_tasks": dispatched,
                "decision": decision,
                "hr_assessment": hr_assessment,
                "hr_recommendations": hr_recommendations
            }
        except Exception as e:
            print(f"[消息处理错误] {e}")
            response = {
                "id": f"msg_{int(time.time())}",
                "type": "executive",
                "content": f"处理消息时出现错误：{str(e)}",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
            }
        
        return jsonify(response)
    
    # 对话中心API - 任务完成后的人事部评估与用户确认
    @bp.route('/task/<task_id>/complete', methods=['POST'])
    def task_complete(task_id):
        """任务完成后的处理：成功则优化本地Agent，失败则搜寻外部资源"""
        data = request.json or {}
        success = data.get('success', False)
        task_info = manager.get_task_status(task_id)
        
        if not task_info:
            return jsonify({"error": "任务不存在"}), 404
        
        result = {"task_id": task_id, "success": success}
        
        if success:
            # 成功：人事部评估并优化本地Agent
            dept = task_info.get('assigned_to', '')
            agent = task_info.get('assigned_agent', '')
            try:
                if agent:
                    optimization = manager.hr_enhancement.optimize_agent(agent)
                    result["optimization"] = optimization
                    result["message"] = f"任务成功完成。人事部已评估并优化Agent: {agent}"
                else:
                    result["message"] = "任务成功完成。"
            except Exception as e:
                result["message"] = f"任务成功完成，Agent优化失败: {e}"
        else:
            # 失败：人事部搜寻外部Agent/Skill
            task_name = task_info.get('task_name', '')
            dept = task_info.get('assigned_to', '')
            try:
                from opc_hr.mcp_integration import MCPIntegration
                mcp = MCPIntegration()
                
                agent_results = mcp.search_agents(task_name, department=dept, limit=3)
                skill_results = mcp.search_skills(task_name, limit=3)
                
                result["external_agents"] = agent_results
                result["external_skills"] = skill_results
                result["message"] = (
                    f"任务执行失败。人事部已从GitHub搜寻到替代资源：\n"
                    f"- {len(agent_results)} 个候选Agent\n"
                    f"- {len(skill_results)} 个候选Skill\n"
                    f"请确认是否引入。"
                )
            except Exception as e:
                result["message"] = f"任务失败，外部资源搜寻出错: {e}"
        
        return jsonify(result)
    
    # 对话中心API - 用户确认引入外部Agent/Skill
    @bp.route('/hr/import', methods=['POST'])
    def hr_import():
        """用户确认引入人事部推荐的外部Agent或Skill"""
        data = request.json or {}
        import_type = data.get('type', 'agent')
        repo_full_name = data.get('repo_full_name', '')
        target_department = data.get('department', None)
        force = data.get('force', False)
        
        if not repo_full_name:
            return jsonify({"error": "repo_full_name is required"}), 400
        
        try:
            if import_type == 'agent':
                result = manager.import_agent_from_mcp(repo_full_name, target_department=target_department, force=force)
            else:
                result = manager.import_skill_from_mcp(repo_full_name, force=force)
            return jsonify(result)
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    # 对话中心API - 获取Agent活动状态
    @bp.route('/agents/activity')
    def get_agent_activity():
        # 从任务管理获取实际Agent活动状态
        tasks = manager.get_all_tasks()
        activity = []
        
        # 收集所有代理的活动
        agent_activities = {}
        for task_id, task_info in tasks.items():
            agent = task_info.get('agent', '')
            if agent:
                if agent not in agent_activities:
                    agent_activities[agent] = {
                        "agent": agent,
                        "action": f"处理任务: {task_info.get('task_name', '未命名任务')}",
                        "status": "active" if task_info.get('status') == 'in_progress' else "idle"
                    }
        
        # 添加所有代理活动
        for agent_activity in agent_activities.values():
            activity.append(agent_activity)
        
        # 如果没有活动，添加默认活动
        if not activity:
            activity.append({
                "agent": "chief_executive_agent",
                "action": "等待任务分配",
                "status": "idle"
            })
        
        return jsonify(activity)
    
    # 对话中心API - 新建对话
    @bp.route('/chat', methods=['POST'])
    def create_chat():
        data = request.json
        title = data.get('title', '新对话')
        
        # 创建新对话并持久化
        chat_id = f"chat_{int(time.time())}"
        response = {
            "id": chat_id,
            "title": title,
            "status": "pending",
            "last_activity": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "message_count": 0,
            "progress": 0
        }
        
        return jsonify(response)
    
    # 三贤者决策
    @bp.route('/three_sages_decision', methods=['POST'])
    def three_sages_decision():
        data = request.json
        issue = data.get('issue')
        context = data.get('context')
        
        if not issue:
            return jsonify({'error': 'Issue is required'}), 400
        
        result = manager.start_three_sages_decision(issue, context)
        return jsonify(result)
    
    return bp
