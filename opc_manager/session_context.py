"""会话上下文管理器 v3.5 — P0-4 多轮对话支持

解决的核心问题：
- 用户无法基于前一轮结果进行迭代修正（"第三阶段时间太长，能改吗？" → 不能）
- 每次execute()都是独立的，没有历史记忆
- 无法引用之前的搜索结果或生成内容

=== 设计目标 ===
让OPC-Agents从"一次性工具"进化为"可对话的助手"：
- 第1轮: "帮我写Q2营销方案" → 生成方案A
- 第2轮: "第三阶段时间太长，能缩短到2周吗？" → 基于方案A修改
- 第3轮: "预算部分再加一个应急储备" → 再次修改

=== 核心架构 ===
  用户第N轮输入
    ↓
  SessionContextManager.get_context_for_llm()
    ↓ (返回前N-1轮的格式化历史)
  TaskEngineV3.execute(enriched_input=[历史] + [当前请求])
    ↓
  SessionContextManager.add_turn(第N轮用户输入, 助手回复, ...)
    ↓ (保存到内存)
  返回结果给用户 + 等待下一轮输入

=== 内存安全 ===
  - 最大20轮（可通过max_turns配置）
  - 超过上限时报错或自动截断旧轮次
  - 每轮数据约1KB，20轮总计约20KB（可忽略）

=== 版本历史 ===
  v3.5.0: 初始版本，支持多轮对话/上下文构建/历史管理
"""
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TurnRole(Enum):
    """对话角色枚举"""
    USER = 'user'
    ASSISTANT = 'assistant'


