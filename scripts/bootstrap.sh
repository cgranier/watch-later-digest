#!/usr/bin/env bash
# bootstrap.sh -- make sure the skill's dependencies exist; fast when they do.
#
#   scripts/bootstrap.sh [STATE_DIR]
#
# The first line of every run. On an agent computer that wipes itself on
# update, this is what puts yt-dlp back. STATE_DIR defaults to ./state next to
# the skill; on Grok Bot use /workspace/watch-later-digest/state (durable).
set -e
STATE="${1:-${WLD_STATE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/state}}"
command -v python3 >/dev/null || { echo "bootstrap: python3 missing" >&2; exit 1; }
if ! command -v yt-dlp >/dev/null 2>&1; then
    python3 -m pip install --user -q yt-dlp 2>/dev/null || python3 -m pip install -q --break-system-packages yt-dlp
    export PATH="$HOME/.local/bin:$PATH"
fi
command -v yt-dlp >/dev/null || { echo "bootstrap: yt-dlp still missing after install" >&2; exit 1; }
mkdir -p "$STATE/runs" "$STATE/transcripts"
echo "bootstrap | yt-dlp $(yt-dlp --version) | state $STATE"
