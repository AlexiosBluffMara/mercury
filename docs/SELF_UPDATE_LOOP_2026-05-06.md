# Mercury Self-Update Loop — daily OpenRouter allocation

**Updated:** 2026-05-06
**Goal:** spend the full 1000 :free reqs/day OpenRouter allocation on Mercury improvements without ever touching the $20 paid credit pool.

## Allocation rules

- Account has $20 in OpenRouter credits → unlocks **1000 :free model reqs/day** permanently (per OpenRouter rate-limit policy: $10+ purchased, ever, keeps the higher cap even if balance drops below).
- Balance does NOT decrease when calling `:free` models. Balance only drops on paid model calls.
- Mercury's quota tracker (`scripts/openrouter_daily.py`) maintains `~/.mercury/openrouter_daily_quota.json`:
  - `free_used` — counter resets daily UTC, archives the prior day to `~/.mercury/openrouter_archive/YYYY-MM-DD.json`
  - `paid_usd` — should always be 0 unless we explicitly opt in
  - `tasks` — which job consumed how many reqs today

## Hard guards

The Mercury config (`~/.mercury/config.yaml`) splits OpenRouter into two providers:
- `openrouter-free` — `allow_only_free_models: true`, `daily_request_cap: 1000`
- `openrouter-paid` — `disabled_unless: cost_floor_paid`, `daily_credit_cap_usd: 0.50`, `monthly_credit_cap_usd: 5.00`

Mercury's router refuses any model that doesn't end in `:free` when only `openrouter-free` is reachable. To intentionally spend a paid credit, the operator must run `mercury -m <model> --allow-paid` (no environment flag — must be per-invocation, no auto-escalation).

## Daily playbook — what 1000 reqs/day buys us

Roughly partitioned, this is the kind of work Mercury self-runs each night via cron:

| Job | Rate | Why |
|-----|------|-----|
| **Log digest** — summarise yesterday's 24h of `~/.mercury/logs/*` and emit a one-page memo to the Obsidian vault | ~50 reqs | Daily situational awareness, accumulates into a queryable history |
| **Session insights** — re-read every multi-turn session from yesterday and tag intent + outcome | ~150 reqs | Future search ranking, training-set candidate flagging |
| **Skill audit** — every skill in `~/.mercury/skills/*` rerun on a synthetic test prompt; flag regressions | ~100 reqs | Catches skill drift after model swaps (e.g. when we swapped 26B from mlx-community to Unsloth UD) |
| **Memory consolidation** — re-summarise the auto-memory vault to surface stale entries | ~30 reqs | Memory hygiene |
| **Eval harness** — run a fixed 200-prompt benchmark against the local stack and `:free` cloud, log latency + agreement rate | ~200 reqs | Continuous quality regression check |
| **Cron task generation** — propose new automation candidates from the day's log patterns | ~20 reqs | Surface high-value automation |
| **Documentation refresh** — re-read code changes from `git log --since=yesterday` and propose doc updates | ~50 reqs | Keep `D:\mercury\docs\` and `~/.mercury/vault/` in sync with code reality |
| **Model comparator** — for each :free model on OpenRouter (Gemma 4, Llama, DeepSeek), run the same 50-prompt check and rank | ~300 reqs | Detects when a different :free model becomes the best free fallback |
| **Slack/Discord summary** — digest non-Mercury channels Soumit follows | ~50 reqs | Free reading time for Soumit |
| **Reserve / overflow** | ~50 reqs | Headroom for ad-hoc agent invocations |
| **Total** | **~1000 reqs** | |

## Cron entries

```cron
# UTC times — Mercury cron lives in ~/.mercury/cron/
00 06 * * *  /usr/bin/python3 ~/cortex/mercury/scripts/openrouter_daily.py audit
05 06 * * *  ~/.mercury/cron/morning_log_digest.sh
30 06 * * *  ~/.mercury/cron/session_insights.sh
00 07 * * *  ~/.mercury/cron/skill_audit.sh
30 07 * * *  ~/.mercury/cron/memory_consolidation.sh
00 08 * * *  ~/.mercury/cron/eval_harness.sh
00 12 * * *  ~/.mercury/cron/midday_dispatch.sh
00 18 * * *  ~/.mercury/cron/evening_doc_sync.sh
00 23 * * *  /usr/bin/python3 ~/cortex/mercury/scripts/openrouter_daily.py status > ~/.mercury/logs/quota-eod.log
```

Each cron script:
1. Calls `openrouter_daily.py reserve --count N --task <name>` first; bails on non-zero
2. Runs the actual work via `mercury -m google/gemma-4-26b-a4b-it:free --provider openrouter-free ...`
3. Calls `openrouter_daily.py record --model ... --task <name>` per call

## Failure modes & guards

- **Quota exhausted before EOD** — script exits clean with status code 1; cron entry doesn't retry. Tomorrow's 1k allocation picks up.
- **Free tier rate-limited (429 burst)** — Mercury sleeps 60s and retries up to 3x; if still 429, marks `openrouter-free` unhealthy for 5 minutes.
- **Paid model accidentally invoked** — `record` subcommand alerts to stderr if cost > $0.01; tripwire sends a Discord notification.
- **OpenRouter outage** — Mercury falls back to local-only routing. Self-update jobs that need cloud just skip for the day; local jobs (eval against own MLX) keep running.

## What I never use the paid pool for

Hard-disabled list (only unlocked with `--allow-paid` flag):
- Anything routine — log digests, doc syncs, summaries
- Anything cron-scheduled
- Skill audits, memory hygiene
- Eval harness runs

Soft-allowed with explicit flag (when local + free both fail):
- Live user-facing query that Mercury must answer right now
- Demo-day burst when judges are testing
- Specific debug runs Soumit invokes manually

## Status sources

- Local: `python3 ~/cortex/mercury/scripts/openrouter_daily.py status`
- Remote: `python3 ~/cortex/mercury/scripts/openrouter_daily.py audit`
- Live balance via [OpenRouter dashboard](https://openrouter.ai/credits)
