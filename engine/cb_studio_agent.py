#!/usr/bin/env python3
"""Read-only Studio Agent projection over the authoritative production pipeline.

The Studio Agent is deliberately not another workflow engine. It compiles the current
canon, script, approval/readiness policy, quality compass and preflight evidence into one
selection-aware HELP or PLAN brief. It has no write path and cannot import or call a
media provider.
"""
from __future__ import annotations

import json
import re

import cb_intake
import cb_lineage
import cb_production_preflight
import cb_state


AGENT_VERSION = "studio-agent-context-v2"
BRIEF_SCHEMA_VERSION = 2
VALID_MODES = ("HELP", "PLAN")
STAGE_ORDER = (
    "script",
    "storyboard",
    "scenelook",
    "voice",
    "keyframe",
    "animation",
    "continuity",
    "final",
)
STAGE_NAMES = {
    "script": "Script",
    "storyboard": "Story & Direction",
    "scenelook": "World Build",
    "voice": "Voice & Timing",
    "keyframe": "Keyframe",
    "animation": "Animation",
    "continuity": "Director Review",
    "final": "Final Master",
    "configuration": "Configuration",
}
STAGE_ALIASES = {"look": "scenelook"}
AUTO_PREP_BLOCKERS = {
    "LOOK_DIRECTION_NOT_CURRENT",
    "CINEMATOGRAPHY_NOT_CURRENT",
    "VOICE_DIRECTION_NOT_CURRENT",
    "ANIMATION_DIRECTION_NOT_CURRENT",
}
OUTCOME_BUILD_BLOCKERS = {
    "SCENE_LOOK_NOT_CURRENT",
    "KEYFRAME_NOT_CURRENT",
    "VOICE_TAKE_NOT_CURRENT",
    "ANIMATION_TAKE_NOT_CURRENT",
}


