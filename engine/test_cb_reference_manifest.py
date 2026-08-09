import pathlib

import cb_departments
import cb_render
import pytest
from PIL import Image


def _approved_keyframe_fields():
    version, text = cb_departments.canonical_style_paragraph()
    return {
        "geography": ["The flower corridor runs frame-left to frame-right."],
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "canonicalStyleVersion": version,
        "canonicalStyleParagraph": text,
        "negativeSpace": ["Hold frame-right lead room open for travel."],
    }


def _write(path, data=b"asset"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _provider_identities(monkeypatch, paths):
    packs = {
        name: {
            "schemaVersion": 1, "source": "fixture",
            "providerViews": {"default": {"view": "front", "crop": [0, 0, 1, 1]}},
            "distinguishingFeatures": (
                ["round glasses", name + " identity"]
                if name == "Zenny" else [name + " identity"]
            ),
            "mustNotBorrow": ["another character's features"],
        }
        for name in paths
    }
    monkeypatch.setattr(cb_render, "_identity_packs_cfg", lambda: packs)

    def provider_record(name, characters_cfg, usage="keyframe"):
        canonical = cb_render._resolve_char(name, characters_cfg)
        path = pathlib.Path(paths[canonical])
        return {
            "character": canonical, "usage": usage, "view": "front",
            "path": str(path), "fileName": path.name,
            "derived": True, "providerSafe": True, "singleSubject": True,
            "contractHash": "fixture-" + canonical.lower(),
            "distinguishingFeatures": packs[canonical]["distinguishingFeatures"],
            "mustNotBorrow": packs[canonical]["mustNotBorrow"],
        }

    monkeypatch.setattr(cb_render, "_provider_identity_record", provider_record)


def test_each_turnaround_remains_one_intact_provider_attachment(monkeypatch, tmp_path):
    media_root = tmp_path / "engine" / "media"
    monkeypatch.setattr(cb_render, "ROOT", tmp_path)
    monkeypatch.setattr(cb_render, "MEDIA", media_root / "shots")
    packs = {}
    characters = {"Zenny": {"heightIn": 12}, "Fuzzby": {"heightIn": 14}}
    for name, colours in {
            "Zenny": ("gold", "black"), "Fuzzby": ("orange", "brown")}.items():
        source = media_root / "sources" / f"{name}_turnaround.png"
        source.parent.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGB", (200, 100), colours[1])
        sheet.paste(Image.new("RGB", (100, 100), colours[0]), (0, 0))
        sheet.save(source)
        packs[name] = {
            "schemaVersion": 1,
            "source": str(source),
            "providerViews": {
                "default": {"view": "front", "crop": [0, 0, 0.5, 1]}},
            "turnaroundViews": [
                {"view": "front", "crop": [0, 0, 0.5, 1]},
                {"view": "rear", "crop": [0.5, 0, 1, 1]},
            ],
            "distinguishingFeatures": (
                ["round glasses", name + " identity"]
                if name == "Zenny" else [name + " identity"]
            ),
            "mustNotBorrow": ["the other character's features"],
        }
    monkeypatch.setattr(cb_render, "_identity_packs_cfg", lambda: packs)
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: characters)
    shot = {
        "shotId": "S1.SH1", "sourceType": "opener",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
    }
    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "Fuzzby chaos against Zenny calm.",
        "lensAndCameraRelationship": "Bee-height camera.",
        "lightingAndDepth": "Warm backlight.",
        "negativeSpace": ["Hold frame-right open for the later flower reveal."],
        "openingFrameLayout": {"sameDepth": True, "placements": [
            {"character": "Fuzzby", "pose": "loose hover", "facing": "screen right"},
            {"character": "Zenny", "pose": "steady glide", "facing": "screen right"},
        ]},
        "continuityProtections": ["Include exactly Fuzzby and Zenny."],
    }

    blueprint = cb_render._expanded_reference_blueprint(
        shot, "keyframeReferenceSlots", characters)
    prompt = cb_render._compile_keyframe_integration_prompt(
        direction, shot, blueprint)

    assert [(item["slot"], item["role"], item.get("view")) for item in blueprint] == [
        ("@图1", "Zenny", "complete-turnaround"),
        ("@图2", "Fuzzby", "complete-turnaround"),
        ("@图3", "scene plate", None),
    ]
    assert "@图1: Zenny's complete, uncropped 360 turnaround is the 100% identity authority" in prompt
    assert "Match Zenny exactly as the same character shown in the turnaround" in prompt
    assert "@图2: Fuzzby's complete, uncropped 360 turnaround is the 100% identity authority" in prompt
    assert "round glasses" not in prompt
    assert "rosy blush" not in prompt
    assert "@图3 is the locked Scene Look plate" in prompt
    assert "do not describe, redesign, simplify, beautify" in prompt
    assert "omitted reference features" in prompt
    assert "[Canonical Style]" in prompt
    assert "Hold frame-right open for the later flower reveal." in prompt
    assert len(prompt.split()) <= cb_render.MAX_KEYFRAME_INTEGRATION_WORDS


