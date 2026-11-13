"""Private JASSIM image-generation worker.

Prompts are processed in this process with local model weights. No hosted
inference API or external provider fallback is implemented here.
"""
import base64
import hmac
import io
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from PIL import Image

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("jassim-image-worker")

MODEL_ID = os.getenv("JASSIM_IMAGE_MODEL_ID", "stabilityai/sdxl-turbo")
MODEL_CACHE = os.getenv("HF_HOME", "/models/huggingface")
WORKER_TOKEN = os.getenv("JASSIM_IMAGE_WORKER_TOKEN", "")
PIPELINE = None
MODEL_ERROR = None
INFERENCE_LOCK = threading.Lock()


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    width: int = Field(default=1024, ge=256, le=1024, multiple_of=8)
    height: int = Field(default=1024, ge=256, le=1024, multiple_of=8)


def _authorized(authorization: str | None) -> bool:
    if not WORKER_TOKEN or not authorization:
        return False
    scheme, _, supplied = authorization.partition(" ")
    return (
        scheme.lower() == "bearer"
        and bool(supplied)
        and hmac.compare_digest(supplied, WORKER_TOKEN)
    )


def _load_pipeline():
    """Load the open-weights model into GPU memory; fail closed without CUDA."""
    import torch
    from diffusers import AutoPipelineForText2Image

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_gpu_required")
    pipeline = AutoPipelineForText2Image.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        variant="fp16",
        cache_dir=MODEL_CACHE,
    )
    pipeline.to("cuda")
    if hasattr(pipeline, "enable_attention_slicing"):
        pipeline.enable_attention_slicing()
    return pipeline


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global PIPELINE, MODEL_ERROR
    if not WORKER_TOKEN:
        MODEL_ERROR = "worker_token_not_configured"
        logger.error(MODEL_ERROR)
    else:
        try:
            PIPELINE = _load_pipeline()
            MODEL_ERROR = None
            logger.info("Private image model loaded: %s", MODEL_ID)
        except Exception as exc:
            PIPELINE = None
            MODEL_ERROR = type(exc).__name__ + ":" + str(exc)[:240]
            logger.exception("Private image model failed to load")
    yield


app = FastAPI(title="JASSIM Private Image Worker", version="1.0.0", lifespan=lifespan)


def _require_auth(authorization: str | None):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health():
    return {"ok": True, "service": "jassim-private-image-worker"}


@app.get("/ready")
def ready(authorization: str | None = Header(default=None)):
    _require_auth(authorization)
    loaded = PIPELINE is not None
    return {
        "ready": loaded,
        "model_ready": loaded,
        "model": MODEL_ID if loaded else "private_worker_model_not_ready",
    }


@app.post("/v1/images/generate")
def generate_image(
    request: GenerateRequest,
    authorization: str | None = Header(default=None),
):
    _require_auth(authorization)
    if PIPELINE is None:
        raise HTTPException(status_code=503, detail="private_image_model_not_ready")
    try:
        with INFERENCE_LOCK:
            result = PIPELINE(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=4,
                guidance_scale=0.0,
            )
            image = result.images[0]
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return {
            "image_base64": encoded,
            "mime_type": "image/png",
            "model": MODEL_ID,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Private image inference failed")
        raise HTTPException(status_code=500, detail="private_image_inference_failed") from exc
