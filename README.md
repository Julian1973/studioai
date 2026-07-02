# Crystal Bears Studio

A gated AI animation pipeline: script → beats → keyframes → Seedance video → retakes → post. Built to make the same show, at broadcast quality, at cadence.

**Start here:** `CLAUDE.md` (operating rules) → `CRYSTAL_BEARS_STUDIO_BIBLE.md` (how things are made) → `TICKET_PACK_001.md` (what's open).

## The tree

- `engine/` — the show-agnostic pipeline code (Director, prompt builder, voice, QA, retakes, post).
- `shows/crystal-bears/` — the tenant: canon, config, laws, docs, chair skills, episode scripts + output.
- `cb-studio/` — the studio UI (`app.html` + `serve.py`).
- `skills/` — the Claude Code chair skills (director, writer, dp, voice, camera, post, continuity, composer).
- `tools/` — `sync_canon.py` (canon drift check/fix) and friends.
- `archive/` — superseded docs, kept for the record, never built against.

## Starting a session

Read `CLAUDE.md`, then `TICKET_PACK_001.md`'s order of play, then the current phase of `WORLD_CLASS_ROADMAP.md`. Fire the studio via `.claude/launch.json`'s `cb-studio` config (port 8765).
