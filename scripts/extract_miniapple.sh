#!/usr/bin/env bash
# extract_miniapple.sh — pull every non-default-Apple file off miniapple
# over Tailscale SSH, plus push every git repo to its remote.
#
# Customized for soumitlahiri@miniapple → seratonin (Windows / git-bash).
# Default destination: D:/miniapple_archive/<DATE>/   (override with --dest)
#
# What it captures:
#   1. Mercury / Hermes runtime state    (~/.mercury, ~/.hermes)
#   2. Claude Code state if any          (~/.claude, ~/Library/Application Support/Claude)
#   3. Shell history + sessions          (~/.zsh_history, ~/.zsh_sessions, ~/.bash_history)
#   4. Dev trees                         (~/dev, ~/Projects, ~/code, ~/work, ~/src)
#   5. Kimi-dispatch artifacts           (any *.md/*.txt under dev trees referencing kimi)
#   6. User-installed LaunchAgents       (~/Library/LaunchAgents)
#   7. Non-Apple Application Support     (Code, Cursor, JetBrains, Ollama, etc.)
#   8. Brew + uv + pip + cargo state     (~/.local, ~/.cargo, ~/Library/Caches/pip, etc.)
#   9. SSH config + git config           (~/.ssh/config, ~/.gitconfig — REDACTED before commit)
#  10. Every git repo's commit log       (so we know what Kimi authored, even if not pushed)
#
# What it explicitly EXCLUDES (saves disk + privacy):
#   - ~/Library/Mail, ~/Library/Photos, ~/Library/Music, ~/Library/Movies
#   - ~/Pictures, ~/Music, ~/Movies (default Apple folders)
#   - iCloud caches, Photos.photoslibrary, MobileSync backups
#   - node_modules, .venv, __pycache__, .DS_Store, *.pyc
#   - Browser caches and cookies
#
# Usage:
#   bash D:/mercury/scripts/extract_miniapple.sh                    # default dest
#   bash D:/mercury/scripts/extract_miniapple.sh --dest E:/backup   # portable drive
#   bash D:/mercury/scripts/extract_miniapple.sh --skip-git-push    # skip pushing repos
#   bash D:/mercury/scripts/extract_miniapple.sh --dry-run          # show what would happen
set -euo pipefail

# ---- defaults (edit here if your setup changes) ----
REMOTE_USER="soumitlahiri"
REMOTE_HOST="miniapple"
SSH_CMD=(tailscale ssh)                # change to (ssh) if using Option B
DATE="$(date +%Y%m%d_%H%M%S)"
DEST="D:/miniapple_archive/${DATE}"
SKIP_GIT_PUSH=0
DRY_RUN=0

# ---- arg parse ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --user) REMOTE_USER="$2"; shift 2 ;;
    --host) REMOTE_HOST="$2"; shift 2 ;;
    --plain-ssh) SSH_CMD=(ssh); shift ;;
    --skip-git-push) SKIP_GIT_PUSH=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '1,40p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REMOTE="${REMOTE_USER}@${REMOTE_HOST}"
mkdir -p "${DEST}"
LOG="${DEST}/extract.log"
exec > >(tee -a "${LOG}") 2>&1

echo "=== miniapple extraction $(date -Iseconds) ==="
echo "remote: ${REMOTE}"
echo "dest:   ${DEST}"
echo "ssh:    ${SSH_CMD[*]}"

# ---- 0. preflight ----
if ! "${SSH_CMD[@]}" "${REMOTE}" 'echo PING' >/dev/null 2>&1; then
  echo "FATAL: cannot reach ${REMOTE} via ${SSH_CMD[*]}." >&2
  echo "See D:/mercury/scripts/miniapple_preflight.md" >&2
  exit 1
fi
echo "[ok] reachable"

# ---- 1. inventory pass (cheap, builds a manifest) ----
echo
echo "=== inventory (writes ${DEST}/manifest/) ==="
mkdir -p "${DEST}/manifest"

