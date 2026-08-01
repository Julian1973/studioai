"""Zero-spend regression checks for the single approved production path."""
import cb_intake
import cb_production_preflight
import cb_render
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


def test_preflight_stops_at_story_direction_for_the_new_canon_aligned_script():
    report = cb_production_preflight.production_preflight("1", "Ep1")
    assert report["zeroSpend"] is True
    assert report["lineage"]["current"] is False
    assert report["lineage"]["reasonCodes"] == ["story-intake-not-approved"]
    codes = {item["code"] for item in report["blockers"]}
    assert "STORY_INTAKE_APPROVAL_REQUIRED" in codes
    assert "CANON_LOCK_REQUIRED" not in codes
    assert "STALE_PRODUCTION_GRAPH" not in codes
    assert "SHOT_NOT_READY" not in codes
    assert report["shots"] == []
    intake = cb_intake.intake_status("Ep1")
    candidate_waiting = bool(
        intake["candidateCurrent"] and not intake["canonicalCurrent"]
    )
    assert report["stages"]["storyboard"]["state"] == (
        "awaiting" if candidate_waiting else "ready"
    )
    assert report["providerCapabilities"]["selectionReady"] is True
    assert report["providerCapabilities"]["selectedVideoModelId"] == "fal-seedance-2.0"
    assert report["showProfile"]["showId"] == "crystal-bears"
    assert report["showProfile"]["adapterReady"] is True
    assert report["nextAction"] == (
        "Review and approve the current episode Story & Direction candidate."
        if candidate_waiting else "Run Story & Direction for the active script."
    )


def test_preflight_blocks_an_unqualified_selected_video_model(monkeypatch):
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "byteplus-seedance-2.5")
    report = cb_production_preflight.production_preflight("1", "Ep1")

    blockers = {item["code"]: item for item in report["blockers"]}
    assert "VIDEO_PROVIDER_NOT_QUALIFIED" in blockers
    assert "disabled" in blockers["VIDEO_PROVIDER_NOT_QUALIFIED"]["message"]
    assert report["providerCapabilities"]["selectionReady"] is False


def test_paid_resolvers_refuse_legacy_fallbacks():
    pkg, _ = cb_render.load_pkg("1", "Ep1")
    shot = pkg["shots"][0]
    try:
        cb_render._resolve_keyframe_prompt(pkg, shot)
    except cb_render.Refused as exc:
        assert "Approve current Cinematography" in str(exc)
    else:
        raise AssertionError("keyframe resolver silently used a fallback")
    try:
        cb_render._approved_voice_lines(pkg, shot)
    except cb_render.Refused as exc:
        assert "Approve current Voice" in str(exc)
    else:
        raise AssertionError("voice resolver silently used a fallback")
    try:
        cb_render._approved_seedance_prompt(pkg, shot)
    except cb_render.Refused as exc:
        assert "Approve current Animation" in str(exc)
    else:
        raise AssertionError("animation resolver silently used a fallback")


def test_scene_look_refuses_before_provider_without_approved_direction(monkeypatch):
    called = []
    monkeypatch.setattr(cb_render.cb_gen, "generate_image", lambda *a, **k: called.append(True))
    try:
        cb_render.generate_scenelook_plate("1", "Ep1")
    except cb_render.Refused as exc:
        assert "production package revision" in str(exc) and "script-version-mismatch" in str(exc)
    else:
        raise AssertionError("Scene Look generation did not refuse")
    assert called == []
