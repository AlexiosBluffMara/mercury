---
name: autoresearch
description: Run Andrej Karpathy's autoresearch loop on the 5090 to discover small training-recipe improvements overnight. Best fit when the user has a small-model training script (nanochat-style, ~600 LOC) and wants to harvest 10-30 micro-optimisations with no manual experimentation. Pairs cleanly with mercury-self-evolution and ml-intern.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [self-evolution, autoresearch, karpathy, nanochat, microGPT, training, RTX5090]
    category: autonomous-ai-agents
    related_skills: [mercury-self-evolution, ml-intern, cortex-bridge]
prerequisites:
  external_repos:
    - https://github.com/karpathy/autoresearch
  hardware: RTX 5090 (or any modern CUDA GPU); cu128 torch wheels for Blackwell
---

# autoresearch — Karpathy's Overnight Self-Improvement Loop

[`karpathy/autoresearch`](https://github.com/karpathy/autoresearch)
(MIT, March 2026) is a minimal, fork-friendly pattern for running an
agent against your own training script.  In the launch demo it ran
700 experiments over 2 days on a single GPU and found 20
optimisations that yielded an 11% training speedup on a larger
follow-on model.

Three files, no library:

| File | Owner | Purpose |
|---|---|---|
| `program.md` | you | The agent's instruction prompt |
| `prepare.py` | you | Read-only constants and utilities |
| `train.py` | the agent | The model + optimizer + training loop the agent edits |

The eval metric is `val_bpb` (validation bits-per-byte) which is
vocab-size-independent — the agent can change architecture freely
and still get fairly compared scores.  Each experiment runs for
exactly 5 minutes; ~12 experiments per hour.

## When to Use

- The user has a small-LM training recipe and wants overnight
  micro-optimisation sweeps without writing the orchestration
- A new architecture idea the user wants prototyped against a
  baseline (e.g., "does muP scaling help here?", "what about
  rotary-vs-NoPE for sequences <=4k?")
- Training-recipe research that's purely local on the 5090 with no
  cloud spend
- Generating a corpus of "what works on small models" findings to
  cite when scaling up via ml-intern

**Do NOT use** for inference, full-pipeline ML projects, or anything
where 5 minutes of training isn't a meaningful eval signal.

## 1. Clone + setup

```bash
cd D:/
git clone https://github.com/karpathy/autoresearch.git
cd autoresearch
C:/Users/soumi/mercury/.venv/Scripts/python.exe -m pip install -e .
```

Verify cu128 torch is in the Mercury venv (Blackwell sm_120 needs it):

```bash
C:/Users/soumi/mercury/.venv/Scripts/python.exe -c \
  "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# expect: 2.11.0+cu128 True NVIDIA GeForce RTX 5090
```

If `cuda.is_available()` is False, reinstall torch from the cu128
index (see Mercury's `CLAUDE.md` "Setting up a fresh venv" section).

## 2. Author your `program.md`

This is the only thing you really write.  It tells the agent what to
optimise for and what's off-limits.  Karpathy's template is short
(~50 lines).  For Mercury / Cortex use, add:

```markdown
You are running on an RTX 5090 (Blackwell sm_120, 32 GB GDDR7).

Constraints:
- Do NOT exceed 10 GB VRAM at peak (Cortex's GPU scheduler may need
  the rest).
- Do NOT modify prepare.py — it has hard-locked constants used by
  the eval harness.
- Each experiment must complete in 5 minutes wall-clock.
- val_bpb is the only metric.  Lower is better.

Suggested directions:
- Optimizer choice (AdamW, Lion, Sophia)
- LR schedule (cosine, WSD, sqrt)
- Architecture: rotary-vs-NoPE, GQA group sizes, head dim
- Data ordering / curriculum
- Mixed precision dtype (bf16 vs fp16 vs fp8 if supported)

Avoid:
- Gradient accumulation that exceeds the 5-min budget
- Distributed strategies (this is single-GPU)
- Loading pretrained weights — train from scratch every run
```

## 3. Boot the agent

```bash
cd D:/autoresearch
ANTHROPIC_API_KEY=... python autoresearch.py \
  --max-experiments 200 \
  --output-dir runs/$(date +%Y%m%d)
```

Or with Mercury's 0x Copilot:

```bash
OPENAI_API_KEY=... python autoresearch.py \
  --provider openai \
  --model gpt-5-mini \
  --max-experiments 200 \
  --output-dir runs/$(date +%Y%m%d)
```

(Karpathy's reference uses Anthropic Claude; the harness is
provider-agnostic via litellm.)

The loop:
1. Agent reads `program.md` + current `train.py`
2. Agent proposes a modification, edits `train.py`
3. Harness runs `python train.py` for 5 min, captures `val_bpb`
4. If improved, the change is kept; if not, reverted
5. Repeat

Wall-clock budget: 200 experiments × 5 min ≈ 17 hours of GPU time.
Run it Friday evening, harvest Sunday morning.

## 4. Reading the results

Output:

```
runs/20260425/
├── leaderboard.csv          # one row per experiment, sorted by val_bpb
├── trajectory/
│   ├── exp_001_train.py     # snapshot of train.py after exp 1
│   ├── exp_002_train.py
│   └── ...
├── traces/
│   └── exp_NNN.log          # agent reasoning + training output
└── winner_train.py          # best version found
```

Diff `winner_train.py` against the original `train.py` to see what
changed.  Karpathy reports that the wins generalize: optimisations
the agent finds on a 5-minute training run usually transfer to
larger / longer runs on the same architecture family.

## 5. Apply to Cortex

For Cortex's Gemma 4 E4B fine-tune (Unsloth track), most of the
training-recipe wins from autoresearch transfer with minimal
adjustment.  Specifically:

- Optimizer hyperparameters (LR, beta1/beta2, weight decay) — direct
  transfer.
- LR schedule shape — direct transfer; just rescale to the longer
  fine-tune horizon.
- Mixed-precision dtype — direct transfer.
- Architecture changes — usually NOT transferable (we don't pretrain
  Gemma 4 from scratch); skip these.

When you find wins, write them up in
`D:/cortex/SPRINT_PLAN.md` under the active sprint, then port the
relevant lines into Cortex's Unsloth fine-tune script.

## Pitfalls

1. **`val_bpb` is a proxy.**  Vocab-size-independent compares
   architectures fairly but ignores anything `val_bpb` doesn't
   capture (retrieval quality, calibration, refusal behavior).
   Don't promote a winner straight to a production fine-tune
   without spot-checking generations.
2. **The agent can break the harness.**  If `train.py` raises an
   exception or hangs, autoresearch's wrapper kills it and reverts.
   But sometimes a "successful" run leaks memory or has subtly
   wrong loss — read the traces/exp_NNN.log for anything unusual
   in the top-5 winners.
3. **5-minute budget exposes you to noise.**  Two runs of the same
   `train.py` can differ in `val_bpb` by 0.005-0.02 just from data
   ordering / dropout RNG.  Validate top winners by re-running them
   3-5x before declaring a real win.
4. **VRAM contention.**  If Cortex's TRIBE pipeline launches while
   autoresearch is mid-experiment, both die.  Either pause
   Mercury's gateway during the autoresearch session or schedule
   them on alternate days.
