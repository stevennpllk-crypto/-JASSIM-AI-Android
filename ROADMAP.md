# JASSIM AI — Product Roadmap

## Product goal

Build an independent, Arabic-first AI assistant with a polished Android app and web client. The goal is to approach the useful product experience of leading assistants while remaining honest about model limits, privacy, latency, and hosting costs. This project does not copy GPT-6 weights, proprietary infrastructure, hidden prompts, or private implementation.

## Product principles

1. Arabic and Tunisian Arabic are first-class languages; support RTL throughout the app and dashboard.
2. Never pretend a fallback, cached response, or tool failure is a model answer.
3. Never expose API tokens, provider keys, private conversations, or server internals.
4. Keep user data portable and exportable; provide clear delete/export controls before calling memory persistent.
5. The Android app must remain usable on entry-level devices and tolerate unstable mobile networks.
6. Every tool action must be explicit, permissioned, logged, and confirmed.
7. Keep the core self-hostable; optional external model providers must be opt-in.

## Capability roadmap

### Phase 0 — Reliable foundation
- [x] Native Android client and HTTPS-only remote endpoint validation.
- [x] Android Keystore AES-GCM encryption for the saved API token.
- [x] Python API, SQLite conversation storage, Bearer authentication, message limits, and per-IP rate limiting.
- [x] Protected conversation-history endpoint.
- [x] Honest non-AI fallback instead of claiming a generated answer.
- [x] Public health endpoint with bounded Ollama/model readiness checks.
- [x] Authenticated installed-model listing endpoint.
- [x] CI smoke tests for API health, chat persistence, and protected/validated history access.
- [x] Deterministic CI integration test against a local Ollama-compatible mock, including generation settings and readiness.
- [ ] Add an explicit offline-engine test and retry/error telemetry.
- [ ] Add request IDs, structured logs, and safe error categories.

### Phase 1 — ChatGPT-like conversation experience
- [ ] Stream generated text to Android and web clients (SSE) with cancel support.
- [x] Restore the active conversation transcript on Android app startup.
- [x] Conversation list, open, and delete with confirmation; rename, archive, search, and export remain planned.
- [ ] Markdown rendering, code blocks, copy buttons, and syntax highlighting.
- [ ] Regenerate response, edit-and-resend, stop generation, and retry.
- [ ] Per-user accounts and short-lived revocable sessions; remove the shared-token-only limitation.
- [ ] Server-side conversation ownership and authorization checks.

### Phase 2 — Personal memory and knowledge
- [ ] User-controlled saved facts with inspect, edit, disable, export, and delete.
- [ ] Explicit memory consent and source tracking.
- [ ] Long-term conversation summaries with user controls.
- [ ] File upload and text extraction for PDF, DOCX, TXT, and common formats.
- [ ] Retrieval-augmented generation (RAG) with citations to uploaded sources.
- [ ] Search across a user's own conversations and files.

### Phase 3 — Tools and multimodal features
- [ ] Search tool with source citations and clear freshness indicators.
- [ ] Calculator, date/time, unit conversion, and other deterministic tools.
- [ ] Sandboxed code execution with strict resource and network limits.
- [ ] Image understanding and optional image generation through configured providers.
- [ ] Audio input/output and speech controls.
- [ ] Tool permission prompts, audit trail, and action confirmation.
- [ ] Never claim a tool ran unless its result was received and checked.

### Phase 4 — Model quality and operations
- [x] Configurable Ollama model, context size, output budget, timeout, history window, and model keep-alive.
- [ ] Configurable local model registry and model selection.
- [ ] Benchmark Arabic, Tunisian Arabic, reasoning, coding, latency, and memory use.
- [x] Stronger Arabic/Tunisian system instructions, larger default answer budget, and bounded recent-history context.
- [x] Colab watchdog that restarts crashed API/model/tunnel processes while the runtime remains alive.
- [ ] Model-specific context limits and prompt templates.
- [ ] Optional cloud providers through server-side secrets only; never embed provider keys in APK or browser code.
- [ ] Health, readiness, latency, token usage, storage, and error dashboards.
- [ ] Backups, restore drills, database migrations, and retention controls.
- [ ] Stable HTTPS deployment and documented upgrade/rollback process.

### Phase 5 — Product polish
- [ ] Responsive premium Arabic RTL web experience and accessible Android UI.
- [ ] Light/dark themes, font scaling, keyboard navigation, and screen-reader labels.
- [ ] Offline draft queue and retry when mobile connectivity returns.
- [ ] Localization and user-facing privacy/security settings.
- [ ] Automated release builds, signing guidance, crash reporting with privacy controls.

## Current honest limitations

- The current backend is a single shared Bearer-token service, not a multi-user product.
- The recommended model baseline is Qwen 2.5 3B. It is stronger than the previous 0.5B default but still a compact model; quality and speed depend on the host GPU/RAM and quantization. Keep-alive applies only while the Ollama runtime itself remains running.
- The API currently returns complete JSON responses, not streamed tokens. The default inference budget is now 8K context / 2K output with a 24K-character recent-history cap; actual quality still depends on the selected model and available GPU/RAM. Ollama is configured to keep the model loaded during the lifetime of its process, but there is no automatic restart or always-on host guarantee.
- Android can list recent conversations, open one, and delete one after confirmation. Rename, archive, search, and export are not implemented yet.
- The dashboard and Android client do not yet offer full file, image, audio, or tool workflows.
- Colab watchdog recovery can restart crashed processes only while the runtime is alive. Colab and quick tunnels remain temporary development infrastructure, not reliable always-on hosting.
- Free hosting does not guarantee persistent storage, sufficient RAM, or GPU access.

## Definition of done

A capability is complete only when it has:
1. A working implementation, not a mock screen.
2. Automated tests for success, failure, and permission boundaries.
3. A real Android/web integration test.
4. Clear privacy and data-retention behavior.
5. Documentation of setup, limits, and rollback.
6. Evidence from a successful CI build or deployment before it is described as shipped.
