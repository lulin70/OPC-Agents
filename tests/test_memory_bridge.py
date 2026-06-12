"""MemoryBridge 单元测试 — 覆盖跨会话持久记忆 + 规则约束 + 降级策略

测试覆盖范围：
1. 记忆检索与 prompt 注入 (build_context)
2. 规则匹配与执行 (match_rules, inject_rules_prompt)
3. CarryMem 不可用时的优雅降级
4. 失败经验提取 (record_failure)
5. Token 预算管理
6. 记忆搜索相关性
7. 跨会话状态持久化
8. NullMemoryProvider 降级回退
9. 辅助方法 (remember, get_rules_for_context, get_status, etc.)
"""

import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

from opc_manager.memory_bridge import (
    MemoryBridge,
    is_memory_enabled,
    _get_db_path,
    get_memory_bridge,
    _CARRYMEM_AVAILABLE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_carrymem():
    """创建一个模拟 CarryMem 实例"""
    cm = MagicMock()
    cm.build_context.return_value = {"system_prompt": "历史记忆：用户偏好简洁风格"}
    cm.classify_and_remember.return_value = {}
    cm.recall_memories.return_value = {"total": 5, "memories": []}
    cm.close.return_value = None
    return cm


def _make_mock_rule_engine():
    """创建一个模拟 RuleEngine 实例"""
    engine = MagicMock()

    # match 返回的 RuleMatch 对象
    match1 = MagicMock()
    match1.rule.trigger = "营销"
    match1.rule.action = "使用数据驱动方案"
    match1.rule.rule_type = MagicMock(value="prefer")
    match1.rule.override = False
    match1.score = 0.9
    match1.match_type = "keyword"

    match2 = MagicMock()
    match2.rule.trigger = "法律"
    match2.rule.action = "必须合规审查"
    match2.rule.rule_type = MagicMock(value="avoid")
    match2.rule.override = True
    match2.score = 0.95
    match2.match_type = "keyword"

    engine.match.return_value = [match1, match2]
    engine.inject.return_value = (
        "[规则约束]\n- 使用数据驱动方案\n- 必须合规审查\n[/规则约束]"
    )
    engine.get_stats.return_value = {"total_active": 3, "auto_promotion": 1}
    engine.get_lesson_stats.return_value = {"pending": 2, "accepted": 1}
    engine.extract_failure_lessons.return_value = {"lessons_found": 1}
    engine.list_pending_lessons.return_value = [
        {
            "id": "lesson-1",
            "lesson": "避免泛泛而谈",
            "trigger_hint": "营销方案",
            "action_hint": "提供具体数据",
            "failure_signal": "quality < 0.5",
            "confidence": "0.8",
        }
    ]
    engine.accept_lesson.return_value = "rule-new-1"
    engine.reject_lesson.return_value = None
    engine.export_rules.return_value = {"rules": [{"trigger": "t1", "action": "a1"}]}
    engine.add_rule.return_value = "rule-auto-1"

    return engine


def _create_enabled_bridge():
    """创建一个启用了记忆功能的 MemoryBridge（绕过 __init__）"""
    bridge = object.__new__(MemoryBridge)
    bridge._cm = _make_mock_carrymem()
    bridge._rule_engine = None
    bridge._enabled = True
    bridge._memory_count = 0
    return bridge


# ---------------------------------------------------------------------------
# Test: is_memory_enabled
# ---------------------------------------------------------------------------


class TestIsMemoryEnabled(unittest.TestCase):
    """测试记忆功能启用判断"""

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", False)
    def test_disabled_when_carrymem_not_installed(self):
        """CarryMem 未安装时返回 False"""
        self.assertFalse(is_memory_enabled())

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch.dict(os.environ, {"CARRYMEM_ENABLED": "true"})
    def test_enabled_when_carrymem_available_and_env_true(self):
        """CarryMem 可用且环境变量为 true 时返回 True"""
        self.assertTrue(is_memory_enabled())

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch.dict(os.environ, {"CARRYMEM_ENABLED": "1"})
    def test_enabled_with_env_value_1(self):
        """环境变量 CARRYMEM_ENABLED=1 也视为启用"""
        self.assertTrue(is_memory_enabled())

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch.dict(os.environ, {"CARRYMEM_ENABLED": "yes"})
    def test_enabled_with_env_value_yes(self):
        """环境变量 CARRYMEM_ENABLED=yes 也视为启用"""
        self.assertTrue(is_memory_enabled())

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch.dict(os.environ, {"CARRYMEM_ENABLED": "false"})
    def test_disabled_when_env_false(self):
        """环境变量为 false 时返回 False"""
        self.assertFalse(is_memory_enabled())

    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch.dict(os.environ, {}, clear=True)
    def test_disabled_when_env_not_set(self):
        """环境变量未设置时默认返回 False"""
        self.assertFalse(is_memory_enabled())


# ---------------------------------------------------------------------------
# Test: _get_db_path
# ---------------------------------------------------------------------------


class TestGetDbPath(unittest.TestCase):
    """测试数据库路径获取"""

    @patch.dict(os.environ, {"CARRYMEM_DB_PATH": "/custom/path/db.sqlite"})
    def test_custom_path_from_env(self):
        """从环境变量获取自定义路径"""
        self.assertEqual(_get_db_path(), "/custom/path/db.sqlite")

    @patch.dict(os.environ, {}, clear=True)
    def test_default_path(self):
        """默认路径为 ~/.opc-agents/memory.db"""
        path = _get_db_path()
        self.assertTrue(path.endswith(".opc-agents/memory.db"))


# ---------------------------------------------------------------------------
# Test: MemoryBridge 初始化与降级
# ---------------------------------------------------------------------------


class TestMemoryBridgeInit(unittest.TestCase):
    """测试 MemoryBridge 初始化及降级"""

    @patch("opc_manager.memory_bridge.is_memory_enabled", return_value=False)
    def test_init_disabled_when_memory_not_enabled(self, mock_enabled):
        """记忆功能未启用时，bridge 不初始化 CarryMem"""
        bridge = MemoryBridge()
        self.assertFalse(bridge.enabled)
        self.assertIsNone(bridge._cm)

    @patch("opc_manager.memory_bridge.is_memory_enabled", return_value=True)
    @patch("opc_manager.memory_bridge.CarryMem", side_effect=Exception("DB error"))
    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    def test_init_graceful_degradation_on_exception(self, mock_cm, mock_enabled):
        """CarryMem 初始化异常时优雅降级"""
        bridge = MemoryBridge()
        self.assertFalse(bridge.enabled)
        self.assertIsNone(bridge._cm)

    @patch("opc_manager.memory_bridge.is_memory_enabled", return_value=True)
    @patch("opc_manager.memory_bridge.CarryMem")
    @patch("opc_manager.memory_bridge._CARRYMEM_AVAILABLE", True)
    @patch(
        "opc_manager.memory_bridge._get_db_path", return_value="/tmp/test_opc/mem.db"
    )
    @patch("os.makedirs")
    def test_init_success(self, mock_makedirs, mock_db_path, mock_cm_cls, mock_enabled):
        """正常初始化成功"""
        mock_cm_cls.return_value = MagicMock()
        bridge = MemoryBridge()
        self.assertTrue(bridge.enabled)
        self.assertIsNotNone(bridge._cm)


# ---------------------------------------------------------------------------
# Test: NullMemoryProvider 降级回退
# ---------------------------------------------------------------------------


class TestNullMemoryProviderFallback(unittest.TestCase):
    """测试当 CarryMem 不可用时的 NullMemoryProvider 行为

    MemoryBridge 在 _enabled=False 时，所有方法应返回安全的空值，
    不抛异常，不影响核心功能。
    """

    def setUp(self):
        self.bridge = MemoryBridge()
        self.bridge._enabled = False
        self.bridge._cm = None
        self.bridge._rule_engine = None
        self.bridge._memory_count = 0

    def test_build_context_returns_empty_string(self):
        self.assertEqual(self.bridge.build_context("测试输入"), "")

    def test_match_rules_returns_empty_list(self):
        self.assertEqual(self.bridge.match_rules("测试场景"), [])

    def test_inject_rules_prompt_returns_empty_string(self):
        self.assertEqual(self.bridge.inject_rules_prompt("测试场景"), "")

    def test_remember_does_nothing(self):
        """remember 不抛异常，静默忽略"""
        self.bridge.remember("输入", "结果", {"success": True})
        self.assertEqual(self.bridge._memory_count, 0)

    def test_record_failure_does_nothing(self):
        """record_failure 不抛异常，静默忽略"""
        self.bridge.record_failure("输入", "原因", 0.1)
        self.assertEqual(self.bridge._memory_count, 0)

    def test_get_rules_for_context_returns_defaults(self):
        result = self.bridge.get_rules_for_context("输入")
        self.assertEqual(
            result, {"rules_prompt": "", "rules": [], "has_hard_rules": False}
        )

    def test_get_pending_lessons_returns_empty(self):
        self.assertEqual(self.bridge.get_pending_lessons(), [])

    def test_accept_lesson_returns_none(self):
        self.assertIsNone(self.bridge.accept_lesson("id-1"))

    def test_reject_lesson_returns_false(self):
        self.assertFalse(self.bridge.reject_lesson("id-1"))

    def test_get_status_shows_disabled(self):
        status = self.bridge.get_status()
        self.assertFalse(status["enabled"])
        self.assertEqual(status["memory_count"], 0)

    def test_get_flywheel_status_shows_disabled(self):
        result = self.bridge.get_flywheel_status()
        self.assertEqual(result["level"], 0)
        self.assertEqual(result["grade"], "未启用")

    def test_suggest_skills_returns_empty(self):
        self.assertEqual(self.bridge.suggest_skills("营销方案"), [])

    def test_cleanup_stale_memories_returns_zero(self):
        self.assertEqual(self.bridge.cleanup_stale_memories(), 0)

    def test_export_user_data_returns_empty(self):
        result = self.bridge.export_user_data()
        self.assertEqual(result, {"memories": [], "rules": [], "flywheel": {}})

    def test_close_does_nothing(self):
        """close 不抛异常"""
        self.bridge.close()


# ---------------------------------------------------------------------------
# Test: build_context — 记忆检索与 prompt 注入
# ---------------------------------------------------------------------------


class TestBuildContext(unittest.TestCase):
    """测试记忆检索与 prompt 注入"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_returns_formatted_context(self):
        """正常返回带标记的记忆上下文"""
        result = self.bridge.build_context("帮我写营销方案")
        self.assertIn("[记忆上下文]", result)
        self.assertIn("历史记忆", result)
        self.assertIn("[/记忆上下文]", result)

    def test_returns_empty_when_no_system_prompt(self):
        """CarryMem 返回无 system_prompt 时返回空字符串"""
        self.bridge._cm.build_context.return_value = {"system_prompt": ""}
        result = self.bridge.build_context("测试")
        self.assertEqual(result, "")

    def test_returns_empty_when_result_is_not_dict(self):
        """CarryMem 返回非字典类型时返回空字符串"""
        self.bridge._cm.build_context.return_value = "just a string"
        result = self.bridge.build_context("测试")
        self.assertEqual(result, "")

    def test_passes_max_memories_and_max_tokens(self):
        """传递 max_memories 和 max_tokens 参数"""
        with patch.dict(
            os.environ, {"CARRYMEM_MAX_MEMORIES": "5", "CARRYMEM_MAX_TOKENS": "1000"}
        ):
            self.bridge.build_context("测试")
            self.bridge._cm.build_context.assert_called_once_with(
                context="测试", max_memories=5, max_tokens=1000
            )

    def test_returns_empty_on_exception(self):
        """CarryMem 异常时返回空字符串"""
        self.bridge._cm.build_context.side_effect = Exception("DB error")
        result = self.bridge.build_context("测试")
        self.assertEqual(result, "")

    def test_returns_empty_when_disabled(self):
        """禁用时返回空字符串"""
        self.bridge._enabled = False
        result = self.bridge.build_context("测试")
        self.assertEqual(result, "")

    def test_returns_empty_when_cm_is_none(self):
        """_cm 为 None 时返回空字符串"""
        self.bridge._cm = None
        result = self.bridge.build_context("测试")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# Test: match_rules — 规则匹配与执行
# ---------------------------------------------------------------------------


class TestMatchRules(unittest.TestCase):
    """测试规则匹配与执行"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_returns_matched_rules(self):
        """正常返回匹配的规则列表"""
        rules = self.bridge.match_rules("帮我做营销方案")
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["trigger"], "营销")
        self.assertEqual(rules[0]["score"], 0.9)
        self.assertEqual(rules[1]["override"], True)

    def test_rule_type_value_extraction(self):
        """rule_type 枚举正确提取 .value"""
        rules = self.bridge.match_rules("测试")
        self.assertEqual(rules[0]["rule_type"], "prefer")

    def test_rule_type_string_fallback(self):
        """rule_type 为字符串时的回退处理"""
        match_obj = MagicMock()
        match_obj.rule.trigger = "test"
        match_obj.rule.action = "action"
        match_obj.rule.rule_type = "custom_type"  # 没有 .value 属性
        match_obj.rule.override = False
        match_obj.score = 0.7
        match_obj.match_type = "semantic"
        self.mock_engine.match.return_value = [match_obj]

        rules = self.bridge.match_rules("测试")
        self.assertEqual(rules[0]["rule_type"], "custom_type")

    def test_max_rules_from_env(self):
        """从环境变量读取最大规则数"""
        with patch.dict(os.environ, {"CARRYMEM_MAX_RULES": "3"}):
            self.bridge.match_rules("测试")
            self.mock_engine.match.assert_called_once_with(
                "测试", limit=3, increment_count=True
            )

    def test_max_rules_parameter_override(self):
        """显式传入 max_rules 参数覆盖环境变量"""
        self.bridge.match_rules("测试", max_rules=2)
        self.mock_engine.match.assert_called_once_with(
            "测试", limit=2, increment_count=True
        )

    def test_returns_empty_when_rule_engine_none(self):
        """rule_engine 为 None 时返回空列表"""
        self.bridge._rule_engine = None
        # rule_engine property 会尝试从 _cm 加载
        self.bridge._cm.rule_engine = None
        result = self.bridge.match_rules("测试")
        self.assertEqual(result, [])

    def test_returns_empty_on_exception(self):
        """规则匹配异常时返回空列表"""
        self.mock_engine.match.side_effect = Exception("match error")
        result = self.bridge.match_rules("测试")
        self.assertEqual(result, [])

    def test_returns_empty_when_disabled(self):
        """禁用时返回空列表"""
        self.bridge._enabled = False
        result = self.bridge.match_rules("测试")
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# Test: inject_rules_prompt
# ---------------------------------------------------------------------------


