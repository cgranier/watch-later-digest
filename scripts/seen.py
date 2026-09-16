#!/usr/bin/env python3
"""
seen.py -- the digested-video ledger. One JSON file, keyed by video id.

    seen.py FILE has ID                       exit 0 if digested before, 1 if not
    seen.py FILE add ID --call CALL [--title T] [--date YYYY-MM-DD]
    seen.py FILE filter ENUMERATION.json      print the items NOT in the ledger, as JSON,
                                              in the enumeration's order
    seen.py FILE list                         one line per entry, newest first

CALL is watch | skim | summary | skip | unavailable. An id in the ledger is
never fetched or summarized again; that is what makes a re-run cheap and safe.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

CALLS = ("watch", "skim", "summary", "skip", "unavailable")


def load(p: Path) -> dict:
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        print(f"seen: {p} is not valid JSON; refusing to overwrite it", file=sys.stderr)
        sys.exit(2)


def save(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("has"); h.add_argument("id")
    a = sub.add_parser("add"); a.add_argument("id"); a.add_argument("--call", required=True, choices=CALLS)
    a.add_argument("--title", default=""); a.add_argument("--date", default=dt.date.today().isoformat())
    f = sub.add_parser("filter"); f.add_argument("enumeration")
    sub.add_parser("list")
    args = ap.parse_args()

    p = Path(args.file)
    d = load(p)
    if args.cmd == "has":
        return 0 if args.id in d else 1
    if args.cmd == "add":
        d[args.id] = {"digested": args.date, "call": args.call, "title": args.title[:120]}
        save(p, d)
        print(f"seen: {args.id} {args.call}")
        return 0
    if args.cmd == "filter":
        items = json.loads(Path(args.enumeration).read_text(encoding="utf-8"))
        new = [it for it in items if it.get("id") and it["id"] not in d]
        print(json.dumps(new, ensure_ascii=False, indent=1))
        print(f"seen: {len(items)} enumerated, {len(items) - len(new)} seen, {len(new)} new", file=sys.stderr)
        return 0
    if args.cmd == "list":
        for k, v in sorted(d.items(), key=lambda kv: kv[1].get("digested", ""), reverse=True):
            print(f"{v.get('digested','')}  {v.get('call',''):<11} {k}  {v.get('title','')}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
