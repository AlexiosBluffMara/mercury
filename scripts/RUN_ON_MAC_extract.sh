#!/usr/bin/env bash
# RUN_ON_MAC_extract.sh
#
# Paste this entire script into Terminal **on miniapple** (the Mac Mini),
# then run it. No SSH from Windows is required. The output tarball is
# pushed back to seratonin (this Windows box) over the tailnet via
# Tailscale taildrop — no port 22, no SMB share, no iCloud needed.
#
# What it captures:
#   1. Mercury / Hermes runtime state    (~/.mercury, ~/.hermes)
#   2. Claude Code state if any          (~/.claude)
#   3. Shell history + sessions          (.zsh_history, .bash_history, .zsh_sessions)
#   4. Dev trees                         (~/dev, ~/Projects, ~/code, ~/work, ~/src)
#   5. Kimi-touched files (manifest)     grep -ril for kimi/moonshot/nous-portal
#   6. User LaunchAgents                 (~/Library/LaunchAgents)
#   7. Non-Apple Application Support     (Code, Cursor, JetBrains, Ollama)
#   8. Brew + uv + cargo + pip state     (~/.local, ~/.cargo, brew leaves)
#   9. Git config + SSH config           (PRIVATE; quarantined separately)
#  10. Per-repo full git log             so we have provenance even if push fails
#
# What it EXCLUDES:  Library/Mail, Photos, Music, Movies, iCloud caches,
#                    node_modules, .venv, __pycache__, .DS_Store, browser caches.
#
# Output:
#   Local file:   ~/Desktop/miniapple_dump_<DATE>.tgz
#   Local file:   ~/Desktop/miniapple_dump_<DATE>_PRIVATE.tgz   (keys/configs)
#   Pushed to:    seratonin via `tailscale file cp` (taildrop)
#                 → on Windows: arrives at the tailscale "file inbox",
#                   collect with:   tailscale file get D:/miniapple_archive/
set -euo pipefail

DATE="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${HOME}/Desktop"
PUBLIC_TGZ="${OUT_DIR}/miniapple_dump_${DATE}.tgz"
PRIVATE_TGZ="${OUT_DIR}/miniapple_dump_${DATE}_PRIVATE.tgz"
MANIFEST="${OUT_DIR}/miniapple_manifest_${DATE}"
mkdir -p "${MANIFEST}"

echo "=== miniapple extraction — running locally on $(hostname) ==="
echo "  date:      $(date -Iseconds)"
echo "  user:      $(whoami)"
echo "  home:      ${HOME}"
echo "  output:    ${PUBLIC_TGZ}"
echo

# ---------- 1. inventory ----------
echo "[1/4] inventory"

{
  echo "host=$(hostname)"
  echo "user=$(whoami)"
  echo "os=$(sw_vers -productVersion 2>/dev/null || uname -a)"
  echo "shell=${SHELL}"
  echo "uptime=$(uptime)"
  echo "tailscale_ip=$(tailscale ip -4 2>/dev/null || echo n/a)"
} > "${MANIFEST}/host.txt"

# every git repo under $HOME (skip system caches)
find "${HOME}" -type d -name .git \
  -not -path "*/Library/*" \
  -not -path "*/node_modules/*" \
  -not -path "*/.venv/*" \
  -not -path "*/.npm/*" \
  -not -path "*/.cargo/registry/*" \
  -not -path "*/Trash/*" \
  2>/dev/null | sed 's,/.git$,,' > "${MANIFEST}/git_repos.txt"
echo "  git repos:    $(wc -l < ${MANIFEST}/git_repos.txt)"

# kimi authorship trail
grep -ril --include='*.md' --include='*.txt' --include='*.py' --include='*.json' \
  -e kimi -e moonshot -e nous-portal -e NOUS_API_KEY \
  "${HOME}/dev" "${HOME}/Projects" "${HOME}/code" "${HOME}/work" "${HOME}/src" \
  "${HOME}/.mercury" "${HOME}/.hermes" 2>/dev/null \
  > "${MANIFEST}/kimi_touches.txt" || true
echo "  kimi files:   $(wc -l < ${MANIFEST}/kimi_touches.txt)"

# brew + npm + cargo leaves so we can reproduce
{
  echo "=== brew leaves ==="
  brew leaves 2>/dev/null || echo "(brew not present)"
  echo
  echo "=== brew tap ==="
  brew tap 2>/dev/null
  echo
  echo "=== npm -g list ==="
  npm list -g --depth=0 2>/dev/null || echo "(npm not present)"
  echo
  echo "=== cargo install --list ==="
  cargo install --list 2>/dev/null || echo "(cargo not present)"
  echo
  echo "=== pip freeze (system) ==="
  pip3 freeze 2>/dev/null | head -200 || true
  echo
  echo "=== uv tool list ==="
  uv tool list 2>/dev/null || echo "(uv not present)"
  echo
  echo "=== ollama list ==="
  ollama list 2>/dev/null || echo "(ollama not present)"
} > "${MANIFEST}/installed_tools.txt"