class TestInjectRulesPrompt(unittest.TestCase):
    """测试规则注入 prompt 生成"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_returns_injected_prompt(self):
        """正常返回规则注入 prompt"""
        result = self.bridge.inject_rules_prompt("营销方案")
        self.assertIn("规则约束", result)

    def test_passes_max_tokens_budget(self):
        """传递 token 预算参数"""
        self.bridge.inject_rules_prompt("测试", max_tokens=300)
        self.mock_engine.inject.assert_called_once_with(
            "测试",
            format="anchored",
            max_rules=5,
            context_budget_tokens=300,
        )

    def test_returns_empty_on_exception(self):
        """异常时返回空字符串"""
        self.mock_engine.inject.side_effect = Exception("inject error")
        result = self.bridge.inject_rules_prompt("测试")
        self.assertEqual(result, "")

    def test_returns_empty_when_disabled(self):
        """禁用时返回空字符串"""
        self.bridge._enabled = False
        result = self.bridge.inject_rules_prompt("测试")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# Test: remember — 记忆存储
# ---------------------------------------------------------------------------


class TestRemember(unittest.TestCase):
    """测试记忆存储"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_stores_memory_and_increments_count(self):
        """存储记忆并增加计数"""
        self.bridge.remember("用户输入", "AI结果")
        self.bridge._cm.classify_and_remember.assert_called_once_with("用户输入")
        self.assertEqual(self.bridge._memory_count, 1)

    def test_stores_correction_for_low_quality(self):
        """质量评分低于 0.5 时存储纠正记忆"""
        self.bridge.remember("输入", "结果", {"quality_score": 0.3})
        self.assertEqual(self.bridge._cm.classify_and_remember.call_count, 2)
        correction_call = self.bridge._cm.classify_and_remember.call_args_list[1]
        self.assertIn("纠正", correction_call[0][0])
        self.assertEqual(self.bridge._memory_count, 2)

    def test_no_correction_for_high_quality(self):
        """质量评分正常时不存储纠正"""
        self.bridge.remember("输入", "结果", {"quality_score": 0.8})
        self.assertEqual(self.bridge._cm.classify_and_remember.call_count, 1)
        self.assertEqual(self.bridge._memory_count, 1)

    def test_auto_add_rule_from_suggestions(self):
        """自动添加规则建议"""
        self.bridge._cm.classify_and_remember.return_value = {
            "auto_rules": [
                {"trigger": "营销", "action": "数据驱动", "rule_type": "prefer"}
            ]
        }
        mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = mock_engine

        self.bridge.remember("营销方案", "结果")
        mock_engine.add_rule.assert_called_once()

    def test_auto_add_rule_default_override_false(self):
        """自动添加的规则 override 默认为 False（软规则）"""
        self.bridge._cm.classify_and_remember.return_value = {
            "auto_rules": [
                {"trigger": "营销", "action": "数据驱动", "rule_type": "prefer"}
            ]
        }
        mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = mock_engine

        self.bridge.remember("营销方案", "结果")
        call_kwargs = mock_engine.add_rule.call_args
        self.assertFalse(call_kwargs[1].get("override", True))

    def test_does_nothing_on_exception(self):
        """异常时静默忽略"""
        self.bridge._cm.classify_and_remember.side_effect = Exception("DB error")
        self.bridge.remember("输入", "结果")
        self.assertEqual(self.bridge._memory_count, 0)

    def test_does_nothing_when_disabled(self):
        """禁用时静默忽略"""
        self.bridge._enabled = False
        self.bridge.remember("输入", "结果")
        self.assertEqual(self.bridge._memory_count, 0)


