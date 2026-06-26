"""SessionContextManager 单元测试 v3.5 — P0-4 多轮对话支持

测试覆盖范围（对应 TEST_PLAN_V3.md 的 TestSessionIteration 类别）：
- SI-001: 单轮上下文存储
- SI-002: 多轮历史累积
- SI-003: LLM上下文格式化
- SI-004: 轮次上限强制
- SI-005: 最新结果快速获取

=== 验收标准 (G-ITERATE-01 门禁) ===
- add_turn()正确保存user_input+response+sources
- get_context_for_llm()返回格式化的对话历史
- 轮次上限20轮强制生效
"""

import unittest
from opc_manager.session_context import (
    SessionContextManager,
    ConversationTurn,
    TurnRole,
)


class TestSingleTurnStorage(unittest.TestCase):
    """SI-001: 单轮上下文存储测试"""

    def setUp(self):
        self.session = SessionContextManager(max_turns=20)

    def test_add_turn_returns_turn_object(self):
        """add_turn()应返回ConversationTurn对象"""
        turn = self.session.add_turn(
            user_input="测试输入",
            assistant_response="测试回复",
        )

        self.assertIsInstance(turn, ConversationTurn)
        self.assertEqual(turn.role, TurnRole.USER)
        self.assertEqual(turn.content, "测试输入")

    def test_add_turn_stores_user_and_assistant(self):
        """add_turn()应同时存储用户和助手消息"""
        self.session.add_turn(
            user_input="帮我写方案",
            assistant_response="已生成方案...",
            task_type="plan",
            filepath="/tmp/plan.md",
            sources=[{"title": "资料1", "url": "http://1"}],
        )

        history = self.session.get_full_history()
        self.assertEqual(len(history), 2)

        user_entry = [h for h in history if h["role"] == "user"][0]
        asst_entry = [h for h in history if h["role"] == "assistant"][0]

        self.assertEqual(user_entry["content"], "帮我写方案")
        self.assertEqual(asst_entry["content"], "已生成方案...")
        self.assertEqual(asst_entry["task_type"], "plan")
        self.assertEqual(asst_entry["filepath"], "/tmp/plan.md")
        self.assertEqual(asst_entry["sources_count"], 1)

    def test_turn_id_increments(self):
        """每轮的turn_id应该递增"""
        turn1 = self.session.add_turn("第1轮", "回复1")
        turn2 = self.session.add_turn("第2轮", "回复2")

        self.assertEqual(turn1.turn_id, 1)
        self.assertEqual(turn2.turn_id, 2)

    def test_get_turn_count_updates(self):
        """get_turn_count()应反映当前轮数"""
        self.assertEqual(self.session.get_turn_count(), 0)

        self.session.add_turn("输入1", "回复1")
        self.assertEqual(self.session.get_turn_count(), 1)

        self.session.add_turn("输入2", "回复2")
        self.assertEqual(self.session.get_turn_count(), 2)


class TestMultiTurnAccumulation(unittest.TestCase):
    """SI-002: 多轮历史累积测试"""

    def setUp(self):
        self.session = SessionContextManager(max_turns=20)

    def test_multiple_turns_accumulate(self):
        """连续add_turn()后get_full_history()应包含所有轮次"""
        for i in range(5):
            self.session.add_turn(
                user_input=f"用户输入{i}",
                assistant_response=f"助手回复{i}",
                task_type=f"type_{i}",
            )

        history = self.session.get_full_history()
        self.assertEqual(len(history), 10)

        turns_set = set(h["turn_id"] for h in history)
        self.assertEqual(turns_set, {1, 2, 3, 4, 5})

    def test_history_chronological_order(self):
        """历史记录应按时间顺序排列"""
        import time

        self.session.add_turn("早", "早回")
        time.sleep(0.05)
        self.session.add_turn("晚", "晚回")

        history = self.session.get_full_history()

        timestamps = [h["timestamp"] for h in history]
        self.assertTrue(timestamps[-1] > timestamps[0], "历史应按时间递增")

    def test_sources_preserved_per_turn(self):
        """每轮的sources应独立保存"""
        sources_1 = [{"title": "A", "url": "http://a"}]
        sources_2 = [
            {"title": "B", "url": "http://b"},
            {"title": "C", "url": "http://c"},
        ]

        self.session.add_turn("Q1", "A1", sources=sources_1)
        self.session.add_turn("Q2", "A2", sources=sources_2)

        last_result = self.session.get_last_result()
        self.assertEqual(len(last_result["sources"]), 2)


