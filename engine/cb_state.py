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
import cb_quality
import cb_render
import cb_audio_authority
import cb_rough_cut


POLICY_VERSION = "canon-locked-current-direction-outcome-approval-v5"

_SHOT_STAGE_DEPENDENCIES = {
    "direction": {
        "preserved": ["scenelook"],
        "invalidated": ["direction", "keyframe", "voice", "animation", "continuity", "final"],
    },
    "keyframe": {
        "preserved": ["direction", "scenelook", "voice"],
        "invalidated": ["keyframe", "animation", "continuity", "final"],
    },
    "voice": {
        "preserved": ["direction", "scenelook", "keyframe"],
        "invalidated": ["voice", "animation", "continuity", "final"],
    },
    "animation": {
        "preserved": ["direction", "scenelook", "keyframe", "voice"],
        "invalidated": ["animation", "continuity", "final"],
    },
}


def _amendment_stage(scope):
    explicit = str(scope.get("changedStage") or scope.get("stage") or "").strip().lower()
    aliases = {"see": "keyframe", "hear": "voice", "watch": "animation"}
    explicit = aliases.get(explicit, explicit)
    if explicit in _SHOT_STAGE_DEPENDENCIES:
        return explicit
    if scope.get("kind") == "dialogue-correction":
        return "voice"
    return None


def _scoped_shot_amendment(intake, scene, pkg):
    """Describe a same-scene edit that may reuse the previous signed package as a base.

    This is a presentation/workflow allowance, not a generation-lineage bypass.  It keeps
    sibling shots and approved visual inputs visible while the named shot's changed
    dependencies are rebuilt and re-approved.
    """
    scope = intake.get("scriptChangeScope") or {}
    shot_id = str(scope.get("shotId") or "").strip()
    package_script = (pkg.get("sourceScript") or {}).get("scriptVersionId")
    try:
        current_scene = int("".join(ch for ch in str(scene) if ch.isdigit()) or "0")
        changed_scene = int("".join(
            ch for ch in str(scope.get("scene")) if ch.isdigit()) or "0")
    except (TypeError, ValueError):
        return None
    changed_stage = _amendment_stage(scope)
    explicit = next((item for item in reversed(pkg.get("scopedAmendments") or [])
                     if item.get("shotId") == shot_id and
                     item.get("scriptVersionId") == intake.get("scriptVersionId") and
                     item.get("kind") == scope.get("kind") and
                     item.get("baseScriptVersionId", package_script) == package_script), None)
    if not (
        changed_stage and shot_id and
        current_scene and current_scene == changed_scene and
        (package_script == intake.get("previousScriptVersionId") or explicit)
    ):
        return None
    package_shots = {shot.get("shotId") for shot in _active_package_shots(pkg)}
    if shot_id not in package_shots:
        return None
    dependency = _SHOT_STAGE_DEPENDENCIES[changed_stage]
    return {
        "active": True,
        "shotId": shot_id,
        "kind": scope.get("kind"),
        "changedStage": changed_stage,
        "preservedStages": list(dependency["preserved"]),
        "invalidatedStages": list(dependency["invalidated"]),
        "previousScriptVersionId": intake.get("previousScriptVersionId"),
        "currentScriptVersionId": intake.get("scriptVersionId"),
        "record": explicit,
    }


def _read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return None


def _stage(state, sub=None, **extra):
    return {"state": state, **({"sub": sub} if sub else {}), **extra}


def _with_quality(payload, pkg=None):
    """Attach one quality view derived from this exact state/package snapshot."""
    payload["qualityCompass"] = cb_quality.quality_compass(payload, pkg)
    return payload


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


def _approved_file_intact(record):
    path = (record or {}).get("path")
    if not ((record or {}).get("approved") and path and os.path.exists(path)):
        return False
    content_hash = (record or {}).get("contentHash")
    return not content_hash or content_hash == cb_render._sha256_file(path)


