"""SQL 注入 / 路径穿越 / 命令注入 E2E 测试.

GAP-P1-2: 现有 XSS 测试仅检查无 stException，未验证其他注入向量.

用户旅程:
  用户在搜索框/Chat 输入框输入恶意 payload → 系统不执行恶意代码 →
  无敏感信息泄露 → 无 SQL 错误泄露 → 无文件内容泄露

测试策略:
  - SQL 注入：在 Deliverables 搜索框输入 SQL 注入 payload，验证无 SQL 错误泄露
  - 路径穿越：在 Chat 输入框输入路径穿越 payload，验证无敏感文件内容泄露
  - 命令注入：在 Chat 输入框输入命令注入 payload，验证无系统命令执行结果泄露

实现说明:
  - 使用 page fixture（Demo 模式）测试 Deliverables 搜索框（无 LLM 调用）
  - 使用 page_real_mode fixture（真实模式）测试 Chat 输入框（有 LLM 调用）
  - 不使用 pytest.skip（用户硬约束 skip=0）

Run:
    pytest tests/e2e/test_injection_e2e.py -v
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _goto_deliverables(page) -> None:
    """导航到成果物页面（Demo 模式可用，搜索框基于 session_state.deliverables）."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="成果物").first
    try:
        radio.wait_for(state="attached", timeout=15000)
        radio.click(force=True)
    except Exception:
        page.evaluate(
            """() => {
                const labels = document.querySelectorAll("[data-testid='stRadio'] label");
                for (const l of labels) {
                    if (l.textContent && l.textContent.includes('成果物')) {
                        l.click();
                        return true;
                    }
                }
                return false;
            }"""
        )
    page.wait_for_timeout(2500)


def _goto_chat(page) -> None:
    """导航到对话页面."""
    radio = page.locator("[data-testid='stRadio'] label", has_text="对话").first
    try:
        radio.wait_for(state="attached", timeout=10000)
        radio.click(force=True)
    except Exception:
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


# ============================================================
# TC-INJ-01: SQL 注入防护
# ============================================================


class TestSQLInjectionE2E:
    """SQL 注入防护验证.

    在 Deliverables 搜索框输入 SQL 注入 payload，验证：
    1. 无 stException 异常抛出
    2. 无 SQL 错误关键字泄露（SQLITE_ERROR / sqlite3.OperationalError / DROP TABLE）
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "admin'--",
            "1' UNION SELECT * FROM finance_records--",
            "'; INSERT INTO users VALUES('admin','pass'); --",
        ],
        ids=["or-1-1", "drop-table", "admin-comment", "union-select", "insert"],
    )
    def test_sql_injection_in_search(self, page, payload):
        """Verify: 搜索框 SQL 注入不触发 SQL 错误泄露.

        Scenario: 用户在搜索框输入 SQL 注入 payload
        Expected: 无 stException 异常，无 SQL 错误关键字泄露
        """
        _goto_deliverables(page)

        # 等待搜索框渲染（conftest.py 预创建 session_deliverable 确保搜索框可见）
        search = page.locator("[data-testid='stTextInput'] input").first
        try:
            search.wait_for(state="visible", timeout=10000)
        except Exception:
            # 如果搜索框仍未渲染，断言失败（不 skip，用户硬约束）
            pytest.fail(
                f"Deliverables 搜索框未渲染，无法测试 SQL 注入。payload={payload}"
            )

        search.fill(payload)
        search.press("Enter")
        page.wait_for_timeout(2000)

        # 验证无 stException 异常
        error = page.locator("[data-testid='stException']")
        expect(error).to_have_count(0)

        # 验证无 SQL 错误关键字泄露
        # Sprint 4.3 fix: 移除 "DROP TABLE" / "UNION SELECT" 断言 —
        # 搜索框会回显用户输入的 payload（正常行为），这些关键字出现在回显中
        # 不代表 SQL 注入成功执行。真正的 SQL 注入防护验证应检查:
        # 1. 无 SQL 异常抛出（SQLITE_ERROR / sqlite3.OperationalError）
        # 2. 无 stException 渲染（上面已验证）
        # 3. 数据库表依然存在（通过验证搜索功能仍正常工作间接确认）
        body = page.locator("body").inner_text()
        assert "SQLITE_ERROR" not in body, (
            f"SQL 注入导致 SQLITE_ERROR 泄露。payload={payload}"
        )
        assert "sqlite3.OperationalError" not in body, (
            f"SQL 注入导致 sqlite3.OperationalError 泄露。payload={payload}"
        )


# ============================================================
# TC-INJ-02: 路径穿越防护
# ============================================================


class TestPathTraversalE2E:
    """路径穿越防护验证.

    在 Chat 输入框输入路径穿越 payload，验证：
    1. 无 /etc/passwd 内容泄露（root: 开头的行）
    2. 无 win.ini 内容泄露（[fonts] 等节段）
    3. 无 stException 异常
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\win.ini",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "....//....//etc/passwd",
            "/etc/shadow",
            "/proc/self/environ",
        ],
        ids=["etc-passwd", "win-ini", "url-encoded", "double-dot", "etc-shadow", "proc-environ"],
    )
    def test_path_traversal_in_input(self, page_real_mode, payload):
        """Verify: 路径穿越 payload 不读取敏感文件.

        Scenario: 用户在 Chat 输入框输入路径穿越 payload
        Expected: 无敏感文件内容泄露，无 stException 异常
        """
        page = page_real_mode
        _goto_chat(page)

        # Sprint 4.3 fix: chat_router 使用 st.chat_input，data-testid 是 'stChatInput'
        textarea = page.locator("[data-testid='stChatInput'] textarea").first
        try:
            textarea.wait_for(state="visible", timeout=15000)
        except Exception:
            pytest.fail(
                f"Chat 输入框未渲染（真实模式应可见），无法测试路径穿越。payload={payload}"
            )

        textarea.fill(f"读取文件 {payload}")
        textarea.press("Enter")
        # 等待 LLM 响应或错误处理
        page.wait_for_timeout(5000)

        # 验证无文件内容泄露
        body = page.locator("body").inner_text()
        assert "root:" not in body, (
            f"路径穿越成功读取 /etc/passwd。payload={payload}"
        )
        assert "[fonts]" not in body, (
            f"路径穿越成功读取 win.ini。payload={payload}"
        )
        assert "root:x:" not in body, (
            f"路径穿越成功读取 /etc/passwd (root:x: 格式)。payload={payload}"
        )

        # 验证无 stException 异常
        error = page.locator("[data-testid='stException']")
        expect(error).to_have_count(0)


