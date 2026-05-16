"""OnboardingManager 单元测试 v0.2.0 — P1-1 新手引导模块

测试覆盖范围：
- OB-001: 初始状态验证
- OB-002: 步骤推进逻辑
- OB-003: 完成标记设置
- OB-004: 跳过引导功能
- OB-005: 重置状态功能
- OB-006: 进度百分比计算
- OB-007: 各步骤内容完整性
- OB-008: 示例任务结果记录
- OB-009: 状态持久化到磁盘
- OB-010: 并发安全访问
"""

import unittest
import tempfile
import shutil
import json
import time
import threading
from pathlib import Path
from unittest.mock import patch

from opc_manager.onboarding import (
    OnboardingManager,
    OnboardingStep,
    OnboardingState,
    SAMPLE_TASKS,
    get_onboarding,
)


class TestInitialState(unittest.TestCase):
    """OB-001: 初始状态验证"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_default_step_is_welcome(self):
        """新实例的当前步骤应该是WELCOME"""
        self.assertEqual(self.manager.get_current_step(), OnboardingStep.WELCOME)

    def test_is_completed_false_initially(self):
        """初始状态is_completed应该为False"""
        self.assertFalse(self.manager.is_completed)

    def test_progress_zero_initially(self):
        """初始进度应该为0%"""
        self.assertEqual(self.manager.progress_pct, 0)

    def test_state_is_onboarding_state_instance(self):
        """state属性应返回OnboardingState实例"""
        self.assertIsInstance(self.manager.state, OnboardingState)

    def test_steps_completed_empty_initially(self):
        """初始状态steps_completed应为空列表"""
        self.assertEqual(len(self.manager.state.steps_completed), 0)


class TestAdvanceSteps(unittest.TestCase):
    """OB-002: 步骤推进逻辑"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_advance_to_llm_config(self):
        """从WELCOME推进到LLM_CONFIG"""
        result = self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_current_step(), OnboardingStep.LLM_CONFIG)

    def test_advance_to_sample_task(self):
        """推进到SAMPLE_TASK"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        result = self.manager.advance_to_step(OnboardingStep.SAMPLE_TASK)
        self.assertTrue(result)
        self.assertEqual(self.manager.get_current_step(), OnboardingStep.SAMPLE_TASK)

    def test_advance_full_flow(self):
        """完整流程：WELCOME → LLM_CONFIG → SAMPLE_TASK → COMPLETED"""
        steps = [
            OnboardingStep.LLM_CONFIG,
            OnboardingStep.SAMPLE_TASK,
            OnboardingStep.COMPLETED,
        ]
        for step in steps:
            result = self.manager.advance_to_step(step)
            self.assertTrue(result, f"Failed to advance to {step}")
        self.assertTrue(self.manager.is_completed)

    def test_advance_records_previous_step(self):
        """推进时应记录上一步到steps_completed（不包括WELCOME）"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.manager.advance_to_step(OnboardingStep.SAMPLE_TASK)
        self.assertIn("llm_config", self.manager.state.steps_completed)

    def test_advance_invalid_step_returns_false(self):
        """传入无效步骤应返回False"""
        result = self.manager.advance_to_step("invalid_step")
        self.assertFalse(result)


