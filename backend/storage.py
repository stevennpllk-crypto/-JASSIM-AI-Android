"""Shared SQLite/PostgreSQL storage layer for horizontally scalable JASSIM workers."""
import os
import sqlite3
import threading
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_DIR = Path(os.environ.get("JASSIM_DATA_DIR", str(Path(__file__).resolve().parent / "data"))).expanduser()
SQLITE_PATH = DATA_DIR / "jassim.db"
_SCHEMA_LOCK = threading.Lock()
_SCHEMA_READY_KEY = None


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        cursor = self.connection.cursor()
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def connect(sqlite_path=None):
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL is configured but psycopg is not installed") from exc
        return PostgresConnection(psycopg.connect(url, connect_timeout=10))
    path = Path(sqlite_path) if sqlite_path is not None else SQLITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    return db


def ensure_schema(db, sqlite_path=None):
    global _SCHEMA_READY_KEY
    with _SCHEMA_LOCK:
        postgres = bool(os.environ.get("DATABASE_URL", "").strip())
        schema_key = "postgres:" + os.environ.get("DATABASE_URL", "").strip() if postgres else "sqlite:" + str(Path(sqlite_path) if sqlite_path is not None else SQLITE_PATH)
        if _SCHEMA_READY_KEY == schema_key:
            return
        if postgres:
            statements = [
                """CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""",
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)",
                """CREATE TABLE IF NOT EXISTS memories (
                    conversation_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                )""",
                "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
                """CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""",
                "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at)",
                """CREATE TABLE IF NOT EXISTS provider_scores (
                    provider_id TEXT PRIMARY KEY,
                    attempts BIGINT NOT NULL DEFAULT 0,
                    successes BIGINT NOT NULL DEFAULT 0,
                    avg_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
                    quality_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    last_success TEXT,
                    last_error TEXT
                )""",
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )"""
            ]
        else:
            statements = [
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""",
                "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)",
                """CREATE TABLE IF NOT EXISTS memories (
                    conversation_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                )""",
                "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)",
                """CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""",
                "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at)",
                """CREATE TABLE IF NOT EXISTS provider_scores (
                    provider_id TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    successes INTEGER NOT NULL DEFAULT 0,
                    avg_latency_ms REAL NOT NULL DEFAULT 0,
                    quality_score REAL NOT NULL DEFAULT 0,
                    last_success TEXT,
                    last_error TEXT
                )"""
            ]
        for statement in statements:
            db.execute(statement)
        db.commit()
        if postgres:
            _migrate_sqlite_once(db)
        # Existing chats are assigned once to a non-login legacy owner. They are
        # never claimable by the first newly registered account.
        db.execute(
            """INSERT INTO users(id,email_normalized,password_hash,role,created_at)
               VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING""",
            ("legacy-owner", "owner@jassim.local", "", "admin", "2026-01-01T00:00:00+00:00")
        )
        db.execute(
            """INSERT INTO conversations(conversation_id,user_id,created_at,updated_at)
               SELECT m.conversation_id,'legacy-owner',MIN(m.created_at),MAX(m.created_at)
               FROM messages m WHERE 1=1 GROUP BY m.conversation_id
               ON CONFLICT(conversation_id) DO NOTHING"""
        )
        db.execute(
            """INSERT INTO conversations(conversation_id,user_id,created_at,updated_at)
               SELECT m.conversation_id,'legacy-owner',m.updated_at,m.updated_at
               FROM memories m WHERE 1=1
               ON CONFLICT(conversation_id) DO NOTHING"""
        )
        db.commit()
        _SCHEMA_READY_KEY = schema_key


def _copy_sqlite_data(target, source_path):
    """Copy all legacy SQLite account and conversation data into a shared target."""
    source_path = Path(source_path)
    if not source_path.exists():
        return
    source = sqlite3.connect(source_path, timeout=5)
    try:
        tables = {row[0] for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        migrations = [
            ("users",
             "SELECT id,email_normalized,password_hash,role,created_at FROM users",
             """INSERT INTO users(id,email_normalized,password_hash,role,created_at)
                VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING"""),
            ("sessions",
             "SELECT token_hash,user_id,created_at,expires_at,revoked_at FROM sessions",
             """INSERT INTO sessions(token_hash,user_id,created_at,expires_at,revoked_at)
                VALUES(?,?,?,?,?) ON CONFLICT(token_hash) DO NOTHING"""),
            ("conversations",
             "SELECT conversation_id,user_id,created_at,updated_at FROM conversations",
             """INSERT INTO conversations(conversation_id,user_id,created_at,updated_at)
                VALUES(?,?,?,?) ON CONFLICT(conversation_id) DO NOTHING"""),
            ("messages",
             "SELECT id,conversation_id,role,content,created_at FROM messages ORDER BY id",
             """INSERT INTO messages(id,conversation_id,role,content,created_at)
                VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING"""),
            ("memories",
             "SELECT conversation_id,content,updated_at FROM memories",
             """INSERT INTO memories(conversation_id,content,updated_at) VALUES(?,?,?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                content=EXCLUDED.content,updated_at=EXCLUDED.updated_at"""),
            ("provider_scores",
             """SELECT provider_id,attempts,successes,avg_latency_ms,quality_score,last_success,last_error
                FROM provider_scores""",
             """INSERT INTO provider_scores(provider_id,attempts,successes,avg_latency_ms,
                quality_score,last_success,last_error) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(provider_id) DO NOTHING"""),
        ]
        for table, select_sql, insert_sql in migrations:
            if table not in tables:
                continue
            for row in source.execute(select_sql):
                target.execute(insert_sql, tuple(row))
    finally:
        source.close()


def _migrate_sqlite_once(target):
    marker = "sqlite_to_postgres_v2_accounts"
    if target.execute("SELECT name FROM schema_migrations WHERE name=?", (marker,)).fetchone():
        return
    _copy_sqlite_data(target, SQLITE_PATH)
    # Keep BIGSERIAL aligned with imported IDs; an empty table must next yield ID 1.
    target.execute(
        """SELECT setval(
               pg_get_serial_sequence('messages','id'),
               COALESCE((SELECT MAX(id) FROM messages), 1),
               EXISTS(SELECT 1 FROM messages)
           )"""
    )
    target.execute("INSERT INTO schema_migrations(name) VALUES(?) ON CONFLICT(name) DO NOTHING", (marker,))
    target.commit()


def backend_name():
    return "postgresql" if os.environ.get("DATABASE_URL", "").strip() else "sqlite"
