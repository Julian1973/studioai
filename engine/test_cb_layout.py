import io

from PIL import Image, ImageDraw
import pytest

import cb_layout


def _cutout(colour):
    image = Image.new("RGBA", (180, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((25, 5, 155, 135), fill=colour)
    draw.rounded_rectangle((35, 105, 145, 295), radius=50, fill=colour)
    return image


def test_composition_master_applies_exact_canon_ratio_on_one_depth_plane(
        monkeypatch, tmp_path):
    plate = tmp_path / "plate.png"
    Image.new("RGB", (1600, 900), (80, 140, 90)).save(plate)
    fuzzby = tmp_path / "Fuzzby.jpeg"
    zenny = tmp_path / "Zenny.jpeg"
    fuzzby.write_bytes(b"fuzzby")
    zenny.write_bytes(b"zenny")
    cutouts = {
        str(fuzzby): _cutout((230, 175, 35, 255)),
        str(zenny): _cutout((215, 190, 70, 255)),
    }
    monkeypatch.setattr(
        cb_layout, "character_cutout", lambda path: cutouts[str(path)].copy())
    characters = {
        "Fuzzby": {"heightIn": 14, "turnaroundPath": str(fuzzby)},
        "Zenny": {"heightIn": 12, "turnaroundPath": str(zenny)},
    }
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

    png, geometry = cb_layout.render_composition_master(plate, characters, layout)

    with Image.open(io.BytesIO(png)) as rendered:
        assert rendered.size == (2048, 1152)
    heights = {item["character"]: item["targetStandingHeightPx"]
               for item in geometry["characters"]}
    assert heights["Fuzzby"] * 6 == heights["Zenny"] * 7
    assert geometry["sameDepth"] is True


def test_posed_integration_uses_approved_pose_art_without_turnaround_crop(
        monkeypatch, tmp_path):
    plate = tmp_path / "plate.png"
    Image.new("RGB", (1600, 900), (80, 140, 90)).save(plate)
    fuzzby_pose = tmp_path / "Fuzzby-pose.png"
    zenny_pose = tmp_path / "Zenny-pose.png"
    fuzzby_pose.write_bytes(b"fuzzby-pose")
    zenny_pose.write_bytes(b"zenny-pose")
    cutouts = {
        str(fuzzby_pose): _cutout((230, 175, 35, 255)),
        str(zenny_pose): _cutout((215, 190, 70, 255)),
    }
    monkeypatch.setattr(
        cb_layout, "posed_character_cutout", lambda path: cutouts[str(path)].copy())
    characters = {
        "Fuzzby": {"heightIn": 14, "turnaroundPath": "unused-Fuzzby.jpeg"},
        "Zenny": {"heightIn": 12, "turnaroundPath": "unused-Zenny.jpeg"},
    }
    layout = {
        "aspectRatio": "16:9", "referenceCharacter": "Fuzzby",
        "referenceHeightFraction": 0.28, "sameDepth": True,
        "placements": [
            {"character": "Fuzzby", "centerX": 0.36, "centerY": 0.43,
             "apparentScale": 1.0, "depthPlane": 1,
             "bodyAngleDegrees": -24, "facing": "screen-right", "pose": "flight"},
            {"character": "Zenny", "centerX": 0.68, "centerY": 0.48,
             "apparentScale": 1.0, "depthPlane": 1,
             "bodyAngleDegrees": -3, "facing": "screen-right", "pose": "glide"},
        ],
    }

    png, geometry = cb_layout.render_posed_integration_frame(
        plate, characters, layout,
        {"Fuzzby": str(fuzzby_pose), "Zenny": str(zenny_pose)})

    with Image.open(io.BytesIO(png)) as rendered:
        assert rendered.size == (2048, 1152)
    heights = {item["character"]: item["targetStandingHeightPx"]
               for item in geometry["characters"]}
    assert heights["Fuzzby"] * 6 == heights["Zenny"] * 7
    assert geometry["source"] == "approved-character-poses"


def test_same_depth_layout_refuses_perspective_scale_drift():
    characters = {
        "Fuzzby": {"heightIn": 14, "turnaroundPath": "Fuzzby.jpeg"},
        "Zenny": {"heightIn": 12, "turnaroundPath": "Zenny.jpeg"},
    }
    layout = {
        "referenceCharacter": "Fuzzby", "referenceHeightFraction": 0.35,
        "sameDepth": True,
        "placements": [
            {"character": "Fuzzby", "centerX": 0.3, "centerY": 0.5,
             "apparentScale": 1.3, "depthPlane": 0},
            {"character": "Zenny", "centerX": 0.7, "centerY": 0.5,
             "apparentScale": 1.0, "depthPlane": 0},
        ],
    }

    with pytest.raises(cb_layout.LayoutError, match="apparentScale=1.0"):
        cb_layout.validate_layout(layout, characters)


def test_fit_frame_safety_clamps_rotated_cinematography_overflow(
        monkeypatch, tmp_path):
    bo = tmp_path / "Bo.png"
    keen = tmp_path / "Keen.png"
    bo.write_bytes(b"bo")
    keen.write_bytes(b"keen")
    cutouts = {
        str(bo): _cutout((80, 150, 240, 255)),
        str(keen): _cutout((50, 180, 230, 255)),
    }
    monkeypatch.setattr(
        cb_layout, "character_cutout", lambda path: cutouts[str(path)].copy())
    characters = {
        "Bo": {"heightIn": 30, "turnaroundPath": str(bo)},
        "Keen": {"heightIn": 57, "turnaroundPath": str(keen)},
    }
    layout = {
        "aspectRatio": "16:9",
        "referenceCharacter": "Bo",
        "referenceHeightFraction": 0.42,
        "sameDepth": False,
        "placements": [
            {"character": "Bo", "centerX": 0.61, "centerY": 0.62,
             "apparentScale": 1.0, "depthPlane": 1,
             "bodyAngleDegrees": -12},
            {"character": "Keen", "centerX": 0.36, "centerY": 0.61,
             "apparentScale": 0.94, "depthPlane": 2,
             "bodyAngleDegrees": 8},
        ],
    }

    fitted = cb_layout.fit_frame_safety(layout, characters)

    assert fitted["placements"][0]["centerY"] == 0.62
    assert fitted["placements"][1]["centerY"] < 0.61
    cb_layout.validate_layout(fitted, characters)

    plate = tmp_path / "plate.png"
    Image.new("RGB", (1600, 900), (80, 140, 90)).save(plate)
    _, geometry = cb_layout.render_composition_master(plate, characters, fitted)
    keen_geometry = next(
        item for item in geometry["characters"] if item["character"] == "Keen")
    assert keen_geometry["renderedBoundsPx"][1] >= 0
    assert keen_geometry["renderedBoundsPx"][3] <= 1152


def test_local_geometry_screen_blocks_gross_size_drift(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cb_layout, "_foreground_alpha",
        lambda image: __import__("numpy").asarray(image)[:, :, 3])
    composition = {"geometry": {
        "frameSize": [1000, 500],
        "characters": [
            {"character": "Fuzzby", "centreNormalized": [0.275, 0.40],
             "renderedBoundsPx": [200, 100, 350, 300]},
            {"character": "Zenny", "centreNormalized": [0.715, 0.48],
             "renderedBoundsPx": [650, 150, 780, 330]},
        ],
    }}
    good = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(good)
    draw.ellipse((200, 100, 350, 300), fill=(240, 180, 20, 255))
    draw.ellipse((650, 150, 780, 330), fill=(220, 180, 50, 255))
    good_path = tmp_path / "good.png"
    good.save(good_path)

    passed = cb_layout.screen_candidate_geometry(good_path, composition)

    assert passed["status"] == "pass"
    assert all(item["passed"] for item in passed["matches"])

    drifted = Image.new("RGBA", (1000, 500), (0, 0, 0, 0))
    draw = ImageDraw.Draw(drifted)
    draw.ellipse((20, 10, 520, 490), fill=(240, 180, 20, 255))
    draw.ellipse((650, 150, 780, 330), fill=(220, 180, 50, 255))
    drifted_path = tmp_path / "drifted.png"
    drifted.save(drifted_path)

    failed = cb_layout.screen_candidate_geometry(drifted_path, composition)

    assert failed["status"] == "fail"
    assert any(not item["passed"] for item in failed["matches"])