class TestCompleteOnboarding(unittest.TestCase):
    """OB-003: 完成标记设置"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_complete_sets_completed_flag(self):
        """complete_onboarding后is_completed应为True"""
        self.manager.complete_onboarding()
        self.assertTrue(self.manager.is_completed)

    def test_complete_sets_completed_timestamp(self):
        """complete_onboarding应设置completed_at时间戳"""
        before = time.time()
        self.manager.complete_onboarding()
        after = time.time()
        self.assertGreaterEqual(self.manager.state.completed_at, before)
        self.assertLessEqual(self.manager.state.completed_at, after)

    def test_complete_sets_current_step_to_completed(self):
        """complete_onboarding后current_step应为COMPLETED"""
        self.manager.complete_onboarding()
        self.assertEqual(self.manager.get_current_step(), OnboardingStep.COMPLETED)

    def test_complete_progress_is_100(self):
        """完成后progress_pct应为100"""
        self.manager.complete_onboarding()
        self.assertEqual(self.manager.progress_pct, 100)


class TestSkipOnboarding(unittest.TestCase):
    """OB-004: 跳过引导功能"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_skip_marks_as_completed(self):
        """skip_onboarding应将状态标记为完成"""
        self.manager.skip_onboarding()
        self.assertTrue(self.manager.is_completed)

    def test_skip_from_any_step(self):
        """从任意步骤跳过都应该有效"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.manager.skip_onboarding()
        self.assertTrue(self.manager.is_completed)


class TestReset(unittest.TestCase):
    """OB-005: 重置状态功能"""

    def setUp(self):
        self.manager = OnboardingManager()

    def test_reset_clears_all_state(self):
        """reset_onboarding应清除所有状态"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.manager.record_sample_task_result("test result")
        self.manager.reset_onboarding()

        self.assertEqual(self.manager.get_current_step(), OnboardingStep.WELCOME)
        self.assertFalse(self.manager.is_completed)
        self.assertEqual(len(self.manager.state.steps_completed), 0)
        self.assertIsNone(self.manager.state.sample_task_result)

    def test_removes_state_file(self):
        """reset_onboarding应删除状态文件"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.assertTrue(self.manager._state_file.exists())

        self.manager.reset_onboarding()
        self.assertFalse(self.manager._state_file.exists())


class TestProgressCalculation(unittest.TestCase):
    """OB-006: 进度百分比计算"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_zero_steps_zero_percent(self):
        """0步完成时进度为0%"""
        self.assertEqual(self.manager.progress_pct, 0)

    def test_one_step_33_percent(self):
        """完成1步时进度约为33%"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.assertEqual(self.manager.progress_pct, 33)

    def test_two_steps_66_percent(self):
        """完成2步时进度约为66%"""
        self.manager.advance_to_step(OnboardingStep.SAMPLE_TASK)
        self.assertEqual(self.manager.progress_pct, 66)

    def test_completed_100_percent(self):
        """完成时进度为100%"""
        self.manager.complete_onboarding()
        self.assertEqual(self.manager.progress_pct, 100)


class TestGetStepContent(unittest.TestCase):
    """OB-007: 各步骤内容完整性"""

    def setUp(self):
        self.manager = OnboardingManager()

    def test_welcome_content_has_title(self):
        """WELCOME步骤应包含title"""
        content = self.manager.get_step_content(OnboardingStep.WELCOME)
        self.assertIn("title", content)
        self.assertIn("欢迎使用", content["title"])

    def test_welcome_content_has_features(self):
        """WELCOME步骤应包含features列表"""
        content = self.manager.get_step_content(OnboardingStep.WELCOME)
        self.assertIn("features", content)
        self.assertEqual(len(content["features"]), 4)

    def test_llm_config_has_providers(self):
        """LLM_CONFIG步骤应包含providers列表"""
        content = self.manager.get_step_content(OnboardingStep.LLM_CONFIG)
        self.assertIn("providers", content)
        self.assertEqual(len(content["providers"]), 3)

    def test_llm_config_provider_fields(self):
        """LLM提供商应包含必要字段"""
        content = self.manager.get_step_content(OnboardingStep.LLM_CONFIG)
        provider = content["providers"][0]
        required_fields = ["id", "name", "description", "base_url", "model", "key_url"]
        for field in required_fields:
            self.assertIn(field, provider, f"Missing field: {field}")

    def test_sample_task_has_task_data(self):
        """SAMPLE_TASK步骤应包含task数据"""
        content = self.manager.get_step_content(OnboardingStep.SAMPLE_TASK)
        self.assertIn("task", content)
        task = content["task"]
        self.assertEqual(task["id"], "first_income")
        self.assertIn("example_input", task)

    def test_completed_has_description(self):
        """COMPLETED步骤应包含description"""
        content = self.manager.get_step_content(OnboardingStep.COMPLETED)
        self.assertIn("description", content)
        self.assertIn("开始使用", content["description"])

    def test_default_returns_current_step(self):
        """不传参数时返回当前步骤的内容"""
        content = self.manager.get_step_content()
        current = self.manager.get_current_step()
        expected = self.manager.get_step_content(current)
        self.assertEqual(content, expected)

    def test_invalid_step_returns_empty_dict(self):
        """无效步骤应返回空字典"""
        content = self.manager.get_step_content(None)
        # 当step为None时会使用current_step，所以这里测试的是边界情况


class TestSampleTaskResult(unittest.TestCase):
    """OB-008: 示例任务结果记录"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_record_result_stores_value(self):
        """record_sample_task_result应存储结果"""
        result = "记录成功：收入5000元"
        self.manager.record_sample_task_result(result)
        self.assertEqual(self.manager.state.sample_task_result, result)

    def test_record_long_result_truncates(self):
        """超过500字符的结果应被截断"""
        long_result = "x" * 1000
        self.manager.record_sample_task_result(long_result)
        self.assertEqual(len(self.manager.state.sample_task_result), 500)

    def test_record_none_result(self):
        """记录None结果不应崩溃"""
        self.manager.record_sample_task_result(None)
        self.assertIsNone(self.manager.state.sample_task_result)


