"""P0 技能真实执行 E2E 测试.

GAP-P0-2: email/finance/report 三个 P0 技能被 @patch.object(TaskEngineV3, "execute")
整体 mock，从未验证真实执行链路.

本文件不 mock TaskEngineV3，直接调用真实技能模块函数，验证:
- email 技能: 真实 Mock SMTP 服务器收到邮件 + DB 记录 + 审计日志 + 频率限制
- finance 技能: 真实 DB 写入 + 月报反映新增收入
- report 技能: 真实文件生成到 data/reports/ 目录 + 文件内容验证

Iron Rule 遵守:
- Rule 1 (Documentation First): 基于 AST/read 源码确认实际 API，不猜测参数名
- Rule 4 (Side-Effect): 验证 DB 写入 / 文件生成 / 审计日志，不只检查返回值
- Rule 5 (User Journey): 测试模拟用户真实操作流程
- Rule 6 (E2E Release Gate): 真实组件（真实 DB / 真实文件系统 / 真实 SMTP 协议）
"""

from __future__ import annotations

import json
import os
import time
from email import message_from_bytes
from email.header import decode_header, make_header
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.e2e


def _decode_mime_header(value: str) -> str:
    """解码 RFC 2047 MIME 编码的邮件 header（如中文 Subject）.

    例: '=?utf-8?b?RTJFIOa1i+ivlemCruS7tg==?=' → 'E2E 测试邮件'
    """
    if not value:
        return value
    return str(make_header(decode_header(value)))