@dataclass
class ConversationTurn:
    """单轮对话的数据容器
    
    设计意图：
    - 记录完整的交互信息（用户输入+助手回复+元数据）
    - 支持时间戳追踪和来源追溯
    - 轻量级设计，避免序列化开销
    """
    turn_id: int
    role: TurnRole
    content: str
    timestamp: float = field(default_factory=time.time)
    task_type: Optional[str] = None
    filepath: Optional[str] = None
    sources: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionContextManager:
    """轻量级会话上下文管理器 — 支持多轮对话
    
    核心能力：
    1. 多轮记录：add_turn()保存每轮的完整交互
    2. 上下文构建：get_context_for_llm()生成格式化的历史供LLM使用
    3. 快速访问：get_last_result()获取最近一轮的助手回复
    4. 历史管理：get_full_history()/get_history_summary()
    5. 安全限制：max_turns防止内存膨胀
    
    使用示例：
        >>> session = SessionContextManager(max_turns=20)
        >>> 
        >>> # 第1轮
        >>> session.add_turn(
        ...     user_input="帮我写Q2营销方案",
        ...     assistant_response="已生成Q2营销方案，包含3个阶段...",
        ...     sources=[{'title': '营销策略', 'url': 'http://...'}],
        ... )
        >>> 
        >>> # 第2轮（迭代修正）
        >>> context = session.get_context_for_llm(max_turns=3)
        >>> print(context)  # 包含第1轮的历史
        >>> 
        >>> session.add_turn(
        ...     user_input="第三阶段时间太长，能缩短到2周吗？",
        ...     assistant_response="已调整第三阶段为2周敏捷迭代...",
        ... )
        >>> 
        >>> last = session.get_last_result()
        >>> print(last['response'])  # "已调整第三阶段为2周敏捷迭代..."
    
    线程安全：
    - 设计为无状态或使用外部锁（调用方负责）
    - 推荐在AsyncTaskExecutor的单线程worker中使用
    - 或在Streamlit的session_state中作为单一实例使用
    
    与TaskEngineV3集成：
        # 在app.py中的典型用法：
        if 'session_ctx' not in st.session_state:
            st.session_state.session_ctx = SessionContextManager()
        
        ctx = st.session_state.session_ctx
        
        # 执行前获取上下文
        if ctx.get_turn_count() > 0:
            enriched_prompt = f"[历史对话]\n{ctx.get_context_for_llm()}\n\n[当前]\n{prompt}"
        else:
            enriched_prompt = prompt
        
        result = engine.execute(enriched_prompt)
        
        # 执行后保存本轮
        if result.success:
            ctx.add_turn(
                user_input=prompt,
                assistant_response=result.content,
                task_type=result.task_type.value,
                filepath=result_filepath,
                sources=result.sources or [],
            )
    """

    def __init__(self, max_turns: int = 20):
        """初始化会话管理器
        
        Args:
            max_turns: 最大允许的对话轮数（默认20，防内存膨胀）
        """
        self.max_turns = max_turns
        self._turns: List[ConversationTurn] = []
        self._next_turn_id = 1

        logger.info(
            f"[SessionContextManager] 初始化完成: "
            f"max_turns={max_turns}"
        )

    def add_turn(
        self,
        user_input: str,
        assistant_response: str,
        task_type: Optional[str] = None,
        filepath: Optional[str] = None,
        sources: List[Dict] = None,
        **metadata
    ) -> ConversationTurn:
        """记录一轮完整对话
        
        每轮包含两条记录：
        - user角色：用户的原始输入
        - assistant角色：系统的回复内容
        
        Args:
            user_input: 用户本轮的输入文本
            assistant_response: 系统本轮的回复内容
            task_type: 任务类型（如'info_collection', 'content_generation'等）
            filepath: 生成的文件路径（如有）
            sources: 搜索结果来源列表（如有）
            **metadata: 额外的元数据键值对
            
        Returns:
            ConversationTurn: 创建的用户轮次记录
            
        Raises:
            ValueError: 超过max_turns限制时抛出
            
        使用示例：
            >>> turn = session.add_turn(
            ...     user_input="帮我写报告",
            ...     assistant_response="已生成报告...",
            ...     task_type='report',
            ...     filepath='/tmp/report.md',
            ...     sources=[{'title': '资料1', 'url': 'http://...'}],
            ... )
            >>> print(f"第{turn.turn_id}轮已记录")
        """
        if len(self._turns) >= self.max_turns * 2:
            raise ValueError(
                f"已达最大轮次限制({self.max_turns}轮)，"
                f"请开始新会话"
            )

        user_turn = ConversationTurn(
            turn_id=self._next_turn_id,
            role=TurnRole.USER,
            content=user_input.strip(),
            task_type=task_type,
            metadata={'filepath': filepath} if filepath else {},
        )

        assistant_turn = ConversationTurn(
            turn_id=self._next_turn_id,
            role=TurnRole.ASSISTANT,
            content=assistant_response.strip(),
            task_type=task_type,
            filepath=filepath,
            sources=sources or [],
            metadata={
                'sources_count': len(sources or []),
                'response_length': len(assistant_response),
                **metadata,
            },
        )

        self._turns.append(user_turn)
        self._turns.append(assistant_turn)
        self._next_turn_id += 1

        logger.debug(
            f"[SessionContextManager] 已记录第{user_turn.turn_id}轮: "
            f"user={len(user_input)}字, assistant={len(assistant_response)}字"
        )

        return user_turn

    def get_context_for_llm(self, max_turns: int = 5) -> str:
        """构建供LLM使用的上下文摘要（最近N轮）
        
        格式化规则：
        - 按轮次分组展示（User → Assistant 配对）
        - 最近N轮优先（最相关的上下文）
        - 包含任务类型和关键元数据
        - 截断过长内容（每轮最多500字符）
        
        Args:
            max_turns: 包含的最大轮数（默认5，控制token消耗）
            
        Returns:
            格式化的上下文字符串，可直接拼接到Prompt前面
            
        输出格式示例：
            [对话历史 - 共3轮]
            
            === 第1轮 (2026-04-16 10:30) ===
            👤 用户: 帮我写Q2营销方案
            🤖 助手: 已生成Q2营销方案，包含3个阶段...
                 📎 参考资料: 3条 | 📄 文件: /tmp/q2_plan.md
            
            === 第2轮 (2026-04-16 10:35) ===
            👤 用户: 第三阶段时间太长，能缩短到2周吗？
            🤖 助手: 已调整第三阶段为2周敏捷迭代...
        """
        if not self._turns:
            return ""

        paired_turns = self._group_by_turn_id()

        recent_turns = paired_turns[-max_turns:] if len(paired_turns) > max_turns else paired_turns

        lines = [f"[对话历史 - 共{len(recent_turns)}轮]\n"]

        for turn_data in recent_turns:
            turn_num = turn_data['turn_id']
            timestamp_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(turn_data.get('timestamp', time.time())))

            lines.append(f"\n=== 第{turn_num}轮 ({timestamp_str}) ===\n")

            user_content = turn_data.get('user_content', '')
            if user_content:
                truncated_user = user_content[:300] + ('...' if len(user_content) > 300 else '')
                lines.append(f"👤 用户: {truncated_user}")

            asst_content = turn_data.get('assistant_content', '')
            if asst_content:
                truncated_asst = asst_content[:500] + ('...' if len(asst_content) > 500 else '')
                lines.append(f"🤖 助手: {truncated_asst}")

            meta_parts = []
            if turn_data.get('task_type'):
                meta_parts.append(f"类型:{turn_data['task_type']}")
            if turn_data.get('filepath'):
                meta_parts.append(f"📄 文件: {turn_data['filepath'][:60]}")
            if turn_data.get('sources_count', 0) > 0:
                meta_parts.append(f"📎 参考:{turn_data['sources_count']}条")

            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")

        return '\n'.join(lines)

    def get_last_result(self) -> Optional[Dict[str, Any]]:
        """获取最后一次助手回复（用于快速访问最新结果）
        
        这是迭代场景的核心接口：
        - 用户说"修改XXX"时，系统需要知道上次生成了什么
        - 返回完整的助手回复内容和元数据
        
        Returns:
            包含以下字段的字典（如果没有历史则返回None）：
            - response: 最后一次助手回复的完整文本
            - turn_id: 所属轮次ID
            - task_type: 任务类型
            - filepath: 生成的文件路径（如有）
            - sources: 参考资料列表（如有）
            - timestamp: 回复时间戳
        """
        assistant_turns = [
            t for t in self._turns
            if t.role == TurnRole.ASSISTANT
        ]

        if not assistant_turns:
            return None

        last = assistant_turns[-1]
        return {
            'response': last.content,
            'turn_id': last.turn_id,
            'task_type': last.task_type,
            'filepath': last.filepath,
            'sources': last.sources,
            'timestamp': last.timestamp,
            'metadata': last.metadata,
        }

    def get_full_history(self) -> List[Dict[str, Any]]:
        """获取完整的对话历史（所有轮次）
        
        Returns:
            对话历史列表，每个元素是一轮的详细信息
        """
        return [
            {
                'turn_id': t.turn_id,
                'role': t.role.value,
                'content': t.content,
                'timestamp': t.timestamp,
                'task_type': t.task_type,
                'filepath': t.filepath,
                'sources_count': len(t.sources),
            }
            for t in self._turns
        ]

    def get_history_summary(self) -> str:
        """获取本次会话的简明摘要（一行概览）
        
        用于日志记录或调试时的快速查看。
        
        Returns:
            摘要字符串，如："共3轮(6条消息), 最新: 第3轮用户输入"
        """
        total_messages = len(self._turns)
        total_turns = self._next_turn_id - 1

        if total_turns == 0:
            return "空会话（无对话记录）"

        last_role = self._turns[-1].role.value if self._turns else 'none'
        last_preview = self._turns[-1].content[:50] + ('...' if len(self._turns[-1].content) > 50 else '')

        return (
            f"共{total_turns}轮({total_messages}条消息), "
            f"最新: 第{self._turns[-1].turn_id}轮{last_role}: {last_preview}"
        )

    def get_turn_count(self) -> int:
        """获取当前已完成的总轮次数"""
        return self._next_turn_id - 1

    def clear(self):
        """清空所有会话历史（开始新会话）"""
        count = len(self._turns)
        self._turns.clear()
        self._next_turn_id = 1

        logger.info(f"[SessionContextManager] 会话已清空（删除了{count // 2}轮历史）")

    def _group_by_turn_id(self) -> List[Dict[str, Any]]:
        """将按时间顺序的turns列表按turn_id分组"""
        groups = {}
        for turn in self._turns:
            tid = turn.turn_id
            if tid not in groups:
                groups[tid] = {'turn_id': tid, 'timestamp': turn.timestamp}

            if turn.role == TurnRole.USER:
                groups[tid]['user_content'] = turn.content
            elif turn.role == TurnRole.ASSISTANT:
                groups[tid]['assistant_content'] = turn.content
                groups[tid]['task_type'] = turn.task_type
                groups[tid]['filepath'] = turn.filepath
                groups[tid]['sources_count'] = len(turn.sources)

        return list(groups.values())
