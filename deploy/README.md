# Развёртывание публичного стенда в РФ (без VPN, до 28 ноября и далее)

Стенд рассчитан на любую российскую облачную ВМ (**Yandex Cloud Compute**, **Timeweb Cloud**, **Selectel**) с Ubuntu 22.04 / 24.04 LTS или Debian 12 (достаточно `1–2 vCPU`, `1–2 ГБ RAM`, `15 ГБ SSD`, публичный IPv4). Никаких зарубежных CDN и туннелей нет — статика, шрифты и TLS обслуживаются напрямую контейнером Caddy 2.

## Что нужно от владельца перед запуском
1. **Публичный IPv4** созданной российской ВМ и SSH-доступ (ключ).
2. **Домен или поддомен** с `A`-записью на этот IP (боевой домен стенда: `https://semestr.iamcp.ru`, резервный адрес в `Caddyfile` — `semestr.136-234-232-127.sslip.io`).  
   *Если на чистой ВМ домена ещё нет:* скрипт может временно поднять Let's Encrypt HTTPS на `semester-<IP-через-дефис>.sslip.io`.
3. Открытые входящие порты `80/tcp`, `443/tcp` и `443/udp` в группе безопасности облака.

## Запуск одной командой
Скопируйте репозиторий на сервер и выполните:

```bash
scp -r work/semester root@<IP_СЕРВЕРА>:/opt/semester
ssh root@<IP_СЕРВЕРА> "SEMESTER_DOMAIN=semester.<ваш-домен>.ru bash /opt/semester/deploy/bootstrap.sh"
```

Если запускать сразу по IP (через `sslip.io`):

```bash
ssh root@<IP_СЕРВЕРА> "bash /opt/semester/deploy/bootstrap.sh"
```

Скрипт `deploy/bootstrap.sh` автоматически:
- установит Docker Engine и Compose Plugin (если их ещё нет);
- сгенерирует `/opt/semester/.env` с 256-битным `SEMESTER_SECRET` и уникальными паролями для 3 демо-аккаунтов (в базе хранятся только их `scrypt`-хэши);
- соберёт и запустит `app` (Gunicorn) + `proxy` (Caddy 2 с автоматическим сертификатом Let's Encrypt и заголовком `HSTS`);
- настроит `/etc/cron.d/semester-ops`:
  - **ежедневный онлайн-бэкап SQLite** (`deploy/backup-sqlite.sh` → `/var/backups/semester/semester-*.sqlite3.gz`, хранение 14 суток);
  - **проверку `/healthz` каждые 5 минут** (`deploy/uptime-check.sh`) с автоматическим подъёмом контейнеров при сбое.

## Внешний мониторинг доступности
Добавьте HTTP-проверку `GET https://<домен>/healthz` (ожидаемый код `200`, тело `ok`, интервал 5 минут) в **Yandex Cloud Monitoring** или **UptimeRobot**, чтобы получать мгновенное уведомление в Telegram/почту до окончания работы жюри (28 ноября 2026).

## Автоматический сброс демо-данных (каждые 45 минут)

На демонстрационном стенде включён таймер `semester-reset-demo.timer` (`deploy/reset-demo.sh`), который каждые **45 минут** вызывает `flask --app semester reset-demo`. Команда возвращает демонстрационные счета, заявки и расписание к эталонному сид-состоянию для следующего члена жюри, сохраняя `password_hash` и активные неистёкшие `login_sessions`.

Ручной сброс на сервере:

```bash
cd /opt/semestr && docker compose exec -T app flask --app semester reset-demo
```
