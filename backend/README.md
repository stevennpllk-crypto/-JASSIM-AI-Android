# JASSIM AI Self-Hosted Backend

A small self-hosted HTTP API for the existing JASSIM AI Android client. It uses only Python's standard library and keeps chat history in SQLite.

## Safety defaults
- Binds to `127.0.0.1` when run directly. The container uses `0.0.0.0` inside its isolated network.
- No API keys are embedded in the Android APK.
- Set `JASSIM_API_TOKEN` before public deployment. The Android app and dashboard send it as `Authorization: Bearer ...`.
- The dashboard keeps the token in session storage only; the Android app stores it in private app preferences.
- Set `JASSIM_CORS_ORIGIN` to the exact HTTPS dashboard origin, not `*`, before public deployment.
- Request size and message length are limited.
- Chat history is stored in SQLite. Mount persistent storage at `JASSIM_DATA_DIR`.

## Deploy with Docker Compose
The repository includes a root `Dockerfile` and `docker-compose.yml`. On a Linux server with Docker Compose installed:

1. Clone the repository.
2. Set secrets as environment variables on the host (do not commit them):
   ```sh
   export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   export JASSIM_CORS_ORIGIN="https://stevennpllk-crypto.github.io"
   export JASSIM_OLLAMA_MODEL="qwen3.5:4b"
   ```
3. Build and start:
   ```sh
   docker compose up -d --build
   docker compose logs -f jassim-api
   ```
4. Check `https://YOUR_API_HOST/health` after configuring an HTTPS reverse proxy.

The Compose file persists SQLite data in the named volume `jassim-data`. Back up that volume regularly. The Compose stack starts one private Ollama engine, downloads the configured model into its persistent volume, and connects the API to it over the private Compose network. No external inference provider is configured.

**Important:** Compose maps port 8787 for local/server networking. Do not expose this plain HTTP port directly to the public internet. Put it behind HTTPS (for example, Caddy or Nginx), restrict inbound firewall access, and use a strong token. Free hosts may sleep, reset storage, or lack the RAM/VRAM needed for a model.

## Run on Termux (Android)
1. Install Python in Termux: `pkg install python`
2. Download/clone this repository, then enter its `backend` directory.
3. Start the API: `python server.py`
4. In another Termux session, test it:
   ```sh
   curl http://127.0.0.1:8787/health
   curl -i http://127.0.0.1:8787/ready

   # If API authentication is enabled, include the configured bearer token
   curl -X POST http://127.0.0.1:8787/api/chat \\
     -H 'Authorization: Bearer YOUR_PRIVATE_API_TOKEN' \\
     -H 'Content-Type: application/json' \\
     -d '{"message":"مرحبا","conversation_id":"test"}'
   ```

## Enable API authentication
Generate a long random token and configure it as an environment variable on the server (never commit it to Git):
```sh
export JASSIM_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export JASSIM_CORS_ORIGIN="https://stevennpllk-crypto.github.io"
python server.py
``
Enter the same token in the Android app settings or the dashboard connection settings. `/health` remains public for connection checks; chat and history require the token. If `JASSIM_API_TOKEN` is unset, the server remains in local-development mode without authentication, so do not expose it publicly.

## Enable a real local model
The API can call an Ollama server compatible with `POST /api/chat`.
Set:
- `JASSIM_OLLAMA_URL` (default `http://127.0.0.1:11434`)
- `JASSIM_OLLAMA_MODEL` (default `qwen3.5:4b`)
- `JASSIM_OLLAMA_AUTH_TOKEN` (optional; sends `Authorization: Bearer ...` on model and readiness requests when a trusted HTTPS authentication proxy protects a remote Ollama endpoint)

**Remote endpoint security:** Ollama's HTTP API does not authenticate requests by itself. `JASSIM_OLLAMA_AUTH_TOKEN` only adds a bearer header; it does not make Ollama validate that token. Configure a trusted HTTPS reverse proxy in front of remote Ollama to enforce the bearer token, and keep the raw Ollama port private. Never point this setting at a publicly exposed, unauthenticated Ollama server. Store the token only in the API host's secret environment; do not put it in Android or dashboard code.

