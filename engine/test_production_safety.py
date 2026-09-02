"""Zero-spend regression checks for the single approved production path."""
import copy

import cb_intake
import cb_production_preflight
import cb_render
import cb_canon
import cb_safety


def test_safety_layer_is_installed():
    assert cb_render.generate_scenelook_plate.__module__ == "cb_safety"
    assert cb_render._resolve_keyframe_prompt.__module__ == "cb_safety"
    assert cb_render.voice_shot.__module__ == "cb_safety"
    assert cb_render.fire_shot.__module__ == "cb_safety"


def test_show_specific_runtime_refuses_an_uninstalled_adapter(monkeypatch):
    monkeypatch.setattr(cb_render.P, "ENGINE_ADAPTER", "another-show-v1")
    try:
        cb_render._require_show_adapter()
    except cb_render.Refused as exc:
        assert "not supported" in str(exc)
        assert "no provider was contacted" in str(exc)
    else:
        raise AssertionError("Crystal Bears runtime accepted another show's adapter")


def test_preflight_keeps_unchanged_scene_usable_during_episode_story_direction_update(monkeypatch):
    intake = dict(cb_intake.intake_status("Ep1"))
    intake.update({
        "hasScript": True,
        "canonLockCurrent": True,
        "canonEpisodeReady": True,
        "canonicalCurrent": False,
        "hasCandidate": True,
        "candidateCurrent": True,
    })
    monkeypatch.setattr(cb_intake, "intake_status", lambda _episode: intake)

    report = cb_production_preflight.production_preflight("1", "Ep1")
    assert report["zeroSpend"] is True
    assert report["lineage"]["current"] is True
    codes = {item["code"] for item in report["blockers"]}
    assert "STORY_INTAKE_APPROVAL_REQUIRED" not in codes
    assert "CANON_LOCK_REQUIRED" not in codes
    assert "STALE_PRODUCTION_GRAPH" not in codes
    assert "SHOT_NOT_READY" in codes
    assert report["shots"]
    assert all(item["allowedActions"]["fireAnimation"] is False
               for item in report["shots"])
    assert report["stages"]["storyboard"]["state"] == "approved"
    assert report["providerCapabilities"]["selectionReady"] is True
    assert report["providerCapabilities"]["selectedVideoModelId"] == (
        "dreamina-seedance-2-5-260628")
    assert "VIDEO_PROVIDER_NOT_QUALIFIED" not in codes
    assert report["showProfile"]["showId"] == "crystal-bears"
    assert report["showProfile"]["adapterReady"] is True
    assert "Story & Direction" not in report["nextAction"]


def test_preflight_blocks_an_unqualified_selected_video_model(monkeypatch):
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "byteplus-seedance-2.0")
    report = cb_production_preflight.production_preflight("1", "Ep1")

    blockers = {item["code"]: item for item in report["blockers"]}
    assert "VIDEO_PROVIDER_NOT_QUALIFIED" in blockers
    assert "disabled" in blockers["VIDEO_PROVIDER_NOT_QUALIFIED"]["message"]
    assert report["providerCapabilities"]["selectionReady"] is False


def test_pose_preparation_is_internal_to_the_keyframe_build(monkeypatch):
    state = {
        "packageCurrent": True,
        "packageRevision": "test-revision",
        "lineage": {"current": True},
        "policyVersion": "test-policy",
        "blockers": [],
        "sceneLook": {"directionCurrent": True, "current": True},
        "timingSlate": {"current": True},
        "stages": {"keyframe": {"state": "ready"}},
        "shots": [{
            "shotId": "S1.SH1",
            "needsKeyframe": True,
            "talky": False,
            "pending": {"keyframe": False},
            "current": {
                "cinematographyDirection": True,
                "keyframe": False,
                "voiceDirection": True,
                "voice": True,
                "animationDirection": True,
                "animation": False,
                "directorReview": False,
            },
        }],
    }
    monkeypatch.setattr(
        cb_render, "pose_reference_status",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("preflight must not expose the internal pose workflow")))
    monkeypatch.setattr(
        cb_production_preflight, "_production_inputs",
        lambda *args, **kwargs: {"look": None, "shots": {}})
    monkeypatch.setattr(
        cb_production_preflight.cb_providers, "capability_report",
        lambda: {"selectionReady": True, "models": []})
    monkeypatch.setattr(
        cb_production_preflight.studio_profile, "load_show_profile", lambda *_: {})
    monkeypatch.setattr(
        cb_production_preflight.studio_profile, "capability_report",
        lambda *_: {"adapterReady": True, "missingRequiredContent": []})
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda *_: None)
    monkeypatch.setattr(cb_render, "load_pkg", lambda *_: ({"shots": []}, None))
    monkeypatch.setattr(cb_production_preflight.cb_gen, "FAL_KEY", "test")
    monkeypatch.setattr(cb_production_preflight.shutil, "which", lambda *_: "/usr/bin/ffmpeg")

    report = cb_production_preflight.production_preflight(
        "1", "Ep1", state=state)

    blockers = {item["code"]: item for item in report["blockers"]}
    assert "KEYFRAME_POSES_NOT_CURRENT" not in blockers
    assert "KEYFRAME_NOT_CURRENT" in blockers
    assert blockers["KEYFRAME_NOT_CURRENT"]["action"].startswith(
        "Build the keyframe; the Studio will use the locked Scene Look")


def test_paid_resolvers_refuse_legacy_fallbacks():
    live_pkg, _ = cb_render.load_pkg("1", "Ep1")
    pkg = copy.deepcopy(live_pkg)
    shot = pkg["shots"][0]
    cb_render._ledger(pkg, shot["shotId"])["departmentWork"] = {}
    try:
        cb_render._resolve_keyframe_prompt(pkg, shot)
    except cb_render.Refused as exc:
        assert "Prepare current Cinematography" in str(exc)
    else:
        raise AssertionError("keyframe resolver silently used a fallback")
    try:
        cb_render._approved_voice_lines(pkg, shot)
    except cb_render.Refused as exc:
        assert "Prepare current Voice" in str(exc)
    else:
        raise AssertionError("voice resolver silently used a fallback")
    try:
        cb_render._approved_seedance_prompt(pkg, shot)
    except cb_render.Refused as exc:
        assert "Prepare current Animation" in str(exc)
    else:
        raise AssertionError("animation resolver silently used a fallback")


def test_scene_look_refuses_before_provider_without_current_direction(monkeypatch):
    called = []
    original_scene_context = cb_render._scene_context
    monkeypatch.setattr(
        cb_render,
        "_scene_context",
        lambda *args, **kwargs: {
            **original_scene_context(*args, **kwargs),
            "testDirectInputChange": True,
        },
    )
    monkeypatch.setattr(cb_render.cb_gen, "generate_image", lambda *a, **k: called.append(True))
    monkeypatch.setattr(cb_canon, "require_locked", lambda *a, **k: {
        "current": True, "manifestDigest": "fixture", "profileDigests": {}})
    try:
        cb_render.generate_scenelook_plate("1", "Ep1")
    except cb_render.Refused as exc:
        assert "Prepare current Look Development direction" in str(exc)
    else:
        raise AssertionError("Scene Look generation did not refuse")
    assert called == []
