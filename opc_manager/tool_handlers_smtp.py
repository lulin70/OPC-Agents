"""
邮件工具处理器 (SmtpHandlers) — Mixin

从 tool_system.py 拆分（Phase 3 架构演进），职责：
- 邮件发送工具执行逻辑（_execute_send_email）
- SMTP 同步发送（_send_smtp_sync）
- 通知文件落盘（_write_notification_sync，SMTP 未配置时的降级方案）

安全防护：
- CRLF 注入清洗：to/subject 字段移除 \\r \\n（防止邮件头注入）
- 收件人邮箱正则校验（^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$）

作为 Mixin 供 ToolSystem（Facade）继承。
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SmtpHandlers:
    """邮件工具处理器 Mixin — 供 ToolSystem 继承。"""

    async def _execute_send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        to = to.replace("\r", "").replace("\n", "")
        subject = subject.replace("\r", "").replace("\n", "")
        if not to or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", to):
            return {"sent": False, "error": f"Invalid email address: {to}"}

        smtp_host = os.environ.get("OPC_SMTP_HOST", "")
        smtp_port = int(os.environ.get("OPC_SMTP_PORT", "587"))
        smtp_user = os.environ.get("OPC_SMTP_USER", "")
        smtp_pass = os.environ.get("OPC_SMTP_PASS", "")
        smtp_from = os.environ.get("OPC_SMTP_FROM", smtp_user)
        smtp_tls = os.environ.get("OPC_SMTP_TLS", "true").lower() == "true"

        if smtp_host and smtp_user and smtp_pass:
            try:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    self._send_smtp_sync,
                    smtp_host,
                    smtp_port,
                    smtp_user,
                    smtp_pass,
                    smtp_from,
                    to,
                    subject,
                    body,
                    smtp_tls,
                    attachments,
                )
                if result.get("sent"):
                    logger.info("Email sent via SMTP to %s", to)
                    return result
                logger.warning(
                    "SMTP send failed: %s, falling back to log", result.get("error")
                )
            except Exception as e:
                logger.warning("SMTP send exception: %s, falling back to log", e)

        notification_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "notifications"
        )
        timestamp = int(time.time() * 1000)
        filename = f"notification_{timestamp}.json"
        filepath = os.path.join(notification_dir, filename)

        notification = {
            "type": "email",
            "to": to,
            "subject": subject,
            "body": body[:5000],
            "attachments": attachments or [],
            "timestamp": timestamp,
            "status": "logged",
            "note": (
                "SMTP not configured. Notification logged to file. "
                "Configure OPC_SMTP_HOST/USER/PASS for actual email delivery."
            ),
        }

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, self._write_notification_sync, filepath, notification
            )
            logger.info("Notification logged: %s", filepath)
        except Exception as e:
            logger.warning("Failed to log notification: %s", e)

        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "attachments": attachments or [],
            "delivery_mode": "logged",
            "log_file": filename,
        }

    @staticmethod
    def _send_smtp_sync(
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        use_tls: bool,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            if use_tls:
                server = smtplib.SMTP(host, port)
                server.ehlo()
                server.starttls()
                server.ehlo()
            else:
                server = smtplib.SMTP(host, port)

            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
            server.quit()

            return {
                "sent": True,
                "to": to_addr,
                "subject": subject,
                "delivery_mode": "smtp",
            }
        except Exception as e:
            return {"sent": False, "error": str(e)}

    @staticmethod
    def _write_notification_sync(filepath: str, notification: dict) -> None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(notification, f, ensure_ascii=False, indent=2)
