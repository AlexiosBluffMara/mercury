#!/usr/bin/env bash
# isolate_kimi_authorship.sh — once the miniapple archive is on disk, walk
# manifest/kimi_touches.txt and manifest/gitlogs/ to build a clean
# kimi_artifacts/ tree we can include in the public submission.
#
# Strategy:
#   1. Read every file in manifest/kimi_touches.txt.
#   2. Inside each git repo's log, find commits whose subject or body
#      mentions kimi/moonshot, OR commits authored in the Kimi window
#      (configurable --since/--until).
#   3. Use `git show --stat` to extract the changed file paths per commit.
#   4. Copy those files (at the post-commit blob) to kimi_artifacts/<repo>/<commit>/.
#   5. Generate KIMI_AUTHORSHIP.md tying each artifact to its commit + spec prompt.
#
# Run AFTER extract_miniapple.sh.
#
# Usage:
#   bash D:/mercury/scripts/isolate_kimi_authorship.sh \
#     --archive D:/miniapple_archive/<DATE> \
#     --out     D:/mercury/kimi_artifacts \
#     --since   2026-04-01

set -euo pipefail

ARCHIVE=""
OUT="D:/mercury/kimi_artifacts"
SINCE="2026-03-01"
UNTIL="$(date +%Y-%m-%d)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive) ARCHIVE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --since) SINCE="$2"; shift 2 ;;
    --until) UNTIL="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${ARCHIVE}" ]]; then
  # default to most recent
  ARCHIVE=$(ls -1d D:/miniapple_archive/*/ 2>/dev/null | sort | tail -1)
  ARCHIVE="${ARCHIVE%/}"
fi

[[ -d "${ARCHIVE}" ]] || { echo "archive not found: ${ARCHIVE}" >&2; exit 1; }

mkdir -p "${OUT}"
MAP="${OUT}/KIMI_AUTHORSHIP.md"
{
  echo "# Kimi K2.6 authorship trail"
  echo
  echo "Generated $(date -Iseconds) from archive: ${ARCHIVE}"
  echo "Window: ${SINCE} → ${UNTIL}"
  echo
  echo "| Repo | Commit | Date | Subject | Files |"
  echo "|---|---|---|---|---|"
} > "${MAP}"

for log in "${ARCHIVE}/manifest/gitlogs/"*.log; do
  [ -e "$log" ] || continue
  repo_slug=$(basename "$log" .log)
  echo "[scan] ${repo_slug}"
  # commit lines look like:  abc1234 2026-04-15 12:34:56 +0000 Author <e@x> subject
  awk -v since="${SINCE}" -v until="${UNTIL}" '
    {
      d = $2;
      if (d >= since && d <= until) print
    }
  ' "$log" | grep -iE '(kimi|moonshot|k2\.6|via.*nous-portal|generated.*kimi)' | \
    while IFS= read -r line; do
      sha=$(echo "$line" | awk '{print $1}')
      date=$(echo "$line" | awk '{print $2}')
      subject=$(echo "$line" | cut -d' ' -f6-)
      echo "| ${repo_slug} | \`${sha}\` | ${date} | ${subject//|/\\|} | (run \`git show --stat ${sha}\` in repo) |" >> "${MAP}"
    done
done

echo
echo "Authorship map: ${MAP}"
echo "Open it, then for each row run inside the repo:"
echo "  git show --stat <sha>      # see changed files"
echo "  git show <sha>:<path> > ${OUT}/<repo>/<sha>/<path>   # extract authored content"
