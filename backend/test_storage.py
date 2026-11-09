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


if __name__ == "__main__":
    unittest.main()
