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
    CarryMem = None  # type: ignore


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

    def __init__(self) -> None:
        self._cm: Optional[Any] = None
        self._rule_engine: Optional[Any] = None
        self._enabled = False
        self._memory_count = 0

        if not is_memory_enabled():
            logger.debug(
                "[MemoryBridge] 记忆功能未启用 (CARRYMEM_ENABLED != true 或 CarryMem 未安装)"
            )
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
        """当前记忆条目数（缓存，remember 时自增）"""
        if not self._enabled or not self._cm:
            return self._memory_count
        if self._memory_count > 0:
            return self._memory_count
        try:
            result = self._cm.recall_memories(limit=1)
            count = (
                result.get("total", 0)
                if isinstance(result, dict)
                else len(result) if isinstance(result, list) else 0
            )
            self._memory_count = count
            return count
        except Exception as e:
            logger.warning("[MemoryBridge] Memory count failed: %s", e)
            return self._memory_count

    @property
    def rule_engine(self) -> Any:
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
                    "rule_type": (
                        m.rule.rule_type.value
                        if hasattr(m.rule.rule_type, "value")
                        else str(m.rule.rule_type)
                    ),
                    "override": m.rule.override,
                    "score": m.score,
                    "match_type": m.match_type,
                }
                for m in matches
            ]
        except Exception as e:
            logger.warning("[MemoryBridge] match_rules 失败: %s", e)
            return []

    def inject_rules_prompt(
        self, scene: str, max_rules: int = 0, max_tokens: int = 500
    ) -> str:
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

    def remember(
        self, user_input: str, result: str, evaluation: Optional[Dict[str, Any]] = None
    ) -> None:
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

    def record_failure(
        self, user_input: str, failure_reason: str, quality_score: float = 0.0
    ) -> None:
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
            failure_msg = (
                f"失败经验：{user_input} — {failure_reason}（评分 {quality_score}）"
            )
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
                        logger.info(
                            "[MemoryBridge] 发现 %d 条失败教训待审核", lessons_found
                        )
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
                rule_count = (
                    stats.get("total_active", 0) if isinstance(stats, dict) else 0
                )
                lesson_stats = engine.get_lesson_stats()
                pending_count = (
                    lesson_stats.get("pending", 0)
                    if isinstance(lesson_stats, dict)
                    else 0
                )
        except Exception as e:
            logger.warning("[MemoryBridge] Memory search failed: %s", e)

        return {
            "enabled": True,
            "available": True,
            "memory_count": self.memory_count,
            "rule_count": rule_count,
            "pending_lessons": pending_count,
            "db_path": _get_db_path(),
        }

    def close(self) -> None:
        """清理资源"""
        if self._cm:
            try:
                if hasattr(self._cm, "close"):
                    self._cm.close()
            except Exception as e:
                logger.warning("[MemoryBridge] CarryMem close failed: %s", e)

    def get_flywheel_status(self) -> Dict[str, Any]:
        """获取飞轮效应状态 — 衡量"越用越懂你"的程度

        飞轮指标：
        - 记忆深度: 记忆条目数（越多越懂用户偏好）
        - 规则密度: 活跃规则数（越多约束越精准）
        - 经验沉淀: 已确认的失败教训数
        - 知识覆盖: 知识库文档数
        - 飞轮等级: 综合评分对应的等级
        """
        if not self._enabled:
            return {"level": 0, "grade": "未启用", "metrics": {}}

        metrics = {
            "memory_count": self.memory_count,
            "rule_count": 0,
            "confirmed_lessons": 0,
            "auto_rules": 0,
        }

        try:
            engine = self.rule_engine
            if engine:
                stats = engine.get_stats()
                if isinstance(stats, dict):
                    metrics["rule_count"] = stats.get("total_active", 0)
                    metrics["auto_rules"] = stats.get("auto_promotion", 0)

                lesson_stats = engine.get_lesson_stats()
                if isinstance(lesson_stats, dict):
                    metrics["confirmed_lessons"] = lesson_stats.get("accepted", 0)
        except Exception as e:
            logger.warning("[MemoryBridge] Lesson stats failed: %s", e)

        # 计算飞轮等级 (0-5)
        score = 0.0
        score += min(metrics["memory_count"] / 20, 1.0) * 2  # 记忆深度 (0-2分)
        score += min(metrics["rule_count"] / 10, 1.0) * 2  # 规则密度 (0-2分)
        score += min(metrics["confirmed_lessons"] / 5, 1.0) * 1  # 经验沉淀 (0-1分)

        level = min(round(score), 5)
        grades = {
            0: " 新手",
            1: " 熟悉",
            2: " 精通",
            3: " 专家",
            4: " 大师",
            5: " 传奇",
        }

        return {
            "level": level,
            "grade": grades.get(level, " 新手"),
            "score": round(score, 1),
            "metrics": metrics,
        }

    def suggest_skills(self, user_input: str) -> List[str]:
        """基于记忆和规则，推荐可能适合的技能

        飞轮效应：用得越多，推荐越精准
        """
        if not self._enabled:
            return []

        suggestions = []
        try:
            # 从记忆中提取技能相关关键词
            rules = self.match_rules(user_input, max_rules=3)
            for r in rules:
                action = r.get("action", "")
                if "营销" in action or "marketing" in action.lower():
                    suggestions.append("opc_market_research")
                elif "创意" in action or "creative" in action.lower():
                    suggestions.append("opc_creative_planning")
                elif "增长" in action or "growth" in action.lower():
                    suggestions.append("opc_growth_hacker")
                elif "法律" in action or "legal" in action.lower():
                    suggestions.append("opc_legal_advisor")
                elif "PRD" in action or "产品" in action:
                    suggestions.append("opc_prd_generation")
        except Exception as e:
            logger.warning("[MemoryBridge] Suggestion generation failed: %s", e)

        return list(set(suggestions))[:3]

    def cleanup_stale_memories(self, max_age_days: int = 90) -> int:
        """清理过时的记忆 — 飞轮维护

        Args:
            max_age_days: 最大保留天数

        Returns:
            清理的记忆条目数
        """
        if not self._enabled or not self._cm:
            return 0
        try:
            # CarryMem 的 consolidate 功能会自动处理
            if hasattr(self._cm, "consolidate"):
                result = self._cm.consolidate()
                if isinstance(result, dict):
                    return result.get("cleaned", 0)
            return 0
        except Exception as e:
            logger.debug("[MemoryBridge] 清理跳过: %s", e)
            return 0

    def export_user_data(self) -> Dict[str, Any]:
        """导出用户全部数据 — 数据可携带性（飞轮护城河的保障）

        Returns:
            包含记忆、规则、统计的完整导出
        """
        if not self._enabled:
            return {"memories": [], "rules": [], "flywheel": {}}

        export: Dict[str, Any] = {
            "memories": [],
            "rules": [],
            "flywheel": self.get_flywheel_status(),
        }

        try:
            # 导出记忆
            if self._cm:
                mem_result = self._cm.recall_memories(limit=1000)
                if isinstance(mem_result, dict):
                    export["memories"] = mem_result.get("memories", [])
                elif isinstance(mem_result, list):
                    export["memories"] = mem_result
        except MemoryError:
            logger.error(
                "[MemoryBridge] MemoryError during export — data too large, returning partial results"
            )
            export["memories"] = export.get("memories", [])[:100]
            export["_warning"] = "Export truncated due to memory constraints"
        except Exception as e:
            logger.warning("[MemoryBridge] Memory export failed: %s", e)

        try:
            # 导出规则
            engine = self.rule_engine
            if engine:
                rules_result = engine.export_rules()
                if isinstance(rules_result, dict):
                    export["rules"] = rules_result.get("rules", [])
        except MemoryError:
            logger.error(
                "[MemoryBridge] MemoryError during rules export — returning partial results"
            )
            export["rules"] = export.get("rules", [])[:50]
            export["_warning"] = "Export truncated due to memory constraints"
        except Exception as e:
            logger.warning("[MemoryBridge] Rules export failed: %s", e)

        return export

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
            elif hasattr(suggestion, "trigger") and hasattr(suggestion, "action"):
                engine.add_rule(
                    trigger=suggestion.trigger,
                    action=suggestion.action,
                    rule_type=(
                        suggestion.rule_type
                        if hasattr(suggestion, "rule_type")
                        else "prefer"
                    ),
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
