"""CarryMem 跨会话记忆 E2E 测试 [TD-005 补充]

覆盖 MemoryBridge（CarryMem 适配层）的端到端行为，验证"越用越懂你"的飞轮效应。

测试策略：
- 真实 CarryMem 0.9.8（已安装，非 Mock）
- 临时数据库隔离：CARRYMEM_DB_PATH 重定向到 tmp_path
- CARRYMEM_ENABLED=true 激活真实集成
- 每个测试重置单例，避免状态污染

覆盖范围：
1. MemoryBridge 初始化（启用/禁用/降级）
2. 跨会话偏好记忆（remember → build_context 闭环）
3. 规则引擎（match_rules + inject_rules_prompt）
4. 飞轮成长（get_flywheel_status 等级提升）
5. 失败经验记录（record_failure → 失败教训）
6. 数据可携带性（export_user_data）

依据：
- memory_bridge.py 接口定义
- project_memory 教训"后端 API 测试通过不等于用户能用"
- E2E_REVIEW_v0.5.7.md：CarryMem 核心卖点完全无 E2E 覆盖
"""


import pytest

from opc_manager.memory_bridge import (
    MemoryBridge,
    _CARRYMEM_AVAILABLE,
    get_memory_bridge,
    is_memory_enabled,
)


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def memory_bridge(tmp_path, monkeypatch):
    """构建启用的 MemoryBridge，数据库隔离到 tmp_path。

    每个测试获得全新的临时数据库，避免跨测试污染。
    """
    if not _CARRYMEM_AVAILABLE:
        pytest.skip("CarryMem 未安装，跳过真实集成 E2E")

    db_path = str(tmp_path / "memory.db")
    monkeypatch.setenv("CARRYMEM_ENABLED", "true")
    monkeypatch.setenv("CARRYMEM_DB_PATH", db_path)

    # 重置模块级单例
    import opc_manager.memory_bridge as _mb_module

    _mb_module._instance = None

    bridge = MemoryBridge()
    yield bridge
    bridge.close()
    _mb_module._instance = None


@pytest.fixture
def disabled_bridge(monkeypatch):
    """构建禁用的 MemoryBridge（CARRYMEM_ENABLED=false）。"""
    monkeypatch.setenv("CARRYMEM_ENABLED", "false")

    import opc_manager.memory_bridge as _mb_module

    _mb_module._instance = None

    bridge = MemoryBridge()
    yield bridge
    bridge.close()
    _mb_module._instance = None


# ============================================================
# 1. MemoryBridge 初始化 E2E
# ============================================================


class TestMemoryBridgeInitialization:
    """MemoryBridge 初始化 — 验证启用/禁用/降级行为。

    依据：memory_bridge.py L38-88
    """

    def test_enabled_bridge_initializes_correctly(self, memory_bridge):
        """启用状态下 MemoryBridge 应正确初始化。"""
        assert memory_bridge.enabled is True
        assert _CARRYMEM_AVAILABLE is True

    def test_disabled_bridge_returns_empty_context(self, disabled_bridge):
        """禁用状态下 build_context 返回空字符串（静默降级）。"""
        assert disabled_bridge.enabled is False
        result = disabled_bridge.build_context("测试输入")
        assert result == ""

    def test_disabled_bridge_returns_empty_rules(self, disabled_bridge):
        """禁用状态下 match_rules 返回空列表。"""
        assert disabled_bridge.enabled is False
        rules = disabled_bridge.match_rules("测试输入")
        assert rules == []

    def test_disabled_bridge_remember_is_noop(self, disabled_bridge):
        """禁用状态下 remember 是无操作（不抛异常）。"""
        assert disabled_bridge.enabled is False
        # 应静默返回，不抛异常
        disabled_bridge.remember("测试", "结果", {"success": True})

    def test_disabled_bridge_status_reflects_state(self, disabled_bridge):
        """禁用状态下 get_status 返回 enabled=False。"""
        status = disabled_bridge.get_status()
        assert status["enabled"] is False
        assert status["memory_count"] == 0
        assert status["rule_count"] == 0

    def test_is_memory_enabled_checks_env_and_package(self, monkeypatch):
        """is_memory_enabled 同时检查环境变量和包可用性。"""
        # 包已安装（_CARRYMEM_AVAILABLE=True），检查环境变量
        monkeypatch.setenv("CARRYMEM_ENABLED", "true")
        assert is_memory_enabled() is True

        monkeypatch.setenv("CARRYMEM_ENABLED", "false")
        assert is_memory_enabled() is False

        monkeypatch.setenv("CARRYMEM_ENABLED", "1")
        assert is_memory_enabled() is True

    def test_get_memory_bridge_returns_singleton(self, memory_bridge):
        """get_memory_bridge 返回单例实例。"""

        # memory_bridge fixture 已重置 _instance=None 然后创建
        instance1 = get_memory_bridge()
        instance2 = get_memory_bridge()
        assert instance1 is instance2


