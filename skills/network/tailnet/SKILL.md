---
name: tailnet
description: Manage the Tailscale-only network that connects the RTX 5090 desktop, the Pixel 9 Pro Fold, the Mac Mini M4, and a GCP Cloud Run instance into one private mesh for Mercury. Use when the user asks about ACLs, "can my phone reach the agent", remote access, identity-aware proxying, or wiring a new device into the trust group. The WebUI and API are tailnet-only by hard invariant — do not expose them publicly.
version: 0.1.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [tailscale, network, security, identity, mesh, mtls, zero-trust]
    category: network
    related_skills: [whatsapp, discord-bot, brain-viz]
prerequisites:
  binaries: [tailscale]
  files: [tailnet/acls.hujson]
---

# Tailnet — Mercury's Private Mesh

Mercury runs as a single-tenant agent on the user's tailnet. There is no
public surface and no Funnel. Reaching the WebUI, the API, or any of the
brain pipeline endpoints requires being on the tailnet AND being authorized
by the ACL that lives in [`acls.hujson`](./acls.hujson).

## Devices

| Tag | Device | Role | Capabilities |
|---|---|---|---|
| `tag:gpu` | RTX 5090 desktop (Windows 11) | Canonical Mercury host | Mercury agent (`:8765` API, `:5173` WebUI), Cortex backend, Ollama, all training |
| `tag:mobile` | Pixel 9 Pro Fold (Android, Tensor G4, 16 GB RAM) | Mobile interface | Mercury via Termux, WhatsApp gateway, on-device Gemma 4 E4B (~5 GB Q4_K_XL) |
| `tag:cloud` | GCP Cloud Run instance (rtk-prod-2026) | Cold-start failover | Static webapp, GPU-job proxy via Cloudflare Tunnel back to GPU host |
| `tag:mac` | Mac Mini M4 | MLX inference fallback | Gemma 4 12B via MLX, llama.cpp endpoint at `:11435` |

The tagged-email owner across all of them is `soumitlahiri@philanthropytraders.com`.

## When to Use This Skill

- "Add my [phone | laptop | cloud VM] to the tailnet so it can reach Mercury"
- "Can the WebUI be opened from my phone?" → yes, via the tailnet IP, with `Tailscale-User-Login` automatically asserted
- "I need to call the agent from a CI job" → add the CI runner to `tag:cloud`, narrow ACL
- "Why is the WebUI giving 403 to my browser?" → identity middleware needs `Tailscale-User-Login`; you're hitting a non-tailnet origin
- Any prompt about Tailscale config, ACLs, or identity-aware routing

**Do NOT use** to expose Mercury publicly. The hard invariant in `CLAUDE.md`
forbids `tailscale serve --funnel`. If a user needs public access to the
brain demo, route through Cloud Run (which IS public-facing) and have it
proxy authenticated calls back to the tailnet.

## Identity Middleware

Mercury's API trusts these headers, set automatically by Tailscale's identity-
aware proxy when a request comes through `tailscale serve`:

```
Tailscale-User-Login    soumitlahiri@philanthropytraders.com
Tailscale-User-Name     Soumit Lahiri
Tailscale-User-Profile-Pic   https://...
```

Mercury's `/api/mercury/*` routes (commit `92bc13aa`) check `Tailscale-User-Login`
and reject requests without it (403 with reason `not_on_tailnet`). This means
WhatsApp messages relayed in via the gateway can be cleanly attributed without
asking the user to log in.

## ACL — `acls.hujson`

The full file lives next to this `SKILL.md`. Key sections:

```hujson
{
  "tagOwners": {
    "tag:gpu":    ["soumitlahiri@philanthropytraders.com"],
    "tag:mobile": ["soumitlahiri@philanthropytraders.com"],
    "tag:cloud":  ["soumitlahiri@philanthropytraders.com"],
    "tag:mac":    ["soumitlahiri@philanthropytraders.com"],
  },
  "acls": [
    // Mobile and Mac can reach the agent + WebUI on the GPU host
    { "action": "accept",
      "src":    ["tag:mobile", "tag:mac"],
      "dst":    ["tag:gpu:8765",   // mercury API
                 "tag:gpu:5173",   // mercury-web
                 "tag:gpu:8766"]   // cortex API (read-only from non-GPU)
    },

    // Cloud failover: Cloud Run instance can call into GPU for inference
    { "action": "accept", "src": ["tag:cloud"], "dst": ["tag:gpu:8765"] },

    // GPU host can push notifications to mobile via the Hermes gateway
    { "action": "accept", "src": ["tag:gpu"], "dst": ["tag:mobile:443"] },

    // Owner SSH everywhere for maintenance
    { "action": "accept",
      "src":    ["soumitlahiri@philanthropytraders.com"],
      "dst":    ["tag:gpu:22", "tag:cloud:22", "tag:mac:22"] }
  ],
  "ssh": [
    { "action": "accept",
      "src":    ["soumitlahiri@philanthropytraders.com"],
      "dst":    ["tag:gpu", "tag:cloud", "tag:mac"],
      "users":  ["soumit", "root"] }
  ]
}
```

Apply with `tailscale set --policy-file=acls.hujson` (admin-API equivalent).

## Onboarding a New Device

```bash
# 1) Install the client (Windows / macOS / Linux / Android / iOS)
#    https://tailscale.com/download
# 2) Authenticate against the tailnet
tailscale up --auth-key=$TS_AUTHKEY --hostname=<choose>
# 3) Tag it (admin → Machines → Edit Tags) — pick from gpu/mobile/cloud/mac
# 4) Verify reachability
tailscale ping <other-device>
# 5) For mobile, install Hermes via Termux
#    https://hermes-agent.nousresearch.com/docs/getting-started/termux
```

For the Pixel 9 Pro Fold specifically, see [`PIXEL_FOLD_SETUP.md`](./PIXEL_FOLD_SETUP.md) (in this directory) — covers Termux + Hermes Agent + the WhatsApp gateway init.

## Output Contract

This skill is mostly a knowledge document — its tools are CLI invocations of
`tailscale` and edits to `acls.hujson`. When chained with brain-viz or
discord-bot it provides the *who-can-reach-what* answer to any "should this
work over the network?" question.

## Hard Invariants (matches `CLAUDE.md` rule #1)

1. **No `tailscale serve --funnel` for Mercury.** Public exposure of the agent
   is forbidden. If something appears to require it, route through Cloud Run.
2. **Always trust `Tailscale-User-Login`** on Mercury's `/api/mercury/*` —
   no fall-through to anonymous user.
3. **No DERP relay for `tag:gpu` ↔ `tag:cloud`** if a direct WireGuard
   handshake is possible (Tailscale handles this automatically; if you see
   relay use, check for double-NAT on the GPU host).
