import json
from pathlib import Path

import cb_lineage
import paths as P  # T45: scratch worlds use the project layout


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene4_production_package.json"
STORYBOARD = ROOT / P.OUTPUT_REL / "creative" / "Ep1_scene4_storyboard.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_scene4_is_three_thirty_second_units():
    package = _load(PACKAGE)
    assert [(shot["shotId"], shot["beatCodes"], shot["durationSec"])
            for shot in package["shots"]] == [
        ("4.B1.S1", ["4.B1", "4.B2"], 30.0),
        ("4.B3.S1", ["4.B3", "4.B4"], 30.0),
        ("4.B5.S1", ["4.B5", "4.B6"], 30.0),
    ]
    assert package["totalSec"] == 90.0
    assert package["validation"]["passed"] is True


def test_scene4_recut_keeps_every_dialogue_occurrence_once():
    package = _load(PACKAGE)
    occurrences = [
        line["dialogueOccurrenceId"]
        for shot in package["shots"]
        for line in shot["dialogueLines"]
    ]
    assert len(occurrences) == 10
    assert len(occurrences) == len(set(occurrences))


def test_scene4_recut_keeps_entrance_and_exit_boundaries_typed():
    package = _load(PACKAGE)
    assert package["shots"][1]["closingCharactersInFrame"] == ["Keen"]
    assert package["shots"][2]["openingCharactersInFrame"] == ["Keen"]
    assert package["shots"][0]["openingCharactersInFrame"] == ["Keen"]
    assert package["shots"][0]["charactersInFrame"] == ["Keen", "Squeaky"]


def test_scene4_opening_keyframe_binds_squeaky_as_a_dolphin():
    package = _load(PACKAGE)
    prompt = package["shots"][0]["keyframePrompt"]
    assert "Keen (@图1, bear)" in prompt
    assert "Squeaky (@图2, dolphin)" in prompt
    assert "larger bear" not in prompt


def test_scene4_opening_unit_carries_real_world_continuity_contract():
    package = _load(PACKAGE)
    storyboard = _load(STORYBOARD)
    constraints = package["shots"][0]["continuityConstraints"]
    labels = {item["label"] for item in constraints}
    body = " ".join(item["value"] for item in constraints).lower()

    assert labels == {
        "Scene 3 handoff state",
        "Keen wristband state",
        "Boat cargo state",
        "Squeaky state",
        "Sailing physics",
    }
    for required in (
        "same little sailboat", "tan sail", "mast and rigging", "open satchel",
        "rolled blanket", "folded map", "food pouch", "exactly two inherited",
        "blank settings", "no crystals", "exactly one squeaky", "bow-first",
        "wake trails coherently", "left-to-right travel axis",
    ):
        assert required in body
    assert storyboard["shots"][0]["continuityConstraints"] == constraints


def test_every_scene4_unit_binds_the_sailboat_as_dedicated_visual_authority():
    package = _load(PACKAGE)
    for shot in package["shots"]:
        assert shot["requiredPropReferences"] == [
            "keen_sailboat", "keen_sailboat_departure_state"]
        assert "prop:keen_sailboat" in shot["referenceSlots"].values()
        assert "prop:keen_sailboat_departure_state" in shot["referenceSlots"].values()
        assert "prop:keen_sailboat" in shot["seedancePrompt"]
        assert "prop:keen_sailboat_departure_state" in shot["seedancePrompt"]
    opener = package["shots"][0]
    assert "prop:keen_sailboat" in opener["keyframeReferenceSlots"].values()
    assert "prop:keen_sailboat_departure_state" in opener["keyframeReferenceSlots"].values()
    assert "prop:keen_sailboat" in opener["keyframePrompt"]
    assert "prop:keen_sailboat_departure_state" in opener["keyframePrompt"]


def test_storyboard_and_package_share_current_recut_signature():
    package = _load(PACKAGE)
    storyboard = _load(STORYBOARD)
    assert len(storyboard["shots"]) == 3
    assert package["sourceStoryboard"]["inputSignature"] == storyboard["inputSignature"]
    assert cb_lineage.signature_matches(
        storyboard["inputSignature"],
        "scene-storyboard-snapshot",
        storyboard["inputSignature"]["inputs"],
    )