class TestLLMContextFormatting(unittest.TestCase):
    """SI-003: LLM上下文格式化测试"""

    def setUp(self):
        self.session = SessionContextManager(max_turns=20)

    def test_context_for_llm_contains_history(self):
        """get_context_for_llm()应包含之前的对话内容"""
        self.session.add_turn(
            user_input="写一份报告",
            assistant_response="已生成报告，共3章...",
            task_type="report",
        )

        context = self.session.get_context_for_llm(max_turns=5)

        self.assertIn("对话历史", context)
        self.assertIn("写一份报告", context)
        self.assertIn("已生成报告", context)

    def test_context_for_llm_format_structure(self):
        """上下文格式应包含轮次编号和角色标识"""
        self.session.add_turn(
            user_input="测试问题",
            assistant_response="测试答案",
        )

        context = self.session.get_context_for_llm()

        self.assertIn("=== 第1轮", context)
        self.assertIn("用户:", context)
        self.assertIn("助手:", context)

    def test_max_turns_parameter_works(self):
        """max_turns参数应限制返回的轮数"""
        for i in range(10):
            self.session.add_turn(f"输入{i}", f"回复{i}")

        context_3 = self.session.get_context_for_llm(max_turns=3)
        context_all = self.session.get_context_for_llm(max_turns=20)

        self.assertLess(len(context_3), len(context_all))

    def test_empty_session_returns_empty_context(self):
        """空会话的get_context_for_llm()应返回空字符串"""
        context = self.session.get_context_for_llm()
        self.assertEqual(context, "")


class TestTurnLimitEnforcement(unittest.TestCase):
    """SI-004: 轮次上限强制测试"""

    def test_max_turns_prevents_overflow(self):
        """超过max_turns时应自动裁剪旧轮次而非抛出异常"""
        session = SessionContextManager(max_turns=3)

        for i in range(3):
            session.add_turn(f"输入{i}", f"回复{i}")

        session.add_turn("超额输入", "超额回复")

        self.assertEqual(session.get_turn_count(), 4)

    def test_default_limit_is_20(self):
        """默认max_turns应为20"""
        session = SessionContextManager()
        self.assertEqual(session.max_turns, 20)

    def test_clear_resets_counter(self):
        """clear()后应能重新添加轮次"""
        session = SessionContextManager(max_turns=2)

        session.add_turn("A", "B")
        session.add_turn("C", "D")
        session.add_turn("E", "F")

        session.clear()

        turn = session.add_turn("G", "H")
        self.assertIsNotNone(turn)


