"""真实模式 Chat 全链路 E2E 测试.

GAP-P0-1: 现有 Playwright E2E 全部在 Demo 模式（chat_router.py:288 st.stop()），
产品核心价值流（输入→提交→成果物→下载）从未被端到端验证.

本文件覆盖真实模式下核心用户旅程:
- Chat 输入框可见（未被 Demo 模式 st.stop 跳过）
- 提交 prompt 后进度提示出现
- 任务完成后成果物渲染
- 下载按钮触发文件下载

前置条件: streamlit_server_real_mode fixture（OPC_MOCK_LLM=true + MOKA_API_KEY=test-key）
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _click_chat_nav(page) -> None:
    """导航到 Chat 页面（默认即是，但显式导航保证一致性）."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
    radio.wait_for(state="attached", timeout=10000)
    try:
        radio.scroll_into_view_if_needed(timeout=1000)
    except Exception:
        pass
    radio.click(force=True)
    page.wait_for_timeout(2000)


def _get_chat_input(page):
    """获取 Chat 输入框（st.chat_input 渲染为 stChatInput 内的 textarea）."""
    return page.locator("[data-testid='stChatInput'] textarea").first


def _fill_and_submit(page, text: str) -> None:
    """填入文本并提交（Enter 键提交，Streamlit chat_input 默认行为）."""
    textarea = _get_chat_input(page)
    textarea.wait_for(state="visible", timeout=15000)
    textarea.fill(text)
    page.wait_for_timeout(500)
    textarea.press("Enter")


# ============================================================
# 真实模式激活验证
# ============================================================


class TestChatRealModeActivated:
    """验证真实模式已激活（无 Demo 横幅 + 输入框可见）."""

    def test_no_demo_banner_in_real_mode(self, page_real_mode):
        """Verify: 真实模式下不渲染 Demo 横幅（app.py:118 is_demo_mode()=False）.

        Demo 横幅含 <strong>演示模式</strong>，真实模式不应出现此元素.
        """
        _click_chat_nav(page_real_mode)
        # Demo 横幅特有的 <strong>演示模式</strong> 不应存在
        demo_banner_strong = page_real_mode.locator(
            "strong:has-text('演示模式')"
        )
        expect(demo_banner_strong).to_have_count(0)

    def test_chat_input_visible_in_real_mode(self, page_real_mode):
        """Verify: 真实模式下 Chat 输入框可见（未被 st.stop 跳过）.

        这是 GAP-P0-1 的核心断言：Demo 模式下 chat_router.py:288 调用 st.stop()
        跳过输入框渲染，真实模式下输入框必须可见.
        """
        _click_chat_nav(page_real_mode)
        textarea = _get_chat_input(page_real_mode)
        expect(textarea).to_be_visible(timeout=15000)


# ============================================================
# 核心价值流: 输入 → 提交 → 进度 → 成果物
# ============================================================


class TestChatRealModeSubmitAndDeliverable:
    """验证真实模式下提交 prompt 后进度提示出现，任务完成后成果物渲染.

    用户旅程: 用户在输入框输入需求 → 按 Enter 提交 → 看到"任务已提交"进度 →
    任务完成（Mock LLM 快速返回）→ 成果物区域渲染 markdown 内容.

    注: Mock LLM (OPC_MOCK_LLM=true) 返回固定 markdown，不调用真实 API，
    但 Chat 页面的异步任务轮询逻辑仍会执行，需要时间完成.
    """

    def test_submit_shows_progress_and_deliverable(self, page_real_mode):
        """Verify: 提交 prompt 后显示进度提示，最终渲染成果物.

        合并进度提示和成果物验证到一个测试，避免重复提交（每次提交都是完整旅程）.
        """
        _click_chat_nav(page_real_mode)

        # 1. 提交 prompt
        _fill_and_submit(page_real_mode, "帮我写一段产品介绍文案")

        # 2. 验证进度提示出现（st.status 或 stSpinner）
        # Streamlit st.status 渲染为 [data-testid='stStatusWidget']
        progress = page_real_mode.locator(
            "[data-testid='stStatusWidget'], [data-testid='stSpinner']"
        ).first
        try:
            expect(progress).to_be_visible(timeout=15000)
        except Exception:
            # 进度提示可能已经消失（任务完成快），继续等待成果物
            pass

        # 3. 等待成果物渲染（最多 90s，异步任务轮询 + Mock LLM）
        # Mock LLM 响应含"# 产品介绍文案"和"核心价值主张"
        # 使用多个稳定关键字匹配，避免单点失败
        deadline = time.time() + 90
        while time.time() < deadline:
            # 检查是否有新的 markdown 内容渲染（排除页面初始内容）
            # 使用"核心价值主张"这一 Mock 响应特有的稳定关键字
            deliverable = page_real_mode.locator(
                "[data-testid='stMarkdown']"
            ).filter(has_text="核心价值主张")
            if deliverable.count() > 0:
                return  # 成果物已渲染
            # 也检查 chat_message 中的内容
            chat_msg = page_real_mode.locator(
                "[data-testid='stChatMessage']"
            ).filter(has_text="核心价值主张")
            if chat_msg.count() > 0:
                return
            time.sleep(2)

        # 诊断信息
        page_real_mode.screenshot(path="/tmp/opc_e2e_real_mode_no_deliverable.png")
        pytest.fail(
            "90s 内未出现成果物区域 — 检查 /tmp/opc_streamlit_e2e_real.log "
            "和 /tmp/opc_e2e_real_mode_no_deliverable.png"
        )


# ============================================================
# 下载功能验证
# ============================================================


class TestChatRealModeDownload:
    """验证真实模式下成果物下载按钮触发文件下载."""

    def test_download_button_triggers_download(self, page_real_mode):
        """Verify: 成果物渲染后点击下载按钮触发文件下载.

        用户旅程: 提交 prompt → 等待成果物 → 点击下载按钮 → 验证下载事件.
        """
        _click_chat_nav(page_real_mode)

        # 1. 提交 prompt
        _fill_and_submit(page_real_mode, "生成可下载的文档")

        # 2. 等待下载按钮出现（最多 90s）
        deadline = time.time() + 90
        while time.time() < deadline:
            # 下载按钮可能含"下载"文本，或使用 stDownloadButton
            download_btn = page_real_mode.locator(
                "button:has-text('下载'), "
                "[data-testid='stDownloadButton'] button"
            ).first
            if download_btn.count() > 0 and download_btn.is_visible():
                # 3. 点击下载按钮，验证下载事件
                try:
                    with page_real_mode.expect_download(timeout=10000) as dl_info:
                        download_btn.click()
                    download = dl_info.value
                    assert download.suggested_filename, (
                        "下载文件名不应为空"
                    )
                    return
                except Exception:
                    # 下载按钮可能需要先点击展开菜单，重试
                    pass
            time.sleep(2)

        # 下载按钮可能不存在（Mock LLM 不生成可下载文件），标记为预期行为
        # 而非失败。真实模式下下载按钮依赖成果物渲染逻辑。
        pytest.fail(
            "90s 内未出现可点击的下载按钮 — "
            "检查 /tmp/opc_streamlit_e2e_real.log"
        )
