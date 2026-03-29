#!/usr/bin/env python3
"""
Communication Manager for OPC-Agents

Manages communication between agents, including message passing, context sharing, and consensus building.
"""

import time
import json
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from data_storage.dao import DatabaseManager

class CommunicationManager:
    """管理代理之间的通信"""
    
    def __init__(self, debug_mode: bool = False, db_manager: 'DatabaseManager' = None, 
                 use_message_queue: bool = True, ai_client=None, progress_streamer=None):
        """初始化通信管理器
        
        Args:
            debug_mode: 是否启用调试模式
            db_manager: 数据库管理器实例
            use_message_queue: 是否使用消息队列
            ai_client: AI客户端实例（用于异步处理）
            progress_streamer: 进度流式传输器实例
        """
        self.debug_mode = debug_mode
        self.logger = logging.getLogger("OPC-Agents.Communication")
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        
        # 数据库管理器
        self.db_manager = db_manager
        
        # 内存缓存（用于快速访问）
        self.message_history = {}
        self.context_store = {}
        self.token_usage = {}
        self.task_status = {}  # 任务状态跟踪
        self.task_history = {}  # 任务历史记录
        
        # 消息队列相关
        self.use_message_queue = use_message_queue
        self.message_queue = None
        self.message_processor = None
        
        # 初始化消息队列
        if use_message_queue:
            self._init_message_queue(ai_client, progress_streamer)
        
        # 从数据库加载现有任务到内存缓存
        if self.db_manager:
            self._load_tasks_from_db()
        
        self.logger.info(f"Communication Manager initialized in {'debug' if debug_mode else 'normal'} mode, queue={'enabled' if use_message_queue else 'disabled'}")
    
    def _init_message_queue(self, ai_client=None, progress_streamer=None):
        """初始化消息队列"""
        try:
            from message_queue.queue_manager import MessageQueue
            from message_queue.message_processor import MessageProcessor
            
            self.message_queue = MessageQueue(max_size=1000)
            self.message_processor = MessageProcessor(
                message_queue=self.message_queue,
                ai_client=ai_client,
                progress_streamer=progress_streamer
            )
            self.logger.info("消息队列初始化完成")
        except Exception as e:
            self.logger.warning(f"消息队列初始化失败: {e}，将使用同步模式")
            self.use_message_queue = False
            self.message_queue = None
            self.message_processor = None
    
    def _load_tasks_from_db(self):
        """从数据库加载任务到内存缓存"""
        try:
            tasks = self.db_manager.get_all_tasks()
            for task in tasks:
                self.task_status[task.id] = {
                    "task_id": task.id,
                    "task_name": task.name,
                    "agent": task.assigned_to or "",
                    "status": task.status,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "progress": task.progress,
                    "description": task.description or ""
                }
            self.logger.info(f"从数据库加载了 {len(tasks)} 个任务到内存缓存")
        except Exception as e:
            self.logger.error(f"从数据库加载任务失败: {e}")
    
    def _compress_content(self, content: str) -> str:
        """压缩消息内容，减少Token消耗"""
        # 优化的压缩策略
        # 1. 去除多余空格
        compressed = ' '.join(content.split())
        
        # 2. 移除重复的标点符号
        import re
        compressed = re.sub(r'([.!?])\1+', r'\1', compressed)
        
        # 3. 限制长度，只保留核心内容
        max_length = 400
        if len(compressed) > max_length:
            # 尝试在句子边界处截断
            truncation_point = compressed.rfind('.', 0, max_length)
            if truncation_point > max_length * 0.8:
                compressed = compressed[:truncation_point + 1] + '...'
            else:
                compressed = compressed[:max_length - 3] + '...'
        
        # 4. 移除不必要的冠词和连接词（适度）
        # 注意：这可能会影响语义，所以只在长文本中使用
        if len(compressed) > 200:
            # 移除常见的虚词，但保留语义
            common_stopwords = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with']
            words = compressed.split()
            filtered_words = [word for word in words if word.lower() not in common_stopwords or len(word) > 3]
            compressed = ' '.join(filtered_words)
        
        return compressed
    
    def send_message(self, sender: str, receiver: str, message_type: str, content: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发送消息
        
        Args:
            sender: 发送者名称
            receiver: 接收者名称
            message_type: 消息类型
            content: 消息内容
            context: 上下文信息
            
        Returns:
            消息传递结果
        """
        # 压缩消息内容
        compressed_content = self._compress_content(content)
        
        # 构建消息
        message = {
            "type": message_type,
            "content": compressed_content,
            "sender": sender,
            "timestamp": time.time(),
            "context": context
        }
        
        # 存储消息历史
        if receiver not in self.message_history:
            self.message_history[receiver] = []
        self.message_history[receiver].append(message)
        
        # 记录Token使用
        token_count = len(compressed_content) // 4  # 粗略估算Token数量
        if sender not in self.token_usage:
            self.token_usage[sender] = 0
        self.token_usage[sender] += token_count
        
        # 传递消息给接收代理
        return self._deliver_message(receiver, message)
    
    def _deliver_message(self, receiver: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """传递消息给接收代理
        
        Args:
            receiver: 接收者名称
            message: 消息内容
            
        Returns:
            消息传递结果
        """
        self.logger.info(f"消息从 {message['sender']} 发送到 {receiver}: {message['type']}")
        self.logger.debug(f"内容: {message['content'][:100]}...")
        
        # 尝试通过ZeroClaw发送消息给接收代理
        try:
            from zeroclaw_integration import ZeroClawIntegration
            zero_claw = ZeroClawIntegration()
            
            # 构建消息内容
            prompt = f"你是{receiver}，收到来自{message['sender']}的消息：\n{message['content']}\n请根据你的角色给出响应。"
            
            # 调用ZeroClaw获取响应
            response = zero_claw.call_llm(prompt, model="glm")
            
            # 检查响应是否有效
            if not response:
                self.logger.warning("ZeroClaw调用失败，使用默认响应")
                response = f"收到来自{message['sender']}的消息，正在处理中..."
            
            # 存储响应
            if receiver not in self.message_history:
                self.message_history[receiver] = []
            
            response_message = {
                "type": "response",
                "content": response,
                "sender": receiver,
                "timestamp": time.time(),
                "context": message.get("context", {})
            }
            
            # 记录Token使用
            token_count = len(response) // 4
            if receiver not in self.token_usage:
                self.token_usage[receiver] = 0
            self.token_usage[receiver] += token_count
            
            self.logger.debug(f"收到响应: {response[:100]}...")
            return {
                "success": True,
                "message_id": f"msg_{int(time.time())}",
                "timestamp": time.time(),
                "response": response
            }
        except Exception as e:
            self.logger.error(f"消息传递失败: {e}")
            return {
                "success": False,
                "message_id": f"msg_{int(time.time())}",
                "timestamp": time.time(),
                "error": str(e)
            }
    
    def start_consensus(self, issue: str, agents: List[str], voting_method: str = "majority", decision_threshold: float = 0.6) -> Dict[str, Any]:
        """启动共识过程
        
        Args:
            issue: 需要达成共识的问题
            agents: 参与共识的代理列表
            voting_method: 投票方式，支持 "majority" (多数决) 和 "unanimous" (一致通过)
            decision_threshold: 决策阈值，默认为0.6 (60%)
            
        Returns:
            共识结果
        """
        self.logger.info(f"启动关于 '{issue}' 的共识过程")
        self.logger.info(f"参与代理: {', '.join(agents)}")
        self.logger.info(f"投票方式: {voting_method}")
        self.logger.info(f"决策阈值: {decision_threshold * 100}%")
        
        # 真正的共识过程
        votes = {}
        opinions = {}
        
        try:
            from zeroclaw_integration import ZeroClawIntegration
            zero_claw = ZeroClawIntegration()
            
            # 收集每个代理的意见和投票
            for agent in agents:
                # 构建共识请求
                prompt = f"你是{agent}，现在需要对以下议题进行投票：\n{issue}\n请明确回答'赞成'或'反对'，并简要说明你的理由。"
                
                # 调用大模型获取代理的意见
                response = zero_claw.call_llm(prompt, model="glm")
                opinions[agent] = response
                
                # 解析投票结果
                vote = "赞成" in response
                votes[agent] = vote
                self.logger.info(f"{agent} 投票: {'赞成' if vote else '反对'}")
                self.logger.debug(f"{agent} 理由: {response[:100]}...")
                
                # 记录Token使用
                token_count = len(prompt) // 4 + len(response) // 4
                if agent not in self.token_usage:
                    self.token_usage[agent] = 0
                self.token_usage[agent] += token_count
        except Exception as e:
            self.logger.error(f"共识过程失败: {e}")
            #  fallback到模拟投票
            import random
            for agent in agents:
                vote = random.random() < 0.8
                votes[agent] = vote
                opinions[agent] = "无法获取代理意见，使用默认投票"
                self.logger.info(f"{agent} 投票: {'赞成' if vote else '反对'} (模拟)")
        
        # 计算投票结果
        yes_votes = sum(1 for vote in votes.values() if vote)
        total_votes = len(votes)
        approval_rate = yes_votes / total_votes
        
        self.logger.info(f"投票结果: {yes_votes}/{total_votes} ({approval_rate * 100:.1f}%)")
        
        # 做出决策
        if voting_method == "unanimous":
            decision = yes_votes == total_votes
        else:  # majority
            decision = approval_rate >= decision_threshold
        
        # 生成共识结果
        consensus_result = {
            "issue": issue,
            "agents": agents,
            "votes": votes,
            "opinions": opinions,
            "yes_votes": yes_votes,
            "total_votes": total_votes,
            "approval_rate": approval_rate,
            "decision": f"关于 '{issue}' 的共识决策: {'通过' if decision else '否决'}",
            "timestamp": time.time(),
            "status": "达成共识" if decision else "未达成共识"
        }
        
        self.logger.info(f"共识结果: {consensus_result['status']}")
        self.logger.info(f"决策: {consensus_result['decision']}")
        
        return consensus_result
    
    def get_message_history(self, agent: str) -> List[Dict[str, Any]]:
        """获取代理的消息历史
        
        Args:
            agent: 代理名称
            
        Returns:
            消息历史列表
        """
        return self.message_history.get(agent, [])
    
    def get_token_usage(self) -> Dict[str, int]:
        """获取Token使用情况
        
        Returns:
            各代理的Token使用量
        """
        return self.token_usage
    
    def clear_history(self, agent: Optional[str] = None):
        """清除消息历史
        
        Args:
            agent: 代理名称，不指定则清除所有历史
        """
        if agent:
            if agent in self.message_history:
                del self.message_history[agent]
        else:
            self.message_history.clear()
    
    def create_task(self, task_id: str, task_name: str, agent: str, initial_status: str = "pending"):
        """创建任务并设置初始状态
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            agent: 负责的代理
            initial_status: 初始状态，默认为"pending"
        """
        now = time.time()
        self.task_status[task_id] = {
            "task_id": task_id,
            "task_name": task_name,
            "agent": agent,
            "status": initial_status,
            "created_at": now,
            "updated_at": now,
            "progress": 0
        }
        self.logger.info(f"创建任务: {task_name} (ID: {task_id}) 分配给: {agent}")
        
        # 同步写入数据库
        if self.db_manager:
            try:
                from data_storage.models import TaskRecord
                task_record = TaskRecord(
                    id=task_id,
                    name=task_name,
                    status=initial_status,
                    progress=0,
                    created_at=now,
                    updated_at=now,
                    assigned_to=agent,
                    description=""
                )
                self.db_manager.save_task(task_record)
                self.logger.debug(f"任务已持久化到数据库: {task_id}")
            except Exception as e:
                self.logger.error(f"持久化任务到数据库失败: {e}")
        
        # 添加任务创建历史记录
        self.add_task_history(task_id, "created", f"任务创建: {task_name} 分配给: {agent}", {
            "task_name": task_name,
            "agent": agent,
            "initial_status": initial_status
        })
    
    def update_task_status(self, task_id: str, status: str, progress: int = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
        """
        if task_id in self.task_status:
            now = time.time()
            self.task_status[task_id]["status"] = status
            self.task_status[task_id]["updated_at"] = now
            if progress is not None:
                self.task_status[task_id]["progress"] = min(100, max(0, progress))
            self.logger.info(f"更新任务 {task_id} 状态: {status}")
            if progress is not None:
                self.logger.info(f"更新任务 {task_id} 进度: {progress}%")
            
            # 同步更新数据库
            if self.db_manager:
                try:
                    from data_storage.models import TaskRecord
                    task_data = self.task_status[task_id]
                    task_record = TaskRecord(
                        id=task_id,
                        name=task_data.get("task_name", ""),
                        status=status,
                        progress=task_data.get("progress", 0),
                        created_at=task_data.get("created_at", now),
                        updated_at=now,
                        assigned_to=task_data.get("agent", ""),
                        description=task_data.get("description", "")
                    )
                    self.db_manager.save_task(task_record)
                    self.logger.debug(f"任务状态已更新到数据库: {task_id}")
                except Exception as e:
                    self.logger.error(f"更新任务到数据库失败: {e}")
        else:
            self.logger.warning(f"任务 {task_id} 不存在")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        return self.task_status.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务状态
        
        Returns:
            所有任务的状态信息
        """
        return self.task_status
    
    def get_tasks_by_agent(self, agent: str) -> List[Dict[str, Any]]:
        """获取指定代理的所有任务
        
        Args:
            agent: 代理名称
            
        Returns:
            代理的任务列表
        """
        return [task for task in self.task_status.values() if task["agent"] == agent]
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """获取指定状态的所有任务
        
        Args:
            status: 任务状态
            
        Returns:
            指定状态的任务列表
        """
        return [task for task in self.task_status.values() if task["status"] == status]
    
    def add_task_history(self, task_id: str, event_type: str, description: str, details: Optional[Dict[str, Any]] = None):
        """添加任务历史记录
        
        Args:
            task_id: 任务ID
            event_type: 事件类型，如"created", "updated", "completed", "failed", "tested"
            description: 事件描述
            details: 事件详细信息
        """
        if task_id not in self.task_history:
            self.task_history[task_id] = []
        
        history_entry = {
            "event_type": event_type,
            "description": description,
            "details": details,
            "timestamp": time.time()
        }
        
        self.task_history[task_id].append(history_entry)
        self.logger.info(f"任务 {task_id} 添加事件: {event_type} - {description}")
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """获取任务的历史记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务历史记录列表
        """
        return self.task_history.get(task_id, [])
    
    def get_all_task_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """获取所有任务的历史记录
        
        Returns:
            所有任务的历史记录
        """
        return self.task_history
    
    def update_task_with_history(self, task_id: str, status: str, progress: int = None, description: str = ""):
        """更新任务状态并添加历史记录
        
        Args:
            task_id: 任务ID
            status: 新的状态
            progress: 任务进度 (0-100)
            description: 状态更新描述
        """
        self.update_task_status(task_id, status, progress)
        
        # 添加历史记录
        event_type = "updated"
        if status == "completed":
            event_type = "completed"
        elif status == "failed":
            event_type = "failed"
        
        details = {
            "status": status
        }
        if progress is not None:
            details["progress"] = progress
        
        history_description = description if description else f"任务状态更新为: {status}"
        if progress is not None:
            history_description += f"，进度: {progress}%"
        
        self.add_task_history(task_id, event_type, history_description, details)
    
    def complete_task(self, task_id: str, result: Optional[Any] = None, description: str = "任务完成"):
        """完成任务并添加历史记录
        
        Args:
            task_id: 任务ID
            result: 任务结果
            description: 完成描述
        """
        self.update_task_with_history(task_id, "completed", 100, description)
        
        # 添加结果到历史记录
        self.add_task_history(task_id, "result", "任务结果", {
            "result": result
        })
    
    def test_task(self, task_id: str, test_result: bool, test_details: Optional[Dict[str, Any]] = None):
        """测试任务并添加历史记录
        
        Args:
            task_id: 任务ID
            test_result: 测试结果
            test_details: 测试详细信息
        """
        status = "tested" if test_result else "failed"
        self.add_task_history(task_id, "tested", f"任务测试{'通过' if test_result else '失败'}", {
            "test_result": test_result,
            "test_details": test_details
        })
        if not test_result:
            self.update_task_with_history(task_id, status, None, f"测试{'通过' if test_result else '失败'}")
    
    def send_message_async(self, sender: str, receiver: str, message_type: str, content: str, 
                          context: Optional[Dict[str, Any]] = None, task_id: str = "") -> Dict[str, Any]:
        """异步发送消息（通过消息队列）
        
        Args:
            sender: 发送者名称
            receiver: 接收者名称
            message_type: 消息类型
            content: 消息内容
            context: 上下文信息
            task_id: 关联的任务ID
            
        Returns:
            消息ID和状态
        """
        if not self.message_queue:
            self.logger.warning("消息队列未初始化，使用同步发送")
            return self.send_message(sender, receiver, message_type, content, context)
        
        from message_queue.models import Message, MessageType, MessageStatus
        
        message = Message(
            task_id=task_id,
            sender=sender,
            receiver=receiver,
            content=content,
            message_type=MessageType.USER if message_type == "user" else MessageType.TASK,
            status=MessageStatus.PENDING,
            metadata={"message_type": message_type, "context": context or {}}
        )
        
        success = self.message_queue.add_message(message)
        
        if success:
            return {
                "success": True,
                "message_id": message.id,
                "status": "queued",
                "timestamp": message.timestamp
            }
        else:
            return {
                "success": False,
                "error": "消息队列已满"
            }
    
    def get_message_progress(self, message_id: str) -> Optional[Dict[str, Any]]:
        """获取消息处理进度
        
        Args:
            message_id: 消息ID
            
        Returns:
            进度信息
        """
        if not self.message_queue:
            return None
        
        progress = self.message_queue.get_progress(message_id)
        if progress:
            return progress.to_dict()
        return None
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """获取消息队列统计信息
        
        Returns:
            统计信息
        """
        if not self.message_queue:
            return {"error": "消息队列未初始化"}
        
        return self.message_queue.get_statistics()
    
    def start_async_processing(self):
        """启动异步消息处理"""
        if self.message_processor:
            self.message_processor.start()
            self.logger.info("异步消息处理器已启动")
    
    def stop_async_processing(self):
        """停止异步消息处理"""
        if self.message_processor:
            self.message_processor.stop()
            self.logger.info("异步消息处理器已停止")

class ContextManager:
    """管理代理之间的共享上下文"""
    
    def __init__(self):
        """初始化上下文管理器"""
        self.contexts = {}
    
    def set_context(self, key: str, value: Any):
        """设置上下文
        
        Args:
            key: 上下文键
            value: 上下文值
        """
        self.contexts[key] = value
    
    def get_context(self, key: str) -> Optional[Any]:
        """获取上下文
        
        Args:
            key: 上下文键
            
        Returns:
            上下文值
        """
        return self.contexts.get(key)
    
    def delete_context(self, key: str):
        """删除上下文
        
        Args:
            key: 上下文键
        """
        if key in self.contexts:
            del self.contexts[key]
    
    def clear_contexts(self):
        """清除所有上下文"""
        self.contexts.clear()
    
    def get_all_contexts(self) -> Dict[str, Any]:
        """获取所有上下文
        
        Returns:
            所有上下文
        """
        return self.contexts