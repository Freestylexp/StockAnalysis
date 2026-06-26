#!/bin/bash
# 本地测试邮件推送
set -e
cd "$(dirname "$0")/.."

if [ -n "$RESEND_API_KEY" ]; then
  :
elif [ -n "$SMTP_USER" ] && [ -n "$SMTP_PASSWORD" ]; then
  :
else
  echo "请先设置邮件配置（二选一）："
  echo ""
  echo "【GitHub 云端推荐】Resend API："
  echo "  export RESEND_API_KEY='re_...'"
  echo "  export EMAIL_TO='your@qq.com'"
  echo ""
  echo "【本地测试】QQ SMTP："
  echo "  export SMTP_USER='your@qq.com'"
  echo "  export SMTP_PASSWORD='你的授权码'"
  echo "  export EMAIL_TO='your@qq.com'"
  echo ""
  echo "详见 docs/email-push-setup.md"
  exit 1
fi

source .venv/bin/activate 2>/dev/null || true
export APP_URL="${APP_URL:-https://huggingface.co/spaces/Freestylexp/stock-portfolio-agent}"
python scripts/daily_push.py