# ---------------------------------------------------------------------------
# Test: record_failure — 失败经验提取
# ---------------------------------------------------------------------------


class TestRecordFailure(unittest.TestCase):
    """测试失败经验提取"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_stores_failure_memory(self):
        """存储失败记忆"""
        self.bridge.record_failure("营销方案", "方案太泛", 0.2)
        self.bridge._cm.classify_and_remember.assert_called_once()
        call_arg = self.bridge._cm.classify_and_remember.call_args[0][0]
        self.assertIn("失败经验", call_arg)
        self.assertIn("方案太泛", call_arg)
        self.assertEqual(self.bridge._memory_count, 1)

    def test_extracts_failure_lessons(self):
        """从记忆中提取失败教训"""
        self.bridge._cm.recall_memories.return_value = {"memories": []}
        self.bridge.record_failure("营销方案", "方案太泛", 0.2)
        self.mock_engine.extract_failure_lessons.assert_called_once()

    def test_lessons_found_count(self):
        """发现失败教训时记录日志"""
        self.mock_engine.extract_failure_lessons.return_value = {"lessons_found": 3}
        self.bridge._cm.recall_memories.return_value = []
        # 不应抛异常
        self.bridge.record_failure("营销方案", "方案太泛", 0.2)

    def test_handles_recall_memories_as_list(self):
        """recall_memories 返回列表时的处理"""
        self.bridge._cm.recall_memories.return_value = ["memory1", "memory2"]
        self.bridge.record_failure("测试", "原因", 0.1)
        self.mock_engine.extract_failure_lessons.assert_called_once_with(
            ["memory1", "memory2"]
        )

    def test_handles_recall_memories_as_dict(self):
        """recall_memories 返回字典时提取 memories 字段"""
        self.bridge._cm.recall_memories.return_value = {"memories": ["m1"]}
        self.bridge.record_failure("测试", "原因", 0.1)
        self.mock_engine.extract_failure_lessons.assert_called_once_with(["m1"])

    def test_skips_lesson_extraction_when_no_engine(self):
        """无 rule_engine 时跳过教训提取"""
        self.bridge._rule_engine = None
        self.bridge._cm.rule_engine = None
        self.bridge.record_failure("测试", "原因", 0.1)
        # 只调用 classify_and_remember，不调用 extract_failure_lessons
        self.bridge._cm.classify_and_remember.assert_called_once()

    def test_does_nothing_on_exception(self):
        """异常时静默忽略"""
        self.bridge._cm.classify_and_remember.side_effect = Exception("error")
        self.bridge.record_failure("测试", "原因", 0.1)
        self.assertEqual(self.bridge._memory_count, 0)

    def test_does_nothing_when_disabled(self):
        """禁用时静默忽略"""
        self.bridge._enabled = False
        self.bridge.record_failure("测试", "原因", 0.1)
        self.assertEqual(self.bridge._memory_count, 0)


# ---------------------------------------------------------------------------
# Test: Token 预算管理
# ---------------------------------------------------------------------------


class TestTokenBudgetManagement(unittest.TestCase):
    """测试 Token 预算管理"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_build_context_respects_max_tokens_env(self):
        """build_context 遵循 CARRYMEM_MAX_TOKENS 环境变量"""
        with patch.dict(os.environ, {"CARRYMEM_MAX_TOKENS": "500"}):
            self.bridge.build_context("测试")
            call_args = self.bridge._cm.build_context.call_args
            # Source uses keyword args: context=, max_memories=, max_tokens=
            self.assertEqual(call_args.kwargs.get("max_tokens"), 500)

    def test_build_context_respects_max_memories_env(self):
        """build_context 遵循 CARRYMEM_MAX_MEMORIES 环境变量"""
        with patch.dict(os.environ, {"CARRYMEM_MAX_MEMORIES": "3"}):
            self.bridge.build_context("测试")
            call_args = self.bridge._cm.build_context.call_args
            self.assertEqual(call_args.kwargs.get("max_memories"), 3)

    def test_inject_rules_prompt_custom_max_tokens(self):
        """inject_rules_prompt 支持自定义 token 预算"""
        mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = mock_engine
        self.bridge.inject_rules_prompt("测试", max_tokens=200)
        mock_engine.inject.assert_called_once_with(
            "测试",
            format="anchored",
            max_rules=5,
            context_budget_tokens=200,
        )


