# Production privacy and deployment audit — 2026-11-12

## Scope and verified production mapping

The Android app's default API URL is `https://jassim-ai-core-final-production.up.railway.app`. The matching Railway service is `jassim-ai-core-final` in the `JASSIM HUB` production environment. The service is attached to this repository's `main` branch, has two online replicas, and currently has no attached volume. The separate PostgreSQL service is online and has a persistent volume. The project also contains an offline `jassim-remote-mcp` service.

The API service exposes port 8787 and Railway's configured health check is `/health`. Its configured environment variable names include `JASSIM_ALLOW_EXTERNAL_CHAT`, `JASSIM_ENABLE_PUBLIC_PROVIDERS`, `JASSIM_OLLAMA_URL`, and `DATABASE_URL`; Railway's configuration inspection redacts variable values.

## Model readiness and privacy findings

- Runtime/startup logs identify the configured model as `qwen3.5:4b` and the Ollama URL as `http://127.0.0.1:11434`.
- No separate Ollama service exists in the inspected `JASSIM HUB` project. Unless Ollama is running inside the same API container, loopback points to the API container itself and cannot reach a different Railway service.
- The API container has no persistent volume. PostgreSQL does have persistent storage.
- The Railway health check targets `/health`, which is an API liveness check; a green deployment does not prove that Ollama is reachable or that the model is loaded.
- The source defines a stricter `/ready` check that should fail unless local model readiness is established or external inference is enabled. A successful `/ready` response alone must also be inspected to confirm which mode made it ready.
- Production variable values were not exposed by the read-only configuration inspection. Therefore the actual values of `JASSIM_ALLOW_EXTERNAL_CHAT` and `JASSIM_ENABLE_PUBLIC_PROVIDERS` have not been independently verified in the running production process.
- No successful synthetic inference through a confirmed local Ollama route was demonstrated in this audit. Do not claim that production inference is currently local-only or that the model is ready.
- The separate Railway service/project named `mahdia-ai-api-production` is not the Android app's configured default hostname. Do not conflate that separate service with `JASSIM HUB`.

## Client-side safeguards in the development branch

The Android client treats explicit external-provider flags, public/fallback provider modes, and non-local provider names as external. It only permits chat when the health check has completed, the local model is reported ready, and no external route is reported. This is a client-side fail-closed safeguard; it does not change server routing and cannot compensate for an incorrectly reported health payload.

## CI privacy change

The Android workflow no longer sends a synthetic prompt to a public AI endpoint. It audits production health/readiness metadata without invoking a public AI inference provider.

## Required safe deployment plan

Do not change the production domain or migrate real user data until all of the following are completed:

1. Deploy the reviewed Python API from an explicitly approved commit, rather than an unreviewed generic provider proxy.
2. Provide a real Ollama runtime reachable from the API service over a private service address, or co-locate it in the same container with a correct loopback configuration.
3. Pin and install the selected model on persistent storage. Validate that the chosen Railway CPU/RAM/GPU resources can load and serve it before committing to a production topology.
4. Set `JASSIM_ALLOW_EXTERNAL_CHAT=false` and `JASSIM_ENABLE_PUBLIC_PROVIDERS=false`; verify the effective values from the running process without exposing secrets.
5. Verify `/health` reports the expected local engine, model readiness, and external routing disabled; verify `/ready`; then send a synthetic authenticated request and confirm the selected engine is Ollama.
6. Test Android registration, login, chat streaming, cancellation, and history isolation with synthetic test accounts and data.
7. Define database backup/restore and rollback procedures. PostgreSQL already has a persistent volume; do not recreate or overwrite it.
8. Only after all checks pass, plan a controlled domain cutover and rollback.

No production variables, domains, deployments, databases, or services were changed during this audit. No GPU or other paid resource was created. A passing APK build is not evidence that production model inference is working.
