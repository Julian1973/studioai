"""Declared scene commands and their explicit transaction boundary."""
from __future__ import annotations

import functools
import inspect
import hashlib
import json

import cb_db


_MEDIA_DECISIONS = {
    "approve_voice", "reject_voice", "approve_keyframe", "reject_keyframe",
    "approve_shot", "reject_shot", "approve_shot_edit", "reject_shot_edit",
    "approve_shot_comparison", "reject_shot_comparison",
}


def _decision_snapshot(module, scene, episode, shot_id):
    pkg, _ = module.load_pkg(scene, episode)
    shot = module._shot(pkg, shot_id)
    ledger = module._ledger(pkg, shot_id)
    return {"sourceVersion": pkg.get("revision"),
            "characters": shot.get("charactersInFrame") or [],
            "shot": shot, "ledger": ledger}


def _record_decision(name, arguments, scene, episode, before, after):
    import cb_learning
    note = str(arguments.get("correction") or arguments.get("note") or "")
    # Hash the actual before/after decision state so retried identical commands do not
    # manufacture corroborating evidence. Preserve both accepted and rejected pointers.
    identity = {"command": name, "episode": episode, "scene": str(scene),
                "shot": arguments.get("shot_id"), "note": note, "after": after}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()
    pointers = []
    for state in (before, after):
        ledger = state.get("ledger") or {}
        for field in ("approvedTake", "candidatePaths", "harvestFrame", "voPath",
                      "voRawPath", "voTimingPath", "voiceApproval",
                      "keyframeCandidate", "keyframeApproval"):
            if ledger.get(field):
                pointers.append({"field": field, "value": ledger[field]})
    cb_learning.capture_evidence(
        "approved" if name.startswith("approve") else "rejected", note,
        episode=episode, scene=str(scene), shot=arguments.get("shot_id"),
        role="Voice" if "voice" in name else "Cinematography" if "keyframe" in name else "Animation",
        sourceVersion=after.get("sourceVersion"), scope="shot", category="media-review",
        context=json.dumps({"command": name, "characters": after.get("characters") or [],
                            "decisionStateHash": key}), assetPointers=pointers,
        capturedBy=arguments.get("reviewed_by") or "Julian", decisionKey=key)


MUTATING_OPERATIONS = (
    "generate_scenelook_plate",
    "approve_scenelook",
    "reject_scenelook",
    "select_scenelook_source",
    "prepare_department",
    "save_department_candidate",
    "decide_department",
    "save_voice_working",
    "restore_voice_working",
    "voice_shot",
    "voice_scene",
    "regen_voice_shot",
    "approve_voice",
    "reject_voice",
    "restore_previous_voice_take",
    "animatic_scene",
    "build_keyframe",
    "generate_pose_reference",
    "select_pose_reference_source",
    "review_pose_reference",
    "qualify_pose_reference",
    "reuse_qualified_pose",
    "approve_pose_reference",
    "reject_pose_reference",
    "keyframe_shot",
    "select_keyframe_source",
    "approve_keyframe",
    "reject_keyframe",
    "save_seedance_working",
    "restore_seedance_working",
    "fire_shot",
    "next_shot",
    "approve_shot",
    "reject_shot",
    "edit_shot",
    "approve_shot_edit",
    "reject_shot_edit",
    "approve_shot_comparison",
    "reject_shot_comparison",
    "stitch_scene",
    "reopen_approved_shot",
    "import_animation_candidate",
    "import_approved_take",
    "recover_approved_shot",
    "set_continuity_mode",
    "bind_animation_location_reference",
)


def _scope(name, signature, args, kwargs):
    bound = signature.bind_partial(*args, **kwargs)
    if name == "voice_shot":
        package = bound.arguments["pkg"]
        return package.get("sceneNumber"), bound.arguments.get(
            "episode", package.get("episode", "Ep1")
        )
    return bound.arguments.get("scene"), bound.arguments.get("episode", "Ep1")


def protect(module, name, target):
    """Compose one declared scene command with its reentrant transaction lease."""
    if name not in MUTATING_OPERATIONS:
        raise ValueError(f"Undeclared scene command: {name}")
    signature = inspect.signature(target)

    @functools.wraps(target)
    def locked(*args, **kwargs):
        scene, episode = _scope(name, signature, args, kwargs)
        if scene is None:
            raise module.Refused(f"REFUSED - cannot determine scene scope for {name}")
        try:
            with cb_db.scene_lease(module.HERE.parent, episode, scene, f"cb_render.{name}"):
                arguments = signature.bind_partial(*args, **kwargs).arguments
                before = None
                if name in _MEDIA_DECISIONS:
                    try:
                        before = _decision_snapshot(module, scene, episode, arguments.get("shot_id"))
                    except Exception:
                        pass
                result = target(*args, **kwargs)
                if before is not None:
                    try:
                        after = _decision_snapshot(module, scene, episode, arguments.get("shot_id"))
                        _record_decision(name, arguments, scene, episode, before, after)
                    except Exception as exc:
                        arguments.get("log", print)(
                            f"LEARNING CAPTURE WARNING — media decision saved: {exc}")
                return result
        except cb_db.SceneBusy as exc:
            raise module.Refused(f"REFUSED - {exc}") from exc

    locked.__studio_mutation__ = {"command": name, "scope": "scene"}
    return locked
