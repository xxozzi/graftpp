"""Shared Modal resources for Hawthorne GPU jobs."""

import modal

MODEL_ID = "Qwen/Qwen3-14B"

torch_image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(
        "torch==2.8.0",
        "transformers==4.57.1",
        "accelerate==1.10.1",
        "safetensors",
        "numpy",
        "huggingface_hub[hf_transfer]",
        "sentencepiece",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_XET_HIGH_PERFORMANCE": "1",
          "TOKENIZERS_PARALLELISM": "false"})
    .add_local_python_source("common")
)

hf_cache_vol = modal.Volume.from_name("huggingface-cache", create_if_missing=True)
models_vol = modal.Volume.from_name("hawthorne-models", create_if_missing=True)
data_vol = modal.Volume.from_name("hawthorne-data", create_if_missing=True)

VOLUMES = {
    "/root/.cache/huggingface": hf_cache_vol,
    "/models": models_vol,
    "/data": data_vol,
}


def build_chat_text(tokenizer, system: str, user: str, reasoning: str, content: str,
                    thinking: bool = True) -> tuple[str, str, str]:
    """Return (prompt_text, think_text, answer_text) such that the model-visible
    sequence is prompt_text + think_text + answer_text, matching Qwen3's template."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=thinking)
    if thinking:
        think_text = f"<think>\n{(reasoning or '').strip()}\n</think>\n\n"
    else:
        think_text = ""
    answer_text = f"{(content or '').strip()}<|im_end|>\n"
    return prompt_text, think_text, answer_text
