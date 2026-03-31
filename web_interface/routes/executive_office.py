#!/usr/bin/env python3
"""
Executive Office routes for OPC-Agents Web Interface
"""

from flask import Blueprint, jsonify, request
import time
import os

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
            
            # 步骤1: 用GLM判断消息意图（闲聊/搜索/任务/追问）
            intent_prompt = (
                f"判断以下用户消息的意图，只回复一个词：\n"
                f"如果是闲聊、问候、提问，回复「chat」\n"
                f"如果需要搜索互联网获取最新信息（如新闻、技术文档、市场数据等），回复「search」\n"
                f"如果是需要执行的任务、工作安排、项目需求，丏述清晰可执行，回复「task」\n"
                f"如果意图不明确、信息不足、需要追问用户才能执行，回复「clarify」\n\n"
                f"用户消息：{message}"
            )
            intent_response = model_manager.generate_response(intent_prompt, model="glm")
            intent_lower = intent_response.lower().strip()
            
            if "clarify" in intent_lower and "task" not in intent_lower:
                clarify_prompt = f"用户消息：「{message}」\n这个消息意图不明确，请用一句话追问用户，获取更多关键信息。只输出追问的问题，不要其他内容。"
                clarify_question = model_manager.generate_response(clarify_prompt, model="glm")
                response = {
                    "id": f"msg_{int(time.time())}",
                    "type": "clarify",
                    "content": clarify_question,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
                return jsonify(response)
            
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
            synthesis = decision.get('synthesis', {})
            execution_steps = synthesis.get('execution_steps', [])
            monitoring_plan = synthesis.get('monitoring_plan', [])
            synthesis_summary = synthesis.get('summary', '三贤者评估完成')

            # 步骤3: 如果三贤者没有生成执行步骤，用GLM动态生成
            if not execution_steps:
                decomposed = manager.decompose_task(message, synthesis)
                execution_steps = decomposed.get('execution_steps', [])

            # 步骤3.5: 生成执行计划并写入工作目录，等待用户确认
            main_task_id = f"task-{int(time.time())}"
            manager.create_task(
                task_id=main_task_id,
                task_name=message[:50],
                agent="executive_office",
                initial_status="pending"
            )

            plan_content = manager.generate_plan_markdown(
                task_name=message,
                synthesis=synthesis,
                execution_steps=execution_steps,
                monitoring_plan=monitoring_plan,
                task_id=main_task_id
            )
            work_dir = manager.get_work_dir(main_task_id)
            plan_path = os.path.join(work_dir, "plan.md") if work_dir else None
            if plan_path:
                try:
                    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
                    with open(plan_path, 'w', encoding='utf-8') as f:
                        f.write(plan_content)
                except Exception as e:
                    print(f"[计划写入] 失败: {e}")

            # 缓存计划数据供确认时使用
            if not hasattr(manager, '_pending_plans'):
                manager._pending_plans = {}
            manager._pending_plans[main_task_id] = {
                "message": message,
                "decision": decision,
                "synthesis": synthesis,
                "execution_steps": execution_steps,
                "monitoring_plan": monitoring_plan,
                "search_context": search_context,
                "work_dir": work_dir
            }

            # 构建计划展示内容
            steps_text = ""
            for i, step in enumerate(execution_steps, 1):
                steps_text += f"| {i} | {step.get('task','')} | {step.get('department','')} | {step.get('deliverable','')} |\n"

            monitor_text = ""
            for mp in monitoring_plan:
                monitor_text += f"- {mp.get('checkpoint','')} (触发: {mp.get('trigger','')})\n"

            ai_response = (
                f"**📋 执行计划已生成，请确认：**\n\n"
                f"**任务概述：** {message}\n\n"
                f"**三贤者评估摘要：** {synthesis_summary}\n\n"
                f"**执行步骤：**\n"
                f"| # | 任务 | 部门 | 预期产出物 |\n"
                f"|---|------|------|-----------|\n"
                f"{steps_text}\n"
            )
            if monitor_text:
                ai_response += f"**监控计划：**\n{monitor_text}\n"
            if work_dir:
                ai_response += f"\n📁 计划文件：{plan_path}\n"
            ai_response += f"\n任务ID: {main_task_id}"

            response = {
                "id": f"msg_{int(time.time())}",
                "type": "plan_pending",
                "content": ai_response,
                "task_id": main_task_id,
                "plan_path": plan_path,
                "execution_steps": execution_steps,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
            }
            return jsonify(response)
            
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

    @bp.route('/chat/<task_id>/confirm_plan', methods=['POST'])
    def confirm_plan(task_id):
        pending = getattr(manager, '_pending_plans', {}).get(task_id)
        if not pending:
            return jsonify({"error": "未找到待确认的计划"}), 404

        execution_steps = pending['execution_steps']
        work_dir = pending.get('work_dir', '')
        message = pending['message']
        synthesis = pending.get('synthesis', {})

        manager.update_task_status(task_id, "in_progress")

        dispatched = []
        previous_outputs = []
        for i, step in enumerate(execution_steps):
            dept = step.get('department', 'engineering')
            agent = step.get('agent', '')
            sub_task_name = step.get('task', f"步骤{i+1}")
            sub_task_id = f"{task_id}-step{i+1}"

            manager.create_task(
                task_id=sub_task_id,
                task_name=sub_task_name,
                agent=agent or dept,
                initial_status="pending"
            )
            if agent:
                manager.task_manager.assign_task_to_agent(sub_task_id, agent, dept)

            enriched_previous = []
            for po in previous_outputs:
                entry = {"step": po["step"], "task": po["task"], "agent": po["agent"], "output_path": po["output_path"]}
                if po.get("output_path") and os.path.exists(po["output_path"]):
                    try:
                        with open(po["output_path"], "r", encoding="utf-8") as f:
                            content = f.read()
                        if len(content) > 1000:
                            content = content[:1000] + "\n...(已截断)"
                        entry["output_content"] = content
                    except Exception:
                        entry["output_content"] = f"(无法读取: {po['output_path']})"
                else:
                    entry["output_content"] = "(无产出物)"
                enriched_previous.append(entry)

            task_context = {
                "user_requirement": message,
                "sages_summary": synthesis.get('summary', ''),
                "execution_plan": execution_steps,
                "current_step": step,
                "previous_outputs": enriched_previous,
                "work_dir": work_dir,
                "step_index": i
            }

            try:
                manager.task_executor.submit_task(
                    sub_task_id,
                    {
                        "task_name": sub_task_name,
                        "description": step.get('description', f"步骤{i+1}: {sub_task_name}"),
                        "department": dept,
                        "assigned_agent": agent,
                        "context": task_context
                    }
                )
                output_path = f"{work_dir}/{agent}_output.md" if agent and work_dir else ""
                previous_outputs.append({
                    "step": i+1,
                    "task": sub_task_name,
                    "agent": agent,
                    "output_path": output_path
                })
            except Exception as exec_err:
                print(f"[任务执行] 提交失败 {sub_task_id}: {exec_err}")

            dispatched.append({
                "task_id": sub_task_id,
                "task_name": sub_task_name,
                "department": dept,
                "agent": agent
            })

        if task_id in getattr(manager, '_pending_plans', {}):
            del manager._pending_plans[task_id]

        dispatch_text = "\n".join([f"- {d['task_name']} → {d['department']}" + (f" ({d['agent']})" if d['agent'] else "") for d in dispatched])

        response = {
            "id": f"msg_{int(time.time())}",
            "type": "executive",
            "content": f"**✅ 计划已确认，开始执行：**\n\n{dispatch_text}\n\n共{len(dispatched)}个子任务已分派，各部门Agent正在处理。\n📁 工作目录：{work_dir}",
            "task_id": task_id,
            "dispatched": dispatched,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
        }
        return jsonify(response)

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
