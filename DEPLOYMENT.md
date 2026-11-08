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
- Enough RAM/VRAM for the selected model. The default `qwen3.5:4b` is a compact baseline, not a frontier model. Larger models may improve reasoning and coding but need more memory and may be slower.
- CPU-only operation is supported but can be much slower. For NVIDIA GPU acceleration, install the NVIDIA Container Toolkit and use the GPU override.

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
   docker compose --env-file .env -f docker-compose.always-on.yml up -d --build
   ```

   On an NVIDIA host:

   ```sh
   docker compose --env-file .env -f docker-compose.always-on.yml -f docker-compose.gpu.yml up -d --build
   ```

6. Check:

   ```sh
   docker compose --env-file .env -f docker-compose.always-on.yml ps
   docker compose --env-file .env -f docker-compose.always-on.yml logs -f ollama jassim-api
   ```

7. Configure Android with the public HTTPS URL and the private token from `.env`. Never commit the token or place it in the APK.

## Persistence and recovery

- SQLite is stored in `jassim-data`; model weights are stored in `ollama-models`.
- Back up the database volume before upgrades. Find the exact volume name with `docker volume ls`; Compose may prefix it with the project name.
- Docker starts services again after a host reboot. If model download or API startup failed, inspect logs and run `docker compose ... up -d` again.
- A health check reports an unhealthy service. Docker's restart policy restarts crashed processes, but does not automatically restart a process that remains alive while unhealthy. Monitor `/ready` and alert/restart on sustained failures.

## Honest limits

- This provides restartability only on a host that remains powered and connected. It cannot prevent a provider from suspending a free instance.
- A stable public address requires a domain/reverse proxy or a configured named tunnel. Cloudflare Quick Tunnel URLs are temporary.
- The shared Bearer token is still one shared identity, not individual accounts.
- `/health` is liveness/diagnostics. `/ready` returns HTTP 503 unless the API token is configured and Ollama is reachable with the configured model installed.
