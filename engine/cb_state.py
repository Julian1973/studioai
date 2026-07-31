#!/usr/bin/env python3
"""Authoritative, zero-spend production readiness for Crystal Bears Studio.

The renderer owns approval freshness. This module only composes those checks into one scene
and per-shot state document for the API, preflight report and UI. It never mutates a package
and cannot call a media provider.
"""
from __future__ import annotations

import json
import os
import pathlib

import cb_intake
import cb_lineage
import cb_render


POLICY_VERSION = "direct-input-readiness-v1"


def _read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return None


def _stage(state, sub=None, **extra):
    return {"state": state, **({"sub": sub} if sub else {}), **extra}


def _candidate_current(pkg, stage, shot_id, scene, episode, candidate):
    if not candidate:
        return False
    try:
        expected = cb_render._department_input_signature(
            pkg, stage, shot_id, scene, episode)
    except (cb_render.Refused, OSError, ValueError):
        return False
    return candidate.get("inputSignature") == expected


def _keyframe_candidate_current(pkg, shot, candidate, scene, episode):
    if not candidate or not candidate.get("path") or not os.path.exists(candidate["path"]):
        return False
    try:
        expected = cb_render._keyframe_record_input_signature(
            pkg, shot, candidate, scene, episode)
    except (cb_render.Refused, OSError, ValueError):
        return False
    return (
        candidate.get("inputSignature") == expected and
        candidate.get("contentHash") == cb_render._sha256_file(candidate["path"])
    )


def _batch_current(pkg, shot, ledger, scene, episode):
    batch = ledger.get("batch") or {}
    if batch.get("status") != "complete":
        return False
    fast = ((batch.get("envelope") or {}).get("tier") == "fast")
    try:
        expected = cb_render._animation_generation_signature(
            pkg, shot, scene, episode, fast=fast)
    except (cb_render.Refused, OSError, ValueError):
        return False
    recorded_files = batch.get("candidateHashes") or []
    current_files = [
        {"path": path, "sha256": (
            cb_render._sha256_file(path) if path and os.path.exists(path) else None)}
        for path in (ledger.get("candidatePaths") or [])
    ]
    return bool(recorded_files) and (
        batch.get("inputSignature") == expected and recorded_files == current_files)


def _storyboard_status(scene, episode, intake):
    path = cb_render._storyboard_path(scene, episode)
    storyboard = _read_json(path)
    if not storyboard:
        return None, False, "missing"
    signature = storyboard.get("inputSignature") or {}
    signature_ok = cb_lineage.signature_matches(
        signature, "scene-storyboard", signature.get("inputs") or {})
    source_version = (storyboard.get("sourceScript") or {}).get("scriptVersionId")
    inputs = signature.get("inputs") or {}
    active_beat_digest = intake.get("canonicalBeatPackageDigest")
    current = bool(
        intake.get("canonicalCurrent") and
        storyboard.get("approvalState") == "approved" and signature_ok and
        source_version and source_version == intake.get("scriptVersionId") and
        inputs.get("beatPackageDigest") == active_beat_digest)
    reason = None
    if not intake.get("canonicalCurrent"):
        reason = "story-intake-source-contract-missing-or-stale"
    elif storyboard.get("approvalState") != "approved":
        reason = storyboard.get("approvalState") or "awaiting-human-storyboard-approval"
    elif not signature_ok:
        reason = "storyboard-input-signature-mismatch"
    elif source_version != intake.get("scriptVersionId"):
        reason = "storyboard-script-version-mismatch"
    elif inputs.get("beatPackageDigest") != active_beat_digest:
        reason = "storyboard-beat-package-mismatch"
    return storyboard, current, reason


