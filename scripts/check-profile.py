#!/usr/bin/env python3
"""
check-profile.py -- parse and gate the user's interest profile.

    check-profile.py PROFILE.md [--json]

Prints a table of the profile's settings and lenses, then a verdict:

    exit 0   usable: three or more lenses, settings present
    exit 1   usable but rough: a lens is missing worth_it / enough / skip_when,
             so calls on it will be coin flips; say so in the digest
    exit 2   not usable: file missing, fewer than three lenses, or a required
             setting absent. Run the onboarding interview; do not fetch anything.

--json prints the parsed profile instead of the table (settings, lenses,
always_skip, always_watch, calibration), for other scripts to consume.

The profile format is references/profile.md in this skill; the template is
assets/profile-template.md.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED = ("owner", "timezone", "cadence", "deliver_via", "cap_per_run", "playback_rate", "list_policy")
LENS_KEYS = ("why", "worth_it", "enough", "skip_when", "vocabulary")
DEFAULTS = {"cap_per_run": "15", "playback_rate": "1.5", "list_policy": "move", "digested_playlist": "Digested"}
KV_RE = re.compile(r"^([a-z_]+):\s*(.*?)\s*(?:#.*)?$")
ITEM_RE = re.compile(r"^-\s+(?:([a-z_]+):\s*)?(.*)$")


def parse(text: str) -> dict:
    prof = {"settings": dict(DEFAULTS), "lenses": [], "always_skip": [], "always_watch": [], "calibration": []}
    section, lens = "settings", None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            h = line[3:].strip().lower()
            section = {"lenses": "lenses", "always skip": "always_skip", "always watch": "always_watch",
                       "calibration notes": "calibration"}.get(h, "other")
            lens = None
            continue
        if line.startswith("### ") and section == "lenses":
            lens = {"name": line[4:].strip()}
            prof["lenses"].append(lens)
            continue
        if section == "settings":
            m = KV_RE.match(line)
            if m:
                prof["settings"][m.group(1)] = m.group(2).strip()
            continue
        m = ITEM_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if section == "lenses" and lens is not None and key:
            lens[key] = val
        elif section in ("always_skip", "always_watch", "calibration"):
            prof[section].append(val if not key else f"{key}: {val}")
    for l in prof["lenses"]:
        l["vocabulary"] = [t.strip() for t in l.get("vocabulary", "").split(",") if t.strip()]
    return prof


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    p = Path(argv[1])
    as_json = "--json" in argv
    if not p.is_file():
        print(f"check-profile: {p} not found -> run the onboarding interview (references/profile.md §2)")
        return 2
    prof = parse(p.read_text(encoding="utf-8"))
    if as_json:                       # JSON only, for other scripts; the verdict is the exit code
        print(json.dumps(prof, indent=1, ensure_ascii=False))
        return 0 if len(prof["lenses"]) >= 3 else 2
    s = prof["settings"]
    missing = [k for k in REQUIRED if not s.get(k)]
    rc = 0
    if not as_json:
        print(f"profile: {p}")
        print("  " + " · ".join(f"{k}={s.get(k, '?')}" for k in REQUIRED + ("digested_playlist",)))
        print(f"  {'lens':<28} {'vocab':>5}  why  worth_it  enough  skip_when")
        for l in prof["lenses"]:
            flags = "  ".join(("yes " if l.get(k) else "MISSING")[:len(k)].ljust(len(k)) for k in LENS_KEYS[:4])
            print(f"  {l['name'][:28]:<28} {len(l['vocabulary']):>5}  {flags}")
        print(f"  always_skip={len(prof['always_skip'])} always_watch={len(prof['always_watch'])} "
              f"calibration_notes={len(prof['calibration'])}")
    if missing:
        print(f"check-profile: missing settings {missing} -> not usable")
        rc = 2
    if len(prof["lenses"]) < 3:
        print(f"check-profile: {len(prof['lenses'])} lens(es); three is the minimum -> run the onboarding interview")
        rc = 2
    if len(prof["lenses"]) > 8:
        print("check-profile: more than eight lenses; calls get mushy past eight (warning)")
    if s.get("list_policy") not in ("move", "remove", "leave"):
        print(f"check-profile: list_policy must be move | remove | leave, got {s.get('list_policy')!r}")
        rc = 2
    if rc == 0:
        rough = [l["name"] for l in prof["lenses"] if not all(l.get(k) for k in ("worth_it", "enough", "skip_when"))]
        if rough:
            print(f"check-profile: rough lenses (missing worth_it/enough/skip_when): {rough} -> usable, calls will be rough")
            rc = 1
        else:
            print("check-profile: usable")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
