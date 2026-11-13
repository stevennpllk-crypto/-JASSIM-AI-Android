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
    def test_ollama_endpoint_rejects_public_hosts(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_private_endpoint_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir
        original = module.OLLAMA_URL
        try:
            for url in ("https://api.example.com", "http://example.com:11434",
                        "http://user:pass@ollama.railway.internal:11434",
                        "http://ollama.railway.internal/path"):
                module.OLLAMA_URL = url
                self.assertFalse(module.ollama_endpoint_is_private(), url)
                self.assertFalse(module.ollama_status()["reachable"], url)
            for url in ("http://127.0.0.1:11434", "http://ollama.railway.internal:11434"):
                module.OLLAMA_URL = url
                self.assertTrue(module.ollama_endpoint_is_private(), url)
        finally:
            module.OLLAMA_URL = original

    def test_ollama_requests_reject_public_hosts_and_never_follow_redirects(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_ollama_redirect_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        original = module.OLLAMA_URL
        try:
            module.OLLAMA_URL = "http://example.com:11434"
            with patch.object(module._OLLAMA_OPENER, "open") as opener:
                with self.assertRaisesRegex(RuntimeError, "ollama_endpoint_must_be_private"):
                    module.open_ollama(Request("http://example.com:11434/api/chat"), timeout=1)
                opener.assert_not_called()
        finally:
            module.OLLAMA_URL = original

        handler = module._NoOllamaRedirects()
        self.assertIsNone(handler.redirect_request(
            None, None, 307, "Temporary Redirect", {}, "https://example.com/collect"
        ))

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

    def test_generate_answer_falls_back_only_after_local_ollama_failure(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location("jassim_fallback_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        messages = [{"role": "user", "content": "synthetic fallback test"}]
        with patch.object(module, "ollama_status", return_value={
            "reachable": True, "model_ready": True, "model_loaded": True
        }):
            with patch.object(module, "ask_ollama", side_effect=RuntimeError("local model unavailable")):
                with patch.object(module.adaptive, "external_chat_enabled", return_value=True), \
                     patch.object(module.adaptive, "answer_with_provider",
                                  return_value=("JASSIM ONLINE", "jarvisclaw")) as fallback:
                    answer, engine = module.generate_answer(messages)
                self.assertEqual(answer, "JASSIM ONLINE")
                self.assertEqual(engine, "jarvisclaw")
                fallback.assert_called_once()

            with patch.object(module, "ask_ollama", return_value="LOCAL ANSWER"):
                with patch.object(module.adaptive, "answer_with_provider") as fallback:
                    answer, engine = module.generate_answer(messages)
                self.assertEqual(answer, "LOCAL ANSWER")
                self.assertEqual(engine, "ollama")
                fallback.assert_not_called()

    def test_private_mode_does_not_attempt_external_fallback(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_private_mode_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        messages = [{"role": "user", "content": "private synthetic test"}]
        with patch.object(module.adaptive, "external_chat_enabled", return_value=False):
            with patch.object(module.adaptive, "answer_with_provider",
                              side_effect=AssertionError("external inference must not be called")) as external:
                answer, engine = module.answer_with_external_fallback(messages)
        self.assertEqual(engine, "fallback")
        self.assertIn("لم يتم إرسال رسالتك", answer)
        external.assert_not_called()

        class StubHandler:
            def __init__(self):
                self.error = None
            def send_json(self, status, payload):
                self.error = (status, payload)

        stub = StubHandler()
        with patch.object(module.adaptive, "external_chat_enabled", return_value=False):
            with patch.object(module.adaptive, "stream_answer_with_provider",
                              side_effect=AssertionError("external stream must not be called")) as stream:
                module.Handler.stream_external_provider_response(
                    stub, "conversation-test", "question", [], "user-test")
        self.assertEqual(stub.error[0], 503)
        self.assertIn("لم يتم إرسال رسالتك", stub.error[1]["message"])
        stream.assert_not_called()

    def test_generate_answer_skips_unavailable_local_model_immediately(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_fast_fallback_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        messages = [{"role": "user", "content": "synthetic fast fallback test"}]
        with patch.object(module, "ollama_status", return_value={
            "reachable": False, "model_ready": False, "model_loaded": False
        }):
            with patch.object(module, "ask_ollama") as local_model:
                with patch.object(module.adaptive, "external_chat_enabled", return_value=True), \
                     patch.object(module.adaptive, "answer_with_provider",
                                  return_value=("FAST JASSIM ANSWER", "jarvisclaw")) as fallback:
                    answer, engine = module.generate_answer(messages)
                self.assertEqual(answer, "FAST JASSIM ANSWER")
                self.assertEqual(engine, "jarvisclaw")
                local_model.assert_not_called()
                fallback.assert_called_once()

    def test_stream_chat_uses_fallback_without_waiting_for_unavailable_ollama(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_stream_fallback_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        class StubHandler:
            def __init__(self):
                self.stream_result = None
                self.error_result = None

            def stream_external_provider_response(self, conversation_id, message, context, user_id):
                self.stream_result = ("live-stream", conversation_id, user_id)

            def send_json(self, status, payload):
                self.error_result = (status, payload)

        stub = StubHandler()
        context = [{"role": "user", "content": "synthetic streaming fallback test"}]
        with patch.object(module, "ollama_status", return_value={
            "reachable": False, "model_ready": False, "model_loaded": False
        }):
            with patch.object(module.adaptive, "external_chat_enabled", return_value=True), \
                     patch.object(module.adaptive, "stream_answer_with_provider",
                                  return_value=("STREAM FALLBACK ANSWER", "jarvisclaw")) as fallback:
                module.Handler.stream_chat_response(
                    stub, "conversation-test", "question", context, "user-test")
        self.assertEqual(stub.stream_result,
                         ("live-stream", "conversation-test", "user-test"))
        self.assertIsNone(stub.error_result)
        fallback.assert_not_called()

    def test_external_provider_stream_sends_tokens_and_persists_complete_turn(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_provider_stream_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        class StubHandler:
            def __init__(self):
                self.events = []
                self.headers_sent = 0
                self.errors = []
            def client_disconnected(self):
                return False
            def send_sse_headers(self):
                self.headers_sent += 1
            def send_sse_event(self, event):
                self.events.append(event)
            def send_json(self, status, payload):
                self.errors.append((status, payload))

        stub = StubHandler()
        def fake_stream(messages, emit):
            emit("Hello ")
            emit("world")
            return "Hello world", "provider-test"
        with patch.object(module.adaptive, "external_chat_enabled", return_value=True), \
             patch.object(module.adaptive, "stream_answer_with_provider", side_effect=fake_stream):
            with patch.object(module, "save_turn") as save:
                module.Handler.stream_external_provider_response(
                    stub, "conversation-test", "question", [], "user-test")
        save.assert_called_once_with("conversation-test", "question", "Hello world", "user-test")
        self.assertEqual(stub.headers_sent, 1)
        self.assertEqual([event["type"] for event in stub.events], ["token", "token", "done"])
        self.assertEqual("".join(event.get("token", "") for event in stub.events), "Hello world")
        self.assertEqual(stub.events[-1]["engine"], "provider-test")
        self.assertEqual(save.call_count, 1)
        self.assertEqual(stub.errors, [])

    def test_interrupted_external_stream_is_not_persisted_as_complete(self):
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_interrupted_stream_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

        class StubHandler:
            def __init__(self):
                self.events = []
                self.headers_sent = 0
                self.errors = []
            def client_disconnected(self):
                return False
            def send_sse_headers(self):
                self.headers_sent += 1
            def send_sse_event(self, event):
                self.events.append(event)
            def send_json(self, status, payload):
                self.errors.append((status, payload))

        stub = StubHandler()
        def interrupted(messages, emit):
            emit("partial")
            raise RuntimeError("upstream interrupted")
        with patch.object(module.adaptive, "external_chat_enabled", return_value=True), \
             patch.object(module.adaptive, "stream_answer_with_provider", side_effect=interrupted):
            with patch.object(module, "save_turn") as save:
                module.Handler.stream_external_provider_response(
                    stub, "conversation-test", "question", [], "user-test")
        self.assertEqual(stub.headers_sent, 1)
        self.assertEqual([event["type"] for event in stub.events], ["token", "error"])
        save.assert_not_called()
        self.assertEqual(stub.errors, [])

    def test_save_turn_rolls_back_user_message_when_assistant_insert_fails(self):
        import importlib.util
        with tempfile.TemporaryDirectory() as tmp:
            previous_data_dir = os.environ.get("JASSIM_DATA_DIR")
            os.environ["JASSIM_DATA_DIR"] = tmp
            try:
                spec = importlib.util.spec_from_file_location(
                    "jassim_atomic_turn_test", Path(__file__).with_name("server.py"))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                db = module.connect_db()
                try:
                    db.execute("""
                        CREATE TRIGGER reject_assistant_message
                        BEFORE INSERT ON messages
                        WHEN NEW.role = 'assistant'
                        BEGIN
                            SELECT RAISE(ABORT, 'simulated assistant persistence failure');
                        END
                    """)
                    db.commit()
                finally:
                    db.close()

                with self.assertRaises(Exception):
                    module.save_turn("atomic-test", "user prompt", "assistant reply", "user-test")

                db = module.connect_db()
                try:
                    self.assertEqual(
                        db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?",
                                   ("atomic-test",)).fetchone()[0], 0)
                    self.assertEqual(
                        db.execute("SELECT COUNT(*) FROM conversations WHERE conversation_id=?",
                                   ("atomic-test",)).fetchone()[0], 0)
                finally:
                    db.close()
            finally:
                if previous_data_dir is None:
                    os.environ.pop("JASSIM_DATA_DIR", None)
                else:
                    os.environ["JASSIM_DATA_DIR"] = previous_data_dir

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
        from unittest.mock import patch
        module.INFERENCE_SEMAPHORE.acquire()
        module.OLLAMA_QUEUE_TIMEOUT = 0.01
        try:
            with patch.object(module, "ollama_status", return_value={
                "reachable": True, "model_ready": True, "model_loaded": True
            }):
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