# ============================================================
# 共享 fixture: 数据隔离
# ============================================================


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """隔离 DB + 审计日志 + SMTP 配置.

    重定向 OPC_DATA_DIR 到临时目录，避免污染真实 data/opc_data.db.
    配置测试加密密钥，避免自动派生机器密钥.
    重定向 AuditLogger 到临时日志文件.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OPC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("OPC_ENCRYPTION_KEY", "test-e2e-key-for-isolated-db-only")

    # 重置 data_manager 模块级状态（_db_initialized 等）
    import opc_manager.data_manager as dm

    monkeypatch.setattr(dm, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(dm, "DB_PATH", str(data_dir / "opc_data.db"))
    monkeypatch.setattr(dm, "_db_initialized", False)
    # 清理线程局部连接
    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None

    # Patch 所有在模块加载时从 data_manager 导入 DATA_DIR 的模块，
    # 确保 isolated_db fixture 的 DATA_DIR 重定向对所有模块生效.
    # （生产环境中 OPC_DATA_DIR 在启动前设置，模块加载时即正确，无需 patch；
    #   测试环境中 monkeypatch 在模块加载后执行，需显式 patch 各模块引用.）
    import opc_manager.email_skill as email_skill_mod
    import opc_manager.report_skill as report_skill_mod

    monkeypatch.setattr(email_skill_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(report_skill_mod, "REPORT_DIR", str(data_dir / "reports"))

    # 重定向 AuditLogger 到临时日志文件
    audit_log_file = str(logs_dir / "audit.jsonl")
    from opc_manager.tool_audit_logger import AuditLogger

    AuditLogger.configure(audit_log_file)
    # 清理可能残留的异步队列
    AuditLogger._write_queue = None
    AuditLogger._writer_task = None
    AuditLogger._shutdown_event = None

    # init_db 创建所有表（必须在 DATA_DIR 重定向后调用）
    dm.init_db()

    yield {
        "data_dir": str(data_dir),
        "logs_dir": str(logs_dir),
        "audit_log_file": audit_log_file,
        "dm": dm,
    }

    # 清理: 关闭线程局部连接
    if hasattr(dm._local, "conn") and dm._local.conn is not None:
        try:
            dm._local.conn.close()
        except Exception:
            pass
        dm._local.conn = None


@pytest.fixture
def mock_smtp_server():
    """启动 aiosmtpd Mock SMTP 服务器，返回 (host, port, received_mails).

    使用 aiosmtpd.controller.Controller 在后台线程运行.
    不配置 TLS（测试环境不需要真实加密），通过 patch smtplib.SMTP.starttls
    跳过 TLS 握手（TLS 是传输层细节，不影响用户可见的"邮件发送"行为）.
    """
    import aiosmtpd.controller

    received: list = []

    class _Handler:
        async def handle_DATA(self, server, session, envelope):
            received.append(message_from_bytes(envelope.content))
            return "250 Message accepted for delivery"

    # 动态分配端口避免冲突
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    controller = aiosmtpd.controller.Controller(
        _Handler(), hostname="127.0.0.1", port=port
    )
    controller.start()

    # Patch starttls 为 no-op（aiosmtpd 默认不支持 STARTTLS）
    # 这是测试基础设施层面的 patch，不影响被测业务逻辑
    with patch.object(__import__("smtplib").SMTP, "starttls", return_value=None):
        try:
            yield ("127.0.0.1", port, received)
        finally:
            controller.stop()


def _save_smtp_config_for_test(host: str, port: int, data_dir: str) -> None:
    """保存 SMTP 配置到 data/email_config.json（email_skill._get_smtp_config 读取）.

    Args:
        host: SMTP 服务器地址
        port: SMTP 服务器端口
        data_dir: data 目录路径
    """
    config_path = os.path.join(data_dir, "email_config.json")
    config = {
        "host": host,
        "port": port,
        "username": "",
        "password": "",
        "from_addr": "test@opc-agents.local",
        "ssl": False,  # Mock SMTP 不使用 SSL
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============================================================
# Email 技能 E2E
# ============================================================


class TestEmailSkillE2E:
    """email 技能真实执行 E2E — 验证邮件发送全链路."""

    def test_email_send_via_mock_smtp(self, isolated_db, mock_smtp_server):
        """Verify: send_email() 通过 Mock SMTP 真实发送邮件.

        用户旅程: 用户输入"帮我发邮件给客户" → email_skill.send_email() 执行
        Expected: Mock SMTP 收到邮件 + email_history 表记录 + 审计日志记录

        Side-Effect 验证 (Iron Rule 4):
        1. Mock SMTP 收件箱有 1 封邮件（Subject/To 匹配）
        2. email_history 表有 status='sent' 的记录
        3. AuditLogger.query("email_sent") 返回非空
        """
        from opc_manager.email_skill import send_email

        host, port, received = mock_smtp_server
        _save_smtp_config_for_test(host, port, isolated_db["data_dir"])

        result = send_email(
            to="client@example.com",
            subject="E2E 测试邮件",
            body="这是 E2E 测试的邮件内容。",
        )

        assert result["success"], f"email 发送失败: {result.get('error', 'unknown')}"

        # Side-Effect 1: Mock SMTP 收到邮件
        assert len(received) == 1, f"应收到 1 封邮件，实际 {len(received)}"
        # Subject 含中文时会被 RFC 2047 MIME 编码，需解码后比较
        assert _decode_mime_header(received[0]["Subject"]) == "E2E 测试邮件"
        assert received[0]["To"] == "client@example.com"

        # Side-Effect 2: email_history 表写入
        from opc_manager.data_manager import execute_query

        rows = execute_query(
            "SELECT to_addr, subject, status FROM email_history WHERE to_addr=?",
            ("client@example.com",),
        )
        assert rows, "email_history 表未记录发送"
        assert rows[0]["status"] == "sent", f"状态应为 sent，实际 {rows[0]['status']}"
        assert rows[0]["subject"] == "E2E 测试邮件"

        # Side-Effect 3: 审计日志记录
        from opc_manager.tool_audit_logger import AuditLogger

        # Sprint 4.3 fix: AuditLogger 异步写入，查询前需 flush 确保记录已持久化
        AuditLogger.flush()
        audit_records = AuditLogger.query(event_type="email_sent")
        assert audit_records, "审计日志未记录 email_sent 事件"
        assert audit_records[-1]["details"]["to"] == "client@example.com"

    def test_email_rate_limit_enforced(self, isolated_db, mock_smtp_server):
        """Verify: email 技能频率限制生效（同一收件人 1 小时内最多 3 封）.

        用户旅程: 用户连续发送 4 封邮件给同一收件人 → 第 4 封被频率限制拒绝
        Expected: 前 3 封成功，第 4 封返回 success=False 且 error 含"频率"

        RATE_LIMIT_MAX=3, RATE_LIMIT_WINDOW=3600 (email_skill.py:34)
        """
        from opc_manager.email_skill import send_email

        host, port, _received = mock_smtp_server
        _save_smtp_config_for_test(host, port, isolated_db["data_dir"])

        # 发送 3 封（应全部成功）
        for i in range(3):
            result = send_email(
                to="rate-test@example.com",
                subject=f"频率测试邮件 {i}",
                body=f"第 {i} 封",
            )
            assert result[
                "success"
            ], f"第 {i+1} 封应成功，实际失败: {result.get('error')}"

        # 第 4 封应被频率限制拒绝
        result = send_email(
            to="rate-test@example.com",
            subject="第 4 封",
            body="应被拒绝",
        )
        assert not result["success"], "第 4 封邮件应被频率限制拒绝"
        assert (
            "频率" in result.get("error", "")
            or "rate" in result.get("error", "").lower()
        ), f"error 应含'频率'关键字，实际: {result.get('error')}"

    def test_email_invalid_address_rejected(self, isolated_db, mock_smtp_server):
        """Verify: 无效收件人地址被拒绝.

        用户旅程: 用户输入无效邮箱地址 → 系统拒绝发送
        Expected: 返回 success=False, error 含"无效"
        """
        from opc_manager.email_skill import send_email

        host, port, _received = mock_smtp_server
        _save_smtp_config_for_test(host, port, isolated_db["data_dir"])

        result = send_email(
            to="not-an-email-address",
            subject="测试",
            body="内容",
        )
        assert not result["success"], "无效地址应被拒绝"
        assert "无效" in result.get(
            "error", ""
        ), f"error 应含'无效'，实际: {result.get('error')}"

    def test_email_no_smtp_config_returns_error(self, isolated_db):
        """Verify: 未配置 SMTP 时返回明确错误.

        用户旅程: 用户未配置邮件 → 尝试发送 → 收到"邮件未配置"提示
        Expected: 返回 success=False, error 含"未配置"
        """
        from opc_manager.email_skill import send_email

        # 不保存 SMTP 配置（data/email_config.json 不存在）
        result = send_email(
            to="test@example.com",
            subject="测试",
            body="内容",
        )
        assert not result["success"]
        assert "未配置" in result.get(
            "error", ""
        ), f"error 应含'未配置'，实际: {result.get('error')}"


# ============================================================
# Finance 技能 E2E
# ============================================================


class TestFinanceSkillE2E:
    """finance 技能真实执行 E2E — 验证记账 + 月报联动."""

    def test_record_income_writes_to_db(self, isolated_db):
        """Verify: record_income() 真实写入 finance_records 表.

        用户旅程: 用户输入"记录收入 5000 元，来源是咨询服务"
        Expected: finance_records 表有 type='income' 的记录

        Side-Effect 验证 (Iron Rule 4):
        1. DB finance_records 表有对应记录（amount/category/source 匹配）
        2. AuditLogger.query("finance_income") 返回非空
        """
        from opc_manager.finance_skill import record_income
        from opc_manager.data_manager import execute_query

        result = record_income(
            amount=5000.00,
            source="咨询服务",
            category="服务收入",
        )

        assert result["success"], f"记账失败: {result.get('error')}"
        assert "id" in result, "返回值应含 id"

        # Side-Effect 1: DB 写入
        rows = execute_query(
            "SELECT amount, category, source, type FROM finance_records " "WHERE id=?",
            (result["id"],),
        )
        assert rows, f"finance_records 表未找到 id={result['id']} 的记录"
        assert rows[0]["amount"] == 5000.00
        assert rows[0]["category"] == "服务收入"
        assert rows[0]["source"] == "咨询服务"
        assert rows[0]["type"] == "income"

        # Side-Effect 2: 审计日志
        from opc_manager.tool_audit_logger import AuditLogger

        # Sprint 4.3 fix: AuditLogger 异步写入，查询前需 flush 确保记录已持久化
        AuditLogger.flush()
        audit_records = AuditLogger.query(event_type="finance_income")
        assert audit_records, "审计日志未记录 finance_income 事件"
        assert audit_records[-1]["details"]["amount"] == 5000.00

    def test_record_expense_writes_to_db(self, isolated_db):
        """Verify: record_expense() 真实写入 finance_records 表.

        用户旅程: 用户输入"记录支出 200 元，办公用品"
        Expected: finance_records 表有 type='expense' 的记录
        """
        from opc_manager.finance_skill import record_expense
        from opc_manager.data_manager import execute_query

        result = record_expense(
            amount=200.00,
            source="超市采购",
            category="办公用品",
        )

        assert result["success"]
        rows = execute_query(
            "SELECT type, amount, category FROM finance_records WHERE id=?",
            (result["id"],),
        )
        assert rows[0]["type"] == "expense"
        assert rows[0]["amount"] == 200.00
        assert rows[0]["category"] == "办公用品"

    def test_record_income_rejects_invalid_amount(self, isolated_db):
        """Verify: 金额 <= 0 被拒绝.

        用户旅程: 用户输入"记录收入 -100 元" → 系统拒绝
        Expected: 返回 success=False, error 含"大于0"
        """
        from opc_manager.finance_skill import record_income

        result = record_income(amount=0, source="测试", category="测试")
        assert not result["success"]
        assert "大于0" in result.get("error", "")

        result = record_income(amount=-100, source="测试", category="测试")
        assert not result["success"]
        assert "大于0" in result.get("error", "")

    def test_monthly_report_reflects_new_income(self, isolated_db):
        """Verify: 记账后 get_monthly_report() 反映新增收入.

        用户旅程: 用户记账 → 查看月报 → 月报收入增加
        Expected: 月报 income 字段 >= 记账金额
        """
        from opc_manager.finance_skill import record_income, get_monthly_report

        # 记录本月收入
        record_income(
            amount=3000.00,
            source="E2E 测试",
            category="测试收入",
        )

        # 查询本月月报
        current_month = time.strftime("%Y-%m")
        report = get_monthly_report(year_month=current_month)

        assert report["success"], f"月报查询失败: {report.get('error')}"
        assert report["income"] >= 3000.00, f"月报收入 {report['income']} 应 >= 3000.00"

    def test_monthly_report_empty_month_returns_zero(self, isolated_db):
        """Verify: 无记录的月份月报返回 0.

        用户旅程: 用户查看无记录月份的月报 → 看到 0 收入
        Expected: income=0, expense=0, profit=0
        """
        from opc_manager.finance_skill import get_monthly_report

        report = get_monthly_report(year_month="2099-12")
        assert report["success"]
        assert report["income"] == 0
        assert report["expense"] == 0
        assert report["profit"] == 0


# ============================================================
# Report 技能 E2E
# ============================================================


class TestReportSkillE2E:
    """report 技能真实执行 E2E — 验证报告文件生成."""

    def test_monthly_report_creates_file(self, isolated_db):
        """Verify: generate_monthly_report() 生成报告文件到 data/reports/.

        用户旅程: 用户输入"生成本月月报" → report_skill 执行
        Expected: 返回 filepath 字段，文件真实存在且非空

        Side-Effect 验证 (Iron Rule 4):
        1. 返回值含 filepath 字段
        2. 文件真实存在于 data/reports/ 目录
        3. 文件大小 > 0
        4. 文件内容含 "# 月度经营报告" 标题
        """
        from opc_manager.report_skill import generate_monthly_report

        current_month = time.strftime("%Y-%m")
        result = generate_monthly_report(year_month=current_month)

        assert result["success"], f"月报生成失败: {result.get('error')}"
        assert "filepath" in result, "返回值应含 filepath 字段"

        # Side-Effect 1: 文件真实存在
        file_path = Path(result["filepath"])
        assert file_path.exists(), f"报告文件未创建: {file_path}"
        assert file_path.stat().st_size > 0, "报告文件为空"

        # Side-Effect 2: 文件内容正确
        content = file_path.read_text(encoding="utf-8")
        assert "# 月度经营报告" in content, "文件内容应含 '# 月度经营报告' 标题"
        assert current_month in content, f"文件内容应含月份 {current_month}"

    def test_weekly_report_creates_file(self, isolated_db):
        """Verify: generate_weekly_report() 生成周报文件.

        用户旅程: 用户输入"生成本周周报" → report_skill 执行
        Expected: 文件生成到 data/reports/ 目录
        """
        from opc_manager.report_skill import generate_weekly_report

        result = generate_weekly_report(week_note="E2E 测试周报备注")

        assert result["success"], f"周报生成失败: {result.get('error')}"
        file_path = Path(result["filepath"])
        assert file_path.exists(), f"周报文件未创建: {file_path}"

        content = file_path.read_text(encoding="utf-8")
        assert "# 周报" in content, "文件内容应含 '# 周报' 标题"
        assert "E2E 测试周报备注" in content, "文件内容应含用户备注"

    def test_report_file_in_data_dir(self, isolated_db):
        """Verify: 报告文件生成在 data/reports/ 目录下（DATA_DIR 隔离生效）.

        安全验证: 文件不应生成到项目根目录的 data/，应在隔离的 DATA_DIR 下.
        """
        from opc_manager.report_skill import generate_monthly_report
        from opc_manager.data_manager import DATA_DIR

        result = generate_monthly_report()
        file_path = Path(result["filepath"])

        # 验证文件在 DATA_DIR/reports/ 下
        expected_dir = Path(DATA_DIR) / "reports"
        assert (
            file_path.parent == expected_dir
        ), f"文件应在 {expected_dir} 下，实际在 {file_path.parent}"

    def test_execute_goal_dispatches_by_keyword(self, isolated_db):
        """Verify: execute_goal() 根据关键词分发到正确的报告生成函数.

        用户旅程: 用户输入"生成年报" → execute_goal 识别"年报"关键词 → 生成年度报告
        Expected: 返回 success=True 且 filepath 含 'annual'
        """
        from opc_manager.report_skill import execute_goal

        # 测试月报关键词
        result_monthly = execute_goal("帮我生成本月月报")
        assert result_monthly["success"]
        assert (
            "monthly" in result_monthly["filepath"]
            or "月" in result_monthly["filepath"]
        )

        # 测试年报关键词
        result_annual = execute_goal("生成年度报告")
        assert result_annual["success"]
        assert (
            "annual" in result_annual["filepath"] or "年" in result_annual["filepath"]
        )

        # 测试默认（无关键词匹配 → 周报）
        result_default = execute_goal("随便生成个报告")
        assert result_default["success"]