def _shot_state(pkg, shot, scene, episode, scene_look_current, package_current):
    shot_id = shot["shotId"]
    ledger = cb_render._ledger(pkg, shot_id)
    needs_keyframe = shot.get("sourceType") == "opener"

    cine = cb_render._department_record_status(
        pkg, shot_id, "cinematography", scene, episode)
    voice_direction = cb_render._department_record_status(
        pkg, shot_id, "voice", scene, episode)
    animation_direction = cb_render._department_record_status(
        pkg, shot_id, "animation", scene, episode)

    keyframe_approval = ledger.get("keyframeApproval") or {}
    keyframe_candidate = ledger.get("keyframeCandidate") or {}
    if needs_keyframe:
        keyframe = cb_render._keyframe_record_status(
            pkg, shot, keyframe_approval, scene, episode)
        candidate_current = _keyframe_candidate_current(
            pkg, shot, keyframe_candidate, scene, episode)
        if keyframe_candidate:
            kf = "awaiting" if candidate_current else "staleInputs"
        elif keyframe["current"]:
            kf = "approved"
        elif keyframe_approval:
            kf = "staleInputs"
        elif ledger.get("keyframeRejected"):
            kf = "rejected"
        else:
            kf = "ready"
        keyframe_satisfied = keyframe["current"]
        source_shot_id = None
    else:
        source_shot_id = shot.get("sourceShotId")
        source_state = None
        if source_shot_id:
            try:
                source_shot = cb_render._shot(pkg, source_shot_id)
                source_state = cb_render._animation_approval_status(
                    pkg, source_shot, scene, episode)
            except cb_render.Refused:
                source_state = None
        keyframe_satisfied = bool(source_state and source_state["current"])
        kf = "inherited" if keyframe_satisfied else "waitingPrev"
        keyframe = source_state or {"current": False, "reason": "source-shot-not-approved"}
        candidate_current = False

    voice = cb_render._voice_approval_status(pkg, shot, scene, episode)
    talky = bool(shot.get("dialogueLines"))
    voice_ok = voice["current"]
    animation = cb_render._animation_approval_status(
        pkg, shot, scene, episode)
    batch_current = _batch_current(pkg, shot, ledger, scene, episode)
    if animation["current"]:
        animation_state = "approved"
    elif ledger.get("status") == "approved":
        animation_state = "stale"
    elif ledger.get("status") == "candidates-pending":
        animation_state = "candidates-pending" if batch_current else "stale-batch"
    elif ledger.get("status") == "model-limited":
        animation_state = "model-limited"
    else:
        animation_state = "designed"

    review = cb_render._department_record_status(
        pkg, shot_id, "review-animation", scene, episode)
    review_work = ((ledger.get("departmentWork") or {}).get("review-animation") or {})
    continuity_current = bool(animation["current"] and review["current"])

    scene_look_gated = not scene_look_current
    ready_to_animate = bool(
        package_current and scene_look_current and keyframe_satisfied and voice_ok and
        animation_direction["current"] and
        animation_state not in ("approved", "candidates-pending", "model-limited"))

    if not package_current:
        label, sub, badge = (
            "Production handover is stale",
            "promote the current approved storyboard before generating",
            "blocked",
        )
    elif scene_look_gated:
        label, sub, badge = (
            "Waiting for current Scene Look approval",
            "the environment, palette and lighting anchor is not current",
            "locked",
        )
    elif kf == "staleInputs":
        label, sub, badge = (
            "Opening-frame inputs changed",
            "generate or select a fresh candidate from current inputs",
            "blocked",
        )
    elif kf == "waitingPrev":
        label, sub, badge = (
            f"Waiting for {source_shot_id} final frame",
            "the source shot needs a current approved animation take",
            "locked",
        )
    elif needs_keyframe and kf == "awaiting":
        label, sub, badge = "Keyframe awaiting approval", None, "awaiting"
    elif needs_keyframe and not keyframe_satisfied:
        label, sub, badge = (
            "New keyframe required",
            None if cine["current"] else "approve Cinematography direction before generation",
            "ready",
        )
    elif not voice_ok:
        label, sub, badge = (
            "Opening frame ready",
            ("approve Voice direction first" if not voice_direction["current"]
             else "generate and approve this shot's voice"),
            "ready",
        )
    elif not animation_direction["current"]:
        label, sub, badge = (
            "Approve Animation direction",
            "the specialist brief is missing or stale against current production inputs",
            "ready",
        )
    elif animation_state == "designed":
        label, sub, badge = "Ready to animate", None, "ready"
    elif animation_state == "candidates-pending":
        label, sub, badge = "Animation awaiting approval", None, "awaiting"
    elif animation_state == "stale-batch":
        label, sub, badge = (
            "Animation candidates are stale",
            "reject this batch and generate from current inputs",
            "blocked",
        )
    elif animation_state == "model-limited":
        label, sub, badge = "Animation blocked", "needs human redesign", "blocked"
    elif animation_state == "stale":
        label, sub, badge = (
            "Approved animation is stale",
            "a direct prompt, frame, reference, voice or media input changed",
            "blocked",
        )
    elif not continuity_current:
        label, sub, badge = (
            "Animation approved",
            "Director Review still needs a current sign-off",
            "ready",
        )
    else:
        label, sub, badge = "Complete", None, "approved"

    return {
        "shotId": shot_id,
        "sourceType": shot.get("sourceType"),
        "sourceShotId": source_shot_id,
        "needsKeyframe": needs_keyframe,
        "kf": kf,
        "keyframeSatisfied": keyframe_satisfied,
        "talky": talky,
        "voiceOk": voice_ok,
        "animState": animation_state,
        "readyToAnimate": ready_to_animate,
        "label": label,
        "sub": sub,
        "badgeState": badge,
        "sceneLookGated": scene_look_gated,
        "current": {
            "cinematographyDirection": cine["current"],
            "keyframe": keyframe_satisfied,
            "keyframeCandidate": candidate_current,
            "voiceDirection": voice_direction["current"],
            "voice": voice_ok,
            "animationDirection": animation_direction["current"],
            "animationBatch": batch_current,
            "animation": animation["current"],
            "directorReview": review["current"],
            "continuity": continuity_current,
        },
        "reasons": {
            "cinematographyDirection": cine["reason"],
            "keyframe": keyframe.get("reason"),
            "voiceDirection": voice_direction["reason"],
            "voice": voice["reason"],
            "animationDirection": animation_direction["reason"],
            "animation": animation["reason"],
            "directorReview": review["reason"],
        },
        "pending": {
            "keyframe": bool(keyframe_candidate),
            "voice": bool(ledger.get("voPath") and not voice_ok),
            "animation": ledger.get("status") == "candidates-pending",
            "directorReview": bool(review_work.get("candidate")),
        },
        "allowedActions": {
            "prepareCinematography": package_current,
            "generateKeyframe": bool(
                package_current and scene_look_current and needs_keyframe and
                cine["current"] and not keyframe_candidate),
            "approveKeyframe": bool(keyframe_candidate and candidate_current),
            "prepareVoice": bool(package_current and talky),
            "generateVoice": bool(
                package_current and talky and voice_direction["current"] and
                not voice["approved"]),
            "approveVoice": bool(
                talky and ledger.get("voPath") and not voice_ok),
            "prepareAnimation": bool(
                package_current and scene_look_current and keyframe_satisfied and voice_ok),
            "fireAnimation": ready_to_animate,
            "approveAnimation": bool(
                animation_state == "candidates-pending" and batch_current),
            "reviewAnimation": bool(animation["current"]),
        },
    }


