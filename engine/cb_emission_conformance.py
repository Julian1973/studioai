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


def locked_dialogue_text(line):
    return normalize_prose(
        line.get("exactText") if line.get("exactText") is not None else line.get("text"))


def dialogue_words(value):
    text = str(value or "").replace("\u2018", "'").replace("\u2019", "'")
    return [word.casefold() for word in re.findall(r"[A-Za-z0-9']+", text)]


def dialogue_marker_pattern(value):
    words = dialogue_words(value)
    if not words:
        return re.compile(r"a^")
    between = r"[\s,.;:!\?\u2026\u2018\u2019'\"-]+"
    return re.compile(r"\{" + between.join(re.escape(word) for word in words) + r"\}", re.I)


def marker_word_matches(text, exact):
    expected = dialogue_words(exact)
    if not expected:
        return []
    return [
        "{" + value + "}"
        for value in re.findall(r"\{([^{}]+)\}", str(text or ""))
        if dialogue_words(value) == expected
    ]


def require_complete_sentence(value, *, context):
    """Reject empty or mechanically clipped prose before it reaches any provider."""
    text = normalize_prose(value)
    if not text:
        raise EmissionConformanceError(f"{context} is empty")
    if not _TERMINAL.search(text):
        raise EmissionConformanceError(
            f"{context} is not a complete sentence: {text!r}")
    return text


def ensure_complete_sentence(value, *, context):
    """Preserve the full authored sentence and add only missing terminal punctuation."""
    text = normalize_prose(value)
    if not text:
        raise EmissionConformanceError(f"{context} is empty")
    return require_complete_sentence(_with_terminal(text), context=context)


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
    """Validate and normalize dialogue ownership for stage assignment.

    Times are compiler-side routing data. They decide which stage owns a line but are
    never emitted into a Seedance prompt.
    """
    cues = []
    duration = float(duration_sec)
    for index, line in enumerate(dialogue_lines):
        try:
            start = float(
                line.get("startSec")
                if line.get("startSec") is not None else line.get("startsAtSec"))
            end = float((line.get("endSec") if line.get("endSec") is not None else (
                start + float(line["estimatedDurationSec"])
                if line.get("estimatedDurationSec") is not None else None
            )))
        except (TypeError, ValueError, KeyError) as exc:
            raise EmissionConformanceError(
                f"audio cue {index + 1} has no approved timing window") from exc
        speaker = str(line.get("speaker") or "").strip()
        if not speaker or start < 0 or end <= start or end > duration + 0.001:
            raise EmissionConformanceError(
                f"audio cue {index + 1} is outside the approved 0-{duration:g}s route")
        exact = locked_dialogue_text(line)
        if not exact:
            raise EmissionConformanceError(f"audio cue {index + 1} has no locked dialogue")
        cues.append({"startSec": start, "endSec": end, "speaker": speaker,
                     "exactText": exact,
                     "delivery": normalize_prose(line.get("delivery")),
                     "dialogueOccurrenceId": line.get("dialogueOccurrenceId")})
    return cues


def written_dialogue_direction(value):
    """Validate authored performance prose; never leak voice tags into video prompts."""
    direction = normalize_prose(value).strip(" .,:;-")
    if not direction:
        return ""
    lowered = direction.casefold()
    raw_tag = bool(re.fullmatch(r"\[?\s*[a-z_-]+\s*\]?", direction, re.I))
    dangling = lowered in {"the approved", "approved", "the approved delivery"}
    if raw_tag or dangling:
        raise EmissionConformanceError(
            f"dialogue direction must be written performance direction, not a raw token: "
            f"{direction!r}")
    return direction


