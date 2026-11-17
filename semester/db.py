import secrets
import sqlite3
import time
from hashlib import sha256
from pathlib import Path

from flask import current_app, g
from .demo import INITIAL_CHARGES, STUDENTS, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL, full_name TEXT NOT NULL, faculty TEXT NOT NULL,
    program TEXT NOT NULL, course INTEGER NOT NULL, student_group TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_sessions (
    key TEXT PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS session_expiry ON login_sessions(expires_at);
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
    kind TEXT NOT NULL, delivery TEXT NOT NULL, comment TEXT NOT NULL,
    created_at INTEGER NOT NULL, ready_at INTEGER NOT NULL, nonce TEXT NOT NULL,
    staff_note TEXT NOT NULL DEFAULT '',
    decision TEXT NOT NULL DEFAULT 'approved',
    verify_token TEXT NOT NULL DEFAULT '',
    revoked_at INTEGER NOT NULL DEFAULT 0,
    UNIQUE(student_id, nonce)
);
CREATE INDEX IF NOT EXISTS requests_by_owner ON requests(student_id, created_at DESC);
CREATE INDEX IF NOT EXISTS requests_by_token ON requests(verify_token);
CREATE TABLE IF NOT EXISTS staff_notices (
    id TEXT PRIMARY KEY,
    target_group TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_reads (
    student_id INTEGER NOT NULL REFERENCES students(id), notice_id TEXT NOT NULL,
    read_key TEXT NOT NULL, PRIMARY KEY(student_id, notice_id, read_key)
);
CREATE TABLE IF NOT EXISTS charges (
    id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    contract_no TEXT NOT NULL,
    period_label TEXT NOT NULL,
    amount INTEGER NOT NULL,
    due_label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unpaid',
    paid_at INTEGER NOT NULL DEFAULT 0,
    payment_method TEXT NOT NULL DEFAULT '',
    receipt_code TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS charges_by_owner ON charges(student_id);
CREATE TABLE IF NOT EXISTS guest_passes (
    id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    guest_name TEXT NOT NULL,
    visit_date TEXT NOT NULL,
    location TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS room_bookings (
    id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    space_id TEXT NOT NULL,
    space_title TEXT NOT NULL,
    booking_date TEXT NOT NULL,
    slot_label TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    UNIQUE(space_id, booking_date, slot_label)
);
CREATE TABLE IF NOT EXISTS office_slots (
    id TEXT PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    visit_date TEXT NOT NULL,
    slot_time TEXT NOT NULL,
    topic TEXT NOT NULL,
    ticket_code TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(visit_date, slot_time)
);
CREATE TABLE IF NOT EXISTS room_overrides (
    id TEXT PRIMARY KEY,
    student_group TEXT NOT NULL,
    weekday INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    new_room TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL,
    UNIQUE(student_group, weekday, start_time)
);
CREATE TABLE IF NOT EXISTS login_attempts (
    source TEXT NOT NULL, bucket INTEGER NOT NULL, count INTEGER NOT NULL,
    PRIMARY KEY(source, bucket)
);
"""


def connect(path):
    db = sqlite3.connect(path, timeout=8)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def session_hash(value):
    return sha256(value.encode("ascii")).hexdigest()


def enable_wal(db):
    deadline = time.monotonic() + 8
    while True:
        try:
            db.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode != sqlite3.SQLITE_BUSY or time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def _ensure_columns(db):
    student_cols = {row["name"] for row in db.execute("PRAGMA table_info(students)").fetchall()}
    if "role" not in student_cols:
        db.execute("ALTER TABLE students ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
    request_cols = {row["name"] for row in db.execute("PRAGMA table_info(requests)").fetchall()}
    if "staff_note" not in request_cols:
        db.execute("ALTER TABLE requests ADD COLUMN staff_note TEXT NOT NULL DEFAULT ''")
    if "decision" not in request_cols:
        db.execute("ALTER TABLE requests ADD COLUMN decision TEXT NOT NULL DEFAULT 'approved'")
    if "verify_token" not in request_cols:
        db.execute("ALTER TABLE requests ADD COLUMN verify_token TEXT NOT NULL DEFAULT ''")
    if "revoked_at" not in request_cols:
        db.execute("ALTER TABLE requests ADD COLUMN revoked_at INTEGER NOT NULL DEFAULT 0")
    db.execute("CREATE INDEX IF NOT EXISTS requests_by_token ON requests(verify_token)")
    missing_tokens = db.execute("SELECT id FROM requests WHERE verify_token = ''").fetchall()
    for r in missing_tokens:
        db.execute("UPDATE requests SET verify_token = ? WHERE id = ?", (secrets.token_urlsafe(16), r["id"]))


def _seed_charges(db, stamp):
    existing_charges = {row["id"] for row in db.execute("SELECT id FROM charges").fetchall()}
    for cid, sid, cat, title, contract_no, period_lbl, amount, due_lbl, st in INITIAL_CHARGES:
        if cid in existing_charges:
            continue
        paid_at = (stamp - 15 * 86400) if st == "paid" else 0
        method = "СБП · 0 %" if st == "paid" else ""
        rcode = f"RCP-{cid[-4:].upper()}-{sid}026" if st == "paid" else ""
        db.execute(
            "INSERT INTO charges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, sid, cat, title, contract_no, period_lbl, amount, due_lbl, st, paid_at, method, rcode),
        )


def _seed_requests(db, stamp):
    db.executemany(
        "INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (secrets.token_hex(16), 1, "grades", "digital", "", stamp - 45 * 60, stamp - 43 * 60, "seed-1", "", "approved", secrets.token_urlsafe(16), 0),
            (secrets.token_hex(16), 2, "study", "office", "", stamp - 60 * 60, stamp - 57 * 60, "seed-2", "", "approved", secrets.token_urlsafe(16), 0),
            (
                secrets.token_hex(16),
                2,
                "appeal",
                "digital",
                "Прошу включить факультатив по дипломатическому протоколу в индивидуальный план осеннего семестра.",
                stamp - 18 * 60,
                stamp + 90 * 60,
                "seed-3",
                "",
                "pending",
                secrets.token_urlsafe(16),
                0,
            ),
            (
                secrets.token_hex(16),
                1,
                "pgas",
                "digital",
                "Номинация: учебная и проектная деятельность (победитель кейс-чемпионата по продуктовой аналитике, рейтинг 90,3).",
                stamp - 10 * 60,
                stamp + 120 * 60,
                "seed-4",
                "",
                "pending",
                secrets.token_urlsafe(16),
                0,
            ),
        ],
    )


def reset_demo_data(db):
    """Reset mutable demo records while preserving students and their password_hash values."""
    stamp = int(now().timestamp())
    existing_tables = {
        row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    mutable_tables = (
        "notification_reads",
        "requests",
        "charges",
        "guest_passes",
        "room_bookings",
        "office_slots",
        "room_overrides",
        "staff_notices",
        "login_attempts",
        "assistant_messages",
        "assistant_gaps",
    )
    with db:
        db.execute("BEGIN IMMEDIATE")
        for tbl in mutable_tables:
            if tbl in existing_tables:
                db.execute(f"DELETE FROM {tbl}")
        _seed_requests(db, stamp)
        _seed_charges(db, stamp)


def initialize(path, password_hashes):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = connect(path)
    try:
        enable_wal(db)
        db.executescript(SCHEMA)
        _ensure_columns(db)
        with db:
            db.execute("BEGIN IMMEDIATE")
            existing = {row["id"] for row in db.execute("SELECT id FROM students").fetchall()}
            stamp = int(now().timestamp())
            if not existing:
                for student, password_hash in zip(STUDENTS, password_hashes, strict=True):
                    db.execute(
                        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (*student, password_hash),
                    )
                _seed_requests(db, stamp)
            elif 3 not in existing and len(password_hashes) >= 3:
                db.execute(
                    "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (*STUDENTS[2], password_hashes[2]),
                )
            _seed_charges(db, stamp)
    finally:
        db.close()
