#!/usr/bin/env python3
"""Quick SMTP connectivity test (no market data)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.email_notify import get_smtp_config, send_report_email


def main() -> int:
    cfg = get_smtp_config()
    print(f"→ SMTP: {cfg['host']}:{cfg['port']}")
    print(f"→ 发件: {cfg['from']}")
    print(f"→ 收件: {cfg['to']}")
    send_report_email(
        "SMTP 测试邮件",
        "<p>这是一封 SMTP 连通性测试邮件。收到说明 GitHub Actions 邮件配置正确。</p>",
    )
    print("✅ SMTP 测试邮件已发送")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"❌ SMTP 测试失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
