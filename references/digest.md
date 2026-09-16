# Rows and the digest

## The row

One block per video in `runs/<date>/rows.md`. `scripts/render-digest.py` parses it and refuses the whole file, naming the row and the rule, on any violation. The bot does not number rows; the renderer does after ordering.

```markdown
## <title>
id: <11-character video id>
channel: <channel>
published: <YYYY-MM-DD>
duration: <H:MM:SS or M:SS>
lens: <lens name, or general>
call: <watch | skim | summary | skip>
segments:                       # required for skim, forbidden for the other three
  - "4:10-9:55  the held-constant method, pucks shown"
  - "19:20-21:05  winners swap when pre-infusion is off"

**TL;DR.** <one sentence: what the video delivers, not what it is about>

**Key takeaways**
- <three to five; each something the title does not already say>

**Watch / skip.** <the call, why, and where>

**Lens hint.** <lens> — <which line it hit: worth_it, enough, or skip_when>
```

Rules the renderer enforces:

- `id` is eleven characters; `duration` parses; `call` is one of the four.
- `**Watch / skip.**` appears literally. A row headed "Skim." or "Skip this one." is a failure, not a variant. (This has lost rows in an earlier system, silently, which is why it is a hard check now.)
- A `**TL;DR.**` line and at least one takeaway bullet.
- `skim` has at least one segment; the other calls have none.
- Every segment has `start < end ≤ duration` and a label.
- No id appears twice.

Segments are data, not prose. Prose is never parsed for timestamps, because "skim 5:33 to 7:58" and "the 1:17 to 5:33 intro is skippable" look identical to a regex and mean the opposite.

## The four calls

- `watch`: the video itself carries something a summary cannot (visuals, density, primary-source voice). Kept time is the full duration.
- `skim`: specific minutes, named. Kept time is the sum of the segments. Labels are the reason the user is being sent there.
- `summary`: the row fully substitutes for watching. Kept time zero.
- `skip`: low value regardless. Kept time zero.

Call lines read like:

- *Worth the full 22 minutes: the dial-in session from 4:10 is the only side-by-side I have seen with the grind held constant.*
- *Skim 5:33 to 7:58 and 9:35 to 16:04; the rest is biography.*
- *The takeaways above are the video. The remaining 18 minutes restate them with B-roll.*
- *Sponsored walkthrough; no benchmark, no comparison, nothing the lens asks for.*

## The digest

One page per run, `runs/<date>/digest.md`, plus `digest.html` (static: thumbnails from `https://i.ytimg.com/vi/<id>/hqdefault.jpg`, which always exists, and `?t=<seconds>s` deep links for every segment; no embedded player, because a page opened from disk has no web origin and YouTube refuses to play in it).

Top to bottom:

1. **Headline.** `15 videos · 4h 12m queued · 41m kept · 3h 31m saved (27m at 1.5×)`, with the call counts. Kept = full duration for `watch` + segments for `skim`. Saved = queued − kept. At-speed = kept ÷ `playback_rate`.
2. **Intro.** Two sentences from `intro.md`: what the batch was mostly about, and the one thing not to miss.
3. **Rows,** grouped `watch`, `skim`, `summary`, `skip`, each group ordered by minutes saved, largest first. Numbered in that order so the user can reply with numbers.
4. **Footer.** Unavailable videos, the count remaining in Watch Later, what happened to the list, and the calibration question.

`rows.json` beside them carries `n, id, title, call, duration, kept, saved, lens` for the log and for tests.

## A filled-in row, for grain

See `assets/example-row.md`. Fictional video, fictional channel.
