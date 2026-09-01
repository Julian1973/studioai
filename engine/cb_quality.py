#!/usr/bin/env python3
"""Deterministic, zero-spend creative quality projection.

This module never declares art "good" from metadata. It separates authored intent from
evidence on actual media and uses calm states for the workspace quality compass.
"""
from __future__ import annotations


QUALITY_SCHEMA_VERSION = 1
DIMENSION_ORDER = ("story", "performance", "picture", "sound", "finish")
VALID_STATES = ("clear", "attention", "waiting", "unassessed")


def _dimension(key, state, summary, evidence=None, question=None):
    if state not in VALID_STATES:
        raise ValueError(f"unknown quality state: {state}")
    return {
        "id": key,
        "label": {
            "story": "Story",
            "performance": "Performance",
            "picture": "Picture",
            "sound": "Sound",
            "finish": "Finish",
        }[key],
        "state": state,
        "summary": summary,
        "evidence": list(evidence or []),
        "directorQuestion": question,
    }


def _stage(state, key):
    return ((state.get("stages") or {}).get(key) or {}).get("state") or "locked"


def _current_shots(state):
    return state.get("shots") or []


def _legacy_statement(pkg):
    statement = (pkg or {}).get("directorStatement") or {}
    return not statement or any(
        str(value or "").lower().startswith(("n/a", "legacy storyboard"))
        for value in statement.values()
    )


def _story_dimension(state, pkg):
    canon = state.get("canonLock") or {}
    blockers = canon.get("blockers") or []
    if blockers:
        return _dimension(
            "story", "attention", blockers[0].get("message") or "Canon needs a decision.",
            ["Canon manifest itself is current" if canon.get("current")
             else "Canon manifest is not current"],
            "Which signed source should govern this conflict?",
        )
    storyboard_state = _stage(state, "storyboard")
    if storyboard_state in ("awaiting", "blocked", "rejected"):
        sub = ((state.get("stages") or {}).get("storyboard") or {}).get("sub")
        return _dimension(
            "story", "attention", sub or "Story & Direction needs a human decision.",
            [f"Story & Direction state: {storyboard_state}"],
            "Does the scene preserve the script and the intended audience experience?",
        )
    if storyboard_state != "approved" or not state.get("packageCurrent"):
        return _dimension(
            "story", "waiting", "The current scene direction has not reached production.",
            [f"Story & Direction state: {storyboard_state}"],
        )
    intent = (pkg or {}).get("creativeIntent") or {}
    beat_contracts = intent.get("beatExperienceContracts") or []
    complete_beats = bool(beat_contracts) and all(
        item.get("emotion") and item.get("comedy") for item in beat_contracts)
    if not intent or _legacy_statement(pkg) or not complete_beats:
        return _dimension(
            "story", "attention",
            "The production graph is current, but its approved audience/emotion/comedy "
            "intent is incomplete or legacy.",
            ["Script and Story & Direction are current"],
            "Redirect this scene with the current supervision contract before media spend.",
        )
    evidence = [
        "Immutable script and canon are current",
        "Approved scene treatment survives production handoff",
        f"{len(beat_contracts)} beat experience contract(s) preserved",
    ]
    if any(item.get("power") for item in beat_contracts):
        evidence.append("Crystal power moment is bound to canon and beat intent")
    return _dimension(
        "story", "clear", "The authored scene promise is current and structurally preserved.",
        evidence,
        "Is this still the most truthful and memorable version of the scene?",
    )


def _performance_dimension(state, pkg):
    if not state.get("packageCurrent") or not pkg:
        return _dimension(
            "performance", "waiting", "Performance follows approved scene direction.")
    shots = pkg.get("shots") or []
    missing = [
        shot.get("shotId") for shot in shots
        if not shot.get("performanceContractApproved") or
        not shot.get("characterTruthsApproved")
    ]
    if missing:
        return _dimension(
            "performance", "attention",
            f"{len(missing)} shot(s) lack character-specific performance truth.",
            [f"First incomplete shot: {missing[0]}"],
            "What would this character do that no other cast member would?",
        )
    reviewed = _stage(state, "continuity") == "approved"
    if not reviewed:
        return _dimension(
            "performance", "unassessed",
            "Character-specific acting is planned; the rendered performances are not all "
            "director-reviewed yet.",
            [f"{len(shots)} shot performance contract(s) current"],
            "While watching the cut, can we read thought before movement and reaction after it?",
        )
    return _dimension(
        "performance", "clear",
        "Every current rendered performance has a character-specific director review.",
        [f"{len(shots)} of {len(shots)} shot performances reviewed"],
        __import__("project_laws").review_question(
            "performance",
            "Do the characters' contrasting temperaments feel affectionate rather than mechanical?"),
    )


