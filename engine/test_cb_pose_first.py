import inspect
import pathlib

from PIL import Image
import pytest

import cb_departments
import cb_render


def _approved_keyframe_fields(characters=("Fuzzby", "Zenny")):
    version, text = cb_departments.canonical_style_paragraph()
    return {
        "geography": ["The flower corridor runs frame-left to frame-right."],
        "charactersInFrame": list(characters),
        "canonicalStyleVersion": version,
        "canonicalStyleParagraph": text,
        "negativeSpace": ["Keep the frame-right lead room open for travel."],
    }


def _write(path, data=b"asset"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_stage_anchor_contract_uploads_only_locked_characters_and_scene_look(
        monkeypatch, tmp_path):
    media_root = tmp_path / "engine" / "media"
    monkeypatch.setattr(cb_render, "MEDIA", media_root / "shots")
    plate = media_root / "Ep1_scene1_plate.png"
    plate.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 900), (60, 120, 70)).save(plate)
    identity = {
        "Fuzzby": _write(media_root / "refs" / "Fuzzby.jpeg", b"fuzzby-id"),
        "Zenny": _write(media_root / "refs" / "Zenny.jpeg", b"zenny-id"),
    }
    layout = {
        "aspectRatio": "16:9", "referenceCharacter": "Fuzzby",
        "referenceHeightFraction": 0.28, "sameDepth": True,
        "placements": [
            {"character": "Fuzzby", "centerX": 0.36, "centerY": 0.43,
             "apparentScale": 1.0, "depthPlane": 1,
             "bodyAngleDegrees": -24, "facing": "screen-right",
             "pose": "committed climbing flight"},
            {"character": "Zenny", "centerX": 0.68, "centerY": 0.48,
             "apparentScale": 1.0, "depthPlane": 1,
             "bodyAngleDegrees": -3, "facing": "screen-right",
             "pose": "clean level glide"},
        ],
    }
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "Fuzzby's chaos is measured against Zenny's calm.",
        "composition": "Fuzzby left, Zenny right, both fully visible.",
        "lensAndCameraRelationship": "Bee-height chase camera.",
        "lightingAndDepth": "Warm backlight and layered flower depth.",
        "openingFrameLayout": layout,
        "continuityProtections": ["No impact yet."],
    }
    shot = {
        "shotId": "S1.SH1", "beatCode": "1.B1", "sourceType": "opener",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
        "referenceSlots": {},
    }
    package = {
        "episode": "Ep1", "sceneNumber": "1", "validation": {"passed": True},
        "shots": [shot], "continuityLedger": [{"shotId": "S1.SH1"}],
    }
    characters = {
        "Fuzzby": {"heightIn": 14, "key_features": "larger bee"},
        "Zenny": {"heightIn": 12, "key_features": "smaller bee"},
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_save", lambda pkg, path: None)
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda *args: None)
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: characters)
    monkeypatch.setattr(cb_render, "_char_ref", lambda role, cfg: str(identity[role]))
    monkeypatch.setattr(
        cb_render, "_provider_identity_record",
        lambda role, cfg, usage="keyframe": {
            "path": str(identity[role]), "character": role, "view": "front",
            "derived": True, "providerSafe": True, "singleSubject": True,
        })
    monkeypatch.setattr(
        cb_render, "_provider_identity_records",
        lambda role, cfg, usage="keyframe": [
            cb_render._provider_identity_record(role, cfg, usage)])
    monkeypatch.setattr(cb_render, "_plate_path", lambda scene, episode="Ep1": str(plate))
    monkeypatch.setattr(
        cb_render, "_inspection_department_output",
        lambda pkg, shot_id, stage: direction)
    monkeypatch.setattr(
        cb_render.cb_layout, "character_cutout",
        lambda path: Image.new("RGBA", (180, 300), (220, 170, 30, 255)))
    cb_render._ensure_opening_composition_master(
        package, shot, "1", "Ep1", characters)

    manifest = cb_render.shot_reference_manifest("1", "S1.SH1", "Ep1")

    assert manifest["posePreparation"]["ready"] is True
    assert manifest["posePreparation"]["applies"] is False
    assert manifest["posedIntegration"]["applies"] is False
    assert [item["role"] for item in manifest["keyframe"]["references"]] == [
        "Zenny", "Fuzzby", "scene plate"]
    assert manifest["keyframe"]["ready"] is True
    assert manifest["technicalControls"]["openingComposition"]["providerUploaded"] is False
    assert manifest["technicalControls"]["characterScale"]["providerUploaded"] is False
    provider_paths = [pathlib.Path(item["path"]) for item in
                      manifest["keyframe"]["references"]]
    assert provider_paths == [identity["Zenny"], identity["Fuzzby"], plate]
    assert all("composition" not in path.name for path in provider_paths)