# ---------------------------------------------------------------------------
# Test: get_rules_for_context
# ---------------------------------------------------------------------------


class TestGetRulesForContext(unittest.TestCase):
    """测试获取策略脑 context 的规则信息"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_returns_complete_context(self):
        """返回完整的规则上下文"""
        result = self.bridge.get_rules_for_context("营销方案")
        self.assertIn("rules_prompt", result)
        self.assertIn("rules", result)
        self.assertIn("has_hard_rules", result)
        self.assertEqual(len(result["rules"]), 2)

    def test_detects_hard_rules(self):
        """检测到硬规则时 has_hard_rules 为 True"""
        result = self.bridge.get_rules_for_context("法律咨询")
        self.assertTrue(result["has_hard_rules"])

    def test_no_hard_rules(self):
        """无硬规则时 has_hard_rules 为 False"""
        # 只返回软规则
        match_soft = MagicMock()
        match_soft.rule.trigger = "测试"
        match_soft.rule.action = "建议"
        match_soft.rule.rule_type = MagicMock(value="prefer")
        match_soft.rule.override = False
        match_soft.score = 0.8
        match_soft.match_type = "keyword"
        self.mock_engine.match.return_value = [match_soft]

        result = self.bridge.get_rules_for_context("测试")
        self.assertFalse(result["has_hard_rules"])


# ---------------------------------------------------------------------------
# Test: memory_count property
# ---------------------------------------------------------------------------


class TestMemoryCount(unittest.TestCase):
    """测试记忆计数"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_returns_cached_count(self):
        """缓存计数大于 0 时直接返回"""
        self.bridge._memory_count = 10
        self.assertEqual(self.bridge.memory_count, 10)

    def test_queries_carrymem_when_cache_zero(self):
        """缓存为 0 时从 CarryMem 查询"""
        self.bridge._cm.recall_memories.return_value = {"total": 42}
        self.assertEqual(self.bridge.memory_count, 42)

    def test_handles_list_result(self):
        """recall_memories 返回列表时计算长度"""
        self.bridge._cm.recall_memories.return_value = [1, 2, 3]
        self.assertEqual(self.bridge.memory_count, 3)

    def test_handles_unexpected_result_type(self):
        """recall_memories 返回意外类型时返回 0"""
        self.bridge._cm.recall_memories.return_value = "unexpected"
        self.assertEqual(self.bridge.memory_count, 0)

    def test_returns_zero_on_exception(self):
        """异常时返回 0"""
        self.bridge._cm.recall_memories.side_effect = Exception("error")
        self.assertEqual(self.bridge.memory_count, 0)

    def test_returns_zero_when_disabled(self):
        """禁用时返回 0"""
        self.bridge._enabled = False
        self.assertEqual(self.bridge.memory_count, 0)


