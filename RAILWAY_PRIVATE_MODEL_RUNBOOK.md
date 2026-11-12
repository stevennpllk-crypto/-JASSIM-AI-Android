# JASSIM AI — Railway private Ollama service runbook

This runbook describes a **separate, private Ollama service** for the JASSIM API. It does not create resources, change the live API, or make public-provider routing available.

## Target topology

```text
Android app
    |
    | HTTPS
    v
Existing JASSIM API service
    |
    | Railway private network only
    | http://ollama.railway.internal:11434
    v
Dedicated Ollama service
    |
    +-- persistent volume mounted at /root/.ollama
    +-- configured local model weights
```

Do not point the API at `127.0.0.1:11434` when Ollama is a separate Railway service: loopback refers to the API container itself.

## Provisioning checklist (manual approval required)

1. In the **JASSIM HUB** Railway project, create a new service named `ollama` from the public Docker image `ollama/ollama:latest`.
2. Set the Ollama service start command to `ollama serve` if the image's default command is not retained.
3. Set `OLLAMA_HOST=0.0.0.0:11434` so the service listens on its private interface.
4. Attach a persistent volume at `/root/.ollama`. Without this, model weights can be lost on redeploy.
5. Do **not** add a public domain or TCP proxy for port 11434. The API should reach Ollama over Railway private networking only.
6. Allocate memory and CPU deliberately. The current API container has only 1 GB RAM and must not also host a 4B model. A 4B model needs several GB of memory once runtime/context overhead is included; benchmark the chosen quantization and context size before exposing it to users. GPU is optional for correctness but important for acceptable latency.
7. From the Ollama service shell, run `ollama pull qwen3.5:4b`, then `ollama list` and verify the exact configured model tag is present.
8. In the API service, set:
   - `JASSIM_OLLAMA_URL=http://ollama.railway.internal:11434`
   - `JASSIM_OLLAMA_MODEL=qwen3.5:4b`
   - `JASSIM_ALLOW_EXTERNAL_CHAT=false`
   - `JASSIM_ENABLE_PUBLIC_PROVIDERS=false`
   - `JASSIM_MAX_CONCURRENT=1` initially
   - Start with a conservative `JASSIM_NUM_CTX` (for example, 4096) and raise it only after memory/latency tests.
9. Redeploy the API only after verifying the Ollama service is healthy and reachable over the private network.

## Private image-generation service (separate from Ollama)

1. The worker implementation now lives in `image-worker/`: FastAPI authenticated API, CUDA-only Diffusers pipeline, Dockerfile, tests, and deployment notes. It defaults to the open-weights `stabilityai/sdxl-turbo` checkpoint; this is a self-hosted model, not a model trained from scratch by JASSIM. Review the model's current license and terms before public/commercial release.
2. Provision a dedicated Railway service only after explicit approval of GPU and storage costs. Set the service root directory to `image-worker` and use its Dockerfile.
3. Attach a persistent volume at `/models`; model cache is stored at `/models/huggingface`. First boot downloads weights; later restarts reuse the volume.
4. Allocate a supported NVIDIA CUDA GPU with enough VRAM for the selected checkpoint and runtime overhead. The service intentionally stays not-ready if CUDA is unavailable or model loading fails. Benchmark the exact instance before public use.
5. Set `JASSIM_IMAGE_WORKER_TOKEN` to a long random secret. Keep port 8188 private, with no public domain or TCP proxy.
6. In the JASSIM API service set `JASSIM_IMAGE_WORKER_URL=http://image-worker.railway.internal:8188` and the same `JASSIM_IMAGE_WORKER_TOKEN`.
7. Test authenticated readiness, Arabic prompts, invalid dimensions, timeouts, worker restart, and model persistence. Verify API logs show only the private worker route.
8. When the worker is unavailable, return a clear local-image-unavailable response. Do not switch to an external provider automatically.
9. External image services, if ever supported, are opt-in backups only. Require an explicit per-user setting and a clear disclosure before transmitting any prompt or reference image outside JASSIM infrastructure.

## JASSIM private image-worker API contract

The API client is implemented in `backend/private_image.py`. The image worker may use ComfyUI internally, but only this authenticated contract is exposed to the JASSIM API:

- API environment: `JASSIM_IMAGE_WORKER_URL=http://image-worker.railway.internal:8188`
- API secret: `JASSIM_IMAGE_WORKER_TOKEN` (a long random token shared only with the private worker)
- `GET /ready` with `Authorization: Bearer <token>` returns JSON with `ready: true`, `model_ready: true`, and a non-empty `model` only after model weights are loaded.
- `POST /v1/images/generate` with the same bearer token accepts JSON `{"prompt":"...","width":1024,"height":1024}`.
- A successful response contains `image_base64`, `mime_type` (`image/png`, `image/jpeg`, or `image/webp`), and a non-empty `model`.
- The API validates the private hostname, bearer token, response type, image signature, and a 15 MiB decoded-image limit. It rejects public worker URLs.
- The worker must not expose a public domain. Do not put the worker token in the Android app or repository.

The worker implementation is committed under `image-worker/`, but the Railway service, GPU, secret, and persistent volume have not been provisioned. A running process alone is not enough: readiness must stay false until the actual image model is loaded.

## Verification gate

Do not call the model server ready until all checks pass:

1. From the API container, request `http://ollama.railway.internal:11434/api/tags`; it must return the configured model tag.
2. Confirm the API `/ready` endpoint returns HTTP 200 only after Ollama is reachable and the configured model is installed.
3. Send a harmless Arabic test prompt through the authenticated JASSIM API and verify the response is produced by the local Ollama route.
4. Inspect API logs and confirm the request reports the Ollama route, not a provider fallback.
5. Temporarily stop or disconnect Ollama and confirm chat fails closed with a clear local-model-unavailable message. No prompt may be sent to a public provider.
6. Restart/redeploy Ollama and confirm the model remains present because the volume persisted.
7. Record first-token latency, full response latency, memory use, and failures across at least 20 Arabic prompts before deciding whether the service can handle real users.

## Current limitations and safety

- This repository's API code hard-disables external chat and public-provider routing. Keep both environment flags false.
- Image generation is a separate inference workload from text chat. The Android/API product policy is **JASSIM-owned engines first; external providers are backup-only and disabled by default**. The intended image topology is a dedicated self-hosted image service (for example, a ComfyUI worker with an open-weights model) reachable only over the Railway private network, with persistent model storage and no public inference endpoint. Ollama handles text chat; it is not itself the image-generation engine.
- The current branch routes image requests only through the authenticated private image worker. Until its private URL/token are configured and the model is loaded, requests fail closed with HTTP 503. It must not silently call Hugging Face or another hosted image API. Do not add or use `JASSIM_HF_TOKEN` for the default path.
- Any future external image provider may be offered only as an explicitly user-enabled backup, with a clear disclosure before sending the prompt or uploaded reference image off our infrastructure. A local-engine outage must never trigger silent external fallback.
- The strict `/ready` check on the current development branch is not yet deployed to the production API.
- The existing production API currently uses a loopback Ollama URL; that does not prove a separate Ollama service exists or that inference works.
- Creating the service, attaching storage, increasing memory, enabling GPU, and redeploying production can incur cost or cause downtime. Obtain explicit owner approval before any of those actions.
- Do not place API tokens in the Android APK, public source files, or Ollama service variables unless the variable is actually required there.
