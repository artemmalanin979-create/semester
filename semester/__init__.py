import os
import re
import secrets
import time
from datetime import date, timedelta
from pathlib import Path

from click import ClickException
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .db import close_db, get_db, initialize, session_hash
from .demo import (
    GROUP_SLOTS,
    REQUEST_TYPES,
    SHORT_DAY,
    STUDENT_PROFILES,
    TIMETABLE,
    WEEKDAY,
    academic_results,
    academic_week_number,
    build_week_ics,
    day_gaps,
    fmt_date,
    fmt_dt,
    lessons_on,
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
    ("requests_list", "file", "Заявки"),
    ("notifications", "bell", "Уведомления"),
)

STAFF_NAV = (
    ("staff_dashboard", "layers", "Очередь заявок"),
    ("profile", "user", "Профиль"),
)

DELIVERY = {"digital": "Электронно", "office": "В деканате"}
GROUPS = ("МП-24-1", "МО-23-2")
READY_DELAY = 120
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
        if request.endpoint and request.endpoint not in {"login", "health"} and not g.student:
            return redirect(url_for("login"), code=303)
        return None

    @app.after_request
    def secure_response(response):
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.is_secure and app.config["SESSION_COOKIE_SECURE"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    def request_summary(row):
        item = dict(row)
        item["title"], _, item["icon"] = REQUEST_TYPES[item["kind"]]
        item["ready"] = g.epoch >= item["ready_at"]
        item["status"] = "Готово" if item["ready"] else "В работе"
        item["remaining"] = max(0, item["ready_at"] - g.epoch)
        return item

    def owned_requests(limit):
        rows = get_db().execute(
            "SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (g.student["id"], limit),
        ).fetchall()
        return [request_summary(row) for row in rows]

    def has_ready_office_doc():
        row = get_db().execute(
            "SELECT 1 FROM requests WHERE student_id = ? AND delivery = 'office' AND ready_at <= ? LIMIT 1",
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
        items = notices(g.student, g.stamp)
        published = get_db().execute(
            """SELECT * FROM staff_notices
               WHERE target_group IN (?, 'all')
               ORDER BY created_at DESC LIMIT 12""",
            (g.student["student_group"],),
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
        ready = get_db().execute(
            """SELECT * FROM requests WHERE student_id = ? AND ready_at <= ?
               ORDER BY ready_at DESC LIMIT 24""",
            (g.student["id"], g.epoch),
        ).fetchall()
        for row in ready:
            endpoint = "request_detail"
            action = "К заявке"
            if row["kind"] == "appeal":
                title = "Ответ деканата по заявлению"
                message = row["staff_note"] or "Ответ методиста доступен на странице обращения."
            elif row["delivery"] == "office":
                title = REQUEST_TYPES[row["kind"]][0] + " готова"
                message = "Оригинал можно получить в окне А–116 по будням с 10:00 до 17:00."
            else:
                title = REQUEST_TYPES[row["kind"]][0] + " готова"
                message = "Электронный документ доступен в кабинете."
                endpoint = "request_document"
                action = "Открыть документ"
            items.append({
                "id": "request-" + row["id"],
                "kind": "Заявки",
                "title": title,
                "body": message,
                "date": timestamp_day(row["ready_at"]),
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
            if item["kind"] in {"Деканат", "Заявки"} or item["id"].startswith("staff-"):
                item["read_key"] = "1"
            else:
                item["read_key"] = item["date"].isoformat()
            item["unread"] = (item["id"], item["read_key"]) not in seen
        g.notices = items
        return items

    def rating_snapshot():
        records = academic_results(g.student["id"], g.stamp.date())
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
                {
                    "cat": "Деканат",
                    "title": "Очередь заявок студентов",
                    "meta": "Рассмотрение справок и обращений",
                    "url": url_for("staff_dashboard"),
                    "icon": "layers",
                },
                {
                    "cat": "Деканат",
                    "title": "Новое объявление группе",
                    "meta": "Уведомление о переносе или сроках",
                    "url": url_for("staff_dashboard") + "#announce-box",
                    "icon": "bell",
                },
                {
                    "cat": "Профиль",
                    "title": "Карточка сотрудника",
                    "meta": STUDENT_PROFILES[g.student["id"]]["card_number"],
                    "url": url_for("profile"),
                    "icon": "user",
                },
            ]
        group = g.student["student_group"]
        monday = week_start(g.stamp.date())
        entries = [
            {"cat": "Разделы", "title": "Учебный день", "meta": "Ближайшее занятие, изменения и заявки", "url": url_for("home"), "icon": "home"},
            {"cat": "Разделы", "title": "Расписание недели", "meta": f"Группа {group}", "url": url_for("schedule", view="week"), "icon": "calendar"},
            {"cat": "Разделы", "title": "Экспорт календаря (.ics)", "meta": "Файл расписания для календаря", "url": url_for("schedule_ics"), "icon": "download"},
            {"cat": "Разделы", "title": "Успеваемость", "meta": "Баллы, ЗЕТ и расписание сессии", "url": url_for("grades"), "icon": "chart"},
            {"cat": "Разделы", "title": "Профиль и пропуск", "meta": STUDENT_PROFILES[g.student["id"]]["card_number"], "url": url_for("profile"), "icon": "id-badge"},
        ]
        for kind_key, (title, desc, glyph) in REQUEST_TYPES.items():
            entries.append({
                "cat": "Заявки",
                "title": title,
                "meta": desc,
                "url": url_for("request_new", kind=kind_key),
                "icon": glyph,
            })
        seen_lessons = set()
        for weekday, start, _, kind, title, teacher, room, previous in TIMETABLE[group]:
            sig = (weekday, start, title)
            if sig in seen_lessons:
                continue
            seen_lessons.add(sig)
            lesson_day = monday + timedelta(days=weekday)
            lesson_id = f"lesson-{lesson_day.isoformat()}-{start.replace(':', '')}"
            room_note = f"{room} (из {previous})" if previous else room
            entries.append({
                "cat": "Пары",
                "title": f"{title} · {SHORT_DAY[weekday]} {start}",
                "meta": f"{kind} · {room_note} · {teacher}",
                "url": f"{url_for('schedule', date=lesson_day.isoformat())}#{lesson_id}",
                "icon": "pin",
            })
        return entries

    @app.context_processor
    def common():
        signed = bool(g.get("student"))
        staff = is_staff()
        unread_count = sum(item["unread"] for item in my_notices()) if (signed and not staff) else 0
        pending_staff = 0
        if signed and staff:
            pending_staff = get_db().execute(
                "SELECT COUNT(*) AS c FROM requests WHERE ready_at > ?",
                (g.epoch,),
            ).fetchone()["c"]
        student_meta = STUDENT_PROFILES[g.student["id"]] if signed else None
        pass_qr = (
            qr_svg_path(f"SEMESTR-PASS:{g.student['id']}:{student_meta['card_number']}")
            if signed else ""
        )
        cookie_theme = request.cookies.get("semester_theme", "")
        theme_pref = cookie_theme if cookie_theme in {"light", "dark"} else ""
        return dict(
            nav=STAFF_NAV if staff else STUDENT_NAV,
            is_staff=staff,
            pending_staff=pending_staff,
            home_endpoint="staff_dashboard" if staff else "home",
            csrf=csrf,
            fmt_date=fmt_date,
            fmt_dt=fmt_dt,
            weekdays=WEEKDAY,
            request_types=REQUEST_TYPES,
            delivery=DELIVERY,
            unread_count=unread_count,
            is_local_demo=is_local_demo,
            demo_accounts=LOCAL_DEMO_ACCOUNTS if is_local_demo else (),
            student_meta=student_meta,
            pass_qr=pass_qr,
            week_num=academic_week_number(g.stamp.date()) if signed else 1,
            search_index=build_search_index() if signed else (),
            theme_pref=theme_pref,
        )

    @app.get("/healthz")
    def health():
        get_db().execute("SELECT 1")
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.student:
            return redirect(url_for("staff_dashboard" if is_staff() else "home"), code=303)
        if request.method == "GET":
            return render_template("login.html", error=None, email="")
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        db = get_db()
        bucket = int(time.time()) // 60
        with db:
            db.execute("DELETE FROM login_attempts WHERE bucket < ?", (bucket - 2,))
            attempt = db.execute(
                """INSERT INTO login_attempts VALUES (?, ?, 1)
                   ON CONFLICT(source, bucket) DO UPDATE SET count = count + 1
                   RETURNING count""",
                (request.remote_addr or "unknown", bucket),
            ).fetchone()["count"]
        if attempt > 30:
            return render_template("login.html", error="Подождите минуту и попробуйте снова.", email=email), 429
        student = db.execute("SELECT * FROM students WHERE email = ?", (email,)).fetchone()
        expected_hash = student["password_hash"] if student else dummy_hash
        if len(password) > 256 or not check_password_hash(expected_hash, password) or not student:
            return render_template("login.html", error="Проверьте почту и пароль.", email=email), 401
        key = secrets.token_hex(32)
        with db:
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
        group = g.student["student_group"]
        day = g.stamp.date()
        today = lessons_on(group, day)
        upcoming = next_lesson(group, g.stamp)
        agenda = today or (lessons_on(group, upcoming["day"]) if upcoming else [])
        gaps = day_gaps(agenda, has_ready_office_doc())
        snap = rating_snapshot()
        return render_template(
            "home.html",
            active="home",
            day=day,
            today=today,
            agenda=agenda,
            gaps=gaps,
            upcoming=upcoming,
            in_class=bool(
                upcoming and upcoming["day"] == day and upcoming["start"] <= g.stamp.strftime("%H:%M")
            ),
            items=my_notices(),
            recent=owned_requests(3),
            snap=snap,
        )

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
        start = week_start(selected)
        week = [start + timedelta(days=i) for i in range(7)]
        week_lessons = {d: lessons_on(group, d) for d in week}
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
        payload = build_week_ics(g.student, week_start(selected))
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
        rows = get_db().execute(
            """SELECT * FROM requests WHERE student_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 13 OFFSET ?""",
            (g.student["id"], (page - 1) * 12),
        ).fetchall()
        return render_template(
            "requests.html",
            active="requests_list",
            page=page,
            more=len(rows) > 12,
            items=[request_summary(row) for row in rows[:12]],
        )

    @app.route("/requests/new/<kind>", methods=["GET", "POST"])
    def request_new(kind):
        guard = require_student()
        if guard:
            return guard
        if kind not in REQUEST_TYPES:
            abort(404)
        if request.method == "GET":
            return render_template(
                "request_new.html",
                active="requests_list",
                kind=kind,
                nonce=secrets.token_hex(16),
                selected="digital",
                comment="",
                error=None,
            )
        nonce = request.form.get("nonce", "")
        if not TOKEN.fullmatch(nonce):
            abort(400)
        selected = "digital" if kind == "appeal" else request.form.get("delivery")
        comment = request.form.get("comment", "").strip()
        error = None
        if selected not in DELIVERY:
            error = "Укажите способ получения."
        elif len(comment) > 500:
            error = "Сократите текст до 500 знаков."
        elif kind == "appeal" and len(comment) < 10:
            error = "Опишите вопрос подробнее, минимум 10 знаков."
        if error:
            return (
                render_template(
                    "request_new.html",
                    active="requests_list",
                    kind=kind,
                    nonce=nonce,
                    selected=selected,
                    comment=comment[:500],
                    error=error,
                ),
                422,
            )
        db = get_db()
        with db:
            db.execute(
                """INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, '')
                   ON CONFLICT(student_id, nonce) DO NOTHING""",
                (
                    secrets.token_hex(16),
                    g.student["id"],
                    kind,
                    selected,
                    comment,
                    g.epoch,
                    g.epoch + (1800 if kind == "appeal" else READY_DELAY),
                    nonce,
                ),
            )
            created = db.execute(
                "SELECT id FROM requests WHERE student_id = ? AND nonce = ?",
                (g.student["id"], nonce),
            ).fetchone()
        flash("Заявка сохранена.")
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
        if not item["ready"] or item["delivery"] != "digital" or item["kind"] == "appeal":
            abort(404)
        records = academic_results(g.student["id"], g.stamp.date()) if item["kind"] == "grades" else []
        doc_qr = qr_svg_path(f"SEMESTR-DOC:{item['id']}:{g.student['id']}")
        verify_code = f"SM-{item['id'][:4].upper()}-{item['id'][4:8].upper()}"
        return render_template(
            "document.html",
            active="requests_list",
            item=item,
            records=records,
            doc_qr=doc_qr,
            verify_code=verify_code,
        )

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

    @app.get("/staff")
    def staff_dashboard():
        require_staff()
        db = get_db()
        rows = db.execute(
            """SELECT requests.*, students.name AS student_name, students.student_group AS student_group,
                      students.faculty AS student_faculty
               FROM requests JOIN students ON students.id = requests.student_id
               ORDER BY (requests.ready_at > ?) DESC, requests.created_at DESC LIMIT 30""",
            (g.epoch,),
        ).fetchall()
        queue = []
        for row in rows:
            entry = request_summary(row)
            entry["student_name"] = row["student_name"]
            entry["student_group"] = row["student_group"]
            entry["student_faculty"] = row["student_faculty"]
            queue.append(entry)
        published = db.execute(
            "SELECT * FROM staff_notices ORDER BY created_at DESC LIMIT 8"
        ).fetchall()
        pending_total = sum(not item["ready"] for item in queue)
        ready_total = sum(item["ready"] for item in queue)
        return render_template(
            "staff.html",
            active="staff_dashboard",
            queue=queue,
            pending_total=pending_total,
            ready_total=ready_total,
            published=published,
            groups=GROUPS,
        )

    @app.post("/staff/requests/<request_id>/resolve")
    def staff_resolve_request(request_id):
        require_staff()
        db = get_db()
        row = db.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        if not row:
            abort(404)
        staff_note = request.form.get("staff_note", "").strip()[:400]
        if row["kind"] == "appeal" and not staff_note:
            staff_note = "Согласовано учебным офисом. Изменения отражены в карточке студента."
        with db:
            db.execute(
                "UPDATE requests SET ready_at = ?, staff_note = ? WHERE id = ?",
                (min(row["ready_at"], g.epoch), staff_note, request_id),
            )
            db.execute(
                "DELETE FROM notification_reads WHERE student_id = ? AND notice_id = ?",
                (row["student_id"], "request-" + request_id),
            )
        flash("Статус заявки обновлён, уведомление отправлено студенту.")
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
            return redirect(url_for("staff_dashboard"), code=303)
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO staff_notices VALUES (?, ?, ?, ?, ?, ?)",
                (secrets.token_hex(12), target_group, kind, title, body, g.epoch),
            )
        flash("Объявление опубликовано в ленте студентов.")
        return redirect(url_for("staff_dashboard"), code=303)

    @app.get("/profile")
    def profile():
        snap = None if is_staff() else rating_snapshot()
        return render_template("profile.html", active="profile", snap=snap)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        text = {
            400: ("Проверьте данные", "Откройте страницу снова и повторите действие."),
            404: ("Страница недоступна", "Проверьте адрес или вернитесь в кабинет."),
            413: ("Слишком большой запрос", "Сократите сообщение и отправьте его снова."),
        }
        title, message = text[error.code]
        return render_template("error.html", title=title, message=message, status=error.code), error.code

    return app
