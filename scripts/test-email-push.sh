#!/bin/bash
# 本地测试邮件推送
set -e
cd "$(dirname "$0")/.."

if [ -z "$SMTP_USER" ] || [ -z "$SMTP_PASSWORD" ]; then
  echo "请先设置邮箱 SMTP："
  echo "  export SMTP_USER='your@qq.com'"
  echo "  export SMTP_PASSWORD='你的授权码'"
  echo "  export EMAIL_TO='收件邮箱（可选，默认同 SMTP_USER）'"
  echo ""
  echo "QQ 邮箱授权码获取：QQ 邮箱 → 设置 → 账户 → POP3/SMTP → 开启服务"
  exit 1
fi

source .venv/bin/activate 2>/dev/null || true
export APP_URL="${APP_URL:-https://huggingface.co/spaces/Freestylexp/stock-portfolio-agent}"
python scripts/daily_push.py
