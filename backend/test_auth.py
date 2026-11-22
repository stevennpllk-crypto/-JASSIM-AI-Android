import importlib.util
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
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

            # The saved memory belongs to the first account, not merely to a known conversation ID.
            self.assertEqual(self.server.get_memory("http-private-first", first["user"]["id"]),
                             "هذه معلومة خاصة بالحساب الأول")
            self.assertEqual(self.server.get_memory("http-private-first", second["user"]["id"]), "")
            self.assertEqual(call("/api/conversations", token=second_token)[1]["conversations"], [])

            # A second account cannot overwrite the first account memory through the HTTP chat route.
            with self.assertRaises(HTTPError) as overwrite_denied:
                call("/api/chat", "POST", second_token, {
                    "conversation_id": "http-private-first",
                    "message": "احفظ أن هذه معلومة بديلة من الحساب الثاني"
                })
            self.assertEqual(overwrite_denied.exception.code, 404)
            self.assertEqual(self.server.get_memory("http-private-first", first["user"]["id"]),
                             "هذه معلومة خاصة بالحساب الأول")
            self.assertFalse(self.server.clear_memory("http-private-first", second["user"]["id"]))

            with self.assertRaises(HTTPError) as denied:
                call("/api/conversations?conversation_id=http-private-first", "DELETE", second_token)
            self.assertEqual(denied.exception.code, 404)

            call("/api/auth/logout", "POST", first_token, {})
            with self.assertRaises(HTTPError) as revoked:
                call("/api/auth/me", token=first_token)
            self.assertEqual(revoked.exception.code, 401)
            # Revocation must block other authenticated data routes too, not only /me.
            with self.assertRaises(HTTPError) as revoked_history:
                call("/api/history?conversation_id=http-private-first", token=first_token)
            self.assertEqual(revoked_history.exception.code, 401)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)

    def test_expired_session_is_rejected_by_authenticated_http_routes(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(httpd.server_port)
        user = auth.create_user(self.db, "expired@example.com", "expired-session-password")
        token = auth.issue_session(self.db, user["id"])
        from datetime import datetime, timedelta, timezone
        expired_at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        self.db.execute(
            "UPDATE sessions SET expires_at=? WHERE token_hash=?",
            (expired_at, auth._token_hash(token))
        )
        self.db.commit()

        def get(path):
            request = Request(
                base + path,
                headers={"Authorization": "Bearer " + token},
                method="GET"
            )
            with urlopen(request, timeout=5) as response:
                return response.status

        try:
            for path in (
                "/api/auth/me",
                "/api/history?conversation_id=expired-private",
                "/api/conversations",
            ):
                with self.subTest(path=path):
                    with self.assertRaises(HTTPError) as denied:
                        get(path)
                    self.assertEqual(denied.exception.code, 401)
            # Expired sessions must also be rejected by state-changing POST routes.
            chat_body = json.dumps({
                "conversation_id": "expired-private",
                "message": "must not be accepted"
            }).encode("utf-8")
            chat_request = Request(
                base + "/api/chat",
                data=chat_body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with self.assertRaises(HTTPError) as expired_chat:
                urlopen(chat_request, timeout=5)
            self.assertEqual(expired_chat.exception.code, 401)

            image_body = json.dumps({"prompt": "must not reach provider"}).encode("utf-8")
            image_request = Request(
                base + "/api/images/generate",
                data=image_body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with patch.object(self.server, "generate_image_hf") as provider:
                with self.assertRaises(HTTPError) as expired_image:
                    urlopen(image_request, timeout=5)
                self.assertEqual(expired_image.exception.code, 401)
                provider.assert_not_called()

            self.assertIsNone(auth.authenticate_session(self.db, token))
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=3)

    def test_image_generation_requires_auth_and_does_not_store_prompt(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), self.server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(httpd.server_port)
        user = auth.create_user(self.db, "image-user@example.com", "image-user-password")
        token = auth.issue_session(self.db, user["id"])
        prompt = "A private test prompt that must not enter chat history"
        body = json.dumps({"prompt": prompt}).encode("utf-8")

        def post(token_value=None):
            headers = {"Content-Type": "application/json"}
            if token_value:
                headers["Authorization"] = "Bearer " + token_value
            request = Request(base + "/api/images/generate", data=body, headers=headers, method="POST")
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))

        try:
            with patch.object(self.server, "generate_image_hf") as provider:
                with self.assertRaises(HTTPError) as denied:
                    post()
                self.assertEqual(denied.exception.code, 401)
                provider.assert_not_called()

            before = self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            with patch.object(self.server, "generate_image_hf", return_value=("aGVsbG8=", "image/png", "test-model")) as provider:
                status, result = post(token)
                self.assertEqual(status, 200)
                self.assertEqual(result["image_base64"], "aGVsbG8=")
                provider.assert_called_once_with(prompt)
            after = self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            self.assertEqual(after, before)
            self.assertEqual(self.server.history("image-prompt-not-saved", 20, user["id"]), [])
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
