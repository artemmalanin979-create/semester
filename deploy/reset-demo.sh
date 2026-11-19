#!/usr/bin/env bash
# Мягкий периодический сброс демо-данных на продакшене (сохраняет хэши паролей и активные сессии).
set -euo pipefail

APP_DIR="${SEMESTER_APP_DIR:-/opt/semestr}"
cd "$APP_DIR"
docker compose exec -T app flask --app semester reset-demo >> /var/log/semester-reset.log 2>&1
