#!/usr/bin/env python3
"""EVERY PATH THE ENGINE READS FOR THE ACTIVE PROJECT, IN ONE PLACE.

T44 (RESTRUCTURE_SPEC_PROJECTS.md, 2026-09-01): the project's profile.json is the only authority for where
its files live; this module reads that profile once and exposes each location as a constant. No engine,
studio, tool or dailies module builds a project path by hand — it imports from here. A path that is not
declared in the profile does not exist as far as the engine is concerned.

    ENGINE            this directory
    ROOT              the repo root (ENGINE's parent)
    PROJECT_ID        the active project's id (env STUDIO_PROJECT, else the profile marked "default")
    PROJECT           projects/<id>/  (SHOW and SHOW_ID remain as aliases for one release)
    CANON             the locked-canon markdown
    CONFIG            the canon/ data directory
    CHARS / LOCATIONS / CONTINUITY / EPISODE_ARC / GAG_LOCKS / BANNED_VOCABULARY / IDENTITY_PACKS
    VOICE_CARDS / SFX_LIBRARY / SFX_DIR / BEAT_COSTS / LOCK_POLICY / CANON_LOCK / REFERENCE_SLOT_POLICY
    STYLE_LAW / WING_LAW / FORBIDDEN_ELEMENTS / EMISSION_CHECKS / CAST_VOCABULARY / CONTINUITY_RULES
                      (None if undeclared)
    CREATIVE          the project's creative/ (taste canons, exemplars, corpus)
    LEARNING / EXEMPLARS / DAILIES_LIBRARY / VOICE_REGISTERS / VOICE_RULEBOOK / VOICE_PLAYBOOK
    ASSETS            the project's reference media root (turnarounds, plates) — None if undeclared
    SHOW_BIBLE / DOCS / CHAIRS
    SCRIPTS           the project's locked screenplays
    OUTPUT            the project's packages / evidence / prompt bank / asset registry
    EPISODES_INDEX    the derived episode index the studio maintains for this project
    MEDIA             generated review media — engine scratch, not project data
    LOCKED / NOTES    the engine's gate-lock and notes state files

The old paths (shows/, cb-output/, engine/config, cb-studio/data/scripts, cb-seed/) exist only as
compatibility links for data files that still name them; tools/check_links.py verifies them.
"""
import os
import re
import project_profile

# FIXED 2026-07-11 (full-codebase audit, duplication finding): this exact pattern used to be hand-duplicated as
# cb_director_schemas._PAUSEHOLD_RE and cb_preflight._HOLD_RE (a beat's pauseHold field must state a concrete
# "N second(s)" duration, rule 47) — extracted once so the two checks (authoring-time repair-trigger vs the
# standing Gate-1 manifest BLOCK) can never silently drift on what counts as a valid duration string.
PAUSEHOLD_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*second")

ENGINE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ENGINE)

PROFILE = project_profile.load_project_profile(ROOT)
SHOW_PROFILE = PROFILE                      # alias, one release
PROJECT_ID = PROFILE.profile.showId
SHOW_ID = PROJECT_ID                        # alias, one release
PROJECT_NAME = PROFILE.profile.name
SHOWRUNNER = PROFILE.profile.showrunner or "the showrunner"   # who signs the gates (T52 chair contracts)
ENGINE_ADAPTER = PROFILE.profile.engineAdapter          # historical label (T55) — never a gate
CAPABILITIES = {**project_profile.DEFAULT_CAPABILITIES, **(PROFILE.profile.capabilities or {})}
PROJECT = str(PROFILE.project_root)
SHOW = PROJECT                              # alias, one release


def _s(path):
    return str(path) if path is not None else None


