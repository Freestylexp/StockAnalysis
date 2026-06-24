"""Send daily report emails via SMTP."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable


def _require(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(
            f"未设置 {name}。"
            f"请在 GitHub → Settings → Secrets → Actions 中添加 {name}"
        )
    return value


def get_smtp_config() -> dict[str, str | int]:
    user = _require(
        "SMTP_USER",
        os.getenv("SMTP_USER", "").strip() or os.getenv("EMAIL_FROM", "").strip(),
    )
    password = _require(
        "SMTP_PASSWORD",
        os.getenv("SMTP_PASSWORD", "").strip() or os.getenv("EMAIL_PASSWORD", "").strip(),
    )
    to_addr = os.getenv("EMAIL_TO", "").strip() or user
    host = os.getenv("SMTP_HOST", "smtp.qq.com").strip()
    port = int(os.getenv("SMTP_PORT", "465"))
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "to": to_addr,
        "from": os.getenv("EMAIL_FROM", user).strip() or user,
    }


def send_report_email(
    subject: str,
    html_body: str,
    markdown_body: str | None = None,
    recipients: Iterable[str] | None = None,
) -> None:
    cfg = get_smtp_config()
    to_list = list(recipients) if recipients else [str(cfg["to"])]
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject[:200]
    msg["From"] = str(cfg["from"])
    msg["To"] = ", ".join(to_list)

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("请使用支持 HTML 的邮件客户端查看本报告。", "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    if markdown_body:
        attachment = MIMEText(markdown_body, "plain", "utf-8")
        filename = subject.replace(" ", "_")[:50] + ".md"
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(attachment)

    host = str(cfg["host"])
    port = int(cfg["port"])
    user = str(cfg["user"])
    password = str(cfg["password"])

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(user, password)
            server.sendmail(str(cfg["from"]), to_list, msg.as_string())
        return

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(user, password)
        server.sendmail(str(cfg["from"]), to_list, msg.as_string())
