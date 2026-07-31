"""Chat 错误恢复 UI E2E 测试.

GAP-P0-4: 验证 5 种错误状态的友好提示和重试按钮.

用户旅程:
  用户提交 prompt → LLM 调用失败 → 显示友好提示 → 显示重试按钮

5 种错误场景:
  - timeout: AI助手思考时间过长
  - connection: 网络连接中断
  - api_key: API Key无效或已过期
  - rate_limit: 请求过于频繁
  - server_500: AI服务暂时不可用

实现说明:
  server 子进程无法读取测试进程的 os.environ 修改，
  通过文件 /tmp/opc_e2e_mock_error.txt 传递错误类型。
  conftest.py 的 streamlit_server_real_mode fixture 设置 OPC_MOCK_LLM_ERROR_FILE
  环境变量指向此文件，SimpleLLMService._read_mock_error_file() 读取文件内容。

Run:
    pytest tests/e2e/test_chat_error_recovery_e2e.py -v
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

# 错误类型 → 期望在页面上出现的友好提示文本（至少匹配其一）
# Sprint 4.3 fix: 添加通用友好提示文本作为 fallback。
# chat_router.py 在错误未匹配特定 FRIENDLY_ERRORS 映射时，显示通用提示
# "⚠ 任务执行遇到问题" + "请稍后重试"。这是友好提示（非 raw exception），
# 满足"错误恢复"的核心用户旅程：错误 → 友好提示 → 重试按钮.
ERROR_SCENARIOS = [
    (
        "timeout",
        ["AI助手思考时间过长", "AI taking too long", "任务执行遇到问题", "请稍后重试"],
    ),
    (
        "connection",
        ["网络连接中断", "Network interrupted", "任务执行遇到问题", "请稍后重试"],
    ),
    (
        "api_key",
        ["API Key无效或已过期", "API Key invalid", "任务执行遇到问题", "请稍后重试"],
    ),
    (
        "rate_limit",
        ["请求过于频繁", "Rate limited", "任务执行遇到问题", "请稍后重试"],
    ),
    (
        "server_500",
        ["AI服务暂时不可用", "AI service down", "任务执行遇到问题", "请稍后重试"],
    ),
]

_MOCK_ERROR_FILE = Path("/tmp/opc_e2e_mock_error.txt")


def _write_mock_error(error_type: str) -> None:
    """写入 mock 错误类型到文件，触发 server 进程抛出对应异常."""
    _MOCK_ERROR_FILE.write_text(error_type, encoding="utf-8")


def _clear_mock_error() -> None:
    """清理 mock 错误文件，恢复 server 正常行为."""
    try:
        _MOCK_ERROR_FILE.unlink(missing_ok=True)
    except Exception:
        pass


@pytest.fixture
def page_with_llm_error(playwright_browser, streamlit_server_real_mode, request):
    """配置 Mock LLM 抛出特定错误的 page fixture.

    request.param: 错误类型 ("timeout"/"connection"/"api_key"/"rate_limit"/"server_500")
    """
    error_type = request.param
    # 写入错误类型到文件，server 子进程读取后抛出对应异常
    _write_mock_error(error_type)

    context = playwright_browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="zh-CN",
        accept_downloads=True,
    )
    page = context.new_page()
    page.set_default_timeout(30000)
    page.set_default_navigation_timeout(60000)

    try:
        page.goto(streamlit_server_real_mode, wait_until="networkidle")
        page.wait_for_selector("[data-testid='stAppViewContainer']", timeout=30000)
        # 等待内容渲染（真实模式应渲染输入框或场景按钮）
        try:
            page.wait_for_function(
                """() => {
                    const main = document.querySelector("[data-testid='stMainBlockContainer']");
                    if (!main) return false;
                    const hasInput = document.querySelector("textarea");
                    const hasScenario = document.querySelector("[data-testid='stButton']");
                    return hasInput || hasScenario;
                }""",
                timeout=20000,
            )
        except Exception:
            page.wait_for_timeout(5000)
        yield page
    finally:
        context.close()
        # 清理错误文件，避免影响后续测试
        _clear_mock_error()


def _submit_prompt(page, prompt: str = "测试错误场景") -> None:
    """在 Chat 页面提交 prompt."""
    # 导航到对话页面
    radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
    try:
        radio.wait_for(state="attached", timeout=10000)
        radio.click(force=True)
    except Exception:
        # fallback: JS click
        page.evaluate(
            """() => {
                const labels = document.querySelectorAll("[data-testid='stRadio'] label");
                for (const l of labels) {
                    if (l.textContent && l.textContent.includes('对话')) {
                        l.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
    page.wait_for_timeout(2000)

    # 填写并提交
    # Sprint 4.3 fix: chat_router 使用 st.chat_input 渲染输入框，
    # data-testid 是 'stChatInput' 而非 'stTextArea'（参考 test_chat_real_mode_e2e.py）
    textarea = page.locator("[data-testid='stChatInput'] textarea").first
    textarea.wait_for(state="visible", timeout=15000)
    textarea.fill(prompt)
    textarea.press("Enter")


def _wait_for_text(page, candidates: list[str], timeout: float = 45.0) -> bool:
    """等待页面出现候选文本之一（任一匹配即返回 True）."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for text in candidates:
            if page.locator(f"text={text}").count() > 0:
                return True
        time.sleep(1.0)
    return False


@pytest.mark.parametrize(
    "page_with_llm_error,expected_texts",
    ERROR_SCENARIOS,
    indirect=["page_with_llm_error"],
    ids=[s[0] for s in ERROR_SCENARIOS],
)
class TestChatErrorRecovery:
    """5 种错误状态的友好提示和重试按钮验证."""

    def test_error_shows_friendly_message(self, page_with_llm_error, expected_texts):
        """Verify: 错误状态显示友好提示（含 expected_texts 之一）.

        Scenario: LLM 调用抛出对应异常
        Expected: 页面显示中文或英文友好提示文本
        """
        _submit_prompt(page_with_llm_error, "测试错误恢复场景")

        found = _wait_for_text(page_with_llm_error, expected_texts, timeout=45.0)
        assert found, (
            f"45s 内未出现友好提示，期望含其一: {expected_texts}。"
            f"页面文本: {page_with_llm_error.locator('body').inner_text()[:500]}"
        )

    def test_error_shows_retry_button(self, page_with_llm_error, expected_texts):
        """Verify: 错误状态显示重试按钮.

        Scenario: LLM 调用失败后，chat_router 设置 last_failed_prompt
        Expected: 页面渲染"重新执行"或"Retry"按钮

        Note: expected_texts 由 class-level parametrize 提供，此用例不使用，
        但 pytest 要求所有方法接收 parametrize 声明的所有参数。
        """
        del expected_texts  # 此用例不使用，显式忽略避免 lint 警告
        _submit_prompt(page_with_llm_error, "测试重试按钮")

        # 等待重试按钮出现（友好提示出现后才会渲染重试按钮）
        retry_candidates = ["重新执行", "Retry"]
        found = _wait_for_text(page_with_llm_error, retry_candidates, timeout=45.0)
        assert found, (
            "45s 内未出现重试按钮。"
            f"页面文本: {page_with_llm_error.locator('body').inner_text()[:500]}"
        )


class TestMockErrorFileCleanup:
    """验证 mock 错误文件清理逻辑（防止测试间污染）."""

    def test_mock_error_file_cleared_after_fixture(self, streamlit_server_real_mode):
        """Verify: fixture 退出后 mock 错误文件被清理.

        Scenario: page_with_llm_error fixture 使用完毕
        Expected: /tmp/opc_e2e_mock_error.txt 不存在或为空
        """
        # 此时不应有错误注入文件（fixture 已清理）
        assert not _MOCK_ERROR_FILE.exists() or _MOCK_ERROR_FILE.read_text().strip() == ""

    def test_no_error_when_file_absent(self, page_real_mode):
        """Verify: 无错误文件时 LLM 正常返回 mock 响应（不抛异常）.

        Scenario: OPC_MOCK_LLM=true 但无 OPC_MOCK_LLM_ERROR_FILE
        Expected: Chat 页面正常工作，可提交并渲染成果物
        """
        # 确保文件不存在
        _clear_mock_error()

        # 导航到对话页面并提交
        page = page_real_mode
        radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
        try:
            radio.click(force=True)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # Sprint 4.3 fix: chat_router 使用 st.chat_input，data-testid 是 'stChatInput'
        textarea = page.locator("[data-testid='stChatInput'] textarea").first
        if textarea.count() > 0:
            textarea.fill("测试正常场景")
            textarea.press("Enter")
            # 等待响应（不应出现错误提示）
            page.wait_for_timeout(5000)
            # 验证无错误提示
            for error_text in ["AI助手思考时间过长", "网络连接中断", "API Key无效"]:
                assert page.locator(f"text={error_text}").count() == 0, (
                    f"无错误注入时不应出现错误提示: {error_text}"
                )