def test_pose_prompt_preserves_fuzzby_silhouette_and_requests_only_one_actor(
        monkeypatch):
    shot = {"shotId": "S1.SH1", "charactersInFrame": ["Fuzzby"]}
    package = {"sceneNumber": "1", "episode": "Ep1", "shots": [shot],
               "continuityLedger": [{"shotId": "S1.SH1"}]}
    direction = {"openingFrameLayout": {
        "placements": [{"character": "Fuzzby", "pose": "fast climbing flight",
                        "facing": "screen-right", "bodyAngleDegrees": -24}]}}
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14, "key_features": "locked larger bee",
                    "avoid": "crystal"}})
    monkeypatch.setattr(
        cb_render, "_inspection_department_output",
        lambda pkg, shot_id, stage: direction)

    prompt = cb_render._pose_prompt(package, shot, "Fuzzby")

    assert "@图1 defines Fuzzby's exact identity" in prompt
    assert "do not make the character fatter" in prompt
    assert "Fuzzby alone" in prompt
    assert "no environment" in prompt


def test_stage_prompt_keeps_pose_flexible_and_never_forwards_stale_composition_props(
        monkeypatch):
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "Fuzzby's chaos is measured against Zenny's calm.",
        "composition": "Fuzzby flies with pollen sacks bouncing behind him.",
        "lensAndCameraRelationship": "Bee-height chase camera.",
        "lightingAndDepth": "Warm backlight and layered flower depth.",
        "openingFrameLayout": {"sameDepth": True, "placements": [
            {"character": "Fuzzby", "pose": "climbing flight; no carried props",
             "facing": "screen-right", "bodyAngleDegrees": -24},
            {"character": "Zenny", "pose": "level glide; no carried props",
             "facing": "screen-right", "bodyAngleDegrees": -3},
        ]},
        "continuityProtections": [
            "Carry the prior aftermath: visible pollen coating and a smeared pollen "
            "moustache must already be present in the opening frame."
        ],
        "providerPrompt": "Use the opening composition master as @图1.",
    }

    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14}, "Zenny": {"heightIn": 12}})
    prompt = cb_render._compile_keyframe_integration_prompt(direction, {
        "shotId": "S1.SH1",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Fuzzby", "@图2": "Zenny", "@图3": "scene plate"},
    })

    assert "pollen sacks" not in prompt.lower()
    assert "opening composition master" not in prompt.lower()
    assert "@图1" in prompt and "@图2" in prompt and "@图3" in prompt
    assert "playable 16:9 opening" in prompt
    assert "[Performance Freedom]" in prompt
    assert "relative-size truth only" in prompt
    assert "locked extreme action pose" in prompt
    assert "body-mounted bags, sacks, baskets or dangling loads" in prompt
    assert ("[Protect]\nCarry the prior aftermath: visible pollen coating and a smeared "
            "pollen moustache." in prompt)
    assert "must already be" not in prompt
    assert len(prompt.split()) <= cb_render.MAX_KEYFRAME_INTEGRATION_HARD_WORDS
    assert "[Generation Goal]" not in prompt
    assert "[Starting Staging Envelope]" not in prompt


def test_stage_prompt_compacts_verbose_specialist_direction_below_hard_limit(monkeypatch):
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": (
            "A bee-height flower corridor opens with comic contrast already visible: "
            "Fuzzby is overcommitted and unstable before the chase has even begun, while "
            "Zenny is calmly capable beside him. The audience should immediately understand "
            "the route, pollen-rich softness and open performance space."),
        "lensAndCameraRelationship": (
            "Bee-height camera inside the flowers, not overhead. Use a moderately wide "
            "animated-CGI lens relationship that feels close to their scale while showing "
            "the complete action lane ahead."),
        "lightingAndDepth": (
            "Warm sunny field light matching the approved scene look: translucent petals, "
            "soft rim light, green stems creating vertical depth and fine golden pollen."),
        "openingFrameLayout": {"sameDepth": True, "placements": [
            {"character": "Fuzzby", "centerX": .39, "centerY": .48,
             "pose": "playable frame-one anticipation: chest-forward overcommitted hover "
                     "beginning a zig-zag entry, with loose pollen trailing; no impact pose",
             "facing": "angled down the corridor toward screen right, slightly open to camera"},
            {"character": "Zenny", "centerX": .28, "centerY": .51,
             "pose": "playable frame-one anticipation: compact steady hover on a clean "
                     "glide line, calm and readable; no later eye-roll",
             "facing": "angled down the corridor toward screen right, aware of Fuzzby"},
        ]},
        "continuityProtections": [
            "Include exactly Fuzzby and Zenny, no extra cast or substitute species."],
    }
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14}, "Zenny": {"heightIn": 12}})
    prompt = cb_render._compile_keyframe_integration_prompt(direction, {
        "shotId": "S1.SH1",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
    })

    assert len(prompt.split()) <= cb_render.MAX_KEYFRAME_INTEGRATION_HARD_WORDS
    assert "chest-forward overcommitted hover beginning a zig-zag entry" in prompt
    assert "compact steady hover on a clean glide line" in prompt
    assert "beginning a." not in prompt
    assert "body-mounted bags, sacks, baskets or dangling loads" in prompt


