#!/usr/bin/env bash
# Первичная настройка и деплой «Семестра» на российском VPS (Ubuntu 22.04/24.04 или Debian 12).
# Использование:
#   sudo SEMESTER_DOMAIN=semester.example.ru bash deploy/bootstrap.sh
# Если домена ещё нет, скрипт автоматически соберёт временный HTTPS-домен <IP>.sslip.io.
set -euo pipefail

APP_DIR="${SEMESTER_APP_DIR:-/opt/semestr}"
REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Запустите от root или через sudo: sudo SEMESTER_DOMAIN=... bash deploy/bootstrap.sh" >&2
  exit 1
fi

echo "[1/5] Проверка Docker и системных пакетов..."
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg openssl cron rsync

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  . /etc/os-release
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker cron

echo "[2/5] Синхронизация приложения в ${APP_DIR}..."
mkdir -p "$APP_DIR"
if [[ "$REPO_SRC" != "$APP_DIR" ]]; then
  rsync -a --delete --exclude '.env' --exclude '.git' --exclude 'instance' --exclude '.venv' "${REPO_SRC}/" "${APP_DIR}/"
fi
chmod +x "${APP_DIR}/deploy/"*.sh

echo "[3/5] Подготовка .env..."
cd "$APP_DIR"
if [[ ! -f .env ]]; then
  PUB_IP="$(curl -4fsSL --max-time 5 https://ifconfig.me || curl -4fsSL --max-time 5 https://icanhazip.com || echo '127.0.0.1')"
  DASH_IP="${PUB_IP//./-}"
  DOMAIN="${SEMESTER_DOMAIN:-semester-${DASH_IP}.sslip.io}"
  SECRET="$(openssl rand -hex 32)"
  PW_LERA="${SEMESTER_LERA_PASSWORD:-Lera-$(openssl rand -base64 12 | tr -dc 'A-Za-z0-9' | head -c 10)-26}"
  PW_MISHA="${SEMESTER_MISHA_PASSWORD:-Misha-$(openssl rand -base64 12 | tr -dc 'A-Za-z0-9' | head -c 10)-26}"
  PW_DEAN="${SEMESTER_DEAN_PASSWORD:-Dean-$(openssl rand -base64 12 | tr -dc 'A-Za-z0-9' | head -c 10)-26}"

  umask 077
  cat > .env <<EOF
SEMESTER_DOMAIN=${DOMAIN}
SEMESTER_SECRET=${SECRET}
SEMESTER_LERA_PASSWORD=${PW_LERA}
SEMESTER_MISHA_PASSWORD=${PW_MISHA}
SEMESTER_DEAN_PASSWORD=${PW_DEAN}
EOF
  echo "Создан новый ${APP_DIR}/.env для домена: ${DOMAIN}"
  echo "Тестовые пароли стенда (сохраните для формы жюри):"
  echo "  lera@demo.example  -> ${PW_LERA}"
  echo "  misha@demo.example -> ${PW_MISHA}"
  echo "  dean@demo.example  -> ${PW_DEAN}"
else
  echo "Используется существующий ${APP_DIR}/.env"
fi

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 22/tcp >/dev/null
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw allow 443/udp >/dev/null
fi

echo "[4/5] Сборка и запуск контейнеров Docker Compose..."
docker compose up -d --build

echo "[5/5] Регистрация ежедневного бэкапа SQLite и 5-минутного мониторинга /healthz..."
cat > /etc/cron.d/semester-ops <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
15 0 * * * root SEMESTER_APP_DIR=${APP_DIR} ${APP_DIR}/deploy/backup-sqlite.sh >> /var/log/semester-backup.log 2>&1
*/5 * * * * root SEMESTER_APP_DIR=${APP_DIR} ${APP_DIR}/deploy/uptime-check.sh
EOF
chmod 0644 /etc/cron.d/semester-ops

# Первый контрольный снимок базы и проверка здоровья
SEMESTER_APP_DIR="${APP_DIR}" "${APP_DIR}/deploy/backup-sqlite.sh"
SEMESTER_APP_DIR="${APP_DIR}" "${APP_DIR}/deploy/uptime-check.sh"

# shellcheck disable=SC1091
source .env
echo ""
echo "Готово. Прототип запущен и доступен по адресу: https://${SEMESTER_DOMAIN}"
