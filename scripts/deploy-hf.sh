#!/bin/bash
# 一键推送到 Hugging Face Space（无需 GitHub）
set -e
cd "$(dirname "$0")/.."

echo ""
echo "=========================================="
echo "  部署到 Hugging Face Spaces"
echo "=========================================="
echo ""
echo "开始前请确认："
echo "  1. 已在 https://huggingface.co 注册并登录"
echo "  2. 已创建 Docker Space（不是 Streamlit SDK）"
echo "  3. 已复制 Access Token（Settings → Access Tokens → Read+Write）"
echo ""

read -p "你的 HF 用户名: " HF_USER
read -p "Space 名称（如 stock-portfolio-agent）: " HF_SPACE
read -p "HF Access Token（粘贴，不会显示）: " -s HF_TOKEN
echo ""

if [ -z "$HF_USER" ] || [ -z "$HF_SPACE" ] || [ -z "$HF_TOKEN" ]; then
  echo "❌ 信息不完整，退出"
  exit 1
fi

REMOTE="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${HF_SPACE}"

echo ""
echo "→ 添加远程仓库 hf ..."
git remote remove hf 2>/dev/null || true
git remote add hf "$REMOTE"

echo "→ 推送代码（可能需要 1–2 分钟）..."
git push hf main --force

echo ""
echo "✅ 推送成功！"
echo ""
echo "打开 Space："
echo "  https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}"
echo ""
echo "等待 Logs 显示 Running 后，用手机浏览器或微信打开上面的链接即可。"
echo ""
