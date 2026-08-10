#!/usr/bin/env python3
"""Shared mechanical conformance helpers for keyframe, render and voice emission.

The helpers in this module never make creative decisions. They protect compiler output
from mechanical damage and give all three emission paths one versioned check registry.
"""
from __future__ import annotations

import re


AAA_PREFLIGHT_VERSION = "aaa-part-8-v2.1"
AAA_PREFLIGHT_CHECKS = (
    (1, "ending-state-present"),
    (2, "route-envelope-and-time-tiling"),
    (3, "character-budget"),
    (4, "camera-grammar-conflict"),
    (5, "brand-names"),
    (6, "geography-block-present"),
    (7, "motion-vocabulary"),
    (8, "numeric-holds"),
    (9, "shot-purpose-and-count"),
    (10, "reference-scope"),
    (11, "duplicate-action-sentences"),
    (12, "transition-continuity"),
    (13, "style-paragraph-verbatim"),
    (14, "music-policy-present"),
    (15, "complete-sentence-integrity"),
    (16, "approved-physical-staging-fidelity"),
)

# This registry is deliberately conservative. A path is implemented only when a
# deterministic check and a regression test exist. "Not relevant" still remains OPEN
# until the path mechanically declares and tests that non-applicability.
AAA_CONFORMANCE = {
    1: {"keyframe": "OPEN", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    2: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "IMPLEMENTED+TESTED"},
    3: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    4: {"keyframe": "OPEN", "render": "OPEN", "voice": "OPEN"},
    5: {"keyframe": "OPEN", "render": "OPEN", "voice": "OPEN"},
    6: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    7: {"keyframe": "OPEN", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    8: {"keyframe": "OPEN", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    9: {"keyframe": "OPEN", "render": "OPEN", "voice": "OPEN"},
    10: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    11: {"keyframe": "OPEN", "render": "OPEN", "voice": "OPEN"},
    12: {"keyframe": "OPEN", "render": "OPEN", "voice": "OPEN"},
    13: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    14: {"keyframe": "OPEN", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
    15: {"keyframe": "IMPLEMENTED+TESTED", "render": "IMPLEMENTED+TESTED", "voice": "IMPLEMENTED+TESTED"},
    16: {"keyframe": "OPEN", "render": "IMPLEMENTED+TESTED", "voice": "OPEN"},
}

_TERMINAL = re.compile(r'[.!?\u2026][\"\'\u201d\u2019)\]]*$')


class EmissionConformanceError(ValueError):
    pass


def normalize_prose(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def require_complete_sentence(value, *, context):
    """Reject empty or mechanically clipped prose before it reaches any provider."""
    text = normalize_prose(value)
    if not text:
        raise EmissionConformanceError(f"{context} is empty")
    if not _TERMINAL.search(text):
        raise EmissionConformanceError(
            f"{context} is not a complete sentence: {text!r}")
    return text


def compact_complete_sentence(value, *, max_words, context):
    """Compact only at an authored clause/sentence boundary, never mid-phrase."""
    text = normalize_prose(value)
    if not text:
        raise EmissionConformanceError(f"{context} is empty")
    if len(text.split()) <= max_words:
        return require_complete_sentence(_with_terminal(text), context=context)

    # Prefer a complete authored sentence. A comma is an acceptable clause boundary,
    # but the compiler owns the full stop it adds after that intact clause.
    boundaries = list(re.finditer(r"[.!?\u2026](?=\s|$)|,(?=\s)", text))
    candidates = [text[:match.end()].rstrip(" ,") for match in boundaries
                  if len(text[:match.end()].split()) <= max_words]
    if not candidates:
        words = text.split()
        # Synthetic/control prose is sometimes an exact repeated phrase. Collapse the
        # repetition rather than cutting an arbitrary word count through it.
        for unit_size in range(1, min(max_words, len(words)) + 1):
            if len(words) % unit_size == 0 and words == words[:unit_size] * (len(words) // unit_size):
                return require_complete_sentence(
                    _with_terminal(" ".join(words[:unit_size])), context=context)
        raise EmissionConformanceError(
            f"{context} cannot be compacted below {max_words} words without cutting prose")
    return require_complete_sentence(_with_terminal(candidates[-1]), context=context)


def _with_terminal(text):
    text = str(text or "").strip().rstrip(" ,;:")
    return text if _TERMINAL.search(text) else text + "."


def time_tiles(stages, duration_sec):
    """Return consecutive full-duration stage tiles, preserving valid authored tiles."""
    items = [dict(item) for item in stages]
    if not items:
        raise EmissionConformanceError("render stage plan is empty")
    duration = float(duration_sec)
    authored = all(item.get("startSec") is not None and item.get("endSec") is not None
                   for item in items)
    if authored:
        return items
    step = duration / len(items)
    for index, item in enumerate(items):
        item["startSec"] = round(index * step, 3)
        item["endSec"] = duration if index == len(items) - 1 else round((index + 1) * step, 3)
    return items


def dialogue_cues(dialogue_lines, *, duration_sec):
    """Validate and normalize audio-region ownership without copying spoken words."""
    cues = []
    duration = float(duration_sec)
    for index, line in enumerate(dialogue_lines):
        start = float(line.get("startSec"))
        end = float(line.get("endSec"))
        speaker = str(line.get("speaker") or "").strip()
        if not speaker or start < 0 or end <= start or end > duration + 0.001:
            raise EmissionConformanceError(
                f"audio cue {index + 1} is outside the approved 0-{duration:g}s route")
        cues.append({"startSec": start, "endSec": end, "speaker": speaker})
    return cues


def format_seconds(value):
    return f"{float(value):g}"


def character_instance_lock(characters):
    """Emit an exact visual subject count for multi-character image/video prompts."""
    names = []
    seen = set()
    for value in characters or []:
        name = normalize_prose(value)
        key = name.casefold()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    if len(names) < 2:
        return ""
    if len(names) == 2:
        subject_list = f"{names[0]} and one {names[1]}"
        duplicate_scope = "either character"
    else:
        subject_list = ", one ".join(names[:-1]) + f" and one {names[-1]}"
        duplicate_scope = "any character"
    return f"Exactly one {subject_list} throughout; no duplicates of {duplicate_scope}."
