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
        # 模拟对话历史数据
        history = [
            {
                "id": "chat_1",
                "title": "产品发布计划",
                "status": "in_progress",
                "last_activity": "2026-03-27T10:15:00",
                "message_count": 32,
                "progress": 80
            },
            {
                "id": "chat_2",
                "title": "市场分析报告",
                "status": "completed",
                "last_activity": "2026-03-27T09:30:00",
                "message_count": 15,
                "progress": 100
            },
            {
                "id": "chat_3",
                "title": "团队建设方案",
                "status": "completed",
                "last_activity": "2026-03-26T14:20:00",
                "message_count": 20,
                "progress": 100
            },
            {
                "id": "chat_4",
                "title": "技术架构设计",
                "status": "in_progress",
                "last_activity": "2026-03-24T11:45:00",
                "message_count": 25,
                "progress": 45
            },
            {
                "id": "chat_5",
                "title": "年度战略规划",
                "status": "in_progress",
                "last_activity": "2026-03-13T16:10:00",
                "message_count": 45,
                "progress": 60
            },
            {
                "id": "chat_6",
                "title": "周度工作总结",
                "status": "pending",
                "last_activity": "2026-03-20T17:30:00",
                "message_count": 10,
                "progress": 0
            }
        ]
        return jsonify(history)
    
    # 对话中心API - 获取对话详情
    @bp.route('/chat/<chat_id>')
    def get_chat_details(chat_id):
        # 模拟对话详情数据
        messages = [
            {
                "id": "msg_1",
                "type": "user",
                "content": "帮我制定一个产品发布计划",
                "timestamp": "2026-03-27T10:00:00"
            },
            {
                "id": "msg_2",
                "type": "executive",
                "content": "收到您的请求，我需要分析这个任务并制定计划。",
                "timestamp": "2026-03-27T10:00:00"
            },
            {
                "id": "msg_3",
                "type": "system",
                "content": "总裁办正在分析任务需求...",
                "timestamp": "2026-03-27T10:00:00"
            },
            {
                "id": "msg_4",
                "type": "executive",
                "content": "我需要分解这个任务：\n1. 市场调研和竞争分析\n2. 产品功能规划\n3. 发布时间线制定\n4. 营销和推广策略\n5. 资源需求评估\n\n我将分派给以下部门：\n- 市场部：市场调研和竞争分析\n- 产品部：产品功能规划\n- 项目管理部：发布时间线制定\n- 营销部：营销和推广策略\n- 资源部：资源需求评估",
                "timestamp": "2026-03-27T10:01:00"
            },
            {
                "id": "msg_5",
                "type": "system",
                "content": "正在分派任务...",
                "timestamp": "2026-03-27T10:01:00"
            },
            {
                "id": "msg_6",
                "type": "task",
                "content": "市场调研和竞争分析",
                "department": "市场部",
                "agent": "市场研究员",
                "status": "in_progress",
                "progress": 25,
                "timestamp": "2026-03-27T10:01:00"
            },
            {
                "id": "msg_7",
                "type": "task",
                "content": "产品功能规划",
                "department": "产品部",
                "agent": "产品经理",
                "status": "in_progress",
                "progress": 15,
                "timestamp": "2026-03-27T10:01:00"
            },
            {
                "id": "msg_8",
                "type": "system",
                "content": "进度更新：市场调研和竞争分析 - 50%",
                "timestamp": "2026-03-27T10:02:00"
            },
            {
                "id": "msg_9",
                "type": "system",
                "content": "进度更新：产品功能规划 - 30%",
                "timestamp": "2026-03-27T10:03:00"
            },
            {
                "id": "msg_10",
                "type": "system",
                "content": "进度更新：市场调研和竞争分析 - 75%",
                "timestamp": "2026-03-27T10:08:00"
            },
            {
                "id": "msg_11",
                "type": "system",
                "content": "进度更新：市场调研和竞争分析 - 100%",
                "timestamp": "2026-03-27T10:10:00"
            },
            {
                "id": "msg_12",
                "type": "system",
                "content": "任务完成：市场调研和竞争分析",
                "timestamp": "2026-03-27T10:10:00"
            },
            {
                "id": "msg_13",
                "type": "executive",
                "content": "市场部已完成市场调研和竞争分析，结果如下：\n- 市场竞争格局：主要竞争对手包括A公司和B公司\n- 市场趋势：AI驱动的产品需求增长迅速\n- 目标用户群体：25-40岁的专业人士",
                "timestamp": "2026-03-27T10:10:00"
            }
        ]
        return jsonify({"messages": messages})
    
    # 对话中心API - 发送消息
    @bp.route('/chat/<chat_id>/message', methods=['POST'])
    def send_chat_message(chat_id):
        data = request.json
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        try:
            # 尝试调用ZeroClaw Gateway处理消息
            from zeroclaw_integration import ZeroClawIntegration
            zero_claw = ZeroClawIntegration()
            
            # 构建提示词
            prompt = f"你是总裁办助理，收到用户的消息：{message}\n请根据你的角色给出响应。"
            
            # 调用ZeroClaw获取响应
            ai_response = zero_claw.call_chat_completion(prompt, model="glm")
            
            if ai_response:
                response = {
                    "id": f"msg_{int(time.time())}",
                    "type": "executive",
                    "content": ai_response,
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
            else:
                # 如果ZeroClaw调用失败，使用manager处理
                result = manager.send_message("user", "chief_executive_agent", "request", message)
                response = {
                    "id": f"msg_{int(time.time())}",
                    "type": "executive",
                    "content": result.get("response", "收到您的消息，正在处理..."),
                    "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
                }
        except Exception as e:
            # 如果所有处理都失败，返回错误信息
            print(f"[消息处理错误] {e}")
            response = {
                "id": f"msg_{int(time.time())}",
                "type": "executive",
                "content": f"处理消息时出现错误：{str(e)}。请检查系统配置或稍后重试。",
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S')
            }
        
        return jsonify(response)
    
    # 对话中心API - 获取Agent活动状态
    @bp.route('/agents/activity')
    def get_agent_activity():
        # 模拟Agent活动状态
        activity = [
            {
                "agent": "chief_executive_agent",
                "action": "整合任务结果",
                "status": "active"
            },
            {
                "agent": "产品经理",
                "action": "完成产品功能规划",
                "status": "active"
            },
            {
                "agent": "市场研究员",
                "action": "提交市场分析报告",
                "status": "active"
            }
        ]
        return jsonify(activity)
    
    # 对话中心API - 新建对话
    @bp.route('/chat', methods=['POST'])
    def create_chat():
        data = request.json
        title = data.get('title', '新对话')
        
        # 模拟创建对话
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
