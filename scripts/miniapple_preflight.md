# miniapple — one-time SSH preflight

The Mac Mini's tailnet IP is reachable but its SSH listener is closed.
You only need to do **one** of these (Tailscale-native is recommended).

## Option A — Tailscale SSH (recommended)

Run on the **Mac Mini** (open Terminal locally):

```sh
sudo tailscale up --ssh
```

Tailscale's own daemon then handles inbound SSH; macOS Remote Login can
stay off. Tailnet identity (your Apple Account / Tailscale ACL) auths the
session — no SSH keys needed from `seratonin`.

Verify from `seratonin` (this Windows box):

```bash
tailscale ssh soumitlahiri@miniapple 'echo OK && hostname && whoami'
```

## Option B — macOS Remote Login

System Settings → General → Sharing → **Remote Login: ON**
(Allow access for: your user only.)

Verify:

```bash
ssh soumitlahiri@miniapple 'echo OK'
```

---

Once either is live, run the extraction:

```bash
bash D:/mercury/scripts/extract_miniapple.sh
```
