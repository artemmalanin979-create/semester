import os
import re
import secrets
import time
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from .db import close_db, get_db, initialize, session_hash
from .demo import (
    REQUEST_TYPES, SHORT_DAY, WEEKDAY, academic_results, fmt_date, fmt_dt, fmt_request_day,
    lessons_on, next_lesson, notices, now, week_start,
)

NAV = (
    ("home", "home", "Главная"),
    ("schedule", "calendar", "Расписание"),
    ("grades", "chart", "Успеваемость"),
    ("requests_list", "file", "Заявки"),
    ("notifications", "bell", "Уведомления"),
)

DELIVERY = {"digital": "Электронно", "office": "В деканате"}
READY_DELAY = 120
SESSION_TTL = 8 * 60 * 60
TOKEN = re.compile(r"[0-9a-f]{32}")


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    local = os.environ.get("SEMESTER_ENV", "local") == "local"
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SEMESTER_SECRET") or (secrets.token_hex(32) if local else None),
        DATABASE=os.environ.get("SEMESTER_DB", str(Path(app.instance_path) / "semester.sqlite3")),
        SESSION_COOKIE_SECURE=not local,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=32 * 1024,
        TRUST_PROXY=os.environ.get("SEMESTER_TRUST_PROXY") == "1",
        DEMO_PASSWORDS=(os.environ.get("SEMESTER_LERA_PASSWORD") or ("Semestr-Lera-26" if local else None),
                        os.environ.get("SEMESTER_MISHA_PASSWORD") or ("Semestr-Misha-26" if local else None)),
    )
    app.config.update(config or {})
    if not app.config["SECRET_KEY"] or (not local and len(app.config["SECRET_KEY"]) < 32):
        raise RuntimeError("Set SEMESTER_SECRET to a random string of at least 32 characters.")
    if not all(app.config["DEMO_PASSWORDS"]):
        raise RuntimeError("Set SEMESTER_LERA_PASSWORD and SEMESTER_MISHA_PASSWORD.")
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    initialize(app.config["DATABASE"], app.config["DEMO_PASSWORDS"])
    app.teardown_appcontext(close_db)
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24))

    def csrf():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

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
        item["status"] = "Готово" if item["ready"] else "В обработке"
        item["remaining"] = max(0, item["ready_at"] - g.epoch)
        return item

    def owned_requests(limit):
        rows = get_db().execute(
            "SELECT * FROM requests WHERE student_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (g.student["id"], limit),
        ).fetchall()
        return [request_summary(row) for row in rows]

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
        items = notices(g.student, g.stamp)
        ready = get_db().execute(
            """SELECT * FROM requests WHERE student_id = ? AND ready_at <= ?
               ORDER BY ready_at DESC LIMIT 24""",
            (g.student["id"], g.epoch),
        ).fetchall()
        for row in ready:
            endpoint = "request_detail"
            action = "К заявке"
            if row["kind"] == "appeal":
                title = "Ответ на заявление готов"
                message = "Ответ деканата доступен на странице заявки."
            elif row["delivery"] == "office":
                title = REQUEST_TYPES[row["kind"]][0] + " готова"
                message = "Документ можно забрать в деканате. На странице заявки есть адрес и часы работы."
            else:
                title = REQUEST_TYPES[row["kind"]][0] + " готова"
                message = "Электронный документ доступен в кабинете."
                endpoint = "request_document"
                action = "Открыть документ"
            items.append({
                "id": "request-" + row["id"], "kind": "Заявки", "title": title,
                "body": message, "date": fmt_request_day(row["ready_at"]), "icon": "file",
                "link": url_for(endpoint, request_id=row["id"]), "action": action,
            })
        seen = {(row["notice_id"], row["read_key"]) for row in get_db().execute(
            "SELECT notice_id, read_key FROM notification_reads WHERE student_id = ?", (g.student["id"],)
        )}
        for item in items:
            if item["kind"] in {"Деканат", "Заявки"}:
                item["read_key"] = "1"
            else:
                item["read_key"] = item["date"].isoformat()
            item["unread"] = (item["id"], item["read_key"]) not in seen
        g.notices = items
        return items

    @app.context_processor
    def common():
        unread_count = sum(item["unread"] for item in my_notices()) if g.get("student") else 0
        return dict(nav=NAV, csrf=csrf, fmt_date=fmt_date, fmt_dt=fmt_dt, weekdays=WEEKDAY,
                    request_types=REQUEST_TYPES, delivery=DELIVERY, unread_count=unread_count)

    @app.get("/healthz")
    def health():
        get_db().execute("SELECT 1")
        return {"status": "ok"}

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.student:
            return redirect(url_for("home"), code=303)
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
                   RETURNING count""", (request.remote_addr or "unknown", bucket),
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
            db.execute("INSERT INTO login_sessions VALUES (?, ?, ?)",
                       (session_hash(key), student["id"], g.epoch + SESSION_TTL))
        session.clear()
        session["key"] = key
        return redirect(url_for("home"), code=303)

    @app.post("/logout")
    def logout():
        db = get_db()
        with db:
            db.execute("DELETE FROM login_sessions WHERE key = ?", (session_hash(session["key"]),))
        session.clear()
        return redirect(url_for("login"), code=303)

    @app.get("/")
    def home():
        group = g.student["student_group"]
        day = g.stamp.date()
        today = lessons_on(group, day)
        upcoming = next_lesson(group, g.stamp)
        agenda = today or (lessons_on(group, upcoming["day"]) if upcoming else [])
        return render_template("home.html", active="home", day=day, today=today, agenda=agenda,
                               upcoming=upcoming, items=my_notices(), recent=owned_requests(2))

    @app.get("/schedule")
    def schedule():
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
        start = week_start(selected)
        week = [start + timedelta(days=i) for i in range(7)]
        days = [selected] if view == "day" else week
        pairs = [(day, lessons_on(g.student["student_group"], day)) for day in days]
        return render_template("schedule.html", active="schedule", selected=selected, today=today,
                               view=view, week=week, week_start=start, days=pairs, short_day=SHORT_DAY,
                               prev=max(today - timedelta(days=120), selected - timedelta(days=7)),
                               next=min(today + timedelta(days=120), selected + timedelta(days=7)))

    @app.get("/grades")
    def grades():
        records = academic_results(g.student["id"], g.stamp.date())
        completed = sum(bool(row["result"]) for row in records)
        marks = [int(row["result"]) for row in records if row["result"].isdigit()]
        average = f"{sum(marks) / len(marks):.1f}".replace(".", ",") if marks else "—"
        upcoming = sorted((row for row in records if not row["result"]), key=lambda row: row["date"])
        return render_template("grades.html", active="grades", records=records, completed=completed,
                               average=average, upcoming=upcoming)

    @app.get("/requests")
    def requests_list():
        try:
            page = max(1, min(int(request.args.get("page", "1")), 100_000))
        except ValueError:
            abort(400)
        rows = get_db().execute(
            """SELECT * FROM requests WHERE student_id = ?
               ORDER BY created_at DESC, rowid DESC LIMIT 13 OFFSET ?""",
            (g.student["id"], (page - 1) * 12),
        ).fetchall()
        return render_template("requests.html", active="requests_list", page=page,
                               more=len(rows) > 12, items=[request_summary(row) for row in rows[:12]])

    @app.route("/requests/new/<kind>", methods=["GET", "POST"])
    def request_new(kind):
        if kind not in REQUEST_TYPES:
            abort(404)
        if request.method == "GET":
            return render_template("request_new.html", active="requests_list", kind=kind,
                                   nonce=secrets.token_hex(16), selected="digital", comment="", error=None)
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
            return render_template("request_new.html", active="requests_list", kind=kind, nonce=nonce,
                                   selected=selected, comment=comment[:500], error=error), 422
        db = get_db()
        with db:
            db.execute(
                """INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, nonce) DO NOTHING""",
                (secrets.token_hex(16), g.student["id"], kind, selected, comment, g.epoch,
                 g.epoch + READY_DELAY, nonce),
            )
            created = db.execute("SELECT id FROM requests WHERE student_id = ? AND nonce = ?",
                                 (g.student["id"], nonce)).fetchone()
        flash("Заявка сохранена.")
        return redirect(url_for("request_detail", request_id=created["id"]), code=303)

    @app.get("/requests/<request_id>")
    def request_detail(request_id):
        return render_template("request_detail.html", active="requests_list", item=owned_request(request_id))

    @app.get("/requests/<request_id>/document")
    def request_document(request_id):
        item = owned_request(request_id)
        if not item["ready"] or item["delivery"] != "digital" or item["kind"] == "appeal":
            abort(404)
        records = academic_results(g.student["id"], g.stamp.date()) if item["kind"] == "grades" else []
        return render_template("document.html", active="requests_list", item=item, records=records)

    @app.get("/notifications")
    def notifications():
        return render_template("notifications.html", active="notifications", items=my_notices())

    @app.get("/notifications/<notice_id>")
    def notification_detail(notice_id):
        item = next((item for item in my_notices() if item["id"] == notice_id), None)
        if not item:
            abort(404)
        return render_template("notification_detail.html", active="notifications", item=item)

    @app.post("/notifications/read")
    def notifications_read():
        notice_id = request.form.get("notice_id", "")
        items = [item for item in my_notices() if notice_id == "all" or item["id"] == notice_id]
        if not items:
            abort(404)
        db = get_db()
        with db:
            db.executemany("INSERT OR IGNORE INTO notification_reads VALUES (?, ?, ?)",
                           [(g.student["id"], item["id"], item["read_key"]) for item in items])
        return redirect(url_for("notifications"), code=303)

    @app.get("/profile")
    def profile():
        return render_template("profile.html", active="profile")

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
