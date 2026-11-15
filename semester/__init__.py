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

NAV = (
    ("home", "home", "Главная"),
    ("schedule", "calendar", "Расписание"),
    ("grades", "chart", "Успеваемость"),
    ("requests_list", "file", "Заявки"),
    ("notifications", "bell", "Уведомления"),
)

DELIVERY = {"digital": "Электронно", "office": "В деканате"}
READY_DELAY = 120
LOCAL_HASHES = (
    "scrypt:32768:8:1$RUE0Sr0umX59HRbk$609960ab64f10a3e222acd29038670c30ef2c1161fc1ad58842d0fdf0ce86958a0d368f21b5914a15a5b220476b959248d5b18487c5f8385375c0c4c0df180f1",
    "scrypt:32768:8:1$OEaczuaFNx7CUTm4$c6b8551ddc54688de0d093f6f9e5ccfbc3f8d10f95c2e421f50e50a41344ecd7dab94892c811d9765a3740be7187a2a556080737409875c5970cd78c1edee8ba",
)
LOCAL_DEMO_ACCOUNTS = (
    {
        "name": "Валерия Маякова",
        "group": "МП-24-1",
        "track": "Маркетинг и продукт · 2 курс",
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
        DEMO_PASSWORDS=(os.environ.get("SEMESTER_LERA_PASSWORD"), os.environ.get("SEMESTER_MISHA_PASSWORD")),
    )
    app.config.update(config or {})
    if not app.config["SECRET_KEY"] or (not local and len(app.config["SECRET_KEY"]) < 32):
        raise RuntimeError("Set SEMESTER_SECRET to a random string of at least 32 characters.")
    passwords = app.config["DEMO_PASSWORDS"]
    if not local and (not all(passwords) or min(map(len, passwords)) < 12 or passwords[0] == passwords[1]):
        raise RuntimeError("Set two distinct demo passwords of at least 12 characters.")
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    password_hashes = tuple(
        generate_password_hash(password) if password else fallback
        for password, fallback in zip(passwords, LOCAL_HASHES, strict=True)
    )
    is_local_demo = bool(local and not any(passwords))
    initialize(app.config["DATABASE"], password_hashes)
    app.teardown_appcontext(close_db)

    @app.cli.command("rotate-demo-passwords")
    def rotate_demo_passwords():
        """Apply the demo passwords from the environment and revoke active sessions."""
        if not all(passwords):
            raise ClickException("Set both demo passwords before rotating.")
        db = get_db()
        with db:
            db.executemany(
                "UPDATE students SET password_hash = ? WHERE id = ?",
                zip(password_hashes, (1, 2), strict=True),
            )
            db.execute("DELETE FROM login_sessions")

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
            if item["kind"] in {"Деканат", "Заявки"}:
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
        group = g.student["student_group"]
        monday = week_start(g.stamp.date())
        entries = [
            {"cat": "Навигация", "title": "Главная · Учебный день", "meta": "Сводка пар, переносов и заявок", "url": url_for("home"), "icon": "home"},
            {"cat": "Навигация", "title": "Расписание на неделю", "meta": f"Сетка пар группы {group}", "url": url_for("schedule", view="week"), "icon": "calendar"},
            {"cat": "Навигация", "title": "Экспорт расписания (.ics)", "meta": "Добавить пары недели в календарь", "url": url_for("schedule_ics"), "icon": "download"},
            {"cat": "Навигация", "title": "Успеваемость и 100-балльный рейтинг", "meta": "Оценки, зачётные единицы и даты сессии", "url": url_for("grades"), "icon": "chart"},
            {"cat": "Навигация", "title": "Профиль и пропуск Семестр ID", "meta": STUDENT_PROFILES[g.student["id"]]["card_number"], "url": url_for("profile"), "icon": "id-badge"},
        ]
        for kind_key, (title, desc, glyph) in REQUEST_TYPES.items():
            entries.append({
                "cat": "Деканат",
                "title": f"Заказать: {title}",
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
            room_note = f"{room} (перенос из {previous})" if previous else room
            entries.append({
                "cat": "Занятия",
                "title": f"{title} · {WEEKDAY[weekday][:2]} {start}",
                "meta": f"{kind} · {room_note} · {teacher}",
                "url": f"{url_for('schedule', date=lesson_day.isoformat())}#{lesson_id}",
                "icon": "pin",
            })
        return entries

    @app.context_processor
    def common():
        signed = bool(g.get("student"))
        unread_count = sum(item["unread"] for item in my_notices()) if signed else 0
        student_meta = STUDENT_PROFILES[g.student["id"]] if signed else None
        pass_qr = (
            qr_svg_path(f"SEMESTR-PASS:{g.student['id']}:{student_meta['card_number']}")
            if signed else ""
        )
        return dict(
            nav=NAV,
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
        )

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
            recent=owned_requests(2),
            snap=snap,
        )

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
                """INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(student_id, nonce) DO NOTHING""",
                (
                    secrets.token_hex(16),
                    g.student["id"],
                    kind,
                    selected,
                    comment,
                    g.epoch,
                    g.epoch + READY_DELAY,
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
        return render_template("request_detail.html", active="requests_list", item=owned_request(request_id))

    @app.get("/requests/<request_id>/document")
    def request_document(request_id):
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
            db.executemany(
                "INSERT OR IGNORE INTO notification_reads VALUES (?, ?, ?)",
                [(g.student["id"], item["id"], item["read_key"]) for item in items],
            )
        return redirect(url_for("notifications"), code=303)

    @app.get("/profile")
    def profile():
        snap = rating_snapshot()
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
