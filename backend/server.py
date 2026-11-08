#!/usr/bin/env python3
"""JASSIM AI self-hosted API. Standard-library only; safe localhost default."""
import json
import os
import sqlite3
import threading
import time
import re
import hmac
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("JASSIM_DATA_DIR", str(ROOT / "data"))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jassim.db"
HOST = os.environ.get("JASSIM_HOST", "127.0.0.1")
PORT = int(os.environ.get("JASSIM_PORT", "8787"))
CORS_ORIGIN = os.environ.get("JASSIM_CORS_ORIGIN", "null")
API_TOKEN = os.environ.get("JASSIM_API_TOKEN", "").strip()
OLLAMA_URL = os.environ.get("JASSIM_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("JASSIM_OLLAMA_MODEL", "qwen2.5:0.5b")
MAX_MESSAGE_CHARS = 8000
DB_LOCK = threading.Lock()
RATE_LOCK = threading.Lock()
RATE_BUCKETS = {}
RATE_LIMIT = int(os.environ.get("JASSIM_RATE_LIMIT_PER_MINUTE", "20"))
RATE_WINDOW = 60
SYSTEM_PROMPT = (
    "You are JASSIM AI, a helpful Arabic-first assistant. "
    "Reply naturally in the user's language, including Tunisian Arabic when appropriate. "
    "Be honest about uncertainty and never claim to have performed actions you did not perform."
)

def connect_db():
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)")
    return db

def history(conversation_id, limit=12):
    with DB_LOCK:
        db = connect_db()
        try:
            rows = db.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit)
            ).fetchall()
            return [{"role": role, "content": content} for role, content in reversed(rows)]
        finally:
            db.close()

def save_message(conversation_id, role, content):
    with DB_LOCK:
        db = connect_db()
        try:
            db.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at) VALUES(?,?,?,?)",
                (conversation_id, role, content, datetime.now(timezone.utc).isoformat())
            )
            db.commit()
        finally:
            db.close()

def ask_ollama(messages):
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "stream": False
    }).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL.rstrip("/") + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read().decode("utf-8"))
    answer = (result.get("message") or {}).get("content", "").strip()
    if not answer:
        raise RuntimeError("محرك Ollama لم يُرجع إجابة.")
    return answer

def ollama_status():
    """Return a bounded, non-sensitive model readiness check."""
    request = urllib.request.Request(OLLAMA_URL.rstrip("/") + "/api/tags", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = payload.get("models", [])
        names = [item.get("name", "") for item in models if isinstance(item, dict)]
        ready = any(name == OLLAMA_MODEL or name.startswith(OLLAMA_MODEL + ":") for name in names)
        return {"reachable": True, "model_ready": ready}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return {"reachable": False, "model_ready": False}


def generate_answer(messages):
    try:
        return ask_ollama(messages), "ollama"
    except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError, OSError):
        # Never echo a user's private message as if it were an AI answer.
        return (
            "محرك الذكاء الاصطناعي غير متاح حالياً. "
            "الخادم استقبل طلبك، لكن لم يتمكن من توليد إجابة من النموذج. "
            "تحقق من تشغيل Ollama وتحميل النموذج ثم أعد المحاولة."
        ), "fallback"

class Handler(BaseHTTPRequestHandler):
    server_version = "JASSIM-AI/0.1"

    def log_message(self, fmt, *args):
        print("[JASSIM] " + (fmt % args))

    def send_json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def end_headers(self):
        origin = self.headers.get("Origin")
        if origin and CORS_ORIGIN not in ("", "null") and origin == CORS_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Vary", "Origin")
        super().end_headers()

    def authorized(self):
        if not API_TOKEN:
            return False
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + API_TOKEN
        return hmac.compare_digest(supplied, expected)

    def rate_limited(self):
        now = time.time()
        client = self.client_address[0]
        with RATE_LOCK:
            hits = [stamp for stamp in RATE_BUCKETS.get(client, []) if now - stamp < RATE_WINDOW]
            if len(hits) >= RATE_LIMIT:
                RATE_BUCKETS[client] = hits
                return True
            hits.append(now)
            RATE_BUCKETS[client] = hits
            if len(RATE_BUCKETS) > 5000:
                for key in list(RATE_BUCKETS)[:1000]:
                    RATE_BUCKETS.pop(key, None)
            return False

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            model_state = ollama_status()
            self.send_json(200, {
                "ok": True,
                "service": "JASSIM AI",
                "version": "0.2.0",
                "engine": "ollama",
                "model": OLLAMA_MODEL,
                "model_ready": model_state["model_ready"],
                "ollama_reachable": model_state["reachable"],
                "storage": "sqlite",
                "authentication": "configured" if API_TOKEN else "not-configured"
            })
            return
        if parsed.path == "/api/models":
            if not self.authorized():
                self.send_json(401, {"error": "unauthorized"})
                return
            if self.rate_limited():
                self.send_json(429, {"error": "rate_limit_exceeded", "retry_after_seconds": 60})
                return
            request = urllib.request.Request(OLLAMA_URL.rstrip("/") + "/api/tags", method="GET")
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                models = [
                    {"name": item.get("name", ""), "size": item.get("size", 0)}
                    for item in payload.get("models", []) if isinstance(item, dict)
                ]
                self.send_json(200, {"models": models, "active_model": OLLAMA_MODEL})
            except (urllib.error.URLError, TimeoutError, ValueError, OSError):
                self.send_json(503, {"error": "model_engine_unavailable"})
            return
        if parsed.path == "/api/history":
            if not self.authorized():
                self.send_json(401, {"error": "unauthorized"})
                return
            if self.rate_limited():
                self.send_json(429, {"error": "rate_limit_exceeded", "retry_after_seconds": 60})
                return
            conversation_id = parse_qs(parsed.query).get("conversation_id", ["default"])[0]
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", conversation_id):
                self.send_json(400, {"error": "invalid_conversation_id"})
                return
            self.send_json(200, {"conversation_id": conversation_id, "messages": history(conversation_id, 100)})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            self.send_json(404, {"error": "not_found"})
            return
        if not self.authorized():
            self.send_json(503 if not API_TOKEN else 401, {"error": "authentication_not_configured" if not API_TOKEN else "unauthorized"})
            return
        if self.rate_limited():
            self.send_json(429, {"error": "rate_limit_exceeded", "retry_after_seconds": 60})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536:
                self.send_json(413, {"error": "invalid_body_size"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                self.send_json(400, {"error": "json_object_required"})
                return
            message = str(body.get("message", "")).strip()
            conversation_id = str(body.get("conversation_id", "default")).strip()[:100] or "default"
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", conversation_id):
                self.send_json(400, {"error": "invalid_conversation_id"})
                return
            if not message:
                self.send_json(400, {"error": "message_required"})
                return
            if len(message) > MAX_MESSAGE_CHARS:
                self.send_json(413, {"error": "message_too_long", "limit": MAX_MESSAGE_CHARS})
                return
            save_message(conversation_id, "user", message)
            context = history(conversation_id, 12)
            answer, engine = generate_answer(context)
            save_message(conversation_id, "assistant", answer)
            self.send_json(200, {
                "answer": answer, "reply": answer,
                "conversation_id": conversation_id, "engine": engine
            })
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            self.send_json(400, {"error": "bad_request", "detail": str(exc)})

def main():
    connect_db().close()
    print(f"JASSIM AI API v0.2.0 listening on http://{HOST}:{PORT}")
    print(f"Persistent database: {DB_PATH}")
    print(f"Ollama model: {OLLAMA_MODEL} ({OLLAMA_URL})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
