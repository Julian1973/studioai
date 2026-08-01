#!/usr/bin/env python3
"""One zero-spend, front-to-back production preflight for the Studio."""
import hashlib
import json
import os
import pathlib
import shutil

import cb_gen
import cb_render
import cb_state


def _hash_text(value):
    return hashlib.sha256((value or "").encode()).hexdigest()


def _department(ledger, stage):
    return (((ledger.get("departmentWork") or {}).get(stage) or {}).get("approved") or {})


def _legacy_production_preflight(scene, episode="Ep1"):
    """Return every known blocker together; never mutate state or call a provider."""
    pkg, _ = cb_render.load_pkg(scene, episode)
    blockers, warnings, exact_inputs, shot_rows = [], [], {}, []

    def block(code, stage, message, action, shot_id=None):
        blockers.append({"code": code, "stage": stage, "shotId": shot_id,
                         "message": message, "action": action})

    if not (pkg.get("validation") or {}).get("passed"):
        block("PACKAGE_VALIDATION", "storyboard", "Production handover validation failed.",
              "Correct every reported handover error and approve Story & Direction again.")
    lineage = cb_render.lineage_status(pkg, scene, episode)
    if not lineage["current"]:
        block("STALE_PACKAGE", "storyboard", "Package and live storyboard do not match.",
              "Rebuild the package from the current approved storyboard.")
    try:
        storyboard_state = json.load(open(cb_render._storyboard_path(scene, episode))).get("approvalState")
    except Exception:
        storyboard_state = None
    if storyboard_state != "approved":
        block("STORYBOARD_NOT_APPROVED", "storyboard", "Story & Direction is not approved.",
              "Approve the current Story & Direction candidate.")

    look_record = cb_render._load_scenelook_rec(scene, episode)
    look_work = (look_record.get("departmentWork") or {}).get("look") or {}
    look_approval = look_work.get("approved") or {}
    look_prompt = ((look_approval.get("output") or {}).get("providerPrompt") or "").strip()
    look_ok = look_approval.get("packageRevision") == pkg.get("revision") and bool(look_prompt)
    if look_ok:
        exact_inputs["look"] = {"source": "approved-look-specialist", "prompt": look_prompt,
                                "promptHash": _hash_text(look_prompt)}
    else:
        block("LOOK_DIRECTION_NOT_APPROVED", "look", "No current approved Look direction.",
              "Review and approve the existing Look candidate." if look_work.get("candidate")
              else "Brief, review and approve Look Development.")

    scene_look = cb_render.scenelook_status(scene, episode)
    if not scene_look.get("current"):
        block("SCENE_LOOK_NOT_APPROVED", "look",
              f"Scene Look is {scene_look.get('status', 'missing')}.",
              "Approve or reject the pending Scene Look candidate." if scene_look.get("candidate")
              else "Generate one Scene Look candidate from approved direction, then approve it.")

    timing_slate = cb_render.timing_slate_status(scene, episode)
    if not timing_slate.get("current"):
        warnings.append({
            "code": "TIMING_SLATE_NOT_CURRENT", "stage": "voice",
            "message": (timing_slate.get("reason") or
                        "Build the timing slate from current approved performances "
                        "before committing final opening frames."),
        })
    else:
        exact_inputs["timingSlate"] = {
            "path": timing_slate.get("path"),
            "generatedAt": timing_slate.get("generatedAt"),
        }

    for provider in ("fal", "elevenlabs"):
        if provider == "elevenlabs" and not any(s.get("dialogueLines") for s in pkg.get("shots") or []):
            continue
        try:
            cb_render._require_confirmed_billing(provider)
        except cb_render.Refused as exc:
            block("BILLING_NOT_CONFIRMED", "configuration", str(exc),
                  f"Confirm the {provider} plan and billing cadence in billing_profile.json.")
    if cb_gen.IMAGE_PROVIDER == "seedream" and not cb_gen.FAL_KEY:
        block("CONFIG_FAL_KEY", "configuration", "FAL_KEY is not configured.",
              "Preserve the Desktop .env or add the fal.ai key before paid work.")
    if any(s.get("dialogueLines") for s in pkg.get("shots") or []) and not cb_gen.ELEVEN_KEY:
        block("CONFIG_ELEVENLABS_KEY", "configuration", "ELEVENLABS_API_KEY is not configured.",
              "Preserve the Desktop .env or add the ElevenLabs key before voice work.")
    if cb_gen.IMAGE_PROVIDER == "seedream" and not cb_gen.SEEDREAM_T2I_ENDPOINT:
        warnings.append({"code": "SCENE_LOOK_REFERENCE_REQUIRED", "stage": "look",
                         "message": "Text-to-image is unset; explicitly select a Scene Look reference."})
    if shutil.which("ffmpeg") is None:
        block("CONFIG_FFMPEG", "configuration", "ffmpeg is unavailable.",
              "Install ffmpeg before frame extraction and stitching.")

    characters = cb_render._characters_cfg()
    for shot in pkg.get("shots") or []:
        sid, ledger = shot["shotId"], cb_render._ledger(pkg, shot["shotId"])
        stages, input_row = {}, {}

        cine = _department(ledger, "cinematography")
        cine_prompt = ((cine.get("output") or {}).get("providerPrompt") or "").strip()
        cine_ok = cine.get("packageRevision") == pkg.get("revision") and bool(cine_prompt)
        stages["cinematography"] = "approved" if cine_ok else "needed"
        if not cine_ok:
            block("CINEMATOGRAPHY_NOT_APPROVED", "keyframe", "No current Cinematography direction.",
                  "Brief, review and approve Cinematography.", sid)
        else:
            input_row["keyframePrompt"] = cine_prompt
            input_row["keyframePromptHash"] = _hash_text(cine_prompt)

        if shot.get("sourceType") == "opener":
            approval = ledger.get("keyframeApproval") or {}
            key_ok = (approval.get("approved") and
                      approval.get("packageRevision") == pkg.get("revision") and
                      os.path.exists(approval.get("path") or ""))
            stages["keyframe"] = "approved" if key_ok else (
                "awaiting" if ledger.get("keyframeCandidate") else "needed")
            if not key_ok:
                block("KEYFRAME_NOT_APPROVED", "keyframe", "No current approved opening frame.",
                      "Approve or reject the pending opening frame." if ledger.get("keyframeCandidate")
                      else "Generate or deliberately select an opening frame, then approve it.", sid)
        else:
            source = cb_render._ledger(pkg, shot.get("sourceShotId")) if shot.get("sourceShotId") else {}
            relay_ok = (source.get("status") == "approved" and
                        os.path.exists(source.get("harvestFrame") or "") and
                        (source.get("approval") or {}).get("packageRevision") == pkg.get("revision"))
            stages["keyframe"] = "inherited" if relay_ok else "waiting-for-previous-shot"
            if not relay_ok:
                block("RELAY_FRAME_NOT_READY", "keyframe", "Previous approved final frame is not ready.",
                      f"Approve {shot.get('sourceShotId')}'s animation first.", sid)

        if scene_look.get("current"):
            try:
                cb_render._slot_paths(shot, "referenceSlots", None, scene, episode, characters)
            except cb_render.Refused as exc:
                block("REFERENCE_MISSING", "keyframe", str(exc),
                      "Restore the named approved identity/environment reference.", sid)

        if shot.get("dialogueLines"):
            voice = _department(ledger, "voice")
            voice_lines = (voice.get("output") or {}).get("lines") or []
            voice_ok = voice.get("packageRevision") == pkg.get("revision") and bool(voice_lines)
            if not voice_ok:
                block("VOICE_DIRECTION_NOT_APPROVED", "voice", "No current Voice direction.",
                      "Brief, review and approve Voice direction.", sid)
            else:
                input_row["voiceLines"] = [{"speaker": x.get("speaker"),
                                             "performedText": x.get("performedText")}
                                            for x in voice_lines]
            missing_voice_ids = [ln["speaker"] for ln in shot.get("dialogueLines") or []
                                 if not (characters.get(cb_render._resolve_char(
                                     ln["speaker"], characters)) or {}).get("voiceId")]
            if missing_voice_ids:
                block("VOICE_ID_MISSING", "voice",
                      "Missing voiceId for: " + ", ".join(sorted(set(missing_voice_ids))),
                      "Assign the canonical ElevenLabs voice IDs.", sid)
            take = ledger.get("voiceApproval") or {}
            take_ok = (take.get("approved") and
                       take.get("packageRevision") == pkg.get("revision") and
                       take.get("path") == ledger.get("voPath") and
                       os.path.exists(take.get("path") or "") and
                       (not take.get("contentHash") or
                        take.get("contentHash") == cb_render._sha256_file(take.get("path"))))
            stages["voice"] = "approved" if take_ok else (
                "awaiting" if ledger.get("voPath") else "needed")
            if not take_ok:
                block("VOICE_TAKE_NOT_APPROVED", "voice", "No current approved voice take.",
                      "Listen to and approve or reject the current take." if ledger.get("voPath")
                      else "Generate the approved Voice direction, then listen and approve it.", sid)
        else:
            stages["voice"] = "not-required"

        animation = _department(ledger, "animation")
        animation_prompt = ((animation.get("output") or {}).get("providerPrompt") or "").strip()
        animation_ok = animation.get("packageRevision") == pkg.get("revision") and bool(animation_prompt)
        animation_stale = False
        if animation_ok and animation.get("inputSignature"):
            try:
                animation_stale = (
                    animation["inputSignature"] !=
                    cb_render._animation_input_signature(pkg, shot, scene, episode))
            except cb_render.Refused:
                animation_stale = True
            animation_ok = not animation_stale
        stages["animationDirection"] = (
            "approved" if animation_ok else "stale" if animation_stale else "needed")
        if not animation_ok:
            if animation_stale:
                block("STALE_ANIMATION_DIRECTION", "animation",
                      "Animation direction no longer matches its approved production inputs.",
                      "Prepare and approve fresh Animation direction from the current opening "
                      "frame, Scene Look, references and voice take.", sid)
            else:
                block("ANIMATION_DIRECTION_NOT_APPROVED", "animation",
                      "No current Animation direction.",
                      "After opening frame and voice approval, brief, review and approve "
                      "Animation direction.", sid)
        else:
            input_row["animationPrompt"] = animation_prompt
            input_row["animationPromptHash"] = _hash_text(animation_prompt)
            if animation.get("inputSignature"):
                input_row["animationInputSignature"] = animation["inputSignature"]
        stages["animation"] = ledger.get("status") or "designed"
        take = ledger.get("approval") or {}
        take_ok = (ledger.get("status") == "approved" and
                   take.get("packageRevision") == pkg.get("revision") and
                   os.path.exists(ledger.get("approvedTake") or "") and
                   os.path.exists(ledger.get("harvestFrame") or ""))
        stages["animation"] = "approved" if take_ok else (
            "awaiting" if ledger.get("candidatePaths") else "needed")
        if not take_ok:
            block("ANIMATION_NOT_APPROVED", "animation",
                  "No current approved animation take and harvested final frame.",
                  "Approve or reject the pending candidate batch." if ledger.get("candidatePaths")
                  else "Generate a candidate batch from approved Animation direction, then approve one.",
                  sid)
        if input_row:
            exact_inputs.setdefault("shots", {})[sid] = input_row
        shot_rows.append({"shotId": sid, "sourceType": shot.get("sourceType"), "stages": stages})

    rank = {"storyboard": 0, "look": 1, "keyframe": 2, "voice": 3,
            "animation": 4, "configuration": 5}
    blockers.sort(key=lambda item: (rank.get(item["stage"], 99), item.get("shotId") or ""))
    all_approved = all(
        cb_render._ledger(pkg, s["shotId"]).get("status") == "approved" and
        (cb_render._ledger(pkg, s["shotId"]).get("approval") or {}).get("packageRevision")
        == pkg.get("revision")
        for s in pkg.get("shots") or [])
    next_action = blockers[0]["action"] if blockers else (
        "Scene is ready for final assembly and post review." if all_approved
        else "All prerequisites are current; generate the next animation candidate batch.")
    return {"ok": not blockers, "zeroSpend": True, "episode": episode, "scene": str(scene),
            "packageRevision": pkg.get("revision"), "lineage": lineage,
            "blockers": blockers, "warnings": warnings, "nextAction": next_action,
            "approvedInputs": exact_inputs, "sceneLook": scene_look,
            "timingSlate": timing_slate, "shots": shot_rows}