# per-repo git log (commit-by-commit provenance)
mkdir -p "${MANIFEST}/gitlogs"
while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  slug="$(echo "$repo" | sed 's,[/ ],_,g')"
  ( cd "$repo" && git log --all --pretty='%h %ai %an <%ae> %s' 2>/dev/null ) \
    > "${MANIFEST}/gitlogs/${slug}.log" || true
done < "${MANIFEST}/git_repos.txt"

# ---------- 2. push every git repo to its remote ----------
echo "[2/4] git push --all (capture Kimi-authored commits even if extraction fails later)"
while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  ( cd "$repo" 2>/dev/null
    if git remote 2>/dev/null | grep -q .; then
      echo "  -> ${repo}"
      git push --all 2>&1 | tail -3 | sed 's/^/     /'
      git push --tags 2>&1 | tail -2 | sed 's/^/     /'
    fi
  ) || true
done < "${MANIFEST}/git_repos.txt"

# ---------- 3. tar streams ----------
echo "[3/4] building tar archives"

# the public-ish archive (everything but secrets)
EXCLUDES=(
  --exclude='*/node_modules/*'
  --exclude='*/.venv/*'
  --exclude='*/__pycache__/*'
  --exclude='*/.DS_Store'
  --exclude='*.pyc'
  --exclude='*/.cache/*'
  --exclude='*/Caches/*'
  --exclude='Library/Mail/*'
  --exclude='Library/Photos/*'
  --exclude='Library/Music/*'
  --exclude='Library/Mobile Documents/*'
  --exclude='Pictures/*'
  --exclude='Music/*'
  --exclude='Movies/*'
  --exclude='*.photoslibrary/*'
)

PUBLIC_PATHS=()
for p in .mercury .hermes .claude .local .cargo .config dev Projects code work src \
         "Library/LaunchAgents" \
         "Library/Application Support/Code" \
         "Library/Application Support/Cursor" \
         "Library/Application Support/Ollama" ; do
  [ -e "${HOME}/${p}" ] && PUBLIC_PATHS+=("${p}")
done
PUBLIC_PATHS+=("${MANIFEST#${HOME}/}")  # include manifest itself

echo "  paths in archive:"
printf '    %s\n' "${PUBLIC_PATHS[@]}"

(
  cd "${HOME}"
  tar "${EXCLUDES[@]}" -czf "${PUBLIC_TGZ}" "${PUBLIC_PATHS[@]}"
)
echo "  -> ${PUBLIC_TGZ}  ($(du -h "${PUBLIC_TGZ}" | awk '{print $1}'))"

# private archive — keys, ssh config, gitconfig — DO NOT commit to public repo
PRIV_PATHS=()
for p in .ssh .gnupg .gitconfig .netrc .aws .config/gcloud .docker; do
  [ -e "${HOME}/${p}" ] && PRIV_PATHS+=("${p}")
done
if [ ${#PRIV_PATHS[@]} -gt 0 ]; then
  ( cd "${HOME}" && tar -czf "${PRIVATE_TGZ}" "${PRIV_PATHS[@]}" )
  echo "  -> ${PRIVATE_TGZ}  ($(du -h "${PRIVATE_TGZ}" | awk '{print $1}'))   PRIVATE"
fi

# shell history rolled into the public archive already via .config/.zsh_sessions
# but bash_history / zsh_history live at top level — bundle separately to be safe
HIST_TGZ="${OUT_DIR}/miniapple_history_${DATE}.tgz"
( cd "${HOME}" && tar -czf "${HIST_TGZ}" \
    .zsh_history .zsh_sessions .bash_history .python_history .lesshst .viminfo \
    2>/dev/null || true )
[ -s "${HIST_TGZ}" ] && echo "  -> ${HIST_TGZ}  ($(du -h "${HIST_TGZ}" | awk '{print $1}'))"

# ---------- 4. push to seratonin via taildrop ----------
echo "[4/4] taildrop -> seratonin"
if command -v tailscale >/dev/null; then
  for f in "${PUBLIC_TGZ}" "${PRIVATE_TGZ}" "${HIST_TGZ}"; do
    [ -f "$f" ] || continue
    echo "  cp $(basename "$f")"
    tailscale file cp "$f" seratonin: || echo "    (taildrop failed — file is still at $f)"
  done
else
  echo "  (tailscale CLI not on PATH — files are on Desktop, drag them via Parsec)"
fi

echo
echo "=== DONE ==="
echo "files on this Mac:  ${OUT_DIR}/miniapple_dump_${DATE}*.tgz"
echo "manifest:           ${MANIFEST}"
echo
echo "On seratonin (Windows), collect the taildrops with:"
echo "  tailscale file get D:/miniapple_archive/"
echo
echo "Then run authorship isolation:"
echo "  bash D:/mercury/scripts/isolate_kimi_authorship.sh \\"
echo "    --archive D:/miniapple_archive --out D:/mercury/kimi_artifacts"