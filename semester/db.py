import secrets
import sqlite3
import time
from hashlib import sha256
from pathlib import Path

from flask import current_app, g
from .demo import STUDENTS, now

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
    UNIQUE(student_id, nonce)
);
CREATE INDEX IF NOT EXISTS requests_by_owner ON requests(student_id, created_at DESC);
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
            if not existing:
                for student, password_hash in zip(STUDENTS, password_hashes, strict=True):
                    db.execute(
                        "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (*student, password_hash),
                    )
                stamp = int(now().timestamp())
                db.executemany(
                    "INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (secrets.token_hex(16), 1, "grades", "digital", "", stamp - 45 * 60, stamp - 43 * 60, "seed-1", ""),
                        (secrets.token_hex(16), 2, "study", "office", "", stamp - 60 * 60, stamp - 57 * 60, "seed-2", ""),
                        (
                            secrets.token_hex(16),
                            2,
                            "appeal",
                            "digital",
                            "Прошу включить факультатив по дипломатическому протоколу в индивидуальный план осеннего семестра.",
                            stamp - 12 * 60,
                            stamp + 50 * 60,
                            "seed-3",
                            "",
                        ),
                    ],
                )
            elif 3 not in existing and len(password_hashes) >= 3:
                db.execute(
                    "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (*STUDENTS[2], password_hashes[2]),
                )
    finally:
        db.close()
