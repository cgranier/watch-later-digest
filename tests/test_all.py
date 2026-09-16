#!/usr/bin/env python3
"""Offline tests for the skill's scripts. Run from anywhere:

    python3 tests/test_all.py

No network, no yt-dlp. fetch-transcript.sh is exercised live by
tests/live-fetch.sh instead.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "scripts"
FX = ROOT / "tests" / "fixtures"
PY = sys.executable


def run(*args, **kw):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, **kw)


class Vtt2Txt(unittest.TestCase):
    def test_dedupes_rolling_captions_and_keeps_times(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(PY, S / "vtt2txt.py", FX / "sample.vtt", Path(d) / "out")
            self.assertEqual(r.returncode, 0, r.stderr)
            plain = (Path(d) / "out.txt").read_text()
            timed = (Path(d) / "out.timed.txt").read_text()
            self.assertEqual(plain.count("so today we're holding the grind"), 1, plain)
            self.assertEqual(plain.count("constant across six grinders"), 1, plain)
            self.assertIn("and here is the puck after the shot", plain)      # &nbsp; unescaped
            self.assertNotIn("<c>", plain)
            self.assertIn("4:10  and here is the puck", timed)
            self.assertIn("19:20  the winners swap", timed)
            self.assertIn("lines=4", r.stdout)

    def test_missing_file_is_exit_1(self):
        self.assertEqual(run(PY, S / "vtt2txt.py", "/nonexistent.vtt", "/tmp/x").returncode, 1)


class Seen(unittest.TestCase):
    def test_has_add_filter_list(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "seen.json"
            self.assertEqual(run(PY, S / "seen.py", f, "has", "aaaaaaaaaaa").returncode, 1)
            self.assertEqual(run(PY, S / "seen.py", f, "add", "aaaaaaaaaaa", "--call", "skip", "--title", "t").returncode, 0)
            self.assertEqual(run(PY, S / "seen.py", f, "has", "aaaaaaaaaaa").returncode, 0)
            enum = Path(d) / "enum.json"
            enum.write_text(json.dumps([{"id": "aaaaaaaaaaa", "title": "t"}, {"id": "bbbbbbbbbbb", "title": "u"},
                                        {"id": "ccccccccccc", "title": "v"}]))
            r = run(PY, S / "seen.py", f, "filter", enum)
            self.assertEqual([x["id"] for x in json.loads(r.stdout)], ["bbbbbbbbbbb", "ccccccccccc"])
            self.assertIn("1 seen, 2 new", r.stderr)
            self.assertIn("aaaaaaaaaaa", run(PY, S / "seen.py", f, "list").stdout)

    def test_bad_call_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(run(PY, S / "seen.py", Path(d) / "s.json", "add", "x", "--call", "maybe").returncode, 0)


class Profile(unittest.TestCase):
    def test_template_is_usable(self):
        r = run(PY, S / "check-profile.py", ROOT / "assets" / "profile-template.md")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("usable", r.stdout)

    def test_thin_profile_is_gated(self):
        r = run(PY, S / "check-profile.py", FX / "profile-thin.md")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("three is the minimum", r.stdout)

    def test_missing_profile_is_gated(self):
        self.assertEqual(run(PY, S / "check-profile.py", "/nonexistent/profile.md").returncode, 2)

    def test_json_parses_lenses_and_lists(self):
        r = run(PY, S / "check-profile.py", ROOT / "assets" / "profile-template.md", "--json")
        p = json.loads(r.stdout)
        self.assertEqual([l["name"] for l in p["lenses"]], ["Home espresso", "Kubernetes at work", "Woodworking"])
        self.assertIn("James Hoffmann", p["lenses"][0]["vocabulary"])
        self.assertEqual(p["settings"]["playback_rate"], "1.5")
        self.assertEqual(p["always_watch"], ["Cluster Talks"])
        self.assertEqual(len(p["always_skip"]), 3)


class Render(unittest.TestCase):
    def test_good_rows_render_with_correct_arithmetic_and_order(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(PY, S / "render-digest.py", "--rows", FX / "rows-good.md",
                    "--profile", ROOT / "assets" / "profile-template.md", "--out-dir", d,
                    "--remaining", "12", "--list-note", "moved 4 to Digested, verified 4/4")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rows = json.loads((Path(d) / "rows.json").read_text())
            # order: watch, skim, summary, skip; numbered in that order
            self.assertEqual([x["call"] for x in rows], ["watch", "skim", "summary", "skip"])
            self.assertEqual([x["n"] for x in rows], [1, 2, 3, 4])
            # kept: watch = full 1:02:10 = 3730; skim = (9:55-4:10)+(21:05-19:20) = 345+105 = 450
            kept = {x["id"]: x["kept"] for x in rows}
            self.assertEqual(kept["bbbbbbbbbbb"], 3730)
            self.assertEqual(kept["aaaaaaaaaaa"], 450)
            self.assertEqual(kept["ccccccccccc"], 0)
            self.assertEqual(kept["ddddddddddd"], 0)
            queued = round((1458 + 3730 + 720 + 510) / 60)          # 107 min, rounded like the script
            self.assertIn(f"queued={queued // 60}h {queued % 60:02d}m", r.stdout)
            self.assertIn("kept=1h 10m", r.stdout)                  # 3730 + 450 = 4180 s
            md = (Path(d) / "digest.md").read_text()
            self.assertIn("**Watch / skip.**", md)
            self.assertIn("&t=250s", md)                       # 4:10 deep link
            self.assertIn("12 videos remain", md)
            self.assertIn("Reply with the row numbers", md)
            htm = (Path(d) / "digest.html").read_text()
            self.assertIn("i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg", htm)
            self.assertIn("&t=1160s", htm)                     # 19:20
            self.assertNotIn("<iframe", htm)                   # static: no player

    def test_bad_rows_fail_naming_every_rule(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(PY, S / "render-digest.py", "--rows", FX / "rows-bad.md",
                    "--profile", ROOT / "assets" / "profile-template.md", "--out-dir", d)
            self.assertEqual(r.returncode, 1)
            self.assertFalse((Path(d) / "digest.md").exists())
            out = r.stdout
            self.assertIn("literal heading **Watch / skip.** is missing", out)
            self.assertIn("is not inside 0..10:00", out)
            self.assertIn("call is skim but no segments", out)
            self.assertIn("is not an 11-character video id", out)
            self.assertIn("call must be one of", out)

    def test_check_only_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(PY, S / "render-digest.py", "--rows", FX / "rows-good.md",
                    "--profile", ROOT / "assets" / "profile-template.md", "--check")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("rows=4", r.stdout)
            self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
