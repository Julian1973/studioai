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
