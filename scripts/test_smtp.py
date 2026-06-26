#!/usr/bin/env python3
"""Quick email connectivity test (Resend API or SMTP)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.email_notify import get_email_config, send_report_email


def main() -> int:
    cfg = get_email_config()
    print(f"→ 方式：{cfg.get('transport', 'smtp')}")
    print(f"→ 发件：{cfg['from']}")
    print(f"→ 收件：{cfg['to']}")
    send_report_email(
        "邮件连通性测试",
        "<p>这是一封连通性测试邮件。收到说明当前邮件配置可用。</p>",
    )
    print("✅ 测试邮件已发送")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ 测试失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
