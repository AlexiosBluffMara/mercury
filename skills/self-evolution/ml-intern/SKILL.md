---
name: ml-intern
description: Use HuggingFace's ml-intern agent to autonomously run an LLM post-training experiment — literature review, dataset discovery, training script execution, iterative evaluation. Best fit when the user wants to fine-tune Cortex's Gemma 4 E4B on a new dataset, run an ablation study overnight, or sweep hyperparameters without writing the harness yourself.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  mercury:
    tags: [self-evolution, ml-intern, fine-tuning, post-training, huggingface, qwen, gemma, training]
    category: autonomous-ai-agents
    related_skills: [mercury-self-evolution, autoresearch, cortex-bridge]
prerequisites:
  external_repos:
    - https://github.com/huggingface/ml-intern
  env_vars: [HF_TOKEN, ANTHROPIC_API_KEY, GITHUB_TOKEN]
---

# ml-intern — Autonomous LLM Post-Training

[`huggingface/ml-intern`](https://github.com/huggingface/ml-intern) is
an open-source AI agent that "autonomously researches, writes, and
ships good quality ML related code" using the HuggingFace ecosystem.
In its launch demo it took `Qwen3-1.7B` from a 10% GPQA baseline to
32% in under 10 hours.

Architecture:

- Single agentic loop, max 300 iterations
- `ToolRouter` covering HF docs/papers/datasets/repos, GitHub code
  search, sandbox execution, MCP server tools
- `ContextManager` with auto-compaction at 170k tokens
- Doom-loop detector that injects corrective prompts on repeated
  patterns
- Provider-agnostic via `litellm`

## When to Use

- Fine-tune `cortex-gemma-4-e4b` on a new dataset (synthetic
  neuroscience QA, domain-specific narration corpora, etc.)
- Run an ablation: try N preprocessing variants, M LoRA configs, K
  data mixes, and report which combo wins
- Sweep hyperparameters on a small base model (Qwen-0.5B, SmolLM-1.7B)
  to validate a training recipe before scaling up
- The user has access to HF Hub paid compute and wants an overnight
  experiment without writing the orchestrator

**Do NOT use** for inference (use Mercury's brains directly), for
non-ML tasks, or when the user can answer the question with a quick
literature lookup — ml-intern is a heavy hammer.

## 1. Install

```bash
cd D:/
git clone https://github.com/huggingface/ml-intern.git
cd ml-intern
C:/Users/soumi/mercury/.venv/Scripts/python.exe -m pip install uv
uv sync
uv tool install -e .
```

Set env vars in `~/.mercury/.env` or shell:

```bash
HF_TOKEN=...                  # HuggingFace Hub access (datasets, models)
ANTHROPIC_API_KEY=...         # default agent provider; can swap via --model
GITHUB_TOKEN=...              # for GitHub code search
OPENAI_API_KEY=...            # optional alt provider
```

## 2. Pick the target

For Cortex fine-tunes:

```text
"Fine-tune RedTeamKitchen/cortex-gemma-4-e4b on the synthetic
neuroscience QA dataset at HF://RedTeamKitchen/neuro-qa-50k.
Target: improve tier-5 (clinician) narration quality on
heldout-ROIs.  Use LoRA r=16 alpha=32 dropout=0.05.  Single H100
or A100-80GB.  Report best checkpoint by validation loss."
```

For ablations:

```text
"Compare three LoRA ranks (8, 16, 32) on Qwen3-1.7B fine-tuned for
brain-region named-entity recognition.  Use the Schaefer-400
parcellation as label space.  Report exact-match F1 on the
heldout 10% split."
```

## 3. Run

Interactive (recommended for the first run, watch what it picks):

```bash
ml-intern
```

Headless (fire-and-forget overnight):

```bash
ml-intern --max-iterations 300 \
  --model anthropic/claude-sonnet-4-6 \
  "Fine-tune ..." > logs/run-$(date +%Y%m%d-%H%M).log 2>&1 &
```

The default model is Anthropic Claude.  Mercury's 0x Copilot models
work too but iteration depth on a 300-step run can be limiting; for
serious training runs Sonnet 4.6 (1x premium) is the practical floor.

## 4. Outputs

ml-intern uploads the final session to HF Hub by default — you'll get
a session URL with the full trace, the trained model artifacts, and an
auto-generated model card.  Check `~/.mercury/.env` for `HF_TOKEN`
scope (write to your namespace).

For Cortex fine-tunes, the HF model goes under
`RedTeamKitchen/cortex-gemma-4-e4b-{run_tag}`.  Mercury's skill
catalogue picks it up automatically once it lands on the Hub.

## 5. Pull into Cortex

When the run produces a winning checkpoint:

```bash
# Manual swap path (verify before committing)
cd D:/cortex
huggingface-cli download RedTeamKitchen/cortex-gemma-4-e4b-{run_tag} \
  --local-dir ./models/cortex-gemma-4-e4b-{run_tag}

# Update the Ollama Modelfile to point at the new weights
ollama create cortex-gemma-4-e4b -f configs/cortex-gemma-4-e4b.Modelfile

# Restart Mercury so the model_manager picks up the new tag
```

Cortex's `cortex/config.py` already reads the active model tag from
`~/.mercury/.env` (`GEMMA_FAST_MODEL`).  Update that one line and
restart.

## Pitfalls

1. **300 iterations isn't unlimited.**  ml-intern sometimes converges
   late.  If the trace shows the agent hit the cap mid-experiment,
   increase `--max-iterations` (some users go 600-1000) but watch the
   API bill.
2. **HF rate limits bite.**  Aggressive HF Hub queries (every paper +
   every dataset card + every model card) can trip rate limits during
   iteration spikes.  ml-intern has built-in backoff but expect
   stalls.
3. **GPU sharing.**  If ml-intern's training step lands on the same
   5090 that's running TRIBE/Gemma, you'll see VRAM contention.
   Either kill Mercury's Gemma worker before launching, run
   ml-intern's training step on Modal/HF's compute, or use
   smaller-base-model experiments that fit alongside.
4. **Don't merge a winner without spot-checks.**  ml-intern optimizes
   training metrics; some "wins" overfit to the eval set.  Sample
   10-20 outputs from the winning checkpoint and compare to the
   baseline by hand before swapping production weights.
