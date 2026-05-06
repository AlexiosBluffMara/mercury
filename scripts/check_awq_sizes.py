#!/usr/bin/env python3
"""Check sizes of candidate Gemma 4 31B AWQ repos."""
import os, requests

TOKEN = os.environ.get("HF_TOKEN", "")
candidates = [
    "cyankiwi/gemma-4-31B-it-AWQ-4bit",
    "QuantTrio/gemma-4-31B-it-AWQ",
    "infantryman77/gemma-4-31B-it-AWQ-8bit",
]
for repo in candidates:
    url = f"https://huggingface.co/api/models/{repo}/tree/main"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {TOKEN}"}, timeout=15)
        if r.status_code == 200:
            files = r.json()
            sf = [f for f in files if f["path"].endswith(".safetensors")]
            print(f"\n=== {repo} ===")
            total = 0
            for f in sf:
                size = f.get("size", 0) or 0
                total += size
                p = f["path"]
                print(f"  {size/1024/1024/1024:.2f} GB  {p}")
            print(f"  TOTAL: {total/1024/1024/1024:.2f} GB")
        else:
            print(f"{repo}: HTTP {r.status_code}")
    except Exception as e:
        print(f"{repo}: {e}")
