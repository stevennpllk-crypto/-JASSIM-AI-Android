# JASSIM AI — Android + Self-hosted API + Cloud Dashboard

JASSIM AI contains an Android client, a small Python API, SQLite conversation storage, and an Arabic RTL web dashboard.

## Product direction

See [ROADMAP.md](ROADMAP.md) for the complete staged plan: streaming chat, user-controlled memory, file knowledge, search/tools, multimodal support, multi-user security, and reliable deployment. These are planned capabilities, not claims that they are already shipped.

## Components

- `app/`: native Android client (Java). Configure the server URL and API token in the app's Settings. The active conversation transcript is restored from the authenticated history endpoint on startup.
- `DEPLOYMENT.md`: restartable Docker deployment, persistent model/database volumes, readiness checks, and HTTPS guidance.
- `backend/server.py`: Python standard-library API (v0.6.0) with SQLite/PostgreSQL storage, account sessions, owner-scoped conversation history, input-size checks, per-IP rate limiting, private Ollama readiness checks, and SSE streaming chat.
- `dashboard/`: Arabic RTL dashboard for health checks and chat.
- `.github/workflows/android.yml`: backend integration/security tests, debug APK build, Android emulator install/launch smoke test, APK integrity verification, and artifact upload.
- `.github/workflows/pages.yml`: GitHub Pages deployment workflow for the dashboard.

## Important security notes

- Never commit `JASSIM_API_TOKEN`, tunnel credentials, or private keys.
- The Android client stores its API token encrypted with Android Keystore (AES-GCM); the token is entered on the device and is not compiled into the APK.
- The dashboard stores its endpoint in browser local storage and its token in session storage. Use it only on a trusted device and close the browser session when finished.
- Use HTTPS for any server reachable over the internet. The Android app intentionally rejects plain HTTP endpoints.
- Keep the API bound to `127.0.0.1` behind a trusted HTTPS reverse proxy/tunnel. Do not expose the Python HTTP server directly to the public internet.
- `JASSIM_API_TOKEN` is an operator credential for maintenance and compatibility; ordinary users should use their own account session tokens. Session tokens are stored as digests server-side and encrypted with Android Keystore on Android.
- `/health` is a public liveness/diagnostics endpoint. `/ready` returns HTTP 503 unless the token is configured and Ollama can see the configured model. A successful chat request remains the definitive inference test.

## Run the API

Install Python 3.10+ and set the required environment variables before starting the server:

```sh
export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export JASSIM_HOST="127.0.0.1"
export JASSIM_PORT="8787"
export JASSIM_OLLAMA_URL="http://127.0.0.1:11434"
export JASSIM_OLLAMA_MODEL="qwen3.5:4b" # use qwen3.5:9b on a capable GPU host for stronger answers
export JASSIM_OLLAMA_KEEP_ALIVE="-1"
export JASSIM_NUM_CTX="8192"
export JASSIM_NUM_PREDICT="3072"
export JASSIM_HISTORY_CHAR_BUDGET="32000"
export JASSIM_REQUEST_TIMEOUT="300"
export JASSIM_MAX_CONCURRENT="1"
export JASSIM_QUEUE_TIMEOUT="180"
export JASSIM_DATA_DIR="$HOME/JASSIM_AI/data"
python backend/server.py
```

The API serializes model inference by default (one generation at a time) to avoid overloading small GPUs; tune `JASSIM_MAX_CONCURRENT` only when the host has enough memory. The API defaults to 3072 output tokens and a 24,000-character recent-history budget. The Colab GPU profile keeps the 3072-token output budget and raises the history budget to 32,000 characters.

Keep the generated token private. Enter the server's HTTPS URL and this token in the Android app's Settings. Do not paste the token into GitHub, public issues, screenshots, or chat messages.

Check local API health:

```sh
curl http://127.0.0.1:8787/health
```

Check model readiness (HTTP 503 means the configured model is not currently available):

```sh
curl -i http://127.0.0.1:8787/ready
```

The chat endpoint requires the Bearer token:

```sh
curl -X POST "http://127.0.0.1:8787/api/chat" \
  -H "Authorization: Bearer $JASSIM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"عرّف بنفسك","conversation_id":"test"}'
```

The legacy `/api/chat` route continues to return a complete JSON response. Android now uses `/api/chat/stream`, which returns Server-Sent Events with JSON payloads: `type=token` for each generated piece, followed by `type=done` when the full answer is saved. A client can cancel delivery by closing its HTTP connection; incomplete generations are not saved when the server detects the disconnect.

Example streaming request:

```sh
curl -N -X POST "http://127.0.0.1:8787/api/chat/stream" \
  -H "Authorization: Bearer $JASSIM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"message":"عرّف بنفسك","conversation_id":"stream-test"}'
```

## Google Colab / temporary tunnels

Colab can run the API and Ollama for experiments, but its runtime and public tunnel URL are temporary. The notebook automatically selects `qwen3.5:9b` when an NVIDIA GPU is detected and falls back to `qwen3.5:4b` otherwise; it uses an 8K context and a 3K output budget in the Colab profile, and configures indefinite model residency while the runtime remains active; this does not prevent Colab from disconnecting or reclaiming the machine. After a runtime restart, start Ollama, the API, and the tunnel again, then update the endpoint in the Android app if the tunnel URL changed. Run the notebook's **Watchdog** cell after the startup cells: it restarts crashed Ollama/API/tunnel processes while the Colab runtime remains alive and prints a replacement tunnel URL when needed. It cannot prevent Colab from disconnecting or reclaiming the machine. SQLite data persists only when `JASSIM_DATA_DIR` points to a mounted persistent drive.

For a restartable private API + Ollama stack on an always-on Linux host, use the root `docker-compose.yml`; Ollama and the API communicate on a private Docker network.

A temporary tunnel is not permanent hosting. For always-on access, deploy the API behind a stable HTTPS domain on an always-on machine that can run the selected model. Free hosting may sleep, limit CPU/RAM, or lack a GPU.

## Android build

The repository's GitHub Actions workflow runs backend integration/security tests, builds `app/build/outputs/apk/debug/app-debug.apk`, installs and launches it in an Android API 35 emulator, verifies the APK archive, and uploads it as the `JASSIM-AI-debug-APK` artifact. Download the artifact only from a successful Actions run. The emulator smoke test verifies installation and foreground launch; it does not prove a live Ollama generation on the production server.

## Dashboard deployment

Enable GitHub Pages for this repository and choose GitHub Actions as the deployment source. The Pages workflow publishes the `dashboard/` directory. The dashboard does not host the AI model; it connects to the API URL you configure in its settings.

## Current limitations

- Registration is currently open and rate-limited per server process; email verification and password recovery are not yet implemented.
- No guaranteed always-on GPU hosting is included.
- `/health` reports API liveness and model diagnostics; `/ready` confirms the configured model is installed and reachable, but only a successful authenticated chat request proves a generation completed.

## Private inference policy

JASSIM AI uses exactly one inference engine: the Ollama model running in the private deployment stack. The backend contains no hosted LLM fallback, no public-provider ranking or probing, and no external image-inference integration. If the private model is unavailable, chat returns HTTP 503 and the message is not forwarded to another service. Image generation remains unavailable until an image model is implemented and hosted within the same private infrastructure.
