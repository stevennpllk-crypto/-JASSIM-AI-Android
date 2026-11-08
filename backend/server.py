#!/usr/bin/env python3
"""JASSIM AI self-hosted API. Standard-library only; safe localhost default."""
import json
import os
import sqlite3
import threading
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
OLLAMA_URL = os.environ.get("JASSIM_OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("JASSIM_OLLAMA_MODEL", "qwen2.5:0.5b")
MAX_MESSAGE_CHARS = 8000
DB_LOCK = threading.Lock()
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

def generate_answer(messages):
    try:
        return ask_ollama(messages), "ollama"
    except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError, OSError) as exc:
        # Explicit fallback: do not pretend this is an LLM response.
        last = messages[-1]["content"] if messages else ""
        return (
            "خادم JASSIM يعمل ويحفظ المحادثة، لكن محرك النموذج غير متصل حالياً. "
            "لتفعيل الإجابات الذكية شغّل Ollama على جهاز يدعم النموذج ثم أعد المحاولة. "
            "رسالتك وصلت: " + last[:500]
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

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self.send_json(200, {
                "ok": True, "service": "JASSIM AI", "version": "0.1.0",
                "engine": "ollama-configured" if OLLAMA_URL else "not-configured",
                "storage": "sqlite", "database": str(DB_PATH)
            })
            return
        if parsed.path == "/api/history":
            conversation_id = parse_qs(parsed.query).get("conversation_id", ["default"])[0]
            self.send_json(200, {"conversation_id": conversation_id, "messages": history(conversation_id, 100)})
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat":
            self.send_json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 65536:
                self.send_json(413, {"error": "invalid_body_size"})
                return
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            message = str(body.get("message", "")).strip()
            conversation_id = str(body.get("conversation_id", "default")).strip()[:100] or "default"
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
    print(f"JASSIM AI API listening on http://{HOST}:{PORT}")
    print(f"Persistent database: {DB_PATH}")
    print(f"Ollama model: {OLLAMA_MODEL} ({OLLAMA_URL})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