def test_reference_manifest_exposes_keyframe_and_animation_in_provider_order(
        monkeypatch, tmp_path):
    media_root = tmp_path / "engine" / "media"
    monkeypatch.setattr(cb_render, "MEDIA", media_root / "shots")
    character = _write(media_root / "refs" / "Fuzzby.png")
    plate = _write(media_root / "Ep1_scene1_plate.png")
    anchor = _write(media_root / "shots" / "Ep1_S1.SH1_keyframe.png")
    audio = _write(media_root / "shots" / "Ep1_S1.SH1_voice.mp3", b"ID3")
    package = {
        "shots": [{
            "shotId": "S1.SH1", "sourceType": "opener",
            "keyframeReferenceSlots": {
                "@图1": "Fuzzby", "@图2": "scene plate"},
            "referenceSlots": {
                "@图1": "opening keyframe", "@图2": "Fuzzby",
                "@图3": "scene plate", "@Audio1": "voice track"},
        }],
        "continuityLedger": [{
            "shotId": "S1.SH1", "voPath": str(audio),
            "voiceApproval": {"approved": True},
        }],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {})
    monkeypatch.setattr(cb_render, "_char_ref", lambda role, cfg: str(character))
    _provider_identities(monkeypatch, {"Fuzzby": character})
    monkeypatch.setattr(cb_render, "_plate_path", lambda scene, episode="Ep1": str(plate))
    monkeypatch.setattr(cb_render, "_anchor_for", lambda pkg, shot: str(anchor))

    manifest = cb_render.shot_reference_manifest("1", "S1.SH1", "Ep1")

    assert manifest["zeroSpend"] is True and manifest["readOnly"] is True
    assert manifest["keyframe"]["ready"] is True
    assert [item["role"] for item in manifest["keyframe"]["references"]] == [
        "Fuzzby", "scene plate"]
    assert manifest["animation"]["ready"] is True
    assert [item["slot"] for item in manifest["animation"]["references"]] == [
        "@图1", "@图2", "@图3", "@Audio1"]
    assert all(item["ready"] for item in manifest["animation"]["references"])


def test_animation_prompt_binds_each_intact_sheet_to_one_character():
    references = [
        {"slot": "@图1", "role": "opening keyframe", "intactTurnaround": False},
        {"slot": "@图2", "role": "Zenny", "intactTurnaround": True},
        {"slot": "@图3", "role": "Fuzzby", "intactTurnaround": True},
    ]

    prompt = cb_render._with_intact_turnaround_law(
        "Animate the approved performance.", references)

    assert "@图2 is Zenny's complete, uncropped 360 turnaround sheet" in prompt
    assert "@图3 is Fuzzby's complete, uncropped 360 turnaround sheet" in prompt
    assert prompt.count("render exactly one instance of this character") == 2
    assert prompt.endswith("Animate the approved performance.")


def test_reference_resolution_refuses_an_asset_from_an_older_workspace(
        monkeypatch, tmp_path):
    canonical_media = tmp_path / "canonical" / "engine" / "media"
    monkeypatch.setattr(cb_render, "MEDIA", canonical_media / "shots")
    old_plate = _write(tmp_path / "older-workspace" / "engine" / "media" / "plate.png")
    monkeypatch.setattr(
        cb_render, "_plate_path", lambda scene, episode="Ep1": str(old_plate))

    with pytest.raises(cb_render.Refused, match="outside this canonical Studio"):
        cb_render._slot_path_for_role("scene plate", None, "1", "Ep1", {})


