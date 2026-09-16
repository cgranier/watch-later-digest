# Bringing it up on a new account

Do these in order. Do not schedule anything until three consecutive supervised runs pass. The rule every practitioner arrives at: run it by hand, correct it, freeze it, then put it on a clock.

1. **Bootstrap.** Pick a durable STATE_DIR (Grok Bot: `/workspace/watch-later-digest/state`). Run `scripts/bootstrap.sh STATE_DIR`. Open a fresh shell and confirm `yt-dlp --version` still works.
2. **Profile.** `scripts/check-profile.py STATE_DIR/profile.md`. If it exits 2, run the interview in `references/profile.md`, write the file, echo the parsed table back, and wait for confirmation.
3. **Enumerate only.** Step 1 of `SKILL.md`. Report the counts and the newest 15 titles. Stop.
4. **One video, by hand, in chat.** Take the newest new video. Fetch, read, write the row, show it, take the correction, rewrite it. Repeat with a second video that hits a different lens. This is where the bot learns the user's grain.
5. **First supervised run.** Ten videos, `list_policy: leave` regardless of the profile. Deliver the digest. Append corrections as calibration notes.
6. **Second and third supervised runs** with the profile's real `list_policy`. Both must pass `references/tests.md` with no manual intervention.
7. **Routine.** Only now: schedule the skill at the profile's cadence. The routine's first step checks that the previous run's `log.md` ended cleanly; if not, run in `leave` mode and say so in the digest header.

## Packaging for a marketplace

On Grok Bot, a bot is shared as a **template**: a bundle of its skills, memories and plugins that another user installs as a copy. Personal memories are filtered out automatically; make sure the filled-in `profile.md` and `seen.json` live in STATE_DIR, not inside the skill folder, so a template never carries them. What ships is this folder: the procedure, the scripts, the profile *template* and the interview. The installing user's first run is the interview.

Two things to verify on the target platform before publishing, because the vendor guides do not say:

- Whether a template snapshots the skill body at publish time or links to its source. If it snapshots, a repo update does not reach installed copies; say so in the listing and version the `metadata.version` field.
- Whether `git` and `python3` survive an agent-computer update. If not, `bootstrap.sh` needs an apt line for them too.
