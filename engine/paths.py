#!/usr/bin/env python3
"""RESTRUCTURE T30 PHASE 2+3 — every path constant in one file. Computed from __file__ + the active show's tenant
directory, never a hardcoded directory name, so this module (and everything that imports it) survives a directory
rename intact. New code should import from here rather than hand-rolling another HERE/ROOT pair.

Phase 3 note: CANON, CONFIG/CHARS/LOCATIONS, OUTPUT and SCRIPTS now point at their real shows/crystal-bears/
locations. The old root-level paths (CRYSTAL_BEARS_LOCKED_CANON.md, engine/config, cb-output, cb-studio/data/scripts)
are kept as symlinks to these real locations for any not-yet-updated consumer — do not remove them without first
grepping for zero remaining references to the old paths.

    ENGINE    this directory (was cb-gen, now engine/)
    ROOT      the repo root (ENGINE's parent)
    SHOW      the active show's tenant directory under shows/ (env STUDIO_SHOW, default crystal-bears)
    CANON     the show's locked-canon markdown (shows/<show>/canon/LOCKED_CANON.md)
    CONFIG    the show's canon/ data directory (characters.json, locations.json, continuity.json, ...)
    CHARS / LOCATIONS   the two most-read config files, as a convenience
    MEDIA     generated review media (keyframes, clips, voice) — stays in the engine, show-agnostic scratch space
    OUTPUT    the show's beat packages (shows/<show>/episodes/output)
    SCRIPTS   the show's locked screenplays (shows/<show>/episodes/scripts)
    LOCKED    the engine's gate-lock state file (locked.json)
    NOTES     the engine's notes state file (notes.json)
"""
import os
import re

# FIXED 2026-07-11 (full-codebase audit, duplication finding): this exact pattern used to be hand-duplicated as
# cb_director_schemas._PAUSEHOLD_RE and cb_preflight._HOLD_RE (a beat's pauseHold field must state a concrete
# "N second(s)" duration, rule 47) — extracted once so the two checks (authoring-time repair-trigger vs the
# standing Gate-1 manifest BLOCK) can never silently drift on what counts as a valid duration string.
PAUSEHOLD_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*second")

ENGINE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ENGINE)

SHOW_ID = os.environ.get("STUDIO_SHOW", "crystal-bears")
SHOW = os.path.join(ROOT, "shows", SHOW_ID)

CANON = os.path.join(SHOW, "canon", "LOCKED_CANON.md")
CONFIG = os.path.join(SHOW, "canon")
CHARS = os.path.join(CONFIG, "characters.json")
LOCATIONS = os.path.join(CONFIG, "locations.json")

MEDIA = os.path.join(ENGINE, "media")
OUTPUT = os.path.join(SHOW, "episodes", "output")
SCRIPTS = os.path.join(SHOW, "episodes", "scripts")

LOCKED = os.path.join(ENGINE, "locked.json")
NOTES = os.path.join(ENGINE, "notes.json")

# FLAGGED 2026-07-12 (full-codebase audit continued, dead-code finding): LOCATIONS, MEDIA, LOCKED and NOTES
# above currently have zero callers anywhere in the repo — the real consumers (cb_pipeline.py's own
# hand-rolled LOCK/NOTES constants + its locations.json path builds, cb-studio/serve.py's CBGEN-relative
# paths, cb_replicator.py's _LOCK_PATH) each still independently recompute the identical path instead of
# importing these. That migration is real and worth doing, but it touches several files outside this
# module's own scope, so it isn't done here. Noted explicitly so a reader doesn't take this module's own
# docstring ("every path constant in one file") as proof these four are already wired up — they aren't yet.


def load_show_bible():
    """(canon_text, chars_dict) — the show's locked-canon markdown (empty string if missing) plus the full
    parsed characters.json. FIXED 2026-07-12 (loose-ends pass): this exact 3-line pattern — a guarded
    CANON.read_text(), then json.load(open(CHARS)) — used to be hand-duplicated in cb_writer.py's `_gen()`,
    cb_director.py's `_mind()`, and cb_director_eye.py's `_show_bible()`; extracted here so all three read the
    same two files the same way. Does NOT unwrap a `{"characters": {...}}` wrapper — the real characters.json
    has always been flat (confirmed live); callers needing the `bible` sub-field per character still do that
    extraction themselves, since only cb_director_eye.py's caller actually needs it."""
    import json
    canon = ""
    if os.path.exists(CANON):
        with open(CANON, encoding="utf-8") as f:
            canon = f.read()
    with open(CHARS, encoding="utf-8") as f:
        chars = json.load(f)
    return canon, chars


def slug(s):
    """Filesystem-safe slug: non-alphanumeric runs collapse to a single underscore, trimmed, "Untitled" if
    empty. FIXED 2026-07-12 (loose-ends pass): this exact formula was hand-duplicated in cb_writer.py (its own
    copy already None-safe, `s or ""`) and cb_director.py (its own copy NOT None-safe — `re.sub(..., s)` alone
    would raise TypeError on a None title) — extracted here, None-safe, so both share one behavior instead of
    silently drifting on this exact edge case."""
    return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_") or "Untitled"


def char_size_order(chars):
    """Character keys sorted by sizeRank, smallest/most-central first — the canonical roster order every
    authoring-prompt/system-prompt builder uses. FIXED 2026-07-11 (full-codebase audit, duplication finding):
    cb_director.py's and cb_writer.py's own _roster() helpers each hand-duplicated this exact sort byte-for-
    byte (same comment, same `or 99` null-safe fallback for a stub character like Bo, T6 ruling) — extracted
    here once so a future change to the ordering rule can't land in only one copy.
    A stub character (e.g. Bo) can have sizeRank explicitly null, not merely absent — .get(key, default) only
    falls back to default on a MISSING key, so a present-but-None value reaches sorted() as None and crashes
    comparing against another character's int rank. `or 99` catches both missing AND explicitly-null."""
    return sorted([k for k, v in chars.items() if isinstance(v, dict) and k not in ("sizeClasses",)],
                  key=lambda k: chars[k].get("sizeRank") or 99)
