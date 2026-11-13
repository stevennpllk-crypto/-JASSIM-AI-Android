# JASSIM AI Self-Hosted Backend

A Python standard-library HTTP API for the JASSIM AI Android client. Chat history uses SQLite by default; PostgreSQL is optional through `DATABASE_URL`.

## Privacy and inference policy

The current development branch `fix/android-message-line-breaks` is designed to use private inference only:

- Chat inference accepts Ollama on loopback or a Railway private hostname (`*.railway.internal`) and restricts requests to the expected Ollama API paths.
- The Ollama transport disables environment proxies and refuses redirects.
- Public LLM provider fallback and public-provider evaluation are disabled. If the private model is unavailable, chat returns an explicit unavailable response instead of forwarding the prompt.
- Image generation is a separate private-worker integration. It requires both `JASSIM_IMAGE_WORKER_URL` and `JASSIM_IMAGE_WORKER_TOKEN`; only loopback or Railway private DNS is accepted. Its transport also disables proxies, refuses redirects, validates origin, path and HTTP method, and authenticates requests.
- Hugging Face may be contacted to download model artifacts during setup. This is not a user-prompt inference route.
- Android speech recognition and text-to-speech may use device-selected services; offline preference is not a hard guarantee.

**Important production caveat:** branch code is not proof of production behavior. The privacy branch has not been merged or deployed. The connected Railway production environment was previously observed without a private Ollama model service and with an external-provider-ready indicator. Do not send real prompts to production until the deployed code and infrastructure have been independently verified.

## Local setup

Requirements: Python 3.10+ for the API. Ollama must run separately on a machine with sufficient RAM/VRAM.

```sh
export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export JASSIM_CORS_ORIGIN="https://YOUR-TRUSTED-DASHBOARD-ORIGIN"
export JASSIM_OLLAMA_URL="http://127.0.0.1:11434"
export JASSIM_OLLAMA_MODEL="qwen3.5:4b"
python server.py
```

The API binds to `127.0.0.1:8787` by default. For container networking, bind inside the isolated container and put public access behind HTTPS, authentication, and a restrictive firewall. Never expose the plain HTTP API port directly to the internet.

## Docker Compose

The repository includes a root `Dockerfile` and `docker-compose.yml`. The API container does not include Ollama or model weights. Run Ollama as a separate private service and configure `JASSIM_OLLAMA_URL` to its loopback or private-network endpoint. Persist `JASSIM_DATA_DIR` and back up the database volume.

## Termux

```sh
pkg install python
python server.py
```

A 3 GB Android phone can host the API and SQLite store for development, but it is not a practical host for a 4B-class LLM. Do not expect the API to answer with a model unless a private Ollama instance is actually running and the configured model is installed.

## API and account notes

- `POST /api/chat` accepts a JSON object with `message` and optional `conversation_id`.
- Successful responses include `answer` and `reply`.
- `GET /health` is a liveness endpoint; `GET /ready` checks private model readiness.
- `GET /api/providers` reports no enabled external chat providers.
- `POST /api/admin/evaluate` is retired and returns HTTP 410.
- Registration/login issue opaque bearer sessions; the database stores session-token digests and PBKDF2 password hashes.
- Conversation history and memory are scoped to the authenticated account.
- Email verification and password recovery are not yet implemented; this is not ready for an unrestricted public launch.

## Validation boundaries

CI tests validate code behavior, request allowlists, privacy guards, notebooks, and Android packaging. They do **not** prove that an LLM has been trained, that a GPU session ran, that production has a private model, or that the APK was installed on a physical phone. Record those as separate operational checks.

Before production rollout:
1. Deploy the reviewed privacy branch only after explicit approval.
2. Provision a JASSIM-controlled private Ollama host and install the selected model.
3. Provision a private image worker only if image generation is required.
4. Verify `/ready` reports the model ready and `/health` reports external inference disabled.
5. Run synthetic Arabic tests against the private endpoint, then inspect outbound network telemetry.
