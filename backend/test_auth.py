import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import auth


class MultiUserAuthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
        os.environ["JASSIM_DATA_DIR"] = self.tmp.name
        spec = importlib.util.spec_from_file_location(
            "jassim_multi_user_server_test", BACKEND / "server.py"
        )
        self.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.server)
        self.db = self.server.connect_db()

    def tearDown(self):
        self.db.close()
        if self.previous_data_dir is None:
            os.environ.pop("JASSIM_DATA_DIR", None)
        else:
            os.environ["JASSIM_DATA_DIR"] = self.previous_data_dir
        self.tmp.cleanup()

    def test_password_hash_and_session_revocation(self):
        user = auth.create_user(self.db, "Test@Example.com", "a-long-test-password")
        row = auth.find_user_by_email(self.db, "test@example.com")
        self.assertEqual(user["email"], "test@example.com")
        self.assertNotEqual(row[2], "a-long-test-password")
        self.assertTrue(auth.verify_password("a-long-test-password", row[2]))
        self.assertFalse(auth.verify_password("wrong-password", row[2]))
        token = auth.issue_session(self.db, user["id"])
        identity = auth.authenticate_session(self.db, token)
        self.assertEqual(identity["user_id"], user["id"])
        self.assertTrue(auth.revoke_session(self.db, token))
        self.assertIsNone(auth.authenticate_session(self.db, token))

    def test_accounts_cannot_read_or_delete_each_others_chats(self):
        first = auth.create_user(self.db, "first@example.com", "first-password-123")
        second = auth.create_user(self.db, "second@example.com", "second-password-123")
        self.server.save_message("private-first", "user", "رسالة خاصة", first["id"])
        self.server.save_message("private-second", "user", "رسالة ثانية", second["id"])

        self.assertEqual(
            self.server.history("private-first", 20, first["id"])[0]["content"],
            "رسالة خاصة"
        )
        self.assertEqual(self.server.history("private-first", 20, second["id"]), [])
        self.assertEqual(
            [x["conversation_id"] for x in self.server.list_conversations(20, second["id"])],
            ["private-second"]
        )
        self.assertEqual(self.server.delete_conversation("private-first", second["id"]), 0)
        with self.assertRaises(PermissionError):
            self.server.save_message("private-first", "user", "اختراق", second["id"])

    def test_old_conversations_remain_with_legacy_owner(self):
        self.server.save_message("legacy-chat", "user", "بيانات قديمة")
        user = auth.create_user(self.db, "new@example.com", "new-user-password")
        self.assertEqual(self.server.history("legacy-chat", 20, user["id"]), [])
        self.assertEqual(
            self.server.history("legacy-chat", 20, "legacy-owner")[0]["content"],
            "بيانات قديمة"
        )


if __name__ == "__main__":
    unittest.main()