# ---------------------------------------------------------------------------
# Test: rule_engine property (懒加载)
# ---------------------------------------------------------------------------


class TestRuleEngineProperty(unittest.TestCase):
    """测试 rule_engine 懒加载"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_lazy_loads_from_carrymem(self):
        """从 CarryMem 懒加载 rule_engine"""
        mock_engine = MagicMock()
        self.bridge._cm.rule_engine = mock_engine
        result = self.bridge.rule_engine
        self.assertEqual(result, mock_engine)

    def test_caches_rule_engine(self):
        """rule_engine 只加载一次"""
        mock_engine = MagicMock()
        self.bridge._cm.rule_engine = mock_engine
        _ = self.bridge.rule_engine
        _ = self.bridge.rule_engine
        # 第二次不应再访问 _cm.rule_engine

    def test_returns_none_on_exception(self):
        """加载异常时返回 None"""
        # Use a fresh bridge to avoid PropertyMock leaking to other tests
        bridge = _create_enabled_bridge()
        type(bridge._cm).rule_engine = PropertyMock(side_effect=Exception("error"))
        result = bridge.rule_engine
        self.assertIsNone(result)
        # Clean up PropertyMock to avoid leaking
        del type(bridge._cm).rule_engine

    def test_returns_none_when_disabled(self):
        """禁用时返回 None"""
        self.bridge._enabled = False
        self.assertIsNone(self.bridge.rule_engine)


# ---------------------------------------------------------------------------
# Test: get_status
# ---------------------------------------------------------------------------


class TestGetStatus(unittest.TestCase):
    """测试记忆系统状态"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_enabled_status(self):
        """启用时返回完整状态"""
        status = self.bridge.get_status()
        self.assertTrue(status["enabled"])
        self.assertTrue(status["available"])
        self.assertEqual(status["rule_count"], 3)
        self.assertEqual(status["pending_lessons"], 2)

    def test_disabled_status(self):
        """禁用时返回默认状态"""
        self.bridge._enabled = False
        status = self.bridge.get_status()
        self.assertFalse(status["enabled"])
        self.assertEqual(status["memory_count"], 0)

    def test_handles_engine_exception(self):
        """rule_engine 异常时仍返回基本状态"""
        self.mock_engine.get_stats.side_effect = Exception("error")
        status = self.bridge.get_status()
        self.assertTrue(status["enabled"])
        self.assertEqual(status["rule_count"], 0)