def _token(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "action"


def _record(record_id, label, **evidence):
    return {
        "id": record_id,
        "label": label,
        **({"evidence": evidence} if evidence else {}),
    }


def _first_open_stage(stages):
    for stage in STAGE_ORDER:
        status = (stages.get(stage) or {}).get("state")
        if status not in ("approved", "locked"):
            return stage, status or "blocked"
    return "final", "approved"


def _action_for(intake, state, preflight, shot_id=None, mode="HELP"):
    """Choose one navigation-only action without reconstructing readiness policy."""
    stages = state.get("stages") or {}
    if not intake.get("hasScript"):
        stage, status = "script", "ready"
        message = "Upload and register the script as an immutable version."
        blocker = None
    else:
        blocker = (preflight.get("blockers") or [None])[0]
        if blocker:
            stage = STAGE_ALIASES.get(
                blocker.get("stage"), blocker.get("stage") or "storyboard")
            if stage not in STAGE_NAMES:
                stage = "configuration"
            status = (stages.get(stage) or {}).get("state") or "blocked"
            message = blocker.get("action") or blocker.get("message")
        else:
            stage, status = _first_open_stage(stages)
            message = preflight.get("nextAction") or "Review the current production state."

    target_shot = blocker.get("shotId") if blocker else shot_id
    if blocker and (
            blocker.get("code") in AUTO_PREP_BLOCKERS or
            (blocker.get("code") in OUTCOME_BUILD_BLOCKERS and status != "awaiting")):
        action_type = "fire-outcome"
    elif status == "awaiting":
        action_type = "human-decision"
    elif status in ("blocked", "rejected") or blocker:
        action_type = "resolve-blocker"
    elif status == "approved" and stage == "final":
        action_type = "inspect-delivery"
    else:
        action_type = "free-preparation"
    action_id = "-".join(filter(None, (
        action_type,
        _token(stage),
        _token(target_shot) if target_shot else None,
        _token((blocker or {}).get("code")) if blocker else None,
    )))
    return {
        "actionId": action_id,
        "type": action_type,
        "stage": stage,
        "stageName": STAGE_NAMES.get(stage, stage),
        "shotId": target_shot,
        "label": message,
        "reason": (blocker or {}).get("message"),
        "blockerCode": (blocker or {}).get("code"),
        "navigation": {"stage": stage, **({"shotId": target_shot} if target_shot else {})},
        "execution": {
            "available": False,
            "mode": mode,
            "changesData": False,
            "canSpend": False,
            "reason": (
                "HELP mode can navigate and explain, but cannot execute work."
                if mode == "HELP"
                else "PLAN mode can prepare a creative plan, but cannot execute work."
            ),
        },
    }


def _facts(intake, state, next_action):
    built = []
    proven = []
    proposed = []
    canon = state.get("canonLock") or {}
    stages = state.get("stages") or {}

    if intake.get("hasScript"):
        built.append(_record(
            "immutable-script-version",
            f"Immutable script registered: {intake.get('scriptName') or 'active script'}",
            scriptVersionId=intake.get("scriptVersionId"),
        ))
    if intake.get("hasCandidate"):
        candidate = intake.get("candidate") or {}
        built.append(_record(
            "story-direction-candidate",
            "Story & Direction candidate exists",
            inputSignature=(candidate.get("inputSignature") or {}).get("digest"),
            current=bool(intake.get("candidateCurrent")),
        ))
        if not intake.get("canonicalCurrent") and intake.get("candidateCurrent"):
            proposed.append(_record(
                "story-direction-awaiting-decision",
                "Story & Direction remains a proposal until human approval",
                current=bool(intake.get("candidateCurrent")),
            ))
    if state.get("packageExists"):
        built.append(_record(
            "scene-production-package",
            "Scene production package exists",
            revision=state.get("packageRevision"),
        ))
    if state.get("shots"):
        built.append(_record(
            "typed-shot-contracts",
            f"{len(state['shots'])} typed shot contract(s) are in the production graph",
            count=len(state["shots"]),
        ))

    if canon.get("current"):
        proven.append(_record(
            "canon-manifest-current",
            "Canon manifest content matches its lock",
            manifestDigest=canon.get("manifestDigest"),
        ))
    if canon.get("episodeReady"):
        proven.append(_record(
            "episode-canon-ready",
            "The active script passes the locked episode canon checks",
            manifestDigest=canon.get("manifestDigest"),
        ))
    if intake.get("canonicalCurrent"):
        proven.append(_record(
            "story-intake-current",
            "Approved Story & Direction matches the active immutable script",
            beatPackageDigest=intake.get("canonicalBeatPackageDigest"),
        ))
    for stage in STAGE_ORDER:
        if (stages.get(stage) or {}).get("state") == "approved":
            label = (
                "Active script identity is current"
                if stage == "script"
                else "Scene world working anchor is current"
                if stage == "scenelook" and "working world anchor" in
                str((stages.get(stage) or {}).get("sub") or "")
                else f"{STAGE_NAMES[stage]} is approved against current dependencies"
            )
            proven.append(_record(
                f"stage-{stage}-approved",
                label,
            ))

    proposed.append(_record(
        "next-best-action",
        next_action["label"],
        actionId=next_action["actionId"],
        stage=next_action["stage"],
        shotId=next_action.get("shotId"),
    ))
    return {"built": built, "proven": proven, "proposed": proposed}


def _headline(scene, state, next_action):
    stages = state.get("stages") or {}
    stage = next_action["stage"]
    status = (stages.get(stage) or {}).get("state")
    label = next_action["stageName"]
    if status == "blocked" or next_action["type"] == "resolve-blocker":
        return f"Scene {scene} needs attention in {label}."
    if status == "awaiting":
        return f"Scene {scene} needs your decision at {label}."
    if all((stages.get(item) or {}).get("state") == "approved" for item in STAGE_ORDER):
        return f"Scene {scene} has a current approved master."
    return f"Scene {scene} is ready at {label}."


def _plan_for(state, next_action, decisions):
    """Build a concise creative plan without inventing canon or changing state."""
    stage = next_action["stage"]
    plans = {
        "script": {
            "objective": "Establish the screenplay as an immutable creative source.",
            "deliverables": [
                "Registered script version and source hash",
                "Scene and exact dialogue-occurrence inventory",
            ],
            "preserve": ["Every authored line, beat and scene boundary"],
        },
        "storyboard": {
            "objective": "Direct the scene as an audience experience before media spend.",
            "deliverables": [
                "Scene treatment with audience alignment and emotional turn",
                "Beat contracts for emotion, comedy and any canon-supported crystal power",
                "Shot design with performance, continuity and cinematography contracts",
            ],
            "preserve": [
                "Signed canon and exact dialogue occurrences",
                "Character-specific wants, pressure responses and comic roles",
            ],
        },
        "scenelook": {
            "objective": "Prove one coherent world, palette, lighting idea and material language.",
            "deliverables": [
                "Current signed scene-world working anchor",
                "Character, prop and location identity checks against locked references",
            ],
            "preserve": ["Approved story point of view and continuity state"],
        },
        "voice": {
            "objective": "Make the exact words feel thought, heard and answered in real time.",
            "deliverables": [
                "Character-specific voice direction and approved performances",
                "Timing slate with breath, silence, reactions and joke holds",
            ],
            "preserve": ["Exact words, speaker, listener and occurrence identity"],
        },
        "keyframe": {
            "objective": "Prove composition, lens intent, staging, depth and light before motion.",
            "deliverables": [
                "Current opening frame for each opener shot",
                "Camera and screen-direction check against the approved shot contract",
            ],
            "preserve": ["Character identity, geography and emotional point of view"],
        },
        "animation": {
            "objective": "Create readable thought, weight, contact, reaction and change over time.",
            "deliverables": [
                "Current animation candidates tied to approved direct inputs",
                "Picture, voice/lip-sync, identity drift and physical-comedy inspection",
            ],
            "preserve": [
                "Approved performance truth and comedy staging",
                "Opening-frame, voice, continuity and cinematography signatures",
            ],
        },
        "continuity": {
            "objective": "Judge the rendered scene as a cut, not as isolated generated clips.",
            "deliverables": [
                "Shot-level director decisions on story, acting, camera, physics and continuity",
                "Precise notes that identify picture, performance, voice or drift causes",
            ],
            "preserve": ["Approved takes and their complete dependency evidence"],
        },
        "final": {
            "objective": "Finish and approve one broadcast-ready scene master.",
            "deliverables": [
                "Conform, mix, captions, color-managed master and delivery derivatives",
                "Automated QC manifest plus uninterrupted human final viewing",
            ],
            "preserve": ["Approved picture, timing, audio and source lineage"],
        },
        "configuration": {
            "objective": "Restore a valid, secure and spend-safe production configuration.",
            "deliverables": ["Passing zero-spend preflight with explicit provider readiness"],
            "preserve": ["Secrets, signed approvals and current production artifacts"],
        },
    }
    plan = dict(plans.get(stage) or plans["configuration"])
    compass = state.get("qualityCompass") or {}
    plan["qualityQuestions"] = [
        item["directorQuestion"]
        for item in (compass.get("dimensions") or [])
        if item.get("directorQuestion") and item.get("state") != "clear"
    ]
    plan["humanDecisions"] = list(decisions)
    if decisions:
        plan["objective"] = (
            "Reconcile the named canon/script conflict against signed source evidence; "
            "do not choose or rewrite canon automatically."
        )
    plan["execution"] = next_action["execution"]
    return plan


def studio_agent_brief(scene, episode="Ep1", shot_id=None, mode="HELP"):
    """Compile one deterministic, read-only brief from authoritative zero-spend reads."""
    scene = str(scene)
    episode = str(episode)
    shot_id = str(shot_id) if shot_id else None
    mode = str(mode or "HELP").upper()
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of: {', '.join(VALID_MODES)}")

    intake = cb_intake.intake_status(episode)
    state = cb_state.production_state(scene, episode, intake=intake)
    preflight = cb_production_preflight.production_preflight(
        scene, episode, state=state)
    shots = state.get("shots") or []
    selected_shot = next((shot for shot in shots if shot.get("shotId") == shot_id), None)
    next_action = _action_for(
        intake, state, preflight, shot_id if selected_shot else None, mode=mode)
    facts = _facts(intake, state, next_action)
    canon = state.get("canonLock") or {}

    dependencies = {
        "agentVersion": AGENT_VERSION,
        "mode": mode,
        "policyVersion": state.get("policyVersion"),
        "episode": episode,
        "scene": scene,
        "selection": {"shotId": shot_id, "resolved": bool(selected_shot)} if shot_id else None,
        "scriptVersionId": intake.get("scriptVersionId"),
        "canonManifestDigest": canon.get("manifestDigest"),
        "canonProfileDigests": canon.get("profileDigests") or {},
        "beatPackageDigest": intake.get("canonicalBeatPackageDigest"),
        "packageRevision": state.get("packageRevision"),
        "stageStates": {
            stage: (state.get("stages", {}).get(stage) or {}).get("state")
            for stage in STAGE_ORDER
        },
        "selectedShotState": (
            {
                "shotId": selected_shot.get("shotId"),
                "label": selected_shot.get("label"),
                "badgeState": selected_shot.get("badgeState"),
                "current": selected_shot.get("current") or {},
            }
            if selected_shot else None
        ),
        "blockers": [
            {
                "code": item.get("code"),
                "stage": item.get("stage"),
                "shotId": item.get("shotId"),
                "message": item.get("message"),
            }
            for item in (preflight.get("blockers") or [])
        ],
        "qualityStates": {
            item.get("id"): item.get("state")
            for item in ((state.get("qualityCompass") or {}).get("dimensions") or [])
        },
    }
    signature = cb_lineage.dependency_signature("studio-agent-context", dependencies)
    canon_blockers = canon.get("blockers") or []
    decisions = [
        {
            "code": item.get("code"),
            "stage": "storyboard",
            "message": item.get("message"),
            "action": item.get("action"),
            "evidence": item.get("evidence"),
        }
        for item in canon_blockers
    ]

    return {
        "schemaVersion": BRIEF_SCHEMA_VERSION,
        "agentVersion": AGENT_VERSION,
        "briefId": f"studio-brief:sha256:{signature['digest']}",
        "mode": mode,
        "zeroSpend": True,
        "readOnly": True,
        "episode": episode,
        "scene": scene,
        "selection": {
            "type": "shot" if shot_id else "scene",
            "shotId": shot_id,
            "resolved": bool(selected_shot) if shot_id else True,
        },
        "headline": _headline(scene, state, next_action),
        "nextAction": next_action,
        "facts": facts,
        "decisions": decisions,
        "blockers": preflight.get("blockers") or [],
        "warnings": preflight.get("warnings") or [],
        "qualityCompass": state.get("qualityCompass") or {},
        "plan": _plan_for(state, next_action, decisions) if mode == "PLAN" else None,
        "context": {
            "show": {
                "canonCurrent": bool(canon.get("current")),
                "canonManifestDigest": canon.get("manifestDigest"),
                "canonProfileDigests": canon.get("profileDigests") or {},
            },
            "episode": {
                "scriptName": intake.get("scriptName"),
                "scriptVersionId": intake.get("scriptVersionId"),
                "storyDirectionCurrent": bool(intake.get("canonicalCurrent")),
                "beatPackageDigest": intake.get("canonicalBeatPackageDigest"),
            },
            "scene": {
                "sceneNumber": scene,
                "packageExists": bool(state.get("packageExists")),
                "packageCurrent": bool(state.get("packageCurrent")),
                "packageRevision": state.get("packageRevision"),
                "lineage": state.get("lineage") or {},
                "stages": state.get("stages") or {},
                "qualityCompass": state.get("qualityCompass") or {},
            },
            "shot": selected_shot,
            "task": {
                "mode": mode,
                "stage": next_action["stage"],
                "actionId": next_action["actionId"],
            },
        },
        "contextSignature": signature,
        "authority": {
            "may": [
                "read-current-state",
                "explain-evidence",
                "identify-blockers",
                "recommend-one-next-action",
                "navigate-to-existing-workspace",
                *(["draft-zero-spend-plan"] if mode == "PLAN" else []),
            ],
            "mayNot": [
                "change-canon",
                "approve-or-reject",
                "mutate-production-artifacts",
                "call-media-providers",
                "spend-credits",
                "retry-generation",
                "switch-provider",
            ],
        },
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(studio_agent_brief(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else "Ep1",
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else "HELP",
    ), indent=1, ensure_ascii=False))
