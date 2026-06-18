#!/bin/bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "首次运行，正在安装依赖..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt -q
else
  source .venv/bin/activate
fi

PORT=8501
URL="http://127.0.0.1:${PORT}"

if lsof -ti :${PORT} >/dev/null 2>&1; then
  echo "重启服务（释放端口 ${PORT}）..."
  lsof -ti :${PORT} | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo ""
echo "=========================================="
echo "  A股持仓分析  http://127.0.0.1:${PORT}"
echo "=========================================="
echo "请保持此终端窗口打开"
echo ""

(sleep 2 && open "${URL}") &
streamlit run app.py --server.address 127.0.0.1 --server.port "${PORT}"
