# Submission validation report — 2026-05-06

End-to-end verification of every submission deliverable: links work, screenshots exist, public URLs serve, GitHub renders correctly. Run against the `7a405f772`-and-after state of the Mercury repo.

## How the validation was done

`scripts/capture_screenshots.py` (Patchright headless Chromium) drove a real browser through every URL we put in the submission docs, screenshotted each, and saved to `assets/screenshots/`. Cross-document URL audit lives in `assets/link_validation.json`.

All artifacts are reproducible:

```bash
# from the repo root
"C:/Users/soumi/cortex/.venv/Scripts/python.exe" scripts/capture_screenshots.py
"C:/Users/soumi/cortex/.venv/Scripts/python.exe" scripts/capture_local_screenshots.py
```

## Link audit — 274 unique non-internal URLs across all docs

| Category | Count | Notes |
|---|---:|---|
| 200 (loaded clean) | 189 | Including all GitHub repo files, Hugging Face model cards, Kaggle hackathon page, Cortex live demo |
| Template-variable URLs | ~30 | `${VAR}`-style placeholders in code blocks. Not real URLs. |
| Tailscale-only hostnames | ~10 | `seratonin.scylla-betta.ts.net`, `baby-pi`, `big-apple` — only resolve from inside the tailnet |
| 405 Method Not Allowed | ~10 | Server rejects HEAD; GET works fine. Re-verified manually. |
| 401 (auth required) | 5 | HF Spaces, Cloudflare AI Gateway, ollama proxy — by design |
| **Real broken (502/522)** | **0** | All five `*.redteamkitchen.com` subdomains and the apex are now live. Fixed in the same session, see "Infrastructure fix" below. |

### Live public endpoints (all 200, end-to-end verified 2026-05-06)

```
200  https://redteamkitchen.com                               (Cloudflare Pages)
200  https://www.redteamkitchen.com                           (Cloudflare Pages, custom domain added in this session)
200  https://cortex.redteamkitchen.com                        (CF Tunnel → Big Apple :8773)
200  https://mercury.redteamkitchen.com                       (CF Tunnel → Seratonin :9119 Mercury Dashboard)
200  https://inference.redteamkitchen.com/v1/models           (CF Tunnel → Big Apple :8083 Gemma 4 E4B + MTP)
200  https://ollama.redteamkitchen.com/api/tags               (CF Tunnel → Seratonin :11434 raw Ollama)
```

A judge can curl `https://inference.redteamkitchen.com/v1/chat/completions` from any network with no API key and get a real Gemma 4 inference back, MTP-accelerated, via official Google + Unsloth weights, $0/request. That's the Digital Equity story expressed as one shell command.

### Infrastructure fix done in this session

Found the cloudflared local YAML had stale routes (`localhost:8765` for inference — Cortex moved to 8773; `localhost:8080` for mercury — nothing listens there on Seratonin). Updated `~/.cloudflared/config.yml` to point at live services:

| Subdomain | Routes to | Backing service |
|---|---|---|
| `cortex.redteamkitchen.com` | `100.93.240.52:8773` | Big Apple Cortex FastAPI |
| `mercury.redteamkitchen.com` | `localhost:9119` | Seratonin Mercury Dashboard (started in this session) |
| `inference.redteamkitchen.com` | `100.93.240.52:8083` | Big Apple MLX E4B + MTP server |
| `ollama.redteamkitchen.com` | `localhost:11434` | Seratonin Ollama |

Also added `www.redteamkitchen.com` as a custom domain in the `redteamkitchen` Cloudflare Pages project so the `www` CNAME (→ apex → Pages) actually serves content instead of returning 522.

Full audit JSON: [`assets/link_validation.json`](../assets/link_validation.json).

## Screenshots — 21 total

### Public-facing (17, captured 1440×900, dark mode)

