#!/usr/bin/env python3
"""
Chat API routes for OPC-Agents Web Interface (v2)
"""

from flask import Blueprint, jsonify, request
from opc_manager.conversation_manager import ConversationManager
import time

bp = Blueprint('chat_v2', __name__, url_prefix='/api/v2/chat')


def register_routes(manager):
    """Register chat routes"""
    conv_manager = ConversationManager(manager.db_manager)
    
    # Create conversation
    @bp.route('', methods=['POST'])
    def create_conversation():
        data = request.json
        user_id = data.get('user_id', 'default_user')
        title = data.get('title', '新对话')
        initial_message = data.get('initial_message')
        metadata = data.get('metadata', {})
        
        try:
            conv = conv_manager.create_conversation(
                user_id=user_id,
                title=title,
                initial_message=initial_message,
                metadata=metadata
            )
            
            return jsonify({
                "success": True,
                "data": conv.to_dict(),
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # List conversations
    @bp.route('', methods=['GET'])
    def list_conversations():
        user_id = request.args.get('user_id', 'default_user')
        status = request.args.get('status')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search')
        
        try:
            result = conv_manager.list_conversations(
                user_id=user_id,
                status=status,
                page=page,
                limit=limit,
                search=search
            )
            
            return jsonify({
                "success": True,
                "data": result,
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # Get conversation by ID
    @bp.route('/<conversation_id>', methods=['GET'])
    def get_conversation(conversation_id):
        try:
            conv = conv_manager.get_conversation(conversation_id)
            
            if not conv:
                return jsonify({
                    "success": False,
                    "error": "Conversation not found"
                }), 404
            
            return jsonify({
                "success": True,
                "data": conv.to_dict(),
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # Send message
    @bp.route('/<conversation_id>/message', methods=['POST'])
    def send_message(conversation_id):
        data = request.json
        role = data.get('role', 'user')
        message_type = data.get('type', 'text')
        content = data.get('content')
        metadata = data.get('metadata', {})
        
        if not content:
            return jsonify({
                "success": False,
                "error": "Content is required"
            }), 400
        
        try:
            msg = conv_manager.add_message(
                conversation_id=conversation_id,
                role=role,
                message_type=message_type,
                content=content,
                metadata=metadata
            )
            
            return jsonify({
                "success": True,
                "data": msg.to_dict(),
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # Get messages
    @bp.route('/<conversation_id>/messages', methods=['GET'])
    def get_messages(conversation_id):
        limit = int(request.args.get('limit', 50))
        before = request.args.get('before')
        
        try:
            messages = conv_manager.get_messages(
                conversation_id=conversation_id,
                limit=limit,
                before=before
            )
            
            return jsonify({
                "success": True,
                "data": {
                    "messages": [msg.to_dict() for msg in messages]
                },
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # Archive conversation
    @bp.route('/<conversation_id>/archive', methods=['POST'])
    def archive_conversation(conversation_id):
        try:
            conv_manager.archive_conversation(conversation_id)
            
            return jsonify({
                "success": True,
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # Delete conversation
    @bp.route('/<conversation_id>', methods=['DELETE'])
    def delete_conversation(conversation_id):
        soft = request.args.get('soft', 'true').lower() == 'true'
        
        try:
            conv_manager.delete_conversation(conversation_id, soft=soft)
            
            return jsonify({
                "success": True,
                "meta": {
                    "timestamp": time.time(),
                    "request_id": f"req_{int(time.time())}"
                }
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    return bp
