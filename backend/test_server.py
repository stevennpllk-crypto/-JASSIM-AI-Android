import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
import subprocess
import sys
import time

class ServerSmokeTest(unittest.TestCase):
    def test_server_health_and_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["JASSIM_DATA_DIR"] = tmp
            env["JASSIM_PORT"] = "18787"
            env["JASSIM_HOST"] = "127.0.0.1"
            env["JASSIM_API_TOKEN"] = "smoke-test-token"
            proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("server.py"))],
                                    env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(40):
                    try:
                        with urlopen("http://127.0.0.1:18787/health", timeout=1) as r:
                            health = json.loads(r.read())
                        break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("server did not start")
                self.assertTrue(health["ok"])
                self.assertIn("model_ready", health)
                self.assertIsInstance(health["model_ready"], bool)
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/models"), timeout=5)
                payload = json.dumps({"message": "hello", "conversation_id": "smoke"}).encode()
                denied = Request("http://127.0.0.1:18787/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
                with self.assertRaises(Exception):
                    urlopen(denied, timeout=5)
                req = Request("http://127.0.0.1:18787/api/chat", data=payload,
                              headers={"Content-Type": "application/json", "Authorization": "Bearer smoke-test-token"})
                with urlopen(req, timeout=5) as r:
                    result = json.loads(r.read())
                self.assertIn("answer", result)
                self.assertEqual(result["conversation_id"], "smoke")
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/history?conversation_id=smoke"), timeout=5)
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/conversations"), timeout=5)
                headers = {"Authorization": "Bearer smoke-test-token"}
                history_req = Request("http://127.0.0.1:18787/api/history?conversation_id=smoke", headers=headers)
                with urlopen(history_req, timeout=5) as r:
                    saved = json.loads(r.read())
                self.assertEqual(len(saved["messages"]), 2)
                self.assertEqual(saved["messages"][0]["role"], "user")
                self.assertEqual(saved["messages"][0]["content"], "hello")
                self.assertEqual(saved["messages"][1]["role"], "assistant")
                conversations_req = Request("http://127.0.0.1:18787/api/conversations", headers=headers)
                with urlopen(conversations_req, timeout=5) as r:
                    conversations = json.loads(r.read())["conversations"]
                self.assertEqual(len(conversations), 1)
                self.assertEqual(conversations[0]["conversation_id"], "smoke")
                self.assertEqual(conversations[0]["title"], "hello")
                self.assertEqual(conversations[0]["message_count"], 2)
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/conversations?conversation_id=smoke",
                                    method="DELETE"), timeout=5)
                invalid_delete = Request(
                    "http://127.0.0.1:18787/api/conversations?conversation_id=bad%2Fid",
                    headers=headers, method="DELETE")
                with self.assertRaises(Exception):
                    urlopen(invalid_delete, timeout=5)
                delete_req = Request(
                    "http://127.0.0.1:18787/api/conversations?conversation_id=smoke",
                    headers=headers, method="DELETE")
                with urlopen(delete_req, timeout=5) as r:
                    deleted = json.loads(r.read())
                self.assertTrue(deleted["deleted"])
                self.assertEqual(deleted["deleted_messages"], 2)
                with urlopen(conversations_req, timeout=5) as r:
                    self.assertEqual(json.loads(r.read())["conversations"], [])
                with self.assertRaises(Exception):
                    urlopen(delete_req, timeout=5)
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/history?conversation_id=bad%2Fid", headers=headers), timeout=5)
                with self.assertRaises(Exception):
                    urlopen(Request("http://127.0.0.1:18787/api/conversations?limit=abc", headers=headers), timeout=5)
            finally:
                proc.terminate()
                proc.wait(timeout=5)

if __name__ == "__main__":
    unittest.main()
