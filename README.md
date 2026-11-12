# JASSIM AI — Android + Self-hosted API + Cloud Dashboard

JASSIM AI contains a native Android client, a Python API, SQLite or PostgreSQL conversation storage, individual email/password accounts with revocable sessions, per-user conversation ownership, and an Arabic RTL web dashboard.

## Product direction

See [ROADMAP.md](ROADMAP.md) for shipped and planned capabilities. Individual email/password accounts, revocable sessions, per-user conversation ownership, streaming chat, and conversation-scoped memory are implemented. Google OAuth, email password recovery, session refresh, richer memory controls, and other roadmap items remain planned.

## Components

- `app/`: native Android client (Java) with individual email/password account registration and sign-in. Configure the HTTPS server URL in Settings; ordinary users sign in with their account, while the optional legacy API token is reserved for owner/admin access. Session tokens are stored encrypted with Android Keystore.
- `DEPLOYMENT.md`: restartable Docker deployment, persistent model/database volumes, readiness checks, and HTTPS guidance.
- `backend/server.py`: Python API (v0.6.0) with SQLite/PostgreSQL storage, individual account registration and login, revocable bearer sessions, per-user conversation ownership, request-size checks, rate limiting, model readiness checks, authenticated model inventory, and SSE chat streaming.
- `dashboard/`: Arabic RTL dashboard for health checks and chat.
- `.github/workflows/android.yml`: backend smoke tests, debug APK build, ZIP integrity/required-entry verification, and artifact upload.
- `.github/workflows/pages.yml`: GitHub Pages deployment workflow for the dashboard.

## Important security notes

- Never commit `JASSIM_API_TOKEN`, tunnel credentials, or private keys.
- The Android client stores its API token encrypted with Android Keystore (AES-GCM); the token is entered on the device and is not compiled into the APK.
- The dashboard stores its endpoint in browser local storage and its token in session storage. Use it only on a trusted device and close the browser session when finished.
- Use HTTPS for any server reachable over the internet. The Android app intentionally rejects plain HTTP endpoints.
- Automatic endpoint discovery is pinned to the canonical production Railway API host; it does not trust arbitrary URLs from the public registry. In Connection Settings, a user may explicitly approve a custom HTTPS DNS hostname (default/443 port, origin only, no credentials, path, query, or fragment). The app warns that the selected server receives account bearer tokens and chat messages. Use only a domain you own or trust. This explicit approval is separate from public-registry discovery.
- For self-hosted Docker, bind the API to `127.0.0.1` behind a trusted HTTPS reverse proxy/tunnel. On managed platforms such as Railway, bind to the platform-required interface only behind the provider's HTTPS edge; do not expose the raw Python server port directly.
- Regular users create accounts and authenticate through `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, and `/api/auth/logout`. Passwords are stored as PBKDF2-HMAC-SHA256 hashes; random session tokens are returned once and only their SHA-256 hashes are stored server-side. Conversations are assigned to an account and access is checked server-side. The optional `JASSIM_API_TOKEN` remains a legacy owner/admin credential for maintenance and migration; it is not required for ordinary account sign-in and must never be embedded in the APK.
- Google OAuth and email-based password recovery are not implemented/configured yet; the Android UI marks both unavailable rather than pretending they work.
- Image generation requires `JASSIM_HF_TOKEN` on the server. Without it, the image endpoint returns `image_provider_not_configured`.
- `/health` is a public liveness/diagnostics endpoint. `/ready` returns HTTP 200 when the configured Ollama model is reachable and installed OR external-chat routing is enabled. The external flag means the route is enabled, not that a provider is currently reachable; `api_token_configured` is informational. A successful authenticated chat request remains the definitive inference test.
- In the current development branch, public-provider inference is hard-disabled in `backend/adaptive.py`; setting external-provider environment variables cannot enable it. The server returns an unavailable response when local Ollama is missing. Do not treat old provider configuration examples as active functionality.

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

For a restartable API + Ollama stack on an always-on Linux host, follow [DEPLOYMENT.md](DEPLOYMENT.md) and use `docker-compose.always-on.yml`.

A temporary tunnel is not permanent hosting. For always-on access, deploy the API behind a stable HTTPS domain on an always-on machine that can run the selected model. Free hosting may sleep, limit CPU/RAM, or lack a GPU.

## Android build

The repository's GitHub Actions workflow builds `app/build/outputs/apk/debug/app-debug.apk` and uploads it as the `JASSIM-AI-debug-APK` artifact after a push to `main` or a manual workflow run. Download the artifact from the successful Actions run.

## Dashboard deployment

Enable GitHub Pages for this repository and choose GitHub Actions as the deployment source. The Pages workflow publishes the `dashboard/` directory. The dashboard does not host the AI model; it connects to the API URL you configure in its settings.

## Current limitations

- Google OAuth and email-based password recovery are not implemented/configured; the Android UI reports these actions as unavailable. Session refresh and a self-service account deletion UI are also not implemented.
- User-controlled memory currently supports explicit save/show/clear commands scoped to a conversation. Dedicated inspect/edit/disable/export controls and long-term cross-conversation summaries remain planned.
- Rate-limit buckets are in-memory per API process; they are not a distributed quota across multiple replicas. Deployments with multiple public replicas should add a shared rate-limit store before relying on the current limit as a global abuse-control boundary.
- No guaranteed always-on GPU hosting is included. `/health` is liveness/diagnostics; `/ready` indicates a model/provider route is ready, but only a successful authenticated chat request proves a generation completed.

## Image generation

The Arabic dashboard includes an authenticated image studio at `/api/images/generate`.
It uses Hugging Face Inference Providers with `black-forest-labs/FLUX.1-schnell` by default.
Configure `JASSIM_HF_TOKEN` as a Railway secret with Inference Providers permission; optionally set `JASSIM_IMAGE_MODEL` and `JASSIM_IMAGE_TIMEOUT`.
Never put the Hugging Face token in dashboard JavaScript, Android source, GitHub, or a public URL.
Image generation is a hosted pretrained model call; it does not train or fine-tune a model. Fine-tuning requires a curated licensed image dataset and a GPU training environment.
Adobe Firefly/Photoshop Services can be added as a separate provider, but requires Adobe Developer Console credentials and an eligible Firefly Services contract.


## External-provider status

Groq, JarvisClaw, and OVH provider definitions remain in the source for reference, but real chat routing and public-provider evaluation are hard-disabled in the current development branch. They are not a fallback and no API key should be configured for them. The intended production architecture is a private Ollama service reachable only from the JASSIM API over a private network.
