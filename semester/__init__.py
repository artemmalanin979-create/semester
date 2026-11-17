import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import click
from click import ClickException
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .db import close_db, get_db, initialize, reset_demo_data, session_hash
from .rag import answer_question, classify_gap_topic, sanitize_gap_question, tokenize_ru
from .rules import CLAUSE_BY_ID, DOCUMENTS
from .demo import (
    BOOKING_SLOTS,
    DORM_INFO,
    GROUP_SLOTS,
    INSTANT_TYPES,
    OFFICE_SLOT_TIMES,
    PETITION_TYPES,
    PREFILL_TEMPLATES,
    REQUEST_TYPES,
    SCHOLARSHIPS,
    SHORT_DAY,
    STAFF_PRESETS,
    STUDENT_PROFILES,
    STUDY_SPACES,
    TEACHING_ROOMS,
    TIMETABLE,
    WEEKDAY,
    academic_results,
    academic_week_number,
    build_navigator_situations,
    build_week_ics,
    day_gaps,
    fmt_date,
    fmt_dt,
    fmt_rub,
    lessons_on,
    mask_full_name,
    match_navigator_query,
    next_lesson,
    notices,
    now,
    qr_svg_path,
    timestamp_day,
    week_start,
)

STUDENT_NAV = (
    ("home", "home", "Главная"),
    ("schedule", "calendar", "Расписание"),
    ("grades", "chart", "Успеваемость"),
    ("requests_list", "file", "Документы"),
    ("campus", "wallet", "Финансы и кампус"),
    ("notifications", "bell", "Уведомления"),
)

STUDENT_MOBILE_NAV = (
    ("home", "home", "Главная"),
    ("schedule", "calendar", "Пары"),
    ("grades", "chart", "Оценки"),
    ("requests_list", "file", "Документы"),
    ("campus", "wallet", "Кампус"),
)

STAFF_NAV = (
    ("staff_dashboard", "layers", "Обращения"),
    ("staff_schedule", "calendar", "Расписание"),
    ("staff_students", "users", "Реестр студентов"),
    ("staff_notices", "bell", "Объявления"),
    ("staff_assistant", "message", "Пробелы в базе"),
)

STAFF_MOBILE_NAV = (
    ("staff_dashboard", "layers", "Очередь"),
    ("staff_schedule", "calendar", "Пары"),
    ("staff_students", "users", "Студенты"),
    ("staff_notices", "bell", "Анонсы"),
    ("staff_assistant", "message", "Вопросы"),
)

ASSISTANT_PROMPTS = (
    "Можно ли взять академ на 2 курсе?",
    "Как перевестись с платного на бюджет?",
    "Сколько пересдач допускается по предмету?",
    "Болел на зачёте — в какой срок подать 095/у?",
    "Когда слетаешь со стипендии и как подать на ПГАС?",
    "До какого числа платить за общагу и что при просрочке?",
)

DELIVERY = {"digital": "Электронно", "office": "В окне А–116"}
PAYMENT_METHODS = {"sbp": "СБП · 0 %", "mir": "Карта «Мир»"}
GROUPS = ("МП-24-1", "МО-23-2")
READY_DELAY = 120
CONCEPT_NOTICE = "Концепт для конкурса MGIMO × AI Challenge. Не официальный сервис вуза. Все данные вымышлены."
LOCAL_HASHES = (
    "scrypt:32768:8:1$RUE0Sr0umX59HRbk$609960ab64f10a3e222acd29038670c30ef2c1161fc1ad58842d0fdf0ce86958a0d368f21b5914a15a5b220476b959248d5b18487c5f8385375c0c4c0df180f1",
    "scrypt:32768:8:1$OEaczuaFNx7CUTm4$c6b8551ddc54688de0d093f6f9e5ccfbc3f8d10f95c2e421f50e50a41344ecd7dab94892c811d9765a3740be7187a2a556080737409875c5970cd78c1edee8ba",
    "scrypt:32768:8:1$sjIWDgyAojptgEJW$7ba4d62ec06caac01389c1f75839e4363de4e8233d059c1bda85e0284aded5b23db6036630aaed4bed2d507801ca977f9a9f84030b9cf01079d73c9805bd340e",
)
LOCAL_DEMO_ACCOUNTS = (
    {
        "name": "Валерия Маякова",
        "group": "МП-24-1",
        "track": "Маркетинг · 2 курс",
        "email": "lera@demo.example",
        "password": "Semestr-Lera-26",
    },
    {
        "name": "Михаил Ратников",
        "group": "МО-23-2",
        "track": "Международные отношения · 3 курс",
        "email": "misha@demo.example",
        "password": "Semestr-Misha-26",
    },
    {
        "name": "Елена Орлова",
        "group": "Деканат",
        "track": "Учебный офис · окно А–116",
        "email": "dean@demo.example",
        "password": "Semestr-Dean-26",
    },
)
SESSION_TTL = 8 * 60 * 60
TOKEN = re.compile(r"[0-9a-f]{32}")


