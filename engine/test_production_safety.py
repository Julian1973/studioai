"""Zero-spend regression checks for the single approved production path."""
import cb_production_preflight
import cb_render
import cb_safety


def test_safety_layer_is_installed():
    assert cb_render.generate_scenelook_plate.__module__ == "cb_safety"
    assert cb_render._resolve_keyframe_prompt.__module__ == "cb_safety"
    assert cb_render.voice_shot.__module__ == "cb_safety"
    assert cb_render.fire_shot.__module__ == "cb_safety"


def test_preflight_reports_all_scene_one_blockers_without_spend():
    report = cb_production_preflight.production_preflight("1", "Ep1")
    assert report["zeroSpend"] is True
    assert report["lineage"]["current"] is False
    assert "script-version-mismatch" in report["lineage"]["reasonCodes"]
    codes = {item["code"] for item in report["blockers"]}
    assert "STALE_PRODUCTION_GRAPH" in codes
    assert "SHOT_NOT_READY" in codes
    assert "CONFIG_FAL_KEY" in codes
    assert "CONFIG_ELEVENLABS_KEY" in codes
    assert report["nextAction"] == "Promote the current approved Story & Direction package."


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
