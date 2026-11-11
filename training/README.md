# JASSIM private model training

This directory is a reproducible starting point for **training on infrastructure we control**.
It does not claim that a model has already been trained. The current Railway API is a small
Python service; it is not a GPU training host and does not contain model weights.

## Target

- Base model: Qwen2.5-1.5B-Instruct (open weights; review its licence before distribution).
- Method: QLoRA supervised fine-tuning; base weights remain frozen and the adapter is saved separately.
- Runtime: a self-managed NVIDIA Linux host with persistent storage.
- Inference: Ollama on the same private host/network. Do not enable public-provider fallback.

## Requirements

Use a clean Python 3.11/3.12 virtual environment on a Linux NVIDIA machine with a compatible
CUDA driver. Install the pinned major/minor ranges below. GPU memory needs depend on sequence
length, batch size, and driver; start with a 12 GB+ GPU and reduce batch size if needed.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r training/requirements.txt
```

## Data format

One JSON object per line with `instruction`, optional `input`, and `output`.
The included `data/seed.jsonl` is only a tiny smoke-test seed (not a month of training
data and not enough to establish model quality). Replace/expand it with reviewed,
licensed, privacy-safe examples. Never put real user conversations in training data
without explicit informed consent and a deletion/retention policy.

## Run

```bash
python training/train_qlora.py \
  --dataset training/data/seed.jsonl \
  --base-model Qwen/Qwen2.5-1.5B-Instruct \
  --output-dir /srv/jassim/models/qwen25-1p5b-arabic-lora \
  --epochs 1
```

The script refuses to run without CUDA. It saves a PEFT adapter and tokenizer; it does
not modify or overwrite the base model. Keep the adapter, base-model revision, dataset
hash, training arguments, and evaluation results together for reproducibility.

## Evaluation gate

Before deployment, compare base vs adapter on a held-out set that is not present in training.
Measure Arabic/Tunisian instruction following, factuality, math, coding, refusal/safety,
latency, and regression rate. Do not promote an adapter just because training loss falls.
The included seed data is for pipeline smoke tests only; it cannot support a public quality claim.
