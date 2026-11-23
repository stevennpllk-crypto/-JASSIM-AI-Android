# Railway deployment: private-model readiness

This repository's Railway API service is not an Ollama host by itself. The API container image installs and starts the Python API; it does not install, start, or persist an Ollama model. A green API deployment therefore does not prove that JASSIM can generate answers.

## The two health endpoints are intentionally different

- `/health` is liveness/diagnostics. It can return HTTP 200 while Ollama is offline.
- `/ready` is readiness for private chat. It returns HTTP 200 only when the API token is configured, Ollama is reachable, and the configured model is installed. Otherwise it returns HTTP 503.
- An authenticated `POST /api/chat` that returns a non-empty answer with `engine: "ollama"` is the definitive end-to-end inference check.

If Railway's service healthcheck is set to `/health`, Railway can mark the API healthy while private chat is unavailable. For a deployment that must not be considered ready until inference is possible, set the Railway service Healthcheck Path to `/ready`. Do this only after the private Ollama endpoint is provisioned and reachable; otherwise the deployment should correctly remain unhealthy.

## Supported private topologies

### A. Colab test stack

Use `notebooks/JASSIM_AI_Colab_GPU.ipynb` to start Ollama, pull the selected model, start the API, run a real generation test, and then create a temporary HTTPS Cloudflare Tunnel. The notebook defaults to manual endpoint entry and does not publish the endpoint to GitHub.

1. Open the notebook in Google Colab.
2. Run the cells in order through the real inference test.
3. Run the tunnel cell only after the local readiness and chat tests pass.
4. Copy the HTTPS tunnel URL into Android Settings.
5. Run the notebook's token-display cell only when you are ready to enter the token on your own trusted device. Keep the token private.
6. Keep the Colab runtime active. Its tunnel and GPU session are temporary and may stop.

The app should point to the Colab tunnel for this topology; do not point it at the Railway API-only service.

### B. Always-on private host

Run the root `docker-compose.yml` on an always-on Linux host with enough RAM/VRAM and persistent storage. The Compose stack starts Ollama, pulls the selected model, and starts the API on a private Docker network. Put a trusted HTTPS reverse proxy or named tunnel in front of the API.

Do not try to run a multi-billion-parameter Ollama model inside the current lightweight Railway API service as a side process. The API container has no Ollama runtime or model volume, and a small API allocation is not a suitable GPU inference host.

## No external inference fallback

JASSIM uses private Ollama only. If the private engine is unavailable, the API returns HTTP 503 and does not forward the user's prompt to another provider. Do not add hosted-provider fallbacks to work around an unavailable private model.

## Safe verification checklist

- `GET /health`: API process liveness only.
- `GET /ready`: model and API readiness.
- `POST /api/chat` with a private account session: must return HTTP 200, a non-empty `answer`, and `engine: "ollama"`.
- With Ollama stopped: chat must return HTTP 503 with `private_model_unavailable`; no prompt may be forwarded elsewhere.

Never put API tokens, tunnel credentials, or private URLs in source control, public logs, screenshots, or chat messages.