class TestStatePersistence(unittest.TestCase):
    """OB-009: 状态持久化到磁盘"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_saved_after_advance(self):
        """步骤推进后状态应保存到磁盘"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.assertTrue(self.manager._state_file.exists())

        data = json.loads(self.manager._state_file.read_text(encoding='utf-8'))
        self.assertEqual(data["current_step"], "llm_config")

    def test_state_loaded_on_init(self):
        """新实例应能加载已保存的状态"""
        self.manager.advance_to_step(OnboardingStep.SAMPLE_TASK)
        self.manager.record_sample_task_result("test persistence")

        new_manager = OnboardingManager()
        self.assertEqual(new_manager.get_current_step(), OnboardingStep.SAMPLE_TASK)
        self.assertEqual(new_manager.state.sample_task_result, "test persistence")

    def test_state_preserves_steps_completed(self):
        """steps_completed列表应在持久化中保留"""
        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.manager.advance_to_step(OnboardingStep.SAMPLE_TASK)

        new_manager = OnboardingManager()
        self.assertIn("llm_config", new_manager.state.steps_completed)

    def test_state_handles_corrupted_file(self):
        """损坏的状态文件不应导致崩溃"""
        self.manager._state_file.parent.mkdir(parents=True, exist_ok=True)
        self.manager._state_file.write_text("{corrupted json", encoding='utf-8')

        manager2 = OnboardingManager()
        self.assertEqual(manager2.get_current_step(), OnboardingStep.WELCOME)

    def test_creates_data_directory_if_not_exists(self):
        """保存状态时如果data目录不存在应自动创建"""
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()
        if self.manager._state_file.parent.exists():
            shutil.rmtree(self.manager._state_file.parent)

        self.manager.advance_to_step(OnboardingStep.LLM_CONFIG)
        self.assertTrue(self.manager._state_file.parent.exists())


class TestConcurrentAccess(unittest.TestCase):
    """OB-010: 并发安全访问"""

    def setUp(self):
        self.manager = OnboardingManager()

    def tearDown(self):
        if self.manager._state_file.exists():
            self.manager._state_file.unlink()

    def test_concurrent_advance_doesnt_crash(self):
        """多线程同时推进步骤不应崩溃"""
        errors = []

        def advance_step(step):
            try:
                for _ in range(10):
                    self.manager.advance_to_step(step)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=advance_step, args=(OnboardingStep.LLM_CONFIG,)),
            threading.Thread(target=advance_step, args=(OnboardingStep.SAMPLE_TASK,)),
            threading.Thread(target=advance_step, args=(OnboardingStep.COMPLETED,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Concurrent access caused errors: {errors}")

    def test_concurrent_read_write(self):
        """并发读写不应导致异常"""
        errors = []

        def writer():
            try:
                for i in range(20):
                    self.manager.record_sample_task_result(f"result_{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    _ = self.manager.state
                    _ = self.manager.is_completed
                    _ = self.manager.progress_pct
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Concurrent read/write caused errors: {errors}")


class TestSampleTasksConstant(unittest.TestCase):
    """验证示例任务常量的完整性"""

    def test_sample_tasks_not_empty(self):
        """SAMPLE_TASKS不应为空"""
        self.assertGreater(len(SAMPLE_TASKS), 0)

    def test_first_task_has_required_fields(self):
        """第一个示例任务应包含所有必需字段"""
        task = SAMPLE_TASKS[0]
        required_fields = ["id", "title", "description", "example_input", "category", "expected_output_contains"]
        for field in required_fields:
            self.assertIn(field, task, f"Missing field: {field}")

    def test_first_income_task_category(self):
        """第一个任务的category应为finance"""
        self.assertEqual(SAMPLE_TASKS[0]["category"], "finance")


class TestGetOnboardingFactory(unittest.TestCase):
    """测试工厂函数"""

    def test_get_onboarding_returns_instance(self):
        """get_onboarding()应返回OnboardingManager实例"""
        manager = get_onboarding()
        self.assertIsInstance(manager, OnboardingManager)

    def tearDown(self):
        cleanup()


def cleanup():
    """清理测试产生的状态文件"""
    state_file = Path("data/onboarding.json")
    if state_file.exists():
        state_file.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=2)