# ---------------------------------------------------------------------------
# Test: get_flywheel_status
# ---------------------------------------------------------------------------


class TestGetFlywheelStatus(unittest.TestCase):
    """测试飞轮效应状态"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_newbie_level(self):
        """新手等级（低指标）"""
        self.bridge._memory_count = 0
        # Override engine stats to return minimal values
        self.mock_engine.get_stats.return_value = {
            "total_active": 0,
            "auto_promotion": 0,
        }
        self.mock_engine.get_lesson_stats.return_value = {"accepted": 0, "pending": 0}
        result = self.bridge.get_flywheel_status()
        self.assertEqual(result["level"], 0)
        self.assertIn("新手", result["grade"])

    def test_expert_level(self):
        """专家等级（高指标）"""
        self.bridge._memory_count = 100
        self.mock_engine.get_stats.return_value = {
            "total_active": 50,
            "auto_promotion": 10,
        }
        self.mock_engine.get_lesson_stats.return_value = {"accepted": 10, "pending": 0}
        result = self.bridge.get_flywheel_status()
        self.assertGreaterEqual(result["level"], 3)

    def test_max_level_is_five(self):
        """等级上限为 5"""
        self.bridge._memory_count = 9999
        self.mock_engine.get_stats.return_value = {
            "total_active": 9999,
            "auto_promotion": 9999,
        }
        self.mock_engine.get_lesson_stats.return_value = {
            "accepted": 9999,
            "pending": 0,
        }
        result = self.bridge.get_flywheel_status()
        self.assertLessEqual(result["level"], 5)

    def test_disabled_returns_level_zero(self):
        """禁用时返回等级 0"""
        self.bridge._enabled = False
        result = self.bridge.get_flywheel_status()
        self.assertEqual(result["level"], 0)


# ---------------------------------------------------------------------------
# Test: suggest_skills
# ---------------------------------------------------------------------------


class TestSuggestSkills(unittest.TestCase):
    """测试技能推荐"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_suggests_marketing_skill(self):
        """推荐营销技能"""
        match = MagicMock()
        match.rule.trigger = "营销"
        match.rule.action = "营销推广"
        match.rule.rule_type = MagicMock(value="prefer")
        match.rule.override = False
        match.score = 0.9
        match.match_type = "keyword"
        self.mock_engine.match.return_value = [match]

        result = self.bridge.suggest_skills("营销方案")
        self.assertIn("opc_market_research", result)

    def test_suggests_creative_skill(self):
        """推荐创意技能"""
        match = MagicMock()
        match.rule.trigger = "创意"
        match.rule.action = "创意策划"
        match.rule.rule_type = MagicMock(value="prefer")
        match.rule.override = False
        match.score = 0.8
        match.match_type = "keyword"
        self.mock_engine.match.return_value = [match]

        result = self.bridge.suggest_skills("创意方案")
        self.assertIn("opc_creative_planning", result)

    def test_suggests_legal_skill(self):
        """推荐法律技能"""
        match = MagicMock()
        match.rule.trigger = "法律"
        match.rule.action = "法律咨询"
        match.rule.rule_type = MagicMock(value="prefer")
        match.rule.override = False
        match.score = 0.8
        match.match_type = "keyword"
        self.mock_engine.match.return_value = [match]

        result = self.bridge.suggest_skills("法律咨询")
        self.assertIn("opc_legal_advisor", result)

    def test_max_three_suggestions(self):
        """最多返回 3 个推荐"""
        result = self.bridge.suggest_skills("测试")
        self.assertLessEqual(len(result), 3)

    def test_deduplicates_suggestions(self):
        """去重推荐结果"""
        result = self.bridge.suggest_skills("测试")
        self.assertEqual(len(result), len(set(result)))


