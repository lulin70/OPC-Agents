"""SmtpHandlers 覆盖率补充测试

覆盖 `opc_manager/tool_handlers_smtp.py` 中以下未覆盖路径：
- `_execute_send_email` 邮箱校验 / CRLF 清洗
- `_execute_send_email` SMTP 已配置分支：成功(early return) / 发送失败降级 / 异常降级
- `_execute_send_email` SMTP 未配置 → notification 落盘（成功 + 失败回退）
- `_send_smtp_sync` 静态方法：TLS / non-TLS / 异常返回
- `_write_notification_sync` 静态方法：建目录 + 写入

外部 SMTP 服务器使用 `unittest.mock` 模拟（必要性：无真实 SMTP 服务器），
文件落盘使用真实 tmp_path 文件系统。
"""

import json
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from opc_manager.tool_handlers_smtp import SmtpHandlers


class _SmtpHandler(SmtpHandlers):
    """SmtpHandlers 是 Mixin，需要具体子类实例化后才能调用 self 方法。"""

    pass


@pytest.fixture
def smtp_handler() -> _SmtpHandler:
    """提供独立的 SmtpHandlers 实例。"""
    return _SmtpHandler()


@pytest.fixture
def clean_smtp_env(monkeypatch):
    """清空 SMTP 环境变量，确保每条测试从已知状态开始。"""
    for var in (
        "OPC_SMTP_HOST",
        "OPC_SMTP_USER",
        "OPC_SMTP_PASS",
        "OPC_SMTP_FROM",
        "OPC_SMTP_TLS",
    ):
        monkeypatch.delenv(var, raising=False)


# ─── 邮箱校验 / CRLF 清洗 ─────────────────────────────────────────


class TestEmailValidation:
    """覆盖 to/subject 清洗与邮箱格式校验。"""

    @pytest.mark.asyncio
    async def test_invalid_email_returns_error(self, smtp_handler, clean_smtp_env):
        """非法邮箱格式应返回 sent=False 与错误信息。"""
        result = await smtp_handler._execute_send_email("not-an-email", "s", "b")

        assert result["sent"] is False
        assert "Invalid email address" in result["error"]

    @pytest.mark.asyncio
    async def test_empty_email_returns_error(self, smtp_handler, clean_smtp_env):
        """空收件人应返回 sent=False。"""
        result = await smtp_handler._execute_send_email("", "s", "b")

        assert result["sent"] is False
        assert "Invalid email address" in result["error"]

    @pytest.mark.asyncio
    async def test_crlf_in_to_makes_email_invalid(
        self, smtp_handler, clean_smtp_env, monkeypatch
    ):
        """to 中的 CRLF 被清洗后若不再匹配邮箱正则，应返回 sent=False。"""
        # 清洗后："to@example.comBcc: evil@x.com" 含空格 → 不匹配正则
        poisoned_to = "to@example.com\r\nBcc: evil@x.com"

        result = await smtp_handler._execute_send_email(poisoned_to, "subj", "body")

        assert result["sent"] is False
        assert "Invalid email address" in result["error"]


# ─── _execute_send_email: SMTP 已配置分支 ─────────────────────────


