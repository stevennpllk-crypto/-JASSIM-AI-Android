# JASSIM AI Self-Hosted Backend

A small self-hosted HTTP API for the existing JASSIM AI Android client. It uses only Python's standard library and keeps chat history in SQLite.

## Safety defaults
- Binds to `127.0.0.1` only. Do not expose it to the public internet as-is.
- No API keys are embedded in the Android APK.
- Set `JASSIM_API_TOKEN` before public deployment. The Android app and dashboard send it as `Authorization: Bearer ...`.
- The dashboard keeps the token in session storage only; the Android app stores it in private app preferences.
- Set `JASSIM_CORS_ORIGIN` to the exact HTTPS dashboard origin, not `*`, before public deployment.
- Request size and message length are limited.
- Chat history is stored locally in `backend/data/jassim.db`.

## Run on Termux (Android)
1. Install Python in Termux: `pkg install python`
2. Download/clone this repository, then enter its `backend` directory.
3. Start the API: `python server.py`
4. In another Termux session, test it:
   ```sh
   curl http://127.0.0.1:8787/health
   curl -X POST http://127.0.0.1:8787/api/chat -H 'Content-Type: application/json' -d '{"message":"مرحبا","conversation_id":"test"}'
   ```

## Enable API authentication
Generate a long random token and configure it as an environment variable on the server (never commit it to Git):

```sh
export JASSIM_API_TOKEN="paste-a-long-random-secret-here"
export JASSIM_CORS_ORIGIN="https://stevennpllk-crypto.github.io"
python server.py
```

Enter the same token in the Android app settings or the dashboard connection settings. `/health` remains public for connection checks; chat and history require the token. If `JASSIM_API_TOKEN` is unset, the server remains in local-development mode without authentication, so do not expose it publicly.

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
The API preserves the existing contract: `POST /api/chat` with JSON `{"message":"..."}`, returning both `answer` and `reply`. The current Android app can use this endpoint after local-network cleartext policy and automatic connection are configured in a later, separate change.

## Current limits
This is the first server foundation, not an unlimited GPU host. A 3 GB Android phone can host the API and SQLite store, but it is not suitable for large LLM inference. For larger models, connect a separately owned computer with sufficient RAM/VRAM and point `JASSIM_OLLAMA_URL` at that machine over a private network.