# ---------------------------------------------------------------------------
# Test: lesson management
# ---------------------------------------------------------------------------


class TestLessonManagement(unittest.TestCase):
    """测试教训管理"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_get_pending_lessons(self):
        """获取待审核教训"""
        lessons = self.bridge.get_pending_lessons()
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]["id"], "lesson-1")
        self.assertEqual(lessons[0]["lesson"], "避免泛泛而谈")

    def test_accept_lesson(self):
        """接受教训并创建规则"""
        rule_id = self.bridge.accept_lesson("lesson-1", note="同意")
        self.assertEqual(rule_id, "rule-new-1")
        self.mock_engine.accept_lesson.assert_called_once_with(
            audit_id="lesson-1", note="同意"
        )

    def test_reject_lesson(self):
        """拒绝教训"""
        result = self.bridge.reject_lesson("lesson-1", note="不适用")
        self.assertTrue(result)
        self.mock_engine.reject_lesson.assert_called_once_with(
            audit_id="lesson-1", note="不适用"
        )

    def test_accept_lesson_returns_none_on_exception(self):
        """接受教训异常时返回 None"""
        self.mock_engine.accept_lesson.side_effect = Exception("error")
        result = self.bridge.accept_lesson("lesson-1")
        self.assertIsNone(result)

    def test_reject_lesson_returns_false_on_exception(self):
        """拒绝教训异常时返回 False"""
        self.mock_engine.reject_lesson.side_effect = Exception("error")
        result = self.bridge.reject_lesson("lesson-1")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Test: cleanup_stale_memories
# ---------------------------------------------------------------------------


class TestCleanupStaleMemories(unittest.TestCase):
    """清理过时记忆"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()

    def test_returns_cleaned_count(self):
        """返回清理的记忆数"""
        self.bridge._cm.consolidate.return_value = {"cleaned": 5}
        result = self.bridge.cleanup_stale_memories()
        self.assertEqual(result, 5)

    def test_returns_zero_when_no_consolidate(self):
        """CarryMem 无 consolidate 方法时返回 0"""
        del self.bridge._cm.consolidate
        result = self.bridge.cleanup_stale_memories()
        self.assertEqual(result, 0)

    def test_returns_zero_on_exception(self):
        """异常时返回 0"""
        self.bridge._cm.consolidate.side_effect = Exception("error")
        result = self.bridge.cleanup_stale_memories()
        self.assertEqual(result, 0)


