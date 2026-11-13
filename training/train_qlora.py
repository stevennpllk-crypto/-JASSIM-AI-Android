#!/usr/bin/env python3
"""Private QLoRA fine-tuning starter for JASSIM; requires an NVIDIA CUDA GPU."""
import argparse
import hashlib
import json
from pathlib import Path

from data_utils import encode_assistant_only

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)


def read_jsonl(path: Path):
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"line {line_no}: each row must be a JSON object")
        if not isinstance(item.get("instruction"), str) or not item["instruction"].strip():
            raise ValueError(f"line {line_no}: a non-empty instruction string is required")
        if not isinstance(item.get("output"), str) or not item["output"].strip():
            raise ValueError(f"line {line_no}: a non-empty output string is required")
        messages = []
        if item["instruction"].strip():
            messages.append({"role": "system", "content": item["instruction"].strip()})
        user_input = item.get("input", "")
        if not isinstance(user_input, str):
            raise ValueError(f"line {line_no}: input must be a string")
        messages.append({"role": "user", "content": user_input.strip() or "ابدأ."})
        messages.append({"role": "assistant", "content": item["output"].strip()})
        rows.append({"messages": messages})
    if not rows:
        raise ValueError("dataset is empty")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="training/data/seed.jsonl")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=float, default=1)
    parser.add_argument("--max-length", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accumulation", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU not detected. Training stopped; no CPU fallback is attempted.")
    if not torch.cuda.is_bf16_supported():
        compute_dtype = torch.float16
    else:
        compute_dtype = torch.bfloat16

    dataset_path = Path(args.dataset)
    rows = read_jsonl(dataset_path)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    ds = Dataset.from_list(rows)

    def tokenize_row(row):
        return encode_assistant_only(tokenizer, row["messages"], args.max_length)

    tokenized = ds.map(tokenize_row, remove_columns=ds.column_names)

    quant = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=compute_dtype,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, quantization_config=quant, device_map="auto",
        torch_dtype=compute_dtype, trust_remote_code=False
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    output_dir = Path(args.output_dir)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accumulation,
        learning_rate=args.learning_rate,
        logging_steps=1,
        save_strategy="epoch",
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        fp16=(compute_dtype == torch.float16),
        bf16=(compute_dtype == torch.bfloat16),
        report_to="none",
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer, model=model, padding=True, label_pad_token_id=-100
        ),
    )
    result = trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    manifest = {
        "base_model": args.base_model,
        "dataset": str(dataset_path),
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "rows": len(rows),
        "epochs": args.epochs,
        "max_length": args.max_length,
        "train_loss": result.metrics.get("train_loss"),
        "adapter_only": True,
        "note": "Smoke-test seed only; evaluate on a held-out benchmark before deployment.",
    }
    (output_dir / "jassim-training-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