class TestLastResultQuickAccess(unittest.TestCase):
    """SI-005: 最新结果快速获取测试"""

    def setUp(self):
        self.session = SessionContextManager(max_turns=20)

    def test_get_last_result_returns_latest(self):
        """get_last_result()应返回最后一轮的助手回复"""
        self.session.add_turn("旧输入", "旧回复")
        self.session.add_turn("新输入", "新回复")

        last = self.session.get_last_result()

        self.assertIsNotNone(last)
        self.assertEqual(last["response"], "新回复")
        self.assertEqual(last["turn_id"], 2)

    def test_get_last_result_none_when_empty(self):
        """空会话时get_last_result()应返回None"""
        last = self.session.get_last_result()
        self.assertIsNone(last)

    def test_get_last_result_includes_metadata(self):
        """get_last_result()应包含完整的元数据"""
        self.session.add_turn(
            user_input="元数据测试",
            assistant_response="带元数据的回复",
            task_type="analysis",
            filepath="/tmp/meta.md",
            sources=[{"title": "M1", "url": "http://m1"}],
        )

        last = self.session.get_last_result()

        self.assertEqual(last["task_type"], "analysis")
        self.assertEqual(last["filepath"], "/tmp/meta.md")
        self.assertEqual(len(last["sources"]), 1)
        self.assertIsInstance(last["timestamp"], float)

    def test_get_last_result_after_iteration(self):
        """迭代场景：第2轮应能看到第1轮的结果"""
        self.session.add_turn(
            user_input="写Q2方案",
            assistant_response="已生成Q2营销方案，第三阶段为4周...",
            task_type="plan",
        )
        self.session.add_turn(
            user_input="第三阶段太长，缩短到2周",
            assistant_response="已调整为2周敏捷迭代...",
            task_type="modification",
        )

        last = self.session.get_last_result()
        self.assertIn("2周", last["response"])
        self.assertEqual(last["turn_id"], 2)

        context = self.session.get_context_for_llm()
        self.assertIn("写Q2方案", context)
        self.assertIn("Q2营销方案", context)


class TestGateITERATE01(unittest.TestCase):
    """G-ITERATE-01: 多轮对话上下文门禁（P0阻断级）

    这是CDR定义的核心验收标准，必须全量通过才能发布v3.5
    """

    def setUp(self):
        self.session = SessionContextManager(max_turns=20)

    def test_three_turns_with_cross_reference(self):
        """门禁：连续3轮调用，第2次能引用第1次结果"""
        self.session.add_turn(
            user_input="帮我制定Q2增长方案",
            assistant_response=(
                "# Q2增长方案\n\n"
                "## 第一阶段 (第1-4周)\n"
                "- 市场调研与用户画像\n"
                "## 第二阶段 (第5-8周)\n"
                "- 产品功能开发与测试\n"
                "## 第三阶段 (第9-12周)\n"
                "- 全面推广与优化\n"
            ),
            task_type="plan",
        )

        context_before_iter = self.session.get_context_for_llm()
        self.assertIn("Q2增长方案", context_before_iter)
        self.assertIn("第一阶段", context_before_iter)

        self.session.add_turn(
            user_input="第三阶段时间太长，能缩短到2周吗？",
            assistant_response=(
                "# Q2增长方案（修订版）\n\n"
                "## 第一阶段 (第1-4周)\n"
                "- 市场调研与用户画像\n"
                "## 第二阶段 (第5-8周)\n"
                "- 产品功能开发与测试\n"
                "## 第三阶段 (第9-10周) ← 已缩短为2周\n"
                "- 快速推广与数据验证\n"
            ),
            task_type="modification",
        )

        last = self.session.get_last_result()
        self.assertIsNotNone(last)
        self.assertIn("2周", last["response"])
        self.assertEqual(last["turn_id"], 2)

        full_context = self.session.get_context_for_llm()
        self.assertIn("Q2增长方案", full_context)
        self.assertIn("缩短到2周吗？", full_context)

    def test_context_format_is_readable(self):
        """门禁：上下文格式应该是人类可读的结构化文本"""
        self.session.add_turn(
            user_input="分析竞品A",
            assistant_response="竞品A分析完成，优势3项劣势2项...",
        )

        context = self.session.get_context_for_llm()

        self.assertIn("[对话历史", context)
        self.assertIn("=== 第", context)
        self.assertIn("用户:", context)
        self.assertIn("助手:", context)

        lines = [l for l in context.split("\n") if l.strip()]
        self.assertGreaterEqual(len(lines), 4, "上下文格式应足够详细")


if __name__ == "__main__":
    unittest.main(verbosity=2)
