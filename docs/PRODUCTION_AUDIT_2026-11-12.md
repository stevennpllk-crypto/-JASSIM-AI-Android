# Production privacy and deployment audit — 2026-11-12

## Verified state

This audit was performed against the Railway production environment, not inferred from repository files.

- The environment reported one online service named `mahdia-ai-api`, one running replica, no attached volume, and no pending deployment.
- The Railway-generated domain `mahdia-ai-api-production.up.railway.app` is attached directly to that same service; domain listing returned no custom domains.
- The Android app's current default API URL is `https://jassim-ai-core-final-production.up.railway.app`, which is a different hostname. This audit has **not** established which Railway service (if any) currently serves that app-configured hostname. The app's live backend mapping therefore remains unresolved and must be verified before any cutover.
- The live service image was `ghcr.io/railwayapp/function-bun:1.4.4`, not the repository's Python API container.
- Its start command contains an inline Bun handler rather than a checkout of this repository.
- The decoded handler selects configured public providers when their variables exist and otherwise defaults to the anonymous `pollinations-anonymous-fallback` provider at `https://text.pollinations.ai/openai`.
- The service's visible variable-name list contained only Railway platform variables; no model, Ollama, or provider credentials were listed.
- The handler's health payload reports a provider/readiness mode, but does not implement the Python API's complete local-model readiness contract.
- No production variables, domains, deployments, databases, or services were changed during this audit.

**Conclusion:** production has not been verified as private-only. The inspected `mahdia-ai-api-production` service is not the repository's self-hosted Python + Ollama stack and contains an anonymous public-provider fallback. Because the Android default URL is a different hostname, do not assume this inspected service is the app's active backend; resolve that hostname-to-service mapping first. Do not describe either endpoint as a private JASSIM model server without direct verification.

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
