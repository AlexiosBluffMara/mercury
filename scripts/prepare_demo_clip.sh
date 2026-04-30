#!/usr/bin/env bash
# prepare_demo_clip.sh — strip the audio track off any demo clip before
# scanning. The Cortex pipeline's audio-transcription stage tries to
# install `whisperx` on first call, and that install currently fails on
# Python 3.13 due to ctranslate2 wheel ABI incompatibility. Until we patch
# whisperx as truly optional, scanning a silent clip avoids the path.
#
# Usage:
#   bash D:/mercury/scripts/prepare_demo_clip.sh <input.mp4>
# Outputs <input>_silent.mp4 next to the original.
set -euo pipefail

IN="${1:-D:/cortex/assets/demo_clip_20s.mp4}"
OUT="${IN%.*}_silent.${IN##*.}"
ffmpeg -y -i "$IN" -an -c:v copy "$OUT"
ls -lh "$OUT"
echo "Done. Now submit it: drag $OUT into the WebUI at http://127.0.0.1:8765/"
