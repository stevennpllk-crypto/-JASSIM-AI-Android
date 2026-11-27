# JASSIM AI — Reliable / always-on deployment

This deployment runs the API and Ollama together on an always-on Linux host (VPS or your own server). It is not a way to keep a Colab session alive.

## What it improves

- Docker restarts the API and Ollama after a host/container restart or process crash (`restart: unless-stopped`).
- Model weights and SQLite conversations live in persistent named volumes.
- The selected model is pulled before the API starts.
- The API container checks `/ready`, so a live Python process is not mistaken for a working model.
- The API binds to host loopback only. Put a trusted HTTPS reverse proxy or a named Cloudflare Tunnel in front of it; do not expose port 8787 directly.

## Requirements

- An always-on Linux host with Docker Engine and Docker Compose.
- Enough RAM/VRAM for the selected model. The default `qwen3.5:4b` is the lighter compatibility choice. For stronger reasoning and coding, set `JASSIM_OLLAMA_MODEL=qwen3.5:9b` on a host with enough memory; the quantized model download is about 6.6 GB, before runtime/context overhead. If the host struggles, return to 4B.
- CPU-only operation is supported but can be much slower. For NVIDIA GPU acceleration, install the NVIDIA Container Toolkit and use the GPU override.

## Railway-specific deployment requirements

Railway does not automatically start every service in `docker-compose.yml` when this repository is deployed from its `Dockerfile`. The Dockerfile starts the Python API only; it does not install or launch an Ollama server.

For a Railway deployment, provision Ollama as a separate private service (or deliberately package and supervise it in the same container), attach persistent storage for model weights, and set `JASSIM_OLLAMA_URL` to the Ollama service's private internal address. Do not use `127.0.0.1:11434` when Ollama runs in a different service: loopback refers to the API container itself. The API and model service must have enough memory for the selected model and its context; a small API-only allocation is not a model host.

Set the Railway service health-check path to `/ready`, not `/health`, when the deployment is intended to serve chat. `/health` is intentionally a liveness/diagnostics endpoint and can return HTTP 200 while Ollama is unavailable. `/ready` verifies the API token, Ollama reachability, and configured model availability. A successful `/ready` check still does not replace a real authenticated chat-generation test.

Do not publish a deployment as ready merely because the API container is online. Confirm all of the following: the Ollama service is online, the configured model is installed, `/ready` returns HTTP 200, and an authenticated `/api/chat/stream` request completes successfully.

## Model quality

The Colab notebook automatically selects Qwen3.5 9B when it detects an NVIDIA GPU and falls back to 4B otherwise. On a permanent host, choose deliberately in `.env`: 9B for better capability when memory permits, 4B for lower resource use. JASSIM allows up to 3072 output tokens by default and serializes generations to reduce GPU memory spikes. This improves answer depth and service stability, but does not replace evaluation on Arabic/Tunisian prompts.

## First start

1. Clone this repository on the server.
2. Copy `.env.example` to `.env`.
3. Generate a private token and place it in `.env`:

   ```sh
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Set `JASSIM_CORS_ORIGIN` to the exact HTTPS dashboard origin, or leave it empty if you do not use the browser dashboard.
5. Start:

   ```sh
   docker compose --env-file .env -f docker-compose.yml up -d --build
   ```

   On an NVIDIA host:

   ```sh
   docker compose --env-file .env -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
   ```

6. Check:

   ```sh
   docker compose --env-file .env -f docker-compose.yml ps
   docker compose --env-file .env -f docker-compose.yml logs -f ollama jassim-api
   ```

7. Configure Android with the public HTTPS URL and the private token from `.env`. Never commit the token or place it in the APK.

## Persistence and recovery

- SQLite is stored in `jassim-data`; model weights are stored in `ollama-models`.
- Back up the database volume before upgrades. Find the exact volume name with `docker volume ls`; Compose may prefix it with the project name.
- Docker starts services again after a host reboot. If model download or API startup failed, inspect logs and run `docker compose ... up -d` again.
- A health check reports an unhealthy service. Docker's restart policy restarts crashed processes, but does not automatically restart a process that remains alive while unhealthy. Monitor `/ready` externally and alert/restart on sustained failures; test backup restoration periodically.

## Honest limits

- This provides restartability only on a host that remains powered and connected. It cannot prevent a provider from suspending a free instance.
- A stable public address requires a domain/reverse proxy or a configured named tunnel. Cloudflare Quick Tunnel URLs are temporary.
- The shared Bearer token is still one shared identity, not individual accounts.
- `/health` is liveness/diagnostics. `/ready` returns HTTP 503 unless the API token is configured and Ollama is reachable with the configured model installed.

## Read-only Railway audit — 2026-11-27

The production environment was inspected without changing its configuration or starting a deployment. The observed state is:

- The API service deploys from the repository's `main` branch, not `feat/gpu-aware-model-selection`. Changes on the development branch are therefore not active in production.
- The API service is online with 2/2 replicas, but has no volume mounted. A separate 500 MB volume named `jassim-ai-data-v2` exists and is currently unattached.
- PostgreSQL is online and has its own persistent volume. This is the currently attached persistent database service; the unattached data volume should not be treated as active application storage.
- No Ollama service exists in this Railway environment. The API's source default is `http://127.0.0.1:11434`; unless a valid Ollama endpoint is explicitly configured, that address targets the API container itself.
- The API allocation is 1 vCPU and 1 GB RAM across 2 replicas. This is an API-sized allocation, not a suitable place to host a 4B/9B Ollama model.
- Railway's configured health-check path is `/health`. This can report the API process as alive while private inference is unavailable. The code's `/ready` endpoint checks API-token configuration, Ollama reachability, and whether the configured model is installed.
- The `jassim-remote-mcp` service exists but has no deployment and is offline.

These observations are diagnostic, not a production change. Do not switch the health-check path to `/ready` or create/resize services until a working Ollama service, adequate memory, and persistent model storage have been provisioned. Do not mark chat as operational until `/ready` returns HTTP 200 and an authenticated generation request succeeds.

## Development-branch validation boundary

The current Android workflow is configured to run on pushes to `main`, pull requests targeting `main`, or manual dispatch. A push to `feat/gpu-aware-model-selection` alone does not start that workflow. The development branch currently has no associated Actions run, so its backend unit tests, APK build, and emulator smoke test remain unverified.

This audit deliberately did not dispatch or re-run Actions. Before treating this branch as release-ready, run the repository workflow against this exact commit and review all test, APK, and emulator results. The existing successful run on `main` validates only the source revision recorded by that run; it does not validate later commits on this development branch.

