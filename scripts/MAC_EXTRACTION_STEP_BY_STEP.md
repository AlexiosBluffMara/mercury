# Mac Mini extraction — pick one path, ~10 minutes start to finish

The Mac Mini's name is `miniapple` (Tailscale IP `100.75.223.113`).
You used Hermes directly on it — every Kimi K2.6 call has a paper trail
in `~/.mercury/logs/`, `~/.mercury/sessions/`, your shell history, and
each git repo's commit log. Below are three paths, ranked by friction.

---

## Path A — paste & run, push via Google Drive (recommended now)

You said you have Google Workspace. Drive has 2 TB on Standard, plenty of
room for a few-GB tarball. This path doesn't need SSH, doesn't need
Tailscale taildrop, and works while Parsec is still up.

### On the Mac Mini (in Terminal — paste the whole block)

```sh
# 1. Build the dump
cd ~ && DATE=$(date +%Y%m%d_%H%M%S)
DUMP=~/Desktop/miniapple_dump_${DATE}.tgz
PRIV=~/Desktop/miniapple_dump_${DATE}_PRIVATE.tgz

# everything-but-secrets
tar --exclude='*/node_modules/*' --exclude='*/.venv/*' \
    --exclude='*/__pycache__/*' --exclude='*/.DS_Store' \
    --exclude='*/Library/Mail/*' --exclude='*/Library/Photos/*' \
    --exclude='*/Library/Music/*' --exclude='Pictures/*' \
    --exclude='Music/*' --exclude='Movies/*' \
    -czf "$DUMP" \
    .mercury .hermes .claude .local .cargo .config .zsh_history \
    .zsh_sessions .bash_history .python_history \
    dev Projects code work src \
    Library/LaunchAgents \
    "Library/Application Support/Code" \
    "Library/Application Support/Cursor" \
    "Library/Application Support/Ollama" \
    2>/dev/null

# secrets — keep separate, never push to a public repo
tar -czf "$PRIV" .ssh .gnupg .gitconfig .netrc .aws .config/gcloud .docker 2>/dev/null

# every git repo's full log so you can audit Kimi commits even before extracting
mkdir -p ~/Desktop/miniapple_manifest_${DATE}/gitlogs
find ~ -type d -name .git \
  -not -path '*/Library/*' -not -path '*/node_modules/*' \
  -not -path '*/.venv/*' 2>/dev/null | sed 's,/.git$,,' \
  > ~/Desktop/miniapple_manifest_${DATE}/git_repos.txt
while read repo; do
  slug=$(echo "$repo" | sed 's,[/ ],_,g')
  ( cd "$repo" && git log --all --pretty='%h %ai %an <%ae> %s' 2>/dev/null ) \
    > ~/Desktop/miniapple_manifest_${DATE}/gitlogs/$slug.log
done < ~/Desktop/miniapple_manifest_${DATE}/git_repos.txt

# kimi authorship trail — every file mentioning kimi/moonshot/nous
grep -ril --include='*.md' --include='*.txt' --include='*.py' --include='*.json' \
  -e kimi -e moonshot -e nous-portal \
  ~/dev ~/Projects ~/code ~/.mercury ~/.hermes 2>/dev/null \
  > ~/Desktop/miniapple_manifest_${DATE}/kimi_touches.txt

ls -lh "$DUMP" "$PRIV"
```

### Upload to Drive (still on the Mac)

```sh
# Easiest: open Finder → drag the two .tgz files into a Drive folder.
# Or via gdrive CLI if installed:
brew install gdrive-org/gdrive/gdrive 2>/dev/null
gdrive about               # one-time auth
gdrive files upload "$DUMP"
gdrive files upload "$PRIV"      # PRIVATE — share with no one
```

Or simply drag both `.tgz` files from your Desktop into
`drive.google.com/drive/my-drive` in your browser.

### Pull on this Windows box

```bash
# Install gcloud's gsutil-equivalent for Drive (or just download via browser).
# Browser path is fastest:
#   1. drive.google.com → right-click each .tgz → Download
#   2. Default save path is C:/Users/soumi/Downloads/

mkdir -p D:/miniapple_archive/$(date +%Y%m%d)
mv C:/Users/soumi/Downloads/miniapple_dump_*.tgz D:/miniapple_archive/$(date +%Y%m%d)/

# Sanity-check the manifest before extracting
tar -tzf D:/miniapple_archive/$(date +%Y%m%d)/miniapple_dump_*.tgz | head -50
```

Then run the authorship-isolation script:
```bash
bash D:/mercury/scripts/isolate_kimi_authorship.sh \
  --archive D:/miniapple_archive/$(date +%Y%m%d) \
  --out    D:/mercury/kimi_artifacts
```

---

## Path B — Tailscale taildrop (no Drive, no SSH)

Same dump, but pushed peer-to-peer over the tailnet without ever leaving
your network. Requires `tailscale` CLI on both ends (you have both).

### On the Mac Mini

Run the bundled script:
```sh
bash <(curl -fsSL file://"$(open -R . | head -1)")    # if you mounted seratonin
# OR paste D:/mercury/scripts/RUN_ON_MAC_extract.sh into Terminal directly.
```

The script ends with `tailscale file cp <tgz> seratonin:` calls.

### On Windows

```bash
mkdir -p D:/miniapple_archive
tailscale file get D:/miniapple_archive/
```

---

## Path C — Tailscale SSH (if you got it working)

What didn't work last time was probably running `tailscale up --ssh`
without `sudo`. Try, on the Mac:
```sh
sudo tailscale up --ssh
sudo tailscale set --ssh           # idempotent — safe to re-run
tailscale status | grep $(hostname)
```
You should see `ssh` in the line. Then on Windows:
```bash
tailscale ssh soumitlahiri@miniapple 'echo OK'
bash D:/mercury/scripts/extract_miniapple.sh         # uses ssh
```

If `sudo tailscale up --ssh` errors with "Tailscale daemon is not running",
restart it: System Settings → Network → Tailscale → toggle off/on, then
re-run the command.

---

## After extraction — what to look for

1. `manifest/git_repos.txt` — full list of repos. Walk these to find Kimi commits.
2. `manifest/gitlogs/*.log` — `grep -i kimi` across these reveals Kimi-authored commits.
3. `manifest/kimi_touches.txt` — every file referencing kimi/moonshot/nous-portal.
4. `~/.mercury/sessions/*.json` (inside the tarball) — full Hermes conversation
   history; each Kimi call has the model name in the metadata.
5. `~/.mercury/logs/agent.log` — the agent's own log of which model each
   tool call routed to.

Build the public-submission `kimi_artifacts/` from those four sources.
The PRIVATE tarball stays out of any commit, ever.
