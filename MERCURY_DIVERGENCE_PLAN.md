# Mercury Divergence Plan — 2026-05-04

> Mercury is currently a **fork of NousResearch/hermes-agent** with local additions. The plan: pull upstream one final time to claim the bug fixes + features that matter, then **hard-divergence** — purge the "Hermes" name everywhere, rewrite the hot paths in faster languages, and ship a leaner, faster, native-feeling local-first agent.

This document is a phased plan, not a "do it all in one PR" instruction. Each phase ships independently.

---

## Snapshot — current state (2026-05-04 08:11)

| | |
|---|---|
| Mercury branch | `main` at `c14931704` (~310 K LOC Python + ~25 K LOC TypeScript) |
| Upstream tracked | `https://github.com/NousResearch/hermes-agent.git` |
| Behind upstream | **1,262 commits** (`HEAD..upstream/main`) |
| "hermes" in tree | 1,279 files, ~15 K occurrences, 287 paths contain `hermes` in the name |
| Largest modules | `run_agent.py` (12,647 LOC), `gateway/run.py` (11,147), `cli.py` (11,116), `mercury_cli/main.py` (9,309) |
| TUI | TypeScript + Ink (`ui-tui/`) — separate package |
| Web app | React + Vite (`mercury-web/`) — separate package |

---

## Phase 0 — pre-merge inventory (do this first, ~30 min)

Reconnaissance, no destructive changes.

1. **Branch off** a `pre-divergence-snapshot` tag at the current `c14931704` so we can always roll back.
2. **Diff stats** for the merge surface:
   ```
   git diff HEAD..upstream/main --stat | tail -30
   git log HEAD..upstream/main --pretty=format:"%h %s" | grep -iE "(security|cve|perf|memory|leak|deadlock|crash)"
   ```
3. **Identify must-take commits** (security + correctness + perf wins). From the survey, the high-value ones:
   - `e50809b77 fix(file-tools): cap read_file result size to prevent context window overflow`
   - `d29f90e89 fix(error_classifier): avoid large-context false overflow heuristics`
   - `b7bbc6250 fix(compressor): _prune_old_tool_results boundary direction`
   - `0cc63043e fix(delegation): increase heartbeat stale thresholds`
   - `74c1b946e fix(browser): inject --no-sandbox for root and AppArmor userns restrictions`
   - `52882dade fix(agent): include name field on every role:tool message for Gemini compatibility (#16478)`
   - `5ec6baa40 feat(kanban): multi-project boards — one install, many kanbans (#19653)`
   - `a175f3957 feat(nous): persist Nous OAuth across profiles via shared token store (#19712)`
4. **Skip** commits that bake the Hermes brand deeper (UI strings, CLI banners, telemetry endpoints, Hermes Atropos environments). Those will conflict with the rebrand anyway.

## Phase 1 — selective upstream merge (one workday)

Don't `git merge upstream/main` blindly — that's 1,262 commits including a lot of CI churn. **Cherry-pick + squash.**

