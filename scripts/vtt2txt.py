#!/usr/bin/env python3
"""
vtt2txt.py -- turn a YouTube auto-caption WebVTT file into two plain-text files.

    vtt2txt.py IN.vtt OUT_BASE

Writes OUT_BASE.txt (deduplicated prose, one caption line per line) and
OUT_BASE.timed.txt (the same lines prefixed with their start time as M:SS or
H:MM:SS, which is what segment ranges are read from).

YouTube's auto-captions are a rolling window: each cue repeats the previous
line and adds one. Naive concatenation doubles every line. This keeps a line
only when it differs from the last line kept. Inline <c> tags, inline
timestamps and positioning attributes are stripped.

Prints one line: "vtt2txt | lines=N chars=N first=M:SS last=M:SS". Exit 1 if the
input is missing or has no cues.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

CUE_RE = re.compile(r"^(\d{1,2}:)?\d{2}:\d{2}\.\d{3}\s+-->\s+((\d{1,2}:)?\d{2}:\d{2}\.\d{3})")
TAG_RE = re.compile(r"<[^>]+>")


def to_seconds(ts: str) -> int:
    parts = ts.split(".")[0].split(":")
    parts = [int(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def fmt(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def clean(line: str) -> str:
    line = TAG_RE.sub("", line)
    line = html.unescape(line).replace("​", "")
    return re.sub(r"\s+", " ", line).strip()


def parse(text: str) -> list[tuple[int, str]]:
    cues: list[tuple[int, str]] = []
    start = None
    for raw in text.splitlines():
        m = CUE_RE.match(raw.strip())
        if m:
            start = to_seconds(raw.strip().split()[0])
            continue
        if start is None or not raw.strip() or raw.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            if not raw.strip():
                start = None
            continue
        line = clean(raw)
        if line:
            cues.append((start, line))
    return cues


def dedupe(cues: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    last = ""
    for t, line in cues:
        if line == last:
            continue
        # a cue that is the previous line plus a suffix: keep only the suffix
        if last and line.startswith(last + " "):
            line = line[len(last) + 1:]
        out.append((t, line))
        last = line
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src, base = Path(argv[1]), Path(argv[2])
    if not src.is_file():
        print(f"vtt2txt: no such file {src}", file=sys.stderr)
        return 1
    cues = dedupe(parse(src.read_text(encoding="utf-8", errors="replace")))
    if not cues:
        print(f"vtt2txt: no cues in {src}", file=sys.stderr)
        return 1
    plain = "\n".join(line for _, line in cues) + "\n"
    timed = "\n".join(f"{fmt(t)}  {line}" for t, line in cues) + "\n"
    base.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{base}.txt").write_text(plain, encoding="utf-8")
    Path(f"{base}.timed.txt").write_text(timed, encoding="utf-8")
    print(f"vtt2txt | lines={len(cues)} chars={len(plain)} first={fmt(cues[0][0])} last={fmt(cues[-1][0])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
