#!/usr/bin/env bash
# live-fetch.sh -- one real fetch through yt-dlp, into a temp dir. Needs network.
#
#   tests/live-fetch.sh [VIDEO_ID]        default: a short, old, captioned public video
set -u
ID="${1:-jNQXAC9IVRw}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
D="$(mktemp -d)"
trap 'rm -rf "$D"' EXIT
"$HERE/scripts/fetch-transcript.sh" "$ID" "$D" || { echo "live-fetch: fetch failed"; exit 1; }
for f in meta.json description txt timed.txt; do
    [ -f "$D/$ID.$f" ] || { echo "live-fetch: missing $ID.$f"; exit 1; }
done
echo "--- meta";  cat "$D/$ID.meta.json"
echo "--- text (first 200 chars)"; head -c 200 "$D/$ID.txt"; echo
echo "--- second call must be a cache hit"
"$HERE/scripts/fetch-transcript.sh" "$ID" "$D" | grep -q cached && echo "live-fetch: ok" || { echo "live-fetch: no cache hit"; exit 1; }