def _local_secret(instance_path):
    path = Path(instance_path) / ".local_secret"
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        path.write_text(secret, encoding="ascii")
        return secret


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    local = os.environ.get("SEMESTER_ENV", "local") == "local"
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SEMESTER_SECRET") or (_local_secret(app.instance_path) if local else None),
        DATABASE=os.environ.get("SEMESTER_DB", str(Path(app.instance_path) / "semester.sqlite3")),
        SESSION_COOKIE_SECURE=not local,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=32 * 1024,
        TRUST_PROXY=os.environ.get("SEMESTER_TRUST_PROXY") == "1",
        DEMO_PASSWORDS=(
            os.environ.get("SEMESTER_LERA_PASSWORD"),
            os.environ.get("SEMESTER_MISHA_PASSWORD"),
            os.environ.get("SEMESTER_DEAN_PASSWORD"),
        ),
    )
    app.config.update(config or {})
    if not app.config["SECRET_KEY"] or (not local and len(app.config["SECRET_KEY"]) < 32):
        raise RuntimeError("Set SEMESTER_SECRET to a random string of at least 32 characters.")
    raw_passwords = tuple(app.config["DEMO_PASSWORDS"])
    if len(raw_passwords) == 2:
        raw_passwords = (*raw_passwords, os.environ.get("SEMESTER_DEAN_PASSWORD"))
    student_passwords = raw_passwords[:2]
    if not local and (
        not all(student_passwords)
        or min(map(len, student_passwords)) < 12
        or student_passwords[0] == student_passwords[1]
    ):
        raise RuntimeError("Set distinct demo passwords of at least 12 characters.")
    if not local and raw_passwords[2] and len(raw_passwords[2]) < 12:
        raise RuntimeError("SEMESTER_DEAN_PASSWORD must be at least 12 characters.")
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    password_hashes = (
        generate_password_hash(raw_passwords[0]) if raw_passwords[0] else LOCAL_HASHES[0],
        generate_password_hash(raw_passwords[1]) if raw_passwords[1] else LOCAL_HASHES[1],
        (
            generate_password_hash(raw_passwords[2])
            if raw_passwords[2]
            else (LOCAL_HASHES[2] if local else generate_password_hash(secrets.token_urlsafe(24)))
        ),
    )
    is_local_demo = bool(local and not any(raw_passwords))
    initialize(app.config["DATABASE"], password_hashes)
    app.teardown_appcontext(close_db)

    @app.cli.command("rotate-demo-passwords")
    def rotate_demo_passwords():
        """Apply the demo passwords from the environment and revoke active sessions."""
        if not all(student_passwords):
            raise ClickException("Set demo passwords before rotating.")
        db = get_db()
        with db:
            db.executemany(
                "UPDATE students SET password_hash = ? WHERE id = ?",
                zip(password_hashes, (1, 2, 3), strict=True),
            )
            db.execute("DELETE FROM login_sessions")

    @app.cli.command("reset-demo")
    def reset_demo():
        """Reset mutable demo data to clean seeded state while keeping password hashes."""
        reset_demo_data(get_db())
        click.echo("Demo data reset complete (password hashes preserved).")

    def public_url(endpoint, **values):
        domain = os.environ.get("SEMESTER_DOMAIN", "").strip()
        if domain and not app.config.get("TESTING"):
            return f"https://{domain}{url_for(endpoint, **values)}"
        return url_for(endpoint, _external=True, **values)

    def pass_token_for(student_id):
        sig = hmac.new(
            app.config["SECRET_KEY"].encode("utf-8"),
            f"pass:{student_id}".encode("ascii"),
            sha256,
        ).hexdigest()[:24]
        return f"p{student_id}-{sig}"

    dummy_hash = generate_password_hash(secrets.token_urlsafe(24))

    def csrf():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    def is_staff():
        return bool(g.get("student") and g.student["role"] == "staff")

    def require_student():
        if is_staff():
            return redirect(url_for("staff_dashboard"), code=303)
        return None

    def require_staff():
        if not is_staff():
            abort(404)

    @app.before_request
    def load_session():
        if request.endpoint == "static":
            return None
        g.student = None
        g.stamp = now()
        g.epoch = int(g.stamp.timestamp())
        key = session.get("key")
        if key:
            g.student = get_db().execute(
                """SELECT students.* FROM students JOIN login_sessions
                   ON login_sessions.student_id = students.id
                   WHERE login_sessions.key = ? AND expires_at > ?""",
                (session_hash(key), g.epoch),
            ).fetchone()
            if not g.student:
                session.clear()
        if request.method == "POST":
            supplied = request.form.get("_csrf", "")
            expected = session.get("_csrf")
            if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
                abort(400)
        public_endpoints = {
            "login",
            "health",
            "verify_document",
            "verify_pass",
            "verify_guest",
            "verify_receipt",
        }
        if request.endpoint and request.endpoint not in public_endpoints and not g.student:
            return redirect(url_for("login"), code=303)
        return None

    @app.after_request
    def secure_response(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.is_secure and app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    def group_overrides(group):
        rows = get_db().execute(
            "SELECT weekday, start_time, new_room FROM room_overrides WHERE student_group = ?",
            (group,),
        ).fetchall()
        return {(row["weekday"], row["start_time"]): row["new_room"] for row in rows}

    def request_summary(row):
        item = dict(row)
        item["title"], _, item["icon"] = REQUEST_TYPES[item["kind"]]
        decision = item.get("decision", "approved")
        item["is_petition"] = item["kind"] in PETITION_TYPES
        item["returned"] = decision == "returned"
        item["rejected"] = decision == "rejected"
        item["revoked"] = bool(item.get("revoked_at", 0) > 0)
        if item["revoked"]:
            item["ready"] = True
            item["closed"] = True
            item["status"] = "Отозвано"
            item["tone"] = "err"
            item["remaining"] = 0
        elif item["returned"]:
            item["ready"] = False
            item["closed"] = True
            item["status"] = "Возвращено"
            item["tone"] = "warn"
            item["remaining"] = 0
        elif item["rejected"]:
            item["ready"] = False
            item["closed"] = True
            item["status"] = "Отклонено"
            item["tone"] = "err"
            item["remaining"] = 0
        elif g.epoch >= item["ready_at"]:
            item["ready"] = True
            item["closed"] = True
            item["status"] = "Согласовано" if item["is_petition"] else "Готово"
            item["tone"] = "ok"
            item["remaining"] = 0
        else:
            item["ready"] = False
            item["closed"] = False
            item["status"] = "В работе"
            item["tone"] = "warn"
            item["remaining"] = max(0, item["ready_at"] - g.epoch)
        return item

    def owned_requests(limit):
        rows = get_db().execute(
            "SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (g.student["id"], limit),
        ).fetchall()
        return [request_summary(row) for row in rows]

    def owned_charges(student_id=None):
        sid = student_id or g.student["id"]
        rows = get_db().execute(
            "SELECT * FROM charges WHERE student_id = ? ORDER BY (status = 'unpaid') DESC, rowid ASC",
            (sid,),
        ).fetchall()
        return [dict(row) for row in rows]

    def has_ready_office_doc():
        row = get_db().execute(
            "SELECT 1 FROM requests WHERE student_id = ? AND delivery = 'office' AND decision NOT IN ('returned', 'rejected') AND ready_at <= ? LIMIT 1",
            (g.student["id"], g.epoch),
        ).fetchone()
        return bool(row)

    def owned_request(request_id):
        row = get_db().execute(
            "SELECT * FROM requests WHERE student_id = ? AND id = ?",
            (g.student["id"], request_id),
        ).fetchone()
        if not row:
            abort(404)
        return request_summary(row)

    def my_notices():
        if "notices" in g:
            return g.notices
        if is_staff():
            g.notices = []
            return g.notices
        group = g.student["student_group"]
        items = notices(g.student, g.stamp, overrides=group_overrides(group))
        published = get_db().execute(
            """SELECT * FROM staff_notices
               WHERE target_group IN (?, 'all')
               ORDER BY created_at DESC LIMIT 12""",
            (group,),
        ).fetchall()
        for row in published:
            items.insert(0, {
                "id": "staff-" + row["id"],
                "kind": row["kind"],
                "title": row["title"],
                "body": row["body"],
                "date": timestamp_day(row["created_at"]),
                "icon": "arrow-swap" if row["kind"] == "Расписание" else "info",
                "link": url_for("schedule") if row["kind"] == "Расписание" else url_for("requests_list"),
                "action": "К расписанию" if row["kind"] == "Расписание" else "К разделу",
            })
        paid_rows = get_db().execute(
            "SELECT * FROM charges WHERE student_id = ? AND status = 'paid' AND paid_at > ? ORDER BY paid_at DESC LIMIT 6",
            (g.student["id"], g.epoch - 7 * 86400),
        ).fetchall()
        for crow in paid_rows:
            items.insert(0, {
                "id": "charge-" + crow["id"],
                "kind": "Финансы",
                "title": f"Оплата проведена: {crow['title']}",
                "body": f"Сумма {fmt_rub(crow['amount'])} ({crow['payment_method']}). Электронная квитанция {crow['receipt_code']} доступна.",
                "date": timestamp_day(crow["paid_at"]),
                "icon": "wallet",
                "link": url_for("campus_receipt", charge_id=crow["id"]),
                "action": "Открыть квитанцию",
            })
        resolved = get_db().execute(
            """SELECT * FROM requests
               WHERE student_id = ? AND (ready_at <= ? OR decision IN ('returned', 'rejected'))
               ORDER BY created_at DESC LIMIT 24""",
            (g.student["id"], g.epoch),
        ).fetchall()
        for row in resolved:
            endpoint = "request_detail"
            action = "К заявке"
            kind_title = REQUEST_TYPES[row["kind"]][0]
            if row["decision"] == "returned":
                title = f"Требуется уточнение: {kind_title}"
                message = row["staff_note"] or "Учебный офис попросил уточнить сведения в обращении."
            elif row["decision"] == "rejected":
                title = f"Отклонено: {kind_title}"
                message = row["staff_note"] or "Учебный офис отклонил обращение."
            elif row["revoked_at"] > 0:
                title = f"Отозвано: {kind_title}"
                message = "Действие электронного документа прекращено в реестре."
            elif row["kind"] == "appeal":
                title = "Ответ деканата по заявлению"
                message = row["staff_note"] or "Ответ методиста доступен на странице обращения."
            elif row["kind"] in PETITION_TYPES:
                title = f"{kind_title} — согласовано"
                message = row["staff_note"] or "Решение учебного офиса отражено в вашей карточке."
            elif row["delivery"] == "office":
                title = kind_title + " готова"
                message = "Оригинал можно получить в окне А–116 по будням с 10:00 до 17:00."
            else:
                title = kind_title + " готова"
                message = "Электронный документ с матричным QR-кодом доступен в кабинете."
                endpoint = "request_document"
                action = "Открыть документ"
            items.append({
                "id": "request-" + row["id"],
                "kind": "Заявки",
                "title": title,
                "body": message,
                "date": timestamp_day(max(row["created_at"], min(row["ready_at"], g.epoch))),
                "icon": "file",
                "link": url_for(endpoint, request_id=row["id"]),
                "action": action,
            })
        seen = {
            (row["notice_id"], row["read_key"])
            for row in get_db().execute(
                "SELECT notice_id, read_key FROM notification_reads WHERE student_id = ?",
                (g.student["id"],),
            )
        }
        for item in items:
            if item["kind"] in {"Деканат", "Заявки", "Финансы"} or item["id"].startswith("staff-"):
                item["read_key"] = "1"
            else:
                item["read_key"] = item["date"].isoformat()
            item["unread"] = (item["id"], item["read_key"]) not in seen
        g.notices = items
        return items

    def rating_snapshot(student_id=None):
        sid = student_id or g.student["id"]
        records = academic_results(sid, g.stamp.date())
        completed = sum(bool(row["result"]) for row in records)
        marks = [int(row["result"]) for row in records if row["result"].isdigit()]
        average = f"{sum(marks) / len(marks):.1f}".replace(".", ",") if marks else "—"
        avg_100 = sum(row["score"] for row in records) / len(records)
        rating_avg = f"{avg_100:.1f}".replace(".", ",")
        rating_int = round(avg_100)
        rating_letter = "A" if rating_int >= 90 else "B"
        earned_credits = sum(row["credits"] for row in records if row["result"])
        total_credits = sum(row["credits"] for row in records)
        upcoming = sorted((row for row in records if not row["result"]), key=lambda row: row["date"])
        return {
            "records": records,
            "completed": completed,
            "average": average,
            "rating_avg": rating_avg,
            "rating_int": rating_int,
            "rating_letter": rating_letter,
            "earned_credits": earned_credits,
            "total_credits": total_credits,
            "upcoming": upcoming,
        }

    def build_search_index():
        if is_staff():
            return [
                {"cat": "Деканат", "title": "Очередь обращений студентов", "meta": "Согласование и возврат заявлений", "url": url_for("staff_dashboard"), "icon": "layers"},
                {"cat": "Деканат", "title": "Управление переносами пар", "meta": "Смена аудиторий групп МП-24-1 и МО-23-2", "url": url_for("staff_schedule"), "icon": "calendar"},
                {"cat": "Деканат", "title": "Реестр студентов и оплат", "meta": "Рейтинги, ЗЕТ и договоры общежития", "url": url_for("staff_students"), "icon": "users"},
                {"cat": "Деканат", "title": "Объявления потокам", "meta": "Публикация уведомлений группам", "url": url_for("staff_notices"), "icon": "bell"},
                {"cat": "Деканат", "title": "Пробелы регламентов (ассистент)", "meta": "Обезличенные вопросы студентов без ответа в положениях", "url": url_for("staff_assistant"), "icon": "message"},
                {"cat": "Регламенты", "title": "Сборник положений «Семестра»", "meta": "8 учебных и кампусных регламентов с пунктами", "url": url_for("rules_view"), "icon": "book"},
                {"cat": "Профиль", "title": "Карточка сотрудника", "meta": STUDENT_PROFILES[g.student["id"]]["card_number"], "url": url_for("profile"), "icon": "user"},
            ]
        group = g.student["student_group"]
        monday = week_start(g.stamp.date())
        overrides = group_overrides(group)
        entries = [
            {"cat": "Ассистент", "title": "Спроси деканат · ИИ по регламентам", "meta": "Ответы строго со сносками [П. X.Y]: академ, бюджет, пересдачи, 095/у, ПГАС", "url": url_for("assistant_view"), "icon": "spark"},
            {"cat": "Регламенты", "title": "Сборник положений «Семестра»", "meta": "Все 8 регламентов обучения, стипендий, общежития и воинского учёта", "url": url_for("rules_view"), "icon": "book"},
            {"cat": "Навигатор", "title": "Умный навигатор деканата", "meta": "Разбор жизненных ситуаций: военкомат, болезнь, общага, ПГАС", "url": url_for("navigator"), "icon": "compass"},
            {"cat": "Разделы", "title": "Финансы, стипендия и общежитие", "meta": "Оплата договора СБП, квитанции, гостевой QR и коворкинг", "url": url_for("campus"), "icon": "wallet"},
            {"cat": "Разделы", "title": "Расписание недели", "meta": f"Группа {group}", "url": url_for("schedule", view="week"), "icon": "calendar"},
            {"cat": "Разделы", "title": "Экспорт календаря (.ics)", "meta": "Файл расписания для смартфона", "url": url_for("schedule_ics"), "icon": "download"},
            {"cat": "Разделы", "title": "Успеваемость и сессия", "meta": "Баллы, ЗЕТ и даты экзаменов", "url": url_for("grades"), "icon": "chart"},
            {"cat": "Разделы", "title": "Профиль и пропуск", "meta": STUDENT_PROFILES[g.student["id"]]["card_number"], "url": url_for("profile"), "icon": "id-badge"},
        ]
        for kind_key, (title, desc, glyph) in REQUEST_TYPES.items():
            entries.append({
                "cat": "Справки" if kind_key in INSTANT_TYPES else "Заявления",
                "title": title,
                "meta": desc,
                "url": url_for("requests_list") if kind_key in INSTANT_TYPES else url_for("request_new", kind=kind_key),
                "icon": glyph,
            })
        seen_lessons = set()
        for offset in range(5):
            lesson_day = monday + timedelta(days=offset)
            for item in lessons_on(group, lesson_day, overrides=overrides):
                sig = (offset, item["start"], item["title"])
                if sig in seen_lessons:
                    continue
                seen_lessons.add(sig)
                room_note = f"{item['room']} (из {item['previous']})" if item["previous"] else item["room"]
                entries.append({
                    "cat": "Пары",
                    "title": f"{item['title']} · {SHORT_DAY[offset]} {item['start']}",
                    "meta": f"{item['kind']} · {room_note} · {item['teacher']}",
                    "url": f"{url_for('schedule', date=lesson_day.isoformat())}#{item['id']}",
                    "icon": "pin",
                })
        return entries

    @app.context_processor
    def common():
        signed = bool(g.get("student"))
        staff = is_staff()
        unread_count = sum(item["unread"] for item in my_notices()) if (signed and not staff) else 0
        unpaid_count = 0
        pending_staff = 0
        gaps_staff = 0
        if signed and not staff:
            unpaid_count = get_db().execute(
                "SELECT COUNT(*) AS c FROM charges WHERE student_id = ? AND status = 'unpaid'",
                (g.student["id"],),
            ).fetchone()["c"]
        elif signed and staff:
            pending_staff = get_db().execute(
                "SELECT COUNT(*) AS c FROM requests WHERE ready_at > ? AND decision NOT IN ('returned', 'rejected')",
                (g.epoch,),
            ).fetchone()["c"]
            gaps_staff = get_db().execute("SELECT COUNT(*) AS c FROM assistant_gaps").fetchone()["c"]
        student_meta = STUDENT_PROFILES[g.student["id"]] if signed else None
        pass_qr = (
            qr_svg_path(public_url("verify_pass", pass_token=pass_token_for(g.student["id"])))
            if signed else None
        )
        cookie_theme = request.cookies.get("semester_theme", "")
        theme_pref = cookie_theme if cookie_theme in {"light", "dark"} else ""
        return dict(
            nav=STAFF_NAV if staff else STUDENT_NAV,
            mobile_nav=STAFF_MOBILE_NAV if staff else STUDENT_MOBILE_NAV,
            is_staff=staff,
            pending_staff=pending_staff,
            gaps_staff=gaps_staff,
            unpaid_count=unpaid_count,
            assistant_prompts=ASSISTANT_PROMPTS,
            home_endpoint="staff_dashboard" if staff else "home",
            csrf=csrf,
            fmt_date=fmt_date,
            fmt_dt=fmt_dt,
            fmt_rub=fmt_rub,
            weekdays=WEEKDAY,
            request_types=REQUEST_TYPES,
            instant_types=INSTANT_TYPES,
            petition_types=PETITION_TYPES,
            delivery=DELIVERY,
            unread_count=unread_count,
            is_local_demo=is_local_demo,
            demo_accounts=LOCAL_DEMO_ACCOUNTS if is_local_demo else (),
            student_meta=student_meta,
            pass_qr=pass_qr,
            week_num=academic_week_number(g.stamp.date()) if signed else 1,
            search_index=build_search_index() if signed else (),
            theme_pref=theme_pref,
            concept_notice=CONCEPT_NOTICE,
        )

    @app.get("/healthz")
    def health():
        get_db().execute("SELECT 1")
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.student:
            return redirect(url_for("staff_dashboard" if is_staff() else "home"), code=303)
        if request.method != "POST":
            return render_template("login.html", error=None, email="")
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        db = get_db()
        client_ip = request.remote_addr or "unknown"
        acct_source = f"acct:{client_ip}:{email}"
        ip_source = f"ip:{client_ip}"
        bucket = int(time.time()) // 60
        with db:
            db.execute("DELETE FROM login_attempts WHERE bucket <= ?", (bucket - 10,))
            acct_fails = db.execute(
                "SELECT COALESCE(SUM(count), 0) AS c FROM login_attempts WHERE source = ? AND bucket > ?",
                (acct_source, bucket - 10),
            ).fetchone()["c"]
            ip_fails = db.execute(
                "SELECT COALESCE(SUM(count), 0) AS c FROM login_attempts WHERE source = ? AND bucket > ?",
                (ip_source, bucket - 10),
            ).fetchone()["c"]
        if acct_fails >= 5 or ip_fails >= 25:
            return (
                render_template(
                    "login.html",
                    error="Слишком много неудачных попыток входа (не более 5 за 10 минут). Подождите 10 минут и попробуйте снова.",
                    email=email,
                ),
                429,
            )
        student = db.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
        expected_hash = student["password_hash"] if student else dummy_hash
        if len(password) > 256 or not check_password_hash(expected_hash, password) or not student:
            with db:
                for src in (acct_source, ip_source):
                    db.execute(
                        """INSERT INTO login_attempts VALUES (?, ?, 1)
                           ON CONFLICT(source, bucket) DO UPDATE SET count = count + 1""",
                        (src, bucket),
                    )
            return render_template("login.html", error="Проверьте почту и пароль.", email=email), 401
        key = secrets.token_hex(32)
        with db:
            db.execute("DELETE FROM login_attempts WHERE source = ?", (acct_source,))
            db.execute("DELETE FROM login_sessions WHERE expires_at <= ?", (g.epoch,))
            db.execute(
                "INSERT INTO login_sessions VALUES (?, ?, ?)",
                (session_hash(key), student["id"], g.epoch + SESSION_TTL),
            )
        session.clear()
        session["key"] = key
        target = "staff_dashboard" if student["role"] == "staff" else "home"
        return redirect(url_for(target), code=303)

    @app.post("/logout")
    def logout():
        db = get_db()
        with db:
            db.execute("DELETE FROM login_sessions WHERE key = ?", (session_hash(session["key"]),))
        session.clear()
        return redirect(url_for("login"), code=303)

    @app.get("/")
    def home():
        guard = require_student()
        if guard:
            return guard
        sid = g.student["id"]
        group = g.student["student_group"]
        overrides = group_overrides(group)
        day = g.stamp.date()
        today = lessons_on(group, day, overrides=overrides)
        upcoming = next_lesson(group, g.stamp, overrides=overrides)
        agenda = today or (lessons_on(group, upcoming["day"], overrides=overrides) if upcoming else [])
        gaps = day_gaps(agenda, has_ready_office_doc())
        snap = rating_snapshot()
        charges = owned_charges()
        dorm = DORM_INFO[sid]
        scholar = SCHOLARSHIPS[sid]
        situations = build_navigator_situations(g.student, snap, charges, dorm, scholar)
        unpaid_dorm = next((c for c in charges if c["status"] == "unpaid"), None)
        booked_slots = {
            (r["booking_date"], r["slot_label"]): dict(r)
            for r in get_db().execute(
                "SELECT * FROM room_bookings WHERE student_id = ?",
                (sid,),
            ).fetchall()
        }
        return render_template(
            "home.html",
            active="home",
            day=day,
            today=today,
            agenda=agenda,
            gaps=gaps,
            booked_slots=booked_slots,
            upcoming=upcoming,
            in_class=bool(
                upcoming and upcoming["day"] == day and upcoming["start"] <= g.stamp.strftime("%H:%M")
            ),
            items=my_notices(),
            recent=owned_requests(3),
            snap=snap,
            unpaid_dorm=unpaid_dorm,
            scholar=scholar,
            dorm=dorm,
            situations=situations[:4],
            instant_nonce=secrets.token_hex(16),
        )

    @app.get("/navigator")
    def navigator():
        guard = require_student()
        if guard:
            return guard
        sid = g.student["id"]
        snap = rating_snapshot()
        charges = owned_charges()
        dorm = DORM_INFO[sid]
        scholar = SCHOLARSHIPS[sid]
        all_situations = build_navigator_situations(g.student, snap, charges, dorm, scholar)
        query = request.args.get("q", "").strip()[:140]
        matched = match_navigator_query(query, all_situations)
        return render_template(
            "navigator.html",
            active="home",
            query=query,
            situations=matched,
            all_situations=all_situations,
            instant_nonce=secrets.token_hex(16),
        )

    def _student_rag_context():
        sid = g.student["id"]
        snap = rating_snapshot(sid)
        charges = owned_charges(sid)
        dorm = DORM_INFO[sid]
        scholar = SCHOLARSHIPS[sid]
        profile = STUDENT_PROFILES[sid]
        unpaid_dorm = next((c for c in charges if c["status"] == "unpaid" and c["category"] == "Общежитие"), None)
        nxt = snap["upcoming"][0] if snap["upcoming"] else None
        other_markers = (
            ("миш", "михаил", "ратников", "орлов", "misha@")
            if sid == 1
            else ("валер", "маяков", "орлов", "lera@")
        )
        return {
            "course": g.student["course"],
            "program": g.student["program"],
            "group": g.student["student_group"],
            "funding": profile["funding"],
            "rating_avg": snap["rating_avg"],
            "earned_credits": snap["earned_credits"],
            "total_credits": snap["total_credits"],
            "next_exam": (
                {"title": nxt["title"], "date": fmt_date(nxt["date"]), "score": nxt["score"]}
                if nxt else None
            ),
            "unpaid_rub": sum(c["amount"] for c in charges if c["status"] == "unpaid"),
            "scholar_monthly": fmt_rub(scholar["total_monthly"]),
            "scholar_next": scholar["next_date"],
            "dorm_building": dorm["building"],
            "unpaid_dorm_rub": fmt_rub(unpaid_dorm["amount"]) if unpaid_dorm else "",
            "unpaid_dorm_due": unpaid_dorm["due_label"] if unpaid_dorm else "",
            "other_student_markers": other_markers,
        }

    def _render_cited_paragraphs(answer_text):
        paragraphs = []
        for raw_part in (answer_text or "").split("\n\n"):
            part = raw_part.strip()
            if not part:
                continue
            safe_str = str(escape(part))

            def _cite_link(match):
                cid = match.group(1)
                clause = CLAUSE_BY_ID.get(cid)
                if not clause:
                    return match.group(0)
                href = escape(clause["url"])
                title_attr = escape(f"{clause['doc_title']} — {clause['title']}")
                return f'<a class="cite-inline" href="{href}" title="{title_attr}">[П. {escape(cid)}]</a>'

            linked = re.sub(r"\[П\.\s*(\d+\.\d+)\]", _cite_link, safe_str)
            paragraphs.append(Markup(linked))
        return paragraphs

    def _load_assistant_state(db, student_id):
        rows = db.execute(
            "SELECT * FROM assistant_messages WHERE student_id = ? ORDER BY created_at ASC, rowid ASC LIMIT 40",
            (student_id,),
        ).fetchall()
        messages = []
        for row in rows:
            item = dict(row)
            item["citations"] = json.loads(item["citations_json"] or "[]")
            item["actions"] = json.loads(item["actions_json"] or "[]")
            item["paragraphs"] = _render_cited_paragraphs(item["answer_text"])
            item["time_label"] = fmt_dt(item["created_at"])
            messages.append(item)
        try:
            daily_budget = int(os.environ.get("SEMESTER_LLM_DAILY_TOKENS", "60000"))
        except ValueError:
            daily_budget = 60000
        day_key = g.stamp.date().isoformat()
        usage_row = db.execute("SELECT tokens_used FROM llm_daily_usage WHERE day = ?", (day_key,)).fetchone()
        used_today = usage_row["tokens_used"] if usage_row else 0
        budget_allows = daily_budget > 0 and used_today < daily_budget
        llm_mode = os.environ.get("SEMESTER_LLM", "off").strip().lower()
        has_gigachat = bool(llm_mode == "gigachat" and os.environ.get("GIGACHAT_AUTH_KEY", "").strip() and budget_allows)
        return messages, has_gigachat, budget_allows

    @app.get("/rules")
    def rules_view():
        query = request.args.get("q", "").strip()[:140]
        q_stems = set(tokenize_ru(query, expand=True)) if query else set()
        filtered_docs = []
        matched_clauses = 0
        for doc in DOCUMENTS:
            if not q_stems:
                clauses = [
                    {**cl, "anchor": f"p-{cl['id'].replace('.', '-')}"}
                    for cl in doc["clauses"]
                ]
            else:
                clauses = []
                for cl in doc["clauses"]:
                    haystack = f"{doc['title']} {cl['id']} {cl['title']} {cl['keywords']} {cl['text']}"
                    cl_stems = set(tokenize_ru(haystack, expand=False))
                    if q_stems & cl_stems or query.lower() in haystack.lower():
                        clauses.append({**cl, "anchor": f"p-{cl['id'].replace('.', '-')}"})
            if clauses:
                matched_clauses += len(clauses)
                filtered_docs.append({**doc, "clauses": clauses})
        return render_template(
            "rules.html",
            active="staff_assistant" if is_staff() else "home",
            documents=filtered_docs,
            total_docs=len(DOCUMENTS),
            matched_clauses=matched_clauses,
            query=query,
        )

    @app.get("/assistant")
    def assistant_view():
        guard = require_student()
        if guard:
            return guard
        prefill_q = request.args.get("q", "").strip()[:500]
        messages, has_gigachat, _ = _load_assistant_state(get_db(), g.student["id"])
        return render_template(
            "assistant.html",
            active="home",
            messages=messages,
            prefill_q=prefill_q,
            prompts=ASSISTANT_PROMPTS,
            has_gigachat=has_gigachat,
            error=None,
        )

    @app.post("/assistant/ask")
    def assistant_ask():
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        raw_question = request.form.get("question", "").strip()
        if len(raw_question) > 500:
            messages, has_gigachat, _ = _load_assistant_state(db, g.student["id"])
            return (
                render_template(
                    "assistant.html",
                    active="home",
                    messages=messages,
                    prefill_q=raw_question[:500],
                    prompts=ASSISTANT_PROMPTS,
                    has_gigachat=has_gigachat,
                    error="Длина вопроса не должна превышать 500 символов.",
                ),
                422,
            )
        if len(raw_question) < 2:
            flash("Введите вопрос по учебным регламентам или кампусу.")
            return redirect(url_for("assistant_view"), code=303)

        sid = g.student["id"]
        client_ip = request.remote_addr or "local"
        now_ts = int(time.time())
        min_bucket = now_ts // 60
        day_bucket = now_ts // 86400
        limits = (
            (f"m:stu:{sid}", min_bucket, 10),
            (f"d:stu:{sid}", day_bucket, 60),
            (f"m:ip:{client_ip}", min_bucket, 20),
            (f"d:ip:{client_ip}", day_bucket, 120),
        )
        with db:
            db.execute(
                "DELETE FROM assistant_rate WHERE (session_key LIKE 'm:%' AND bucket < ?) OR (session_key LIKE 'd:%' AND bucket < ?)",
                (min_bucket - 2, day_bucket - 2),
            )
            for rkey, rbucket, cap in limits:
                used = db.execute(
                    "SELECT COALESCE(SUM(count), 0) AS c FROM assistant_rate WHERE session_key = ? AND bucket = ?",
                    (rkey, rbucket),
                ).fetchone()["c"]
                if used >= cap:
                    abort(429)
            for rkey, rbucket, _ in limits:
                db.execute(
                    """INSERT INTO assistant_rate VALUES (?, ?, 1)
                       ON CONFLICT(session_key, bucket) DO UPDATE SET count = count + 1""",
                    (rkey, rbucket),
                )

        messages, _, budget_allows_llm = _load_assistant_state(db, sid)
        history_turns = []
        for prev in messages[-3:]:
            history_turns.append({"role": "user", "content": prev["question"]})
            history_turns.append({"role": "assistant", "content": prev["answer_text"]})

        result = answer_question(
            raw_question,
            _student_rag_context(),
            history=history_turns,
            budget_allows_llm=budget_allows_llm,
        )
        msg_id = secrets.token_hex(12)
        day_key = g.stamp.date().isoformat()
        with db:
            if result.get("tokens_used", 0) > 0:
                db.execute(
                    """INSERT INTO llm_daily_usage VALUES (?, ?)
                       ON CONFLICT(day) DO UPDATE SET tokens_used = tokens_used + excluded.tokens_used""",
                    (day_key, int(result["tokens_used"])),
                )
            db.execute(
                """INSERT INTO assistant_messages
                   (id, student_id, question, answer_text, citations_json, actions_json, mode_label, found, rating, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    msg_id,
                    sid,
                    raw_question,
                    result["answer_text"],
                    json.dumps(result["citations"], ensure_ascii=False),
                    json.dumps(result["actions"], ensure_ascii=False),
                    result["mode_label"],
                    1 if result["found"] else 0,
                    g.epoch,
                ),
            )
            if not result["found"] and not result.get("is_attack"):
                clean_gap = sanitize_gap_question(raw_question)
                if len(clean_gap) >= 4:
                    topic = classify_gap_topic(raw_question)
                    db.execute(
                        """INSERT INTO assistant_gaps VALUES (?, ?, ?, 1, ?)
                           ON CONFLICT(question_sanitized)
                           DO UPDATE SET hits = hits + 1, updated_at = excluded.updated_at""",
                        (secrets.token_hex(10), topic, clean_gap, g.epoch),
                    )
        return redirect(url_for("assistant_view") + f"#msg-{msg_id}", code=303)

    @app.post("/assistant/feedback/<msg_id>")
    def assistant_feedback(msg_id):
        guard = require_student()
        if guard:
            return guard
        if not re.fullmatch(r"[0-9a-f]{16,32}", msg_id):
            abort(404)
        raw_rating = request.form.get("rating", "")
        if raw_rating not in {"1", "-1"}:
            abort(400)
        rating_val = int(raw_rating)
        db = get_db()
        with db:
            cur = db.execute(
                "UPDATE assistant_messages SET rating = ? WHERE id = ? AND student_id = ?",
                (rating_val, msg_id, g.student["id"]),
            )
        if cur.rowcount == 0:
            abort(404)
        flash("Спасибо! Оценка ответа учтена.")
        return redirect(url_for("assistant_view") + f"#msg-{msg_id}", code=303)

    @app.post("/assistant/clear")
    def assistant_clear():
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        with db:
            db.execute("DELETE FROM assistant_messages WHERE student_id = ?", (g.student["id"],))
        flash("Начат новый диалог.")
        return redirect(url_for("assistant_view"), code=303)

    @app.get("/schedule")
    def schedule():
        guard = require_student()
        if guard:
            return guard
        today = g.stamp.date()
        try:
            selected = date.fromisoformat(request.args.get("date", today.isoformat()))
        except ValueError:
            abort(400)
        if abs((selected - today).days) > 120:
            abort(404)
        view = request.args.get("view", "day")
        if view not in {"day", "week"}:
            abort(404)
        group = g.student["student_group"]
        overrides = group_overrides(group)
        start = week_start(selected)
        week = [start + timedelta(days=i) for i in range(7)]
        week_lessons = {d: lessons_on(group, d, overrides=overrides) for d in week}
        days = [selected] if view == "day" else week
        pairs = [(d, week_lessons[d]) for d in days]
        slots = GROUP_SLOTS[group]
        grid_lookup = {}
        for d in week[:5]:
            for item in week_lessons[d]:
                grid_lookup[(d.isoformat(), item["slot"])] = item
        week_meta = {
            d.isoformat(): {
                "count": len(week_lessons[d]),
                "moved": any(item["previous"] for item in week_lessons[d]),
            }
            for d in week
        }
        gaps = day_gaps(week_lessons[selected], has_ready_office_doc()) if view == "day" else {}
        return render_template(
            "schedule.html",
            active="schedule",
            selected=selected,
            today=today,
            view=view,
            week=week,
            week_start=start,
            days=pairs,
            slots=slots,
            study_days=week[:5],
            grid_lookup=grid_lookup,
            week_meta=week_meta,
            gaps=gaps,
            short_day=SHORT_DAY,
            prev=max(today - timedelta(days=120), selected - timedelta(days=7)),
            next=min(today + timedelta(days=120), selected + timedelta(days=7)),
        )

    @app.get("/schedule.ics")
    def schedule_ics():
        guard = require_student()
        if guard:
            return guard
        today = g.stamp.date()
        try:
            selected = date.fromisoformat(request.args.get("date", today.isoformat()))
        except ValueError:
            abort(400)
        if abs((selected - today).days) > 120:
            abort(404)
        overrides = group_overrides(g.student["student_group"])
        payload = build_week_ics(g.student, week_start(selected), overrides=overrides)
        return Response(
            payload,
            mimetype="text/calendar; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="semester-schedule.ics"'},
        )

    @app.get("/grades")
    def grades():
        guard = require_student()
        if guard:
            return guard
        snap = rating_snapshot()
        next_exam = snap["upcoming"][0] if snap["upcoming"] else None
        days_left = max(0, (next_exam["date"] - g.stamp.date()).days) if next_exam else None
        return render_template(
            "grades.html",
            active="grades",
            records=snap["records"],
            completed=snap["completed"],
            average=snap["average"],
            rating_avg=snap["rating_avg"],
            rating_int=snap["rating_int"],
            rating_letter=snap["rating_letter"],
            earned_credits=snap["earned_credits"],
            total_credits=snap["total_credits"],
            upcoming=snap["upcoming"],
            next_exam=next_exam,
            days_left=days_left,
            instant_nonce=secrets.token_hex(16),
        )

    @app.get("/requests")
    def requests_list():
        guard = require_student()
        if guard:
            return guard
        try:
            page = max(1, min(int(request.args.get("page", "1")), 100_000))
        except ValueError:
            abort(400)
        db = get_db()
        rows = db.execute(
            """SELECT * FROM requests WHERE student_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 13 OFFSET ?""",
            (g.student["id"], (page - 1) * 12),
        ).fetchall()
        my_slots = db.execute(
            "SELECT * FROM office_slots WHERE student_id = ? ORDER BY visit_date ASC, slot_time ASC",
            (g.student["id"],),
        ).fetchall()
        next_study_day = g.stamp.date()
        while next_study_day.weekday() >= 5:
            next_study_day += timedelta(days=1)
        slot_days = [next_study_day, next_study_day + timedelta(days=1 if next_study_day.weekday() < 4 else 3)]
        taken_slots = {
            (r["visit_date"], r["slot_time"])
            for r in db.execute("SELECT visit_date, slot_time FROM office_slots").fetchall()
        }
        return render_template(
            "requests.html",
            active="requests_list",
            page=page,
            more=len(rows) > 12,
            items=[request_summary(row) for row in rows[:12]],
            instant_nonce=secrets.token_hex(16),
            my_slots=my_slots,
            slot_days=slot_days,
            slot_times=OFFICE_SLOT_TIMES,
            taken_slots=taken_slots,
        )

    @app.post("/requests/instant/<kind>")
    def request_instant(kind):
        guard = require_student()
        if guard:
            return guard
        if kind not in INSTANT_TYPES:
            abort(404)
        nonce = request.form.get("nonce", "")
        if not TOKEN.fullmatch(nonce):
            abort(400)
        comment = request.form.get("comment", "").strip()[:200]
        db = get_db()
        with db:
            db.execute(
                """INSERT INTO requests VALUES (?, ?, ?, 'digital', ?, ?, ?, ?, '', 'approved', ?, 0)
                   ON CONFLICT(student_id, nonce) DO NOTHING""",
                (secrets.token_hex(16), g.student["id"], kind, comment, g.epoch, g.epoch, nonce, secrets.token_urlsafe(16)),
            )
            created = db.execute(
                "SELECT id FROM requests WHERE student_id = ? AND nonce = ?",
                (g.student["id"], nonce),
            ).fetchone()
        flash("Электронная справка мгновенно сформирована и подписана кодом реестра.")
        return redirect(url_for("request_document", request_id=created["id"]), code=303)

    @app.post("/requests/slot")
    def book_office_slot():
        guard = require_student()
        if guard:
            return guard
        visit_date = request.form.get("visit_date", "")
        slot_time = request.form.get("slot_time", "")
        topic = request.form.get("topic", "Получение бумажного оригинала").strip()[:120] or "Получение оригинала"
        try:
            parsed_day = date.fromisoformat(visit_date)
        except ValueError:
            abort(400)
        if slot_time not in OFFICE_SLOT_TIMES or abs((parsed_day - g.stamp.date()).days) > 30:
            abort(400)
        ticket = f"А-{parsed_day.day:02d}{slot_time[:2]}"
        db = get_db()
        try:
            with db:
                db.execute(
                    "INSERT INTO office_slots VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (secrets.token_hex(12), g.student["id"], visit_date, slot_time, topic, ticket, g.epoch),
                )
            flash(f"Запись в окно А–116 подтверждена (талон {ticket}, {fmt_date(parsed_day)} в {slot_time}).")
        except sqlite3.IntegrityError:
            flash("Выбранное время в окне А–116 уже занято — выберите соседний слот.")
        return redirect(url_for("requests_list") + "#office-slots", code=303)

    @app.post("/requests/slot/<slot_id>/cancel")
    def cancel_office_slot(slot_id):
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        with db:
            cur = db.execute(
                "DELETE FROM office_slots WHERE id = ? AND student_id = ?",
                (slot_id, g.student["id"]),
            )
        if cur.rowcount == 0:
            abort(404)
        flash("Запись в окно А–116 отменена.")
        return redirect(url_for("requests_list") + "#office-slots", code=303)

    @app.route("/requests/new/<kind>", methods=["GET", "POST"])
    def request_new(kind):
        guard = require_student()
        if guard:
            return guard
        if kind not in REQUEST_TYPES:
            abort(404)
        is_pet = kind in PETITION_TYPES
        if request.method != "POST":
            prefill_key = request.args.get("prefill", "")
            prefill_subj, prefill_body = PREFILL_TEMPLATES.get(prefill_key, ("", ""))
            custom_q = request.args.get("q", "").strip()[:400]
            if custom_q and not prefill_body:
                prefill_subj = prefill_subj or "Индивидуальный вопрос по обучению"
                prefill_body = f"Вопрос в учебный офис: {custom_q}"
            return render_template(
                "request_new.html",
                active="requests_list",
                kind=kind,
                is_petition=is_pet,
                nonce=secrets.token_hex(16),
                selected="digital",
                selected_subject=prefill_subj,
                comment=prefill_body,
                error=None,
                disciplines=[r["title"] for r in academic_results(g.student["id"], g.stamp.date())],
            )
        nonce = request.form.get("nonce", "")
        if not TOKEN.fullmatch(nonce):
            abort(400)
        selected = "digital" if is_pet else request.form.get("delivery")
        extra_subject = request.form.get("subject", "").strip()[:100]
        raw_comment = request.form.get("comment", "").strip()
        comment = f"[{extra_subject}] {raw_comment}".strip() if extra_subject else raw_comment
        error = None
        if selected not in DELIVERY:
            error = "Укажите способ получения."
        elif len(comment) > 500:
            error = "Сократите текст до 500 знаков."
        elif is_pet and len(comment) < 10:
            error = "Опишите основание обращения подробнее, минимум 10 знаков."
        if error:
            return (
                render_template(
                    "request_new.html",
                    active="requests_list",
                    kind=kind,
                    is_petition=is_pet,
                    nonce=nonce,
                    selected=selected,
                    selected_subject=extra_subject,
                    comment=raw_comment[:500],
                    error=error,
                    disciplines=[r["title"] for r in academic_results(g.student["id"], g.stamp.date())],
                ),
                422,
            )
        db = get_db()
        delay = 1800 if is_pet else READY_DELAY
        init_decision = "pending" if is_pet else "approved"
        with db:
            db.execute(
                """INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, 0)
                   ON CONFLICT(student_id, nonce) DO NOTHING""",
                (
                    secrets.token_hex(16),
                    g.student["id"],
                    kind,
                    selected,
                    comment,
                    g.epoch,
                    g.epoch + delay,
                    nonce,
                    init_decision,
                    secrets.token_urlsafe(16),
                ),
            )
            created = db.execute(
                "SELECT id FROM requests WHERE student_id = ? AND nonce = ?",
                (g.student["id"], nonce),
            ).fetchone()
        flash("Обращение передано в учебный офис." if is_pet else "Заявка сохранена.")
        return redirect(url_for("request_detail", request_id=created["id"]), code=303)

    @app.get("/requests/<request_id>")
    def request_detail(request_id):
        guard = require_student()
        if guard:
            return guard
        return render_template("request_detail.html", active="requests_list", item=owned_request(request_id))

    @app.get("/requests/<request_id>/document")
    def request_document(request_id):
        guard = require_student()
        if guard:
            return guard
        item = owned_request(request_id)
        if not item["ready"] or item["returned"] or item["rejected"] or item["delivery"] != "digital" or item["kind"] not in INSTANT_TYPES:
            abort(404)
        sid = g.student["id"]
        records = academic_results(sid, g.stamp.date()) if item["kind"] == "grades" else []
        scholar = SCHOLARSHIPS[sid] if item["kind"] == "income" else None
        dorm = DORM_INFO[sid] if item["kind"] == "dorm_cert" else None
        verify_url = public_url("verify_document", token=item["verify_token"])
        doc_qr = qr_svg_path(verify_url)
        verify_code = f"SM-{item['id'][:4].upper()}-{item['id'][4:8].upper()}"
        valid_days = 30 if item["kind"] == "military" else 90
        valid_until = fmt_date(timestamp_day(item["ready_at"] + valid_days * 86400))
        return render_template(
            "document.html",
            active="requests_list",
            item=item,
            records=records,
            scholar=scholar,
            dorm=dorm,
            doc_qr=doc_qr,
            verify_code=verify_code,
            verify_url=verify_url,
            valid_until=valid_until,
        )

    @app.get("/verify/<token>")
    def verify_document(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{12,64}", token):
            abort(404)
        row = get_db().execute(
            """SELECT requests.*, students.full_name, students.faculty, students.program, students.course
               FROM requests JOIN students ON students.id = requests.student_id
               WHERE requests.verify_token = ? AND requests.delivery = 'digital'
                 AND requests.decision = 'approved' AND requests.ready_at <= ?""",
            (token, g.epoch),
        ).fetchone()
        if not row or row["kind"] not in INSTANT_TYPES:
            abort(404)
        doc_title = REQUEST_TYPES[row["kind"]][0]
        verify_code = f"SM-{row['id'][:4].upper()}-{row['id'][4:8].upper()}"
        valid_days = 30 if row["kind"] == "military" else 90
        valid_until = fmt_date(timestamp_day(row["ready_at"] + valid_days * 86400))
        is_revoked = row["revoked_at"] > 0
        can_revoke = bool(
            g.student and (g.student["id"] == row["student_id"] or is_staff()) and not is_revoked
        )
        return render_template(
            "verify.html",
            active="requests_list",
            doc_id=row["id"],
            doc_title=doc_title,
            masked_name=mask_full_name(row["full_name"]),
            faculty=row["faculty"],
            program=row["program"],
            course=row["course"],
            issued_at=fmt_dt(row["ready_at"]),
            valid_until=valid_until,
            verify_code=verify_code,
            is_revoked=is_revoked,
            revoked_at=fmt_dt(row["revoked_at"]) if is_revoked else "",
            can_revoke=can_revoke,
        )

    @app.post("/requests/<request_id>/revoke")
    def revoke_document(request_id):
        db = get_db()
        row = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        if not row or row["kind"] not in INSTANT_TYPES or row["delivery"] != "digital":
            abort(404)
        if not (row["student_id"] == g.student["id"] or is_staff()):
            abort(404)
        if row["revoked_at"] == 0:
            with db:
                db.execute("UPDATE requests SET revoked_at = ? WHERE id = ?", (g.epoch, request_id))
            flash("Электронная справка отозвана, статус в публичном реестре обновлён.")
        return redirect(url_for("verify_document", token=row["verify_token"]), code=303)

    @app.get("/verify/pass/<pass_token>")
    def verify_pass(pass_token):
        m = re.fullmatch(r"p([1-3])-([0-9a-f]{24})", pass_token)
        if not m:
            abort(404)
        sid = int(m.group(1))
        if not secrets.compare_digest(pass_token, pass_token_for(sid)):
            abort(404)
        row = get_db().execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
        if not row:
            abort(404)
        meta = STUDENT_PROFILES[sid]
        return render_template(
            "verify.html",
            active="profile",
            doc_id="",
            doc_title="Электронный кампусный пропуск «Семестр ID»",
            masked_name=mask_full_name(row["full_name"]),
            faculty=row["faculty"],
            program=f"{meta['degree']} · зоны: {meta['pass_zone']}",
            course=row["course"] or 1,
            issued_at="Осенний семестр 2026",
            valid_until=meta["pass_valid"],
            verify_code=meta["card_number"],
            is_revoked=False,
            revoked_at="",
            can_revoke=False,
        )

    @app.get("/verify/guest/<pass_id>")
    def verify_guest(pass_id):
        if not re.fullmatch(r"[0-9a-f]{16,32}", pass_id):
            abort(404)
        row = get_db().execute(
            """SELECT guest_passes.*, students.faculty, students.course
               FROM guest_passes JOIN students ON students.id = guest_passes.student_id
               WHERE guest_passes.id = ?""",
            (pass_id,),
        ).fetchone()
        if not row:
            abort(404)
        return render_template(
            "verify.html",
            active="campus",
            doc_id="",
            doc_title="Разовый гостевой пропуск в кампус",
            masked_name=mask_full_name(row["guest_name"]),
            faculty=row["location"],
            program="Вход с 09:00 до 22:00 по документу, удостоверяющему личность",
            course=row["course"],
            issued_at=fmt_dt(row["created_at"]),
            valid_until=row["visit_date"],
            verify_code=f"GP-{row['id'][:6].upper()}",
            is_revoked=False,
            revoked_at="",
            can_revoke=False,
        )

    @app.get("/verify/receipt/<receipt_code>")
    def verify_receipt(receipt_code):
        if not re.fullmatch(r"RCP-[A-Z0-9]{4}-[0-9]{4}", receipt_code):
            abort(404)
        row = get_db().execute(
            """SELECT charges.*, students.full_name, students.faculty, students.course
               FROM charges JOIN students ON students.id = charges.student_id
               WHERE charges.receipt_code = ? AND charges.status = 'paid'""",
            (receipt_code,),
        ).fetchone()
        if not row:
            abort(404)
        return render_template(
            "verify.html",
            active="campus",
            doc_id="",
            doc_title=f"Электронная квитанция ({row['category']})",
            masked_name=mask_full_name(row["full_name"]),
            faculty=row["faculty"],
            program=f"Договор {row['contract_no']} · {row['period_label']}",
            course=row["course"],
            issued_at=fmt_dt(row["paid_at"]),
            valid_until="Бессрочно",
            verify_code=row["receipt_code"],
            is_revoked=False,
            revoked_at="",
            can_revoke=False,
        )

    @app.get("/campus")
    def campus():
        guard = require_student()
        if guard:
            return guard
        sid = g.student["id"]
        db = get_db()
        charges = owned_charges()
        unpaid_total = sum(c["amount"] for c in charges if c["status"] == "unpaid")
        dorm = DORM_INFO[sid]
        scholar = SCHOLARSHIPS[sid]
        passes = []
        for row in db.execute(
            "SELECT * FROM guest_passes WHERE student_id = ? ORDER BY created_at DESC LIMIT 8",
            (sid,),
        ).fetchall():
            entry = dict(row)
            entry["qr"] = qr_svg_path(public_url("verify_guest", pass_id=row["id"]))
            entry["code"] = f"GP-{row['id'][:6].upper()}"
            passes.append(entry)
        my_bookings = db.execute(
            "SELECT * FROM room_bookings WHERE student_id = ? ORDER BY booking_date ASC, slot_label ASC",
            (sid,),
        ).fetchall()
        taken_bookings = {
            (r["space_id"], r["booking_date"], r["slot_label"])
            for r in db.execute("SELECT space_id, booking_date, slot_label FROM room_bookings").fetchall()
        }
        base_day = g.stamp.date()
        if base_day.weekday() >= 5:
            base_day += timedelta(days=(7 - base_day.weekday()))
        booking_days = [base_day, base_day + timedelta(days=1 if base_day.weekday() < 4 else 3)]
        return render_template(
            "campus.html",
            active="campus",
            charges=charges,
            unpaid_total=unpaid_total,
            dorm=dorm,
            scholar=scholar,
            guest_passes=passes,
            my_bookings=my_bookings,
            spaces=STUDY_SPACES,
            booking_slots=BOOKING_SLOTS,
            booking_days=booking_days,
            taken_bookings=taken_bookings,
            instant_nonce=secrets.token_hex(16),
        )

    @app.post("/campus/pay/<charge_id>")
    def campus_pay(charge_id):
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        row = db.execute(
            "SELECT * FROM charges WHERE id = ? AND student_id = ?",
            (charge_id, g.student["id"]),
        ).fetchone()
        if not row:
            abort(404)
        method_key = request.form.get("method", "sbp")
        method_label = PAYMENT_METHODS.get(method_key, "СБП · 0 %")
        if row["status"] != "paid":
            rcode = f"RCP-{secrets.token_hex(2).upper()}-{g.student['id']}026"
            with db:
                db.execute(
                    """UPDATE charges
                       SET status = 'paid', paid_at = ?, payment_method = ?, receipt_code = ?, due_label = ?
                       WHERE id = ? AND student_id = ?""",
                    (
                        g.epoch,
                        method_label,
                        rcode,
                        f"оплачено {fmt_date(g.stamp.date())}",
                        charge_id,
                        g.student["id"],
                    ),
                )
            flash(f"Платёж {fmt_rub(row['amount'])} успешно проведён без комиссии. Сформирована электронная квитанция.")
        return redirect(url_for("campus_receipt", charge_id=charge_id), code=303)

    @app.get("/campus/receipt/<charge_id>")
    def campus_receipt(charge_id):
        guard = require_student()
        if guard:
            return guard
        row = get_db().execute(
            "SELECT * FROM charges WHERE id = ? AND student_id = ?",
            (charge_id, g.student["id"]),
        ).fetchone()
        if not row or row["status"] != "paid":
            abort(404)
        charge = dict(row)
        receipt_qr = qr_svg_path(public_url("verify_receipt", receipt_code=charge["receipt_code"]))
        return render_template(
            "receipt.html",
            active="campus",
            charge=charge,
            dorm=DORM_INFO[g.student["id"]],
            receipt_qr=receipt_qr,
        )

    @app.post("/campus/guest-pass")
    def campus_guest_pass():
        guard = require_student()
        if guard:
            return guard
        guest_name = request.form.get("guest_name", "").strip()
        visit_date = request.form.get("visit_date", "").strip()
        location = request.form.get("location", "").strip()
        allowed_locations = {
            DORM_INFO[g.student["id"]]["building"],
            "Учебный корпус А",
            "Учебный корпус Б",
        }
        try:
            parsed_day = date.fromisoformat(visit_date)
        except ValueError:
            abort(400)
        if len(guest_name) < 5 or len(guest_name) > 100 or location not in allowed_locations:
            flash("Укажите полное ФИО гостя и выберите корпус.")
            return redirect(url_for("campus") + "#campus-pass-section", code=303)
        if abs((parsed_day - g.stamp.date()).days) > 30:
            abort(400)
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO guest_passes VALUES (?, ?, ?, ?, ?, ?)",
                (secrets.token_hex(12), g.student["id"], guest_name, visit_date, location, g.epoch),
            )
        flash(f"Разовый гостевой QR-пропуск для «{guest_name}» выпущен.")
        return redirect(url_for("campus") + "#campus-pass-section", code=303)

    @app.post("/campus/guest-pass/<pass_id>/revoke")
    def campus_revoke_guest(pass_id):
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        with db:
            cur = db.execute(
                "DELETE FROM guest_passes WHERE id = ? AND student_id = ?",
                (pass_id, g.student["id"]),
            )
        if cur.rowcount == 0:
            abort(404)
        flash("Гостевой пропуск отозван.")
        return redirect(url_for("campus") + "#campus-pass-section", code=303)

    @app.post("/campus/book-room")
    def campus_book_room():
        guard = require_student()
        if guard:
            return guard
        space_id = request.form.get("space_id", "")
        booking_date = request.form.get("booking_date", "")
        slot_label = request.form.get("slot_label", "")
        purpose = request.form.get("purpose", "").strip()[:120] or "Групповая подготовка к семинару"
        space_map = {sid: title for sid, title, _ in STUDY_SPACES}
        try:
            parsed_day = date.fromisoformat(booking_date)
        except ValueError:
            abort(400)
        if space_id not in space_map or slot_label not in BOOKING_SLOTS or abs((parsed_day - g.stamp.date()).days) > 30:
            abort(400)
        db = get_db()
        try:
            with db:
                db.execute(
                    "INSERT INTO room_bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        secrets.token_hex(12),
                        g.student["id"],
                        space_id,
                        space_map[space_id],
                        booking_date,
                        slot_label,
                        purpose,
                        g.epoch,
                    ),
                )
            flash(f"Забронировано: {space_map[space_id]} ({fmt_date(parsed_day)}, {slot_label}).")
        except sqlite3.IntegrityError:
            flash("Этот тайм-слот уже занят другой проектной группой.")
        return redirect(url_for("campus") + "#cowork-section", code=303)

    @app.post("/campus/book-room/<booking_id>/cancel")
    def campus_cancel_room(booking_id):
        guard = require_student()
        if guard:
            return guard
        db = get_db()
        with db:
            cur = db.execute(
                "DELETE FROM room_bookings WHERE id = ? AND student_id = ?",
                (booking_id, g.student["id"]),
            )
        if cur.rowcount == 0:
            abort(404)
        flash("Бронирование аудитории отменено.")
        return redirect(url_for("campus") + "#cowork-section", code=303)

    @app.post("/campus/book-gap")
    def campus_book_gap():
        guard = require_student()
        if guard:
            return guard
        booking_date = request.form.get("booking_date", "")
        slot_label = request.form.get("slot_label", "")
        try:
            parsed_day = date.fromisoformat(booking_date)
        except ValueError:
            abort(400)
        if slot_label not in BOOKING_SLOTS or abs((parsed_day - g.stamp.date()).days) > 30:
            abort(400)
        db = get_db()
        existing = db.execute(
            "SELECT space_title FROM room_bookings WHERE student_id = ? AND booking_date = ? AND slot_label = ?",
            (g.student["id"], booking_date, slot_label),
        ).fetchone()
        if existing:
            flash(f"На это окно у вас уже забронирован «{existing['space_title']}» ({slot_label}).")
            return redirect(url_for("home") + "#agenda-heading", code=303)
        booked_title = None
        for space_id, space_title, _ in STUDY_SPACES:
            try:
                with db:
                    db.execute(
                        "INSERT INTO room_bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            secrets.token_hex(12),
                            g.student["id"],
                            space_id,
                            space_title,
                            booking_date,
                            slot_label,
                            "Свободное окно между парами",
                            g.epoch,
                        ),
                    )
                booked_title = space_title
                break
            except sqlite3.IntegrityError:
                continue
        if booked_title:
            flash(f"Свободное окно занято в 1 клик: {booked_title} ({fmt_date(parsed_day)}, {slot_label}).")
        else:
            flash("Все проектные боксы на этот слот уже заняты.")
        return redirect(url_for("home") + "#agenda-heading", code=303)

    @app.get("/notifications")
    def notifications():
        guard = require_student()
        if guard:
            return guard
        return render_template("notifications.html", active="notifications", items=my_notices())

    @app.get("/notifications/<notice_id>")
    def notification_detail(notice_id):
        guard = require_student()
        if guard:
            return guard
        item = next((item for item in my_notices() if item["id"] == notice_id), None)
        if not item:
            abort(404)
        return render_template("notification_detail.html", active="notifications", item=item)

    @app.post("/notifications/read")
    def notifications_read():
        guard = require_student()
        if guard:
            return guard
        notice_id = request.form.get("notice_id", "")
        items = [item for item in my_notices() if notice_id == "all" or item["id"] == notice_id]
        if not items:
            abort(404)
        db = get_db()
        with db:
            db.executemany(
                "INSERT OR IGNORE INTO notification_reads VALUES (?, ?, ?)",
                [(g.student["id"], item["id"], item["read_key"]) for item in items],
            )
        return redirect(url_for("notifications"), code=303)

    def _staff_metrics(db):
        all_reqs = db.execute("SELECT ready_at, decision FROM requests").fetchall()
        pending_total = sum((r["ready_at"] > g.epoch and r["decision"] not in ("returned", "rejected")) for r in all_reqs)
        closed_total = len(all_reqs) - pending_total
        unpaid_total = db.execute("SELECT COUNT(*) AS c FROM charges WHERE status = 'unpaid'").fetchone()["c"]
        overrides_total = db.execute("SELECT COUNT(*) AS c FROM room_overrides").fetchone()["c"]
        gaps_total = db.execute("SELECT COUNT(*) AS c FROM assistant_gaps").fetchone()["c"]
        return {
            "pending_total": pending_total,
            "closed_total": closed_total,
            "unpaid_total": unpaid_total,
            "overrides_total": overrides_total,
            "gaps_total": gaps_total,
        }

    @app.get("/staff")
    def staff_dashboard():
        require_staff()
        db = get_db()
        rows = db.execute(
            """SELECT requests.*, students.name AS student_name, students.student_group AS student_group,
                      students.faculty AS student_faculty
               FROM requests JOIN students ON students.id = requests.student_id
               ORDER BY (requests.ready_at > ? AND requests.decision NOT IN ('returned', 'rejected')) DESC,
                        requests.created_at DESC LIMIT 40""",
            (g.epoch,),
        ).fetchall()
        queue = []
        for row in rows:
            entry = request_summary(row)
            entry["student_name"] = row["student_name"]
            entry["student_group"] = row["student_group"]
            entry["student_faculty"] = row["student_faculty"]
            queue.append(entry)
        slots = db.execute(
            """SELECT office_slots.*, students.name AS student_name, students.student_group AS student_group
               FROM office_slots JOIN students ON students.id = office_slots.student_id
               ORDER BY visit_date ASC, slot_time ASC LIMIT 12"""
        ).fetchall()
        quick_slots = []
        for grp in GROUPS:
            for weekday, start, end, _, subj_title, _, base_room, _ in TIMETABLE[grp][:4]:
                quick_slots.append({
                    "value": f"{grp}|{weekday}|{start}",
                    "label": f"{grp} · {SHORT_DAY[weekday]} {start} · {subj_title} ({base_room})",
                })
        stats = _staff_metrics(db)
        return render_template(
            "staff.html",
            active="staff_dashboard",
            tab="queue",
            queue=queue,
            office_appointments=slots,
            quick_slots=quick_slots,
            teaching_rooms=TEACHING_ROOMS,
            presets=STAFF_PRESETS,
            groups=GROUPS,
            **stats,
        )

    @app.get("/staff/schedule")
    def staff_schedule():
        require_staff()
        db = get_db()
        selected_group = request.args.get("group", GROUPS[0])
        if selected_group not in GROUPS:
            selected_group = GROUPS[0]
        overrides = db.execute(
            "SELECT * FROM room_overrides ORDER BY updated_at DESC"
        ).fetchall()
        override_map = {
            (r["student_group"], r["weekday"], r["start_time"]): dict(r)
            for r in overrides
        }
        group_lessons = []
        for weekday, start, end, kind, title, teacher, base_room, prev in TIMETABLE[selected_group]:
            ov = override_map.get((selected_group, weekday, start))
            group_lessons.append({
                "weekday": weekday,
                "day_name": WEEKDAY[weekday],
                "start": start,
                "end": end,
                "kind": kind,
                "title": title,
                "teacher": teacher,
                "base_room": base_room,
                "active_room": ov["new_room"] if ov else base_room,
                "override_id": ov["id"] if ov else None,
            })
        stats = _staff_metrics(db)
        return render_template(
            "staff.html",
            active="staff_schedule",
            tab="schedule",
            selected_group=selected_group,
            group_lessons=group_lessons,
            overrides=overrides,
            teaching_rooms=TEACHING_ROOMS,
            groups=GROUPS,
            **stats,
        )

    @app.post("/staff/schedule/override")
    def staff_set_override():
        require_staff()
        slot_combo = request.form.get("slot_combo", "")
        if slot_combo and slot_combo.count("|") == 2:
            group, wk_raw, start_time = slot_combo.split("|", 2)
        else:
            group = request.form.get("student_group", "")
            wk_raw = request.form.get("weekday", "-1")
            start_time = request.form.get("start_time", "")
        try:
            weekday = int(wk_raw)
        except ValueError:
            abort(400)
        new_room = request.form.get("new_room", "")
        note = request.form.get("note", "").strip()[:200]
        if group not in GROUPS or new_room not in TEACHING_ROOMS:
            abort(400)
        matched = next(
            (row for row in TIMETABLE[group] if row[0] == weekday and row[1] == start_time),
            None,
        )
        if not matched:
            abort(400)
        _, _, _, _, subj_title, _, base_room, _ = matched
        db = get_db()
        with db:
            db.execute(
                """INSERT INTO room_overrides VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_group, weekday, start_time)
                   DO UPDATE SET new_room = excluded.new_room, note = excluded.note, updated_at = excluded.updated_at""",
                (secrets.token_hex(12), group, weekday, start_time, new_room, note, g.epoch),
            )
            notice_body = (
                f"{WEEKDAY[weekday]}, {start_time}: дисциплина «{subj_title}» перенесена из {base_room} в {new_room}."
                + (f" {note}" if note else "")
            )
            db.execute(
                "INSERT INTO staff_notices VALUES (?, ?, 'Расписание', ?, ?, ?)",
                (secrets.token_hex(12), group, f"Перенос аудитории: {subj_title}", notice_body, g.epoch),
            )
        flash(f"Перенос для группы {group} сохранён ({base_room} → {new_room}) и отправлен в ленту потока.")
        if request.form.get("origin") == "dashboard":
            return redirect(url_for("staff_dashboard"), code=303)
        return redirect(url_for("staff_schedule", group=group), code=303)

    @app.post("/staff/schedule/override/<override_id>/clear")
    def staff_clear_override(override_id):
        require_staff()
        db = get_db()
        row = db.execute("SELECT student_group FROM room_overrides WHERE id = ?", (override_id,)).fetchone()
        if not row:
            abort(404)
        with db:
            db.execute("DELETE FROM room_overrides WHERE id = ?", (override_id,))
        flash("Исходная аудитория в расписании восстановлена.")
        return redirect(url_for("staff_schedule", group=row["student_group"]), code=303)

    @app.get("/staff/students")
    def staff_students():
        require_staff()
        db = get_db()
        student_rows = db.execute(
            "SELECT * FROM students WHERE role = 'student' ORDER BY student_group ASC, name ASC"
        ).fetchall()
        roster = []
        for srow in student_rows:
            sid = srow["id"]
            snap = rating_snapshot(sid)
            charges = owned_charges(sid)
            unpaid_sum = sum(c["amount"] for c in charges if c["status"] == "unpaid")
            open_reqs = db.execute(
                "SELECT COUNT(*) AS c FROM requests WHERE student_id = ? AND ready_at > ? AND decision NOT IN ('returned', 'rejected')",
                (sid, g.epoch),
            ).fetchone()["c"]
            roster.append({
                "id": sid,
                "name": srow["name"],
                "full_name": srow["full_name"],
                "email": srow["email"],
                "group": srow["student_group"],
                "course": srow["course"],
                "faculty": srow["faculty"],
                "program": srow["program"],
                "card_number": STUDENT_PROFILES[sid]["card_number"],
                "dorm": DORM_INFO[sid],
                "scholar": SCHOLARSHIPS[sid],
                "snap": snap,
                "unpaid_sum": unpaid_sum,
                "open_reqs": open_reqs,
            })
        stats = _staff_metrics(db)
        return render_template(
            "staff.html",
            active="staff_students",
            tab="students",
            roster=roster,
            groups=GROUPS,
            **stats,
        )

    @app.get("/staff/notices")
    def staff_notices():
        require_staff()
        db = get_db()
        published = db.execute(
            "SELECT * FROM staff_notices ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        prefill_title = request.args.get("title", "").strip()[:120]
        prefill_body = request.args.get("body", "").strip()[:400]
        stats = _staff_metrics(db)
        return render_template(
            "staff.html",
            active="staff_notices",
            tab="notices",
            published=published,
            prefill_title=prefill_title,
            prefill_body=prefill_body,
            groups=GROUPS,
            **stats,
        )

    @app.get("/staff/assistant")
    def staff_assistant():
        require_staff()
        db = get_db()
        gaps = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM assistant_gaps ORDER BY hits DESC, updated_at DESC LIMIT 30"
            ).fetchall()
        ]
        stats = _staff_metrics(db)
        return render_template(
            "staff.html",
            active="staff_assistant",
            tab="assistant",
            gaps=gaps,
            groups=GROUPS,
            **stats,
        )

    @app.post("/staff/assistant/<gap_id>/dismiss")
    def staff_dismiss_gap(gap_id):
        require_staff()
        db = get_db()
        with db:
            cur = db.execute("DELETE FROM assistant_gaps WHERE id = ?", (gap_id,))
        if cur.rowcount == 0:
            abort(404)
        flash("Тема отмечена закрытой и убрана из списка пробелов.")
        return redirect(url_for("staff_assistant"), code=303)

    @app.post("/staff/requests/<request_id>/resolve")
    def staff_resolve_request(request_id):
        require_staff()
        db = get_db()
        row = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            abort(404)
        decision = request.form.get("decision", "approved")
        if decision not in {"approved", "returned", "rejected"}:
            abort(400)
        staff_note = request.form.get("staff_note", "").strip()[:400]
        if decision == "returned" and not staff_note:
            staff_note = "Возвращено на доработку: уточните реквизиты подтверждающего документа."
        elif decision == "rejected" and not staff_note:
            staff_note = "Отклонено учебным офисом: отсутствуют основания по академическому регламенту."
        elif row["kind"] in PETITION_TYPES and not staff_note:
            staff_note = "Согласовано учебным офисом. Изменения отражены в карточке студента."
        with db:
            db.execute(
                "UPDATE requests SET ready_at = ?, staff_note = ?, decision = ? WHERE id = ?",
                (min(row["ready_at"], g.epoch), staff_note, decision, request_id),
            )
            db.execute(
                "DELETE FROM notification_reads WHERE student_id = ? AND notice_id = ?",
                (row["student_id"], "request-" + request_id),
            )
        msg_map = {
            "approved": "Заявка согласована, уведомление отправлено студенту.",
            "returned": "Обращение возвращено студенту на доработку.",
            "rejected": "Обращение отклонено, решение направлено студенту.",
        }
        flash(msg_map[decision])
        return redirect(url_for("staff_dashboard"), code=303)

    @app.post("/staff/announcements")
    def staff_announce():
        require_staff()
        target_group = request.form.get("target_group", "")
        kind = request.form.get("kind", "Деканат")
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if target_group not in (*GROUPS, "all") or kind not in {"Расписание", "Деканат", "Сессия"}:
            abort(400)
        if len(title) < 4 or len(title) > 120 or len(body) < 8 or len(body) > 400:
            flash("Заполните заголовок и текст сообщения.")
            return redirect(url_for("staff_notices"), code=303)
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO staff_notices VALUES (?, ?, ?, ?, ?, ?)",
                (secrets.token_hex(12), target_group, kind, title, body, g.epoch),
            )
        flash("Объявление опубликовано в ленте студентов.")
        return redirect(url_for("staff_notices"), code=303)

    @app.post("/staff/announcements/<notice_id>/delete")
    def staff_delete_notice(notice_id):
        require_staff()
        db = get_db()
        with db:
            cur = db.execute("DELETE FROM staff_notices WHERE id = ?", (notice_id,))
        if cur.rowcount == 0:
            abort(404)
        flash("Объявление снято с публикации.")
        return redirect(url_for("staff_notices"), code=303)

    @app.get("/profile")
    def profile():
        snap = None if is_staff() else rating_snapshot()
        dorm = None if is_staff() else DORM_INFO[g.student["id"]]
        return render_template("profile.html", active="profile", snap=snap, dorm=dorm)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def error_page(error):
        text = {
            400: ("Проверьте данные", "Откройте страницу заново и повторите отправку формы."),
            403: ("Доступ ограничен", "Эта запись или раздел недоступны для текущего профиля."),
            404: ("Страница или запись недоступна", "Проверьте адрес: ссылка могла устареть или принадлежит другому аккаунту."),
            413: ("Слишком большой запрос", "Сократите объём передаваемых данных и отправьте форму снова."),
            429: ("Слишком частые запросы", "Превышен лимит обращений. Подождите несколько минут и повторите попытку."),
        }
        title, message = text.get(error.code, ("Ошибка запроса", "Вернитесь в личный кабинет."))
        return render_template("error.html", title=title, message=message, status=error.code), error.code

    return app
