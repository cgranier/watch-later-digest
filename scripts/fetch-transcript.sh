#!/usr/bin/env bash
# fetch-transcript.sh -- metadata, description and auto-captions for one public video.
#
#   scripts/fetch-transcript.sh VIDEO_ID OUT_DIR
#
# Writes into OUT_DIR:
#   <id>.meta.json     title, channel, upload_date, duration, view_count, webpage_url
#   <id>.description   full description (may be empty: Shorts do that)
#   <id>.txt           deduplicated caption prose, or the no-captions marker
#   <id>.timed.txt     the same with M:SS prefixes (segments are read from this)
#
# Idempotent: if <id>.txt exists the fetch is skipped and "cached" is printed.
# Uses the public watch URL; no cookies, no login. Needs yt-dlp on PATH (or
# YTDLP=/path/to/yt-dlp) and python3. Exit 0 on success (including the
# no-captions case, which is a normal outcome), 1 on a failed fetch.
set -uo pipefail
ID="${1:?video id}"; OUT="${2:?out dir}"
YTDLP="${YTDLP:-yt-dlp}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARK="[no auto-generated subtitles available]"
mkdir -p "$OUT"

case "$ID" in *[!A-Za-z0-9_-]*|"") echo "fetch-transcript: bad id '$ID'" >&2; exit 1;; esac
if [ -s "$OUT/$ID.txt" ] && [ -s "$OUT/$ID.meta.json" ]; then
    echo "fetch-transcript | $ID | cached"; exit 0
fi

# --print implies --simulate unless --no-simulate; we need the subs written.
# Languages are exact ("en", "en-orig"), never a wildcard: "en.*" also matches
# every auto-translated track and one video becomes forty requests and a 429.
# A subtitle error is not a fetch failure: metadata and description still land.
"$YTDLP" --no-simulate --skip-download --no-warnings --quiet \
    --write-auto-sub --write-subs --sub-lang "en,en-orig" --sub-format vtt \
    --write-description \
    --print "%(.{id,title,channel,upload_date,duration,view_count,webpage_url})j" \
    -o "$OUT/%(id)s.%(ext)s" \
    "https://www.youtube.com/watch?v=$ID" > "$OUT/$ID.meta.json" 2> "$OUT/$ID.err"
rc=$?
if [ ! -s "$OUT/$ID.meta.json" ]; then
    echo "fetch-transcript | $ID | FAILED: $(tail -1 "$OUT/$ID.err" 2>/dev/null)"; rm -f "$OUT/$ID.meta.json"; exit 1
fi
[ $rc -ne 0 ] && echo "fetch-transcript | $ID | warning (non-fatal): $(tail -1 "$OUT/$ID.err")" >&2
rm -f "$OUT/$ID.err"
[ -f "$OUT/$ID.description" ] || : > "$OUT/$ID.description"

# prefer manual English subs, then auto; yt-dlp names them <id>.<lang>.vtt
VTT="$(ls -1 "$OUT/$ID".en.vtt "$OUT/$ID".en-orig.vtt "$OUT/$ID".en*.vtt 2>/dev/null | head -1 || true)"
if [ -n "$VTT" ] && [ -s "$VTT" ]; then
    python3 "$HERE/vtt2txt.py" "$VTT" "$OUT/$ID" >/dev/null \
        || { printf '%s\n' "$MARK" > "$OUT/$ID.txt"; : > "$OUT/$ID.timed.txt"; }
else
    printf '%s\n' "$MARK" > "$OUT/$ID.txt"; : > "$OUT/$ID.timed.txt"
fi

python3 - "$OUT/$ID" <<'PY'
import json, sys
from pathlib import Path
b = Path(sys.argv[1]); m = json.loads(Path(f"{b}.meta.json").read_text())
txt = Path(f"{b}.txt").read_text(); desc = Path(f"{b}.description").read_text()
cap = "none" if txt.startswith("[no auto-generated") else f"{len(txt)}c"
print(f"fetch-transcript | {m.get('id')} | {m.get('title','')[:70]} | {m.get('channel','')} | "
      f"{m.get('upload_date','')} | {m.get('duration','?')}s | desc={len(desc)}c | captions={cap}")
PY