class TestExecuteSendEmailSmtpConfigured:
    """覆盖 SMTP 环境变量齐全时的发送分支。"""

    @pytest.mark.asyncio
    async def test_smtp_success_returns_smtp_mode(self, smtp_handler, monkeypatch):
        """SMTP 配置齐全且发送成功 → 直接返回 delivery_mode=smtp，不落盘。"""
        monkeypatch.setenv("OPC_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("OPC_SMTP_USER", "user@example.com")
        monkeypatch.setenv("OPC_SMTP_PASS", "secret")
        monkeypatch.setenv("OPC_SMTP_TLS", "true")

        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server) as mock_smtp:
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["sent"] is True
        assert result["delivery_mode"] == "smtp"
        assert result["to"] == "to@example.com"
        assert result["subject"] == "subj"
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        assert mock_server.ehlo.call_count == 2
        mock_server.login.assert_called_once_with("user@example.com", "secret")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @pytest.mark.asyncio
    async def test_smtp_no_tls_success(self, smtp_handler, monkeypatch):
        """OPC_SMTP_TLS=false 时不调用 starttls/ehlo。"""
        monkeypatch.setenv("OPC_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("OPC_SMTP_USER", "user@example.com")
        monkeypatch.setenv("OPC_SMTP_PASS", "secret")
        monkeypatch.setenv("OPC_SMTP_TLS", "false")

        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["delivery_mode"] == "smtp"
        mock_server.starttls.assert_not_called()
        mock_server.ehlo.assert_not_called()

    @pytest.mark.asyncio
    async def test_smtp_from_defaults_to_user(self, smtp_handler, monkeypatch):
        """未设置 OPC_SMTP_FROM 时 from_addr 默认等于 OPC_SMTP_USER。"""
        monkeypatch.setenv("OPC_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("OPC_SMTP_USER", "defaultuser@example.com")
        monkeypatch.setenv("OPC_SMTP_PASS", "secret")
        monkeypatch.delenv("OPC_SMTP_FROM", raising=False)

        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["delivery_mode"] == "smtp"
        sendmail_args = mock_server.sendmail.call_args[0]
        assert sendmail_args[0] == "defaultuser@example.com"

    @pytest.mark.asyncio
    async def test_smtp_send_failure_falls_back_to_log(self, smtp_handler, monkeypatch):
        """_send_smtp_sync 返回 sent=False → 降级到 logged 模式。"""
        monkeypatch.setenv("OPC_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("OPC_SMTP_USER", "user@example.com")
        monkeypatch.setenv("OPC_SMTP_PASS", "secret")

        # 让 server.login 抛异常 → _send_smtp_sync 内部捕获并返回 sent=False
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"auth failed"
        )
        with patch("smtplib.SMTP", return_value=mock_server):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["sent"] is True
        assert result["delivery_mode"] == "logged"
        assert result["to"] == "to@example.com"

    @pytest.mark.asyncio
    async def test_smtp_method_exception_falls_back_to_log(
        self, smtp_handler, monkeypatch
    ):
        """_send_smtp_sync 抛出未捕获异常 → 降级到 logged 模式（覆盖 except 分支）。"""
        monkeypatch.setenv("OPC_SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("OPC_SMTP_USER", "user@example.com")
        monkeypatch.setenv("OPC_SMTP_PASS", "secret")

        with patch.object(
            smtp_handler,
            "_send_smtp_sync",
            side_effect=RuntimeError("unexpected executor failure"),
        ):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["sent"] is True
        assert result["delivery_mode"] == "logged"


# ─── _execute_send_email: notification 落盘分支 ───────────────────


class TestExecuteSendEmailNotificationFallback:
    """覆盖 SMTP 未配置时的 notification 落盘分支。"""

    @pytest.mark.asyncio
    async def test_notification_logged_when_smtp_unconfigured(
        self, smtp_handler, clean_smtp_env
    ):
        """SMTP 未配置 → 写入 notification 文件并返回 delivery_mode=logged。"""
        result = await smtp_handler._execute_send_email(
            "to@example.com", "subj", "body content"
        )

        assert result["sent"] is True
        assert result["delivery_mode"] == "logged"
        assert result["to"] == "to@example.com"
        assert result["subject"] == "subj"
        assert result["log_file"].startswith("notification_")
        assert result["log_file"].endswith(".json")

    @pytest.mark.asyncio
    async def test_notification_includes_attachments(
        self, smtp_handler, clean_smtp_env
    ):
        """attachments 参数应被透传到返回结果。"""
        result = await smtp_handler._execute_send_email(
            "to@example.com",
            "subj",
            "body",
            attachments=["/tmp/a.txt", "/tmp/b.txt"],
        )

        assert result["sent"] is True
        assert result["attachments"] == ["/tmp/a.txt", "/tmp/b.txt"]

    @pytest.mark.asyncio
    async def test_notification_write_failure_still_returns_logged(
        self, smtp_handler, clean_smtp_env
    ):
        """notification 落盘失败时仍返回 logged（覆盖 except 分支，不抛异常）。"""
        with patch.object(
            smtp_handler,
            "_write_notification_sync",
            side_effect=OSError("disk full"),
        ):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", "body"
            )

        assert result["sent"] is True
        assert result["delivery_mode"] == "logged"

    @pytest.mark.asyncio
    async def test_notification_body_truncated_to_5000_chars(
        self, smtp_handler, clean_smtp_env, tmp_path, monkeypatch
    ):
        """body 超过 5000 字符时应被截断后落盘。"""
        long_body = "x" * 6000
        captured: dict = {}

        original_write = SmtpHandlers._write_notification_sync

        def capture_write(filepath, notification):
            captured["filepath"] = filepath
            captured["notification"] = notification
            return original_write(filepath, notification)

        with patch.object(
            smtp_handler, "_write_notification_sync", side_effect=capture_write
        ):
            result = await smtp_handler._execute_send_email(
                "to@example.com", "subj", long_body
            )

        assert result["sent"] is True
        assert len(captured["notification"]["body"]) == 5000
        assert captured["notification"]["status"] == "logged"
        assert captured["notification"]["type"] == "email"


# ─── _send_smtp_sync (static) ─────────────────────────────────────


class TestSendSmtpSync:
    """覆盖 _send_smtp_sync 静态方法的 TLS / non-TLS / 异常路径。"""

    def test_send_smtp_sync_tls_success(self):
        """use_tls=True 时调用 starttls + 两次 ehlo + login + sendmail + quit。"""
        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = SmtpHandlers._send_smtp_sync(
                "smtp.example.com",
                587,
                "u@x.com",
                "pw",
                "from@x.com",
                "to@x.com",
                "subj",
                "body",
                True,
            )

        assert result == {
            "sent": True,
            "to": "to@x.com",
            "subject": "subj",
            "delivery_mode": "smtp",
        }
        mock_server.starttls.assert_called_once()
        assert mock_server.ehlo.call_count == 2
        mock_server.login.assert_called_once_with("u@x.com", "pw")
        sendmail_args = mock_server.sendmail.call_args[0]
        assert sendmail_args[0] == "from@x.com"
        assert sendmail_args[1] == ["to@x.com"]
        mock_server.quit.assert_called_once()

    def test_send_smtp_sync_no_tls_success(self):
        """use_tls=False 时不调用 starttls/ehlo，直接 login + sendmail。"""
        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = SmtpHandlers._send_smtp_sync(
                "smtp.example.com",
                25,
                "u@x.com",
                "pw",
                "from@x.com",
                "to@x.com",
                "subj",
                "body",
                False,
            )

        assert result["sent"] is True
        mock_server.starttls.assert_not_called()
        mock_server.ehlo.assert_not_called()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    def test_send_smtp_sync_exception_returns_error(self):
        """smtplib.SMTP 抛异常时返回 sent=False 与错误描述。"""
        with patch(
            "smtplib.SMTP", side_effect=ConnectionRefusedError("connection refused")
        ):
            result = SmtpHandlers._send_smtp_sync(
                "smtp.example.com",
                587,
                "u@x.com",
                "pw",
                "from@x.com",
                "to@x.com",
                "subj",
                "body",
                True,
            )

        assert result["sent"] is False
        assert "connection refused" in result["error"]

    def test_send_smtp_sync_accepts_attachments_argument(self):
        """attachments 参数应被接受（当前实现仅传参，未实际附加）。"""
        mock_server = MagicMock()
        with patch("smtplib.SMTP", return_value=mock_server):
            result = SmtpHandlers._send_smtp_sync(
                "smtp.example.com",
                587,
                "u@x.com",
                "pw",
                "from@x.com",
                "to@x.com",
                "subj",
                "body",
                True,
                ["/tmp/a.txt", "/tmp/b.txt"],
            )

        assert result["sent"] is True


# ─── _write_notification_sync (static) ────────────────────────────


class TestWriteNotificationSync:
    """覆盖 _write_notification_sync 静态方法。"""

    def test_creates_nested_dir_and_writes_json(self, tmp_path):
        """目标父目录不存在时应自动创建，并写入 JSON。"""
        nested = tmp_path / "deep" / "nested" / "note.json"

        SmtpHandlers._write_notification_sync(str(nested), {"a": 1, "b": "中文"})

        assert nested.is_file()
        data = json.loads(nested.read_text(encoding="utf-8"))
        assert data == {"a": 1, "b": "中文"}

    def test_overwrites_existing_file(self, tmp_path):
        """已存在的文件应被覆盖写入。"""
        target = tmp_path / "note.json"
        target.write_text("old-content", encoding="utf-8")

        SmtpHandlers._write_notification_sync(str(target), {"new": True})

        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"new": True}

    def test_writes_unicode_content_ensure_ascii_false(self, tmp_path):
        """非 ASCII 字符应以原文写入（ensure_ascii=False）。"""
        target = tmp_path / "unicode.json"

        SmtpHandlers._write_notification_sync(str(target), {"msg": "你好世界 — メール"})

        raw = target.read_text(encoding="utf-8")
        assert "你好世界" in raw
        assert "メール" in raw
