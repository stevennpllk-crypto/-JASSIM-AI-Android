# JASSIM AI — Project Handoff State

Last updated: 2026-11-21 (Africa/Tunis)
Purpose: durable handoff between ChatGPT conversations. This file records verified repository facts separately from historical reports and unverified work.

## Canonical project
- Repository: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android
- Default branch: main
- Product: Arabic-first Android assistant + self-hosted Python API + SQLite + Arabic RTL dashboard.
- Current verified main commit: `e676868d4d584148ef87493f0c6d439f7eab48c0`
- Commit date: 2026-11-15 14:53:01 UTC
- Commit message: "Keep offline readiness tests isolated from optional free providers"

## Verified repository architecture (README.md and ROADMAP.md)
- Android client: `app/` (Java); HTTPS-only remote endpoint; API token stored with Android Keystore AES-GCM.
- Backend: `backend/server.py`; Python standard-library API; SQLite persistence; Bearer auth; request-size checks; per-IP rate limiting; Ollama readiness; authenticated model inventory; SSE streaming.
- Dashboard: `dashboard/`, Arabic RTL.
- Colab notebook: `notebooks/JASSIM_AI_Colab_GPU.ipynb`.
- CI workflow: `.github/workflows/android.yml` validates notebook code, runs backend unit tests, probes the configured Railway health URL, builds a debug APK, verifies APK ZIP integrity/required entries, and uploads the APK artifact.
- Pages workflow: `.github/workflows/pages.yml`.
- Roadmap explicitly distinguishes shipped features from planned features.

## Product and privacy constraints
- The core should remain self-hosted/private; external model providers are optional and must be opt-in.
- README says `JASSIM_ALLOW_EXTERNAL_CHAT=false` by default; enabling public-provider use for real chat requires explicit server-side opt-in.
- Never place API/provider tokens, tunnel credentials, or private keys in source, APK, dashboard JavaScript, public issues, or chat.
- Never send users' private conversation history to an external provider for a synthetic benchmark.
- No paid hosting, paid model tier, production deployment, or spending without the user's explicit approval.
- Do not claim an APK/device test, deployment, or feature is complete without verifiable evidence.

## Latest known CI / build history (historical; re-check before relying on it)
- Earlier report: run #499 passed 20 backend tests, notebook validation, server health, APK compilation/package verification and artifact upload. Android unit tests/device runtime were not established by that report.
- Earlier report: run #500 compiled an APK but emulator startup failed after a 600-second wait (adb exit 224 / broken pipe); no artifact was reported.
- A prior handoff mentioned run #501 as in progress, but its completion was never verified in the available conversation context.
- These run numbers/statuses are historical notes, not a statement of current GitHub Actions status. Check the latest Actions run and its artifacts before reporting current build status.

## Current verified workflow concern to audit
- The current `.github/workflows/android.yml` includes a "Probe anonymous JarvisClaw fallback" step using a fixed synthetic prompt. It is marked `continue-on-error: true`, so it is not required for a successful workflow.
- Confirm that this synthetic probe is still wanted and does not route any real user content. Keep ordinary JASSIM chats on the self-hosted server unless the operator explicitly enables an external provider.
- The current workflow also checks the Railway `/health` URL. A healthy API process does not prove model readiness or successful inference; verify `/ready` and an authenticated synthetic chat separately when authorized and safe.

## Roadmap priorities from ROADMAP.md
1. Reliability: retry/error telemetry, request IDs, structured safe logs.
2. Chat UX: Markdown/code rendering, regenerate, edit-and-resend, retry.
3. Security: per-user accounts, revocable sessions, conversation ownership and authorization.
4. Memory/knowledge: user-controlled memory, file ingestion, RAG and citations.
5. Tools/multimodal: search, deterministic tools, sandboxed code, image/audio flows, permission/audit trail.
6. Operations: Arabic/Tunisian benchmarks, health/latency/token/storage dashboards, backups/restore drills, stable always-on hosting only with approval.
7. Device verification: real install/runtime test on a supported Android device; emulator failures must be reported separately from APK compilation.

## Next actions for the next session
1. Re-check the latest main commit, open PRs, and latest Actions runs; do not assume the historical #499/#500/#501 state is current.
2. Inspect the exact code and tests behind the latest offline-readiness/provider-routing commits.
3. Audit every external network/provider path, especially the optional JarvisClaw workflow probe and NPC-only routing. Confirm normal private chats never leave the self-hosted backend by default.
4. Run backend tests and notebook validation; inspect job logs for any failure.
5. Build and verify the APK artifact. Report compile/package success separately from emulator/device runtime success.
6. Fix only evidence-backed issues, preferably on a dedicated branch with a PR; do not merge or deploy production without explicit approval.
7. Update this file after each meaningful verified milestone, including commit SHA, test results, APK artifact link/expiry, and unresolved issues.

## Reporting rules
Every progress report must distinguish:
- Code changes committed vs merely proposed.
- Backend/unit tests vs notebook checks vs APK compilation/package verification.
- Emulator boot/install/runtime tests vs successful APK build.
- CI artifact available vs APK actually installed and tested.
- Local health vs readiness vs successful authenticated model inference.
- Self-hosted inference vs optional external provider inference.
- Free/temporary hosting vs stable paid hosting.

Do not invent percentages of model quality or project completion. Any comparison must state its benchmark, model/version, test set, and date.
