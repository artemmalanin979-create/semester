#!/usr/bin/env bash
# Повторный деплой «Семестра» одной командой на продакшен-сервер (без перезаписи /opt/semestr/.env).
# Использование:
#   ./deploy.sh [user@host]
set -euo pipefail

REMOTE="${1:-deploy@136.234.232.127}"
SSH_KEY="${SEMESTER_SSH_KEY:-$HOME/.ssh/id_ed25519}"
APP_DIR="${SEMESTER_APP_DIR:-/opt/semestr}"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/3] Синхронизация исходников в ${REMOTE}:${APP_DIR}..."
rsync -az --delete \
  --exclude '.git' \
  --exclude '.env' \
  --exclude '.env.*' \
  --exclude 'instance' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.sqlite3*' \
  -e "ssh -i ${SSH_KEY} -o StrictHostKeyChecking=accept-new" \
  "${SRC_DIR}/" "${REMOTE}:${APP_DIR}/"

echo "[2/3] Пересборка и перезапуск контейнеров Docker Compose..."
ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new "${REMOTE}" \
  "cd '${APP_DIR}' && chmod +x deploy/*.sh deploy.sh && docker compose up -d --build --remove-orphans"

echo "[3/3] Проверка /healthz..."
ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new "${REMOTE}" \
  "cd '${APP_DIR}' && source .env && for i in {1..15}; do curl -fsSL --max-time 5 \"https://\${SEMESTER_DOMAIN}/healthz\" && echo '' && exit 0; sleep 2; done; exit 1"

echo "Деплой успешно завершён."