def dialogue_placement_line(cue, *, direction="", hold_after=True):
    """Emit exact dialogue with typed direction and only its ruled post-line hold."""
    speaker = normalize_prose(cue.get("speaker"))
    exact = locked_dialogue_text(cue)
    if not speaker or not exact:
        raise EmissionConformanceError("dialogue placement requires speaker and exact words")
    performance = written_dialogue_direction(direction)
    if performance:
        # The typed hold flag owns pacing. Strip any specialist-authored copy
        # before deterministically emitting the ruled hold (or no hold) below.
        performance = re.sub(
            r"(?:^|[;,]\s*)\b(?:hold|pause|linger|wait)\b[^.;]*?"
            r"\bafter (?:the )?line(?: ends?)?\b[^.;]*[.;]?",
            "", performance, flags=re.I).strip(" .,:;-")
        if not hold_after and re.search(
                r"\b(?:hold|pause|linger|wait)\b[^.;]*?"
                r"\bafter (?:the )?line(?: ends?)?\b",
                performance, re.I):
            raise EmissionConformanceError(
                "dialogue direction contradicts holdAfterDialogue=false")
    prefix = f"Spoken action: {speaker}"
    if performance:
        prefix += f", {performance}"
    line = f"{prefix}: {{{exact}}}"
    if hold_after:
        line += " The pose holds a full beat after the line ends."
    return line


def drop_superseded_action_prefix(action, environment_contract):
    """R17: discard an obsolete character-action prefix before a world-first replacement.

    Director shot plans replace stage summaries. When an older action has accidentally
    been prepended to the explicit world-first marker, retaining both creates a direct
    contradiction. This is deliberately marker-led rather than character-specific.
    """
    text = normalize_prose(action)
    contract = " ".join(normalize_prose(item) for item in environment_contract or [])
    if not re.search(r"environment changes completely before (?:either|any) character reacts", contract, re.I):
        return text
    marker = re.search(r"\bBefore (?:either|any) character reacts\b", text, re.I)
    if not marker or not text[:marker.start()].strip():
        return text
    return text[marker.start():]


def is_instance_lock_equivalent(value, characters):
    """Return true when authored consistency prose already restates cast uniqueness."""
    text = normalize_prose(value).casefold()
    names = [normalize_prose(name).casefold() for name in characters or []
             if normalize_prose(name)]
    return (len(names) > 1 and all(name in text for name in names)
            and "exactly one" in text
            and any(word in text for word in ("duplicate", "duplicates", "blended")))


SINGLE_INSTANCE_DIALOGUE_LOCK = (
    "Use @Audio1 as the only voice authority. Only the character currently speaking "
    "in @Audio1 may move their mouth. "
    "Seedance 2.5 must provide the shot's directed non-verbal SFX, ambience and "
    "instrumental music; it must not generate speech, sung lyrics or vocal music. "
    "VERBATIM DIALOGUE LOCK — TRANSCRIPT ONLY. Every approved line below already exists "
    "once in @Audio1. Use the written transcript only to assign the correct speaker and "
    "mouth timing. Do not synthesize, repeat, dub, echo, layer or replace any spoken line. "
    "The final render must contain exactly one audible dialogue performance: the supplied "
    "@Audio1, unchanged."
)


