# JASSIM AI — Open-model and GPU options
Date: 2026-11-12
Purpose: choose candidates for a controlled private benchmark. No model or GPU has been purchased or deployed by this report.

## Model candidates

| Candidate | Practical role | Approximate artifact / size | Strengths relevant to JASSIM | Constraints |
|---|---|---:|---|---|
| Qwen3.5 4B (Ollama Q4) | Baseline / low-cost fallback for tests | ~3.4 GB | Current Ollama library offers a ready tag; vision support; Apache 2.0 model card | Smaller capacity; benchmark Arabic/Tunisian quality before production |
| Qwen3.5 9B (Ollama Q4_K_M) | **Primary candidate** | ~6.6–7.6 GB | Current Ollama tag; official Qwen card reports 201 languages/dialects; Apache 2.0; multimodal architecture | Needs more VRAM than 4B; verify exact inference speed and prompt adherence on our GPU |
| Gemma 3 12B IT | Alternative multilingual / vision model | Quantized size depends on format | Google reports 140+ languages, up to 128K context and image input | Gemma terms are not Apache 2.0; review usage terms; confirm Ollama tag/runtime compatibility |
| Mistral Small 3.2 24B Instruct | Larger quality/function-calling challenger | 24B parameters; full repository artifacts are much larger than quantized runtime | Apache 2.0; model card lists Arabic among 24 languages; improved instruction following and function calling | Heavier GPU/RAM requirement; test quantized serving before selecting |
| Llama 3.3 70B Instruct | High-capacity reference, not first deployment | 70B parameters | Strong published reasoning/coding results | Official supported-language list does not include Arabic; custom Llama Community License; high VRAM and cost |

## Reproducible local benchmark harness

The repository now includes `backend/local_model_benchmark.py`. It:
- tests only synthetic prompts from the frozen 14-case evaluation set;
- connects only to loopback or a `*.railway.internal` Ollama endpoint;
- refuses public Ollama URLs before making a request;
- tests only exact model tags already present in `/api/tags`;
- never runs `ollama pull` or downloads missing model weights;
- reports pass rate, median/p95 latency and generated tokens/second to a local JSON file.

Example on the Ollama host after the operator has installed the desired tags:
```sh
cd backend
python local_model_benchmark.py --models qwen3.5:4b,qwen3.5:9b --output comparison.json
```

The benchmark should be run separately for each model set and repeated at the same context and concurrency settings. Keep the JSON reports with the GPU type, quantization and Ollama version.

## Recommended benchmark order

1. Qwen3.5 4B as a low-cost baseline.
2. Qwen3.5 9B as the leading production candidate.
3. Gemma 3 12B and Mistral Small 3.2 24B as challengers after checking exact runtime and license.
4. Llama 3.3 70B only as a reference if a suitable large-memory GPU is available.

Do not select based on vendor-reported aggregate scores alone. The project benchmark should include at least:
- Modern Standard Arabic and Tunisian Arabic (Mahdia dialect) understanding.
- Exact instruction following, concise answers and refusal honesty.
- Arithmetic, multi-step reasoning and factual uncertainty.
- Python/Kotlin/Android coding tasks.
- Long conversation recall and memory isolation between accounts.
- JSON/tool-call correctness.
- First-token latency, tokens/second, peak VRAM/RAM, failure rate and cost per 1,000 generated tokens.

The current repository evaluation set is small and synthetic; it is not enough to claim a model beats Gemini or ChatGPT. Expand and freeze a held-out test set before tuning.

## GPU pricing snapshot (USD; provider pages checked 2026-11-12)

Indicative Runpod Secure Cloud hourly rates:
| GPU | VRAM | Hourly | 2-hour smoke test | 730 hours/month |
|---|---:|---:|---:|---:|
| RTX 4090 | 24 GB | $0.89 | $1.78 | ~$649.70 |
| L40S | 48 GB | $1.09 | $2.18 | ~$795.70 |
| A100 PCIe | 80 GB | $1.79 | $3.58 | ~$1,306.70 |

Runpod Community Cloud advertises lower starting rates (for example, RTX 4090 from $0.34/hour and A100 PCIe from $1.19/hour), but availability and host trust vary. For private user conversations, prefer a dedicated/secure option over the cheapest marketplace host.

Lambda's published options include A6000 48 GB from about $1.09/GPU-hour, A10 24 GB about $1.29/hour, and A100 40 GB about $1.99/hour in its current listed instance tiers. Check the actual checkout quote and regional availability before launch.

## Cost interpretation

- A short 2-hour controlled test on a Secure RTX 4090 is about $1.78 before storage, tax and any additional services.
- A continuously running Secure RTX 4090 is roughly $650/month at 730 hours, before storage, tax, backups and networking.
- L40S 48 GB is a more comfortable single-GPU option for 9B/24B quantized experiments and larger context, but costs about $796/month if left running.
- A100 80 GB is not the sensible starting point for a 9B model; reserve it for measured need, high concurrency or larger models.
- Image generation is a separate workload and would require a separate cost estimate. Do not provision it alongside the chat model initially.

## Recommendation

Start with a **time-boxed 2-hour Secure RTX 4090 test**, using Qwen3.5 4B and 9B quantizations sequentially, persistent model cache only if its storage price is approved, and no public API endpoint for Ollama. Run the benchmark locally against the private worker. Shut the GPU down after the test. If 9B is too slow or memory-constrained, evaluate L40S next.

This is a proposal only. No GPU, storage volume, paid plan, model download or deployment is authorized by this document.
