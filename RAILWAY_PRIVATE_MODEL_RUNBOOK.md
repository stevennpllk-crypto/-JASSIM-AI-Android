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
- The strict `/ready` check on the current development branch is not yet deployed to the production API.
- The existing production API currently uses a loopback Ollama URL; that does not prove a separate Ollama service exists or that inference works.
- Creating the service, attaching storage, increasing memory, enabling GPU, and redeploying production can incur cost or cause downtime. Obtain explicit owner approval before any of those actions.
- Do not place API tokens in the Android APK, public source files, or Ollama service variables unless the variable is actually required there.
