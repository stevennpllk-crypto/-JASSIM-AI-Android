"""Synthetic benchmark helpers and guarded provider-routing code for JASSIM AI.

Public-provider routing is hard-disabled in this build. This module does not
claim that a local Ollama model is installed, reachable, or benchmarked.
"""
import ast
import json
import os
import re
import sqlite3
import statistics
import unicodedata
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(os.environ.get("JASSIM_DATA_DIR", str(Path(__file__).resolve().parent / "data"))).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "jassim.db"
# Privacy boundary: real prompts and inference must remain on our Ollama host.
# Public model providers are deliberately hard-disabled; environment variables
# cannot silently turn external inference back on.
ALLOW_EXTERNAL_CHAT = False
ENABLE_PUBLIC_PROVIDERS = False
TIMEOUT = max(8, min(int(os.environ.get("JASSIM_PROVIDER_TIMEOUT", "45")), 120))
# Keep fallback attempts bounded so one unavailable public provider cannot make
# a single chat request wait through several full provider timeouts.
PROVIDER_ATTEMPT_TIMEOUT = max(
    3, min(int(os.environ.get("JASSIM_PROVIDER_ATTEMPT_TIMEOUT", "12")), 60)
)
PROVIDER_TOTAL_TIMEOUT = max(
    8, min(int(os.environ.get("JASSIM_PROVIDER_TOTAL_TIMEOUT", "35")), 90)
)

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

BENCHMARK_VERSION = "jassim-core-2026-11-v1"
EVALUATION_CASES = [
    {"id":"ar_capital_01","category":"arabic","messages":[{"role":"user","content":"أجب بكلمة واحدة فقط: ما عاصمة تونس؟"}],"grader":"exact","expected":"تونس"},
    {"id":"math_multiply_01","category":"math","messages":[{"role":"user","content":"احسب 17 × 19. أعد العدد فقط دون شرح."}],"grader":"number","expected":323},
    {"id":"math_multistep_01","category":"reasoning","messages":[{"role":"user","content":"لدي 4 صناديق، في كل صندوق 12 كرة، ثم أضفت 7 كرات. كم كرة لدي؟ أجب بالعدد فقط."}],"grader":"number","expected":55},
    {"id":"logic_chain_01","category":"reasoning","messages":[{"role":"user","content":"كل الزهور في الحديقة حمراء. الوردة زهرة في الحديقة. ما لون الوردة؟ أجب بكلمة واحدة."}],"grader":"exact","expected":"حمراء"},
    {"id":"json_schema_01","category":"instructions","messages":[{"role":"user","content":"أخرج JSON صالحاً فقط بهذا الشكل: {\"name\":\"Ali\",\"age\":16}. لا تضف أي نص."}],"grader":"json","expected":{"name":"Ali","age":16}},
    {"id":"python_ast_01","category":"coding","messages":[{"role":"user","content":"اكتب كود Python فقط لتعريف دالة اسمها add تأخذ a و b وتعيد a + b."}],"grader":"python_add"},
    {"id":"english_api_01","category":"multilingual","messages":[{"role":"user","content":"In one short English sentence, explain what an API lets software do. Include the words request and response."}],"grader":"contains","expected":["request","response"]},
    {"id":"french_translation_01","category":"multilingual","messages":[{"role":"user","content":"ترجم كلمة Hello إلى الفرنسية. أجب بكلمة واحدة."}],"grader":"exact","expected":"bonjour"}
]


def _normalize_benchmark_text(value):
    value = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    value = re.sub(r"^[\s\W_]+|[\s\W_]+$", "", value)
    return re.sub(r"\s+", " ", value)


def _grade_benchmark_case(case, answer):
    grader = case["grader"]
    if grader == "exact":
        return _normalize_benchmark_text(answer) == _normalize_benchmark_text(case["expected"])
    if grader == "number":
        normalized_answer = str(answer).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")).strip()
        # The prompt requests a number only: reject explanations and extra numbers.
        if not re.fullmatch(r"[-+]?\d+(?:[.٫]\d+)?", normalized_answer):
            return False
        return abs(float(normalized_answer.replace("٫", ".")) - float(case["expected"])) <= 1e-9
    if grader == "json":
        candidate = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", str(answer).strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError):
            return False
        return isinstance(parsed, dict) and parsed == case["expected"]
    if grader == "python_add":
        candidate = re.sub(r"^\s*```(?:python)?\s*|\s*```\s*$", "", str(answer).strip(), flags=re.IGNORECASE)
        try:
            tree = ast.parse(candidate)
        except (SyntaxError, ValueError, TypeError):
            return False
        # Accept only the requested single, plain function definition.
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            return False
        fn = tree.body[0]
        if fn.name != "add" or fn.decorator_list or fn.returns is not None:
            return False
        if (fn.args.posonlyargs or [arg.arg for arg in fn.args.args] != ["a", "b"]
                or fn.args.vararg or fn.args.kwonlyargs or fn.args.kwarg
                or fn.args.defaults or fn.args.kw_defaults):
            return False
        if len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return):
            return False
        expr = fn.body[0].value
        return isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add) and isinstance(expr.left, ast.Name) and expr.left.id == "a" and isinstance(expr.right, ast.Name) and expr.right.id == "b"
    if grader == "contains":
        normalized = _normalize_benchmark_text(answer)
        return all(
            re.search(
                r"(?<!\w)" + re.escape(_normalize_benchmark_text(word)) + r"(?!\w)",
                normalized,
            ) is not None
            for word in case["expected"]
        )
    return False


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


