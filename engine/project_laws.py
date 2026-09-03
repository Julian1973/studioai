#!/usr/bin/env python3
"""THE PROJECT'S OWN VOCABULARY AND LAWS — read from data, never spelled in code.

T46/T47 (RESTRUCTURE_SPEC_PROJECTS.md, 2026-09-01): the engine used to know cast names, species,
appearance words, a pronunciation fix, a "bees have no crystal" proximity ban and a keyframe
forbidden-elements list by heart. They are Crystal Bears facts, so they now live in the project
(laws/cast_vocabulary.json, laws/forbidden_elements.json, declared in profile.json) and every
consumer asks this module. A project that declares neither file gets empty vocabularies and the
generic checks only — never another project's names.

Everything here is zero-cost and cached per process; call `reload()` after editing the files.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import paths as P


def _load(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=None)
def cast_vocabulary() -> Dict[str, Any]:
    return _load(P.CAST_VOCABULARY)


@lru_cache(maxsize=None)
def forbidden_elements() -> Dict[str, Any]:
    return _load(P.FORBIDDEN_ELEMENTS)


@lru_cache(maxsize=None)
def continuity_rules() -> Dict[str, Any]:
    return _load(P.CONTINUITY_RULES)


@lru_cache(maxsize=None)
def emission_checks() -> Dict[str, Any]:
    return _load(P.EMISSION_CHECKS)


def reload() -> None:
    cast_vocabulary.cache_clear()
    forbidden_elements.cache_clear()
    continuity_rules.cache_clear()
    emission_checks.cache_clear()
    room.cache_clear()


# ---- cast -------------------------------------------------------------------------------------

def cast_names() -> List[str]:
    return [str(n) for n in (cast_vocabulary().get("names") or [])]


def names_regex(group: bool = True) -> Optional[str]:
    """A word-bounded alternation of the cast names, longest first, or None for a project with none."""
    names = sorted(cast_names(), key=len, reverse=True)
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in names)
    return f"({alt})" if group else alt


def appearance_regex() -> Optional[str]:
    terms = sorted({str(t) for t in (cast_vocabulary().get("appearanceTerms") or [])}, key=len, reverse=True)
    if not terms:
        return None
    return r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b"


def species_of(name: str, record: Optional[Dict[str, Any]] = None) -> str:
    """The on-screen species for a character: typed canon (`species`) > the legacy `isBee` flag > the
    vocabulary's fallback terms found in the character's own identity prose > the project's species map
    (for a record with no prose at all) > "character"."""
    record = record or {}
    typed = str(record.get("species") or "").strip().lower()
    if typed:
        return typed
    if record.get("isBee"):
        return "bee"
    # The character's OWN identity prose is evidence before any map: a record the caller hands in
    # (a test fixture, a new project's draft) is never overruled by the vocabulary file.
    identity = " ".join(str(record.get(k) or "") for k in ("size", "key_features", "promptRole")).lower()
    bible = record.get("bible") or {}
    identity += " " + " ".join(str(bible.get(k) or "") for k in ("title", "whoTheyAre")).lower()
    for candidate in (cast_vocabulary().get("speciesFallbackTerms") or []):
        if re.search(rf"\b{re.escape(str(candidate))}s?\b", identity):
            return str(candidate)
    mapped = (cast_vocabulary().get("species") or {}).get(name)
    if mapped:
        return str(mapped).strip().lower()
    return "character"


def has_wings(name: str, record: Optional[Dict[str, Any]] = None) -> bool:
    """physiology.wings from the vocabulary; falls back to the legacy isBee flag / 'bee' in `avoid`."""
    record = record or {}
    phys = (cast_vocabulary().get("physiology") or {}).get(name) or {}
    if "wings" in phys:
        return bool(phys.get("wings"))
    if record.get("isBee"):
        return True
    return "bee" in str(record.get("avoid") or "").lower()


def winged_names() -> List[str]:
    phys = cast_vocabulary().get("physiology") or {}
    return [n for n, v in phys.items() if isinstance(v, dict) and v.get("wings")]


def pronunciation_overrides() -> Dict[str, str]:
    return {str(k): str(v) for k, v in (cast_vocabulary().get("pronunciation") or {}).items()}


def proximity_bans() -> List[Dict[str, Any]]:
    return [b for b in (cast_vocabulary().get("proximityBans") or []) if isinstance(b, dict)]


def retake_terms(key: str) -> List[str]:
    return [str(t).lower() for t in ((cast_vocabulary().get("retakeTerms") or {}).get(key) or [])]


def vocal_cue(kind: str) -> Optional[str]:
    """A performance-note template for a detected vocal kind (e.g. a mantra chant); {cue} is the
    authored phonetic cue. None when the project has no such note."""
    v = (cast_vocabulary().get("vocalCues") or {}).get(kind)
    return str(v) if v else None


def comedy_default(key: str, fallback):
    v = (cast_vocabulary().get("comedyDefaults") or {}).get(key)
    return v if v not in (None, "", []) else fallback


def nonverbal_sound_palette(default: str) -> str:
    """The project's own non-dialogue sound palette for a provider prompt (cast_vocabulary.json →
    nonverbalSoundPalette, a list of phrases) joined as prose, or the generic default."""
    items = [str(t).strip() for t in (cast_vocabulary().get("nonverbalSoundPalette") or []) if str(t).strip()]
    return ", ".join(items) if items else default


def offscreen_only() -> List[str]:
    return [str(n) for n in (cast_vocabulary().get("offscreenOnly") or [])]


def complexity_signals(generic) -> List[str]:
    """The engine's generic complexity words plus the project's own gag words."""
    extra = [str(t).lower() for t in (cast_vocabulary().get("complexitySignals") or [])]
    return list(dict.fromkeys([*[str(g).lower() for g in generic], *extra]))


def archetype_signals() -> List[Dict[str, Any]]:
    """emission_checks.json → archetypeSignals, in declared order."""
    return [r for r in (emission_checks().get("archetypeSignals") or []) if isinstance(r, dict) and r.get("archetype")]


def review_question(key: str, default: str) -> str:
    return str((cast_vocabulary().get("reviewQuestions") or {}).get(key) or default)


# ---- forbidden elements -----------------------------------------------------------------------

def keyframe_forbidden(winged_in_frame: bool) -> List[str]:
    fe = forbidden_elements()
    out = [str(x) for x in (fe.get("always") or [])]
    if winged_in_frame:
        out += [str(x) for x in (fe.get("winged") or [])]
    return out


def animation_negatives(group: str) -> List[tuple]:
    pairs = ((forbidden_elements().get("animationNegatives") or {}).get(group) or [])
    return [tuple(p) for p in pairs if isinstance(p, (list, tuple)) and len(p) == 2]


# ---- continuity rules -------------------------------------------------------------------------

def continuity_constraints(text: str, beat_index: int) -> List[Dict[str, str]]:
    """Evaluate the project's continuity rules (laws/continuity_rules.json) against a beat's locked
    text. A rule applies when `whenTextContains` is present; its cases are tried in order and the
    first match supplies the constraint. Returns [] for a project without rules."""
    text_l = (text or "").casefold()
    out: List[Dict[str, str]] = []
    for rule in (continuity_rules().get("rules") or []):
        if not isinstance(rule, dict):
            continue
        trigger = str(rule.get("whenTextContains") or "").casefold()
        if trigger and trigger not in text_l:
            continue
        state = None
        for case in (rule.get("cases") or []):
            if not isinstance(case, dict):
                continue
            if case.get("default"):
                state = case.get("state"); break
            if any(str(t).casefold() in text_l for t in (case.get("whenNotContains") or [])):
                continue
            if case.get("whenContainsAny") and not any(
                    str(t).casefold() in text_l for t in case["whenContainsAny"]):
                continue
            if "beatIndexAtLeast" in case and beat_index < int(case["beatIndexAtLeast"]):
                continue
            state = case.get("state"); break
        if state:
            out.append({"label": str(rule.get("label") or rule.get("id") or "continuity"),
                        "value": str(state), "severity": str(rule.get("severity") or "critical")})
    return out


def state_from_markers(text: str) -> Optional[str]:
    """The identity state whose markers appear in a shot's continuity text (continuity_rules.json →
    stateMarkers, tried in order), or None."""
    text_l = (text or "").casefold()
    for entry in (continuity_rules().get("stateMarkers") or []):
        if not isinstance(entry, dict):
            continue
        if any(str(m).casefold() in text_l for m in (entry.get("markers") or [])):
            return str(entry.get("state") or "") or None
    return None


# ---- chairs (the project's taste overlays) --------------------------------------------------

def _chair_file(name: str) -> Optional[str]:
    if not P.CHAIRS:
        return None
    for ext in (".json", ".md"):
        candidate = os.path.join(P.CHAIRS, name + ext)
        if os.path.exists(candidate):
            return candidate
    return None


@lru_cache(maxsize=None)
def room() -> Dict[str, Any]:
    """chairs/room.json — the creative room's own voice and any role-level flavour text."""
    return _load(_chair_file("room"))


def room_voice(default: str = "a professional animation studio voice") -> str:
    return str(room().get("voice") or default)


def chair_taste(role: str) -> str:
    """chairs/<role>.md — the project's taste overlay for a generic craft chair, or ""."""
    path = _chair_file(role)
    if not path or not path.endswith(".md"):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def director_grammar() -> Dict[str, Any]:
    """The project's own Director grammar - style paragraph, cast motion vocabulary, appearance
    words, canon blocks (laws/director_grammar.json); {} when the project declares none."""
    import paths as _paths
    return _load(getattr(_paths, "DIRECTOR_GRAMMAR", None))