def _storyboard_status(scene, episode, intake):
    path = cb_render._storyboard_path(scene, episode)
    storyboard = _read_json(path)
    if not storyboard:
        return None, False, "missing"
    signature = storyboard.get("inputSignature") or {}
    source_version = (storyboard.get("sourceScript") or {}).get("scriptVersionId")
    inputs = signature.get("inputs") or {}
    active_beat_digest = intake.get("canonicalBeatPackageDigest")
    active_canon_digest = (intake.get("canonProfileDigests") or {}).get("storyboard")
    if signature.get("kind") == "scene-storyboard-snapshot":
        expected_inputs = {
            "scriptVersionId": intake.get("scriptVersionId"),
            "beatPackageDigest": active_beat_digest,
            "sceneNumber": str(storyboard.get("sceneNumber")),
            "sourceBeatIds": [beat.get("sourceBeatId") for beat in storyboard.get("beats") or []],
            "shotIds": [shot.get("shotId") for shot in storyboard.get("shots") or []],
        }
        signature_ok = cb_lineage.signature_matches(
            signature, "scene-storyboard-snapshot", expected_inputs)
        canon_ok = True
    else:
        signature_ok = cb_lineage.signature_matches(
            signature, "scene-storyboard", inputs)
        canon_ok = inputs.get("canonProfileDigest") == active_canon_digest
    scope = intake.get("scriptChangeScope") or {}
    try:
        scene_number = int("".join(ch for ch in str(scene) if ch.isdigit()) or "0")
        changed_scene = int("".join(ch for ch in str(scope.get("scene")) if ch.isdigit()) or "0")
    except (TypeError, ValueError):
        scene_number = changed_scene = 0
    scoped_previous = bool(
        ((scope.get("kind") == "dialogue-format-cleanup") or
         (scope.get("kind") == "dialogue-correction" and scene_number and
          changed_scene and scene_number < changed_scene)) and
        source_version)
    if scoped_previous and signature.get("kind") == "scene-storyboard-snapshot":
        # Its own signed snapshot remains valid; only the episode-wide active script and
        # beat-package pointers advanced for a later-scene correction.
        signature_ok = cb_lineage.signature_matches(
            signature, "scene-storyboard-snapshot", inputs)
    version_current = source_version == intake.get("scriptVersionId") or scoped_previous
    beat_current = inputs.get("beatPackageDigest") == active_beat_digest or scoped_previous
    current = bool(
        intake.get("canonicalCurrent") and
        storyboard.get("approvalState") == "approved" and signature_ok and
        source_version and version_current and beat_current and canon_ok)
    reason = None
    if not intake.get("canonicalCurrent"):
        reason = "story-intake-source-contract-missing-or-stale"
    elif storyboard.get("approvalState") != "approved":
        reason = storyboard.get("approvalState") or "awaiting-human-storyboard-approval"
    elif not signature_ok:
        reason = "storyboard-input-signature-mismatch"
    elif not version_current:
        reason = "storyboard-script-version-mismatch"
    elif not beat_current:
        reason = "storyboard-beat-package-mismatch"
    elif not canon_ok:
        reason = "storyboard-canon-lock-mismatch"
    return storyboard, current, reason