def production_preflight(scene, episode="Ep1", state=None):
    """Return every known blocker from the authoritative readiness policy.

    Configuration checks are appended here because they concern the local machine, not an
    approval. No approval or readiness fact is re-derived in this report.
    """
    state = state if state is not None else cb_state.production_state(scene, episode)
    blockers = list(state.get("blockers") or [])
    warnings = []

    def block(code, stage, message, action, shot_id=None):
        record = {"code": code, "stage": stage, "shotId": shot_id,
                  "message": message, "action": action}
        if not any(
                existing.get("code") == code and
                existing.get("shotId") == shot_id
                for existing in blockers):
            blockers.append(record)

    if state.get("packageCurrent"):
        scene_look = state.get("sceneLook") or {}
        if not scene_look.get("directionCurrent"):
            block("LOOK_DIRECTION_NOT_CURRENT", "look",
                  "Look Development direction is missing or stale.",
                  "Prepare and approve current Look Development direction.")
        if not scene_look.get("current"):
            block("SCENE_LOOK_NOT_CURRENT", "look",
                  "No current approved Scene Look plate is available.",
                  "Generate or select a plate from current direction, then approve it.")

        for shot in state.get("shots") or []:
            sid = shot["shotId"]
            current = shot.get("current") or {}
            if shot.get("needsKeyframe") and not current.get("cinematographyDirection"):
                block("CINEMATOGRAPHY_NOT_CURRENT", "keyframe",
                      "Cinematography direction is missing or stale.",
                      "Prepare and approve current Cinematography direction.", sid)
            if shot.get("needsKeyframe") and not current.get("keyframe"):
                block("KEYFRAME_NOT_CURRENT", "keyframe",
                      "No current approved opening frame is available.",
                      "Generate or select an opening frame, then approve it.", sid)
            if shot.get("talky") and not current.get("voiceDirection"):
                block("VOICE_DIRECTION_NOT_CURRENT", "voice",
                      "Voice direction is missing or stale.",
                      "Prepare and approve current Voice direction.", sid)
            if shot.get("talky") and not current.get("voice"):
                block("VOICE_TAKE_NOT_CURRENT", "voice",
                      "No current approved voice take is available.",
                      "Generate, listen to and approve the current performance.", sid)
            if not current.get("animationDirection"):
                block("ANIMATION_DIRECTION_NOT_CURRENT", "animation",
                      "Animation direction is missing or stale.",
                      "Prepare and approve direction from the current frame, references and voice.",
                      sid)
            if not current.get("animation"):
                block("ANIMATION_TAKE_NOT_CURRENT", "animation",
                      "No current approved animation take is available.",
                      "Generate a candidate batch and approve one current candidate.", sid)
            if current.get("animation") and not current.get("directorReview"):
                block("DIRECTOR_REVIEW_NOT_CURRENT", "continuity",
                      "The approved animation has no current Director Review sign-off.",
                      "Review the approved take and approve the review evidence.", sid)

    timing = state.get("timingSlate") or {}
    if not timing.get("current"):
        warnings.append({
            "code": "TIMING_SLATE_NOT_CURRENT",
            "stage": "voice",
            "message": timing.get("reason") or "Build the timing slate from current voice approvals.",
        })

    package = None
    try:
        package, _ = cb_render.load_pkg(scene, episode)
    except cb_render.Refused:
        pass

    for provider in ("fal", "elevenlabs"):
        if (provider == "elevenlabs" and package and
                not any(shot.get("dialogueLines") for shot in package.get("shots") or [])):
            continue
        try:
            cb_render._require_confirmed_billing(provider)
        except cb_render.Refused as exc:
            block("BILLING_NOT_CONFIRMED", "configuration", str(exc),
                  f"Confirm the {provider} plan and billing cadence in billing_profile.json.")
    if cb_gen.IMAGE_PROVIDER == "seedream" and not cb_gen.FAL_KEY:
        block("CONFIG_FAL_KEY", "configuration", "FAL_KEY is not configured.",
              "Preserve the Desktop .env or add the fal.ai key before paid work.")
    if (package and any(shot.get("dialogueLines") for shot in package.get("shots") or []) and
            not cb_gen.ELEVEN_KEY):
        block("CONFIG_ELEVENLABS_KEY", "configuration",
              "ELEVENLABS_API_KEY is not configured.",
              "Preserve the Desktop .env or add the ElevenLabs key before voice work.")
    if shutil.which("ffmpeg") is None:
        block("CONFIG_FFMPEG", "configuration", "ffmpeg is unavailable.",
              "Install ffmpeg before frame extraction and assembly.")

    rank = {"storyboard": 0, "look": 1, "keyframe": 2, "voice": 3,
            "animation": 4, "continuity": 5, "final": 6, "configuration": 7}
    blockers.sort(key=lambda item: (
        rank.get(item.get("stage"), 99), item.get("shotId") or "", item.get("code") or ""))
    next_action = (
        blockers[0]["action"] if blockers
        else "All current approvals are ready for final assembly and post review."
    )
    return {
        "ok": not blockers,
        "zeroSpend": True,
        "episode": episode,
        "scene": str(scene),
        "packageRevision": state.get("packageRevision"),
        "lineage": state.get("lineage"),
        "policyVersion": state.get("policyVersion"),
        "blockers": blockers,
        "warnings": warnings,
        "nextAction": next_action,
        "sceneLook": state.get("sceneLook"),
        "timingSlate": timing,
        "shots": state.get("shots") or [],
        "stages": state.get("stages") or {},
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(production_preflight(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Ep1"),
                     indent=1, ensure_ascii=False))
