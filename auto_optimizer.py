#!/usr/bin/env python3
"""
Agent自动优化调度器
实现定期自动自我优化功能
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from opc_manager import OPCManager

class AutoOptimizer:
    """自动优化调度器"""
    
    def __init__(self, config_path: str = "auto_optimizer_config.json"):
        """初始化自动优化器"""
        self.config_path = config_path
        self.config = self._load_config()
        self.opc_manager = OPCManager()
        self.scheduler_thread = None
        self.is_running = False
        self.optimization_history = []
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[自动优化] 加载配置失败: {e}")
        
        # 默认配置
        default_config = {
            "enabled": True,
            "schedule": {
                "type": "weekly",  # daily, weekly, monthly
                "day": 0,  # 0=周一, 6=周日 (weekly时有效)
                "hour": 2,  # 凌晨2点
                "minute": 0
            },
            "optimization": {
                "agent_selection": "all",  # all, performance_based, custom
                "custom_agents": [],
                "iterations": 1,
                "min_performance_threshold": 0.7,
                "max_agents_per_session": 50
            },
            "notifications": {
                "enabled": True,
                "channels": ["console", "file"],  # console, file, email, webhook
                "email": {
                    "enabled": False,
                    "recipients": [],
                    "smtp_server": "",
                    "smtp_port": 587,
                    "username": "",
                    "password": ""
                },
                "webhook": {
                    "enabled": False,
                    "url": "",
                    "headers": {}
                }
            },
            "history": {
                "max_records": 100,
                "retention_days": 90
            }
        }
        
        self._save_config(default_config)
        return default_config
    
    def _save_config(self, config: Dict[str, Any]):
        """保存配置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[自动优化] 保存配置失败: {e}")
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置"""
        self.config.update(new_config)
        self._save_config(self.config)
        print("[自动优化] 配置已更新")
    
    def get_next_optimization_time(self) -> datetime:
        """计算下次优化时间"""
        schedule = self.config["schedule"]
        now = datetime.now()
        
        if schedule["type"] == "daily":
            # 每天指定时间
            next_time = now.replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
        
        elif schedule["type"] == "weekly":
            # 每周指定星期几的指定时间
            days_ahead = schedule["day"] - now.weekday()
            if days_ahead <= 0:  # 目标日期已过，设为下周
                days_ahead += 7
            next_time = now + timedelta(days=days_ahead)
            next_time = next_time.replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
        
        elif schedule["type"] == "monthly":
            # 每月1号的指定时间
            if now.day == 1 and now.hour < schedule["hour"]:
                next_time = now.replace(hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
            else:
                # 设为下月1号
                if now.month == 12:
                    next_time = now.replace(year=now.year + 1, month=1, day=1, 
                                          hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
                else:
                    next_time = now.replace(month=now.month + 1, day=1,
                                          hour=schedule["hour"], minute=schedule["minute"], second=0, microsecond=0)
        
        else:
            # 默认每天
            next_time = now + timedelta(days=1)
        
        return next_time
    
    def select_agents_for_optimization(self) -> List[str]:
        """选择需要优化的Agent"""
        selection_type = self.config["optimization"]["agent_selection"]
        
        if selection_type == "all":
            # 选择所有Agent
            all_agents = []
            for department in self.opc_manager.get_departments():
                official_agents = self.opc_manager.get_official_agent_by_department(department)
                custom_agents = self.opc_manager.get_agent_by_department(department)
                
                for agent in official_agents:
                    all_agents.append(agent.get('name'))
                all_agents.extend(custom_agents)
            
            return list(set(all_agents))[:self.config["optimization"]["max_agents_per_session"]]
        
        elif selection_type == "performance_based":
            # 基于性能选择表现不佳的Agent
            # 这里需要实际实现性能监控逻辑
            # 暂时返回所有Agent
            return self.select_agents_for_optimization()[:self.config["optimization"]["max_agents_per_session"]]
        
        elif selection_type == "custom":
            # 使用自定义列表
            return self.config["optimization"]["custom_agents"]
        
        return []
    
    def run_optimization(self) -> Dict[str, Any]:
        """执行优化"""
        print(f"[自动优化] 开始执行自动优化 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 选择Agent
        agents = self.select_agents_for_optimization()
        print(f"[自动优化] 选择的Agent数量: {len(agents)}")
        
        # 执行优化
        iterations = self.config["optimization"]["iterations"]
        result = self.opc_manager.optimize_agents(agent_ids=agents, iterations=iterations)
        
        # 记录优化历史
        optimization_record = {
            "timestamp": time.time(),
            "datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "agents_count": len(agents),
            "iterations": iterations,
            "result": result
        }
        
        self.optimization_history.append(optimization_record)
        self._save_optimization_history()
        
        # 发送通知
        self._send_notification(result)
        
        print(f"[自动优化] 自动优化完成 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return result
    
    def _send_notification(self, result: Dict[str, Any]):
        """发送通知"""
        if not self.config["notifications"]["enabled"]:
            return
        
        channels = self.config["notifications"]["channels"]
        
        # 生成通知内容
        notification_content = self._generate_notification_content(result)
        
        # 控制台通知
        if "console" in channels:
            print("[自动优化通知]")
            print(notification_content)
        
        # 文件通知
        if "file" in channels:
            self._save_notification_to_file(notification_content)
        
        # 邮件通知
        if "email" in channels and self.config["notifications"]["email"]["enabled"]:
            self._send_email_notification(notification_content)
        
        # Webhook通知
        if "webhook" in channels and self.config["notifications"]["webhook"]["enabled"]:
            self._send_webhook_notification(notification_content)
    
    def _generate_notification_content(self, result: Dict[str, Any]) -> str:
        """生成通知内容"""
        content = f"Agent自动优化完成报告\n"
        content += f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"迭代次数: {result['summary']['total_iterations']}\n"
        content += f"优化的Agent数量: {len(result['summary']['optimized_agents'])}\n\n"
        
        content += "改进总结:\n"
        for improvement in result['summary']['improvements']:
            content += f"  - {improvement}\n"
        
        return content
    
    def _save_notification_to_file(self, content: str):
        """保存通知到文件"""
        notification_dir = "optimization_notifications"
        if not os.path.exists(notification_dir):
            os.makedirs(notification_dir)
        
        filename = f"notification_{int(time.time())}.txt"
        file_path = os.path.join(notification_dir, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[自动优化] 通知已保存到: {file_path}")
        except Exception as e:
            print(f"[自动优化] 保存通知失败: {e}")
    
    def _send_email_notification(self, content: str):
        """发送邮件通知"""
        # 这里需要实现邮件发送逻辑
        # 暂时只打印日志
        print("[自动优化] 邮件通知功能待实现")
    
    def _send_webhook_notification(self, content: str):
        """发送Webhook通知"""
        # 这里需要实现Webhook发送逻辑
        # 暂时只打印日志
        print("[自动优化] Webhook通知功能待实现")
    
    def _save_optimization_history(self):
        """保存优化历史"""
        history_path = "optimization_history.json"
        
        # 限制历史记录数量
        max_records = self.config["history"]["max_records"]
        if len(self.optimization_history) > max_records:
            self.optimization_history = self.optimization_history[-max_records:]
        
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(self.optimization_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[自动优化] 保存优化历史失败: {e}")
    
    def load_optimization_history(self) -> List[Dict[str, Any]]:
        """加载优化历史"""
        history_path = "optimization_history.json"
        
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[自动优化] 加载优化历史失败: {e}")
        
        return []
    
    def start_scheduler(self):
        """启动调度器"""
        if self.is_running:
            print("[自动优化] 调度器已在运行")
            return
        
        if not self.config["enabled"]:
            print("[自动优化] 自动优化已禁用")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        
        print("[自动优化] 调度器已启动")
        next_time = self.get_next_optimization_time()
        print(f"[自动优化] 下次优化时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def stop_scheduler(self):
        """停止调度器"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("[自动优化] 调度器已停止")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        while self.is_running:
            try:
                next_time = self.get_next_optimization_time()
                now = datetime.now()
                
                if now >= next_time:
                    # 执行优化
                    self.run_optimization()
                    
                    # 等待一段时间避免重复执行
                    time.sleep(60)
                else:
                    # 计算等待时间
                    wait_seconds = (next_time - now).total_seconds()
                    wait_seconds = min(wait_seconds, 3600)  # 最多等待1小时
                    
                    print(f"[自动优化] 等待下次优化，还有 {wait_seconds/60:.1f} 分钟")
                    time.sleep(wait_seconds)
                    
            except Exception as e:
                print(f"[自动优化] 调度器错误: {e}")
                time.sleep(300)  # 出错后等待5分钟
    
    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计信息"""
        history = self.load_optimization_history()
        
        if not history:
            return {
                "total_optimizations": 0,
                "last_optimization": None,
                "average_improvement_rate": 0,
                "total_agents_optimized": 0
            }
        
        total_optimizations = len(history)
        last_optimization = history[-1]["datetime"]
        
        # 计算平均改进率
        total_improvement_rate = 0
        total_agents_optimized = 0
        
        for record in history:
            result = record.get("result", {})
            summary = result.get("summary", {})
            improvements = summary.get("improvements", [])
            
            for improvement in improvements:
                if "整体改进率" in improvement:
                    try:
                        rate = float(improvement.split(":")[1].strip())
                        total_improvement_rate += rate
                    except:
                        pass
            
            total_agents_optimized += record.get("agents_count", 0)
        
        average_improvement_rate = total_improvement_rate / total_optimizations if total_optimizations > 0 else 0
        
        return {
            "total_optimizations": total_optimizations,
            "last_optimization": last_optimization,
            "average_improvement_rate": average_improvement_rate,
            "total_agents_optimized": total_agents_optimized
        }

def main():
    """主函数"""
    print("=== Agent自动优化调度器 ===")
    
    # 创建自动优化器
    auto_optimizer = AutoOptimizer()
    
    # 显示配置
    print("\n当前配置:")
    print(f"  启用状态: {auto_optimizer.config['enabled']}")
    print(f"  调度类型: {auto_optimizer.config['schedule']['type']}")
    print(f"  优化迭代次数: {auto_optimizer.config['optimization']['iterations']}")
    
    # 显示统计信息
    stats = auto_optimizer.get_optimization_statistics()
    print("\n优化统计:")
    print(f"  总优化次数: {stats['total_optimizations']}")
    print(f"  上次优化: {stats['last_optimization']}")
    print(f"  平均改进率: {stats['average_improvement_rate']:.2f}")
    print(f"  优化的Agent总数: {stats['total_agents_optimized']}")
    
    # 启动调度器
    auto_optimizer.start_scheduler()
    
    try:
        # 保持程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
        auto_optimizer.stop_scheduler()

if __name__ == "__main__":
    main()