def _shot_state(pkg, shot, scene, episode, scene_look_current, package_current,
                amendment=None):
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
    keyframe_screening = (
        keyframe_candidate.get("conformanceScreening") or
        keyframe_approval.get("conformanceScreening") or {})
    if needs_keyframe:
        keyframe = cb_render._keyframe_record_status(
            pkg, shot, keyframe_approval, scene, episode)
        stage_contract = cb_render._keyframe_stage_contract_report(keyframe_approval)
        candidate_current = _keyframe_candidate_current(
            pkg, shot, keyframe_candidate, scene, episode)
        if keyframe_candidate:
            if candidate_current and keyframe_screening.get("status") == "pass":
                kf = "awaiting"
            elif candidate_current:
                kf = "screening"
            else:
                kf = "staleInputs"
        elif keyframe["current"]:
            kf = "approved" if stage_contract["ready"] else "stageBlocked"
        elif (keyframe_approval and
              keyframe.get("reason") == "keyframe-conformance-not-passed"):
            kf = "screening"
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
            # Approved relay media may survive a scoped package refresh while the old
            # approval ledger is being rehydrated. A recorded predecessor final frame is
            # sufficient to show the handoff in SEE; it does not authorise WATCH spend.
            if not (source_state and source_state["current"]):
                final_frame = (cb_render.ROOT / "engine" / "media" / "shots" /
                               f"{episode}_{source_shot_id}_final_frame.png")
                if final_frame.is_file():
                    source_state = {"current": True, "reason": "verified predecessor final frame",
                                    "harvestFrame": str(final_frame)}
        keyframe_satisfied = bool(source_state and source_state["current"])
        kf = "inherited" if keyframe_satisfied else "waitingPrev"
        keyframe = source_state or {"current": False, "reason": "source-shot-not-approved"}
        candidate_current = False

    voice = cb_render._voice_approval_status(pkg, shot, scene, episode)
    talky = bool(cb_audio_authority.spoken_dialogue_lines(shot))
    voice_ok = voice["current"]
    # Once HEAR is signed, the immutable approved media bundle is the operational
    # performance direction. A later unapproved draft cannot make that decision stale.
    voice_direction_current = bool(voice_direction["current"] or voice_ok)
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
        (not needs_keyframe or stage_contract["ready"]) and
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
            "Waiting for the scene world",
            "the environment, palette and lighting anchor has not been generated from current direction",
            "locked",
        )
    elif kf == "staleInputs":
        label, sub, badge = (
            "Opening-frame inputs changed",
            "generate or select a fresh candidate from current inputs",
            "blocked",
        )
    elif kf == "screening":
        label, sub, badge = (
            "Opening frame held for identity check",
            keyframe_screening.get("reason") or
            "retry the objective identity and scale check; no media regeneration is needed",
            "blocked",
        )
    elif kf == "stageBlocked":
        label, sub, badge = (
            "Opening keyframe must be corrected",
            "Audio is ready as Seedance 2.5 SFX; no ElevenLabs track is required. "
            "The image-only blocker is: " + (stage_contract.get("reason") or
            "the approved image does not prove the required physical stage"),
            "blocked",
        )
    elif kf == "waitingPrev":
        label, sub, badge = (
            f"Waiting for {source_shot_id} final frame",
            "the source shot needs a current accepted animation take",
            "locked",
        )
    elif needs_keyframe and kf == "awaiting":
        label, sub, badge = "Keyframe awaiting your decision", None, "awaiting"
    elif needs_keyframe and not keyframe_satisfied:
        label, sub, badge = (
            "New keyframe required",
            None if cine["current"] else
            "direction will prepare automatically when you build the keyframe",
            "ready",
        )
    elif not voice_ok:
        label, sub, badge = (
            "Opening frame ready",
            ("performance direction will prepare automatically when you fire"
             if not voice_direction["current"] else
             "generate, listen and choose Accept or Iterate"),
            "ready",
        )
    elif not animation_direction["current"]:
        label, sub, badge = (
            "Ready to fire animation",
            "the Studio will prepare current Animation direction before showing the spend",
            "ready",
        )
    elif animation_state == "designed":
        label, sub, badge = "Ready to animate", None, "ready"
    elif animation_state == "candidates-pending":
        label, sub, badge = "Animation awaiting your decision", None, "awaiting"
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
            "Accepted animation is stale",
            "a direct prompt, frame, reference, voice or media input changed",
            "blocked",
        )
    elif not continuity_current:
        label, sub, badge = (
            "Animation accepted",
            "Director Review still needs a current sign-off",
            "ready",
        )
    else:
        label, sub, badge = "Complete", None, "approved"

    result = {
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
        "keyframeScreening": keyframe_screening,
        "current": {
            "cinematographyDirection": cine["current"],
            "keyframe": keyframe_satisfied,
            "keyframeCandidate": candidate_current,
            "voiceDirection": voice_direction_current,
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
            "voiceDirection": None if voice_direction_current else voice_direction["reason"],
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
            "approveKeyframe": bool(
                keyframe_candidate and candidate_current and
                keyframe_screening.get("status") == "pass"),
            "rescreenKeyframe": bool(
                package_current and scene_look_current and kf == "screening"),
            "prepareVoice": bool(package_current and talky),
            "generateVoice": bool(
                package_current and talky and voice_direction_current and
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
    if amendment and shot_id == amendment.get("shotId"):
        # A dialogue/timing amendment does not erase an approved opening image.  HEAR and
        # WATCH remain closed until the amended shot has a newly signed production record.
        changed_stage = amendment.get("changedStage") or "voice"
        preserved = set(
            amendment.get("preservedStages") or
            _SHOT_STAGE_DEPENDENCIES[changed_stage]["preserved"])
        if "keyframe" in preserved and _approved_file_intact(keyframe_approval):
            result["kf"] = "approved"
            result["keyframeSatisfied"] = True
            result["current"]["keyframe"] = True
        changed_stage_current = {
            "direction": bool(result["current"]["cinematographyDirection"]),
            "keyframe": bool(result["current"]["keyframe"]),
            "voice": bool(result["current"]["voice"]),
            "animation": bool(result["current"]["animation"]),
        }[changed_stage]
        result["amendment"] = {
            **amendment,
            "active": not changed_stage_current,
            "changedStageCurrent": changed_stage_current,
        }
        if changed_stage_current:
            # Recompute the first downstream action after any preserved approval has been
            # restored above. The initial action map was built before that scoped carry-forward.
            result["allowedActions"]["prepareAnimation"] = bool(
                package_current and scene_look_current and
                result["current"]["keyframe"] and result["current"]["voice"])
        if not changed_stage_current:
            if "voice" not in preserved:
                result["voiceOk"] = False
                result["current"]["voice"] = False
            result["animState"] = "amendment-pending"
            result["readyToAnimate"] = False
            phase = {"direction": "DIRECTION", "keyframe": "SEE",
                     "voice": "HEAR", "animation": "WATCH"}[changed_stage]
            result["label"] = f"Shot amendment needs {phase}"
            result["sub"] = (
                "Earlier approved stages are preserved. Review this scoped change; only its "
                "genuine downstream dependencies will reopen.")
            result["badgeState"] = "ready"
            result["current"]["animationDirection"] = False
            result["current"]["animationBatch"] = False
            result["current"]["animation"] = False
            result["current"]["directorReview"] = False
            result["current"]["continuity"] = False
            result["pending"]["voice"] = False
            result["pending"]["animation"] = False
            result["allowedActions"]["prepareAnimation"] = False
            result["allowedActions"]["fireAnimation"] = False
            result["allowedActions"]["approveAnimation"] = False
            result["allowedActions"]["reviewAnimation"] = False
    elif amendment:
        # Sibling shots retain the decisions made against the previous immutable package.
        # Verify every referenced file before displaying it as preserved.
        preserved_keyframe = _approved_file_intact(keyframe_approval)
        preserved_voice = _approved_file_intact(ledger.get("voiceApproval") or {})
        approved_take = ledger.get("approvedTake")
        preserved_animation = bool(
            ledger.get("status") == "approved" and approved_take and
            os.path.exists(approved_take))
        if preserved_keyframe:
            result["kf"] = "approved"
            result["keyframeSatisfied"] = True
            result["current"]["keyframe"] = True
        if preserved_voice:
            result["voiceOk"] = True
            result["current"]["voice"] = True
        if preserved_animation:
            result["animState"] = "approved"
            result["current"]["animation"] = True
            result["label"] = "Approved work preserved"
            result["sub"] = "This shot is unaffected by the scoped amendment."
            result["badgeState"] = "approved"
        result["amendment"] = {
            "active": False,
            "preservedFromSiblingAmendment": True,
            "changedShotId": amendment.get("shotId"),
        }
    return result


def _active_package_shots(pkg):
    """Return only production units that still belong to the live scene route."""
    retired = {"superseded", "archived", "inactive"}
    def is_retired(shot):
        status = str(shot.get("status") or "").strip().lower()
        return (status in retired or status.startswith("skipped-") or
                bool(shot.get("superseded")))
    return [
        shot for shot in (pkg.get("shots") or [])
        if not is_retired(shot)
    ]


def production_state(scene, episode="Ep1", intake=None):
    """Return the sole approval/readiness document for one scene."""
    scene = str(scene)
    intake = intake if intake is not None else cb_intake.intake_status(episode)
    script_current = bool(intake.get("hasScript"))
    canon_ready = bool(intake.get("canonLockCurrent") and
                       intake.get("canonEpisodeReady"))
    canon_summary = {
        "current": bool(intake.get("canonLockCurrent")),
        "episodeReady": bool(intake.get("canonEpisodeReady")),
        "manifestDigest": intake.get("canonLockDigest"),
        "profileDigests": intake.get("canonProfileDigests") or {},
        "blockers": intake.get("canonBlockers") or [],
        "warnings": intake.get("canonWarnings") or [],
    }
    storyboard, storyboard_current, storyboard_reason = _storyboard_status(
        scene, episode, intake)

    stages = {
        "script": _stage("approved" if script_current else "ready",
                         None if script_current else "upload a script"),
    }
    intake_current = bool(intake.get("canonicalCurrent"))
    if not script_current:
        stages["storyboard"] = _stage("locked")
    elif not canon_ready:
        first = (canon_summary["blockers"] or [{}])[0]
        stages["storyboard"] = _stage(
            "blocked", first.get("message") or "canon lock is missing, stale or incomplete")
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

    try:
        pkg, _ = cb_render.load_pkg(scene, episode)
        package_exists = True
        lineage = cb_render.lineage_status(pkg, scene, episode)
        amendment = _scoped_shot_amendment(intake, scene, pkg)
        preserved_scene = bool(
            not intake_current and lineage["current"] and storyboard and
            storyboard.get("approvalState") == "approved")
        if preserved_scene:
            storyboard_current = True
            stages["storyboard"] = _stage(
                "approved", "this scene is unchanged in the active script")
        package_current = bool(
            (pkg.get("validation") or {}).get("passed") and lineage["current"] and
            storyboard_current)
    except cb_render.Refused:
        pkg = None
        package_exists = False
        package_current = False
        amendment = None
        preserved_scene = False
        lineage = {"current": False, "reasonCodes": ["production-package-missing"]}

    if amendment:
        # Keep the signed package as the production baseline while the one named shot is
        # amended.  This does not make the package generation-current; per-shot actions
        # below keep the amended HEAR/WATCH path closed until it is resynchronised.
        package_current = bool((pkg.get("validation") or {}).get("passed"))
        stages["storyboard"] = _stage(
            "approved", "accepted direction retained; one shot amendment is in progress")

    if not pkg:
        downstream = (
            _stage("blocked", "approve and promote Story & Direction into production")
            if storyboard_current else _stage("locked"))
        for name in ("scenelook", "voice", "keyframe", "animation", "continuity", "final"):
            stages[name] = dict(downstream)
        return _with_quality({
            "policyVersion": POLICY_VERSION,
            "episode": episode,
            "scene": scene,
            "canonLock": canon_summary,
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
        })

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
    scene_look_current = bool(scene_look.get("current"))
    if amendment:
        carried_look = ((amendment.get("record") or {}).get("sceneLookPath") and {
            "path": (amendment.get("record") or {}).get("sceneLookPath"),
            "hash": (amendment.get("record") or {}).get("sceneLookContentHash"),
        }) or scene_look.get("active") or look_record.get("candidate") or \
            look_record.get("approved") or {}
        look_path = carried_look.get("path")
        scene_look_current = bool(
            look_path and os.path.exists(look_path) and
            carried_look.get("hash") == cb_render._sha256_file(look_path))

    if amendment and scene_look_current:
        stages["scenelook"] = _stage(
            "approved", "approved scene world preserved for the scoped shot amendment")
    elif production_block:
        stages["scenelook"] = production_block
    elif look_work.get("candidate") and not look_direction["current"]:
        stages["scenelook"] = _stage(
            "blocked", "Look direction inputs changed")
    elif not look_direction["current"]:
        stages["scenelook"] = _stage(
            "ready", "prepare current Look Development direction")
    elif scene_look.get("candidate"):
        stages["scenelook"] = _stage(
            "approved" if scene_look.get("candidateCurrent") else "awaiting",
            ("working world anchor is current; its proof is the first keyframe"
             if scene_look.get("candidateCurrent") else
             "the generated world anchor no longer matches current inputs"),
            approvedPlateStillCurrent=bool(scene_look.get("approvedCurrent")))
    elif scene_look_current:
        stages["scenelook"] = _stage("approved", "approved and current")
    elif scene_look.get("status") == "rejected":
        stages["scenelook"] = _stage("rejected", "ready for a new candidate")
    elif scene_look.get("status") == "stale":
        stages["scenelook"] = _stage(
            "ready", "world inputs changed; build a fresh working anchor")
    else:
        stages["scenelook"] = _stage(
            "ready", "direction ready; generate or select one plate candidate")

    shots = [
        _shot_state(pkg, shot, scene, episode, scene_look_current, package_current,
                    amendment=amendment)
        for shot in _active_package_shots(pkg)
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
            "approved", f"{approved_voice} of {len(talky)} accepted; timing current")
    elif pending_voice:
        stages["voice"] = _stage(
            "awaiting",
            f"{approved_voice} of {len(talky)} accepted; {pending_voice} awaiting review")
    else:
        stages["voice"] = _stage(
            "ready",
            (f"{approved_voice} performances accepted; build or refresh timing"
             if approved_voice == len(talky)
             else f"{approved_voice} of {len(talky)} performances accepted"))

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
        stages["keyframe"] = _stage("locked", "generate the current scene world first")
    elif not openers:
        stages["keyframe"] = _stage("approved", "no shot needs a separate opening frame")
    elif stale_keyframes:
        stages["keyframe"] = _stage(
            "blocked",
            f"{approved_keyframes} accepted; {stale_keyframes} have changed direct inputs")
    elif pending_keyframes:
        stages["keyframe"] = _stage(
            "awaiting",
            f"{approved_keyframes} accepted; {pending_keyframes} awaiting review")
    elif approved_keyframes == len(openers):
        stages["keyframe"] = _stage(
            "approved", f"{approved_keyframes} of {len(openers)} accepted")
    else:
        stages["keyframe"] = _stage(
            "ready", f"{approved_keyframes} of {len(openers)} accepted")

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
        stages["animation"] = _stage("locked", "generate the current scene world first")
    elif blocked_animation:
        stages["animation"] = _stage(
            "blocked", f"{blocked_animation} shot(s) need intervention")
    elif pending_animation:
        stages["animation"] = _stage(
            "awaiting",
            f"{approved_animation} accepted; {pending_animation} awaiting review")
    elif shots and approved_animation == len(shots):
        stages["animation"] = _stage(
            "approved", f"{approved_animation} of {len(shots)} accepted")
    else:
        stages["animation"] = _stage(
            "ready",
            f"{approved_animation} accepted; {ready_animation} ready; "
            f"{max(0, len(shots) - approved_animation - ready_animation)} waiting")

    if approved_animation == 0:
        stages["continuity"] = _stage("locked", "accept the first WATCH take to open Director's Seat")
    else:
        try:
            cut = cb_rough_cut.scene_status(
                episode, str(scene), out=cb_render.HERE.parent / "cb-output")
        except (OSError, ValueError) as exc:
            stages["continuity"] = _stage("blocked", f"Director's Seat could not load: {exc}")
        else:
            if cut["staleCount"]:
                stages["continuity"] = _stage(
                    "blocked", f"{cut['staleCount']} approved cut source(s) changed")
            elif cut["confirmedCurrent"]:
                stages["continuity"] = _stage(
                    "approved", f"{len(cut['sequence'])} approved take(s) locked in the scene cut")
            else:
                stages["continuity"] = _stage(
                    "ready", f"{cut['approvedCount']} of {cut['expectedCount']} approved take(s) ready in Director's Seat")

    post = cb_render.post_status(pkg, scene, episode)
    final_status = cb_render._department_record_status(
        pkg, None, "review-final", scene, episode)
    final_work = (pkg.get("departmentWork") or {}).get("review-final") or {}
    if stages["continuity"]["state"] != "approved":
        stages["final"] = _stage("locked", "lock the scene cut in Director's Seat first")
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
    if script_current and not canon_ready:
        first = (canon_summary["blockers"] or [{}])[0]
        blockers.append({
            "code": "CANON_LOCK_REQUIRED",
            "stage": "storyboard",
            "message": first.get("message") or
                       "The approved canon snapshot is missing, stale or incomplete.",
            "action": first.get("action") or
                      "Resolve the listed canon issue and explicitly re-lock canon.",
        })
    if script_current and not intake_current and not preserved_scene and not amendment:
        blockers.append({
            "code": "STORY_INTAKE_APPROVAL_REQUIRED",
            "stage": "storyboard",
            "message": "The active script has a pending Story & Direction update.",
            "action": (
                "Review and approve the current episode Story & Direction candidate."
                if intake.get("hasCandidate") and intake.get("candidateCurrent")
                else "Run Story & Direction for the active script."),
        })
    storyboard_approval = str((storyboard or {}).get("approvalState") or "")
    if storyboard and storyboard_approval != "approved" and not amendment:
        blockers.append({
            "code": "STORYBOARD_NOT_APPROVED",
            "stage": "storyboard",
            "message": "The current Story & Direction candidate needs a human decision.",
            "action": (
                "Run Story & Direction again from the human iteration note."
                if "reject" in storyboard_approval.lower() else
                "Review the candidate and choose Approve or Iterate."),
        })
    if not package_current and not blockers:
        blockers.append({
            "code": "STALE_PRODUCTION_GRAPH",
            "stage": "storyboard",
            "message": "Production package does not match the active script and storyboard.",
            "action": "Promote the current approved Story & Direction package.",
        })
    for shot in shots:
        if package_current and shot["badgeState"] in ("blocked", "locked"):
            blockers.append({
                "code": "SHOT_NOT_READY",
                "stage": "animation",
                "shotId": shot["shotId"],
                "message": shot["label"],
                "action": shot.get("sub") or "Resolve the named direct-input dependency.",
            })

    return _with_quality({
        "policyVersion": POLICY_VERSION,
        "episode": episode,
        "scene": scene,
        "canonLock": canon_summary,
        "packageExists": True,
        "packageCurrent": package_current,
        "preservedScene": preserved_scene,
        "scopedAmendment": amendment,
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
    }, pkg)


if __name__ == "__main__":
    import sys

    print(json.dumps(
        production_state(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Ep1"),
        indent=1,
        ensure_ascii=False,
    ))
