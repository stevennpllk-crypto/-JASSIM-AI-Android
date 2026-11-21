import sqlite3
import tempfile
import unittest
from pathlib import Path

import storage


class SharedStorageTests(unittest.TestCase):
    def test_sqlite_fallback_creates_shared_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jassim-test.db"
            db = storage.connect(sqlite_path=path)
            try:
                storage.ensure_schema(db, sqlite_path=path)
                db.execute(
                    "INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)",
                    ("chat-1", "user", "مرحبا", "2026-11-10T00:00:00Z")
                )
                db.commit()
                row = db.execute(
                    "SELECT role,content FROM messages WHERE conversation_id=?",
                    ("chat-1",)
                ).fetchone()
                self.assertEqual(tuple(row), ("user", "مرحبا"))
                tables = {item[0] for item in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()}
                self.assertTrue({"messages", "memories", "account_memories", "provider_scores"} <= tables)
            finally:
                db.close()

    def test_backend_name_defaults_to_sqlite(self):
        self.assertIn(storage.backend_name(), ("sqlite", "postgresql"))

    def test_postgres_adapter_supports_rollback(self):
        raw = sqlite3.connect(":memory:")
        db = storage.PostgresConnection(raw)
        db.execute("CREATE TABLE rollback_test (value TEXT)")
        db.execute("INSERT INTO rollback_test(value) VALUES('temporary')")
        db.rollback()
        self.assertEqual(db.execute("SELECT COUNT(*) FROM rollback_test").fetchone()[0], 0)
        db.close()

    def test_sqlite_migration_preserves_users_sessions_and_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "source.db"
            target_path = Path(tmp) / "target.db"
            source = sqlite3.connect(source_path)
            source.executescript("""
                CREATE TABLE users (
                    id TEXT PRIMARY KEY, email_normalized TEXT UNIQUE,
                    password_hash TEXT, role TEXT, created_at TEXT
                );
                CREATE TABLE conversations (
                    conversation_id TEXT PRIMARY KEY, user_id TEXT,
                    created_at TEXT, updated_at TEXT
                );
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY, conversation_id TEXT,
                    role TEXT, content TEXT, created_at TEXT
                );
                CREATE TABLE memories (
                    conversation_id TEXT PRIMARY KEY, content TEXT, updated_at TEXT
                );
                CREATE TABLE sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT,
                    created_at TEXT, expires_at TEXT, revoked_at TEXT
                );
                CREATE TABLE provider_scores (
                    provider_id TEXT PRIMARY KEY, attempts INTEGER, successes INTEGER,
                    avg_latency_ms REAL, quality_score REAL, last_success TEXT, last_error TEXT
                );
                INSERT INTO users VALUES ('user-1','one@example.com','pbkdf2-hash','user','2026-01-01');
                INSERT INTO conversations VALUES ('chat-1','user-1','2026-01-01','2026-01-02');
                INSERT INTO messages VALUES (1,'chat-1','user','private message','2026-01-02');
                INSERT INTO memories VALUES ('chat-1','private memory','2026-01-02');
                INSERT INTO sessions VALUES ('token-digest','user-1','2026-01-01','2026-02-01',NULL);
                INSERT INTO provider_scores VALUES ('local',2,1,120.0,0.8,'2026-01-02',NULL);
            """)
            source.commit()
            source.close()

            class SQLiteBackedPostgresTarget:
                def __init__(self, path):
                    self.db = sqlite3.connect(path)
                def execute(self, sql, params=()):
                    if sql.startswith("SELECT setval("):
                        return self.db.execute("SELECT 1")
                    return self.db.execute(sql, params)
                def commit(self):
                    self.db.commit()

            target = SQLiteBackedPostgresTarget(target_path)
            target.db.executescript("""
                CREATE TABLE schema_migrations (name TEXT PRIMARY KEY);
                INSERT INTO schema_migrations(name) VALUES ('sqlite_to_postgres_v1');
                CREATE TABLE users (
                    id TEXT PRIMARY KEY, email_normalized TEXT UNIQUE,
                    password_hash TEXT, role TEXT, created_at TEXT
                );
                INSERT INTO users VALUES ('new-user-id','one@example.com','new-password-hash','user','2026-02-01');
                CREATE TABLE conversations (
                    conversation_id TEXT PRIMARY KEY, user_id TEXT,
                    created_at TEXT, updated_at TEXT
                );
                INSERT INTO conversations VALUES ('chat-1','legacy-owner','old','old');
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY, conversation_id TEXT,
                    role TEXT, content TEXT, created_at TEXT
                );
                CREATE TABLE memories (
                    conversation_id TEXT PRIMARY KEY, content TEXT, updated_at TEXT
                );
                CREATE TABLE sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT,
                    created_at TEXT, expires_at TEXT, revoked_at TEXT
                );
                CREATE TABLE provider_scores (
                    provider_id TEXT PRIMARY KEY, attempts INTEGER, successes INTEGER,
                    avg_latency_ms REAL, quality_score REAL, last_success TEXT, last_error TEXT
                );
            """)
            previous_path = storage.SQLITE_PATH
            storage.SQLITE_PATH = source_path
            try:
                storage._migrate_sqlite_once(target)
                self.assertEqual(target.execute(
                    "SELECT email_normalized FROM users WHERE id=?", ("new-user-id",)
                ).fetchone()[0], "one@example.com")
                self.assertIsNone(target.execute(
                    "SELECT id FROM users WHERE id=?", ("user-1",)
                ).fetchone())
                self.assertEqual(target.execute(
                    "SELECT user_id FROM conversations WHERE conversation_id=?", ("chat-1",)
                ).fetchone()[0], "new-user-id")
                self.assertEqual(target.execute(
                    "SELECT content FROM messages WHERE id=?", (1,)
                ).fetchone()[0], "private message")
                self.assertEqual(target.execute(
                    "SELECT content FROM memories WHERE conversation_id=?", ("chat-1",)
                ).fetchone()[0], "private memory")
                self.assertEqual(target.execute(
                    "SELECT user_id FROM sessions WHERE token_hash=?", ("token-digest",)
                ).fetchone()[0], "new-user-id")
                self.assertIsNotNone(target.execute(
                    "SELECT name FROM schema_migrations WHERE name=?", ("sqlite_to_postgres_v2",)
                ).fetchone())
            finally:
                storage.SQLITE_PATH = previous_path
                target.db.close()


if __name__ == "__main__":
    unittest.main()
