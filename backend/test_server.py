import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
import subprocess
import sys
import time
from unittest.mock import patch
import threading
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer

class FakeOllamaHandler(BaseHTTPRequestHandler):
    last_chat_payload = None
    offline = False
    stream_slow = False

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
        answer = "مرحباً! أنا JASSIM AI، وهذه إجابة اختبار حقيقية من محرك Ollama التجريبي."
        if FakeOllamaHandler.last_chat_payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.end_headers()
            for index, chunk in enumerate(("مرحباً! أنا JASSIM AI، ", "وهذه إجابة اختبار حقيقية من محرك Ollama التجريبي.")):
                raw = json.dumps({"message": {"content": chunk}, "done": False}, ensure_ascii=False).encode()
                self.wfile.write(raw + b"\n")
                self.wfile.flush()
                if index == 0 and FakeOllamaHandler.stream_slow:
                    time.sleep(0.5)
            final = json.dumps({"message": {"content": ""}, "done": True}).encode()
            self.wfile.write(final + b"\n")
            self.wfile.flush()
            return
        raw = json.dumps({"message": {"content": answer}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ServerSmokeTest(unittest.TestCase):
    def test_colab_notebook_code_cells_compile(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "JASSIM_AI_Colab_GPU.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        self.assertEqual(notebook.get("nbformat"), 4)
        code_cells = [cell for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"]
        self.assertGreaterEqual(len(code_cells), 8)
        for index, cell in enumerate(code_cells):
            source = "".join(cell.get("source", []))
            self.assertTrue(source.strip(), f"Notebook code cell {index} is empty")
            compile(source, f"JASSIM_AI_Colab_GPU.ipynb:cell-{index}", "exec")

    def test_colab_endpoint_publication_is_opt_in_even_after_watchdog_restart(self):
        notebook_path = Path(__file__).resolve().parents[1] / "notebooks" / "JASSIM_AI_Colab_GPU.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        cells = ["".join(cell.get("source", [])) if isinstance(cell.get("source", []), list) else str(cell.get("source", "")) for cell in notebook.get("cells", [])]
        self.assertIn("PUBLISH_ENDPOINT_TO_GITHUB = False", cells[13])
        self.assertIn("globals().get('PUBLISH_ENDPOINT_TO_GITHUB', False)", cells[17])
        self.assertIn("private/manual only", cells[17])
        self.assertIn("Android auto-discovery is disabled", cells[15])
        self.assertIn("Copy this HTTPS URL into Android Settings", cells[15])
        self.assertIn("requests.get(tunnel_url + '/ready', timeout=8)", cells[17])

    def test_history_budget_preserves_recent_messages(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location("jassim_server_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir
        module.HISTORY_CHAR_BUDGET = 10
        kept = module.fit_history_to_budget([
            {"role": "user", "content": "قديم جداً"},
            {"role": "assistant", "content": "رد قديم"},
            {"role": "user", "content": "هذا أحدث سؤال"}
        ])
        self.assertEqual(kept[-1]["role"], "user")
        self.assertLessEqual(sum(len(x["content"]) for x in kept), 10)

    def test_history_budget_preserves_start_of_long_current_prompt(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location("jassim_prompt_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir
        module.HISTORY_CHAR_BUDGET = 5
        kept = module.fit_history_to_budget([
            {"role": "user", "content": "START-question-tail"}
        ])
        self.assertEqual(kept, [{"role": "user", "content": "START"}])

    def test_user_controlled_memory_save_read_clear(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location("jassim_memory_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.assertEqual(module.memory_command("تذكر أن لغتي المفضلة العربية"),
                                 ("save", "لغتي المفضلة العربية"))
                self.assertEqual(module.memory_command("ماذا تتذكر عني؟"), ("show", ""))
                self.assertEqual(module.memory_command("انسَ ذاكرتي"), ("clear", ""))
                module.set_memory("chat-test", "أفضل الشرح المختصر")
                self.assertEqual(module.get_memory("chat-test"), "أفضل الشرح المختصر")
                self.assertTrue(module.clear_memory("chat-test"))
                self.assertEqual(module.get_memory("chat-test"), "")
                with self.assertRaises(ValueError):
                    module.set_memory("chat-test", " ")
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

    def test_inference_queue_rejects_overload_cleanly(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("jassim_queue_test", Path(__file__).with_name("server.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.INFERENCE_SEMAPHORE.acquire()
        module.OLLAMA_QUEUE_TIMEOUT = 0.01
        try:
            answer, engine = module.generate_answer([])
            self.assertEqual(engine, "busy")
            self.assertIn("مشغول", answer)
        finally:
            module.INFERENCE_SEMAPHORE.release()

    def test_liveness_and_readiness_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["JASSIM_DATA_DIR"] = tmp
            env["JASSIM_PORT"] = "18788"
            env["JASSIM_HOST"] = "127.0.0.1"
            env["JASSIM_API_TOKEN"] = "readiness-test-token"
            env["JASSIM_OLLAMA_URL"] = "http://127.0.0.1:1"
            env["JASSIM_OLLAMA_MODEL"] = "qwen3.5:4b"
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("server.py"))],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            try:
                for _ in range(40):
                    try:
                        with urlopen("http://127.0.0.1:18788/health", timeout=2) as response:
                            health = json.loads(response.read())
                        break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("server did not start")
                self.assertTrue(health["ok"])
                self.assertFalse(health["ollama_reachable"])
                with self.assertRaises(Exception) as raised:
                    urlopen("http://127.0.0.1:18788/ready", timeout=3)
                self.assertEqual(getattr(raised.exception, "code", None), 503)
            finally:
                proc.terminate()
                proc.wait(timeout=5)

    def test_private_chat_fails_closed_when_ollama_is_offline(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_private_only_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                with patch.object(module, "ask_ollama", side_effect=RuntimeError("offline")):
                    answer, engine = module.generate_answer(
                        [{"role": "user", "content": "رسالة خاصة"}])
                self.assertEqual(engine, "unavailable")
                self.assertIn("لم تُرسل رسالتك إلى أي خادم أو مزوّد آخر", answer)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

    def test_streaming_returns_503_when_private_ollama_is_offline(self):
        import importlib.util
        import urllib.error
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_stream_private_only_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.INFERENCE_SEMAPHORE = threading.BoundedSemaphore(1)
                module.OLLAMA_QUEUE_TIMEOUT = 1
                handler = module.Handler.__new__(module.Handler)
                sent = []
                handler.send_json = lambda status, payload: sent.append((status, payload))
                with patch.object(module.urllib.request, "urlopen",
                                  side_effect=urllib.error.URLError("private Ollama offline")):
                    handler.stream_chat_response(
                        "private-stream", "رسالة خاصة",
                        [{"role": "user", "content": "رسالة خاصة"}], "test-user")
                self.assertEqual(len(sent), 1)
                self.assertEqual(sent[0][0], 503)
                self.assertEqual(sent[0][1]["error"], "private_model_unavailable")
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

    def test_http_head_method_and_authentication_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            env = os.environ.copy()
            env["JASSIM_DATA_DIR"] = tmp
            env["JASSIM_PORT"] = str(port)
            env["JASSIM_HOST"] = "127.0.0.1"
            env.pop("JASSIM_API_TOKEN", None)
            env["JASSIM_OLLAMA_URL"] = "http://127.0.0.1:1"
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).with_name("server.py"))],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            base = "http://127.0.0.1:" + str(port)
            try:
                for _ in range(50):
                    try:
                        with urlopen(base + "/health", timeout=1):
                            break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("server did not start for HTTP method tests")

                with urlopen(base + "/", timeout=3) as response:
                    root = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(root["service"], "JASSIM AI")
                    self.assertEqual(root["status"], "api_online")
                    self.assertEqual(root["inference"], "private_ollama_only")

                with urlopen(base + "/favicon.ico", timeout=3) as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(response.read(), b"")

                with self.assertRaises(Exception) as providers_error:
                    urlopen(base + "/api/providers", timeout=3)
                self.assertEqual(getattr(providers_error.exception, "code", None), 404)

                head = Request(base + "/health", method="HEAD")
                with urlopen(head, timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertGreater(int(response.headers.get("Content-Length", "0")), 0)
                    self.assertEqual(response.read(), b"")

                unsupported = Request(base + "/health", method="PUT")
                with self.assertRaises(Exception) as method_error:
                    urlopen(unsupported, timeout=3)
                self.assertEqual(getattr(method_error.exception, "code", None), 405)
                self.assertIn("GET", method_error.exception.headers.get("Allow", ""))

                unknown_verb = Request(base + "/health", method="BREW")
                with self.assertRaises(Exception) as unknown_verb_error:
                    urlopen(unknown_verb, timeout=3)
                self.assertEqual(getattr(unknown_verb_error.exception, "code", None), 405)

                unknown = Request(
                    base + "/api/route-that-does-not-exist",
                    data=b"{}", headers={"Content-Type": "application/json"}
                )
                with self.assertRaises(Exception) as missing_error:
                    urlopen(unknown, timeout=3)
                self.assertEqual(getattr(missing_error.exception, "code", None), 404)

                chat = Request(
                    base + "/api/chat",
                    data=json.dumps({"message": "private test"}).encode(),
                    headers={"Content-Type": "application/json"}
                )
                with self.assertRaises(Exception) as auth_error:
                    urlopen(chat, timeout=3)
                self.assertEqual(getattr(auth_error.exception, "code", None), 401)

                stream_chat = Request(
                    base + "/api/chat/stream",
                    data=json.dumps({"message": "private stream test"}).encode(),
                    headers={"Content-Type": "application/json", "Accept": "text/event-stream"}
                )
                with self.assertRaises(Exception) as stream_auth_error:
                    urlopen(stream_chat, timeout=3)
                self.assertEqual(getattr(stream_auth_error.exception, "code", None), 401)
            finally:
                proc.terminate()
                proc.wait(timeout=5)

    def test_server_health_and_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["JASSIM_DATA_DIR"] = tmp
            with socket.socket() as port_probe:
                port_probe.bind(("127.0.0.1", 0))
                api_port = port_probe.getsockname()[1]
            api_base = "http://127.0.0.1:" + str(api_port)
            env["JASSIM_PORT"] = str(api_port)
            env["JASSIM_HOST"] = "127.0.0.1"
            FakeOllamaHandler.offline = False
            FakeOllamaHandler.last_chat_payload = None
            env["JASSIM_API_TOKEN"] = "smoke-test-token"
            fake_ollama = HTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
            fake_thread = threading.Thread(target=fake_ollama.serve_forever, daemon=True)
            fake_thread.start()
            env["JASSIM_OLLAMA_URL"] = "http://127.0.0.1:" + str(fake_ollama.server_port)
            env["JASSIM_OLLAMA_MODEL"] = "qwen3.5:4b"
            server_log_path = Path(tmp) / "server.log"
            server_log = open(server_log_path, "w")
            proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name("server.py"))],
                                    env=env, stdout=server_log, stderr=subprocess.STDOUT)
            try:
                for _ in range(40):
                    try:
                        with urlopen(api_base + "/health", timeout=1) as r:
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
                with urlopen(api_base + "/ready", timeout=5) as r:
                    self.assertTrue(json.loads(r.read())["ready"])
                with self.assertRaises(Exception):
                    urlopen(Request(api_base + "/api/models"), timeout=5)
                payload = json.dumps({"message": "hello", "conversation_id": "smoke"}).encode()
                denied = Request(api_base + "/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
                with self.assertRaises(Exception):
                    urlopen(denied, timeout=5)
                req = Request(api_base + "/api/chat", data=payload,
                              headers={"Content-Type": "application/json", "Authorization": "Bearer smoke-test-token"})
                # Allow extra scheduler time on busy shared CI runners.
                try:
                    with urlopen(req, timeout=20) as r:
                        result = json.loads(r.read())
                except Exception as exc:
                    server_log.flush()
                    self.fail("Chat request failed: " + repr(exc) + "\\n" + server_log_path.read_text(errors="ignore"))
                self.assertIn("answer", result)
                self.assertEqual(result["engine"], "ollama")
                self.assertIn("إجابة اختبار", result["answer"])
                self.assertEqual(result["conversation_id"], "smoke")
                sent = FakeOllamaHandler.last_chat_payload
                self.assertEqual(sent["model"], "qwen3.5:4b")
                self.assertEqual(sent["keep_alive"], "-1")
                self.assertEqual(sent["options"]["num_ctx"], 8192)
                self.assertEqual(sent["options"]["num_predict"], 3072)
                self.assertEqual(sent["options"]["temperature"], 0.45)
                self.assertEqual(sent["options"]["top_k"], 40)
                self.assertEqual(sent["messages"][0]["role"], "system")
                self.assertIn("اللهجة التونسية", sent["messages"][0]["content"])
                with self.assertRaises(Exception):
                    urlopen(Request(api_base + "/api/history?conversation_id=smoke"), timeout=5)
                with self.assertRaises(Exception):
                    urlopen(Request(api_base + "/api/conversations"), timeout=5)
                headers = {"Authorization": "Bearer smoke-test-token"}
                memory_payload = json.dumps({
                    "message": "تذكر أن أفضل الإجابات المختصرة",
                    "conversation_id": "memory-chat"
                }).encode()
                memory_req = Request(
                    api_base + "/api/chat", data=memory_payload,
                    headers={"Content-Type": "application/json", **headers})
                with urlopen(memory_req, timeout=5) as response:
                    self.assertEqual(json.loads(response.read())["engine"], "memory")
                memory_history_req = Request(
                    api_base + "/api/history?conversation_id=memory-chat", headers=headers)
                with urlopen(memory_history_req, timeout=5) as response:
                    memory_history = json.loads(response.read())["messages"]
                self.assertEqual(len(memory_history), 2)
                self.assertIn("حفظت هذه المعلومة", memory_history[1]["content"])
                show_memory_payload = json.dumps({
                    "message": "ماذا تتذكر عني؟",
                    "conversation_id": "memory-chat"
                }).encode()
                show_memory_req = Request(
                    api_base + "/api/chat", data=show_memory_payload,
                    headers={"Content-Type": "application/json", **headers})
                with urlopen(show_memory_req, timeout=5) as response:
                    shown_memory = json.loads(response.read())["answer"]
                self.assertIn("أفضل الإجابات المختصرة", shown_memory)
                delete_memory_chat = Request(
                    api_base + "/api/conversations?conversation_id=memory-chat",
                    headers=headers, method="DELETE")
                with urlopen(delete_memory_chat, timeout=5):
                    pass
                history_req = Request(api_base + "/api/history?conversation_id=smoke", headers=headers)
                with urlopen(history_req, timeout=5) as r:
                    saved = json.loads(r.read())
                self.assertEqual(len(saved["messages"]), 2)
                self.assertEqual(saved["messages"][0]["role"], "user")
                self.assertEqual(saved["messages"][0]["content"], "hello")
                self.assertEqual(saved["messages"][1]["role"], "assistant")
                conversations_req = Request(api_base + "/api/conversations", headers=headers)
                with urlopen(conversations_req, timeout=5) as r:
                    conversations = json.loads(r.read())["conversations"]
                self.assertEqual(len(conversations), 1)
                self.assertEqual(conversations[0]["conversation_id"], "smoke")
                self.assertEqual(conversations[0]["title"], "hello")
                self.assertEqual(conversations[0]["message_count"], 2)
                FakeOllamaHandler.offline = True
                with self.assertRaises(Exception):
                    urlopen(api_base + "/ready", timeout=5)
                offline_payload = json.dumps({"message": "اختبار انقطاع المحرك", "conversation_id": "offline"}).encode()
                offline_req = Request(
                    api_base + "/api/chat", data=offline_payload,
                    headers={"Content-Type": "application/json", "Authorization": "Bearer smoke-test-token"})
                with self.assertRaises(Exception) as offline_error:
                    urlopen(offline_req, timeout=5)
                self.assertEqual(getattr(offline_error.exception, "code", None), 503)
                offline_history = Request(
                    api_base + "/api/history?conversation_id=offline", headers=headers)
                with urlopen(offline_history, timeout=5) as r:
                    self.assertEqual(json.loads(r.read())["messages"], [])
                delete_offline = Request(
                    api_base + "/api/conversations?conversation_id=offline",
                    headers=headers, method="DELETE")
                with self.assertRaises(Exception) as missing_offline:
                    urlopen(delete_offline, timeout=5)
                self.assertEqual(getattr(missing_offline.exception, "code", None), 404)
                FakeOllamaHandler.offline = False
                with self.assertRaises(Exception):
                    urlopen(Request(api_base + "/api/conversations?conversation_id=smoke",
                                    method="DELETE"), timeout=5)
                invalid_delete = Request(
                    api_base + "/api/conversations?conversation_id=bad%2Fid",
                    headers=headers, method="DELETE")
                with self.assertRaises(Exception):
                    urlopen(invalid_delete, timeout=5)
                delete_req = Request(
                    api_base + "/api/conversations?conversation_id=smoke",
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
                    urlopen(Request(api_base + "/api/history?conversation_id=bad%2Fid", headers=headers), timeout=5)
                with self.assertRaises(Exception):
                    urlopen(Request(api_base + "/api/conversations?limit=abc", headers=headers), timeout=5)
                stream_payload = json.dumps({
                    "message": "اختبار البث المباشر",
                    "conversation_id": "stream-smoke"
                }).encode()
                stream_req = Request(
                    api_base + "/api/chat/stream",
                    data=stream_payload,
                    headers={"Content-Type": "application/json", **headers}
                )
                with urlopen(stream_req, timeout=10) as stream_response:
                    self.assertIn("text/event-stream", stream_response.headers.get("Content-Type", ""))
                    stream_body = stream_response.read().decode("utf-8")
                stream_events = [
                    json.loads(line[6:])
                    for line in stream_body.splitlines()
                    if line.startswith("data: ")
                ]
                token_events = [event for event in stream_events if event.get("type") == "token"]
                self.assertGreaterEqual(len(token_events), 2)
                self.assertTrue(any(event.get("type") == "done" for event in stream_events))
                streamed_answer = "".join(event["token"] for event in token_events)
                self.assertIn("إجابة اختبار حقيقية", streamed_answer)
                stream_history_req = Request(
                    api_base + "/api/history?conversation_id=stream-smoke",
                    headers=headers
                )
                with urlopen(stream_history_req, timeout=5) as stream_history_response:
                    stream_history = json.loads(stream_history_response.read())["messages"]
                self.assertEqual(len(stream_history), 2)
                self.assertEqual(stream_history[0]["content"], "اختبار البث المباشر")
                self.assertEqual(stream_history[1]["content"], streamed_answer)

                # A disconnected Android client must not leave a partial turn in SQLite.
                FakeOllamaHandler.stream_slow = True
                cancel_payload = json.dumps({
                    "message": "اختبار إلغاء البث",
                    "conversation_id": "stream-cancel"
                }).encode()
                cancel_req = Request(
                    api_base + "/api/chat/stream",
                    data=cancel_payload,
                    headers={"Content-Type": "application/json", **headers}
                )
                with urlopen(cancel_req, timeout=10) as cancel_response:
                    first_event = cancel_response.readline().decode("utf-8")
                    self.assertTrue(first_event.startswith("data: "))
                    cancel_response.readline()
                time.sleep(0.8)
                FakeOllamaHandler.stream_slow = False
                cancel_history_req = Request(
                    api_base + "/api/history?conversation_id=stream-cancel",
                    headers=headers
                )
                with urlopen(cancel_history_req, timeout=5) as cancel_history_response:
                    self.assertEqual(json.loads(cancel_history_response.read())["messages"], [])
            finally:
                FakeOllamaHandler.stream_slow = False
                FakeOllamaHandler.offline = False
                proc.terminate()
                proc.wait(timeout=5)
                server_log.close()
                fake_ollama.shutdown()
                fake_ollama.server_close()
                fake_thread.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
