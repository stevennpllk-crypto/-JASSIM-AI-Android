# Production privacy and deployment audit — 2026-11-12

## Verified state

This audit was performed against the Railway production environment, not inferred from repository files.

- The environment reported one online service named `mahdia-ai-api`, one running replica, no attached volume, and no pending deployment.
- The Railway-generated domain `mahdia-ai-api-production.up.railway.app` is attached directly to that same service; domain listing returned no custom domains.
- The Android app's current default API URL is `https://jassim-ai-core-final-production.up.railway.app`. A separate Railway project named `JASSIM HUB` contains a `jassim-ai-core-final` service whose generated domain matches that URL exactly; the service is attached to this repository's `main` branch and is online with 2/2 replicas.
- The `JASSIM HUB` API service has no mounted volume. Its separate PostgreSQL service is online and has a persistent volume. The API's current runtime logs identify the database as PostgreSQL and the configured model as `qwen3.5:4b` at `http://127.0.0.1:11434`.
- `JASSIM HUB` contains no separate Ollama service. The configured loopback URL points inside each API container, not to an Ollama service in the project. No Ollama reachability or successful local inference was established in this audit. The actual variable values are redacted by the Railway connection, so the production privacy flags could not be independently read back.
- The live service image was `ghcr.io/railwayapp/function-bun:1.4.4`, not the repository's Python API container.
- Its start command contains an inline Bun handler rather than a checkout of this repository.
- The decoded handler selects configured public providers when their variables exist and otherwise defaults to the anonymous `pollinations-anonymous-fallback` provider at `https://text.pollinations.ai/openai`.
- The service's visible variable-name list contained only Railway platform variables; no model, Ollama, or provider credentials were listed.
- The handler's health payload reports a provider/readiness mode, but does not implement the Python API's complete local-model readiness contract.
- No production variables, domains, deployments, databases, or services were changed during this audit.

**Conclusion:** the Android default URL maps to the Python API service in `JASSIM HUB`, but the model endpoint currently points to loopback and no Ollama service exists in that project. The inspected `mahdia-ai-api-production` service is a separate Bun proxy with an anonymous public-provider fallback; it is not the Android app's default hostname. Neither API liveness nor the presence of PostgreSQL proves local inference readiness. Do not describe the production model as ready or private-only until Ollama reachability, model readiness, disabled external routing, and a successful synthetic inference are directly verified.

## Client-side safeguards added

The Android client now treats explicit external-provider flags, public/fallback provider modes, and non-local provider names as external. It only permits chat when the health check has completed, the local model is ready, and no external route is reported. This is a client-side fail-closed safeguard; it does not change the server's routing behavior.

## CI privacy change

The Android workflow no longer sends a synthetic prompt to the public JarvisClaw endpoint. It now records production model readiness and external-provider routing as a CI summary and warning, without invoking a public AI inference provider.

## Safe cutover requirements

Do not switch the production domain until all of the following are true:

1. Deploy the repository's `backend/server.py` API from a reviewed commit, not an inline generic provider proxy.
2. Run Ollama with a locally installed, pinned model on infrastructure sized for that model. Keep model weights on persistent storage.
3. Set `JASSIM_ALLOW_EXTERNAL_CHAT=false` and `JASSIM_ENABLE_PUBLIC_PROVIDERS=false`; verify both are disabled in the actual running process.
4. Provide persistent storage for the API database and model weights; define backup and restore procedures before migrating any real accounts or conversations.
5. Verify `/health` reports the local model as ready and external routing disabled, then verify `/ready` and a synthetic authenticated chat request use the `ollama` engine.
6. Test Android registration, login, chat streaming, cancellation, and history isolation against the new service using synthetic test accounts and data.
7. Only after these checks pass, plan a controlled domain cutover and rollback. Do not delete the existing service or migrate production data as part of an unreviewed build.

A dedicated GPU host, persistent database, or other paid resource must be explicitly approved before it is created or enabled. A passing APK build is not evidence that this server cutover has happened.
