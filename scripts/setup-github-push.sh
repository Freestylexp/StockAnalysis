#!/bin/bash
# 推送代码到 GitHub，供 Actions 定时微信推送使用
set -e
cd "$(dirname "$0")/.."

echo ""
echo "=========================================="
echo "  推送代码到 GitHub"
echo "=========================================="
echo ""

if [ -n "$HTTPS_PROXY" ] || [ -n "$https_proxy" ]; then
  PROXY="${HTTPS_PROXY:-$https_proxy}"
else
  SYS_PORT=$(scutil --proxy 2>/dev/null | awk '/HTTPPort/{print $3; exit}')
  if [ -n "$SYS_PORT" ]; then
    PROXY="http://127.0.0.1:${SYS_PORT}"
  fi
fi

if [ -n "$PROXY" ]; then
  echo "→ 使用代理: $PROXY"
  export https_proxy="$PROXY"
  export http_proxy="$PROXY"
  git config --global http.https://github.com.proxy "$PROXY" 2>/dev/null || true
fi

KNOWN_HOSTS="$(pwd)/.github_known_hosts"
DEPLOY_KEY="$(pwd)/.deploy_key"

if [ ! -f "$DEPLOY_KEY" ]; then
  echo "→ 生成 GitHub Deploy Key ..."
  ssh-keygen -t ed25519 -C "stock-portfolio-github" -f "$DEPLOY_KEY" -N ""
fi

echo ""
echo "【若尚未添加 Deploy Key，请复制下面公钥到 GitHub】"
echo "页面: https://github.com/Freestylexp/StockAnalysis/settings/keys/new"
echo ""
cat "${DEPLOY_KEY}.pub"
echo ""
read -p "Deploy Key 已添加到 GitHub 了吗？按回车继续，Ctrl+C 取消..."

export GIT_SSH_COMMAND="ssh -i ${DEPLOY_KEY} -o UserKnownHostsFile=${KNOWN_HOSTS} -o StrictHostKeyChecking=accept-new"

echo ""
echo "→ 推送到 GitHub ..."
git push git@github.com:Freestylexp/StockAnalysis.git main

echo ""
echo "✅ GitHub 推送成功！"
echo "下一步: 配置 GitHub Secret → PUSHPLUS_TOKEN"
echo "https://github.com/Freestylexp/StockAnalysis/settings/secrets/actions"
echo ""