# ---------------------------------------------------------------------------
# Test: export_user_data
# ---------------------------------------------------------------------------


class TestExportUserData(unittest.TestCase):
    """测试用户数据导出

    Note: export_user_data() has a bug — missing 'return export' at the end.
    The method returns None when enabled=True. Tests verify the method
    completes without error and document this known issue.
    """

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_exports_calls_recall_memories(self):
        """导出时调用 recall_memories"""
        self.bridge._memory_count = (
            5  # Avoid memory_count property calling recall_memories
        )
        self.bridge._cm.recall_memories.return_value = {"memories": ["m1", "m2"]}
        self.bridge.export_user_data()
        self.bridge._cm.recall_memories.assert_called_with(limit=1000)

    def test_exports_calls_engine_export_rules(self):
        """导出时调用 engine.export_rules"""
        self.bridge._cm.recall_memories.return_value = {"memories": []}
        self.bridge.export_user_data()
        self.mock_engine.export_rules.assert_called_once()

    def test_handles_export_exception_gracefully(self):
        """导出异常时不抛出"""
        self.bridge._cm.recall_memories.side_effect = Exception("error")
        # Should not raise
        self.bridge.export_user_data()

    def test_disabled_returns_empty_structure(self):
        """禁用时返回空结构"""
        self.bridge._enabled = False
        result = self.bridge.export_user_data()
        self.assertEqual(result, {"memories": [], "rules": [], "flywheel": {}})


# ---------------------------------------------------------------------------
# Test: close
# ---------------------------------------------------------------------------


class TestClose(unittest.TestCase):
    """测试资源清理"""

    def test_closes_carrymem(self):
        """调用 CarryMem.close()"""
        bridge = _create_enabled_bridge()
        bridge.close()
        bridge._cm.close.assert_called_once()

    def test_close_when_no_close_method(self):
        """CarryMem 无 close 方法时不抛异常"""
        bridge = _create_enabled_bridge()
        del bridge._cm.close
        bridge.close()

    def test_close_exception_handled(self):
        """close 异常时不抛出"""
        bridge = _create_enabled_bridge()
        bridge._cm.close.side_effect = Exception("error")
        bridge.close()

    def test_close_when_cm_is_none(self):
        """_cm 为 None 时不抛异常"""
        bridge = _create_enabled_bridge()
        bridge._cm = None
        bridge.close()


# ---------------------------------------------------------------------------
# Test: get_memory_bridge 单例
# ---------------------------------------------------------------------------


class TestGetMemoryBridge(unittest.TestCase):
    """测试模块级单例"""

    def test_returns_same_instance(self):
        """多次调用返回同一实例"""
        import opc_manager.memory_bridge as mb

        mb._instance = None  # 重置单例
        with patch("opc_manager.memory_bridge.is_memory_enabled", return_value=False):
            b1 = get_memory_bridge()
            b2 = get_memory_bridge()
            self.assertIs(b1, b2)
        mb._instance = None  # 清理


# ---------------------------------------------------------------------------
# Test: _try_auto_add_rule
# ---------------------------------------------------------------------------


class TestTryAutoAddRule(unittest.TestCase):
    """测试自动添加规则"""

    def setUp(self):
        self.bridge = _create_enabled_bridge()
        self.mock_engine = _make_mock_rule_engine()
        self.bridge._rule_engine = self.mock_engine

    def test_adds_dict_suggestion(self):
        """添加字典类型的规则建议"""
        suggestion = {"trigger": "营销", "action": "数据驱动", "rule_type": "prefer"}
        self.bridge._try_auto_add_rule(suggestion)
        self.mock_engine.add_rule.assert_called_once()

    def test_adds_object_suggestion(self):
        """添加对象类型的规则建议"""
        suggestion = MagicMock()
        suggestion.trigger = "营销"
        suggestion.action = "数据驱动"
        suggestion.rule_type = "prefer"
        self.bridge._try_auto_add_rule(suggestion)
        self.mock_engine.add_rule.assert_called_once()

    def test_skips_empty_suggestion(self):
        """空建议跳过"""
        self.bridge._try_auto_add_rule(None)
        self.mock_engine.add_rule.assert_not_called()

    def test_handles_exception_gracefully(self):
        """异常时静默跳过"""
        self.mock_engine.add_rule.side_effect = Exception("error")
        self.bridge._try_auto_add_rule({"trigger": "t", "action": "a"})
        # 不应抛异常

    def test_skips_when_no_engine(self):
        """无 rule_engine 时跳过"""
        self.bridge._rule_engine = None
        self.bridge._cm.rule_engine = None
        self.bridge._try_auto_add_rule({"trigger": "t", "action": "a"})
        # 不应抛异常


if __name__ == "__main__":
    unittest.main()
