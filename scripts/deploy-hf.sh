#!/bin/bash
# 推送到 Hugging Face Space（自动检测 Mac 系统代理）
set -e
cd "$(dirname "$0")/.."

echo ""
echo "=========================================="
echo "  部署到 Hugging Face Spaces"
echo "=========================================="
echo ""

pick_proxy() {
  local port="$1"
  if curl -sI --connect-timeout 3 -x "http://127.0.0.1:${port}" https://huggingface.co >/dev/null 2>&1; then
    echo "http://127.0.0.1:${port}"
    return 0
  fi
  return 1
}

PROXY=""
if [ -n "$HTTPS_PROXY" ] || [ -n "$https_proxy" ]; then
  CANDIDATE="${HTTPS_PROXY:-$https_proxy}"
  echo "→ 测试你指定的代理: $CANDIDATE"
  if curl -sI --connect-timeout 3 -x "$CANDIDATE" https://huggingface.co >/dev/null 2>&1; then
    PROXY="$CANDIDATE"
  else
    echo "⚠️  指定代理不可用，改为自动检测..."
  fi
fi

if [ -z "$PROXY" ]; then
  SYS_PORT=$(scutil --proxy 2>/dev/null | awk '/HTTPPort/{print $3; exit}')
  if [ -n "$SYS_PORT" ] && PROXY=$(pick_proxy "$SYS_PORT"); then
    echo "→ 使用系统代理: $PROXY"
  else
    for port in 7897 7890 6152 1087 1080; do
      if PROXY=$(pick_proxy "$port"); then
        echo "→ 使用可用代理: $PROXY"
        break
      fi
    done
  fi
fi

if [ -z "$PROXY" ]; then
  echo ""
  echo "❌ 找不到可用代理。请先："
  echo "  1. 打开 VPN / Clash / Surge 等代理软件"
  echo "  2. 确认代理已开启（本机常见端口 7897）"
  echo "  3. 再运行: ./scripts/deploy-hf.sh"
  exit 1
fi

export HTTPS_PROXY="$PROXY"
export https_proxy="$PROXY"
export http_proxy="$PROXY"
git config --global http.https://huggingface.co.proxy "$PROXY" 2>/dev/null || true
git config --global http.https://hf.co.proxy "$PROXY" 2>/dev/null || true

echo "→ 网络测试通过，可以连接 huggingface.co"
echo ""
echo "开始前请确认："
echo "  1. 已在 HF 创建 Docker Space"
echo "  2. 已复制 Write 权限 Token"
echo ""
echo "⚠️  输入 Token 时只粘贴 hf_ 开头那一串，不要粘贴命令！"
echo ""

read -p "你的 HF 用户名 [Freestylexp]: " HF_USER
HF_USER=${HF_USER:-Freestylexp}
read -p "Space 名称 [stock-portfolio-agent]: " HF_SPACE
HF_SPACE=${HF_SPACE:-stock-portfolio-agent}
read -p "HF Access Token（只粘贴 hf_...）: " -s HF_TOKEN
echo ""

HF_TOKEN=$(echo "$HF_TOKEN" | tr -d '[:space:]')

if [ -z "$HF_TOKEN" ] || [[ ! "$HF_TOKEN" =~ ^hf_ ]]; then
  echo "❌ Token 格式不对。应类似: hf_xxxxxxxxxxxxxxxx"
  exit 1
fi

REMOTE="https://${HF_USER}:${HF_TOKEN}@huggingface.co/spaces/${HF_USER}/${HF_SPACE}"

echo ""
echo "→ 添加远程仓库 hf ..."
git remote remove hf 2>/dev/null || true
git remote add hf "$REMOTE"

echo "→ 推送代码（可能需要 1–3 分钟）..."
if git push hf main --force; then
  git remote set-url hf "https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}"
  echo ""
  echo "✅ 推送成功！"
  echo "  https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}"
  echo "  等 Logs 显示 Running 后打开 App 即可。"
else
  echo ""
  echo "❌ 推送失败。请检查 Token 是否有 Write 权限。"
  exit 1
fi
