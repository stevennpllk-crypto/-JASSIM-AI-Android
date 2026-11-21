# JASSIM AI Self-Hosted Backend

A small self-hosted HTTP API for the JASSIM AI Android client. The core API uses Python's standard library; PostgreSQL deployments additionally install psycopg. SQLite is the default local store.

## Safety defaults
- Binds to `127.0.0.1` when run directly. The container uses `0.0.0.0` inside its isolated network.
- No API keys are embedded in the Android APK.
- `JASSIM_API_TOKEN` is an optional legacy operator/admin credential. Android and dashboard users authenticate with individual account session tokens.
- The dashboard keeps its session token in tab-scoped `sessionStorage`; Android encrypts its session token with Android Keystore (AES-GCM).
- Set `JASSIM_CORS_ORIGIN` to the exact HTTPS dashboard origin, not `*`, before public deployment.
- Request size and message length are limited.
- Chat history uses SQLite by default, or PostgreSQL when `DATABASE_URL` is configured. Persist the database volume or back up PostgreSQL.

## Deploy with Docker Compose
The repository includes a root `Dockerfile` and `docker-compose.yml`. On a Linux server with Docker Compose installed:

1. Clone the repository.
2. Set secrets as environment variables on the host (do not commit them):
   ```sh
   export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   export JASSIM_CORS_ORIGIN="https://stevennpllk-crypto.github.io"
   # Point this to your Ollama service; default assumes Ollama runs on the Docker host.
   export JASSIM_OLLAMA_URL="http://host.docker.internal:11434"
   export JASSIM_OLLAMA_MODEL="qwen2.5:0.5b"
   ```
3. Build and start:
   ```sh
   docker compose up -d --build
   docker compose logs -f jassim-api
   ```
4. Check `https://YOUR_API_HOST/health` after configuring an HTTPS reverse proxy.

The Compose file persists SQLite data in the named volume `jassim-data`. Back up that volume regularly. The API container does not include Ollama or model weights; run Ollama separately on a machine with enough RAM/VRAM and configure `JASSIM_OLLAMA_URL`.

**Important:** Compose maps port 8787 for local/server networking. Do not expose this plain HTTP port directly to the public internet. Put it behind HTTPS (for example, Caddy or Nginx), restrict inbound firewall access, and use a strong token. Free hosts may sleep, reset storage, or lack the RAM/VRAM needed for a model.

## Run on Termux (Android)
1. Install Python in Termux: `pkg install python`
2. Download/clone this repository, then enter its `backend` directory.
3. Start the API: `python server.py`
4. In another Termux session, test it:
   ```sh
   curl http://127.0.0.1:8787/health
   # Register or log in first, then use the returned session token:
   curl -X POST http://127.0.0.1:8787/api/chat -H 'Authorization: Bearer SESSION_TOKEN' -H 'Content-Type: application/json' -d '{"message":"مرحبا","conversation_id":"test"}'
   ```

## Legacy operator/admin token
Generate a long random token only if you need the legacy operator/admin credential (never commit it to Git):
```sh
export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export JASSIM_CORS_ORIGIN="https://stevennpllk-crypto.github.io"
python server.py
```
Normal users should register or log in in the Android app or dashboard and use the returned session token. The operator token is not needed for ordinary chat and must not be shared with users. `/health` remains public; protected routes require a valid account session or the operator credential. Registration and login are public endpoints protected by a process-local rate limiter. Do not expose the service publicly without HTTPS and abuse protection.

## Enable a real local model
The API can call an Ollama server compatible with `POST /api/chat`.
Set:
- `JASSIM_OLLAMA_URL` (default `http://127.0.0.1:11434`)
- `JASSIM_OLLAMA_MODEL` (default `qwen2.5:0.5b`)

Example:
```sh
JASSIM_OLLAMA_MODEL=qwen2.5:0.5b python server.py
```

If Ollama is unavailable, the API returns an explicit fallback response; it does not pretend that a language model is running.

## Android compatibility
The API preserves the existing contract: `POST /api/chat` with JSON `{"message":"..."}`, returning both `answer` and `reply`. The Android app supports HTTPS endpoints and automatically checks the configured discovery registry before using the saved/default server address.

## Current limits
This is a self-hosted API foundation, not an unlimited GPU host. A 3 GB Android phone can host the API and SQLite store, but it is not suitable for large LLM inference. For larger models, connect a separately owned computer or GPU host with sufficient RAM/VRAM and persistent storage.


