"""
Onboarding Manager — v0.3.27 新手引导系统

Provides step-by-step first-run experience for new users.
Guides through: Welcome → LLM Config → Sample Task → Complete.
"""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, cast
from dataclasses import dataclass, field
from enum import Enum
import os

from opc_manager.config import LLM_PROVIDERS

logger = logging.getLogger(__name__)


def _get_onboarding_marker() -> Path:
    """Return the onboarding completion marker path.

    The path is resolved at call time so tests can isolate it via the
    OPC_ONBOARDING_MARKER environment variable without reloading the module.
    """
    return Path(
        os.environ.get(
            "OPC_ONBOARDING_MARKER",
            os.path.expanduser("~/.opc-agents/onboarding_complete"),
        )
    )


# Backwards-compatible module-level alias (deprecated, prefer _get_onboarding_marker).
_ONBOARDING_MARKER = _get_onboarding_marker()
_SAMPLE_TASK_RESULT_MAX_LENGTH = 500


QUICK_START_GUIDE = """
┌─────────────────────────────────────────────────────┐
│            OPC-Agents 快速上手指南               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ① 设置  →  ② 对话  →  ③ 查看  →  ④ 导出         │
│                                           │
│                                                     │
│  ┌──────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │填入  │  │ 输入需求  │  │ 查看数据  │  │ 导出为  │ │
│  │API Key│  │ 如：     │  │ 图表/统计 │  │ PDF等   │ │
│  └──────┘  │ 记录一笔  │  └──────────┘  └─────────┘ │
│            │ 收入5000  │                           │
│            └──────────┘                           │
│                                                     │
│   小技巧：                                        │
│  • 按 Ctrl+Z 可撤销上一步操作                       │
│  • 输入 "/" 打开快捷命令                            │
│  • 设置页可切换主题和语言                             │
│  • 数据自动备份，不怕丢失                             │
│                                                     │
└─────────────────────────────────────────────────────┘
"""


class OnboardingStep(Enum):
    WELCOME = "welcome"
    LLM_CONFIG = "llm_config"
    SAMPLE_TASK = "sample_task"
    COMPLETED = "completed"


@dataclass
class OnboardingState:
    current_step: OnboardingStep = OnboardingStep.WELCOME
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0
    steps_completed: List[str] = field(default_factory=list)
    sample_task_result: Optional[str] = None


SAMPLE_TASKS = [
    {
        "id": "first_income",
        "title": " 试试记录一笔收入",
        "description": "体验OPC-Agents的核心能力：自然语言→自动执行",
        "example_input": "帮我记录一笔收入5000元，来自客户张三的咨询服务费",
        "category": "finance",
        "expected_output_contains": ["记录成功", "5000"],
    },
]


