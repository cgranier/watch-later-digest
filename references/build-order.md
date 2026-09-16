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

On Grok Bot, a bot is shared as a **template**: a bundle of its skills, memories and plugins that another user installs as a copy. Confirmed with the vendor's bot (2026-09-16): the pack **copies the skill prose into the template; it is a versioned snapshot, not a git pointer.** Installed copies do not update when the repo does. The loop is: edit the skill in the repo → tag it → re-pack → publish a new template version.

Also confirmed: the pack carries **only the skill's body text**. The packer passes name, description and the scrubbed prose, and the host builds a fresh `SKILL.md` from those. Frontmatter (`metadata.*`), `scripts/`, `references/` and `assets/` are not copied.

What that means for this skill:

- `SKILL.md` step 0 carries the repo URL and the tag as literal text, with a tarball fallback for a computer without `git`, and clones the skill into `/workspace/skills/watch-later-digest` when `scripts/` is absent. A prose-only template therefore still gets the scripts, references and assets the prose was written against. Bump `metadata.version`, the URL/tag in step 0, and the git tag together; they are one number.
- The template ships this folder's *shape*, never a user's state. Keep `profile.md`, `seen.json` and transcripts in STATE_DIR, outside the skill folder. Personal memories are filtered by the packer, but files are not memories; do not rely on it.
- Put the skill on its own bot (name it **Digest**, description from the brief), not on a bot that holds the author's own memories. A getting-started skill on that bot can run the onboarding interview, but the interview text lives here in `references/profile.md`; the getting-started skill should call it, not restate it.
- Routines are not part of the pack as far as the vendor guides say. The installing user creates the routine after three supervised runs, per the sequence above. Say so in the template's description.
- No plugins are needed. The browser is built in; `chat` and `file` delivery need nothing; `email` delivery needs whatever the platform offers and is the installing user's choice.

Still to verify on the target platform: whether `git`, `curl` and `python3` survive an agent-computer update. Step 0 works with either `git` or `curl`; `python3` has no fallback, so if it is wiped `bootstrap.sh` needs an apt line for it.
