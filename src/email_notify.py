"""Send daily report emails via Resend API (cloud) or SMTP (local)."""

from __future__ import annotations

import base64
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

import requests


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


def _is_github_actions() -> bool:
    return _env("GITHUB_ACTIONS").lower() == "true"


def get_email_config() -> dict[str, str | int]:
    """Return normalized email settings for logging and sending."""
    resend_key = _env("RESEND_API_KEY")
    if resend_key:
        to_addr = _require("EMAIL_TO", _env("EMAIL_TO"))
        from_addr = _env("RESEND_FROM", "onboarding@resend.dev") or "onboarding@resend.dev"
        return {
            "transport": "resend",
            "resend_api_key": resend_key,
            "from": from_addr,
            "to": to_addr,
            "host": "api.resend.com",
            "port": 443,
        }

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
        "transport": "smtp",
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "to": to_addr,
        "from": _env("EMAIL_FROM") or user,
    }


def get_smtp_config() -> dict[str, str | int]:
    """Backward-compatible helper used by local SMTP tests."""
    cfg = get_email_config()
    if cfg.get("transport") != "smtp":
        raise RuntimeError("当前使用的是 Resend API，不是 SMTP")
    return cfg


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


def _send_via_resend(
    api_key: str,
    from_addr: str,
    to_list: list[str],
    subject: str,
    html_body: str,
    markdown_body: str | None,
) -> None:
    payload: dict[str, object] = {
        "from": from_addr,
        "to": to_list,
        "subject": subject[:200],
        "html": html_body,
    }
    if markdown_body:
        payload["attachments"] = [
            {
                "filename": subject.replace(" ", "_")[:50] + ".md",
                "content": base64.b64encode(markdown_body.encode("utf-8")).decode("ascii"),
            }
        ]

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Resend API 网络错误：{exc}") from exc

    if resp.status_code >= 400:
        detail = resp.text.strip() or resp.reason
        hint = ""
        if resp.status_code in (401, 403):
            hint = " 请检查 RESEND_API_KEY 是否正确。"
        elif "domain" in detail.lower() or "from" in detail.lower():
            hint = (
                " 免费版默认发件地址为 onboarding@resend.dev，"
                "且只能发到 Resend 注册邮箱；或绑定自己的域名后改用 RESEND_FROM。"
            )
        raise RuntimeError(f"Resend API 失败 ({resp.status_code})：{detail}{hint}")


def _send_via_ssl(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_list: list[str],
    msg: MIMEMultipart,
) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=45) as server:
        server.login(user, password)
        server.sendmail(from_addr, to_list, msg.as_string())


def _send_via_starttls(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_list: list[str],
    msg: MIMEMultipart,
) -> None:
    with smtplib.SMTP(host, port, timeout=45) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(user, password)
        server.sendmail(from_addr, to_list, msg.as_string())


def _send_via_smtp(cfg: dict[str, str | int], msg: MIMEMultipart, to_list: list[str]) -> None:
    host = str(cfg["host"])
    user = str(cfg["user"])
    password = str(cfg["password"])
    from_addr = str(cfg["from"])
    preferred_port = int(cfg["port"])

    if _is_github_actions():
        raise RuntimeError(
            "GitHub Actions 云端无法稳定连接 QQ SMTP（465/587 端口常被阻断，会出现 "
            "'please run connect() first'）。请在 GitHub Secrets 配置 RESEND_API_KEY 使用 "
            "HTTPS 发信；本地测试仍可用 QQ SMTP。"
        )

    attempts: list[tuple[str, int, str]] = []
    if preferred_port == 465:
        attempts = [("SSL", 465, "ssl"), ("STARTTLS", 587, "starttls")]
    elif preferred_port == 587:
        attempts = [("STARTTLS", 587, "starttls"), ("SSL", 465, "ssl")]
    else:
        attempts = [(f"PORT {preferred_port}", preferred_port, "starttls")]

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
                "不是 QQ 登录密码。"
                f"（{host}:{port} {exc})"
            ) from exc
        except Exception as exc:
            errors.append(f"{label} {host}:{port} → {exc}")

    raise RuntimeError("SMTP 发送失败：\n" + "\n".join(errors))


def send_report_email(
    subject: str,
    html_body: str,
    markdown_body: str | None = None,
    recipients: Iterable[str] | None = None,
) -> None:
    cfg = get_email_config()
    to_list = list(recipients) if recipients else [str(cfg["to"])]

    if cfg.get("transport") == "resend":
        _send_via_resend(
            api_key=str(cfg["resend_api_key"]),
            from_addr=str(cfg["from"]),
            to_list=to_list,
            subject=subject,
            html_body=html_body,
            markdown_body=markdown_body,
        )
        return

    msg = _build_message(cfg, subject, html_body, markdown_body, to_list)
    _send_via_smtp(cfg, msg, to_list)