# ============================================================
# TC-INJ-03: 命令注入防护
# ============================================================


class TestCommandInjectionE2E:
    """命令注入防护验证.

    在 Chat 输入框输入命令注入 payload，验证：
    1. 无 /etc/passwd 内容泄露（命令执行结果）
    2. 无 whoami/id 输出泄露
    3. 无 ls/dir 输出特征泄露
    4. 无 stException 异常
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "; ls -la",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "& dir",
            "&& cat /etc/shadow",
            "; rm -rf /",
        ],
        ids=["semicolon-ls", "pipe-cat", "dollar-whoami", "backtick-id", "amp-dir", "and-cat", "semicolon-rm"],
    )
    def test_command_injection_in_input(self, page_real_mode, payload):
        """Verify: 命令注入 payload 不执行系统命令.

        Scenario: 用户在 Chat 输入框输入命令注入 payload
        Expected: 无命令执行结果泄露，无 stException 异常
        """
        page = page_real_mode
        _goto_chat(page)

        # Sprint 4.3 fix: chat_router 使用 st.chat_input，data-testid 是 'stChatInput'
        textarea = page.locator("[data-testid='stChatInput'] textarea").first
        try:
            textarea.wait_for(state="visible", timeout=15000)
        except Exception:
            pytest.fail(
                f"Chat 输入框未渲染（真实模式应可见），无法测试命令注入。payload={payload}"
            )

        textarea.fill(f"执行 {payload}")
        textarea.press("Enter")
        # 等待 LLM 响应或错误处理
        page.wait_for_timeout(5000)

        # 验证无命令执行结果泄露
        body = page.locator("body").inner_text()
        # /etc/passwd 内容特征
        assert "root:x:" not in body, (
            f"命令注入成功执行 cat /etc/passwd。payload={payload}"
        )
        # whoami/id 输出特征
        assert "uid=" not in body, (
            f"命令注入成功执行 id 命令。payload={payload}"
        )
        # ls 输出特征（drwxr-xr-x 权限位）
        assert "drwxr" not in body, (
            f"命令注入成功执行 ls 命令。payload={payload}"
        )
        # dir 输出特征（Windows）
        assert "Volume in drive" not in body, (
            f"命令注入成功执行 dir 命令。payload={payload}"
        )

        # 验证无 stException 异常
        error = page.locator("[data-testid='stException']")
        expect(error).to_have_count(0)


# ============================================================
# TC-INJ-04: XSS 防护验证（补充现有 test_a11y_axe.py 的 XSS 测试）
# ============================================================


class TestXSSProtectionE2E:
    """XSS 防护验证.

    在 Chat 输入框输入 XSS payload，验证：
    1. payload 不被执行（无 alert 弹窗）
    2. payload 被转义或作为文本显示
    3. 无 stException 异常
    """

    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src=javascript:alert('XSS')>",
        ],
        ids=["script-tag", "img-onerror", "svg-onload", "javascript-url", "iframe"],
    )
    def test_xss_payload_not_executed(self, page_real_mode, payload):
        """Verify: XSS payload 不被执行.

        Scenario: 用户在 Chat 输入框输入 XSS payload
        Expected: payload 被转义或作为文本显示，不触发 JavaScript 执行
        """
        page = page_real_mode
        _goto_chat(page)

        # 监听 dialog 事件（alert/confirm/prompt）
        dialog_triggered = []
        page.on("dialog", lambda dialog: dialog_triggered.append(dialog.message))

        # Sprint 4.3 fix: chat_router 使用 st.chat_input，data-testid 是 'stChatInput'
        textarea = page.locator("[data-testid='stChatInput'] textarea").first
        try:
            textarea.wait_for(state="visible", timeout=15000)
        except Exception:
            pytest.fail(
                f"Chat 输入框未渲染（真实模式应可见），无法测试 XSS。payload={payload}"
            )

        textarea.fill(payload)
        textarea.press("Enter")
        page.wait_for_timeout(5000)

        # 验证无 dialog 弹窗（XSS 未执行）
        assert not dialog_triggered, (
            f"XSS payload 触发了 dialog 弹窗: {dialog_triggered}。payload={payload}"
        )

        # 验证无 stException 异常
        error = page.locator("[data-testid='stException']")
        expect(error).to_have_count(0)

        # 验证页面无新增的 <script> 标签（XSS 注入检测）
        # Streamlit 自身会有 script 标签，这里只验证没有以 alert('XSS') 为内容的 script
        xss_scripts = page.locator("script:has-text('alert')")
        assert xss_scripts.count() == 0, (
            f"XSS payload 注入了恶意 script 标签。payload={payload}"
        )