Example:
```sh
JASSIM_OLLAMA_MODEL=qwen3.5:4b python server.py
``

If Ollama or the configured private model is unavailable, chat fails closed with HTTP 503 and an explicit message. The user's prompt is not forwarded to another host or hosted AI provider.

## Android compatibility
The API supports `POST /api/chat` for a complete JSON response and `POST /api/chat/stream` for Server-Sent Events. The current Android client uses the streaming route and requires an HTTPS server URL plus an account session token or configured operator token.

## Current limits
This is a self-hosted API foundation, not an unlimited GPU host. A 3 GB Android phone can host the API and SQLite store, but it is not suitable for large LLM inference. For larger models, connect a separately owned computer or GPU host with sufficient RAM/VRAM and persistent storage.


## Single private inference engine

JASSIM uses one inference engine only: the Ollama instance in the private Docker Compose network. Chat requests are never routed to hosted model providers. If the private model is unavailable, the API returns HTTP 503 and explicitly reports that the message was not sent elsewhere. Image generation through hosted inference providers is not enabled in this private-only configuration.

## Shared PostgreSQL storage and horizontal replicas (v0.6)

When `DATABASE_URL` is configured, the API stores chat messages and conversation memories in PostgreSQL through the shared `storage.py` adapter. Without it, local development and tests continue to use SQLite.

On the first PostgreSQL startup, the backend checks the existing `JASSIM_DATA_DIR/jassim.db` SQLite file and imports its messages and memories once. The source SQLite file is retained; the migration is marked in PostgreSQL so later replicas do not repeat it. All API replicas then share the same records.

When PostgreSQL is configured, set `DATABASE_URL` through the private environment of the chosen self-hosted deployment platform. After migration and verification, retain a backup of the original SQLite volume before detaching it. Multiple API replicas can then share the PostgreSQL data layer. Model inference still uses only the configured private Ollama instance; database scaling does not add hosted model providers or route prompts outside the private deployment.


# JASSIM AI Multi-user Accounts

## Authentication API

The backend now supports account sessions in addition to the legacy operator token:

- `POST /api/auth/register` — JSON body: `{"email":"person@example.com","password":"at-least-10-characters"}`. Returns a one-time opaque bearer token.
- `POST /api/auth/login` — same JSON body; returns a new session token.
- `GET /api/auth/me` — returns the authenticated account profile.
- `POST /api/auth/logout` — revokes the current session.

Send the returned token on normal API requests as `Authorization: Bearer <session-token>`. Tokens expire after 30 days. The server stores only a SHA-256 digest of each random session token. Passwords are stored using PBKDF2-HMAC-SHA256 with a unique random salt (310,000 iterations); passwords must be at least 10 characters.

## Account privacy and migration

Every conversation has one owner in the `conversations` table. History, memory, listing and deletion are scoped to the authenticated owner. A user cannot claim an existing conversation ID belonging to another account. Existing messages and memories are assigned to the non-login `legacy-owner` account during schema initialization; they are not exposed to newly registered accounts.

`JASSIM_API_TOKEN` remains an operator/admin credential for maintenance and backwards compatibility. It must not be embedded in a distributed APK or shared with ordinary users. New users receive their own session token after login or registration.

## Current beta limitations

Registration is open and currently protected by the API's per-process IP rate limiter. Email verification and password reset are not yet implemented. Do not treat this as a finished public launch until registration abuse protection is moved to shared storage, email verification/recovery is configured, and the Android and dashboard login screens are deployed. Always use HTTPS for public traffic.

The main branch includes Android and dashboard login/register/logout controls. Android stores the opaque session token using Android Keystore-backed encryption; the dashboard keeps it in sessionStorage for the current tab. Client account features require a deployment that is running the matching backend revision and has its database and session configuration set correctly.
