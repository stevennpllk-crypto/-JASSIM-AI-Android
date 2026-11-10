"""Adaptive provider evaluation and routing for JASSIM AI.

Only synthetic prompts are used by the evaluator. Real conversation content is
sent to public providers only when JASSIM_ALLOW_EXTERNAL_CHAT=true.
"""
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(os.environ.get("JASSIM_DATA_DIR", str(Path(__file__).resolve().parent / "data"))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jassim.db"
ALLOW_EXTERNAL_CHAT = os.environ.get("JASSIM_ALLOW_EXTERNAL_CHAT", "false").lower() in ("1", "true", "yes")
ENABLE_PUBLIC_PROVIDERS = os.environ.get("JASSIM_ENABLE_PUBLIC_PROVIDERS", "true").lower() in ("1", "true", "yes")
TIMEOUT = max(8, min(int(os.environ.get("JASSIM_PROVIDER_TIMEOUT", "45")), 120))

PROVIDERS = [
    # Groq is the preferred managed candidate when an operator configures a key.
    # Its free tier is rate-limited; no paid upgrade is enabled by this code.
    {"id": "groq", "name": "Groq", "url": "https://api.groq.com/openai/v1/chat/completions", "model": "openai/gpt-oss-20b", "key_env": "GROQ_API_KEY"},
    {"id": "jarvisclaw", "name": "JarvisClaw", "url": "https://api.jarvisclaw.ai/v1/chat/completions", "model": "auto/free"},
    {"id": "ovh", "name": "OVHcloud AI", "url": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions", "model": "Meta-Llama-3_3-70B-Instruct"},
]


def _configured_providers():
    """Do not advertise or probe credentialed providers until configured."""
    return [
        provider for provider in PROVIDERS
        if not provider.get("key_env") or os.environ.get(provider["key_env"], "").strip()
    ]

EVALUATION_CASES = [
    {"messages": [{"role": "user", "content": "أجب بالعربية بكلمة واحدة: ما عاصمة تونس؟"}], "needles": ["تونس"]},
    {"messages": [{"role": "user", "content": "احسب 17 × 19، وأعطني العدد فقط."}], "needles": ["323"]},
    {"messages": [{"role": "user", "content": "Explain in one short English sentence what an API does."}], "needles": ["request", "software", "application", "communicate"]},
]


def _db():
    if os.environ.get("DATABASE_URL", "").strip():
        import storage
        db = storage.connect()
        storage.ensure_schema(db)
        return db
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.execute("""CREATE TABLE IF NOT EXISTS provider_scores (
        provider_id TEXT PRIMARY KEY,
        attempts INTEGER NOT NULL DEFAULT 0,
        successes INTEGER NOT NULL DEFAULT 0,
        avg_latency_ms REAL NOT NULL DEFAULT 0,
        quality_score REAL NOT NULL DEFAULT 0,
        last_success TEXT,
        last_error TEXT
    )""")
    return db


def _request(provider, messages, max_tokens=256):
    payload = json.dumps({
        "model": provider["model"],
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.2
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    key_env = provider.get("key_env")
    if key_env:
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            raise RuntimeError("provider_key_not_configured:" + provider["id"])
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(
        provider["url"], data=payload, headers=headers, method="POST"
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        data = json.loads(response.read(1024 * 1024).decode("utf-8"))
    answer = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")).strip()
    if not answer:
        raise RuntimeError("empty_provider_response")
    return answer, (time.monotonic() - started) * 1000


def _quality(answer, needles):
    text = answer.casefold()
    if len(answer.strip()) < 2:
        return 0.0
    matched = sum(1 for needle in needles if needle.casefold() in text)
    return 0.25 + (0.75 * matched / max(1, len(needles)))


def _record(provider_id, latency, quality, error=""):
    db = _db()
    try:
        row = db.execute("SELECT attempts, successes, avg_latency_ms, quality_score FROM provider_scores WHERE provider_id=?", (provider_id,)).fetchone()
        if row:
            attempts, successes, avg_latency, old_quality = row
            new_attempts = attempts + 1
            new_successes = successes + (1 if not error else 0)
            new_latency = latency if not attempts else (avg_latency * 0.7 + latency * 0.3)
            new_quality = quality if not attempts else (old_quality * 0.7 + quality * 0.3)
        else:
            new_attempts, new_successes, new_latency, new_quality = 1, (0 if error else 1), latency, quality
        db.execute("""INSERT INTO provider_scores(provider_id,attempts,successes,avg_latency_ms,quality_score,last_success,last_error)
            VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider_id) DO UPDATE SET
            attempts=excluded.attempts, successes=excluded.successes, avg_latency_ms=excluded.avg_latency_ms,
            quality_score=excluded.quality_score, last_success=COALESCE(excluded.last_success,provider_scores.last_success),
            last_error=excluded.last_error""",
            (provider_id, new_attempts, new_successes, new_latency, new_quality,
             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) if not error else None, error[:240]))
        db.commit()
    finally:
        db.close()


def provider_stats():
    db = _db()
    try:
        rows = db.execute("SELECT provider_id,attempts,successes,avg_latency_ms,quality_score,last_success,last_error FROM provider_scores").fetchall()
    finally:
        db.close()
    known = {row[0]: row[1:] for row in rows}
    result = []
    for provider in _configured_providers() if ENABLE_PUBLIC_PROVIDERS else []:
        values = known.get(provider["id"], (0, 0, 0, 0, None, None))
        attempts, successes, latency, quality, last_success, last_error = values
        reliability = successes / attempts if attempts else 0.5
        # Quality dominates; reliability and latency break ties.
        score = (quality * 0.65) + (reliability * 0.25) + (max(0, 1 - latency / 30000) * 0.10 if latency else 0.05)
        result.append({
            "id": provider["id"], "name": provider["name"], "model": provider["model"],
            "attempts": attempts, "successes": successes,
            "average_latency_ms": round(latency), "quality_score": round(quality, 3),
            "routing_score": round(score, 3), "last_success": last_success,
            "last_error": last_error
        })
    return sorted(result, key=lambda item: item["routing_score"], reverse=True)


def evaluate_providers():
    """Benchmark only fixed synthetic prompts; never reads user conversation data."""
    if not ENABLE_PUBLIC_PROVIDERS:
        return {"enabled": False, "tested": 0, "results": [], "message": "Public provider evaluation is disabled."}
    results = []
    for provider in _configured_providers():
        case_results = []
        for case in EVALUATION_CASES:
            try:
                answer, latency = _request(provider, case["messages"], max_tokens=120)
                quality = _quality(answer, case["needles"])
                _record(provider["id"], latency, quality)
                case_results.append({"ok": True, "latency_ms": round(latency), "quality": round(quality, 2)})
            except Exception as exc:
                _record(provider["id"], 0, 0, type(exc).__name__ + ": " + str(exc))
                case_results.append({"ok": False, "error": type(exc).__name__})
        results.append({"provider": provider["id"], "cases": case_results})
    return {"enabled": True, "tested": len(results), "results": results, "ranking": provider_stats()}


def answer_with_provider(messages):
    """Route real chat only after an explicit server-side privacy opt-in."""
    if not ALLOW_EXTERNAL_CHAT or not ENABLE_PUBLIC_PROVIDERS:
        raise RuntimeError("external_chat_disabled")
    ranked = provider_stats()
    by_id = {item["id"]: item for item in _configured_providers()}
    errors = []
    for item in ranked:
        provider = by_id[item["id"]]
        try:
            answer, latency = _request(provider, messages, max_tokens=2048)
            _record(provider["id"], latency, 0.65)
            return answer, provider["id"]
        except Exception as exc:
            _record(provider["id"], 0, 0, type(exc).__name__ + ": " + str(exc))
            errors.append(provider["id"])
    raise RuntimeError("all_external_providers_failed:" + ",".join(errors))


def external_chat_enabled():
    return ALLOW_EXTERNAL_CHAT and ENABLE_PUBLIC_PROVIDERS