def validate_dialogue_synthesis(prompt, dialogue_lines):
    """Validate the synthesis contract used by every Seedance render emission.

    The provider receives the verbatim words only to stage speaker attribution and lip
    sync. The approved audio reference is the sole audible performance authority and
    must never be accompanied by a synthesized duplicate.
    """
    text = str(prompt or "")
    low = text.casefold()
    lines = list(dialogue_lines or [])
    if not lines:
        return {"ready": True, "errors": [], "markers": []}

    errors = []
    required_phrases = (
        "@audio1",
        "sole authority",
        "voice identity",
        "cadence",
        "delivery",
        "mouth timing",
        "silence",
        "no alternative performance",
        "listeners remain silent and closed-mouth",
        "no narration",
        "no subtitles or captions",
        "transcript only",
        "already exists once in @audio1",
        "do not synthesize, repeat, dub, echo, layer or replace",
        "exactly one audible dialogue performance",
        "@audio1, unchanged",
    )
    for phrase in required_phrases:
        if phrase not in low:
            errors.append(f"dialogue authority is missing {phrase!r}")
    if not any(phrase in low for phrase in (
            "no extra words", "no improvised or extra words")):
        errors.append("dialogue authority is missing 'no extra words'")

    expected = []
    expected_counts = {}
    for line in lines:
        key = tuple(dialogue_words(locked_dialogue_text(line)))
        expected_counts[key] = expected_counts.get(key, 0) + 1
    counted = set()
    for index, line in enumerate(lines):
        speaker = normalize_prose(line.get("speaker"))
        exact = locked_dialogue_text(line)
        marker = "{" + exact + "}"
        expected.append(marker)
        exact_count = text.count(marker)
        matches = ([marker] * exact_count if exact_count else
                   marker_word_matches(text, exact))
        dialogue_key = tuple(dialogue_words(exact))
        if (dialogue_key not in counted and
                len(matches) != expected_counts[dialogue_key]):
            errors.append(
                f"dialogue line {index + 1} must appear exactly "
                f"{expected_counts[dialogue_key]} time(s) as {marker!r}")
        counted.add(dialogue_key)
        marker_pattern = re.escape(matches[0]) if matches else re.escape(marker)
        placement = re.compile(
            rf"(?:Dialogue placement|Spoken action):\s*{re.escape(speaker)}"
            rf"\b[^\n{{}}]*:\s*{marker_pattern}",
            re.I)
        if not placement.search(text):
            errors.append(
                f"dialogue line {index + 1} is not attributed to {speaker} in English")

    emitted = re.findall(r"\{([^{}]+)\}", text)
    expected_text = [locked_dialogue_text(line) for line in lines]
    if [dialogue_words(value) for value in emitted] != [
            dialogue_words(value) for value in expected_text]:
        errors.append("dialogue markers are invented, reordered or duplicated")
    return {"ready": not errors, "errors": errors, "markers": expected}


def format_seconds(value):
    return f"{float(value):g}"


def character_instance_lock(characters, *, medium="video"):
    """Emit an exact visual subject count for multi-character prompts.

    A still owns one image, so describing subjects as persisting "throughout" is both
    unnecessary and less direct for an image model. Video prompts retain the continuity
    wording because duplicate instances can appear after motion or occlusion.
    """
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
    if medium == "still":
        if len(names) == 2:
            return f"Exactly one {names[0]} and one {names[1]} appear in this image."
        subject_list = ", one ".join(names[:-1]) + f" and one {names[-1]}"
        return f"Exactly one {subject_list} appear in this image."
    if medium != "video":
        raise ValueError("medium must be 'still' or 'video'")
    if len(names) == 2:
        subject_list = f"{names[0]} and one {names[1]}"
        duplicate_scope = "either character"
    else:
        subject_list = ", one ".join(names[:-1]) + f" and one {names[-1]}"
        duplicate_scope = "any character"
    return f"Exactly one {subject_list} throughout; no duplicates of {duplicate_scope}."


def reference_slot_stability_line(bindings):
    """Emit the compact resolved slot map used for this production request."""
    grouped = []
    for slot, role in bindings or []:
        slot = str(slot or "").strip()
        role = " ".join(str(role or "").split()).strip()
        if slot and role:
            if grouped and grouped[-1][1] == role:
                grouped[-1][0].append(slot)
            else:
                grouped.append(([slot], role))
    if not grouped:
        return ""
    stable = [f"{'/'.join(slots)}={role}" for slots, role in grouped]
    return "Project-stable slots: " + "; ".join(stable) + ". Never swap roles."


def multi_angle_collapse_line(slot, character):
    """State that every turnaround angle belongs to one subject instance."""
    slot = str(slot or "").strip()
    character = " ".join(str(character or "").split()).strip()
    if not slot or not character:
        return ""
    return f"{slot}: all turnaround angles are one {character}, not extra characters."


def multi_angle_collapse_summary(bindings):
    identities = []
    for slot, character in bindings or []:
        slot = str(slot or "").strip()
        character = " ".join(str(character or "").split()).strip()
        if slot and character:
            identities.append(f"{slot}=one {character}")
    if not identities:
        return ""
    return ("Multi-angle collapse: " + "; ".join(identities) +
            "; views are angles, not extra characters.")
