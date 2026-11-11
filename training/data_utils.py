"""Dependency-light helpers for preparing assistant-only fine-tuning examples."""


def encode_assistant_only(tokenizer, messages, max_length):
    """Encode a chat example while masking system/user tokens from the loss.

    The prompt/full common prefix is used instead of assuming that separately
    tokenized strings have identical token boundaries at their join.
    """
    if len(messages) < 2 or messages[-1].get("role") != "assistant":
        raise ValueError("the final message must be an assistant response")
    prompt_text = tokenizer.apply_chat_template(
        messages[:-1], tokenize=False, add_generation_prompt=True
    )
    full_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=False
    )
    prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
    input_ids = tokenizer.encode(full_text, add_special_tokens=False)
    prefix_len = 0
    for prompt_token, full_token in zip(prompt_ids, input_ids):
        if prompt_token != full_token:
            break
        prefix_len += 1
    input_ids = input_ids[:max_length]
    prefix_len = min(prefix_len, len(input_ids))
    if prefix_len >= len(input_ids):
        raise ValueError("example has no assistant target tokens after truncation")
    labels = ([-100] * prefix_len) + input_ids[prefix_len:]
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
    }