def _picture_dimension(state, pkg):
    if not state.get("packageCurrent") or not pkg:
        return _dimension("picture", "waiting", "Picture planning follows scene direction.")
    shots = pkg.get("shots") or []
    missing = [
        shot.get("shotId") for shot in shots
        if not shot.get("cinematographyContractApproved")
    ]
    if missing:
        return _dimension(
            "picture", "attention",
            f"{len(missing)} shot(s) lack a story-motivated cinematography contract.",
            [f"First incomplete shot: {missing[0]}"],
            "Whose experience does the camera express, and why is this view the right one?",
        )
    look = _stage(state, "scenelook")
    animation = _stage(state, "animation")
    review = _stage(state, "continuity")
    if review != "approved":
        return _dimension(
            "picture", "unassessed",
            "Camera and visual intent are planned; final motion, continuity and image quality "
            "are not all proven on rendered media.",
            [f"Look Development: {look}", f"Animation: {animation}",
             f"Director Review: {review}"],
            "Does every cut reveal a new idea, and do light and depth carry the emotional turn?",
        )
    return _dimension(
        "picture", "clear",
        "The current picture has approved look, camera, animation and continuity evidence.",
        [f"{len(shots)} shot cinematography contract(s) reviewed on media"],
        "Does the assembled scene feel designed as one visual sentence?",
    )


def _sound_dimension(state, pkg):
    if not state.get("packageCurrent") or not pkg:
        return _dimension("sound", "waiting", "Sound planning follows scene direction.")
    voice_state = _stage(state, "voice")
    if voice_state in ("blocked", "rejected"):
        return _dimension(
            "sound", "attention", "Voice or timing needs intervention.",
            [f"Voice & Timing: {voice_state}"],
            "Are the exact words performed toward the listener rather than merely read?",
        )
    if voice_state != "approved":
        return _dimension(
            "sound", "unassessed",
            "Exact dialogue intent exists, but voice and scene timing are not fully approved.",
            [f"Voice & Timing: {voice_state}"],
            "Do silence, breath, effects and score leave room for the joke and the feeling?",
        )
    final_state = _stage(state, "final")
    if final_state != "approved":
        return _dimension(
            "sound", "unassessed",
            "Voice and timing are current; the final scene mix is not yet approved.",
            ["Exact dialogue occurrences approved", "Timing slate current"],
            "Can every word be understood without flattening ambience, effects or music?",
        )
    return _dimension(
        "sound", "clear", "Voice, timing and final mix are current and approved.",
        ["Dialogue, mix and master share current lineage"],
    )


def _finish_dimension(state):
    final_state = _stage(state, "final")
    post = state.get("postProduction") or {}
    if final_state in ("blocked", "rejected"):
        return _dimension(
            "finish", "attention", "The delivery candidate is stale or failed review.",
            [f"Final Master: {final_state}"],
            "Which upstream cause should be corrected before rebuilding the master?",
        )
    if final_state == "approved":
        approved = post.get("approved") or {}
        return _dimension(
            "finish", "clear", "The QC-passed final master is current and human-approved.",
            [f"Manifest: {approved.get('manifestDigest') or 'current'}"],
            "After one uninterrupted viewing, is this the version we want children to remember?",
        )
    if final_state == "locked":
        return _dimension(
            "finish", "waiting", "Finishing waits for approved picture and director review.")
    candidate = post.get("candidate") or {}
    evidence = []
    if candidate.get("exists"):
        evidence.append("A post candidate exists")
    return _dimension(
        "finish", "unassessed",
        "Conform, mix, captions, delivery QC and final human review are not complete.",
        evidence,
    )


def quality_compass(state, pkg=None):
    """Return a compact quality projection from one coherent state/package snapshot."""
    current_pkg = pkg if state.get("packageCurrent") else None
    dimensions = [
        _story_dimension(state, current_pkg),
        _performance_dimension(state, current_pkg),
        _picture_dimension(state, current_pkg),
        _sound_dimension(state, current_pkg),
        _finish_dimension(state),
    ]
    counts = {name: sum(item["state"] == name for item in dimensions)
              for name in VALID_STATES}
    if counts["attention"]:
        overall = "attention"
    elif counts["waiting"]:
        overall = "waiting"
    elif counts["unassessed"]:
        overall = "unassessed"
    else:
        overall = "clear"
    return {
        "schemaVersion": QUALITY_SCHEMA_VERSION,
        "zeroSpend": True,
        "overall": overall,
        "dimensions": dimensions,
        "counts": counts,
        "claim": "Structural and evidence status only; artistic quality remains a human verdict.",
    }