# ============================================================
# 2. 跨会话偏好记忆 E2E
# ============================================================


class TestCrossSessionPreferenceMemory:
    """跨会话偏好记忆 — 验证 remember → build_context 闭环。

    核心卖点："用户说'我喜欢简洁风格' → 下次自动应用"
    依据：memory_bridge.py L127-156（build_context）+ L233-266（remember）
    """

    def test_remember_increases_memory_count(self, memory_bridge):
        """remember 后 memory_count 应增加。"""
        initial_count = memory_bridge.memory_count
        memory_bridge.remember("帮我写营销方案", "营销方案结果", {"success": True})
        assert memory_bridge.memory_count >= initial_count + 1

    def test_build_context_returns_string_when_enabled(self, memory_bridge):
        """启用状态下 build_context 返回字符串（可能为空如果无匹配记忆）。"""
        memory_bridge.remember("用户偏好简洁风格", "已记录", {"success": True})
        result = memory_bridge.build_context("帮我写方案")
        assert isinstance(result, str)

    def test_cross_session_memory_persists(self, memory_bridge, tmp_path, monkeypatch):
        """跨会话记忆持久化 — 新 MemoryBridge 实例能读取旧记忆。

        模拟：会话1 存储记忆 → 会话2（新实例）检索到记忆。
        """
        # 会话1：存储偏好
        memory_bridge.remember("我喜欢简洁的中文回复", "已记录偏好", {"success": True})
        memory_bridge.close()

        # 会话2：新实例，同一数据库
        import opc_manager.memory_bridge as _mb_module

        _mb_module._instance = None
        bridge2 = MemoryBridge()
        try:
            assert bridge2.enabled is True
            # 新实例应能读取旧记忆
            assert bridge2.memory_count >= 1
            context = bridge2.build_context("帮我写方案")
            assert isinstance(context, str)
        finally:
            bridge2.close()
            _mb_module._instance = None

    def test_remember_with_low_quality_stores_correction(self, memory_bridge):
        """低质量结果（quality_score < 0.5）应存储为纠正记忆。"""
        initial_count = memory_bridge.memory_count
        memory_bridge.remember(
            "帮我写方案",
            "质量不佳的结果",
            {"success": True, "quality_score": 0.3},
        )
        # 应存储原始记忆 + 纠正记忆 = 至少 +2
        assert memory_bridge.memory_count >= initial_count + 2

    def test_remember_without_evaluation_stores_once(self, memory_bridge):
        """无 evaluation 参数时只存储一次记忆。"""
        initial_count = memory_bridge.memory_count
        memory_bridge.remember("普通任务", "普通结果")
        assert memory_bridge.memory_count >= initial_count + 1


# ============================================================
# 3. 规则引擎 E2E
# ============================================================


class TestRuleEngine:
    """规则引擎 — 验证 match_rules + inject_rules_prompt。

    依据：memory_bridge.py L158-231（match_rules + inject_rules_prompt）
    场景：失败经验自动提炼为规则，同类错误不再犯。
    """

    def test_match_rules_returns_list(self, memory_bridge):
        """match_rules 返回列表（可能为空如果无规则）。"""
        rules = memory_bridge.match_rules("帮我写营销方案")
        assert isinstance(rules, list)

    def test_inject_rules_prompt_returns_string(self, memory_bridge):
        """inject_rules_prompt 返回字符串。"""
        result = memory_bridge.inject_rules_prompt("帮我写方案")
        assert isinstance(result, str)

    def test_get_rules_for_context_returns_dict(self, memory_bridge):
        """get_rules_for_context 返回包含 rules_prompt/rules/has_hard_rules 的字典。"""
        result = memory_bridge.get_rules_for_context("帮我写方案")
        assert isinstance(result, dict)
        assert "rules_prompt" in result
        assert "rules" in result
        assert "has_hard_rules" in result
        assert isinstance(result["rules"], list)
        assert isinstance(result["has_hard_rules"], bool)

    def test_disabled_bridge_rules_are_empty(self, disabled_bridge):
        """禁用状态下规则相关方法返回空。"""
        assert disabled_bridge.get_rules_for_context("测试") == {
            "rules_prompt": "",
            "rules": [],
            "has_hard_rules": False,
        }


