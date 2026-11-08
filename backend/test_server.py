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
                models_denied = Request("http://127.0.0.1:18787/api/models")
                with self.assertRaises(Exception):
                    urlopen(models_denied, timeout=5)
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
                history_req = Request("http://127.0.0.1:18787/api/history?conversation_id=smoke", headers={"Authorization": "Bearer smoke-test-token"})
                with urlopen(history_req) as r:
                    saved = json.loads(r.read())
                self.assertEqual(len(saved["messages"]), 2)
            finally:
                proc.terminate()
                proc.wait(timeout=5)

if __name__ == "__main__":
    unittest.main()
