#!/bin/bash
# 只同步持仓 data/portfolio.json 到 GitHub（供 Actions 邮件使用）
set -e
cd "$(dirname "$0")/.."

if [ -n "$HTTPS_PROXY" ] || [ -n "$https_proxy" ]; then
  PROXY="${HTTPS_PROXY:-$https_proxy}"
else
  SYS_PORT=$(scutil --proxy 2>/dev/null | awk '/HTTPPort/{print $3; exit}')
  if [ -n "$SYS_PORT" ]; then
    PROXY="http://127.0.0.1:${SYS_PORT}"
  fi
fi

if [ -n "$PROXY" ]; then
  export https_proxy="$PROXY"
  export http_proxy="$PROXY"
  git config --global http.https://github.com.proxy "$PROXY" 2>/dev/null || true
fi

FILE="data/portfolio.json"
if git diff --quiet "$FILE" 2>/dev/null && git diff --cached --quiet "$FILE" 2>/dev/null; then
  echo "→ $FILE 无本地改动"
else
  echo "→ 提交 $FILE ..."
  git add "$FILE"
  git commit -m "Sync portfolio holdings for cloud email reports"
fi

AHEAD=$(git rev-list --count origin/main..main 2>/dev/null || git rev-list --count @{u}..main 2>/dev/null || echo "?")
echo "→ 待推送 commit 数：${AHEAD}"

KNOWN_HOSTS="$(pwd)/.github_known_hosts"
DEPLOY_KEY="$(pwd)/.deploy_key"
if [ ! -f "$DEPLOY_KEY" ]; then
  echo "❌ 未找到 .deploy_key，请先运行 ./scripts/setup-github-push.sh"
  exit 1
fi

export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o UserKnownHostsFile=${KNOWN_HOSTS} -o StrictHostKeyChecking=accept-new"

echo "→ 推送到 GitHub ..."
git push git@github.com:Freestylexp/StockAnalysis.git main

echo ""
echo "✅ 持仓已同步到 GitHub"
echo "   验证: https://github.com/Freestylexp/StockAnalysis/blob/main/data/portfolio.json"
echo ""
echo "   若已配置 HF_TOKEN，GitHub Actions 会自动同步到 Hugging Face（约 2–5 分钟）"
echo "   https://huggingface.co/spaces/Freestylexp/stock-portfolio-agent"
echo "   邮件测试: Actions → Daily Email Report → Run workflow"
echo ""
python3 -c "
import json
from pathlib import Path
p = json.loads(Path('$FILE').read_text())
for h in p.get('holdings', []):
    print(f\"   {h['name']} {h['shares']}股 @ {h['cost_price']}\")
"