1. Create a feature branch: `git checkout -b sync-2026-05-upstream`.
2. **Cherry-pick the must-take list** from Phase 0. Each is small and merges cleanly into our base.
3. For larger features (multi-project kanban boards, web config improvements), cherry-pick the merge commits with `git cherry-pick -m 1 -x <sha>`.
4. Run the full test suite (`uv run pytest tests/` — should be green; the local additions don't touch most of these paths).
5. **Manually verify** Discord gateway, Snowy bot, dashboard at port 9119, OAuth flows.
6. Merge `sync-2026-05-upstream` to `main` once green.

Expected delta: ~60–100 commits cherry-picked, mostly bug fixes + 2–3 features. Not 1,262.

**What we leave on the table from upstream**: the entire `hermes-` branding (UI strings, banner ASCII art, Sentry telemetry endpoints calling home to Nous), the `hermes-atropos-environments` skill (we don't run RL training), and any commits that introduce paid Nous Research API dependencies.

## Phase 2 — hard rebrand (Hermes → Mercury everywhere) (one workday)

This is mechanical. The blast radius is wide but each replacement is local.

### What stays "Hermes"-shaped

- `upstream` git remote — kept so we can keep cherry-picking. Branch `upstream/main` is read-only history; don't push to it.
- `mercury_cli/` itself — already named, no change.
- Anything inside `.git/` — automatic.

### What gets renamed

| From | To | Why |
|---|---|---|
| `Hermes`, `hermes` (brand) | `Mercury`, `mercury` | The point of the divergence. |
| `hermes-agent` (CLI invocation) | `mercury-agent` (alias for `mercury`) | Already mostly done. |
| `~/.hermes/` (home dir) | `~/.mercury/` | Keep a symlink for one release cycle so existing users don't lose state. |
| `HERMES_*` env vars | `MERCURY_*` | Read both during a 2-release deprecation window. |
| `tests/hermes_cli/` | `tests/mercury_cli/` | Rename + fix imports. |
| `tests/hermes_state/` | `tests/mercury_state/` | Same. |
| `ui-tui/packages/hermes-ink` | `ui-tui/packages/mercury-ink` | Package rename + tsconfig path updates. |
| `scripts/hermes-gateway` (binary symlink) | `scripts/mercury-gateway` | Plus shim that prints a deprecation warning. |
| Nous Research telemetry endpoints | Either remove entirely OR self-host on `telemetry.redteamkitchen.com` | Don't keep calling home to a separate org's DNS for our forked product. |
| `hermes-self-evolution` skill | `mercury-self-evolution` | If we keep it. |
| README headers, banners, config snippets | All branded "Mercury" | One-shot sed per file, then human read-through. |

### Mechanical execution recipe

```bash
# 1. Audit the scope (already done):
git grep -lI -i 'hermes' | wc -l                  # 1279 files

# 2. Run a careful sed pass — case-preserving:
git ls-files | xargs perl -p -i -e '
    s/HERMES/MERCURY/g;
    s/Hermes/Mercury/g;
    s/hermes/mercury/g;
'

# 3. Rename file paths separately (sed touches contents only):
git mv hermes/                        mercury/
git mv mercury_cli/                   mercury_cli/        # already named
git mv tests/hermes_cli/              tests/mercury_cli/
git mv tests/hermes_state/            tests/mercury_state/
git mv ui-tui/packages/hermes-ink/    ui-tui/packages/mercury-ink/
git mv scripts/hermes-gateway         scripts/mercury-gateway
git mv environments/hermes_swe_env/   environments/mercury_swe_env/
git mv environments/hermes_base_env.py environments/mercury_base_env.py
git mv skills/autonomous-ai-agents/hermes-agent/ skills/autonomous-ai-agents/mercury-agent/
git mv skills/self-evolution/hermes-self-evolution/ skills/self-evolution/mercury-self-evolution/

# 4. Search for hand-curated "Hermes" references (skill descriptions, model
#    names, OAuth scopes that include 'hermes' as a literal string) — those
#    might be intentional and need human review:
git grep -nI 'hermes' | grep -vE '^(\.git/|.*\.lock:|.*\.json:|tests/)' | head -50

# 5. Add ~/.hermes → ~/.mercury symlink shim:
#    mercury_cli/config.py: HERMES_HOME = Path.home() / ".hermes"  →
#                           MERCURY_HOME = Path.home() / ".mercury"
#                           but also accept ~/.hermes if it exists, with one warning.

# 6. Backward-compat env-var shim:
#    For each HERMES_* env var, fall back to it ONCE with a DeprecationWarning.

# 7. Update the README, AGENTS.md, CONTRIBUTING.md, LICENSE attribution
#    (keep upstream credit but rename the product).

# 8. Bump major version: 0.x → 1.0.0 to mark the divergence.
```

### Risks of the rebrand

- **OAuth tokens with `hermes` in the path** stop being read until users re-authenticate (or the symlink shim covers them). Document loudly.
- **Cron jobs / systemd units** that hard-coded `~/.hermes/...` will break. Provide a migrate script.
- **Public mentions / reviews** still reference Hermes. Use the README to make the lineage explicit: "Mercury is a divergent fork of Hermes by Nous Research; we rewrote X, Y, Z and renamed for clarity."

---

## Phase 3 — performance rewrite (the long arc)

The Python codebase is 311 K LOC. Most paths are I/O-bound (LLM calls, gateway HTTP, file I/O) and don't need a rewrite. **Profile first, rewrite second.**

### Where Python is genuinely slow / wasteful

| Hot path | Problem | Candidate replacement | Effort |
|---|---|---|---|
| **Token streaming + parse** (LLM stream chunks) | Per-chunk regex + JSON parse in pure Python; eats CPU when running 4× concurrent narrations | **Rust crate via PyO3** (sub-30 LOC) — stream_chunk_parse | M |
| **Compressor + token counter** (`agent/compressor.py`) | Run on every turn; tiktoken is C but the surrounding loop is Python | Rust extension with a thread-safe `tiktoken_rs` wrapper | M |
| **Logsearch / FTS5** | Cross-session search; SQLite FTS5 is fast but the result-ranking logic is Python | Already SQLite, marginal gains | S |
| **Gateway message dedup** (Discord/QQ/etc.) | Hashmap on every inbound message; CPython dict scaling fine to 10k msg/s — leave it | — | — |
| **TUI render loop** (Ink, TS) | React reconciler is overkill for a terminal | Replace `ui-tui/` with **Bubble Tea (Go)** — single static binary, no Node, ~10 MB | L |
| **MCP server poller** | Every tick walks the list of registered MCP servers and pings them in series | Goroutine fanout if we move to Go, or `asyncio.gather` if we stay Python | S (gather) / L (Go rewrite) |
| **Web dashboard** (`mercury-web/`, React + Vite) | Bundle size 1.6 MB, slow first paint | **SolidJS or HTMX + minimal JS** — same UX, 10× smaller bundle | M |

### Recommended language picks (post-Phase 2)

- **Stay Python** for: core agent loop, LLM clients, gateway adapters, anything that touches `httpx`/`aiohttp`. Python is the right tool here.
- **Add Rust** for: token-bucket parser, compressor, hot regex/JSON paths. PyO3 + maturin makes this painless. Ship as `mercury-fast` extension.
- **Replace Node TUI with Go (Bubble Tea)** — the TUI is a leaf concern; can be developed and shipped independently. One static binary, instant start, native terminal feel. Inspiration: `lazygit`, `glow`, `gh`.
- **Replace React web dashboard with SolidJS** — same ergonomics for our team, ~10× smaller bundle, no virtual DOM overhead. Or **HTMX + Alpine** if we want to delete the build pipeline entirely.

### Sequencing

1. Profile the agent under load (concurrent narration burst). `py-spy record -- python -m mercury chat …` → flame graph.
2. Pick the top-2 hot paths from the flame graph. Rewrite those in Rust via PyO3.
3. **Independently** (different Mercury CLI subcommand, different binary), prototype `mercury tui` in Go using Bubble Tea — keep the Python TUI as fallback during the transition.
4. **Independently**, replace `mercury-web/` build with SolidJS or HTMX.

Expected outcome:
- Cold start: 1.8 s (current Python+Ink) → ~80 ms (Go binary)
- Memory: ~280 MB resident → ~40 MB
- Concurrent narration: ~325 tok/s aggregate → ~500 tok/s (Rust parsing path)
- Web dashboard bundle: 1.6 MB → ~150 KB (SolidJS) or ~30 KB JS (HTMX)

---

## Phase 4 — TUI overhaul + new live-render surfaces

Once the Go-based TUI is in:

1. **Live GPU + queue panes** — same data the cortex `/api/fleet-health` exposes, rendered as in-terminal sparklines via `lipgloss` charts.
2. **Discord conversation panel** — split-screen, current channel + agent reply.
3. **Kanban-in-terminal** — multi-project boards (we get this from the upstream merge).
4. **Embedded log tail** with regex filtering, jump-to-bottom, copy-mode (we have a working pattern in the cortex frontend; port the UX to TUI).
5. **Mouse + keyboard parity** — Bubble Tea handles both natively. Vim-style nav, mouse for click-to-focus.

### Other live-info renderers worth integrating

- **Local OBS scene controller** — already a skill; surface in TUI as a hotkey ("press `s` to start streaming this session").
- **Big Apple ↔ Sera fleet view** — pretty-printed JSON of `/api/fleet-health`, refreshed via WS.
- **Mercury session graph** — use https://github.com/lucasb-eyer/graph-as-text-output to render a node graph of agent → tool calls in the terminal.

---

## Risk log

| Risk | Mitigation |
|---|---|
| Cherry-pick conflicts blow up | Pre-divergence-snapshot tag; merge each commit individually; back out anything that touches >5 files we've modified locally |
| Rebrand breaks user OAuth | `~/.hermes` symlink shim + env-var fallbacks for one release |
| Telemetry endpoint removal silently breaks update checks | Either self-host or disable the update-check entirely; document |
| Rust extension build fails on a user's machine | Ship pre-built wheels for win64/linux64/macOS arm64; pure-Python fallback always available |
| Go TUI fragments the project (now 3 languages) | Worth it: Python core stays Python, TUI is a thin client over the daemon, and Bubble Tea binaries are trivial to distribute |
| 1262-commit merge introduces a regression we don't catch | Cherry-pick selectively, not bulk merge; manual smoke-test the 4 critical paths (CLI, gateway, dashboard, OAuth) |

---

## TL;DR

1. **Merge selectively, not bulk**: cherry-pick ~60–100 high-value commits from upstream, leave the brand-bake-in commits behind. ~1 day.
2. **Rebrand mechanically**: sed pass + git mv pass + symlink shim for `~/.hermes`. 1 day, hold a backup tag.
3. **Profile before rewriting**: `py-spy` → top-2 hot paths → Rust PyO3 extension. Keep Python core.
4. **Replace TUI with Go (Bubble Tea)** and React web dashboard with SolidJS/HTMX. Each ships independently.
5. **TUI gets live GPU/queue/Discord panes** powered by the same WebSocket stream we'll add for the cortex frontend.
6. **Don't touch upstream remote** — keep cherry-picking trickle of fixes, even after divergence.
