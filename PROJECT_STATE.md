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
- GitHub Actions run #598 (event: `pull_request`, head `a220573df1950494bdbf9e240d06efcfe370f97d`) completed successfully on 2026-11-21 21:53 UTC. Job `build` passed all steps: notebook JSON/code validation, 21 backend unit tests, deployed `/health` probe, Gradle debug APK build, APK ZIP integrity/required-entry verification, and artifact upload.
- APK verified by CI: 40,473 bytes; SHA-256 `52b510738fb9918a68d6373b54fe59abaa66c7d86dfbe9cdf7d6916a52dba940`.
- Artifact `JASSIM-AI-debug-APK`, ID `14726468586`, expires 2027-02-19 21:52:29 UTC. Download: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/actions/runs/44953779990/artifacts/14726468586
- Run #603 (head `d1ebaf30ed607353de2b62069c62a82d21cc1d24`) completed successfully: 24 backend/static tests, notebook validation, deployed `/health`, Gradle debug APK build, APK integrity checks, and artifact upload.
- The 3 Android privacy regression tests passed: no direct public LLM endpoints, chat only through the configured JASSIM backend, and HTTPS/session-token request checks.
- The unauthenticated image-generation regression test passed as part of the 24-test suite.
- Latest APK: 36,297 bytes; SHA-256 `49e2d4ca2a97042b8b53d1eb6d0d9bdab3e710d00358c37600d38f2aa9a72bc3`.
- Artifact `JASSIM-AI-debug-APK`, ID `14727201559`, expires 2027-02-19 21:59:32 UTC. Download: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/actions/runs/44954357038/artifacts/14727201559
- Follow-up fix: `backend/server.py` now defines `/ready` for ordinary chat only (private Ollama model ready or explicitly enabled ordinary external chat); NPC-only provider availability no longer makes ordinary chat appear ready.
- Regression test `test_npc_provider_does_not_mark_private_chat_ready` verifies that with Ollama unavailable, public providers enabled, and ordinary external chat disabled, `/ready` remains HTTP 503.
- GitHub Actions run #605 passed on head `b8cf20227a3a61c362ddda8145451d1b40aecefd`: 25 backend tests in 3.426s (including the new readiness regression), notebook validation, deployed `/health`, Gradle debug APK build, APK integrity checks, and artifact upload.
- Latest APK: 36,297 bytes; SHA-256 `7967d151dd0d69378f57bef949fdabca86428a1fefdbd4ac3f4433642589febd`.
- Artifact `JASSIM-AI-debug-APK`, ID `14727685207`, ZIP size 32,543 bytes; artifact ZIP digest `sha256:9ac1936c1cbd9f22f4d4190bcb61c2991a9a9eb5fea949013b8e646e609251c5`. Download: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/actions/runs/44955673750/artifacts/14727685207 (expires 2027-02-19 22:14:05 UTC).
- Run #605 still checks only deployed `/health`; it does not prove production `/ready`, authenticated live inference, or physical-device runtime. The readiness fix is unit-tested only.
- CI log warning: GitHub Actions reports Node.js 20 deprecation for several pinned action major versions; no compatibility migration has been made yet.
- Account-memory isolation regression: extended `test_accounts_cannot_read_or_delete_each_others_chats` to verify another account cannot read, overwrite, or clear the first account's conversation memory; owner can still read and clear it.
- GitHub Actions run #607 passed on head `27c2ae9b4ebc68eafa5e93d8fc8f5889ed07eac9`: 25 backend tests in 3.493s, notebook validation, deployed `/health`, Gradle debug APK build, APK ZIP integrity/required-entry checks, and artifact upload.
- Latest APK: 36,296 bytes; SHA-256 `ce6ccd936c58dd796e6b2d6e63927acd62e52cfc8d08ef17f104e56d1641c22b`.
- Artifact `JASSIM-AI-debug-APK`, ID `14727674568`, ZIP size 32,544 bytes; ZIP digest `sha256:3ce83a295f7bc93372474811db64783373c650fe946b299410f856f487dfd3a8`. Download: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/actions/runs/44957795272/artifacts/14727674568 (expires 2027-02-19 22:38:30 UTC).
- No emulator/device install or live user-chat test was performed. The workflow checks deployed `/health`, not `/ready` or inference. Do not imply device runtime success.
- Note: the connector's commit-run wrapper returned an empty list, but the GitHub Actions REST runs endpoint confirmed run #598; use the direct endpoint for subsequent run discovery.

