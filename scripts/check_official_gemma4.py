#!/usr/bin/env python3
"""Find vLLM-compatible Gemma 4 quants from Google or Unsloth only.

vLLM-compatible quant formats: bnb-4bit (bitsandbytes), GPTQ, AWQ, FP8, BF16.
NOT compatible: GGUF, MLX, OpenVINO.
"""
import os, requests, sys

TOKEN = os.environ.get("HF_TOKEN", "")
candidates = [
    # 31B candidates
    "unsloth/gemma-4-31B-it-bnb-4bit",
    "unsloth/gemma-4-31b-it-bnb-4bit",
    "unsloth/gemma-4-31B-it-AWQ",
    "unsloth/gemma-4-31b-it-GPTQ",
    "google/gemma-4-31B-it",
    # 26B-A4B candidates
    "unsloth/gemma-4-26B-A4B-it-bnb-4bit",
    "unsloth/gemma-4-26b-a4b-it-bnb-4bit",
    "google/gemma-4-26B-A4B-it",
    # E4B candidates (smaller, easier to test MTP first)
    "unsloth/gemma-4-E4B-it-bnb-4bit",
    "google/gemma-4-E4B-it",
    # Drafters (official Google)
    "google/gemma-4-31B-it-assistant",
    "google/gemma-4-26B-A4B-it-assistant",
    "google/gemma-4-E4B-it-assistant",
]
for repo in candidates:
    url = f"https://huggingface.co/api/models/{repo}/tree/main"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
        if r.status_code == 200:
            files = r.json()
            safetensors = [f for f in files if f["path"].endswith(".safetensors")]
            total = sum((f.get("size", 0) or 0) for f in safetensors)
            extras = []
            if any(f["path"].endswith((".gguf", ".bin")) for f in files):
                extras.append("[has GGUF/bin]")
            print(f"OK  {repo:55s} {total/1024/1024/1024:>5.1f} GB  {' '.join(extras)}")
        elif r.status_code == 401:
            print(f"GATED  {repo:55s} (license click required)")
        elif r.status_code == 404:
            print(f"404  {repo}")
        else:
            print(f"HTTP{r.status_code}  {repo}")
    except Exception as e:
        print(f"ERR  {repo}: {e}")
