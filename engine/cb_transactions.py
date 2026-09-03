"""Install scene-level mutation leases around the production runtime."""
from __future__ import annotations

import functools
import inspect

import cb_db


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
    "stitch_scene",
    # 2026-09-03 audit: these wrote the package outside the lease; a write landing during a
    # render made the next progress save a StateConflict and failed a paid candidate.
    "abandon_batch", "apply_scoped_dialogue_correction", "apply_scoped_voice_contract_correction",
    "bind_animation_location_reference", "cancel_spend_authorization", "decide_timing_slate",
    "import_animation_candidate", "import_approved_take", "override_model_limited",
    "recompile_animation_candidate", "recover_approved_shot", "register_existing_keyframe_ab",
    "reopen_approved_shot", "rescreen_keyframe_geometry", "save_opening_frame_layout",
    "save_watch_director_feedback", "select_keyframe_candidate", "select_voice_audition",
    "set_continuity_mode",
)


def _scope(name, signature, args, kwargs):
    bound = signature.bind_partial(*args, **kwargs)
    if name == "voice_shot":
        package = bound.arguments["pkg"]
        return package.get("sceneNumber"), bound.arguments.get(
            "episode", package.get("episode", "Ep1")
        )
    return bound.arguments.get("scene"), bound.arguments.get("episode", "Ep1")


def install(module):
    for name in MUTATING_OPERATIONS:
        target = getattr(module, name)
        signature = inspect.signature(target)

        @functools.wraps(target)
        def locked(*args, __name=name, __target=target, __signature=signature, **kwargs):
            scene, episode = _scope(__name, __signature, args, kwargs)
            if scene is None:
                raise module.Refused(
                    f"REFUSED - cannot determine scene scope for {__name}"
                )
            try:
                with cb_db.scene_lease(
                    module.HERE.parent, episode, scene, f"cb_render.{__name}"
                ):
                    return __target(*args, **kwargs)
            except cb_db.SceneBusy as exc:
                raise module.Refused(f"REFUSED - {exc}") from exc

        setattr(module, name, locked)
