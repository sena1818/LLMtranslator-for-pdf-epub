#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_FRONTEND_BUILD="${1:-}"

cd "$ROOT_DIR"

echo "[1/3] Python 语法检查"
python3 -m compileall src tests translate.py run_server.py run_worker.py >/dev/null

echo "[2/3] 后端回归测试"
python3 -m unittest discover -s tests -v

if [[ "$RUN_FRONTEND_BUILD" == "--with-frontend" ]]; then
  echo "[3/3] 前端构建检查"
  (
    cd frontend
    npm run build
  )
else
  echo "[3/3] 跳过前端构建检查"
  echo "提示: 如需同时验证前端，请运行: bash scripts/run_tests.sh --with-frontend"
fi
