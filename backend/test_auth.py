import importlib.util
import os
import sys
import tempfile
import unittest
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
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

    def test_http_registration_and_cross_account_access(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(httpd.server_port)

        def call(path, method="GET", token=None, body=None):
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = "Bearer " + token
            data = json.dumps(body).encode("utf-8") if body is not None else None
            request = Request(base + path, data=data, headers=headers, method=method)
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))

        try:
            _, first = call("/api/auth/register", "POST", body={
                "email": "http-first@example.com", "password": "first-password-123"
            })
            _, second = call("/api/auth/register", "POST", body={
                "email": "http-second@example.com", "password": "second-password-123"
            })
            first_token, second_token = first["token"], second["token"]
            self.assertEqual(call("/api/auth/me", token=first_token)[1]["user"]["email"],
                             "http-first@example.com")

            _, saved = call("/api/chat", "POST", first_token, {
                "conversation_id": "http-private-first",
                "message": "تذكر أن هذه معلومة خاصة بالحساب الأول"
            })
            self.assertEqual(saved["engine"], "memory")
            first_history = call("/api/history?conversation_id=http-private-first", token=first_token)[1]
            second_history = call("/api/history?conversation_id=http-private-first", token=second_token)[1]
            self.assertEqual(len(first_history["messages"]), 2)
            self.assertEqual(second_history["messages"], [])

            with self.assertRaises(HTTPError) as denied:
                call("/api/conversations?conversation_id=http-private-first", "DELETE", second_token)
            self.assertEqual(denied.exception.code, 404)

            call("/api/auth/logout", "POST", first_token, {})
            with self.assertRaises(HTTPError) as revoked:
                call("/api/auth/me", token=first_token)
            self.assertEqual(revoked.exception.code, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)

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
