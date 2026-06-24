#!/bin/bash
# 本地测试 PushPlus 微信推送
set -e
cd "$(dirname "$0")/.."

if [ -z "$PUSHPLUS_TOKEN" ]; then
  echo "请先设置 PushPlus Token："
  echo "  export PUSHPLUS_TOKEN='你的token'"
  echo "获取地址: https://www.pushplus.plus"
  exit 1
fi

source .venv/bin/activate 2>/dev/null || true
export APP_URL="${APP_URL:-https://huggingface.co/spaces/Freestylexp/stock-portfolio-agent}"
python scripts/daily_push.py