## Adaptive provider learning (v0.5)

JASSIM can benchmark multiple OpenAI-compatible inference providers and rank them using synthetic Arabic, arithmetic, and English test prompts. It stores attempts, success rate, latency, and an exponentially weighted quality estimate in SQLite. The evaluator never reads or uploads the user's chat history.

- `GET /api/providers` (Bearer token): current provider ranking and score history.
- `POST /api/admin/evaluate` (Bearer token): run the synthetic benchmark against configured public providers.
- `JASSIM_ENABLE_PUBLIC_PROVIDERS=true`: enable provider probes (synthetic prompts only).
- `JASSIM_ALLOW_EXTERNAL_CHAT=true`: explicitly allow actual user messages to be sent to public providers when local Ollama is unavailable. This is OFF by default. Do not enable it for confidential conversations.

The initial public candidates are JarvisClaw and OVHcloud AI Endpoints. Provider availability, quotas, and terms can change; scores are routing heuristics, not proof of factual correctness. The system learns routing preferences from measured outcomes; it does not retrain model weights or rewrite its own source code. Source changes still require tests and a reviewed deployment.


## Shared PostgreSQL storage and horizontal replicas (v0.6)

When `DATABASE_URL` is configured, the API stores chat messages, conversation memories, and adaptive-provider scores in PostgreSQL through the shared `storage.py` adapter. Without it, local development and tests continue to use SQLite.

On PostgreSQL startup, migration `sqlite_to_postgres_v2` checks the existing `JASSIM_DATA_DIR/jassim.db` SQLite file and imports users, sessions, conversation ownership, messages, memories, and provider scores. Version 2 also backfills account and ownership tables for databases previously marked by v1. The source SQLite file is retained; the v2 migration marker prevents later replicas from repeating the import. Keep the source volume or a backup until account/session counts and conversation ownership are verified.

Railway deploys PostgreSQL privately and injects `DATABASE_URL=${{Postgres.DATABASE_URL}}` into the API service. After migration and verification, the legacy SQLite volume can be detached (not deleted), allowing multiple API replicas to run without a single-writer disk mount.

The current horizontal topology uses multiple API replicas behind the Railway domain. PostgreSQL is the shared durable data layer. This is horizontal replica scaling; it does not mean model weights are retrained. Provider evaluation remains synthetic, and routing scores are shared through PostgreSQL.


# JASSIM AI Multi-user Accounts

## Authentication API

The backend now supports account sessions in addition to the legacy operator token:

- `POST /api/auth/register` — JSON body: `{"email":"person@example.com","password":"at-least-10-characters"}`. Returns a one-time opaque bearer token.
- `POST /api/auth/login` — same JSON body; returns a new session token.
- `GET /api/auth/me` — returns the authenticated account profile.
- `POST /api/auth/logout` — revokes the current session.

Send the returned token on normal API requests as `Authorization: Bearer <session-token>`. Tokens expire after 30 days. The server stores only a SHA-256 digest of each random session token. Passwords are stored using PBKDF2-HMAC-SHA256 with a unique random salt (310,000 iterations); passwords must be at least 10 characters.

## Account privacy and migration

Every conversation has one owner in the `conversations` table. History, memory, listing and deletion are scoped to the authenticated owner. A user cannot claim an existing conversation ID belonging to another account. Existing messages without an ownership record are assigned to the non-login `legacy-owner` account during schema initialization; imported account-owned conversations retain their original owner.

`JASSIM_API_TOKEN` remains an operator/admin credential for maintenance and backwards compatibility. It must not be embedded in a distributed APK or shared with ordinary users. New users receive their own session token after login or registration.

## Current beta limitations

Registration is open and currently protected by the API's per-process IP rate limiter. Email verification and password reset are not yet implemented. Do not treat this as a finished public launch until registration abuse protection is moved to shared storage, email verification/recovery is configured, and the Android and dashboard login screens are deployed. Always use HTTPS for public traffic.

The merged main branch includes Android and dashboard login/register/logout controls. Android stores the opaque session token using Android Keystore-backed encryption; the dashboard keeps it in sessionStorage for the current tab. These changes require a successful Railway deployment before clients can use the new account endpoints. The production Railway service still needs its GitHub source connection authorized for this repository.
