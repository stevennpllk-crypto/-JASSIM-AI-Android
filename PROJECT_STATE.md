# JASSIM AI — Project Handoff State

Last updated: 2026-11-21 (Africa/Tunis)
Purpose: durable handoff between ChatGPT conversations. This file records verified repository facts separately from historical reports and unverified work.

## Canonical project
- Repository: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android
- Default branch: main
- Product: Arabic-first Android assistant + self-hosted Python API + SQLite + Arabic RTL dashboard.
- Current verified main commit: `fc7d071f10c355c0b4309dec25cca990d3163c25`
- Commit date: 2026-11-21 21:47:53 UTC
- Commit message: `docs: add durable JASSIM AI project handoff state` (documentation-only; added this file)
- Latest verified application-code baseline remains `e676868d4d584148ef87493f0c6d439f7eab48c0`.

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

## Current privacy-hardening work (unmerged)
- Pull request #19: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/pull/19
- Branch: `fix/opt-in-public-providers`; head currently contains changes removing the anonymous JarvisClaw CI probe, changing `JASSIM_ENABLE_PUBLIC_PROVIDERS` default to `false`, and adding opt-in regression coverage.
- The PR is open and must not be merged without review/approval.
- The available Actions lookup returned no PR-triggered workflow runs for the current head, and its combined commit status was empty. CI therefore remains unverified; inspect the PR Checks tab before claiming test success.

## Latest known CI / build history (historical; re-check before relying on it)
- Earlier report: run #499 passed 20 backend tests, notebook validation, server health, APK compilation/package verification and artifact upload. Android unit tests/device runtime were not established by that report.
- Earlier report: run #500 compiled an APK but emulator startup failed after a 600-second wait (adb exit 224 / broken pipe); no artifact was reported.
- A prior handoff mentioned run #501 as in progress, but its completion was never verified in the available conversation context.
- These run numbers/statuses are historical notes, not a statement of current GitHub Actions status. Check the latest Actions run and its artifacts before reporting current build status.

## Current verified workflow concern to audit
- On `main` at `fc7d071`, `.github/workflows/android.yml` still includes an optional anonymous JarvisClaw synthetic prompt probe. PR #19 removes it.
- On `main`, `JASSIM_ENABLE_PUBLIC_PROVIDERS` defaults to `true`, while ordinary chat is separately gated by `JASSIM_ALLOW_EXTERNAL_CHAT=false`. PR #19 changes the public-provider master switch to default `false`, so NPC routing/evaluation also require explicit server-side opt-in.
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
1. Review PR #19 and inspect its GitHub Actions Checks tab; verify backend tests, notebook validation, APK build, package integrity, and artifact upload independently.
2. Inspect remaining external provider paths and confirm ordinary private chats and stored history cannot be routed externally by default.
3. Verify `/ready` and an authenticated synthetic chat only against an authorized test environment; do not use real conversation data.
4. Build and verify the APK artifact. Report compile/package success separately from emulator/device runtime success.
5. Keep PR #19 unmerged until reviewed; do not deploy production or spend money without explicit approval.
6. Update this file after each meaningful verified milestone, including commit SHA, test results, APK artifact link/expiry, and unresolved issues.

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
