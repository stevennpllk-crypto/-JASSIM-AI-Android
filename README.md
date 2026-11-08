# JASSIM AI — Android + Self-hosted API + Cloud Dashboard

JASSIM AI contains an Android client, a small Python API, SQLite conversation storage, and an Arabic RTL web dashboard.

## Product direction\n\nSee [ROADMAP.md](ROADMAP.md) for the complete staged plan: streaming chat, user-controlled memory, file knowledge, search/tools, multimodal support, multi-user security, and reliable deployment. These are planned capabilities, not claims that they are already shipped.\n\n## Components

- `app/`: native Android client (Java). Configure the server URL and API token in the app's Settings.
- `backend/server.py`: Python standard-library API (v0.2.0) with SQLite persistence, Bearer authentication, input-size checks, per-IP rate limiting, model readiness checks, and an authenticated model inventory endpoint.
- `dashboard/`: Arabic RTL dashboard for health checks and chat.
- `.github/workflows/android.yml`: backend unit-test step and debug APK build.
- `.github/workflows/pages.yml`: GitHub Pages deployment workflow for the dashboard.

## Important security notes

- Never commit `JASSIM_API_TOKEN`, tunnel credentials, or private keys.
- The Android client stores its API token encrypted with Android Keystore (AES-GCM); the token is entered on the device and is not compiled into the APK.
- The dashboard stores its endpoint in browser local storage and its token in session storage. Use it only on a trusted device and close the browser session when finished.
- Use HTTPS for any server reachable over the internet. The Android app intentionally rejects plain HTTP endpoints.
- Keep the API bound to `127.0.0.1` behind a trusted HTTPS reverse proxy/tunnel. Do not expose the Python HTTP server directly to the public internet.
- The shared Bearer token currently represents one shared API identity, not individual user accounts. Rotate it if it was ever exposed. A multi-user login/session system is a separate next step.
- `/health` is intentionally public and performs a short Ollama/model readiness probe. A successful chat request is still the definitive inference test.

## Run the API

Install Python 3.10+ and set the required environment variables before starting the server:

```sh
export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export JASSIM_HOST="127.0.0.1"
export JASSIM_PORT="8787"
export JASSIM_OLLAMA_URL="http://127.0.0.1:11434"
export JASSIM_OLLAMA_MODEL="qwen2.5:1.5b"
export JASSIM_DATA_DIR="$HOME/JASSIM_AI/data"
python backend/server.py
```

Keep the generated token private. Enter the server's HTTPS URL and this token in the Android app's Settings. Do not paste the token into GitHub, public issues, screenshots, or chat messages.

Check local API health:

```sh
curl http://127.0.0.1:8787/health
```

The chat endpoint requires the Bearer token:

```sh
curl -X POST "http://127.0.0.1:8787/api/chat" \
  -H "Authorization: Bearer $JASSIM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"عرّف بنفسك","conversation_id":"test"}'
```

## Google Colab / temporary tunnels

Colab can run the API and Ollama for experiments, but its runtime and public tunnel URL are temporary. After a runtime restart, start Ollama, the API, and the tunnel again, then update the endpoint in the Android app if the tunnel URL changed. SQLite data persists only when `JASSIM_DATA_DIR` points to a mounted persistent drive.

A temporary tunnel is not permanent hosting. For always-on access, deploy the API behind a stable HTTPS domain on a machine or host that can run the selected model. Free hosting may sleep, limit CPU/RAM, or lack a GPU.

## Android build

The repository's GitHub Actions workflow builds `app/build/outputs/apk/debug/app-debug.apk` and uploads it as the `JASSIM-AI-debug-APK` artifact after a push to `main` or a manual workflow run. Download the artifact from the successful Actions run.

## Dashboard deployment

Enable GitHub Pages for this repository and choose GitHub Actions as the deployment source. The Pages workflow publishes the `dashboard/` directory. The dashboard does not host the AI model; it connects to the API URL you configure in its settings.

## Current limitations

- One shared Bearer token; no user registration, per-user permissions, or token revocation UI yet.
- No guaranteed always-on GPU hosting is included.
- Health checks confirm API reachability/configuration. They do not independently verify inference availability.