def test_stage_prompt_allows_reasonable_over_target_tolerance(monkeypatch):
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": " ".join(["A readable bee-height chase lane protects comic cause and effect"] * 10),
        "lensAndCameraRelationship": " ".join(["Drone-like bee-height pursuit camera"] * 8),
        "lightingAndDepth": " ".join(["Locked warm scene plate with translucent flower depth"] * 8),
        "openingFrameLayout": {"sameDepth": True, "placements": [
            {"character": "Fuzzby", "centerX": .42, "centerY": .49,
             "pose": "forward, unstable, playable anticipation with clear room to crash",
             "facing": "down the flower corridor"},
            {"character": "Zenny", "centerX": .25, "centerY": .5,
             "pose": "steady hover, precise, composed and watching Fuzzby's path",
             "facing": "down the flower corridor"},
        ]},
        "continuityProtections": [
            "Keep exactly two bees, the corridor route readable, and the first frame before the gag payoff."],
    }
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14}, "Zenny": {"heightIn": 12}})

    prompt = cb_render._compile_keyframe_integration_prompt(direction, {
        "shotId": "S1.SH1A",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
    })
    assert (cb_render.MAX_KEYFRAME_INTEGRATION_WORDS < len(prompt.split()) <=
            cb_render.MAX_KEYFRAME_INTEGRATION_HARD_WORDS)


def test_keyframe_prompt_recompiles_from_exact_approved_direction(monkeypatch):
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "Fuzzby commits to the chase while Zenny holds steady.",
        "lensAndCameraRelationship": "Bee-height pursuit camera.",
        "lightingAndDepth": "Warm right-side key light with cool fill.",
        "openingFrameLayout": {"sameDepth": True, "placements": [
            {"character": "Fuzzby", "pose": "forward hover", "facing": "screen-right"},
            {"character": "Zenny", "pose": "steady hover", "facing": "screen-right"},
        ]},
    }
    shot = {
        "shotId": "S1.SH1A", "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
    }
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14}, "Zenny": {"heightIn": 12}})

    first = cb_render._compile_keyframe_integration_prompt(direction, shot)
    sections = cb_departments.prompt_sections(first)
    assert sections["Geography"] == direction["geography"][0]
    assert sections["Light"] == direction["lightingAndDepth"]
    assert sections["Canonical Style"] == direction["canonicalStyleParagraph"]
    assert sections["Characters In Frame"].splitlines() == ["- Fuzzby", "- Zenny"]
    assert "Lead room stays open frame-right" in sections["Negative Space"]

    changed = {**direction,
               "geography": ["The chase now travels frame-right to frame-left."],
               "lightingAndDepth": "Cool left-side storm light with warm rim."}
    second = cb_render._compile_keyframe_integration_prompt(changed, shot)
    assert second != first
    changed_sections = cb_departments.prompt_sections(second)
    assert changed_sections["Geography"] == changed["geography"][0]
    assert changed_sections["Light"] == changed["lightingAndDepth"]


def test_keyframe_prompt_refuses_empty_sections_and_cast_drift(monkeypatch):
    with pytest.raises(ValueError, match="has no body"):
        cb_departments.prompt_sections("[Negative Space]\n\n[Light]\nWarm light")

    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "A readable chase opening.",
        "lensAndCameraRelationship": "Bee-height camera.",
        "lightingAndDepth": "Warm light.",
        "openingFrameLayout": {"placements": [
            {"character": "Fuzzby", "pose": "hover", "facing": "screen-right"},
            {"character": "Zenny", "pose": "glide", "facing": "screen-right"},
        ]},
        "negativeSpace": [],
    }
    shot = {"shotId": "S1.SH1A", "charactersInFrame": ["Fuzzby", "Zenny"]}
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14}, "Zenny": {"heightIn": 12}})
    with pytest.raises(cb_render.Refused, match="negativeSpace"):
        cb_render._compile_keyframe_integration_prompt(direction, shot, [])

    direction["negativeSpace"] = ["Keep frame-right clear."]
    direction["charactersInFrame"] = ["Zenny", "Fuzzby"]
    with pytest.raises(cb_render.Refused, match="does not match the shot contract"):
        cb_render._compile_keyframe_integration_prompt(direction, shot, [])