def _request(provider, messages, max_tokens=256, timeout=None):
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
    request_timeout = TIMEOUT if timeout is None else max(1.0, min(float(timeout), float(TIMEOUT)))
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        data = json.loads(response.read(1024 * 1024).decode("utf-8"))
    answer = str((((data.get("choices") or [{}])[0]).get("message") or {}).get("content", "")).strip()
    if not answer:
        raise RuntimeError("empty_provider_response")
    return answer, (time.monotonic() - started) * 1000



def _stream_request(provider, messages, max_tokens=2048, timeout=None, on_delta=None):
    """Read OpenAI-compatible SSE and emit text deltas as soon as they arrive."""
    payload = json.dumps({
        "model": provider["model"], "messages": messages, "stream": True,
        "max_tokens": max_tokens, "temperature": 0.2
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    key_env = provider.get("key_env")
    if key_env:
        api_key = os.environ.get(key_env, "").strip()
        if not api_key:
            raise RuntimeError("provider_key_not_configured:" + provider["id"])
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(provider["url"], data=payload, headers=headers, method="POST")
    started = time.monotonic()
    request_timeout = TIMEOUT if timeout is None else max(1.0, min(float(timeout), float(TIMEOUT)))
    parts = []
    saw_done = False
    with urllib.request.urlopen(request, timeout=request_timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                saw_done = True
                break
            try:
                item = json.loads(data)
            except json.JSONDecodeError as exc:
                raise RuntimeError("invalid_provider_stream_event") from exc
            if item.get("error"):
                raise RuntimeError("provider_stream_error")
            choices = item.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            token = delta.get("content")
            if token is None and choice.get("message"):
                # Some compatible endpoints ignore stream=true and return JSON.
                token = choice["message"].get("content", "")
            if isinstance(token, str) and token:
                parts.append(token)
                if on_delta:
                    on_delta(token)
            if choice.get("finish_reason"):
                saw_done = True
                break
    answer = "".join(parts).strip()
    if not answer:
        raise RuntimeError("empty_provider_stream")
    if not saw_done:
        raise RuntimeError("incomplete_provider_stream")
    return answer, (time.monotonic() - started) * 1000


def stream_answer_with_provider(messages, on_delta):
    """Try providers in rank order; never switch after text reached the client."""
    if not ALLOW_EXTERNAL_CHAT or not ENABLE_PUBLIC_PROVIDERS:
        raise RuntimeError("external_chat_disabled")
    ranked = provider_stats()
    by_id = {item["id"]: item for item in _configured_providers()}
    errors = []
    deadline = time.monotonic() + PROVIDER_TOTAL_TIMEOUT
    for item in ranked:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            errors.append("provider_budget_exhausted")
            break
        provider = by_id[item["id"]]
        attempt_timeout = min(PROVIDER_ATTEMPT_TIMEOUT, remaining, TIMEOUT)
        emitted = []
        try:
            answer, latency = _stream_request(
                provider, messages, max_tokens=2048, timeout=attempt_timeout,
                on_delta=lambda token: (emitted.append(token), on_delta(token))
            )
            _record(provider["id"], latency, None)
            return answer, provider["id"]
        except Exception as exc:
            _record(provider["id"], 0, None, type(exc).__name__ + ": " + str(exc))
            if emitted:
                raise RuntimeError("provider_stream_interrupted:" + provider["id"]) from exc
            errors.append(provider["id"])
    raise RuntimeError("all_external_providers_failed:" + ",".join(errors))


def _record(provider_id, latency, quality=None, error=""):
    db = _db()
    try:
        row = db.execute("SELECT attempts, successes, avg_latency_ms, quality_score FROM provider_scores WHERE provider_id=?", (provider_id,)).fetchone()
        if row:
            attempts, successes, avg_latency, old_quality = row
            new_attempts = attempts + 1
            new_successes = successes + (1 if not error else 0)
            # Failed requests do not make a provider appear faster, and live
            # chat has no ground-truth label from which to infer answer quality.
            new_latency = (
                latency if not attempts else
                (avg_latency * 0.7 + latency * 0.3 if not error and latency > 0 else avg_latency)
            )
            new_quality = (
                old_quality if quality is None else
                (quality if not attempts else old_quality * 0.7 + quality * 0.3)
            )
        else:
            new_attempts = 1
            new_successes = 0 if error else 1
            new_latency = latency if not error and latency > 0 else 0
            new_quality = 0 if quality is None else quality
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
        # Route on observable service behavior only. Answer quality requires
        # benchmark labels and must never be inferred from live-chat success.
        latency_score = max(0, 1 - latency / 30000) if latency else 0.5
        score = (reliability * 0.75) + (latency_score * 0.25)
        result.append({
            "id": provider["id"], "name": provider["name"], "model": provider["model"],
            "attempts": attempts, "successes": successes,
            "average_latency_ms": round(latency), "quality_score": round(quality, 3),
            "routing_score": round(score, 3), "last_success": last_success,
            "last_error": last_error
        })
    return sorted(result, key=lambda item: item["routing_score"], reverse=True)


def evaluate_providers():
    """Run versioned deterministic checks against synthetic prompts only."""
    if not ENABLE_PUBLIC_PROVIDERS:
        return {"enabled": False, "benchmark_version": BENCHMARK_VERSION, "tested": 0, "results": [], "message": "Public provider evaluation is disabled."}
    results = []
    for provider in _configured_providers():
        case_results, latencies = [], []
        category_totals, failures = {}, 0
        for case in EVALUATION_CASES:
            category = category_totals.setdefault(case["category"], {"passed": 0, "total": 0})
            category["total"] += 1
            try:
                answer, latency = _request(provider, case["messages"], max_tokens=256)
                passed = _grade_benchmark_case(case, answer)
                latencies.append(latency)
                category["passed"] += int(passed)
                _record(provider["id"], latency, 1.0 if passed else 0.0)
                case_results.append({"id": case["id"], "category": case["category"], "passed": passed, "latency_ms": round(latency)})
            except Exception as exc:
                failures += 1
                _record(provider["id"], 0, None, type(exc).__name__ + ": " + str(exc))
                case_results.append({"id": case["id"], "category": case["category"], "passed": False, "error": type(exc).__name__})
        ordered = sorted(latencies)
        p95 = ordered[max(0, int(len(ordered) * 0.95 + 0.999999) - 1)] if ordered else None
        total, passed_count = len(case_results), sum(1 for item in case_results if item["passed"])
        results.append({
            "provider": provider["id"], "benchmark_version": BENCHMARK_VERSION,
            "pass_rate": round(passed_count / total, 3) if total else 0,
            "median_latency_ms": round(statistics.median(latencies)) if latencies else None,
            "p95_latency_ms": round(p95) if p95 is not None else None,
            "error_rate": round(failures / total, 3) if total else 0,
            "categories": {name: {"passed": values["passed"], "total": values["total"], "pass_rate": round(values["passed"] / values["total"], 3)} for name, values in category_totals.items()},
            "cases": case_results
        })
    return {"enabled": True, "benchmark_version": BENCHMARK_VERSION, "case_count": len(EVALUATION_CASES), "tested": len(results), "results": results, "routing": provider_stats()}


def answer_with_provider(messages):
    """Route real chat only after an explicit server-side privacy opt-in."""
    if not ALLOW_EXTERNAL_CHAT or not ENABLE_PUBLIC_PROVIDERS:
        raise RuntimeError("external_chat_disabled")
    ranked = provider_stats()
    by_id = {item["id"]: item for item in _configured_providers()}
    errors = []
    deadline = time.monotonic() + PROVIDER_TOTAL_TIMEOUT
    for item in ranked:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            errors.append("provider_budget_exhausted")
            break
        provider = by_id[item["id"]]
        attempt_timeout = min(PROVIDER_ATTEMPT_TIMEOUT, remaining, TIMEOUT)
        try:
            answer, latency = _request(
                provider, messages, max_tokens=2048, timeout=attempt_timeout
            )
            _record(provider["id"], latency, None)
            return answer, provider["id"]
        except Exception as exc:
            _record(provider["id"], 0, None, type(exc).__name__ + ": " + str(exc))
            errors.append(provider["id"])
    raise RuntimeError("all_external_providers_failed:" + ",".join(errors))


def external_chat_enabled():
    return ALLOW_EXTERNAL_CHAT and ENABLE_PUBLIC_PROVIDERS