"${SSH_CMD[@]}" "${REMOTE}" 'bash -lc "
  set -e
  echo HOST=\$(hostname); echo USER=\$(whoami); echo HOME=\$HOME
  echo OS=\$(sw_vers -productVersion 2>/dev/null || uname -a)
  echo SHELL=\$SHELL
  echo NOUS_API_KEY_set=\$([ -n \"\${NOUS_API_KEY:-}\" ] && echo yes || echo no)
"' > "${DEST}/manifest/host.txt"

# every git repo under $HOME (excluding Library/Caches/etc)
"${SSH_CMD[@]}" "${REMOTE}" 'bash -lc "
  find \$HOME -type d -name .git \
    -not -path \"*/Library/*\" \
    -not -path \"*/node_modules/*\" \
    -not -path \"*/.venv/*\" \
    -not -path \"*/.npm/*\" \
    -not -path \"*/.cargo/registry/*\" \
    -not -path \"*/Trash/*\" \
    2>/dev/null \
    | sed \"s,/.git$,,\"
"' > "${DEST}/manifest/git_repos.txt"

GIT_REPO_COUNT=$(wc -l < "${DEST}/manifest/git_repos.txt" | tr -d ' ')
echo "[ok] found ${GIT_REPO_COUNT} git repos"

# every kimi-related file (proves what Kimi touched)
"${SSH_CMD[@]}" "${REMOTE}" 'bash -lc "
  set +e
  grep -ril --include=*.md --include=*.txt --include=*.py --include=*.json \
    -e kimi -e moonshot -e nous-portal -e NOUS_API_KEY \
    \$HOME/dev \$HOME/Projects \$HOME/code \$HOME/work \$HOME/src \
    \$HOME/.mercury \$HOME/.hermes 2>/dev/null
"' > "${DEST}/manifest/kimi_touches.txt" || true

KIMI_COUNT=$(wc -l < "${DEST}/manifest/kimi_touches.txt" | tr -d ' ')
echo "[ok] found ${KIMI_COUNT} Kimi-referencing files"

# every git log entry from every repo (so we have a paper trail even if push fails)
mkdir -p "${DEST}/manifest/gitlogs"
while IFS= read -r repo; do
  [ -z "$repo" ] && continue
  slug="$(echo "$repo" | sed 's,[/ ],_,g')"
  "${SSH_CMD[@]}" "${REMOTE}" "bash -lc 'cd \"$repo\" && git log --all --pretty=\"%h %ai %an <%ae> %s\" 2>/dev/null'" \
    > "${DEST}/manifest/gitlogs/${slug}.log" || true
done < "${DEST}/manifest/git_repos.txt"
echo "[ok] git logs captured"

# ---- 2. tar streams (the actual data) ----
# Each stream is gzipped on the Mac and dropped as a single file here.
# Extract on demand with: tar -tzf <archive>.tgz | head
echo
echo "=== tar streams ==="

stream_tar () {
  local label="$1" remote_path="$2" extra_excludes="${3:-}"
  local out="${DEST}/${label}.tgz"
  if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "[dry-run] would tar ${remote_path} -> ${out}"
    return
  fi
  echo "[stream] ${label} <- ${remote_path}"
  # macOS bsdtar, --exclude works for path globs
  "${SSH_CMD[@]}" "${REMOTE}" "bash -lc '
    set -e
    cd \$HOME
    if [ ! -e \"${remote_path}\" ]; then
      echo \"  (skip — ${remote_path} does not exist on remote)\" >&2
      exit 0
    fi
    tar \
      --exclude=\"*/node_modules/*\" \
      --exclude=\"*/.venv/*\" \
      --exclude=\"*/__pycache__/*\" \
      --exclude=\"*/.DS_Store\" \
      --exclude=\"*.pyc\" \
      --exclude=\"*/.cache/*\" \
      --exclude=\"*/Caches/*\" \
      ${extra_excludes} \
      -czf - \"${remote_path}\" 2>/dev/null
  '" > "${out}"
  size=$(du -h "${out}" 2>/dev/null | awk '{print $1}')
  echo "    -> ${out} (${size})"
}

stream_tar "01_mercury_state"   ".mercury"
stream_tar "02_hermes_state"    ".hermes"
stream_tar "03_claude_state"    ".claude"
stream_tar "04_appsupport_claude" "Library/Application\\ Support/Claude"
stream_tar "05_appsupport_code"   "Library/Application\\ Support/Code"
stream_tar "06_appsupport_cursor" "Library/Application\\ Support/Cursor"
stream_tar "07_launch_agents"   "Library/LaunchAgents"
stream_tar "08_local_bin"       ".local"
stream_tar "09_cargo"           ".cargo" "--exclude=\"*/registry/*\""
stream_tar "10_dev"             "dev"
stream_tar "11_projects"        "Projects"
stream_tar "12_code"            "code"
stream_tar "13_work"            "work"
stream_tar "14_src"             "src"
stream_tar "15_documents_dev"   "Documents" "--exclude=\"*/Photos*/*\" --exclude=\"*/Music*/*\""

# Shell history — separate, small, lossless
echo "[stream] shell history"
"${SSH_CMD[@]}" "${REMOTE}" 'bash -lc "
  for f in .zsh_history .bash_history .zsh_sessions; do
    [ -e \$HOME/\$f ] && tar -czf - -C \$HOME \$f
  done
"' > "${DEST}/16_shell_history.tgz"

# SSH + git config (KEEP PRIVATE — never commit to public repo)
echo "[stream] config files (private)"
"${SSH_CMD[@]}" "${REMOTE}" 'bash -lc "
  tar -czf - -C \$HOME .gitconfig .ssh/config 2>/dev/null || true
"' > "${DEST}/17_configs_PRIVATE.tgz"

# ---- 3. push every git repo to its remote (so Kimi-authored commits land) ----
if [[ ${SKIP_GIT_PUSH} -eq 0 ]]; then
  echo
  echo "=== git push --all (per repo) ==="
  while IFS= read -r repo; do
    [ -z "$repo" ] && continue
    if [[ ${DRY_RUN} -eq 1 ]]; then
      echo "[dry-run] would push: $repo"
      continue
    fi
    echo "[push] $repo"
    "${SSH_CMD[@]}" "${REMOTE}" "bash -lc '
      cd \"$repo\" 2>/dev/null || exit 0
      # only push if there is a remote
      if git remote 2>/dev/null | grep -q .; then
        git push --all 2>&1 | tail -5
        git push --tags 2>&1 | tail -3
      else
        echo \"  (no remote)\"
      fi
    '" || true
  done < "${DEST}/manifest/git_repos.txt"
fi

# ---- 4. summary ----
echo
echo "=== summary ==="
echo "destination: ${DEST}"
du -sh "${DEST}"/*.tgz 2>/dev/null | sort -k1 -h
echo
echo "manifest files:"
ls -la "${DEST}/manifest/"
echo
echo "DONE. Next steps:"
echo "  1. Review ${DEST}/manifest/kimi_touches.txt — that's your Kimi authorship paper trail"
echo "  2. Review ${DEST}/manifest/gitlogs/  — commit-by-commit history per repo"
echo "  3. ${DEST}/17_configs_PRIVATE.tgz contains keys/SSH config — DO NOT commit"
echo "  4. When portable drive arrives, move ${DEST} there and update D:/mercury/scripts/extract_miniapple.sh DEST default"
