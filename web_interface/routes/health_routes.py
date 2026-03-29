#!/usr/bin/env python3
"""
Health Check Routes for OPC-Agents Web Interface

Provides API endpoints for health checks and monitoring.
"""

from flask import Blueprint, jsonify, request, Response
import logging

health_bp = Blueprint('health', __name__, url_prefix='/api/health')
logger = logging.getLogger("OPC-Agents.HealthRoutes")

_opc_manager = None


def init_health_routes(opc_manager):
    """初始化健康检查路由"""
    global _opc_manager
    _opc_manager = opc_manager


def get_opc_manager():
    """获取OPCManager实例"""
    global _opc_manager
    if _opc_manager is None:
        from opc_manager.core import OPCManager
        _opc_manager = OPCManager()
    return _opc_manager


@health_bp.route('/', methods=['GET'])
def health_overview():
    """系统健康概览"""
    try:
        opc = get_opc_manager()
        from monitoring.health_check import HealthChecker
        checker = HealthChecker(opc)
        result = checker.run_all_checks()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Health overview failed: {e}")
        return jsonify({
            "overall_status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/database', methods=['GET'])
def health_database():
    """数据库健康检查"""
    try:
        opc = get_opc_manager()
        from monitoring.health_check import HealthChecker
        checker = HealthChecker(opc)
        result = checker.check_database()
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return jsonify({
            "component": "database",
            "status": "error",
            "message": str(e)
        }), 500


@health_bp.route('/agents', methods=['GET'])
def health_agents():
    """Agent状态检查"""
    try:
        opc = get_opc_manager()
        
        agents_status = {
            "total_agents": 0,
            "active_agents": 0,
            "departments": {}
        }
        
        if opc.agent_manager:
            all_agents = opc.agent_manager.get_all_agents()
            agents_status["total_agents"] = len(all_agents)
            
            for agent in all_agents:
                dept = agent.get("department", "unknown")
                if dept not in agents_status["departments"]:
                    agents_status["departments"][dept] = {"count": 0, "agents": []}
                agents_status["departments"][dept]["count"] += 1
                agents_status["departments"][dept]["agents"].append(agent.get("name", "unknown"))
        
        return jsonify({
            "status": "healthy",
            "agents": agents_status
        })
    except Exception as e:
        logger.error(f"Agents health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/tasks', methods=['GET'])
def health_tasks():
    """任务状态检查"""
    try:
        opc = get_opc_manager()
        
        task_stats = {
            "status": "healthy",
            "statistics": {}
        }
        
        if opc.task_executor:
            task_stats["statistics"] = opc.task_executor.get_statistics()
        
        if opc.task_manager:
            all_tasks = opc.task_manager.get_all_tasks()
            status_counts = {}
            for task in all_tasks.values():
                status = task.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            task_stats["status_counts"] = status_counts
        
        return jsonify(task_stats)
    except Exception as e:
        logger.error(f"Tasks health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/queue', methods=['GET'])
def health_queue():
    """消息队列状态检查"""
    try:
        opc = get_opc_manager()
        
        queue_stats = {
            "status": "healthy",
            "queue_enabled": False,
            "statistics": {}
        }
        
        if opc.communication_manager:
            cm = opc.communication_manager
            queue_stats["queue_enabled"] = cm.message_queue is not None
            
            if cm.message_queue:
                queue_stats["statistics"] = cm.get_queue_statistics()
        
        return jsonify(queue_stats)
    except Exception as e:
        logger.error(f"Queue health check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """获取系统指标"""
    try:
        from monitoring.metrics import MetricsCollector
        
        collector = MetricsCollector()
        summary = collector.get_summary()
        
        return jsonify({
            "status": "success",
            "metrics": summary
        })
    except Exception as e:
        logger.error(f"Get metrics failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """获取告警列表"""
    try:
        from monitoring.alerts import AlertManager, AlertLevel
        
        manager = AlertManager()
        
        level = request.args.get('level')
        if level:
            level = AlertLevel(level)
        
        alerts = manager.get_active_alerts(level=level)
        
        return jsonify({
            "status": "success",
            "alerts": [a.to_dict() for a in alerts],
            "statistics": manager.get_statistics()
        })
    except Exception as e:
        logger.error(f"Get alerts failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """确认告警"""
    try:
        from monitoring.alerts import AlertManager
        
        manager = AlertManager()
        success = manager.acknowledge_alert(alert_id)
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Alert {alert_id} acknowledged"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Alert {alert_id} not found"
            }), 404
    except Exception as e:
        logger.error(f"Acknowledge alert failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """解决告警"""
    try:
        from monitoring.alerts import AlertManager
        
        manager = AlertManager()
        success = manager.resolve_alert(alert_id)
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Alert {alert_id} resolved"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Alert {alert_id} not found"
            }), 404
    except Exception as e:
        logger.error(f"Resolve alert failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@health_bp.route('/prometheus', methods=['GET'])
def prometheus_metrics():
    """Prometheus格式的指标"""
    try:
        from monitoring.metrics import MetricsCollector
        
        collector = MetricsCollector()
        metrics_text = collector.export_prometheus()
        
        return Response(metrics_text, mimetype='text/plain')
    except Exception as e:
        logger.error(f"Prometheus metrics failed: {e}")
        return Response(f"# Error: {e}", mimetype='text/plain'), 500


@health_bp.route('/liveness', methods=['GET'])
def liveness():
    """存活探针"""
    return jsonify({"status": "alive"})


@health_bp.route('/readiness', methods=['GET'])
def readiness():
    """就绪探针"""
    try:
        opc = get_opc_manager()
        from monitoring.health_check import HealthChecker
        checker = HealthChecker(opc)
        result = checker.run_all_checks()
        
        if result.get("overall_status") == "healthy":
            return jsonify({"status": "ready"})
        else:
            return jsonify({
                "status": "not_ready",
                "reason": result.get("overall_status")
            }), 503
    except Exception as e:
        return jsonify({
            "status": "not_ready",
            "reason": str(e)
        }), 503
