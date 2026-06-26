"""Send daily report emails via SMTP."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable


def _env(name: str, default: str = "") -> str:
    """Read env var; treat blank GitHub Secret placeholders as unset."""
    return (os.getenv(name) or default).strip()


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
        _env("SMTP_USER") or _env("EMAIL_FROM"),
    )
    password = _require(
        "SMTP_PASSWORD",
        _env("SMTP_PASSWORD") or _env("EMAIL_PASSWORD"),
    )
    to_addr = _env("EMAIL_TO") or user
    host = _env("SMTP_HOST", "smtp.qq.com") or "smtp.qq.com"
    port_raw = _env("SMTP_PORT", "465") or "465"
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise RuntimeError(f"SMTP_PORT 无效：{port_raw!r}，请填 465 或 587") from exc
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "to": to_addr,
        "from": _env("EMAIL_FROM") or user,
    }


def _build_message(
    cfg: dict[str, str | int],
    subject: str,
    html_body: str,
    markdown_body: str | None,
    to_list: list[str],
) -> MIMEMultipart:
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
    return msg


def _send_via_ssl(host: str, port: int, user: str, password: str, from_addr: str, to_list: list[str], msg: MIMEMultipart) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=45) as server:
        server.login(user, password)
        server.sendmail(from_addr, to_list, msg.as_string())


def _send_via_starttls(host: str, port: int, user: str, password: str, from_addr: str, to_list: list[str], msg: MIMEMultipart) -> None:
    with smtplib.SMTP(host, port, timeout=45) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(user, password)
        server.sendmail(from_addr, to_list, msg.as_string())


def send_report_email(
    subject: str,
    html_body: str,
    markdown_body: str | None = None,
    recipients: Iterable[str] | None = None,
) -> None:
    cfg = get_smtp_config()
    to_list = list(recipients) if recipients else [str(cfg["to"])]
    msg = _build_message(cfg, subject, html_body, markdown_body, to_list)

    host = str(cfg["host"])
    user = str(cfg["user"])
    password = str(cfg["password"])
    from_addr = str(cfg["from"])
    preferred_port = int(cfg["port"])

    attempts: list[tuple[str, int, str]] = []
    if preferred_port == 465:
        attempts.append(("SSL", 465, "ssl"))
        attempts.append(("STARTTLS", 587, "starttls"))
    elif preferred_port == 587:
        attempts.append(("STARTTLS", 587, "starttls"))
        attempts.append(("SSL", 465, "ssl"))
    else:
        attempts.append((f"PORT {preferred_port}", preferred_port, "starttls"))

    errors: list[str] = []
    for label, port, mode in attempts:
        try:
            if mode == "ssl":
                _send_via_ssl(host, port, user, password, from_addr, to_list, msg)
            else:
                _send_via_starttls(host, port, user, password, from_addr, to_list, msg)
            return
        except smtplib.SMTPAuthenticationError as exc:
            raise RuntimeError(
                "SMTP 登录失败：请确认 SMTP_PASSWORD 是 QQ 邮箱「16 位授权码」，"
                "不是 QQ 登录密码。可在 QQ 邮箱 → 设置 → 账户 重新生成授权码。"
                f"（{host}:{port} {exc})"
            ) from exc
        except Exception as exc:
            errors.append(f"{label} {host}:{port} → {exc}")

    hint = (
        "邮件发送失败（GitHub 云端到美国服务器再连 QQ SMTP，偶发超时）。"
        "请检查授权码是否正确，或稍后重试 Run workflow。"
    )
    raise RuntimeError(f"{hint}\n" + "\n".join(errors))
