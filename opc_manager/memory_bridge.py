"""MemoryBridge — CarryMem 适配层，为 OPC-Agents 提供跨会话持久记忆 + 规则约束。

职责：
1. 任务执行前：从 CarryMem 检索相关记忆+规则，注入到 prompt 上下文
2. 任务执行后：将对话摘要存入 CarryMem 长期记忆
3. 规则引擎：匹配场景规则，注入行为约束到策略脑
4. 失败经验：反思脑判定质量不佳时，提炼失败教训为规则
5. 降级策略：CarryMem 不可用时静默降级，不影响核心功能

配置（环境变量）：
    CARRYMEM_ENABLED=true          # 是否启用记忆功能
    CARRYMEM_DB_PATH=~/.opc-agents/memory.db  # 数据库路径
    CARRYMEM_MAX_MEMORIES=10       # 每次检索最大记忆数
    CARRYMEM_MAX_TOKENS=2000       # 记忆注入 token 预算
    CARRYMEM_MAX_RULES=5           # 每次注入最大规则数
    CARRYMEM_VECTOR_SEARCH=false   # 是否启用向量搜索

依赖：
    pip install opc-agents[memory]  # 安装 CarryMem 可选依赖
"""

import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# 运行时检测 CarryMem 是否可用
_CARRYMEM_AVAILABLE = False
try:
    from carrymem import CarryMem
    _CARRYMEM_AVAILABLE = True
except ImportError:
    pass


def is_memory_enabled() -> bool:
    """检查记忆功能是否启用（环境变量 + CarryMem 可用性）"""
    if not _CARRYMEM_AVAILABLE:
        return False
    return os.environ.get("CARRYMEM_ENABLED", "false").lower() in ("true", "1", "yes")


def _get_db_path() -> str:
    """获取 CarryMem 数据库路径"""
    default_path = os.path.expanduser("~/.opc-agents/memory.db")
    return os.environ.get("CARRYMEM_DB_PATH", default_path)