def test_composition_and_scale_controls_remain_local_while_locked_assets_own_provider_input(
        monkeypatch, tmp_path):
    media_root = tmp_path / "engine" / "media"
    monkeypatch.setattr(cb_render, "MEDIA", media_root / "shots")
    zenny = _write(media_root / "refs" / "CB_Zenny.jpeg", b"zenny-turnaround")
    fuzzby = _write(media_root / "refs" / "CB_Fuzzby.jpeg", b"fuzzby-turnaround")
    plate = media_root / "Ep1_scene1_plate.png"
    plate.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 900), (80, 140, 90)).save(plate)
    anchor = _write(media_root / "shots" / "Ep1_S1.SH1_keyframe.png")
    refs = {"Zenny": str(zenny), "Fuzzby": str(fuzzby)}
    characters = {
        "Zenny": {"heightIn": 12, "sizeRank": 0.4},
        "Fuzzby": {"heightIn": 14, "sizeRank": 0.6},
    }
    shot = {
        "shotId": "S1.SH1", "sourceType": "opener",
        "charactersInFrame": ["Fuzzby", "Zenny"],
        "keyframeReferenceSlots": {
            "@图1": "Zenny", "@图2": "Fuzzby", "@图3": "scene plate"},
        "referenceSlots": {
            "@图1": "opening keyframe", "@图2": "Zenny",
            "@图3": "Fuzzby", "@图4": "scene plate"},
    }
    package = {
        "episode": "Ep1", "sceneNumber": "1", "shots": [shot],
        "continuityLedger": [{"shotId": "S1.SH1"}],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda scene, episode="Ep1": (package, tmp_path / "pkg.json"))
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: characters)
    monkeypatch.setattr(cb_render, "_char_ref", lambda role, cfg: refs[role])
    _provider_identities(monkeypatch, refs)
    monkeypatch.setattr(cb_render, "_plate_path", lambda scene, episode="Ep1": str(plate))
    monkeypatch.setattr(cb_render, "_anchor_for", lambda pkg, item: str(anchor))
    layout = {
        "aspectRatio": "16:9", "referenceCharacter": "Fuzzby",
        "referenceHeightFraction": 0.35, "sameDepth": True,
        "placements": [
            {"character": "Fuzzby", "centerX": 0.32, "centerY": 0.58,
             "apparentScale": 1.0, "depthPlane": 0,
             "bodyAngleDegrees": -25, "facing": "upper-right", "pose": "flight"},
            {"character": "Zenny", "centerX": 0.70, "centerY": 0.44,
             "apparentScale": 1.0, "depthPlane": 0,
             "bodyAngleDegrees": -8, "facing": "screen-right", "pose": "glide"},
        ],
    }
    monkeypatch.setattr(
        cb_render, "_inspection_department_output",
        lambda pkg, shot_id, stage: {"openingFrameLayout": layout})
    monkeypatch.setattr(
        cb_render.cb_layout, "character_cutout",
        lambda path: Image.new("RGBA", (180, 300), (220, 170, 30, 255)))

    composition = cb_render._ensure_opening_composition_master(
        package, shot, "1", "Ep1", characters)

    control = cb_render._ensure_character_scale_control(
        shot, "1", "Ep1", characters, same_depth=True)

    assert composition["zeroSpend"] is True and composition["providerCalled"] is False
    assert composition["geometry"]["sameDepth"] is True
    assert control["zeroSpend"] is True and control["providerCalled"] is False
    assert [(item["character"], item["heightIn"]) for item in control["characters"]] == [
        ("Fuzzby", 14), ("Zenny", 12)]
    pixels = cb_render._scale_pixel_heights(control)
    assert pixels["Fuzzby"] * 6 == pixels["Zenny"] * 7
    with Image.open(control["path"]) as board:
        assert board.size == (1600, 900)

    direction = {
        **_approved_keyframe_fields(),
        "audienceRead": "Fuzzby chaos against Zenny calm.",
        "composition": "Fuzzby left, Zenny right.",
        "lensAndCameraRelationship": "Bee-height camera.",
        "lightingAndDepth": "Warm backlight.",
        "openingFrameLayout": layout,
        "continuityProtections": ["No impact yet."],
    }
    keyframe_prompt = cb_render._compile_keyframe_integration_prompt(direction, shot)
    animation_prompt = cb_render._with_character_scale_control(
        "Animate the approved performance.", shot, "referenceSlots", "1", "Ep1")
    assert "@图1: Zenny's complete, uncropped 360 turnaround is the 100% identity authority" in keyframe_prompt
    assert "@图2: Fuzzby's complete, uncropped 360 turnaround is the 100% identity authority" in keyframe_prompt
    assert "round glasses" not in keyframe_prompt
    assert "@图3 is the locked Scene Look plate" in keyframe_prompt
    assert "[Performance Freedom]" in keyframe_prompt
    assert cb_render.OPENING_COMPOSITION_ROLE not in keyframe_prompt
    assert cb_render.CHARACTER_SCALE_CONTROL_MARKER not in keyframe_prompt
    assert cb_render.CHARACTER_SCALE_CONTROL_MARKER not in animation_prompt
    with pytest.raises(cb_render.Refused, match="local sizing/composition proof"):
        cb_render._with_opening_composition_control(
            "@图1 is the opening composition master.", shot, "1", "Ep1")

    manifest = cb_render.shot_reference_manifest("1", "S1.SH1", "Ep1")
    assert [item["role"] for item in manifest["keyframe"]["references"]] == [
        "Zenny", "Fuzzby", "scene plate"]
    assert all(item["ready"] for item in manifest["keyframe"]["references"])
    assert manifest["keyframe"]["ready"] is True
    assert manifest["posePreparation"]["ready"] is True
    assert manifest["posePreparation"]["applies"] is False
    assert manifest["posePreparation"]["items"] == []
    assert cb_render.CHARACTER_SCALE_CONTROL_ROLE not in [
        item["role"] for item in manifest["keyframe"]["references"]]
    assert cb_render.CHARACTER_SCALE_CONTROL_ROLE not in [
        item["role"] for item in manifest["animation"]["references"]]
    assert manifest["technicalControls"]["openingComposition"]["ready"] is True
    assert manifest["technicalControls"]["openingComposition"]["providerUploaded"] is False
    assert manifest["technicalControls"]["characterScale"]["ready"] is True
    assert manifest["technicalControls"]["characterScale"]["providerUploaded"] is False
    assert manifest["animation"]["ready"] is True

    zenny.write_bytes(b"changed-turnaround")
    assert cb_render._load_character_scale_control(
        shot, "1", "Ep1", characters) is None