_CANON = PROFILE.canon_paths
CANON = _s(_CANON["lockedCanon"])
CHARS = _s(_CANON["characters"])
LOCATIONS = _s(_CANON["locations"])
CONTINUITY = _s(_CANON["continuity"])
EPISODE_ARC = _s(_CANON.get("episodeArc"))
GAG_LOCKS = _s(_CANON.get("gagLocks"))
IDENTITY_PACKS = _s(_CANON.get("identityPacks"))
BANNED_VOCABULARY = _s(_CANON.get("bannedVocabulary"))
VOICE_CARDS = _s(_CANON.get("voiceCards"))
SFX_LIBRARY = _s(_CANON.get("sfxLibrary"))
SFX_DIR = _s(_CANON.get("sfxDir"))
BEAT_COSTS = _s(_CANON.get("beatCosts"))
LOCK_POLICY = _s(_CANON.get("lockPolicy"))
CANON_LOCK = _s(_CANON.get("canonLock"))
REFERENCE_SLOT_POLICY = _s(_CANON.get("referenceSlotPolicy"))
CONFIG = os.path.dirname(CHARS)

_LAWS = PROFILE.laws_paths
STYLE_LAW = _s(_LAWS.get("style"))
WING_LAW = _s(_LAWS.get("wingLaw"))
FORBIDDEN_ELEMENTS = _s(_LAWS.get("forbiddenElements"))
EMISSION_CHECKS = _s(_LAWS.get("emissionChecks"))
CAST_VOCABULARY = _s(_LAWS.get("castVocabulary"))
CONTINUITY_RULES = _s(_LAWS.get("continuityRules"))

CREATIVE = _s(PROFILE.creative_root)


def _creative(key, default_rel):
    """A creative file the profile declares, else its conventional home under creative/ (T58: a
    project that has not written one yet still has a definite path; the module handles absence)."""
    declared = PROFILE.creative_path(key)
    return _s(declared) if declared else os.path.join(CREATIVE, default_rel)


LEARNING = _creative("learning", "learning")
EXEMPLARS = _creative("exemplars", "EXEMPLAR_LIBRARY.json")
DAILIES_LIBRARY = _creative("dailiesLibrary", os.path.join("learning", "DAILIES_LIBRARY.jsonl"))
VOICE_REGISTERS = _creative("voiceRegisters", "VOICE_ARCHETYPE_REGISTERS.json")
VOICE_RULEBOOK = _creative("voiceRulebook", "VOICE_DIRECTOR_RULEBOOK.json")
VOICE_PLAYBOOK = _creative("voicePlaybook", os.path.join("learning", "VOICE_PLAYBOOK.json"))

ASSETS = _s(PROFILE.assets_root)
SHOW_BIBLE = _s(PROFILE.show_bible_path)
DOCS = _s(PROFILE.docs_path)
CHAIRS = _s(PROFILE.chairs_path)

SCRIPTS = _s(PROFILE.scripts_path)
OUTPUT = _s(PROFILE.output_path)
EPISODES_INDEX = _s(PROFILE.episodes_index_path)

# Repo-relative forms, for callers that work under a caller-supplied root (tests pass a scratch root).
OUTPUT_REL = os.path.relpath(OUTPUT, ROOT)
SCRIPTS_REL = os.path.relpath(SCRIPTS, ROOT)
EPISODES_INDEX_REL = os.path.relpath(EPISODES_INDEX, ROOT)
CONFIG_REL = os.path.relpath(CONFIG, ROOT)

# T58: the project's own media home when its profile declares episodes.media; otherwise the legacy
# shared engine/media (the first project, for one release). Every module builds media paths from here.
MEDIA = _s(PROFILE.media_path) or os.path.join(ENGINE, "media")
MEDIA_URL = "/" + os.path.relpath(MEDIA, ROOT).replace(os.sep, "/") + "/"   # the studio's URL root for it
LOCKED = os.path.join(ENGINE, "locked.json")
NOTES = os.path.join(ENGINE, "notes.json")


def rel(path):
    """A project path as the repo-relative string data files and URLs use (forward slashes)."""
    return os.path.relpath(str(path), ROOT).replace(os.sep, "/")


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
