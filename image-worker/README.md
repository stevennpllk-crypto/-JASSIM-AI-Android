# JASSIM Private Image Worker

This service runs the image model inside JASSIM-controlled compute. It does not
call hosted image-generation APIs and has no external-provider fallback.

## Deployment shape

- Railway service root directory: `image-worker`
- Builder: Dockerfile
- Private listening port: `8188`
- Private hostname example: `image-worker.railway.internal`
- Persistent volume mount: `/models`
- GPU: NVIDIA CUDA GPU required
- Model cache: `/models/huggingface`

## Required variables

- `JASSIM_IMAGE_WORKER_TOKEN`: long random secret shared only with the API service
- `JASSIM_IMAGE_MODEL_ID`: optional; defaults to `stabilityai/sdxl-turbo`
- `HF_HOME=/models/huggingface`

The first boot downloads open model weights into the persistent volume. Subsequent
boots reuse the cache. Prompts and generated images are processed by this worker;
model-weight download is the only expected model-hub network activity.

## API

- `GET /health`: process liveness only; no inference readiness claim.
- `GET /ready`: authenticated; reports ready only after CUDA is available and the model is loaded.
- `POST /v1/images/generate`: authenticated JSON body with `prompt`, `width`, and `height`; returns base64 PNG, MIME type, and model ID.

Do not add a public Railway domain or TCP proxy. Configure the JASSIM API with
`JASSIM_IMAGE_WORKER_URL=http://image-worker.railway.internal:8188` and the same
`JASSIM_IMAGE_WORKER_TOKEN`.

## Model and hardware notes

The default SDXL Turbo checkpoint is an open-weights starting point, not a
claim that the model was trained by JASSIM. Review its current license and
usage terms before public/commercial release. Benchmark VRAM, latency, output
quality, Arabic prompt behavior, and concurrency on the exact GPU before
selecting production capacity. The service intentionally stays not-ready if
CUDA/model loading fails.

No cloud service, GPU, storage volume, or production deployment is created by
these repository files. Provisioning requires separate explicit approval.
