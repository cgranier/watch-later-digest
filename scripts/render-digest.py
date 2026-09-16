#!/usr/bin/env python3
"""
render-digest.py -- validate the rows the bot wrote, do the arithmetic, order them,
and emit the digest as Markdown and static HTML.

    render-digest.py --rows ROWS.md --profile PROFILE.md --out-dir DIR
                     [--intro INTRO.md] [--remaining N] [--list-note "moved 15 to Digested"]
                     [--unavailable "id title"]... [--title "Watch Later digest"] [--check]

ROWS.md is what the bot writes, one block per video (references/digest.md):

    ## <title>
    id: <11-char video id>
    channel: <channel>
    published: <YYYY-MM-DD>
    duration: <H:MM:SS or M:SS>
    lens: <lens name or general>
    call: <watch | skim | summary | skip>
    segments:                       # required for skim, forbidden otherwise
      - "M:SS-M:SS  label"

    **TL;DR.** ...
    **Key takeaways**
    - ...
    **Watch / skip.** ...
    **Lens hint.** ...

Every rule the row must satisfy is enforced here, and a failure names the row
and the rule; nothing is silently dropped. Kept time is full duration for
watch, the sum of segments for skim, zero for summary and skip. Rows are
ordered watch, skim, summary, skip, then by minutes saved descending, and
numbered in that order (the bot does not number them).

Exit 0 rendered, 1 validation failed (nothing written), 2 bad invocation.
--check validates and prints the headline only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALLS = ("watch", "skim", "summary", "skip")
ORDER = {c: i for i, c in enumerate(CALLS)}
TS = r"\d{1,2}:\d{2}(?::\d{2})?"
SEG_RE = re.compile(rf'^\s*-\s*"?({TS})\s*[-–—]\s*({TS})\s+(.*?)"?\s*$')
KV_RE = re.compile(r"^([a-z_]+):\s*(.*?)\s*$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
HEADING = "**Watch / skip.**"


def to_seconds(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def fmt_hm(sec: int) -> str:
    h, m = divmod(round(sec / 60), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def fmt_clock(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_rows(text: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    blocks = re.split(r"(?m)^## ", text)
    for block in blocks[1:]:
        lines = block.splitlines()
        row = {"title": lines[0].strip(), "segments": [], "takeaways": [], "tldr": "", "call_text": "",
               "lens_hint": "", "id": "", "channel": "", "published": "", "duration": 0, "lens": "general", "call": ""}
        label = row["title"][:60]
        body_start = None
        i = 1
        in_segments = False
        while i < len(lines):
            ln = lines[i]
            if not ln.strip():
                body_start = i + 1
                break
            m = KV_RE.match(ln)
            if m and not ln.startswith(" "):
                in_segments = m.group(1) == "segments"
                k, v = m.group(1), m.group(2)
                if k == "duration":
                    try:
                        row["duration"] = to_seconds(v)
                    except ValueError:
                        errors.append(f"{label}: duration '{v}' is not H:MM:SS or M:SS")
                elif k != "segments":
                    row[k] = v
            elif in_segments:
                sm = SEG_RE.match(ln)
                if sm:
                    row["segments"].append({"start": to_seconds(sm.group(1)), "end": to_seconds(sm.group(2)),
                                            "label": sm.group(3).strip()})
                else:
                    errors.append(f"{label}: segment line not 'M:SS-M:SS  label': {ln.strip()!r}")
            else:
                errors.append(f"{label}: unexpected header line {ln.strip()!r}")
            i += 1
        body = "\n".join(lines[body_start:]) if body_start else ""
        row["body"] = body.strip()
        m = re.search(r"\*\*TL;DR\.\*\*\s*(.+)", body)
        row["tldr"] = m.group(1).strip() if m else ""
        m = re.search(r"\*\*Key takeaways\*\*\s*\n((?:\s*-\s+.*\n?)+)", body)
        row["takeaways"] = [t.strip()[2:].strip() for t in m.group(1).strip().splitlines()] if m else []
        m = re.search(re.escape(HEADING) + r"\s*(.+)", body)
        row["call_text"] = m.group(1).strip() if m else ""
        m = re.search(r"\*\*Lens hint\.\*\*\s*(.+)", body)
        row["lens_hint"] = m.group(1).strip() if m else ""

        # --- the rules ---
        if not ID_RE.match(row["id"]):
            errors.append(f"{label}: id '{row['id']}' is not an 11-character video id")
        if row["duration"] <= 0:
            errors.append(f"{label}: duration missing or zero")
        if row["call"] not in CALLS:
            errors.append(f"{label}: call must be one of {CALLS}, got '{row['call']}'")
        if HEADING not in body:
            errors.append(f"{label}: the literal heading {HEADING} is missing (T5)")
        if not row["tldr"]:
            errors.append(f"{label}: no **TL;DR.** line")
        if not row["takeaways"]:
            errors.append(f"{label}: no **Key takeaways** bullets")
        if row["call"] == "skim" and not row["segments"]:
            errors.append(f"{label}: call is skim but no segments: list (T6)")
        if row["call"] != "skim" and row["segments"]:
            errors.append(f"{label}: segments: given but call is {row['call']}; segments belong to skim only")
        for s in row["segments"]:
            if not (0 <= s["start"] < s["end"] <= row["duration"]):
                errors.append(f"{label}: segment {fmt_clock(s['start'])}-{fmt_clock(s['end'])} "
                              f"is not inside 0..{fmt_clock(row['duration'])} with start < end (T6)")
            if not s["label"]:
                errors.append(f"{label}: segment without a label")
        kept = row["duration"] if row["call"] == "watch" else sum(s["end"] - s["start"] for s in row["segments"])
        row["kept"] = min(kept, row["duration"]) if row["duration"] else 0
        row["saved"] = row["duration"] - row["kept"]
        rows.append(row)
    ids = [r["id"] for r in rows]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"video id {dup} appears in more than one row")
    if not rows:
        errors.append("no rows found (a row starts with '## ')")
    return rows, errors


def load_profile(path: Path) -> dict:
    out = subprocess.run([sys.executable, str(HERE / "check-profile.py"), str(path), "--json"],
                         capture_output=True, text=True)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        print(f"render-digest: profile at {path} unreadable; using playback_rate 1.5", file=sys.stderr)
        return {"settings": {"playback_rate": "1.5", "owner": ""}}


def md_digest(rows, headline, intro, footer, title, stamp) -> str:
    out = [f"# {title}", "", f"*{stamp}*", "", headline["md"], ""]
    if intro:
        out += [intro.strip(), ""]
    group = None
    for r in rows:
        if r["call"] != group:
            group = r["call"]
            out += [f"### {group.capitalize()}", ""]
        kept = (f"{fmt_clock(r['kept'])} of {fmt_clock(r['duration'])}" if r["call"] in ("watch", "skim")
                else fmt_clock(r["duration"]))
        out += [f"## {r['n']}. {r['title']}",
                f"{r['channel']} · {r['published']} · {kept} · lens: {r['lens']} · "
                f"[open](https://www.youtube.com/watch?v={r['id']})", ""]
        out += [f"**TL;DR.** {r['tldr']}", "", "**Key takeaways**"] + [f"- {t}" for t in r["takeaways"]] + [""]
        out += [f"{HEADING} {r['call_text']}"]
        for s in r["segments"]:
            out.append(f"- [{fmt_clock(s['start'])}–{fmt_clock(s['end'])}](https://www.youtube.com/watch?v={r['id']}&t={s['start']}s) {s['label']}")
        out += ["", f"**Lens hint.** {r['lens_hint']}", ""]
    out += ["---", ""] + footer + [""]
    return "\n".join(out)


CSS = """
:root{--bg:#f6f4ef;--ink:#1e1c19;--dim:#6a655c;--line:#dcd6ca;--panel:#eeeae1;--accent:#8a3b12;--watch:#1f6f43;--skim:#8a5a12;--summary:#3d5a80;--skip:#7a7a7a}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#161519;--ink:#e9e4da;--dim:#a39c91;--line:#33313a;--panel:#1f1e24;--accent:#e08a4a;--watch:#5fcf8f;--skim:#e0a84a;--summary:#8fb4e0;--skip:#8a8a8a}}
:root[data-theme="dark"]{--bg:#161519;--ink:#e9e4da;--dim:#a39c91;--line:#33313a;--panel:#1f1e24;--accent:#e08a4a;--watch:#5fcf8f;--skim:#e0a84a;--summary:#8fb4e0;--skip:#8a8a8a}
body{background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;padding:0 18px;padding-block:24px}
main{max-width:48rem;margin:0 auto}
h1{font-size:1.6rem;line-height:1.2;margin:0 0 .3rem;text-wrap:balance}
.stamp{color:var(--dim);font-size:.85rem}
.head{display:flex;flex-wrap:wrap;gap:.6rem 1.4rem;margin:1rem 0;padding:.9rem 1rem;background:var(--panel);border:1px solid var(--line);border-radius:8px;font-variant-numeric:tabular-nums}
.head b{font-size:1.25rem;display:block}.head span{font-size:.8rem;color:var(--dim);letter-spacing:.03em;text-transform:uppercase}
.intro{margin:.6rem 0 1.2rem;max-width:65ch}
h2.group{font-size:.85rem;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:1.8rem 0 .5rem;border-top:1px solid var(--line);padding-top:.9rem}
.row{display:grid;grid-template-columns:160px 1fr;gap:1rem;padding:1rem 0;border-bottom:1px solid var(--line)}
.row img{width:160px;max-width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:6px;background:var(--panel)}
.row h3{margin:0;font-size:1.05rem;line-height:1.3}
.meta{color:var(--dim);font-size:.82rem;margin:.25rem 0 .5rem}
.call{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:.1rem .45rem;border-radius:4px;border:1px solid currentColor;margin-right:.4rem}
.c-watch{color:var(--watch)}.c-skim{color:var(--skim)}.c-summary{color:var(--summary)}.c-skip{color:var(--skip)}
.tldr{margin:.3rem 0;font-weight:600}
ul.kt{margin:.3rem 0 .5rem;padding-left:1.2rem}ul.kt li{margin:.15rem 0}
.ws{margin:.4rem 0}.segs{display:flex;flex-wrap:wrap;gap:.4rem;margin:.4rem 0}
.segs a{font-size:.8rem;text-decoration:none;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:.25rem .55rem}
.segs a b{font-variant-numeric:tabular-nums;color:var(--accent);margin-right:.35rem}
.lens{font-size:.82rem;color:var(--dim)}
.num{color:var(--dim);font-weight:400;margin-right:.3rem}
footer{margin-top:1.5rem;color:var(--dim);font-size:.9rem}footer p{margin:.3rem 0}
a{color:var(--accent)}
@media (max-width:520px){.row{grid-template-columns:1fr}.row img{width:100%}}
"""


def html_digest(rows, headline, intro, footer, title, stamp) -> str:
    e = html.escape
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{e(title)}</title><style>{CSS}</style></head><body><main>",
             f"<h1>{e(title)}</h1><div class='stamp'>{e(stamp)}</div>",
             "<div class='head'>" + "".join(f"<div><b>{e(v)}</b><span>{e(k)}</span></div>" for k, v in headline["cells"]) + "</div>"]
    if intro:
        parts.append(f"<div class='intro'>{e(intro.strip())}</div>")
    group = None
    for r in rows:
        if r["call"] != group:
            group = r["call"]
            parts.append(f"<h2 class='group'>{e(group)}</h2>")
        url = f"https://www.youtube.com/watch?v={r['id']}"
        parts.append("<div class='row'>"
                     f"<a href='{url}'><img src='https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg' alt=''></a><div>"
                     f"<h3><span class='num'>{r['n']}.</span><a href='{url}'>{e(r['title'])}</a></h3>"
                     f"<div class='meta'><span class='call c-{r['call']}'>{r['call']}</span>{e(r['channel'])} · {e(r['published'])} · "
                     f"{(fmt_clock(r['kept']) + ' of ' if r['call'] in ('watch', 'skim') else '')}{fmt_clock(r['duration'])} · lens: {e(r['lens'])}</div>"
                     f"<p class='tldr'>{e(r['tldr'])}</p>"
                     "<ul class='kt'>" + "".join(f"<li>{e(t)}</li>" for t in r["takeaways"]) + "</ul>"
                     f"<p class='ws'><b>Watch / skip.</b> {e(r['call_text'])}</p>")
        if r["segments"]:
            parts.append("<div class='segs'>" + "".join(
                f"<a href='{url}&t={s['start']}s'><b>{fmt_clock(s['start'])}–{fmt_clock(s['end'])}</b>{e(s['label'])}</a>"
                for s in r["segments"]) + "</div>")
        parts.append(f"<div class='lens'>{e(r['lens_hint'])}</div></div></div>")
    parts.append("<footer>" + "".join(f"<p>{e(f)}</p>" for f in footer if f) + "</footer></main></body></html>")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--intro")
    ap.add_argument("--remaining", type=int)
    ap.add_argument("--list-note", default="")
    ap.add_argument("--unavailable", action="append", default=[])
    ap.add_argument("--title", default="Watch Later digest")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not args.check and not args.out_dir:
        print("render-digest: --out-dir is required unless --check", file=sys.stderr)
        return 2

    rows, errors = parse_rows(Path(args.rows).read_text(encoding="utf-8"))
    if errors:
        print("render-digest: FAIL, nothing written:")
        for err in errors:
            print(f"  - {err}")
        return 1

    prof = load_profile(Path(args.profile))
    try:
        rate = float(prof.get("settings", {}).get("playback_rate", "1.5"))
    except ValueError:
        rate = 1.5
    rows.sort(key=lambda r: (ORDER[r["call"]], -r["saved"]))
    for n, r in enumerate(rows, 1):
        r["n"] = n
    queued = sum(r["duration"] for r in rows)
    kept = sum(r["kept"] for r in rows)
    saved = queued - kept
    counts = {c: sum(1 for r in rows if r["call"] == c) for c in CALLS}
    headline = {
        "md": f"**{len(rows)} videos · {fmt_hm(queued)} queued · {fmt_hm(kept)} kept · {fmt_hm(saved)} saved "
              f"({fmt_hm(int(kept / rate))} at {rate:g}×)** · "
              + " · ".join(f"{c} {counts[c]}" for c in CALLS),
        "cells": [("videos", str(len(rows))), ("queued", fmt_hm(queued)), ("kept", fmt_hm(kept)),
                  ("saved", fmt_hm(saved)), (f"kept at {rate:g}×", fmt_hm(int(kept / rate)))],
    }
    print(f"render-digest | rows={len(rows)} queued={fmt_hm(queued)} kept={fmt_hm(kept)} saved={fmt_hm(saved)} "
          f"at_rate={fmt_hm(int(kept / rate))} | " + " ".join(f"{c}={counts[c]}" for c in CALLS))
    if args.check:
        return 0

    intro = Path(args.intro).read_text(encoding="utf-8") if args.intro else ""
    footer = []
    if args.unavailable:
        footer.append("Unavailable (recorded, not retried): " + "; ".join(args.unavailable))
    if args.remaining is not None:
        footer.append(f"{args.remaining} videos remain in Watch Later after this run.")
    if args.list_note:
        footer.append(f"List: {args.list_note}")
    footer.append("Reply with the row numbers you watched, and any you wish I had called differently.")
    tz = prof.get("settings", {}).get("timezone", "")
    try:
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo(tz)) if tz else dt.datetime.now()
    except Exception:
        now = dt.datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M") + (f" {tz}" if tz else "")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "digest.md").write_text(md_digest(rows, headline, intro, footer, args.title, stamp), encoding="utf-8")
    (out / "digest.html").write_text(html_digest(rows, headline, intro, footer, args.title, stamp), encoding="utf-8")
    (out / "rows.json").write_text(json.dumps(
        [{k: r[k] for k in ("n", "id", "title", "call", "duration", "kept", "saved", "lens")} for r in rows],
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"render-digest | wrote {out / 'digest.md'} and digest.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
