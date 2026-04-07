#!/usr/bin/env python3
"""
Notification API routes for OPC-Agents Web Interface (v2)
"""

from flask import Blueprint, jsonify, request
from opc_manager.notification_manager import NotificationManager
import time

bp = Blueprint('notifications_v2', __name__, url_prefix='/api/v2/notifications')


def register_routes(manager):
    """Register notification routes"""
    notif_manager = NotificationManager(manager.db_manager, manager.event_bus)
    
    # Get notifications list
    @bp.route('', methods=['GET'])
    def get_notifications():
        user_id = request.args.get('user_id', 'default_user')
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        type_filter = request.args.get('type_filter')
        priority_filter = request.args.get('priority_filter')
        
        try:
            result = notif_manager.get_notifications(
                user_id=user_id,
                unread_only=unread_only,
                page=page,
                limit=limit,
                type_filter=type_filter,
                priority_filter=priority_filter
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
    
    # Get unread count
    @bp.route('/unread-count', methods=['GET'])
    def get_unread_count():
        user_id = request.args.get('user_id', 'default_user')
        
        try:
            count = notif_manager.get_unread_count(user_id)
            
            return jsonify({
                "success": True,
                "data": {"unread_count": count},
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
    
    # Mark as read
    @bp.route('/<notification_id>/read', methods=['PUT'])
    def mark_as_read(notification_id):
        user_id = request.args.get('user_id', 'default_user')
        
        try:
            success = notif_manager.mark_as_read(notification_id, user_id)
            
            return jsonify({
                "success": success,
                "data": {"marked": success},
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
    
    # Mark all as read
    @bp.route('/read-all', methods=['PUT'])
    def mark_all_as_read():
        user_id = request.args.get('user_id', 'default_user')
        before = request.args.get('before')
        
        try:
            count = notif_manager.mark_all_as_read(user_id, before)
            
            return jsonify({
                "success": True,
                "data": {"marked_count": count},
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
    
    # Delete notification
    @bp.route('/<notification_id>', methods=['DELETE'])
    def delete_notification(notification_id):
        user_id = request.args.get('user_id', 'default_user')
        
        try:
            success = notif_manager.delete_notification(notification_id, user_id)
            
            return jsonify({
                "success": success,
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
    
    # Create notification (for testing)
    @bp.route('', methods=['POST'])
    def create_notification():
        data = request.json
        user_id = data.get('user_id', 'default_user')
        type_ = data.get('type', 'task')
        priority = data.get('priority', 'normal')
        title = data.get('title', 'Test Notification')
        content = data.get('content', '')
        related_object_type = data.get('related_object_type')
        related_object_id = data.get('related_object_id')
        
        try:
            notif = notif_manager.create_notification(
                user_id=user_id,
                type=type_,
                priority=priority,
                title=title,
                content=content,
                related_object_type=related_object_type,
                related_object_id=related_object_id
            )
            
            return jsonify({
                "success": True,
                "data": notif.to_dict(),
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
