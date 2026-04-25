---
name: hermes-self-evolution
description: Run NousResearch's offline DSPy + GEPA pipeline to mutate and improve Mercury's own SKILL.md files based on execution traces. Use when a skill keeps misfiring, when the user has a corpus of session traces and wants the skills tuned to them, or when planning a periodic skill-quality pass.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [self-evolution, DSPy, GEPA, skills, optimization, hermes-agent-self-evolution]
    category: autonomous-ai-agents
    related_skills: [ml-intern, autoresearch, three-js-component, cortex-bridge]
prerequisites:
  external_repos:
    - https://github.com/NousResearch/hermes-agent-self-evolution
  python_packages: [dspy, openai]
---

# Hermes Self-Evolution — Offline Skill Optimization

`NousResearch/hermes-agent-self-evolution` is an **offline** DSPy + GEPA
pipeline that reads execution traces from Claude Code, Copilot, or
Mercury sessions, proposes textual mutations to `SKILL.md` files, runs
each variant through constraint gates (tests, size caps, benchmarks),
and emits PR-ready improvements.  Typical run is `$2-10` per
optimization cycle on commercial APIs.

Phase 1 (skill optimization) is implemented in upstream.  Phase 2
(prompts) and Phase 3 (implementation code) are planned.  Mercury's
skill catalogue under `~/.mercury/skills/` is the canonical input.

## When to Use

- A specific skill keeps misfiring — the user reports the agent picks
  the wrong tool sequence, misreads the output schema, or skips a
  pitfall.
- The user has accumulated a few hundred session traces and wants the
  skills tuned to their actual workflow.
- Periodic maintenance: every few weeks, run a sweep over the top-N
  most-used skills and PR any wins.

**Do NOT use** for one-off skill tweaks the user can do by hand in
30 seconds, or to optimize skills the agent is barely using (cost
is wasted).

## 1. Clone + setup

```bash
cd D:/
git clone https://github.com/NousResearch/hermes-agent-self-evolution.git
cd hermes-agent-self-evolution
C:/Users/soumi/mercury/.venv/Scripts/python.exe -m pip install -e .
```

It uses the same Mercury venv — DSPy + the inference provider you've
configured (Copilot, Anthropic, OpenAI; route via litellm).

## 2. Pick a target skill

```bash
cp ~/.mercury/skills/3d/three-js-component/SKILL.md \
   target_skills/three-js-component.md
```

Or batch:

```bash
cp -r ~/.mercury/skills/3d target_skills/
```

## 3. Provide trace data

Two sources:

- **Synthetic eval set** — write 20-50 prompts that should trigger the
  skill, with the expected outcome.  Lower variance, narrower coverage.
- **Real session history** — point the optimizer at
  `~/.mercury/state.db` and let it sample turns where the skill was
  invoked.  Higher variance, broader coverage, no extra writing.

Mercury's SessionDB schema is FTS5; the optimizer needs read-only SQLite
access.

## 4. Run the optimization

```bash
python -m hermes_self_evolution optimize \
  --skill target_skills/three-js-component.md \
  --traces ~/.mercury/state.db \
  --budget-usd 5.0 \
  --output-dir runs/three-js-$(date +%Y%m%d) \
  --provider copilot \
  --judge-model gpt-5-mini
```

Settings to tune:
- `--budget-usd` — hard stop.  $2-10 is the typical effective range.
- `--judge-model` — the LLM that scores variants; needs reasonable
  reasoning (GPT-5 mini at 0x is fine for most skills; escalate to
  Sonnet 4.6 for nuanced narration / safety skills).
- `--population` — DSPy program population per generation (default 8).
- `--generations` — how many GEPA cycles (default 5).

Wall-clock for $5 budget: ~30-60 minutes.  Run it overnight; Mercury
can keep working in parallel — the optimizer isn't on the GPU.

## 5. Review the proposed mutations

Output structure:

```
runs/three-js-20260425/
├── original.md           # input SKILL.md
├── variants/
│   ├── v01.md           # first survivor
│   ├── v02.md
│   └── ...
├── eval/
│   ├── scores.json      # per-variant judge scores
│   └── traces.jsonl     # full eval traces for spot-checking
└── winner.md            # best variant by aggregate score
```

Read `winner.md` and the top-3 variants.  GEPA tends to make skills
**more specific** (better) but sometimes **longer** (mixed — Mercury's
progressive disclosure caches at L0/L1/L2, so longer SKILL.md eats
more tokens at L1).  If the winner's word count is >2x the original,
manually trim before merging.

## 6. Merge back into Mercury

```bash
cp runs/three-js-20260425/winner.md \
   ~/.mercury/skills/3d/three-js-component/SKILL.md
```

Mercury's skill sync (`mercury skills sync`) treats user-modified files
as "local wins" so this overwrite sticks across upstream pulls.

Commit to your Mercury fork if you want it durable:

```bash
cp runs/three-js-20260425/winner.md \
   D:/mercury/skills/3d/three-js-component/SKILL.md
cd D:/mercury
git add skills/3d/three-js-component/SKILL.md
git commit -m "skills(3d): incorporate self-evolution winner from $(date +%Y-%m-%d) run"
```

## Pitfalls

1. **Don't trust the judge blindly.**  GEPA optimizes the judge's
   scoring function, which approximates real success.  Always
   eyeball-review the winner before merging — there are pathological
   cases where the judge rewards verbose-but-wrong outputs.
2. **Frozen-snapshot caching.**  Mercury's MEMORY.md / USER.md and the
   skill registry get loaded as a frozen snapshot at session start to
   keep the prefix cache hot.  After overwriting a SKILL.md, restart
   any long-running Mercury sessions or the old version stays in cache.
3. **Cost overruns happen.**  `--budget-usd 5` is a *target*, not a
   hard cap on every provider.  Some providers bill per-token per-call
   and the optimizer can tip $1-2 above target on long traces.  Watch
   the running spend in the optimizer's progress output.
4. **Don't optimize Cortex skills against synthetic data.**  TRIBE v2
   inference is expensive and not reproducible with mocks; use real
   session traces from `~/.mercury/state.db` only.  Better yet, leave
   Cortex skills alone — they're domain-specific and the judge LLM
   doesn't have the neuroscience grounding to score them well.
