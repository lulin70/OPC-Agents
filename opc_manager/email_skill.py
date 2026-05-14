import asyncio
import hashlib
import logging
import os
import re
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

from opc_manager.data_manager import (
    encrypt_field, decrypt_field, execute_query, execute_write, gen_id, init_db,
)
from opc_manager.tool_system import AuditLogger

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {".exe", ".bat", ".sh", ".cmd", ".ps1", ".vbs", ".com", ".scr"}
MAX_DAILY_SENDS = 100
SMTP_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]
MAX_SUBJECT_LEN = 200
MAX_BODY_LEN = 50000
MAX_BODY_SIZE = 50 * 1024
RATE_LIMIT_WINDOW = 3600
RATE_LIMIT_MAX = 3


def _get_smtp_config() -> Optional[Dict[str, Any]]:
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "email_config.json"
    )
    if not os.path.exists(config_path):
        return None
    try:
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if config.get("password_encrypted"):
            decrypted = decrypt_field(config.get("password", ""))
            config["password"] = decrypted if decrypted is not None else ""
        return config
    except Exception:
        return None


def save_smtp_config(config: Dict[str, Any]) -> Dict[str, Any]:
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "data", "email_config.json"
    )
    try:
        import json
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        save_config = dict(config)
        if save_config.get("password"):
            save_config["password"] = encrypt_field(save_config["password"])
            save_config["password_encrypted"] = True
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(save_config, f, ensure_ascii=False, indent=2)
        return {"success": True, "message": "邮件配置已保存（密码已加密）"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _sanitize_email_field(value: str) -> str:
    return value.replace("\r", "").replace("\n", "")


def _validate_email(addr: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", addr))


def _count_today_sends() -> int:
    today = time.strftime("%Y-%m-%d")
    rows = execute_query(
        "SELECT COUNT(*) as cnt FROM email_history WHERE date(created_at)=? AND status='sent'",
        (today,),
    )
    return rows[0]["cnt"] if rows else 0


def _check_rate_limit(to: str) -> bool:
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - RATE_LIMIT_WINDOW))
    rows = execute_query(
        "SELECT COUNT(*) as cnt FROM email_history WHERE to_addr=? AND status='sent' AND created_at>=?",
        (to, cutoff),
    )
    count = rows[0]["cnt"] if rows else 0
    return count < RATE_LIMIT_MAX


def send_email(to: str, subject: str, body: str,
               cc: str = "", template_name: str = "") -> Dict[str, Any]:
    to = _sanitize_email_field(to)
    subject = _sanitize_email_field(subject)
    cc = _sanitize_email_field(cc) if cc else ""

    if not _validate_email(to):
        return {"success": False, "error": f"收件人地址无效: {to}"}

    if _count_today_sends() >= MAX_DAILY_SENDS:
        return {"success": False, "error": f"今日发送已达上限({MAX_DAILY_SENDS}封)"}

    if not _check_rate_limit(to):
        return {"success": False, "error": f"发送频率过高：同一收件人1小时内最多{RATE_LIMIT_MAX}封"}

    if len(body.encode("utf-8")) > MAX_BODY_SIZE:
        return {"success": False, "error": f"邮件正文超过大小限制({MAX_BODY_SIZE // 1024}KB)"}

    config = _get_smtp_config()
    if not config:
        return {"success": False, "error": "邮件未配置，请先运行邮件配置向导"}

    msg = MIMEMultipart()
    msg["From"] = config.get("from_addr", config.get("username", ""))
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc

    msg.attach(MIMEText(body, "plain", "utf-8"))

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    record_id = gen_id()

    for attempt in range(MAX_RETRIES):
        try:
            smtp_host = config["host"]
            smtp_port = int(config.get("port", 465))
            username = config["username"]
            password = config.get("password", "")
            use_ssl = config.get("ssl", True)

            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=SMTP_TIMEOUT)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=SMTP_TIMEOUT)
                try:
                    server.starttls()
                except smtplib.SMTPNotSupportedError:
                    logger.error("[email_skill] Server does not support STARTTLS, aborting")
                    server.quit()
                    raise RuntimeError("SMTP server does not support STARTTLS, cannot send securely")

            if username:
                server.login(username, password)

            recipients = [to]
            if cc:
                recipients.extend(cc.split(","))

            server.sendmail(msg["From"], recipients, msg.as_string())
            server.quit()

            body_digest = hashlib.sha256(body.encode()).hexdigest()[:16]
            execute_write(
                "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (record_id, to, subject, body, "sent", template_name, now),
            )
            AuditLogger.log("email_sent", {"to": to, "subject": subject[:50], "body_digest": body_digest})
            return {"success": True, "message": f"邮件已发送至 {to}", "id": record_id}

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAYS[attempt])
                continue
            body_digest = hashlib.sha256(body.encode()).hexdigest()[:16]
            execute_write(
                "INSERT INTO email_history (id,to_addr,subject,body,status,template_name,created_at) VALUES (?,?,?,?,?,?,?)",
                (record_id, to, subject, body, "failed", template_name, now),
            )
            AuditLogger.log("email_failed", {"to": to, "error": "smtp_error"})
            return {"success": False, "error": f"邮件发送失败(重试3次): {e}"}

    return {"success": False, "error": "邮件发送失败"}


async def send_email_async(to: str, subject: str, body: str,
                           cc: str = "", template_name: str = "") -> Dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, send_email, to, subject, body, cc, template_name
    )


def list_templates() -> List[Dict[str, Any]]:
    return execute_query("SELECT name, subject, variables FROM email_templates ORDER BY name")


def get_template(name: str) -> Optional[Dict[str, Any]]:
    rows = execute_query("SELECT * FROM email_templates WHERE name=?", (name,))
    return rows[0] if rows else None


def render_template(name: str, variables: Dict[str, str]) -> Dict[str, Any]:
    tpl = get_template(name)
    if not tpl:
        return {"success": False, "error": f"模板不存在: {name}"}

    subject = tpl["subject"]
    body = tpl["body"]
    for key, value in variables.items():
        subject = subject.replace(f"{{{key}}}", value)
        body = body.replace(f"{{{key}}}", value)

    leftover = re.findall(r"\{[a-zA-Z_]+\}", subject + body)
    if leftover:
        return {"success": False, "error": f"模板变量未替换: {leftover}", "subject": subject, "body": body}

    return {"success": True, "subject": subject, "body": body}


def create_template(name: str, subject: str, body: str, variables: str = "") -> Dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        execute_write(
            "INSERT OR REPLACE INTO email_templates (name,subject,body,variables,created_at) VALUES (?,?,?,?,?)",
            (name, subject, body, variables, now),
        )
        return {"success": True, "message": f"模板 '{name}' 已保存"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_email_history(limit: int = 20) -> List[Dict[str, Any]]:
    return execute_query(
        "SELECT id, to_addr, subject, status, template_name, created_at FROM email_history ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )


def execute_goal(goal: str, _context=None, **kwargs) -> Dict[str, Any]:
    init_db()
    to = kwargs.get("to", "")
    subject = kwargs.get("subject", "")
    body = kwargs.get("body", "")

    if to and subject and body:
        return send_email(to, subject, body)

    if "模板" in goal or "template" in goal.lower():
        templates = list_templates()
        return {"success": True, "templates": templates, "message": f"共{len(templates)}个邮件模板"}

    if to:
        subject = subject or f"关于{goal}"
        body = body or goal
        return send_email(to, subject, body)

    return {"success": False, "error": "请提供收件人地址(to参数)，或说'帮我给xxx发邮件'"}
