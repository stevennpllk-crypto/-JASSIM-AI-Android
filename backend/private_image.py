"""Fail-closed client for JASSIM's private image inference worker.

The worker is a separately hosted, JASSIM-controlled service. This module
never contains or calls a public image-provider integration.
"""
import base64
import json
import os
import urllib.error
import urllib.request
import threading
import time
from urllib.parse import urlparse

WORKER_URL = os.environ.get("JASSIM_IMAGE_WORKER_URL", "").strip().rstrip("/")
WORKER_TOKEN = os.environ.get("JASSIM_IMAGE_WORKER_TOKEN", "").strip()
STATUS_TIMEOUT = 1.0
STATUS_CACHE_TTL = 5.0
_STATUS_LOCK = threading.Lock()
_STATUS_CACHE = None
_STATUS_CACHE_AT = 0.0
GENERATION_TIMEOUT = max(30, min(int(os.environ.get("JASSIM_IMAGE_TIMEOUT", "240")), 600))
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_MIME = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/webp": b"RIFF",
}


def _private_worker_url():
    """Accept only Railway private DNS or explicit loopback development URLs."""
    if not WORKER_URL or not WORKER_TOKEN:
        return None
    parsed = urlparse(WORKER_URL)
    host = (parsed.hostname or "").lower()
    private_host = (
        host.endswith(".railway.internal")
        or host in ("localhost", "127.0.0.1")
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
        return None
    try:
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            return None
    except ValueError:
        return None
    return WORKER_URL


class _NoWorkerRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward the worker bearer token through an HTTP redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_WORKER_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoWorkerRedirects(),
)


def open_worker(request, timeout):
    """Open only the configured private worker origin and approved API paths."""
    base = _private_worker_url()
    if not base:
        raise RuntimeError("private_image_worker_url_not_allowed")
    configured = urlparse(base)
    requested = urlparse(request.full_url)
    configured_origin = (configured.scheme, configured.hostname, configured.port)
    requested_origin = (requested.scheme, requested.hostname, requested.port)
    if (
        requested_origin != configured_origin
        or requested.username
        or requested.password
        or requested.query
        or requested.fragment
        or requested.path not in ("/ready", "/v1/images/generate")
    ):
        raise RuntimeError("private_image_worker_request_target_mismatch")
    return _WORKER_OPENER.open(request, timeout=timeout)


def worker_status(force_refresh=False):
    """Return cached readiness briefly to keep API liveness checks responsive."""
    global _STATUS_CACHE, _STATUS_CACHE_AT
    with _STATUS_LOCK:
        now = time.monotonic()
        if (
            not force_refresh
            and _STATUS_CACHE is not None
            and now - _STATUS_CACHE_AT < STATUS_CACHE_TTL
        ):
            return dict(_STATUS_CACHE)
        status = _fetch_worker_status()
        _STATUS_CACHE = dict(status)
        _STATUS_CACHE_AT = time.monotonic()
        return status


def _fetch_worker_status():
    """Probe the authenticated worker and require its actual model to be loaded."""
    base = _private_worker_url()
    if not base:
        return {"reachable": False, "model_ready": False, "model": "not_configured_private_worker"}
    request = urllib.request.Request(
        base + "/ready",
        headers={"Authorization": "Bearer " + WORKER_TOKEN, "Accept": "application/json"},
        method="GET",
    )
    try:
        with open_worker(request, timeout=STATUS_TIMEOUT) as response:
            payload = json.loads(response.read(65536).decode("utf-8"))
        ready = bool(
            isinstance(payload, dict)
            and payload.get("ready") is True
            and payload.get("model_ready") is True
            and isinstance(payload.get("model"), str)
            and payload.get("model").strip()
        )
        return {
            "reachable": True,
            "model_ready": ready,
            "model": payload.get("model") if ready else "private_worker_model_not_ready",
        }
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return {"reachable": False, "model_ready": False, "model": "private_worker_unavailable"}


def generate(prompt, width=1024, height=1024):
    """Generate only through the authenticated JASSIM private worker."""
    base = _private_worker_url()
    if not base:
        raise RuntimeError("local_image_model_not_configured")
    status = worker_status(force_refresh=True)
    if not status["reachable"] or not status["model_ready"]:
        raise RuntimeError("private_image_worker_unavailable")
    body = json.dumps({
        "prompt": str(prompt),
        "width": max(256, min(int(width), 1024)),
        "height": max(256, min(int(height), 1024)),
    }).encode("utf-8")
    request = urllib.request.Request(
        base + "/v1/images/generate",
        data=body,
        headers={
            "Authorization": "Bearer " + WORKER_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with open_worker(request, timeout=GENERATION_TIMEOUT) as response:
            raw = response.read(MAX_IMAGE_BYTES * 2)
        payload = json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise RuntimeError("private_image_worker_request_failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("private_image_worker_invalid_response")
    encoded = payload.get("image_base64")
    mime = payload.get("mime_type")
    model = payload.get("model")
    if not isinstance(encoded, str) or mime not in ALLOWED_MIME or not isinstance(model, str) or not model.strip():
        raise RuntimeError("private_image_worker_invalid_response")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("private_image_worker_invalid_image") from exc
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError("private_image_worker_image_size_invalid")
    signature = ALLOWED_MIME[mime]
    if not image_bytes.startswith(signature):
        raise RuntimeError("private_image_worker_mime_mismatch")
    if mime == "image/webp" and image_bytes[8:12] != b"WEBP":
        raise RuntimeError("private_image_worker_mime_mismatch")
    return encoded, mime, model.strip()