class OnboardingManager:
    """Manages the onboarding flow for first-time users.

    State persistence:
    - Uses data/onboarding.json for disk persistence
    - Also integrates with session_state for Streamlit
    """

    STATE_FILE = "data/onboarding.json"
    TOTAL_STEPS = 3

    def __init__(self) -> None:
        self._state_file = Path(self.STATE_FILE)
        self._state = OnboardingState()
        self._load_state()

    def _load_state(self) -> None:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                step_str = data.get("current_step", "welcome")
                self._state.current_step = OnboardingStep(step_str)
                self._state.started_at = data.get("started_at", time.time())
                self._state.completed_at = data.get("completed_at", 0)
                self._state.steps_completed = data.get("steps_completed", [])
                self._state.sample_task_result = data.get("sample_task_result")
            except Exception as e:
                logger.warning("Failed to load onboarding state: %s", e)

    def _save_state(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "current_step": self._state.current_step.value,
                "started_at": self._state.started_at,
                "completed_at": self._state.completed_at,
                "steps_completed": self._state.steps_completed,
                "sample_task_result": self._state.sample_task_result,
            }
            self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error("Failed to save onboarding state: %s", e)

    @property
    def state(self) -> OnboardingState:
        return self._state

    @property
    def is_completed(self) -> bool:
        if self._state.current_step == OnboardingStep.COMPLETED:
            return True
        # Check file-based marker for returning users
        if _get_onboarding_marker().exists():
            self._state.current_step = OnboardingStep.COMPLETED
            return True
        return False

    @property
    def progress_pct(self) -> int:
        if self.is_completed:
            return 100
        step_order = [
            OnboardingStep.WELCOME,
            OnboardingStep.LLM_CONFIG,
            OnboardingStep.SAMPLE_TASK,
        ]
        try:
            current_index = step_order.index(self._state.current_step)
            return int((current_index / self.TOTAL_STEPS) * 100)
        except ValueError:
            return 0

    def get_current_step(self) -> OnboardingStep:
        return self._state.current_step

    def get_step_content(self, step: Optional[OnboardingStep] = None) -> Dict[str, Any]:
        """Get content for a specific onboarding step."""
        step = step or self._state.current_step

        contents = {
            OnboardingStep.WELCOME: {
                "title": " 欢迎使用 OPC-Agents",
                "subtitle": "一人公司智能任务执行系统",
                "description": (
                    "OPC-Agents 不是聊天机器人，而是能干活的AI执行者。\n\n"
                    "告诉它你要什么结果，它直接做完并交付文件给你。\n\n"
                    " 搜索分析   内容创作   财务记录\n"
                    " 客户管理   邮件发送   日程安排"
                ),
                "features": [
                    (" 智能搜索", "实时网络搜索，不编造数据"),
                    (" 内容生成", "研究报告、方案文档、营销文案"),
                    (" 财务管理", "收支记录、报表、趋势分析"),
                    (" 客户CRM", "客户档案、跟进提醒、合作追踪"),
                ],
                "action_text": "开始配置 →",
                "action_target": "llm_config",
            },
            OnboardingStep.LLM_CONFIG: {
                "title": " 配置 AI 大脑",
                "subtitle": "选择你的LLM提供商并输入API密钥",
                "description": (
                    "OPC-Agents 需要连接大语言模型来理解你的需求并执行任务。\n"
                    "支持多种提供商，选择你最方便的一个。"
                ),
                "providers": [
                    {
                        "id": "moka",
                        "name": "MokaAI (推荐)",
                        "description": "Claude Sonnet 4，高质量中文输出",
                        "base_url": LLM_PROVIDERS["moka"],
                        "model": "moka/claude-sonnet-4-6",
                        "key_url": "https://moka-ai.com",
                    },
                    {
                        "id": "openai",
                        "name": "OpenAI",
                        "description": "GPT-4o，全球最流行的LLM",
                        "base_url": LLM_PROVIDERS["openai"],
                        "model": "gpt-4o",
                        "key_url": "https://platform.openai.com/api-keys",
                    },
                    {
                        "id": "glm",
                        "name": "智谱GLM-4",
                        "description": "国产大模型，中文能力强",
                        "base_url": LLM_PROVIDERS["zhipu"],
                        "model": "glm-4",
                        "key_url": "https://open.bigmodel.cn",
                    },
                ],
                "action_text": "测试连接 →",
                "action_target": "sample_task",
            },
            OnboardingStep.SAMPLE_TASK: {
                "title": " 试试第一个任务",
                "subtitle": "体验OPC-Agents的核心能力",
                "task": SAMPLE_TASKS[0],
                "action_text": "完成设置 →",
                "action_target": "completed",
            },
            OnboardingStep.COMPLETED: {
                "title": " 准备就绪！",
                "subtitle": "OPC-Agents 已配置完成",
                "description": (
                    "你现在可以开始使用所有功能了！\n\n"
                    " 小提示：\n"
                    "• 直接在对话框输入你的需求即可\n"
                    "• 支持21种技能：搜索、写作、财务、邮件等\n"
                    "• 所有成果物都可以导出为PDF/Word/Excel"
                ),
                "quick_start_guide": QUICK_START_GUIDE,
                "action_text": "开始使用",
                "action_target": None,
            },
        }
        return cast(Dict[str, Any], contents.get(step, {}))

    def advance_to_step(self, step: OnboardingStep) -> bool:
        """Advance to a specific step."""
        if not isinstance(step, OnboardingStep):
            return False

        old_step = self._state.current_step
        self._state.current_step = step

        if step != old_step and old_step != OnboardingStep.WELCOME:
            self._state.steps_completed.append(old_step.value)

        self._save_state()
        logger.info("Onboarding advanced: %s → %s", old_step.value, step.value)
        return True

    def complete_onboarding(self) -> None:
        """Mark onboarding as completed."""
        self._state.current_step = OnboardingStep.COMPLETED
        self._state.completed_at = time.time()
        self._save_state()
        # Write file-based marker for returning users
        marker = _get_onboarding_marker()
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(time.time()), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to write onboarding marker: %s", e)
        logger.info(
            "Onboarding completed in %.1fs",
            self._state.completed_at - self._state.started_at,
        )

    def skip_onboarding(self) -> None:
        """Allow user to skip onboarding."""
        self.complete_onboarding()

    def reset_onboarding(self) -> None:
        """Reset onboarding state (for testing/re-onboarding)."""
        self._state = OnboardingState()
        if self._state_file.exists():
            self._state_file.unlink()
        marker = _get_onboarding_marker()
        try:
            if marker.exists():
                marker.unlink()
        except Exception as e:
            logger.warning("Failed to remove onboarding marker: %s", e)
        logger.info("Onboarding reset")

    def record_sample_task_result(self, result: str) -> None:
        """Record the result of the sample task."""
        if result is not None:
            self._state.sample_task_result = str(result)[
                :_SAMPLE_TASK_RESULT_MAX_LENGTH
            ]  # truncate
        self._save_state()


def get_onboarding() -> OnboardingManager:
    return OnboardingManager()
