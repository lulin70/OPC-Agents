#!/usr/bin/env python3
"""
对话历史管理器

提供对话历史的存储、检索、搜索和管理功能。
"""

import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from data_storage import DatabaseManager, MessageRecord, ConversationRecord


class ConversationManager:
    """对话历史管理器"""
    
    def __init__(self, db_manager: DatabaseManager):
        """初始化对话历史管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 上下文窗口配置
        self.max_context_messages = 50  # 最大上下文消息数
        self.max_context_tokens = 4000  # 最大上下文token数
        self.summary_threshold = 30  # 触发摘要的消息数阈值
    
    def save_message_to_conversation(self, message: MessageRecord) -> bool:
        """将消息保存到对话历史
        
        Args:
            message: 消息记录对象
            
        Returns:
            是否保存成功
        """
        try:
            # 保存消息到数据库
            if not self.db_manager.save_message(message):
                return False
            
            # 更新或创建对话记录
            conversation = self._get_or_create_conversation(message.task_id)
            
            if conversation:
                # 添加消息ID到对话的消息列表
                messages_list = json.loads(conversation.messages)
                messages_list.append(message.id)
                
                # 更新对话记录
                conversation.messages = json.dumps(messages_list)
                conversation.updated_at = time.time()
                
                # 检查是否需要生成摘要
                if len(messages_list) >= self.summary_threshold:
                    self._generate_conversation_summary(conversation)
                
                # 保存对话记录
                self._save_conversation(conversation)
            
            self.logger.debug(f"消息已保存到对话历史: {message.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存消息到对话历史失败: {e}")
            return False
    
    def get_conversation_history(self, task_id: str, limit: int = None) -> List[MessageRecord]:
        """获取对话历史
        
        Args:
            task_id: 任务ID
            limit: 限制返回的消息数量（可选）
            
        Returns:
            消息记录列表
        """
        try:
            messages = self.db_manager.get_messages_by_task(task_id)
            
            # 如果指定了限制，返回最近的N条消息
            if limit and len(messages) > limit:
                return messages[-limit:]
            
            return messages
            
        except Exception as e:
            self.logger.error(f"获取对话历史失败: {e}")
            return []
    
    def search_conversations(self, query: str, task_id: str = None) -> List[Dict[str, Any]]:
        """搜索对话历史
        
        Args:
            query: 搜索关键词
            task_id: 任务ID（可选，如果指定则只搜索该任务的对话）
            
        Returns:
            搜索结果列表
        """
        try:
            results = []
            
            # 获取所有消息或指定任务的消息
            if task_id:
                messages = self.db_manager.get_messages_by_task(task_id)
            else:
                # 这里需要实现获取所有消息的方法
                messages = []
            
            # 搜索消息内容
            for message in messages:
                if query.lower() in message.content.lower():
                    results.append({
                        "message_id": message.id,
                        "task_id": message.task_id,
                        "content": message.content[:200],  # 截取前200个字符
                        "timestamp": message.timestamp,
                        "sender": message.sender,
                        "relevance_score": self._calculate_relevance(query, message.content)
                    })
            
            # 按相关性排序
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return results
            
        except Exception as e:
            self.logger.error(f"搜索对话历史失败: {e}")
            return []
    
    def get_context_window(self, task_id: str, max_messages: int = None) -> List[MessageRecord]:
        """获取上下文窗口
        
        Args:
            task_id: 任务ID
            max_messages: 最大消息数量（可选）
            
        Returns:
            上下文消息列表
        """
        try:
            if max_messages is None:
                max_messages = self.max_context_messages
            
            # 获取最近的N条消息作为上下文
            messages = self.get_conversation_history(task_id, limit=max_messages)
            
            # 如果消息数量超过阈值，考虑使用摘要
            if len(messages) >= self.summary_threshold:
                # 这里可以实现更智能的上下文选择策略
                # 例如：保留最近的N条消息 + 重要的历史消息
                pass
            
            return messages
            
        except Exception as e:
            self.logger.error(f"获取上下文窗口失败: {e}")
            return []
    
    def export_conversation(self, task_id: str, format: str = "json") -> Optional[str]:
        """导出对话历史
        
        Args:
            task_id: 任务ID
            format: 导出格式（json, txt, markdown）
            
        Returns:
            导出的内容字符串，如果失败则返回None
        """
        try:
            messages = self.get_conversation_history(task_id)
            
            if not messages:
                return None
            
            if format == "json":
                return json.dumps([msg.to_dict() for msg in messages], indent=2, ensure_ascii=False)
            
            elif format == "txt":
                lines = []
                for msg in messages:
                    timestamp = datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    lines.append(f"[{timestamp}] {msg.sender}: {msg.content}")
                return "\n".join(lines)
            
            elif format == "markdown":
                lines = ["# 对话历史\n"]
                for msg in messages:
                    timestamp = datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    lines.append(f"**{msg.sender}** ({timestamp}):\n{msg.content}\n")
                return "\n".join(lines)
            
            else:
                self.logger.error(f"不支持的导出格式: {format}")
                return None
            
        except Exception as e:
            self.logger.error(f"导出对话历史失败: {e}")
            return None
    
    def import_conversation(self, task_id: str, content: str, format: str = "json") -> bool:
        """导入对话历史
        
        Args:
            task_id: 任务ID
            content: 导入的内容
            format: 导入格式（json）
            
        Returns:
            是否导入成功
        """
        try:
            if format == "json":
                messages_data = json.loads(content)
                
                for msg_data in messages_data:
                    message = MessageRecord.from_dict(msg_data)
                    message.task_id = task_id  # 确保任务ID正确
                    self.save_message_to_conversation(message)
                
                self.logger.info(f"对话历史已导入: {len(messages_data)} 条消息")
                return True
            
            else:
                self.logger.error(f"不支持的导入格式: {format}")
                return False
            
        except Exception as e:
            self.logger.error(f"导入对话历史失败: {e}")
            return False
    
    def _get_or_create_conversation(self, task_id: str) -> Optional[ConversationRecord]:
        """获取或创建对话记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            对话记录对象
        """
        try:
            # 尝试获取现有对话记录
            # 这里需要实现get_conversation_by_task_id方法
            conversation = None
            
            if not conversation:
                # 创建新的对话记录
                conversation = ConversationRecord(
                    id=f"conv_{task_id}",
                    task_id=task_id,
                    messages="[]",
                    created_at=time.time(),
                    updated_at=time.time()
                )
            
            return conversation
            
        except Exception as e:
            self.logger.error(f"获取或创建对话记录失败: {e}")
            return None
    
    def _save_conversation(self, conversation: ConversationRecord) -> bool:
        """保存对话记录
        
        Args:
            conversation: 对话记录对象
            
        Returns:
            是否保存成功
        """
        try:
            # 这里需要实现save_conversation方法
            return True
            
        except Exception as e:
            self.logger.error(f"保存对话记录失败: {e}")
            return False
    
    def _generate_conversation_summary(self, conversation: ConversationRecord):
        """生成对话摘要
        
        Args:
            conversation: 对话记录对象
        """
        try:
            # 获取对话的所有消息
            messages_list = json.loads(conversation.messages)
            
            if not messages_list:
                return
            
            # 生成简单的摘要（这里可以集成AI来生成更智能的摘要）
            summary_parts = []
            message_count = len(messages_list)
            
            summary_parts.append(f"对话包含 {message_count} 条消息")
            
            # 统计各类型的消息数量
            user_messages = sum(1 for msg_id in messages_list if msg_id.startswith("user"))
            system_messages = sum(1 for msg_id in messages_list if msg_id.startswith("system"))
            
            if user_messages > 0:
                summary_parts.append(f"用户消息: {user_messages} 条")
            if system_messages > 0:
                summary_parts.append(f"系统消息: {system_messages} 条")
            
            conversation.summary = " | ".join(summary_parts)
            
        except Exception as e:
            self.logger.error(f"生成对话摘要失败: {e}")
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """计算相关性得分
        
        Args:
            query: 查询字符串
            content: 内容字符串
            
        Returns:
            相关性得分（0-1）
        """
        try:
            query_lower = query.lower()
            content_lower = content.lower()
            
            # 简单的相关性计算：查询词在内容中出现的次数
            count = content_lower.count(query_lower)
            
            # 归一化得分
            max_possible = len(content_lower.split()) / len(query_lower.split())
            score = min(count / max_possible, 1.0) if max_possible > 0 else 0.0
            
            return score
            
        except Exception as e:
            self.logger.error(f"计算相关性得分失败: {e}")
            return 0.0