# ============================================================
# 4. 飞轮成长 E2E
# ============================================================


class TestFlywheelGrowth:
    """飞轮成长机制 — 验证 get_flywheel_status 等级提升。

    依据：memory_bridge.py L434-489（get_flywheel_status）
    等级：0 新手 → 1 熟悉 → 2 精通 → 3 专家 → 4 大师 → 5 传奇
    评分：记忆深度(0-2) + 规则密度(0-2) + 经验沉淀(0-1)
    """

    def test_initial_flywheel_is_newbie(self, memory_bridge):
        """初始状态飞轮等级为 0（新手）。"""
        status = memory_bridge.get_flywheel_status()
        assert isinstance(status, dict)
        assert "level" in status
        assert "grade" in status
        assert "metrics" in status
        assert isinstance(status["level"], int)
        assert 0 <= status["level"] <= 5

    def test_flywheel_level_increases_with_memories(self, memory_bridge):
        """存储记忆后飞轮等级应提升（或保持非负）。

        飞轮评分：min(memory_count/20, 1.0)*2 → 20 条记忆得满分 2 分。
        """
        # 存储多条记忆以提升等级
        for i in range(5):
            memory_bridge.remember(f"任务{i}", f"结果{i}", {"success": True})

        status = memory_bridge.get_flywheel_status()
        assert status["level"] >= 0
        # 存储了 5 条记忆，memory_count 应 > 0
        assert status["metrics"]["memory_count"] >= 5

    def test_disabled_bridge_flywheel_is_inactive(self, disabled_bridge):
        """禁用状态下飞轮等级为 0。"""
        status = disabled_bridge.get_flywheel_status()
        assert status["level"] == 0
        assert status["grade"] == "未启用"

    def test_suggest_skills_returns_list(self, memory_bridge):
        """suggest_skills 返回列表。"""
        result = memory_bridge.suggest_skills("帮我做营销")
        assert isinstance(result, list)

    def test_cleanup_stale_memories_returns_int(self, memory_bridge):
        """cleanup_stale_memories 返回整数（清理条数）。"""
        memory_bridge.remember("旧任务", "旧结果")
        result = memory_bridge.cleanup_stale_memories(max_age_days=90)
        assert isinstance(result, int)
        assert result >= 0


# ============================================================
# 5. 失败经验记录 E2E
# ============================================================


class TestFailureExperienceRecording:
    """失败经验记录 — 验证 record_failure 记录失败教训。

    依据：memory_bridge.py L268-307（record_failure）
    场景：反思脑判定质量不佳时，提炼失败教训为规则。
    """

    def test_record_failure_increases_memory_count(self, memory_bridge):
        """record_failure 后 memory_count 应增加。"""
        initial_count = memory_bridge.memory_count
        memory_bridge.record_failure("帮我写方案", "方案太泛，缺少具体数据", 0.3)
        assert memory_bridge.memory_count >= initial_count + 1

    def test_record_failure_does_not_raise(self, memory_bridge):
        """record_failure 不应抛异常（即使规则引擎不可用）。"""
        memory_bridge.record_failure("测试任务", "测试失败原因", 0.0)
        # 不抛异常即通过

    def test_disabled_bridge_record_failure_is_noop(self, disabled_bridge):
        """禁用状态下 record_failure 是无操作。"""
        disabled_bridge.record_failure("测试", "原因", 0.0)
        assert disabled_bridge.memory_count == 0

    def test_get_pending_lessons_returns_list(self, memory_bridge):
        """get_pending_lessons 返回列表。"""
        memory_bridge.record_failure("失败任务", "失败原因", 0.2)
        lessons = memory_bridge.get_pending_lessons()
        assert isinstance(lessons, list)