class MemoryBridge:
    """CarryMem 适配层 — 隔离 API 细节，提供降级策略。

    使用方式：
        bridge = MemoryBridge()
        # 任务前：注入记忆+规则上下文
        extra = bridge.build_context("帮我写营销方案")
        rules = bridge.match_rules("帮我写营销方案")
        # 任务后：存储记忆
        bridge.remember("帮我写营销方案", result_content, {"success": True})
        # 反思失败时：提炼失败教训
        bridge.record_failure("帮我写营销方案", "方案太泛，缺少具体数据")
    """

    def __init__(self):
        self._cm = None
        self._rule_engine = None
        self._enabled = False
        self._memory_count = 0

        if not is_memory_enabled():
            logger.debug("[MemoryBridge] 记忆功能未启用 (CARRYMEM_ENABLED != true 或 CarryMem 未安装)")
            return

        try:
            db_path = _get_db_path()
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            self._cm = CarryMem(storage="sqlite", db_path=db_path)
            self._enabled = True
            logger.info("[MemoryBridge] 初始化成功，数据库: %s", db_path)
        except Exception as e:
            logger.warning("[MemoryBridge] 初始化失败，将无记忆运行: %s", e)
            self._cm = None

    @property
    def enabled(self) -> bool:
        """记忆功能是否已启用"""
        return self._enabled

    @property
    def memory_count(self) -> int:
        """当前记忆条目数"""
        if not self._enabled or not self._cm:
            return 0
        try:
            result = self._cm.recall_memories(limit=1)
            return result.get("total", 0) if isinstance(result, dict) else len(result) if isinstance(result, list) else 0
        except Exception:
            return self._memory_count

    @property
    def rule_engine(self):
        """懒加载 RuleEngine"""
        if not self._enabled or not self._cm:
            return None
        if self._rule_engine is None:
            try:
                self._rule_engine = self._cm.rule_engine
            except Exception as e:
                logger.warning("[MemoryBridge] RuleEngine 加载失败: %s", e)
        return self._rule_engine

    def build_context(self, user_input: str) -> str:
        """任务前注入记忆上下文（含规则）。

        Args:
            user_input: 用户输入的原始 prompt

        Returns:
            注入到 prompt 前的记忆上下文字符串，失败时返回空字符串
        """
        if not self._enabled or not self._cm:
            return ""

        max_memories = int(os.environ.get("CARRYMEM_MAX_MEMORIES", "10"))
        max_tokens = int(os.environ.get("CARRYMEM_MAX_TOKENS", "2000"))

        try:
            result = self._cm.build_context(
                context=user_input,
                max_memories=max_memories,
                max_tokens=max_tokens,
            )

            if isinstance(result, dict):
                system_prompt = result.get("system_prompt", "")
                if system_prompt:
                    return f"[记忆上下文]\n{system_prompt}\n[/记忆上下文]"
            return ""
        except Exception as e:
            logger.warning("[MemoryBridge] build_context 失败: %s", e)
            return ""

    def match_rules(self, scene: str, max_rules: int = 0) -> List[Dict[str, Any]]:
        """匹配场景规则，返回规则列表。

        Args:
            scene: 场景描述（通常是用户输入）
            max_rules: 最大返回规则数，0 表示使用环境变量

        Returns:
            规则字典列表，每项含 trigger, action, rule_type, override, score
        """
        if not self._enabled:
            return []

        if max_rules <= 0:
            max_rules = int(os.environ.get("CARRYMEM_MAX_RULES", "5"))

        engine = self.rule_engine
        if engine is None:
            return []

        try:
            matches = engine.match(scene, limit=max_rules, increment_count=True)
            return [
                {
                    "trigger": m.rule.trigger,
                    "action": m.rule.action,
                    "rule_type": m.rule.rule_type.value if hasattr(m.rule.rule_type, 'value') else str(m.rule.rule_type),
                    "override": m.rule.override,
                    "score": m.score,
                    "match_type": m.match_type,
                }
                for m in matches
            ]
        except Exception as e:
            logger.warning("[MemoryBridge] match_rules 失败: %s", e)
            return []

    def inject_rules_prompt(self, scene: str, max_rules: int = 0, max_tokens: int = 500) -> str:
        """生成规则注入的 prompt 片段（用于策略脑规划）。

        Args:
            scene: 场景描述
            max_rules: 最大规则数
            max_tokens: token 预算

        Returns:
            规则约束 prompt 片段，失败时返回空字符串
        """
        if not self._enabled:
            return ""

        if max_rules <= 0:
            max_rules = int(os.environ.get("CARRYMEM_MAX_RULES", "5"))

        engine = self.rule_engine
        if engine is None:
            return ""

        try:
            return engine.inject(
                scene,
                format="anchored",
                max_rules=max_rules,
                context_budget_tokens=max_tokens,
            )
        except Exception as e:
            logger.warning("[MemoryBridge] inject_rules_prompt 失败: %s", e)
            return ""

    def remember(self, user_input: str, result: str, evaluation: Optional[Dict[str, Any]] = None) -> None:
        """任务后存储记忆。

        Args:
            user_input: 用户输入
            result: AI 执行结果
            evaluation: 可选的评估信息（如 success, quality_score 等）
        """
        if not self._enabled or not self._cm:
            return

        try:
            # 存储用户输入
            store_result = self._cm.classify_and_remember(user_input)
            self._memory_count += 1

            # 自动确认规则建议（如果有的话）
            if isinstance(store_result, dict) and store_result.get("auto_rules"):
                for suggestion in store_result["auto_rules"][:2]:
                    self._try_auto_add_rule(suggestion)

            # 如果结果质量不佳，存储为纠正记忆
            if evaluation and isinstance(evaluation, dict):
                quality_score = evaluation.get("quality_score", 1.0)
                if quality_score < 0.5:
                    correction = f"纠正：{user_input} 的结果质量不佳（评分 {quality_score}），需要改进"
                    self._cm.classify_and_remember(correction)
                    self._memory_count += 1

            logger.debug("[MemoryBridge] 记忆已存储，当前总数: %d", self._memory_count)
        except Exception as e:
            logger.warning("[MemoryBridge] 记忆存储失败: %s", e)

    def record_failure(self, user_input: str, failure_reason: str, quality_score: float = 0.0) -> None:
        """反思脑判定质量不佳时，记录失败经验。

        Args:
            user_input: 原始用户输入
            failure_reason: 失败原因描述
            quality_score: 质量评分
        """
        if not self._enabled or not self._cm:
            return

        try:
            # 存储失败记忆
            failure_msg = f"失败经验：{user_input} — {failure_reason}（评分 {quality_score}）"
            self._cm.classify_and_remember(failure_msg)
            self._memory_count += 1

            # 尝试提取失败教训为规则
            engine = self.rule_engine
            if engine is not None:
                try:
                    memories = self._cm.recall_memories(limit=50)
                    if isinstance(memories, dict):
                        memories = memories.get("memories", [])
                    result = engine.extract_failure_lessons(memories)
                    lessons_found = result.get("lessons_found", 0)
                    if lessons_found > 0:
                        logger.info("[MemoryBridge] 发现 %d 条失败教训待审核", lessons_found)
                except Exception as e:
                    logger.debug("[MemoryBridge] 失败教训提取跳过: %s", e)

            logger.debug("[MemoryBridge] 失败经验已记录")
        except Exception as e:
            logger.warning("[MemoryBridge] 失败经验记录失败: %s", e)

    def get_rules_for_context(self, user_input: str) -> Dict[str, Any]:
        """获取用于策略脑 context 的规则信息。

        返回可直接注入到 AgentLoop._phase_plan 的 context 字典。

        Args:
            user_input: 用户输入

        Returns:
            {"rules_prompt": str, "rules": list, "has_hard_rules": bool}
        """
        if not self._enabled:
            return {"rules_prompt": "", "rules": [], "has_hard_rules": False}

        rules = self.match_rules(user_input)
        rules_prompt = self.inject_rules_prompt(user_input)
        has_hard = any(r.get("override", False) for r in rules)

        return {
            "rules_prompt": rules_prompt,
            "rules": rules,
            "has_hard_rules": has_hard,
        }

    def get_pending_lessons(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取待审核的失败教训（用于 UI 展示）"""
        if not self._enabled:
            return []
        engine = self.rule_engine
        if engine is None:
            return []
        try:
            pending = engine.list_pending_lessons(limit=limit)
            return [
                {
                    "id": str(lesson.get("id", "")),
                    "lesson": lesson.get("lesson", ""),
                    "trigger_hint": lesson.get("trigger_hint", ""),
                    "action_hint": lesson.get("action_hint", ""),
                    "failure_signal": str(lesson.get("failure_signal", "")),
                    "confidence": str(lesson.get("confidence", "")),
                }
                for lesson in pending
            ]
        except Exception as e:
            logger.debug("[MemoryBridge] 获取待审核教训失败: %s", e)
            return []

    def accept_lesson(self, audit_id: str, note: str = "") -> Optional[str]:
        """接受一条失败教训（自动创建 avoid 规则）"""
        if not self._enabled:
            return None
        engine = self.rule_engine
        if engine is None:
            return None
        try:
            rule_id = engine.accept_lesson(audit_id=audit_id, note=note)
            logger.info("[MemoryBridge] 接受教训，创建规则: %s", rule_id)
            return str(rule_id)
        except Exception as e:
            logger.warning("[MemoryBridge] 接受教训失败: %s", e)
            return None

    def reject_lesson(self, audit_id: str, note: str = "") -> bool:
        """拒绝一条失败教训"""
        if not self._enabled:
            return False
        engine = self.rule_engine
        if engine is None:
            return False
        try:
            engine.reject_lesson(audit_id=audit_id, note=note)
            return True
        except Exception as e:
            logger.warning("[MemoryBridge] 拒绝教训失败: %s", e)
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取记忆系统状态（用于 UI 展示）"""
        if not self._enabled:
            return {
                "enabled": False,
                "available": _CARRYMEM_AVAILABLE,
                "memory_count": 0,
                "rule_count": 0,
                "pending_lessons": 0,
                "db_path": _get_db_path() if _CARRYMEM_AVAILABLE else None,
            }

        rule_count = 0
        pending_count = 0
        try:
            engine = self.rule_engine
            if engine:
                stats = engine.get_stats()
                rule_count = stats.get("total_active", 0) if isinstance(stats, dict) else 0
                lesson_stats = engine.get_lesson_stats()
                pending_count = lesson_stats.get("pending", 0) if isinstance(lesson_stats, dict) else 0
        except Exception:
            pass

        return {
            "enabled": True,
            "available": True,
            "memory_count": self.memory_count,
            "rule_count": rule_count,
            "pending_lessons": pending_count,
            "db_path": _get_db_path(),
        }

    def close(self):
        """清理资源"""
        if self._cm:
            try:
                if hasattr(self._cm, 'close'):
                    self._cm.close()
            except Exception:
                pass

    def _try_auto_add_rule(self, suggestion: Any) -> None:
        """尝试自动添加规则建议（仅添加软规则，硬规则需用户确认）"""
        if not suggestion:
            return
        engine = self.rule_engine
        if engine is None:
            return
        try:
            if isinstance(suggestion, dict):
                engine.add_rule(
                    trigger=suggestion.get("trigger", ""),
                    action=suggestion.get("action", ""),
                    rule_type=suggestion.get("rule_type", "prefer"),
                    override=False,  # 自动添加的规则默认为软规则
                    derived_from="auto_promotion",
                )
            elif hasattr(suggestion, 'trigger') and hasattr(suggestion, 'action'):
                engine.add_rule(
                    trigger=suggestion.trigger,
                    action=suggestion.action,
                    rule_type=suggestion.rule_type if hasattr(suggestion, 'rule_type') else "prefer",
                    override=False,
                    derived_from="auto_promotion",
                )
        except Exception as e:
            logger.debug("[MemoryBridge] 自动添加规则跳过: %s", e)


# 模块级单例（懒初始化）
_instance: Optional[MemoryBridge] = None


def get_memory_bridge() -> MemoryBridge:
    """获取 MemoryBridge 单例"""
    global _instance
    if _instance is None:
        _instance = MemoryBridge()
    return _instance
