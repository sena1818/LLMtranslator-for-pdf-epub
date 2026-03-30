#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$ROOT_DIR/logs"
SERVER_PID_FILE="$LOG_DIR/server.pid"
WORKER_PID_FILE="$LOG_DIR/worker.pid"
PORT="${TRANSLATION_SERVER_PORT:-8000}"
PREVENT_SLEEP="${TRANSLATION_PREVENT_SLEEP:-0}"

mkdir -p "$LOG_DIR"

is_running() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    tr -d '[:space:]' < "$path"
  fi
}

SERVER_PID="$(read_pid_file "$SERVER_PID_FILE")"
WORKER_PID="$(read_pid_file "$WORKER_PID_FILE")"

if is_running "$SERVER_PID"; then
  echo "ℹ️ API 服务已在运行，PID=${SERVER_PID}"
else
  echo "🚀 启动 API 服务（端口: ${PORT}）..."
  nohup env \
    TRANSLATION_INLINE_WORKER=0 \
    TRANSLATION_SERVER_PORT="${PORT}" \
    python run_server.py > "$LOG_DIR/server.out" 2>&1 &
  SERVER_PID=$!
  echo "${SERVER_PID}" > "$SERVER_PID_FILE"
fi

if is_running "$WORKER_PID"; then
  echo "ℹ️ Worker 已在运行，PID=${WORKER_PID}"
else
  echo "🎯 启动后台 worker..."
  if [[ "$PREVENT_SLEEP" == "1" ]] && command -v caffeinate >/dev/null 2>&1; then
    echo "☕ 已启用防休眠模式（caffeinate）"
    nohup caffeinate -dimsu python run_worker.py > "$LOG_DIR/worker.out" 2>&1 &
  else
    nohup python run_worker.py > "$LOG_DIR/worker.out" 2>&1 &
  fi
  WORKER_PID=$!
  echo "${WORKER_PID}" > "$WORKER_PID_FILE"
fi

echo
echo "✅ 长任务模式已启动"
echo "API 文档: http://localhost:${PORT}/docs"
echo "Web 页面: http://localhost:${PORT}"
echo "Server PID: ${SERVER_PID}"
echo "Worker PID: ${WORKER_PID}"
echo
echo "日志文件:"
echo "  - $LOG_DIR/server.out"
echo "  - $LOG_DIR/worker.out"
echo
echo "查看实时日志:"
echo "  tail -f logs/server.out"
echo "  tail -f logs/worker.out"
echo
echo "可选防休眠:"
echo "  TRANSLATION_PREVENT_SLEEP=1 bash scripts/longrun.sh"
echo
echo "停止服务:"
echo "  kill \$(cat logs/server.pid) \$(cat logs/worker.pid)"
