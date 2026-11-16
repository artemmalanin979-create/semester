#!/usr/bin/env bash
# Проверка /healthz каждые 5 минут с автоподнятием контейнеров при сбое.
set -euo pipefail

APP_DIR="${SEMESTER_APP_DIR:-/opt/semester}"
LOG_FILE="${SEMESTER_UPTIME_LOG:-/var/log/semester-uptime.log}"

cd "$APP_DIR"
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

TARGET_URL="https://${SEMESTER_DOMAIN:-127.0.0.1}/healthz"

check_once() {
  curl --silent --show-error --fail --max-time 8 "$TARGET_URL" >/dev/null 2>&1 \
    || docker compose exec -T app python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=4)" >/dev/null 2>&1
}

if check_once; then
  echo "[$(date -Is)] OK ${TARGET_URL}" >> "$LOG_FILE"
  exit 0
fi

sleep 4
if check_once; then
  echo "[$(date -Is)] RECOVERED ${TARGET_URL}" >> "$LOG_FILE"
  exit 0
fi

echo "[$(date -Is)] FAIL ${TARGET_URL} — restarting docker compose" >> "$LOG_FILE"
docker compose up -d >> "$LOG_FILE" 2>&1