## Latest known CI / build history (historical; re-check before relying on it)
- Earlier report: run #499 passed 20 backend tests, notebook validation, server health, APK compilation/package verification and artifact upload. Android unit tests/device runtime were not established by that report.
- Earlier report: run #500 compiled an APK but emulator startup failed after a 600-second wait (adb exit 224 / broken pipe); no artifact was reported.
- A prior handoff mentioned run #501 as in progress, but its completion was never verified in the available conversation context.
- These run numbers/statuses are historical notes, not a statement of current GitHub Actions status. Check the latest Actions run and its artifacts before reporting current build status.

## External provider audit (read-only inspection)
- Text generation provider calls are centralized in `backend/adaptive.py`; ordinary external chat additionally requires `JASSIM_ALLOW_EXTERNAL_CHAT=true`. PR #19 also defaults the public-provider master switch to `false`, covering provider evaluation and the NPC opt-in path.
- Image generation uses Hugging Face only through the explicit authenticated `/api/images/generate` endpoint. The endpoint requires an authenticated session; the provider token is read server-side from `JASSIM_HF_TOKEN`. A prompt explicitly submitted to this endpoint is sent to Hugging Face when the token is configured. Do not describe image prompts as private/local in that configuration.
- CI's former anonymous JarvisClaw probe is removed on the PR branch. No production settings or deployments were changed.
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
1. Re-check the latest PR head and CI after this handoff update; the current verified run is #598 on the previous head.
2. Review Node 20 deprecation warnings and migrate compatible GitHub Actions to supported Node 24-compatible releases after checking compatibility.
3. Verify `/ready` and an authenticated synthetic chat only against an authorized test environment; do not use real conversation data.
4. Keep PR #19 unmerged until reviewed; do not deploy production or spend money without explicit approval.
5. Test installation/runtime on a real device separately from APK compilation.

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


## Security follow-up and latest verified build (2026-11-21 22:46 UTC)
- Login timing hardening: unknown email addresses now perform a dummy PBKDF2-HMAC-SHA256 verification before returning the same generic `invalid_credentials` response as a wrong password. Password verification rejects empty inputs and inputs over 256 characters.
- NPC routing authorization hardening: a request's `context=game_npc` field no longer grants ordinary user accounts the public-provider exception. Only the server-admin identity can request that path; the public-provider master switch must still be enabled.
- Added HTTP regression coverage for unknown-account PBKDF2 work and for a normal authenticated account attempting to forge `context=game_npc`. Existing test suite remains 25 test methods; all pass in run #611 (3.627 seconds).
- Removed `.github/workflows/probe-llm-fallback.yml`. The repository branch now contains only `.github/workflows/android.yml` and `.github/workflows/pages.yml`; no separate automatic anonymous-provider probe workflow remains on this PR branch.
- Important audit disclosure: before deletion, workflow run #137 completed successfully and its two steps contacted JarvisClaw and OVH using only the fixed synthetic prompt `Reply exactly: JASSIM ONLINE`. These were not user conversation transcripts. The workflow file has since been deleted on this branch.
- Run #611 passed on exact latest application branch head `8a7e9f0e879e30b7c3ebc7ab096bf1891f7d408d`: 25 backend tests, notebook code validation, deployed `/health` probe, Gradle debug APK build, APK package integrity verification, and artifact upload.
- Latest APK: 36,301 bytes; SHA-256 `2e373cf3ce6197ad4ab701c1474eb23888ba5fba78f9e453056bc1d66c46b980`.
- Artifact `JASSIM-AI-debug-APK`, ID `14727874863`, size 32,548 bytes; ZIP digest `sha256:e29bfa99547ed82f54006be36cbbaf4cc9fe1364f5536d3b7d6eef93949e2302`. Download: https://github.com/stevennpllk-crypto/-JASSIM-AI-Android/actions/runs/44958330742/artifacts/14727874863 (expires 2027-02-19 22:44:58 UTC).
- Run #611's workflow still does not prove physical-device install/runtime or successful authenticated live inference. The deployed check is `/health`, not `/ready` or model inference.
- PR #19 remains open and unmerged. No production deployment, paid provider, or production configuration was changed.