def production_state(scene, episode="Ep1"):
    """Return the sole approval/readiness document for one scene."""
    scene = str(scene)
    intake = cb_intake.intake_status(episode)
    script_current = bool(intake.get("hasScript"))
    storyboard, storyboard_current, storyboard_reason = _storyboard_status(
        scene, episode, intake)

    stages = {
        "script": _stage("approved" if script_current else "ready",
                         None if script_current else "upload a script"),
    }
    intake_current = bool(intake.get("canonicalCurrent"))
    if not script_current:
        stages["storyboard"] = _stage("locked")
    elif not intake_current:
        if intake.get("hasCandidate") and intake.get("candidateCurrent"):
            stages["storyboard"] = _stage(
                "awaiting", "review and approve the episode Story & Direction candidate")
        else:
            stages["storyboard"] = _stage(
                "ready", "run Story & Direction for the active script")
    elif not storyboard:
        stages["storyboard"] = _stage("ready", "direct the scene from the current script")
    elif storyboard_current:
        stages["storyboard"] = _stage("approved")
    elif "reject" in str(storyboard.get("approvalState") or "").lower():
        stages["storyboard"] = _stage(
            "rejected", storyboard.get("humanNote") or storyboard_reason)
    elif storyboard.get("approvalState") == "approved":
        stages["storyboard"] = _stage("blocked", storyboard_reason)
    else:
        stages["storyboard"] = _stage("awaiting", storyboard_reason)

    if script_current and not intake_current:
        action = (
            "Review and approve the current episode Story & Direction candidate."
            if intake.get("hasCandidate") and intake.get("candidateCurrent")
            else "Run Story & Direction for the active script."
        )
        for name in ("scenelook", "voice", "keyframe", "animation", "continuity", "final"):
            stages[name] = _stage("locked")
        return {
            "policyVersion": POLICY_VERSION,
            "episode": episode,
            "scene": scene,
            "packageExists": False,
            "packageCurrent": False,
            "staleBeatPackageIgnored": bool(intake.get("hasCanonicalPackage")),
            "lineage": {"current": False, "reasonCodes": ["story-intake-not-approved"]},
            "stages": stages,
            "shots": [],
            "_per": [],
            "blockers": [{
                "code": "STORY_INTAKE_APPROVAL_REQUIRED",
                "stage": "storyboard",
                "message": "The active script has no current approved episode Story & Direction package.",
                "action": action,
            }],
        }

    try:
        pkg, _ = cb_render.load_pkg(scene, episode)
        package_exists = True
        lineage = cb_render.lineage_status(pkg, scene, episode)
        package_current = bool(
            (pkg.get("validation") or {}).get("passed") and lineage["current"] and
            storyboard_current)
    except cb_render.Refused:
        pkg = None
        package_exists = False
        package_current = False
        lineage = {"current": False, "reasonCodes": ["production-package-missing"]}

    if not pkg:
        downstream = (
            _stage("blocked", "approve and promote Story & Direction into production")
            if storyboard_current else _stage("locked"))
        for name in ("scenelook", "voice", "keyframe", "animation", "continuity", "final"):
            stages[name] = dict(downstream)
        return {
            "policyVersion": POLICY_VERSION,
            "episode": episode,
            "scene": scene,
            "packageExists": package_exists,
            "packageCurrent": False,
            "lineage": lineage,
            "stages": stages,
            "shots": [],
            "_per": [],
            "blockers": [{
                "code": "PRODUCTION_PACKAGE_MISSING",
                "stage": "storyboard",
                "message": "No current production handover exists for this scene.",
                "action": "Approve and promote Story & Direction.",
            }],
        }

    if not package_current:
        production_block = _stage(
            "blocked", "production handover does not match the active script and storyboard")
    else:
        production_block = None

    scene_look = cb_render.scenelook_status(scene, episode)
    look_record = cb_render._load_scenelook_rec(scene, episode)
    look_work = (look_record.get("departmentWork") or {}).get("look") or {}
    look_direction = cb_render._department_record_status(
        pkg, None, "look", scene, episode)
    look_candidate_current = _candidate_current(
        pkg, "look", None, scene, episode, look_work.get("candidate"))
    scene_look_current = bool(scene_look.get("current"))

    if production_block:
        stages["scenelook"] = production_block
    elif look_work.get("candidate"):
        stages["scenelook"] = _stage(
            "awaiting" if look_candidate_current else "blocked",
            "Look direction awaits approval" if look_candidate_current
            else "Look direction inputs changed")
    elif not look_direction["current"]:
        stages["scenelook"] = _stage(
            "ready", "brief and approve current Look Development direction")
    elif scene_look.get("candidate"):
        stages["scenelook"] = _stage(
            "awaiting", "a replacement plate awaits approval",
            approvedPlateStillCurrent=scene_look_current)
    elif scene_look_current:
        stages["scenelook"] = _stage("approved", "approved and current")
    elif scene_look.get("status") == "rejected":
        stages["scenelook"] = _stage("rejected", "ready for a new candidate")
    elif scene_look.get("status") == "stale":
        stages["scenelook"] = _stage(
            "blocked", "approved plate inputs or file content changed")
    else:
        stages["scenelook"] = _stage("ready", "generate or select one plate candidate")

    shots = [
        _shot_state(pkg, shot, scene, episode, scene_look_current, package_current)
        for shot in (pkg.get("shots") or [])
    ]

    talky = [shot for shot in shots if shot["talky"]]
    approved_voice = sum(1 for shot in talky if shot["current"]["voice"])
    pending_voice = sum(1 for shot in talky if shot["pending"]["voice"])
    timing = cb_render.timing_slate_status(scene, episode)
    if production_block:
        stages["voice"] = production_block
    elif not talky:
        stages["voice"] = (
            _stage("approved", "silent timing slate is current")
            if timing.get("current") else
            _stage("ready", "build the silent scene timing slate"))
    elif approved_voice == len(talky) and timing.get("current"):
        stages["voice"] = _stage(
            "approved", f"{approved_voice} of {len(talky)} approved; timing current")
    elif pending_voice:
        stages["voice"] = _stage(
            "awaiting",
            f"{approved_voice} of {len(talky)} approved; {pending_voice} awaiting review")
    else:
        stages["voice"] = _stage(
            "ready",
            (f"{approved_voice} performances approved; build or refresh timing"
             if approved_voice == len(talky)
             else f"{approved_voice} of {len(talky)} performances approved"))

    openers = [shot for shot in shots if shot["needsKeyframe"]]
    approved_keyframes = sum(
        1 for shot in openers if shot["current"]["keyframe"])
    pending_keyframes = sum(
        1 for shot in openers if shot["pending"]["keyframe"])
    stale_keyframes = sum(
        1 for shot in openers if shot["kf"] == "staleInputs")
    if production_block:
        stages["keyframe"] = production_block
    elif not scene_look_current:
        stages["keyframe"] = _stage("locked", "approve a current Scene Look first")
    elif not openers:
        stages["keyframe"] = _stage("approved", "no shot needs a separate opening frame")
    elif stale_keyframes:
        stages["keyframe"] = _stage(
            "blocked",
            f"{approved_keyframes} approved; {stale_keyframes} have changed direct inputs")
    elif pending_keyframes:
        stages["keyframe"] = _stage(
            "awaiting",
            f"{approved_keyframes} approved; {pending_keyframes} awaiting review")
    elif approved_keyframes == len(openers):
        stages["keyframe"] = _stage(
            "approved", f"{approved_keyframes} of {len(openers)} approved")
    else:
        stages["keyframe"] = _stage(
            "ready", f"{approved_keyframes} of {len(openers)} approved")

    approved_animation = sum(
        1 for shot in shots if shot["current"]["animation"])
    pending_animation = sum(
        1 for shot in shots if shot["animState"] == "candidates-pending")
    blocked_animation = sum(
        1 for shot in shots
        if shot["animState"] in ("stale", "stale-batch", "model-limited"))
    ready_animation = sum(1 for shot in shots if shot["readyToAnimate"])
    if production_block:
        stages["animation"] = production_block
    elif not scene_look_current:
        stages["animation"] = _stage("locked", "approve a current Scene Look first")
    elif blocked_animation:
        stages["animation"] = _stage(
            "blocked", f"{blocked_animation} shot(s) need intervention")
    elif pending_animation:
        stages["animation"] = _stage(
            "awaiting",
            f"{approved_animation} approved; {pending_animation} awaiting review")
    elif shots and approved_animation == len(shots):
        stages["animation"] = _stage(
            "approved", f"{approved_animation} of {len(shots)} approved")
    else:
        stages["animation"] = _stage(
            "ready",
            f"{approved_animation} approved; {ready_animation} ready; "
            f"{max(0, len(shots) - approved_animation - ready_animation)} waiting")

    continuity_count = sum(
        1 for shot in shots if shot["current"]["continuity"])
    pending_reviews = sum(
        1 for shot in shots if shot["pending"]["directorReview"])
    if stages["animation"]["state"] != "approved":
        stages["continuity"] = _stage("locked", "approve every current animation take first")
    elif pending_reviews:
        stages["continuity"] = _stage(
            "awaiting", f"{pending_reviews} Director Review decision(s) pending")
    elif shots and continuity_count == len(shots):
        stages["continuity"] = _stage(
            "approved", f"{continuity_count} of {len(shots)} reviewed")
    else:
        stages["continuity"] = _stage(
            "ready", f"{continuity_count} of {len(shots)} reviewed")

    post = cb_render.post_status(pkg, scene, episode)
    final_status = cb_render._department_record_status(
        pkg, None, "review-final", scene, episode)
    final_work = (pkg.get("departmentWork") or {}).get("review-final") or {}
    if stages["continuity"]["state"] != "approved":
        stages["final"] = _stage("locked", "approve every current Director Review first")
    elif post["candidate"]["exists"] and not post["candidate"]["current"]:
        stages["final"] = _stage("blocked", "post candidate is stale or changed; rebuild it")
    elif post["candidate"]["current"] and final_work.get("candidate"):
        stages["final"] = _stage(
            "awaiting" if _candidate_current(
                pkg, "review-final", None, scene, episode, final_work["candidate"])
            else "blocked",
            "mastered post candidate awaits a human decision")
    elif post["candidate"]["current"]:
        stages["final"] = _stage("ready", "run Final & Post review on the mastered candidate")
    elif post["approved"]["current"] and final_status["current"]:
        stages["final"] = _stage("approved", "QC-passed final master reviewed and approved")
    elif post["approved"]["exists"] and not post["approved"]["current"]:
        stages["final"] = _stage("blocked", "approved master is stale against current inputs")
    elif post["approved"]["current"]:
        stages["final"] = _stage("ready", "rerun Final & Post review on the current master")
    else:
        stages["final"] = _stage(
            "ready", "build conform, mix, captions, delivery masters and QC manifest")

    blockers = []
    if not package_current:
        blockers.append({
            "code": "STALE_PRODUCTION_GRAPH",
            "stage": "storyboard",
            "message": "Production package does not match the active script and storyboard.",
            "action": "Promote the current approved Story & Direction package.",
        })
    for shot in shots:
        if shot["badgeState"] in ("blocked", "locked"):
            blockers.append({
                "code": "SHOT_NOT_READY",
                "stage": "animation",
                "shotId": shot["shotId"],
                "message": shot["label"],
                "action": shot.get("sub") or "Resolve the named direct-input dependency.",
            })

    return {
        "policyVersion": POLICY_VERSION,
        "episode": episode,
        "scene": scene,
        "packageExists": True,
        "packageCurrent": package_current,
        "packageRevision": pkg.get("revision"),
        "lineage": lineage,
        "sceneLook": {
            "status": scene_look.get("status"),
            "current": scene_look_current,
            "directionCurrent": look_direction["current"],
        },
        "timingSlate": timing,
        "postProduction": {
            "candidate": {"exists": post["candidate"]["exists"],
                          "current": post["candidate"]["current"],
                          "reason": post["candidate"]["reason"],
                          "manifestDigest": (post["candidate"].get("manifest") or {}).get(
                              "manifestDigest")},
            "approved": {"exists": post["approved"]["exists"],
                         "current": post["approved"]["current"],
                         "reason": post["approved"]["reason"],
                         "manifestDigest": (post["approved"].get("manifest") or {}).get(
                             "manifestDigest")},
        },
        "stages": stages,
        "shots": shots,
        "_per": shots,
        "blockers": blockers,
    }


if __name__ == "__main__":
    import sys

    print(json.dumps(
        production_state(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Ep1"),
        indent=1,
        ensure_ascii=False,
    ))
