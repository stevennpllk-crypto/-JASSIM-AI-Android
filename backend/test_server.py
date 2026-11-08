import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
import subprocess
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class FakeOllamaHandler(BaseHTTPRequestHandler):
    last_chat_payload = None
    offline = False

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if FakeOllamaHandler.offline:
            self.send_error(503)
            return
        if self.path == "/api/tags":
            payload = {"models": [{"name": "qwen3.5:4b", "size": 1234}]}
        elif self.path == "/api/ps":
            payload = {"models": [{"name": "qwen3.5:4b"}]}
        else:
            self.send_error(404)
            return
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if FakeOllamaHandler.offline:
            self.send_error(503)
            return
        length = int(self.headers.get("Content-Length", "0"))
        FakeOllamaHandler.last_chat_payload = json.loads(self.rfile.read(length))
        raw = json.dumps({"message": {"content": "مرحباً! أنا JASSIM AI، وهذه إجابة اختبار حقيقية من محرك Ollama التجريبي."}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ServerSmokeTest(unittest.TestCase):
    def test_history_budget_preserves_recent_messages(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("jassim_server", Path(__file__).with_name("server.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.HISTORY_CHAR_BUDGET = 10
        kept = module.fit_history_to_budget([
            {"role": "user", "content": "قديم جداً"},
            {"role": "assistant", "content": "رد قديم"},
            {"role": "user", "content": "هذا أحدث سؤال"}
        ])
        self.assertEqual(kept[-1]["role"], "user")
        self.assertLessEqual(sum(len(x["content"]) for x in kept), 10)

    def test_server_health_and_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["JASSIM_DATA_DIR"] = tmp
            env["JASSIM_PORT"] = "18787"
            env["JASSIM_HOST"] = "127.0.0.1"
            env["JASSIM_API_TOKEN"] = "smoke-test-token"
            fake_ollama = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
            fake_thread = threading.Thread(target=fake_ollama.serve_forever, daemon=True)
            fake_thread.start()
            env["JASSIM_OLLAMA_URL"] = "http://127.0.0.1:" + str(fake_ollama.server_port)
            env["JASSIM_OLLAMA_MODEL"] = "qwen3.5:4b"
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
                self.assertTrue(health["model_ready"])
                self.assertTrue(health["model_loaded"])
                self.assertTrue(health["ollama_reachable"])
                self.assertGreaterEqual(health["uptime_seconds"], 0)
                with urlopen("http://127.0.0.1:18787/ready", timeout=5) as r:
                    self.assertTrue(json.loads(r.read())["ready"])
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
                self.assertEqual(result["engine"], "ollama")
                self.assertIn("إجابة اختبار", result["answer"])
                self.assertEqual(result["conversation_id"], "smoke")
                sent = FakeOllamaHandler.last_chat_payload
                self.assertEqual(sent["model"], "qwen3.5:4b")
                self.assertEqual(sent["keep_alive"], "-1")
                self.assertEqual(sent["options"]["num_ctx"], 8192)
                self.assertEqual(sent["options"]["num_predict"], 2048)
                self.assertEqual(sent["options"]["temperature"], 0.55)
                self.assertEqual(sent["options"]["top_k"], 40)
                self.assertEqual(sent["messages"][0]["role"], "system")
                self.assertIn("اللهجة التونسية", sent["messages"][0]["content"])
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
                FakeOllamaHandler.offline = True
                with self.assertRaises(Exception):
                    urlopen("http://127.0.0.1:18787/ready", timeout=5)
                offline_payload = json.dumps({"message": "اختبار انقطاع المحرك", "conversation_id": "offline"}).encode()
                offline_req = Request(
                    "http://127.0.0.1:18787/api/chat", data=offline_payload,
                    headers={"Content-Type": "application/json", "Authorization": "Bearer smoke-test-token"})
                with urlopen(offline_req, timeout=5) as r:
                    offline_result = json.loads(r.read())
                self.assertEqual(offline_result["engine"], "fallback")
                offline_history = Request(
                    "http://127.0.0.1:18787/api/history?conversation_id=offline", headers=headers)
                with urlopen(offline_history, timeout=5) as r:
                    self.assertEqual(len(json.loads(r.read())["messages"]), 1)
                FakeOllamaHandler.offline = False
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
                fake_ollama.shutdown()
                fake_ollama.server_close()
                fake_thread.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
