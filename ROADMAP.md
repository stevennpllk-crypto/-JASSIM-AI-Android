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
- [x] Add an explicit offline-engine test and verify fallback replies are not saved as AI answers.
- [ ] Add retry/error telemetry.
- [ ] Add request IDs, structured logs, and safe error categories.

### Phase 1 — ChatGPT-like conversation experience
- [ ] Stream generated text to Android and web clients (SSE) with cancel support.
- [x] Restore the active conversation transcript on Android app startup.
- [x] Conversation list, open, and delete with confirmation; rename, archive, search, and export remain planned.
- [x] Android long-press message copying and keyboard send action.
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
- [x] Stronger Arabic/Tunisian system instructions, larger 3072-token answer budget, and bounded 32K-character recent-history context.
- [x] Colab selects Qwen3.5 9B when an NVIDIA GPU is detected, with a 4B low-resource fallback.
- [x] Serialize model inference by default with a bounded queue to reduce GPU memory spikes under concurrent requests.
- [x] Colab watchdog that restarts crashed API/model/tunnel processes while the runtime remains alive.
- [ ] Model-specific context limits and prompt templates.
- [ ] Optional cloud providers through server-side secrets only; never embed provider keys in APK or browser code.
- [ ] Health, readiness, latency, token usage, storage, and error dashboards.
- [ ] Backups, restore drills, database migrations, and retention controls.
- [x] Documented restartable Docker deployment, persistent model/database volumes, and readiness checks.
- [ ] Operate the stack on an always-on host with stable HTTPS, backups, monitoring, and a tested restore/rollback process.

### Phase 5 — Product polish
- [ ] Responsive premium Arabic RTL web experience and accessible Android UI.
- [ ] Light/dark themes, font scaling, keyboard navigation, and screen-reader labels.
- [ ] Offline draft queue and retry when mobile connectivity returns.
- [ ] Localization and user-facing privacy/security settings.
- [ ] Automated release builds, signing guidance, crash reporting with privacy controls.

## Current honest limitations

- The current backend is a single shared Bearer-token service, not a multi-user product.
- The self-hosted API default is Qwen 3.5 4B. The Colab GPU notebook selects Qwen 3.5 9B when it detects an NVIDIA GPU and falls back to 4B otherwise. Stronger answers require a larger capable model and sufficient host RAM/VRAM; model selection is configurable through `JASSIM_OLLAMA_MODEL`. Quality and speed depend on host memory and quantization. Keep-alive applies only while Ollama itself remains running.
- The API currently returns complete JSON responses, not streamed tokens. The standard API profile defaults to 8K context / 3K output with a 24K-character recent-history cap; the Colab GPU profile raises recent history to 32K characters. Actual quality still depends on the selected model and available GPU/RAM. Ollama keep-alive holds the model in memory while the process runs. Colab Watchdog and Docker restart policies recover crashed processes, but neither can keep an interrupted Colab session or suspended host alive.
- Android can list recent conversations, open one, and delete one after confirmation. Rename, archive, search, and export are not implemented yet.
- The dashboard and Android client do not yet offer full file, image, audio, or tool workflows.
- Colab watchdog recovery can restart crashed processes only while the runtime is alive. The Docker deployment can restart crashed services on an always-on host; Colab and Quick Tunnels remain temporary.
- Free hosting does not guarantee persistent storage, sufficient RAM, or GPU access.

## Definition of done

A capability is complete only when it has:
1. A working implementation, not a mock screen.
2. Automated tests for success, failure, and permission boundaries.
3. A real Android/web integration test.
4. Clear privacy and data-retention behavior.
5. Documentation of setup, limits, and rollback.
6. Evidence from a successful CI build or deployment before it is described as shipped.