def test_pose_pass_requires_one_subject_and_every_objective_dimension():
    dimension = {"score": 2, "visibleEvidence": "Clearly visible."}
    payload = {
        "verdict": "pass", "character": "Fuzzby", "subjectCount": 1,
        "summary": "Passes.",
        "identityAndProportions": dimension,
        "requestedPoseAndPerformance": dimension,
        "anatomyAndSilhouette": dimension,
        "isolationAndFraming": dimension,
        "forbiddenContent": dimension,
    }
    assert cb_departments.PoseConformanceReview.model_validate(payload).verdict == "pass"

    payload["identityAndProportions"] = {
        "score": 1, "visibleEvidence": "The torso is visibly too wide.",
        "correction": "Restore the locked torso width.",
    }
    with pytest.raises(ValueError, match="passing pose"):
        cb_departments.PoseConformanceReview.model_validate(payload)


def test_build_keyframe_uses_one_direct_stage_call_and_no_pose_generation(
        monkeypatch, tmp_path):
    shot = {
        "shotId": "S1.SH1", "sourceType": "opener",
        "charactersInFrame": ["Fuzzby", "Zenny"],
    }
    package = {
        "validation": {"passed": True}, "shots": [shot],
        "continuityLedger": [{"shotId": "S1.SH1"}],
    }
    finished = []
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda *args: None)
    monkeypatch.setattr(cb_render, "_require_confirmed_billing", lambda *args: None)
    monkeypatch.setattr(cb_render, "_require_current_scenelook", lambda *args: None)
    monkeypatch.setattr(
        cb_render, "generate_pose_reference",
        lambda *args, **kwargs: pytest.fail("pose generation must not run"))
    monkeypatch.setattr(
        cb_render, "keyframe_shot",
        lambda *args, **kwargs: finished.append("stage") or "stage.png")

    result = inspect.unwrap(cb_render.build_keyframe)(
        "1", "S1.SH1", "Ep1", log=lambda *args, **kwargs: None)

    assert result == "stage.png"
    assert finished == ["stage"]


def test_pose_library_contract_reuses_acting_across_screen_positions(
        monkeypatch, tmp_path):
    identity = _write(tmp_path / "Fuzzby.png", b"locked-fuzzby")
    shot = {"shotId": "S1.SH1", "charactersInFrame": ["Fuzzby"]}
    package = {"shots": [shot], "continuityLedger": [{"shotId": "S1.SH1"}]}
    placement = {
        "character": "Fuzzby", "pose": "committed climbing flight",
        "facing": "screen-right", "bodyAngleDegrees": -24,
        "centerX": 0.25, "centerY": 0.45, "apparentScale": 1.0, "depthPlane": 0,
    }
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14, "key_features": "locked bee", "avoid": "props"}})
    monkeypatch.setattr(cb_render, "_char_ref", lambda name, cfg: str(identity))
    monkeypatch.setattr(
        cb_render, "_inspection_department_output",
        lambda pkg, shot_id, stage: {"openingFrameLayout": {"placements": [placement]}})

    first, _ = cb_render._pose_library_key(package, shot, "Fuzzby")
    placement["centerX"] = 0.78
    placement["centerY"] = 0.62
    second, _ = cb_render._pose_library_key(package, shot, "Fuzzby")
    placement["pose"] = "braking hover"
    third, _ = cb_render._pose_library_key(package, shot, "Fuzzby")

    assert first == second
    assert third != first


def test_next_pose_prompt_consumes_the_last_recorded_correction(monkeypatch):
    shot = {"shotId": "S1.SH1", "charactersInFrame": ["Fuzzby"]}
    package = {
        "shots": [shot],
        "continuityLedger": [{
            "shotId": "S1.SH1",
            "keyframePoseReferences": {"Fuzzby": {"history": [{
                "outcome": "rejected",
                "reason": "Restore the turnaround's slimmer torso and smaller belly.",
            }]}},
        }],
    }
    direction = {"openingFrameLayout": {"placements": [{
        "character": "Fuzzby", "pose": "committed climbing flight",
        "facing": "screen-right", "bodyAngleDegrees": -24,
    }]}}
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Fuzzby": {"heightIn": 14, "key_features": "locked bee", "avoid": "props"}})
    monkeypatch.setattr(
        cb_render, "_inspection_department_output",
        lambda pkg, shot_id, stage: direction)

    prompt = cb_render._pose_prompt(package, shot, "Fuzzby")

    assert "[Correction From The Previous Attempt]" in prompt
    assert "Restore the turnaround's slimmer torso and smaller belly." in prompt
