"""DIRECT and SEE must share opening geometry without a legacy department pass."""
from copy import deepcopy

import pytest
from PIL import Image

import cb_departments
import cb_render as render


def test_direct_opening_reaches_real_composition_validation(tmp_path, monkeypatch):
    plate = tmp_path / "plate.png"
    identity = tmp_path / "Sunny.png"
    Image.new("RGB", (1600, 900)).save(plate)
    Image.new("RGBA", (100, 200), "yellow").save(identity)
    shot = {
        "shotId": "S3.SH1", "openingCharactersInFrame": ["Sunny"],
        "charactersInFrame": ["Sunny"],
        "openingPose": "Sunny adjusts the cups at the party table.",
        "purpose": "Establish Sunny's careful order.",
    }
    original = deepcopy(shot)
    monkeypatch.setattr(render, "_char_ref", lambda *a: str(identity))
    monkeypatch.setattr(render, "_plate_path", lambda *a: str(plate))
    def obsolete_department(*args):
        raise AssertionError("DIRECT must not require a legacy Cinematography pass")
    monkeypatch.setattr(render, "_inspection_department_output", obsolete_department)

    direction = render._direct_keyframe_direction(shot)
    layout = cb_departments.OpeningFrameLayout.model_validate(
        direction["openingFrameLayout"]).model_dump()
    contract, characters, actual_plate = render._opening_composition_contract(
        {}, shot, "3", "Ep4", {"Sunny": {"heightIn": 20}})
    assert contract["layout"] == layout
    assert list(characters) == ["Sunny"]
    assert actual_plate == plate
    assert shot == original


@pytest.mark.parametrize("modern", [False, True])
def test_see_preserves_opening_coverage_not_later_views(modern):
    first = {"viewId": "V1", "purpose": "Care expressed through alignment",
             "framing": "CU across the cup row", "staging": "Paw beside cup",
             "startState": "Cup untouched", "cinematography": {
                 "lens": "35mm", "angle": "table height", "focus": "cup rim",
                 "composition": "paws at right edge", "light": "warm side light",
                 "atmosphere": "dry clearing", "movement": "later tilt to face"}}
    shot = {"shotId": "S3.SH1", "charactersInFrame": ["Sunny"],
            "openingPose": "Paw beside cup", "purpose": "Scene summary",
            "storyboardInternalShotPlanApproved": [first, {"framing": "LATER RAIN"}]}
    if modern:
        shot["directorCard"] = {"views": [deepcopy(first)]}
        shot["storyboardInternalShotPlanApproved"][0] = {"framing": "STALE CAMERA"}
    before = deepcopy(shot)
    result = render._direct_keyframe_direction(shot)
    camera = result["lensAndCameraRelationship"]
    for value in ("CU across the cup row", "35mm", "table height", "cup rim", "paws at right edge"):
        assert value in camera
    assert "warm side light" in result["lightingAndDepth"]
    assert "dry clearing" in result["lightingAndDepth"]
    assert result["openingState"] == "Cup untouched"
    assert result["audienceRead"] == "Care expressed through alignment"
    assert all(text not in str(result) for text in ("LATER RAIN", "later tilt", "STALE CAMERA"))
    assert shot == before


def test_see_does_not_import_scene_wide_cast_or_later_beat_into_opening():
    view = {"viewId": "S4_V06", "staging": "Sunny holds the garland; Keen is beneath it.",
            "continuity": "The garland remains attached.", "startState": "Garland held."}
    shot = {
        "shotId": "S4.SH2", "charactersInFrame": ["Sunny", "Keen"],
        "openingPose": "Sunny grips the garland; Keen looks up.",
        "directorCard": {"views": [view]},
        "openingFrameLayoutApproved": {"placements": [
            {"character": "Sunny", "centerX": .3, "centerY": .6, "depthPlane": 0},
            {"character": "Keen", "centerX": .7, "centerY": .6, "depthPlane": 0}]},
        "cinematographyContractApproved": {
            "depthStrategy": "Keep Sunny, Keen and Misty staggered for later beats.",
            "composition": "Scene-wide composition with Misty."},
    }
    direction = render._direct_keyframe_direction(shot)
    assert "Misty" not in str(direction)
    assert direction["geography"] == [view["staging"], view["continuity"]]
    assert "Misty" not in direction["lightingAndDepth"]
    assert direction["openingState"] == view["startState"]


def test_legacy_see_projection_does_not_duplicate_scene_text_or_infer_depth():
    staging = "Sunny holds the wet garland; Keen stands below and looks up."
    shot = {
        "shotId": "S4.SH2", "charactersInFrame": ["Sunny", "Keen"],
        "openingPose": "The wet garland sags above Keen; drops gather.",
        "storyboardInternalShotPlanApproved": [{"staging": staging}],
    }

    direction = render._direct_keyframe_direction(shot)
    layout = direction["openingFrameLayout"]

    assert layout["sameDepth"] is False
    assert [item["pose"] for item in layout["placements"]] == [
        "in the approved frame-one staging", "in the approved frame-one staging"]
    assert all(staging not in item["facing"] for item in layout["placements"])
    assert direction["geography"] == [staging]


def test_invalid_direct_layout_does_not_fall_back_to_legacy_direction(monkeypatch):
    shot = {"shotId": "S3.SH1", "charactersInFrame": ["Sunny"],
            "openingFrameLayoutApproved": {"placements": [
                {"character": "Sunny", "centerX": 9}]}}
    monkeypatch.setattr(render, "_inspection_department_output",
                        lambda *a: pytest.fail("Invalid DIRECT must not be bypassed"))
    with pytest.raises(render.Refused, match="invalid typed opening-frame layout"):
        render._opening_composition_contract({}, shot, "3", "Ep4", {})


@pytest.mark.parametrize("compare", [False, True])
def test_single_provider_build_does_not_require_google_billing(monkeypatch, compare):
    pkg = {"shots": [{"shotId": "S3.SH1"}],
           "continuityLedger": [{"shotId": "S3.SH1"}]}
    monkeypatch.setattr(render, "load_pkg", lambda *a: (pkg, None))
    for name in ("_require_current_see_canon", "_require_valid", "_require_current_lineage"):
        monkeypatch.setattr(render, name, lambda *a: None)
    checked = []
    monkeypatch.setattr(render, "_require_confirmed_billing", checked.append)
    def stop_before_media(*args):
        raise render.Refused("fixture stops before any media work")
    monkeypatch.setattr(render, "_require_current_scenelook", stop_before_media)
    with pytest.raises(render.Refused, match="fixture stops"):
        render.keyframe_shot("3", "S3.SH1", "Ep4", compare=compare)
    assert checked == (["byteplus", "google"] if compare else ["byteplus"])
