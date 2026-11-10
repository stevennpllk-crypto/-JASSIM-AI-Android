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
                self.assertTrue({"messages", "memories", "provider_scores"} <= tables)
            finally:
                db.close()

    def test_backend_name_defaults_to_sqlite(self):
        self.assertIn(storage.backend_name(), ("sqlite", "postgresql"))


    def test_sqlite_to_postgres_copy_preserves_accounts_sessions_and_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "legacy.db"
            target_path = root / "target.db"

            source = sqlite3.connect(source_path)
            source.executescript("""
                CREATE TABLE users (
                    id TEXT PRIMARY KEY, email_normalized TEXT UNIQUE,
                    password_hash TEXT, role TEXT, created_at TEXT
                );
                CREATE TABLE sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT,
                    created_at TEXT, expires_at TEXT, revoked_at TEXT
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
                CREATE TABLE provider_scores (
                    provider_id TEXT PRIMARY KEY, attempts INTEGER, successes INTEGER,
                    avg_latency_ms REAL, quality_score REAL, last_success TEXT, last_error TEXT
                );
            """)
            source.execute("INSERT INTO users VALUES(?,?,?,?,?)",
                           ("user-1", "person@example.com", "pbkdf2_hash", "user", "2026-01-01T00:00:00Z"))
            source.execute("INSERT INTO sessions VALUES(?,?,?,?,?)",
                           ("token-hash-1", "user-1", "2026-01-01T00:00:00Z",
                            "2026-02-01T00:00:00Z", None))
            source.execute("INSERT INTO conversations VALUES(?,?,?,?)",
                           ("chat-1", "user-1", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"))
            source.execute("INSERT INTO messages VALUES(?,?,?,?,?)",
                           (7, "chat-1", "user", "رسالة محفوظة", "2026-01-01T00:00:00Z"))
            source.execute("INSERT INTO memories VALUES(?,?,?)",
                           ("chat-1", "ذاكرة محفوظة", "2026-01-02T00:00:00Z"))
            source.commit()
            source.close()

            target = storage.connect(sqlite_path=target_path)
            try:
                storage.ensure_schema(target, sqlite_path=target_path)
                storage._copy_sqlite_data(target, source_path)
                target.commit()
                self.assertEqual(
                    target.execute("SELECT email_normalized FROM users WHERE id='user-1'").fetchone()[0],
                    "person@example.com"
                )
                self.assertEqual(
                    target.execute("SELECT user_id FROM sessions WHERE token_hash='token-hash-1'").fetchone()[0],
                    "user-1"
                )
                self.assertEqual(
                    target.execute("SELECT user_id FROM conversations WHERE conversation_id='chat-1'").fetchone()[0],
                    "user-1"
                )
                self.assertEqual(
                    target.execute("SELECT content FROM messages WHERE id=7").fetchone()[0],
                    "رسالة محفوظة"
                )
                self.assertEqual(
                    target.execute("SELECT content FROM memories WHERE conversation_id='chat-1'").fetchone()[0],
                    "ذاكرة محفوظة"
                )
            finally:
                target.close()

    def test_postgres_connection_exposes_rollback(self):
        class FakeConnection:
            rolled_back = False
            def rollback(self):
                self.rolled_back = True

        raw = FakeConnection()
        storage.PostgresConnection(raw).rollback()
        self.assertTrue(raw.rolled_back)


if __name__ == "__main__":
    unittest.main()
