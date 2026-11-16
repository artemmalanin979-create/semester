#!/usr/bin/env bash
# Онлайн-бэкап тома SQLite (безопасно при включённом WAL, без остановки Gunicorn).
set -euo pipefail

APP_DIR="${SEMESTER_APP_DIR:-/opt/semestr}"
BACKUP_DIR="${SEMESTER_BACKUP_DIR:-/var/backups/semestr}"
RETENTION_DAYS="${SEMESTER_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

cd "$APP_DIR"

docker compose exec -T app python -c "
import sqlite3
src = sqlite3.connect('/data/semester.sqlite3')
dst = sqlite3.connect('/data/backup_snapshot.sqlite3')
with dst:
    src.backup(dst)
dst.close()
src.close()
"

CID="$(docker compose ps -q app)"
docker cp "${CID}:/data/backup_snapshot.sqlite3" "${BACKUP_DIR}/semester-${STAMP}.sqlite3"
docker compose exec -T app rm -f /data/backup_snapshot.sqlite3
gzip -f "${BACKUP_DIR}/semester-${STAMP}.sqlite3"

find "$BACKUP_DIR" -name 'semester-*.sqlite3.gz' -type f -mtime "+${RETENTION_DAYS}" -delete
echo "[$(date -Is)] backup ok: ${BACKUP_DIR}/semester-${STAMP}.sqlite3.gz"
