#!/usr/bin/env python3
"""Compare already-installed Ollama models using synthetic JASSIM evaluation cases.

This tool never pulls model weights and refuses public Ollama URLs.
"""
import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

import adaptive

DEFAULT_MODELS = [
    "qwen3.5:4b",
    "qwen3.5:9b",
    "gemma3:12b",
    "mistral-small3.2:24b",
    "llama3.3:70b",
]


def is_private_ollama_url(value):
    try:
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        private_host = (
            host in ("localhost", "127.0.0.1", "::1")
            or host.endswith(".railway.internal")
        )
        if (
            parsed.scheme != "http"
            or not private_host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            return False
        return parsed.port is None or 1 <= parsed.port <= 65535
    except (TypeError, ValueError):
        return False


def is_private_ollama_request_url(value):
    """Allow only known Ollama API paths on a private host, without URL extras."""
    try:
        parsed = urlparse(value)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return (
            is_private_ollama_url(base)
            and parsed.path in ("/api/chat", "/api/tags", "/api/ps")
            and not parsed.query
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        return False


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not let a private Ollama URL redirect benchmark prompts elsewhere."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_PRIVATE_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler)


def request_json(url, payload=None, timeout=240):
    if not is_private_ollama_request_url(url):
        raise ValueError("Refusing non-private or malformed Ollama request URL.")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=headers, method="GET" if data is None else "POST"
    )
    with _PRIVATE_OPENER.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def run_benchmark(base_url, model, cases, timeout):
    if not is_private_ollama_url(base_url):
        raise ValueError("Refusing non-private Ollama URL; no prompt was sent.")
    results = []
    for case in cases:
        started = time.perf_counter()
        try:
            response = request_json(
                base_url.rstrip("/") + "/api/chat",
                {
                    "model": model,
                    "messages": case["messages"],
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {
                        "temperature": 0,
                        "num_ctx": 4096,
                        "num_predict": 256,
                    },
                },
                timeout=timeout,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            answer = response.get("message", {}).get("content", "")
            passed = adaptive._grade_benchmark_case(case, answer)
            eval_count = int(response.get("eval_count") or 0)
            eval_duration = int(response.get("eval_duration") or 0)
            results.append({
                "case_id": case["id"],
                "category": case["category"],
                "passed": bool(passed),
                "latency_ms": round(elapsed_ms, 2),
                "prompt_tokens": int(response.get("prompt_eval_count") or 0),
                "completion_tokens": eval_count,
                "tokens_per_second": round(eval_count / (eval_duration / 1e9), 2)
                    if eval_duration > 0 else None,
                "answer": answer,
            })
        except Exception as exc:
            results.append({
                "case_id": case["id"],
                "category": case["category"],
                "passed": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error": type(exc).__name__ + ": " + str(exc)[:240],
            })

    completed = [item for item in results if "error" not in item]
    latencies = [item["latency_ms"] for item in completed]
    speeds = [item["tokens_per_second"] for item in completed
              if item.get("tokens_per_second") is not None]
    passed = sum(1 for item in completed if item["passed"])
    return {
        "model": model,
        "case_count": len(cases),
        "completed": len(completed),
        "passed": passed,
        "pass_rate": round(passed / len(completed), 4) if completed else 0,
        "median_latency_ms": round(statistics.median(latencies), 2) if latencies else None,
        "p95_latency_ms": percentile(latencies, 0.95),
        "mean_tokens_per_second": round(statistics.mean(speeds), 2) if speeds else None,
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("JASSIM_OLLAMA_URL", "http://127.0.0.1:11434"),
        help="Private Ollama base URL only (loopback or *.railway.internal).",
    )
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated model tags already installed in Ollama; no model is pulled.",
    )
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--output", default="local-model-benchmark.json")
    args = parser.parse_args()

    if not is_private_ollama_url(args.url):
        raise SystemExit("Refusing non-private Ollama URL; no network request was made.")

    base_url = args.url.rstrip("/")
    tags = request_json(base_url + "/api/tags", timeout=min(args.timeout, 10))
    installed = {
        item.get("name", "")
        for item in tags.get("models", [])
        if isinstance(item, dict)
    }
    requested = [name.strip() for name in args.models.split(",") if name.strip()]
    cases = adaptive.EVALUATION_CASES
    reports = []
    for model in requested:
        if model not in installed:
            reports.append({
                "model": model,
                "status": "not_installed",
                "message": "Model not found in local Ollama; it was not downloaded.",
            })
            continue
        reports.append({
            "status": "tested",
            **run_benchmark(base_url, model, cases, args.timeout),
        })

    output = {
        "benchmark_version": adaptive.BENCHMARK_VERSION,
        "policy": "synthetic_prompts_only_private_ollama_no_model_downloads",
        "model_count": len(requested),
        "case_count": len(cases),
        "results": reports,
    }
    Path(args.output).write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(Path(args.output).resolve()),
        "case_count": len(cases),
        "results": [
            {k: v for k, v in item.items() if k != "cases"}
            for item in reports
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
