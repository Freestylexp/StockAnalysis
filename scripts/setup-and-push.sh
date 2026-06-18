#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"

echo "==> 1/4 检查 GitHub CLI"
if ! command -v gh &>/dev/null; then
  echo "未找到 gh，请先运行 Agent 安装步骤或执行: brew install gh"
  exit 1
fi
gh --version

echo ""
echo "==> 2/4 登录 GitHub（会打开浏览器）"
if ! gh auth status &>/dev/null; then
  gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key
fi
gh auth status

echo ""
echo "==> 3/4 配置 git 使用 gh 凭证"
gh auth setup-git

echo ""
echo "==> 4/4 推送代码到 GitHub"
cd "$(dirname "$0")/.."
git push -u origin main

echo ""
echo "✅ 推送成功！可回到 Cursor Automation 点击 Run Test"
