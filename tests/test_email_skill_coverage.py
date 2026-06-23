"""Email Skill 覆盖率补充测试

目标：将 email_skill.py 覆盖率从 16.96% 提升到 ≥60%

覆盖范围：
- SMTP 配置读取/保存 (_get_smtp_config / save_smtp_config)
- 邮件字段清洗与校验 (_sanitize_email_field / _validate_email)
- 频率限制 (_count_today_sends / _check_rate_limit)
- 邮件发送 (send_email) 成功/失败/重试/各种校验分支
- 异步发送 (send_email_async)
- 模板管理 (list_templates / get_template / render_template / create_template)
- 邮件历史查询 (list_email_history)
- 收件人姓名查找 (_lookup_email_by_name)
- 自然语言入口 (execute_goal) 各分支
- 撤销发送 (undo_send_email)

外部依赖全部 mock：
- smtplib.SMTP_SSL / smtplib.SMTP → mock server
- time.sleep → 跳过重试等待
- CRM get_customer → mock 返回
- 数据库 → 临时目录 (OPC_DATA_DIR=tmp_path)
"""

import asyncio
import json
import os
import smtplib
from unittest.mock import MagicMock, mock_open, patch

import pytest

import opc_manager.data_manager as dm
from opc_manager.email_skill import (
    BLOCKED_EXTENSIONS,
    MAX_BODY_SIZE,
    MAX_DAILY_SENDS,
    MAX_RETRIES,
    RATE_LIMIT_MAX,
    RATE_LIMIT_WINDOW,
    _check_rate_limit,
    _count_today_sends,
    _get_smtp_config,
    _lookup_email_by_name,
    _sanitize_email_field,
    _validate_email,
    create_template,
    execute_goal,
    get_template,
    list_email_history,
    list_templates,
    render_template,
    save_smtp_config,
    send_email,
    send_email_async,
    undo_send_email,
)
from opc_manager.tool_system import AuditLogger

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """临时数据库环境，每个测试独立隔离。

    直接更新 data_manager 模块级变量 DATA_DIR/DB_PATH 到临时目录，
    确保 DB 操作完全隔离（仅 setenv 不够，因为变量在模块导入时已固定）。
    """
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    monkeypatch.setenv("OPC_DATA_DIR", str(db_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-key-for-encryption-32chars!!")

    _orig_initialized = dm._db_initialized
    _orig_conn = getattr(dm._local, "conn", None)
    _orig_data_dir = dm.DATA_DIR
    _orig_db_path = dm.DB_PATH

    dm.DATA_DIR = str(db_dir)
    dm.DB_PATH = str(db_dir / "opc_data.db")
    dm._db_initialized = False
    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None

    # 将审计日志重定向到临时目录，避免污染仓库
    orig_log_file = AuditLogger._log_file
    AuditLogger._log_file = str(tmp_path / "audit.jsonl")

    yield db_dir

    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None
    dm._db_initialized = _orig_initialized
    dm.DATA_DIR = _orig_data_dir
    dm.DB_PATH = _orig_db_path
    AuditLogger._log_file = orig_log_file


@pytest.fixture
def smtp_config():
    """标准 SMTP 配置（用于 mock _get_smtp_config 返回值）。"""
    return {
        "host": "smtp.test.com",
        "port": 465,
        "username": "sender@test.com",
        "password": "secret-pass",
        "ssl": True,
        "from_addr": "sender@test.com",
    }


def _make_mock_smtp():
    """创建一个 mock SMTP server 实例。"""
    server = MagicMock()
    server.sendmail.return_value = {}
    server.quit.return_value = None
    server.login.return_value = None
    return server


# ---------------------------------------------------------------------------
# _sanitize_email_field / _validate_email
# ---------------------------------------------------------------------------


class TestSanitizeAndValidate:
    def test_sanitize_removes_crlf(self):
        assert _sanitize_email_field("a\r\nb\nc") == "abc"

    def test_sanitize_no_change(self):
        assert _sanitize_email_field("plain text") == "plain text"

    def test_validate_email_valid(self):
        assert _validate_email("user@example.com") is True
        assert _validate_email("a.b+c-d@sub.example.co.uk") is True

    def test_validate_email_invalid(self):
        assert _validate_email("not-an-email") is False
        assert _validate_email("missing@domain") is False
        assert _validate_email("@nodomain.com") is False
        assert _validate_email("") is False
        assert _validate_email("spaces in@addr.com") is False


# ---------------------------------------------------------------------------
# _get_smtp_config / save_smtp_config
# ---------------------------------------------------------------------------


class TestSmtpConfig:
    @patch("opc_manager.email_skill.os.path.exists", return_value=False)
    def test_get_smtp_config_no_file(self, _mock_exists):
        assert _get_smtp_config() is None

    @patch("opc_manager.email_skill.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_get_smtp_config_valid_plain(self, mock_file, _mock_exists):
        config = {
            "host": "smtp.test.com",
            "port": 465,
            "username": "u@test.com",
            "password": "plain",
            "ssl": True,
        }
        mock_file.return_value.read.return_value = json.dumps(config)
        result = _get_smtp_config()
        assert result["host"] == "smtp.test.com"
        assert result["password"] == "plain"

    @patch("opc_manager.email_skill.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    def test_get_smtp_config_encrypted_password(self, mock_file, _mock_exists):
        from opc_manager.data_manager import encrypt_field

        encrypted = encrypt_field("my-secret")
        config = {
            "host": "smtp.test.com",
            "username": "u@test.com",
            "password": encrypted,
            "password_encrypted": True,
        }
        mock_file.return_value.read.return_value = json.dumps(config)
        result = _get_smtp_config()
        assert result["password"] == "my-secret"

    @patch("opc_manager.email_skill.os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("read error"))
    def test_get_smtp_config_read_error(self, _mock_open, _mock_exists):
        assert _get_smtp_config() is None

    @patch("opc_manager.email_skill.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_smtp_config_with_password(self, mock_file, _mock_makedirs):
        result = save_smtp_config(
            {"host": "smtp.test.com", "username": "u@test.com", "password": "secret"}
        )
        assert result["success"] is True
        # 验证写入的 JSON 中密码已加密
        written = mock_file.return_value.write.call_args_list
        # json.dump 会多次调用 write，拼接得到完整 JSON
        full_json = "".join(call.args[0] for call in written)
        saved = json.loads(full_json)
        assert saved["password"] != "secret"
        assert saved["password_encrypted"] is True

    @patch("opc_manager.email_skill.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_smtp_config_no_password(self, mock_file, _mock_makedirs):
        result = save_smtp_config({"host": "smtp.test.com", "username": "u@test.com"})
        assert result["success"] is True

    @patch("opc_manager.email_skill.os.makedirs", side_effect=OSError("disk full"))
    def test_save_smtp_config_error(self, _mock_makedirs):
        result = save_smtp_config({"host": "smtp.test.com", "password": "x"})
        assert result["success"] is False
        assert "disk full" in result["error"]


# ---------------------------------------------------------------------------
# _count_today_sends / _check_rate_limit
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_count_today_sends_empty(self, temp_db):
        dm.init_db()
        assert _count_today_sends() == 0

    def test_count_today_sends_with_records(self, temp_db):
        dm.init_db()
        import time as _time

        now = _time.strftime("%Y-%m-%dT%H:%M:%S")
        for i in range(3):
            dm.execute_write(
                "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (f"id{i}", "to@test.com", "s", "b", "sent", "", now),
            )
        assert _count_today_sends() == 3

    def test_check_rate_limit_under(self, temp_db):
        dm.init_db()
        assert _check_rate_limit("new@test.com") is True

    def test_check_rate_limit_exceeded(self, temp_db):
        dm.init_db()
        import time as _time

        now = _time.strftime("%Y-%m-%dT%H:%M:%S")
        for i in range(RATE_LIMIT_MAX):
            dm.execute_write(
                "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (f"r{i}", "same@test.com", "s", "b", "sent", "", now),
            )
        assert _check_rate_limit("same@test.com") is False


# ---------------------------------------------------------------------------
# send_email
# ---------------------------------------------------------------------------


class TestSendEmail:
    def test_send_invalid_email(self, temp_db):
        dm.init_db()
        result = send_email("not-an-email", "subject", "body")
        assert result["success"] is False
        assert "无效" in result["error"]

    @patch("opc_manager.email_skill._count_today_sends", return_value=MAX_DAILY_SENDS)
    def test_send_daily_limit_reached(self, _mock, temp_db):
        dm.init_db()
        result = send_email("user@test.com", "subject", "body")
        assert result["success"] is False
        assert "上限" in result["error"]

    @patch("opc_manager.email_skill._check_rate_limit", return_value=False)
    def test_send_rate_limited(self, _mock, temp_db):
        dm.init_db()
        result = send_email("user@test.com", "subject", "body")
        assert result["success"] is False
        assert "频率" in result["error"]

    def test_send_body_too_large(self, temp_db):
        dm.init_db()
        big_body = "x" * (MAX_BODY_SIZE + 1)
        result = send_email("user@test.com", "subject", big_body)
        assert result["success"] is False
        assert "大小限制" in result["error"]

    @patch("opc_manager.email_skill._get_smtp_config", return_value=None)
    def test_send_no_smtp_config(self, _mock, temp_db):
        dm.init_db()
        result = send_email("user@test.com", "subject", "body")
        assert result["success"] is False
        assert "未配置" in result["error"]

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_success_ssl(self, mock_config, mock_smtp_ssl, temp_db, smtp_config):
        dm.init_db()
        mock_config.return_value = smtp_config
        server = _make_mock_smtp()
        mock_smtp_ssl.return_value = server

        result = send_email("user@test.com", "主题", "正文内容")
        assert result["success"] is True
        assert "id" in result
        server.login.assert_called_once_with("sender@test.com", "secret-pass")
        server.sendmail.assert_called_once()
        server.quit.assert_called_once()

        # 验证数据库写入
        rows = dm.execute_query("SELECT * FROM email_history WHERE status='sent'")
        assert len(rows) == 1
        assert rows[0]["to_addr"] == "user@test.com"

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_success_with_cc(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        server = _make_mock_smtp()
        mock_smtp_ssl.return_value = server

        result = send_email(
            "user@test.com", "主题", "正文", cc="cc1@test.com,cc2@test.com"
        )
        assert result["success"] is True
        # 验证收件人列表包含 cc
        _args, kwargs = server.sendmail.call_args
        recipients = _args[1] if len(_args) > 1 else kwargs.get("to_addrs")
        assert "cc1@test.com" in recipients
        assert "cc2@test.com" in recipients

    @patch("opc_manager.email_skill.smtplib.SMTP")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_success_non_ssl_starttls(
        self, mock_config, mock_smtp, temp_db, smtp_config
    ):
        dm.init_db()
        config = dict(smtp_config)
        config["ssl"] = False
        mock_config.return_value = config
        server = _make_mock_smtp()
        server.starttls.return_value = None
        mock_smtp.return_value = server

        result = send_email("user@test.com", "主题", "正文")
        assert result["success"] is True
        server.starttls.assert_called_once()

    @patch("opc_manager.email_skill.smtplib.SMTP")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_starttls_not_supported(
        self, mock_config, mock_smtp, temp_db, smtp_config
    ):
        dm.init_db()
        config = dict(smtp_config)
        config["ssl"] = False
        mock_config.return_value = config
        server = _make_mock_smtp()
        server.starttls.side_effect = smtplib.SMTPNotSupportedError("no starttls")
        mock_smtp.return_value = server

        with patch("opc_manager.email_skill.time.sleep"):
            result = send_email("user@test.com", "主题", "正文")
        assert result["success"] is False
        assert "发送失败" in result["error"]

    @patch("opc_manager.email_skill.time.sleep")
    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_smtp_failure_retries(
        self, mock_config, mock_smtp_ssl, _mock_sleep, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.side_effect = smtplib.SMTPException("connection refused")

        result = send_email("user@test.com", "主题", "正文")
        assert result["success"] is False
        assert "发送失败" in result["error"]
        # 验证重试 MAX_RETRIES 次
        assert mock_smtp_ssl.call_count == MAX_RETRIES
        # 验证失败记录写入数据库
        rows = dm.execute_query("SELECT * FROM email_history WHERE status='failed'")
        assert len(rows) == 1

    @patch("opc_manager.email_skill.time.sleep")
    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_success_after_retry(
        self, mock_config, mock_smtp_ssl, _mock_sleep, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        server = _make_mock_smtp()
        # 第一次失败，第二次成功
        mock_smtp_ssl.side_effect = [smtplib.SMTPException("timeout"), server]

        result = send_email("user@test.com", "主题", "正文")
        assert result["success"] is True
        assert mock_smtp_ssl.call_count == 2

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_with_template(self, mock_config, mock_smtp_ssl, temp_db, smtp_config):
        dm.init_db()
        mock_config.return_value = smtp_config
        server = _make_mock_smtp()
        mock_smtp_ssl.return_value = server

        # 先创建模板
        create_template("test_tpl", "模板主题", "模板正文")

        result = send_email("user@test.com", "", "", template_name="test_tpl")
        assert result["success"] is True
        # 验证使用了模板内容
        rows = dm.execute_query("SELECT * FROM email_history WHERE status='sent'")
        assert rows[0]["subject"] == "模板主题"
        assert rows[0]["body"] == "模板正文"

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_no_username_skips_login(self, mock_config, mock_smtp_ssl, temp_db):
        dm.init_db()
        config = {
            "host": "smtp.test.com",
            "port": 465,
            "username": "",
            "password": "",
            "ssl": True,
            "from_addr": "noreply@test.com",
        }
        mock_config.return_value = config
        server = _make_mock_smtp()
        mock_smtp_ssl.return_value = server

        result = send_email("user@test.com", "主题", "正文")
        assert result["success"] is True
        server.login.assert_not_called()


# ---------------------------------------------------------------------------
# send_email_async
# ---------------------------------------------------------------------------


class TestSendEmailAsync:
    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_send_email_async_success(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        server = _make_mock_smtp()
        mock_smtp_ssl.return_value = server

        result = asyncio.run(send_email_async("async@test.com", "异步主题", "异步正文"))
        assert result["success"] is True


# ---------------------------------------------------------------------------
# 模板管理
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_list_templates_seeded(self, temp_db):
        dm.init_db()
        templates = list_templates()
        # init_db 会种子 3 个模板
        assert len(templates) >= 3

    def test_get_template_existing(self, temp_db):
        dm.init_db()
        create_template("my_tpl", "主题", "正文", "var1,var2")
        tpl = get_template("my_tpl")
        assert tpl is not None
        assert tpl["subject"] == "主题"

    def test_get_template_not_found(self, temp_db):
        dm.init_db()
        assert get_template("nonexistent") is None

    def test_create_template(self, temp_db):
        dm.init_db()
        result = create_template("new_tpl", "新主题", "新正文", "")
        assert result["success"] is True
        tpl = get_template("new_tpl")
        assert tpl["body"] == "新正文"

    def test_create_template_replace_existing(self, temp_db):
        dm.init_db()
        create_template("dup", "原主题", "原正文")
        result = create_template("dup", "新主题", "新正文")
        assert result["success"] is True
        tpl = get_template("dup")
        assert tpl["subject"] == "新主题"

    def test_render_template_success(self, temp_db):
        dm.init_db()
        create_template("render_tpl", "你好{name}", "内容: {topic}")
        result = render_template("render_tpl", {"name": "张三", "topic": "项目讨论"})
        assert result["success"] is True
        assert "张三" in result["subject"]
        assert "项目讨论" in result["body"]

    def test_render_template_not_found(self, temp_db):
        dm.init_db()
        result = render_template("no_such", {"a": "b"})
        assert result["success"] is False
        assert "不存在" in result["error"]

    def test_render_template_leftover_variables(self, temp_db):
        dm.init_db()
        create_template("leftover", "你好{name}", "内容: {topic}")
        # 只提供 name，不提供 topic → 有未替换变量
        result = render_template("leftover", {"name": "张三"})
        assert result["success"] is False
        assert "未替换" in result["error"]


# ---------------------------------------------------------------------------
# list_email_history
# ---------------------------------------------------------------------------


class TestEmailHistory:
    def test_list_history_empty(self, temp_db):
        dm.init_db()
        assert list_email_history() == []

    def test_list_history_with_records(self, temp_db):
        dm.init_db()
        import time as _time

        now = _time.strftime("%Y-%m-%dT%H:%M:%S")
        for i in range(5):
            dm.execute_write(
                "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (f"h{i}", f"to{i}@test.com", f"subject{i}", "b", "sent", "", now),
            )
        history = list_email_history(limit=3)
        assert len(history) == 3
        # 验证字段
        assert "body" not in history[0]  # body 不在查询字段中
        assert "to_addr" in history[0]


# ---------------------------------------------------------------------------
# _lookup_email_by_name
# ---------------------------------------------------------------------------


class TestLookupEmailByName:
    def test_empty_name(self, temp_db):
        assert _lookup_email_by_name("") == ""

    def test_name_too_long(self, temp_db):
        assert _lookup_email_by_name("x" * 51) == ""

    @patch("opc_manager.crm_skill.get_customer")
    def test_lookup_success(self, mock_get, temp_db):
        mock_get.return_value = {
            "success": True,
            "customer": {"email": "found@test.com"},
        }
        assert _lookup_email_by_name("张三") == "found@test.com"

    @patch("opc_manager.crm_skill.get_customer")
    def test_lookup_no_email(self, mock_get, temp_db):
        mock_get.return_value = {"success": True, "customer": {"email": ""}}
        assert _lookup_email_by_name("张三") == ""

    @patch("opc_manager.crm_skill.get_customer")
    def test_lookup_decrypt_failed(self, mock_get, temp_db):
        mock_get.return_value = {
            "success": True,
            "customer": {"email": "[DECRYPT_FAILED]"},
        }
        assert _lookup_email_by_name("张三") == ""

    @patch("opc_manager.crm_skill.get_customer")
    def test_lookup_customer_not_found(self, mock_get, temp_db):
        mock_get.return_value = {"success": False}
        assert _lookup_email_by_name("张三") == ""

    @patch("opc_manager.crm_skill.get_customer", side_effect=Exception("db error"))
    def test_lookup_exception(self, _mock, temp_db):
        assert _lookup_email_by_name("张三") == ""


# ---------------------------------------------------------------------------
# execute_goal
# ---------------------------------------------------------------------------


class TestExecuteGoal:
    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_goal_with_email_prefix(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal("邮箱：user@test.com 主题", subject="测试", body="内容")
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_goal_with_recipient_prefix_valid_email(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal(
            "收件人：valid@test.com 请发送", subject="测试", body="内容"
        )
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    @patch(
        "opc_manager.email_skill._lookup_email_by_name", return_value="looked@test.com"
    )
    def test_goal_with_recipient_prefix_name_lookup(
        self, mock_lookup, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal("收件人：张三 请发送", subject="测试", body="内容")
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_goal_with_gei_pattern_valid_email(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal("给 valid@test.com 发邮件", subject="测试", body="内容")
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    @patch(
        "opc_manager.email_skill._lookup_email_by_name", return_value="found@test.com"
    )
    def test_goal_with_gei_pattern_name_lookup(
        self, mock_lookup, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal("给李四发邮件", subject="", body="")
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_goal_all_params_provided(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal(
            "发邮件", to="direct@test.com", subject="直接主题", body="直接内容"
        )
        assert result["success"] is True

    def test_goal_template_query(self, temp_db):
        dm.init_db()
        result = execute_goal("查看邮件模板", to="", subject="", body="")
        assert result["success"] is True
        assert "templates" in result

    def test_goal_template_query_english(self, temp_db):
        dm.init_db()
        result = execute_goal("list template", to="", subject="", body="")
        assert result["success"] is True

    @patch("opc_manager.email_skill.smtplib.SMTP_SSL")
    @patch("opc_manager.email_skill._get_smtp_config")
    def test_goal_to_only_derives_subject_body(
        self, mock_config, mock_smtp_ssl, temp_db, smtp_config
    ):
        dm.init_db()
        mock_config.return_value = smtp_config
        mock_smtp_ssl.return_value = _make_mock_smtp()

        result = execute_goal(
            "给 valid@test.com 发邮件讨论项目进度", to="", subject="", body=""
        )
        assert result["success"] is True

    def test_goal_no_recipient_error(self, temp_db):
        dm.init_db()
        result = execute_goal("随便说点什么", to="", subject="", body="")
        assert result["success"] is False
        assert "收件人" in result["error"]


# ---------------------------------------------------------------------------
# undo_send_email
# ---------------------------------------------------------------------------


class TestUndoSendEmail:
    def test_undo_with_record_id(self, temp_db):
        dm.init_db()
        import time as _time

        now = _time.strftime("%Y-%m-%dT%H:%M:%S")
        dm.execute_write(
            "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
            ("undo1", "to@test.com", "s", "b", "sent", "", now),
        )
        result = undo_send_email(record_id="undo1")
        assert result["success"] is True
        rows = dm.execute_query("SELECT status FROM email_history WHERE id='undo1'")
        assert rows[0]["status"] == "draft"

    def test_undo_without_id_latest(self, temp_db):
        dm.init_db()
        import time as _time

        now = _time.strftime("%Y-%m-%dT%H:%M:%S")
        dm.execute_write(
            "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
            ("latest1", "to@test.com", "s", "b", "sent", "", now),
        )
        result = undo_send_email()
        assert result["success"] is True
        rows = dm.execute_query("SELECT status FROM email_history WHERE id='latest1'")
        assert rows[0]["status"] == "draft"

    def test_undo_without_id_no_records(self, temp_db):
        dm.init_db()
        result = undo_send_email()
        assert result["success"] is True  # 即使没记录也返回成功
