# JASSIM AI — Privacy and outbound-connection audit
Date: 2026-11-12
Scope: current branch `fix/android-message-line-breaks`; production deployment is tracked separately.

## Executive result

The current branch hard-disables public LLM inference. Synchronous and streaming fallback functions must fail closed when the private Ollama model is unavailable. The API accepts Ollama only on loopback or a Railway private hostname. This is a code-level policy; it does not prove that the currently deployed production service has these changes.

## Outbound paths found

| Component | Destination / mechanism | Data leaving the component | Classification |
|---|---|---|---|
| Android startup | GitHub Pages `dashboard/connection.json` | A GET for a small public endpoint registry; no chat or account token | Static discovery; registry URL is pinned by the Android trusted-endpoint policy |
| Android chat / accounts / history | Configured JASSIM API (default Railway HTTPS) | Chat messages, account credentials during login/register, session bearer token, history operations | Required application traffic; the API host receives the data |
| Android custom endpoint | User-entered HTTPS host | Same API payloads and bearer token | Only after a warning/confirmation; trust depends on the user owning/trusting that host |
| Android voice input | Android `RecognizerIntent.ACTION_RECOGNIZE_SPEECH` | Microphone audio may be processed by the installed speech-recognition service | Externality depends on the device's selected recognizer; `EXTRA_PREFER_OFFLINE=true` is a preference, not a guarantee |
| Android voice output | Installed Android TextToSpeech engine | Text of the answer is passed to the selected TTS engine | May be on-device or network-backed depending on the installed engine and language pack |
| Backend chat | Private Ollama URL | Prompt and context, only to loopback or `*.railway.internal` | Private inference route; public hosts are rejected |
| Backend image generation | Private image-worker hostname | Image prompt and generation parameters, authenticated by a private bearer token | Private inference route; public worker URLs are rejected |
| Image worker first boot | Hugging Face model repository | Model-weight/configuration downloads into persistent cache | Artifact download; not a user-prompt inference endpoint |
| QLoRA training | Hugging Face model/tokenizer download via Transformers | Model artifacts are downloaded; local training dataset is read from disk and adapter saved locally | Training artifact acquisition; `report_to=none`; no dataset upload is implemented in the training script |
| GitHub Actions | GitHub, Actions, package registries, Gradle/Maven/PyPI | Source code and build dependencies; workflow calls production `/health` only | CI infrastructure; no user prompt is sent by the health probe |
| GitHub Pages dashboard | Static site hosting | Static HTML/CSS/JS and public connection registry | No chat data unless the browser itself calls the API |
| Dashboard browser | Configured API endpoint | Chat, account and history requests; token is held in sessionStorage, endpoint in localStorage | Required app traffic; verify the configured endpoint before use |
| Colab notebook (legacy/optional) | Google Colab/Drive, GitHub API, Cloudflare quick tunnel, GitHub-hosted Ollama installer | Notebook/runtime traffic; can publish a temporary tunnel URL into the repository registry | Third-party hosting/tunnel path; not a suitable permanent private production deployment |

## Public inference providers

The code contains provider definitions for Groq, JarvisClaw and OVHcloud. In this branch:
- `ALLOW_EXTERNAL_CHAT = False` and `ENABLE_PUBLIC_PROVIDERS = False` are hard-coded.
- Environment variables cannot turn either flag on.
- Both synchronous and streaming provider routes fail before calling `urlopen`.
- Provider evaluation returns disabled without a network request.
- The CI workflow that previously probed anonymous public providers has been replaced by a local-only policy test workflow.

The provider URL constants remain in the source for historical/test compatibility. They are not active routes while the hard-disable remains in place.

## Production caveat

The Railway production service was previously observed to be sourced from `main`, not this branch. Production network logs showed DNS lookups and outbound HTTPS flows involving external provider infrastructure near chat request timestamps. Those logs do not expose request bodies and therefore do not prove which prompt, if any, was transmitted. The old production code contains an external fallback path. Until the privacy branch is reviewed, merged and deliberately deployed, do not claim production is private-only.

## Residual privacy work

1. Decide whether voice input should display a clear disclosure before invoking the Android speech recognizer; offline preference is not a hard privacy boundary.
2. Offer a clear TTS privacy note or an offline-engine requirement for sensitive conversations.
3. Consider disabling arbitrary custom API endpoints in a consumer build, or retain the current explicit trust confirmation.
4. Keep the public discovery registry pinned to the canonical production origin; do not accept a Colab/Cloudflare quick-tunnel URL as a trusted production endpoint.
5. After an approved production rollout, inspect DNS/network telemetry again and perform a controlled synthetic chat test against the private Ollama service.
6. Keep API health checks free of user messages and credentials.

## Evidence and tests

- `backend/test_local_only.py`: environment variables cannot enable public routing; sync/stream routes fail before network access; provider evaluation is offline.
- `backend/test_server.py`: tests private endpoint validation and server fallback behavior.
- `backend/test_private_image.py` and `backend/test_image_privacy.py`: private worker URL, authentication and fail-closed behavior.
- `image-worker/test_app.py`: auth, readiness and local pipeline behavior.
- `app/src/main/java/com/jassim/ai/TrustedEndpointPolicy.java`: HTTPS-only endpoint validation and pinned public discovery host.