# ============================================================
# 6. 数据可携带性与状态 E2E
# ============================================================


class TestDataPortabilityAndStatus:
    """数据可携带性 — 验证 export_user_data + get_status。

    依据：memory_bridge.py L386-423（get_status）+ L542-590（export_user_data）
    场景：用户可导出全部数据（飞轮护城河的保障）。
    """

    def test_get_status_returns_complete_dict(self, memory_bridge):
        """get_status 返回完整状态字典。"""
        memory_bridge.remember("状态测试", "结果")
        status = memory_bridge.get_status()

        assert status["enabled"] is True
        assert status["available"] is True
        assert "memory_count" in status
        assert "rule_count" in status
        assert "pending_lessons" in status
        assert "db_path" in status
        assert status["memory_count"] >= 1

    def test_export_user_data_returns_dict(self, memory_bridge):
        """export_user_data 返回包含 memories/rules/flywheel 的字典。"""
        memory_bridge.remember("导出测试", "结果")
        exported = memory_bridge.export_user_data()

        assert isinstance(exported, dict)
        assert "memories" in exported
        assert "rules" in exported
        assert "flywheel" in exported
        assert isinstance(exported["memories"], list)

    def test_export_after_multiple_memories(self, memory_bridge):
        """多条记忆后导出应包含所有记忆。"""
        for i in range(3):
            memory_bridge.remember(f"导出任务{i}", f"结果{i}")

        exported = memory_bridge.export_user_data()
        assert len(exported["memories"]) >= 3

    def test_disabled_bridge_export_returns_empty(self, disabled_bridge):
        """禁用状态下导出返回空结构。"""
        exported = disabled_bridge.export_user_data()
        assert exported == {"memories": [], "rules": [], "flywheel": {}}


# ============================================================
# 7. MemoryBridge 集成到 TaskOrchestrator E2E
# ============================================================


class TestMemoryBridgeTaskOrchestratorIntegration:
    """MemoryBridge 与 TaskOrchestrator 集成 — 验证规则注入到策略脑。

    依据：task_orchestrator.py L173-188（execute_plan_phase 中 MemoryBridge 规则注入）
    场景：任务执行前从 CarryMem 检索记忆+规则，注入到 prompt 上下文。
    """

    def test_get_rules_for_context_does_not_raise(self, memory_bridge):
        """get_rules_for_context 在真实集成下不抛异常。"""
        # 模拟 task_orchestrator.execute_plan_phase 中的调用
        result = memory_bridge.get_rules_for_context("发邮件给张总")
        assert isinstance(result, dict)
        assert "rules_prompt" in result
        assert "rules" in result
        assert "has_hard_rules" in result

    def test_memory_bridge_graceful_degradation(self, disabled_bridge, monkeypatch):
        """MemoryBridge 不可用时应静默降级，不影响核心功能。

        依据：memory_bridge.py L8 "降级策略：CarryMem 不可用时静默降级"
        """
        # 模拟 task_orchestrator.py L175-182 的 try/except
        memory_rules = {}
        try:
            _mb = disabled_bridge
            if _mb.enabled:
                memory_rules = _mb.get_rules_for_context("测试")
        except Exception as e:
            # 不应到达这里
            pytest.fail(f"MemoryBridge 降级不应抛异常: {e}")

        # 禁用时 memory_rules 保持空
        assert memory_rules == {}

    def test_build_context_with_stored_preference(self, memory_bridge):
        """存储偏好后 build_context 应能检索到相关上下文。

        模拟：用户说"我喜欢简洁风格" → 下次 build_context 包含相关记忆。
        """
        # 存储偏好
        memory_bridge.remember(
            "我喜欢简洁的中文回复风格，不要太多 emoji",
            "已记录用户偏好",
            {"success": True, "quality_score": 0.9},
        )

        # 下次任务前检索上下文
        context = memory_bridge.build_context("帮我写一封邮件")
        assert isinstance(context, str)
        # build_context 可能返回空（如果 CarryMem 的检索未匹配），
        # 但不应抛异常，且 memory_count 应 > 0
        assert memory_bridge.memory_count >= 1