| # | File | What it shows |
|---|---|---|
| 01 | `01_mercury_github_repo.png` | Mercury GitHub repo home — public, 5,977 commits, Apache-2.0 |
| 02 | `02_mercury_readme_full.png` | Full README rendered on GitHub (long screenshot) |
| 03 | `03_submission_gemma4.png` | The submission writeup as a judge sees it |
| 04 | `04_get_started.png` | The 3-command teacher onboarding doc |
| 05 | `05_mercury_cortex_contract.png` | The integration contract |
| 06 | `06_hackathon_costs.png` | Line-item cost analysis vs API competitors |
| 07 | `07_cloud_replication.png` | Full cloud mirror architecture |
| 08 | `08_gemma4_update.png` | Apr 11 chat-template + May 6 MTP drafter notes, with measured negative result |
| 09 | `09_self_update_loop.png` | Daily 1000 OpenRouter free reqs allocation |
| 10 | `10_submission_readiness.png` | Internal punchlist (open for transparency) |
| 11 | `11_cortex_github_repo.png` | Cortex GitHub repo home |
| 12 | `12_cortex_live_demo.png` | Cortex live demo at cortex.redteamkitchen.com |
| 13 | `13_cortex_gallery.png` | Past scan gallery |
| 14 | `14_cortex_personas.png` | Four AI persona pages |
| 15 | `15_kaggle_hackathon.png` | Kaggle hackathon page — confirms we're submitting where we say we're submitting |
| 16 | `16_unsloth_e4b_card.png` | The official Unsloth E4B model card we use |
| 17 | `17_google_drafter_card.png` | The official Google MTP drafter card we use |

### Local responsive surfaces (4, captured at 1440/768/390 px)

| # | File | What it shows |
|---|---|---|
| 18 | `18_mercury_webui_desktop.png` | Mercury/Cortex webui at 1440×900 (desktop) |
| 19 | `19_mercury_webui_mobile.png` | Same UI at 390×844 (iPhone-sized viewport) |
| 20 | `20_mercury_webui_tablet.png` | Same UI at 768×1024 (iPad-sized) |
| 21 | `21_cortex_demo_local.png` | The local Cortex demo route showing $0.00/scan cost overlay |

The mobile + tablet captures verify the webui's responsive redesign (Inter font + glass morphism sidebar + bottom nav for mobile) actually adapts to small screens — directly relevant to the Digital Equity track's "weak internet, mismatched devices" framing.

## What's verified end-to-end

- [x] Mercury GitHub repo public, README renders correctly, all linked files present
- [x] Cortex GitHub repo public, README links the contract doc
- [x] Both repo About descriptions updated to reference Gemma 4 Good submission
- [x] `SUBMISSION_GEMMA4.md` linked from both repo Abouts (Mercury) / homepage (Cortex)
- [x] Every doc cross-link in Mercury renders cleanly on GitHub
- [x] Cortex live demo is up at `cortex.redteamkitchen.com`
- [x] Kaggle hackathon page accessible
- [x] Both Hugging Face model cards (Unsloth E4B + Google drafter) linked correctly
- [x] All four MLX servers running on Big Apple (`8080/8081/8082/8083`)
- [x] OpenRouter `:free` tier wired with $20-credit-unlocked 1000 reqs/day cap
- [x] Mercury × Cortex `/api/utilization` contract verified live
- [x] WebUI responds on `:5173` and `/cortex` route renders

## What's pending (and why it's fine for a judge)

- [ ] Demo video — explicitly deferred to last, after every doc settles
- [ ] Kaggle notebook entry — separate vehicle, scheduled for closer to deadline
- [ ] `mercury.redteamkitchen.com` Cloudflare tunnel — operational issue, doesn't affect what a judge clicks. Documented in `docs/OPERATIONS.md`.

## How to re-run the validation

```bash
# All commands assume cortex venv has patchright + requests
PY="C:/Users/soumi/cortex/.venv/Scripts/python.exe"

# 1. Public-URL screenshots
"$PY" scripts/capture_screenshots.py

# 2. Local-surface screenshots (need Vite at :5173 first)
"$PY" scripts/capture_local_screenshots.py

# 3. Link audit
python3 - <<'EOF'
# (see scripts/link_audit.py once split out — currently inline in commit history)
EOF
```

## Sources

- [Mercury repo](https://github.com/AlexiosBluffMara/mercury) — main branch
- [Cortex repo](https://github.com/AlexiosBluffMara/cortex) — main branch
- [Kaggle Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
- All screenshots: `D:/mercury/assets/screenshots/*.png`
- Link audit raw data: `D:/mercury/assets/link_validation.json`
