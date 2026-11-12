"""Fail-closed client for JASSIM's private image inference worker.

The worker is a separately hosted, JASSIM-controlled service. This module
never contains or calls a public image-provider integration.
"""
import base64
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

WORKER_URL = os.environ.get("JASSIM_IMAGE_WORKER_URL", "").strip().rstrip("/")
WORKER_TOKEN = os.environ.get("JASSIM_IMAGE_WORKER_TOKEN", "").strip()
STATUS_TIMEOUT = 2.5
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


def worker_status():
    """Return ready only when the authenticated private worker has its model loaded."""
    base = _private_worker_url()
    if not base:
        return {"reachable": False, "model_ready": False, "model": "not_configured_private_worker"}
    request = urllib.request.Request(
        base + "/ready",
        headers={"Authorization": "Bearer " + WORKER_TOKEN, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=STATUS_TIMEOUT) as response:
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
    status = worker_status()
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
        with urllib.request.urlopen(request, timeout=GENERATION_TIMEOUT) as response:
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
