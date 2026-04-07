"""
微信配对路由（Flask Blueprint）

提供配对相关的 API 端点和 Web 页面
"""

from flask import Blueprint, render_template, jsonify, request
from opc_manager.openclaw_protocol.pairing_manager import pairing_manager
from opc_manager.openclaw_protocol.qr_generator import qr_generator
import uuid
import logging

logger = logging.getLogger(__name__)

router = Blueprint('wechat_pairing', __name__)


@router.route("/wechat/pairing", methods=['GET'])
def pairing_page():
    """
    配对页面
    
    显示二维码和配对码，引导用户完成绑定
    """
    return render_template("wechat/pairing.html")


@router.route("/api/wechat/pairing/create", methods=['POST'])
def create_pairing():
    """
    创建配对请求
    
    Returns:
        {
            "ok": true,
            "result": {
                "pairing_code": "ABCD1234",
                "qr_code": "data:image/png;base64,...",
                "expires_in": 3600,
                "device_id": "uuid"
            }
        }
    """
    device_id = str(uuid.uuid4())
    
    try:
        # 创建配对请求
        pairing_code = pairing_manager.create_pairing_request(
            channel='wechat',
            device_id=device_id,
            device_info={
                'type': 'wechat_plugin',
                'source': 'web_interface'
            }
        )
        
        # 生成 WebSocket URL
        host = request.host.split(':')[0] or 'localhost'
        ws_url = f"ws://{host}:18789/ws/openclaw"
        
        # 生成二维码
        base64_qr = qr_generator.generate_pairing_qr(
            pairing_code=pairing_code,
            websocket_url=ws_url,
            device_id=device_id
        )
        
        logger.info(f"Created pairing request: {pairing_code} (device={device_id})")
        
        return jsonify({
            'ok': True,
            'result': {
                'pairing_code': pairing_code,
                'qr_code': base64_qr,
                'expires_in': 3600,
                'device_id': device_id,
                'instructions': {
                    'zh': '请使用微信扫码绑定',
                    'en': 'Please scan QR code with WeChat to bind'
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to create pairing: {e}", exc_info=True)
        return jsonify({
            'ok': False,
            'error': {'message': str(e)}
        }), 400


@router.route("/api/wechat/pairing/status", methods=['GET'])
def pairing_status():
    """
    检查配对状态
    
    Args:
        code: 配对码
        
    Returns:
        {
            "status": "pending" | "approved" | "expired" | "unknown",
            "remaining": 3600  # 剩余秒数
        }
    """
    code = request.args.get('code', '')
    
    # 检查是否在待处理列表中
    pending = pairing_manager.list_pending('wechat')
    for p in pending:
        if p['code'] == code:
            if p['remaining_seconds'] <= 0:
                return jsonify({'status': 'expired'})
            return jsonify({
                'status': 'pending',
                'remaining': p['remaining_seconds']
            })
    
    # 检查是否已批准（简化：检查所有已批准设备）
    approved = pairing_manager.list_approved('wechat')
    for device in approved:
        # 这里应该检查具体的配对码关联
        # 简化处理：如果有已批准设备，就认为可能已批准
        pass
    
    return jsonify({'status': 'unknown'})


@router.route("/api/wechat/pairing/approve", methods=['POST'])
def approve_pairing():
    """
    批准配对（CLI 或管理界面使用）
    
    Args:
        code: 配对码
        
    Returns:
        {
            "ok": true,
            "result": {
                "device_id": "xxx"
            }
        }
    """
    code = request.args.get('code', '')
    device_info = pairing_manager.approve_pairing(code)
    
    if device_info:
        device_id = device_info.get('device_id', 'unknown')
        logger.info(f"Approved pairing: {device_id} (code={code})")
        
        return jsonify({
            'ok': True,
            'result': {
                'device_id': device_id,
                'message': 'Pairing approved successfully'
            }
        })
    else:
        return jsonify({
            'ok': False,
            'error': {
                'message': 'Invalid or expired pairing code'
            }
        }), 400


@router.route("/api/wechat/pairing/reject", methods=['POST'])
def reject_pairing():
    """
    拒绝配对
    
    Args:
        code: 配对码
        
    Returns:
        {
            "ok": true/false
        }
    """
    code = request.args.get('code', '')
    success = pairing_manager.reject_pairing(code)
    
    if success:
        return jsonify({
            'ok': True,
            'result': {
                'message': 'Pairing rejected'
            }
        })
    else:
        return jsonify({
            'ok': False,
            'error': {
                'message': 'Pairing code not found'
            }
        }), 404


@router.route("/api/wechat/pairing/list", methods=['GET'])
def list_pairings():
    """
    列出待处理配对请求
    
    Args:
        channel: 频道（默认 wechat）
        
    Returns:
        {
            "ok": true,
            "result": {
                "pending_pairings": [...],
                "count": 3
            }
        }
    """
    channel = request.args.get('channel', 'wechat')
    pending = pairing_manager.list_pending(channel)
    
    return jsonify({
        'ok': True,
        'result': {
            'pending_pairings': pending,
            'count': len(pending),
            'channel': channel
        }
    })


@router.route("/api/wechat/pairing/list-approved", methods=['GET'])
def list_approved():
    """
    列出已批准设备
    
    Args:
        channel: 频道（默认 wechat）
        
    Returns:
        {
            "ok": true,
            "result": {
                "approved_devices": [...],
                "count": 5
            }
        }
    """
    channel = request.args.get('channel', 'wechat')
    approved = pairing_manager.list_approved(channel)
    
    return jsonify({
        'ok': True,
        'result': {
            'approved_devices': approved,
            'count': len(approved),
            'channel': channel
        }
    })


@router.route("/api/wechat/pairing/revoke", methods=['POST'])
def revoke_device():
    """
    撤销已批准设备
    
    Args:
        device_id: 设备 ID
        
    Returns:
        {
            "ok": true/false
        }
    """
    device_id = request.args.get('device_id', '')
    success = pairing_manager.revoke_device(device_id)
    
    if success:
        logger.info(f"Revoked device: {device_id}")
        return jsonify({
            'ok': True,
            'result': {
                'message': f'Device {device_id} revoked'
            }
        })
    else:
        return jsonify({
            'ok': False,
            'error': {
                'message': 'Device not found'
            }
        }), 404


@router.route("/api/wechat/pairing/stats", methods=['GET'])
def pairing_stats():
    """
    获取配对统计信息
    
    Returns:
        {
            "ok": true,
            "result": {
                "pending_count": 3,
                "approved_count": 5,
                "expired_count": 0
            }
        }
    """
    stats = pairing_manager.get_stats()
    
    return jsonify({
        'ok': True,
        'result': stats
    })
