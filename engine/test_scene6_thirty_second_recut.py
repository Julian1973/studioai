import importlib.util
import json
import pathlib
import paths as P  # T45: scratch worlds use the project layout


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "engine" / "tools" / "recut_scene6_thirty_second_units.py"


def test_scene6_recut_script_preserves_all_beats_and_dialogue():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "B1+B2 (26s)" in source
    assert "B3+B4 (28s)" in source
    assert "protected B5 beacon payoff (6s)" in source
    assert "dialogueOccurrenceIds" in source
    assert "sourceBeatIds" in source


def test_current_scene6_package_is_three_story_led_units():
    path = ROOT / P.OUTPUT_REL / "Ep1_scene6_production_package.json"
    if not path.exists():
        return
    package = json.loads(path.read_text(encoding="utf-8"))
    if package.get("revision", 1) < 2:
        return
    shots = package["shots"]
    assert [(shot["shotId"], shot["durationSec"]) for shot in shots] == [
        ("6.B1.S1", 26), ("6.B3.S1", 28), ("6.B5.S1", 6)]
    assert len(shots[0]["dialogueOccurrenceIds"]) == 4
    assert len(shots[1]["dialogueOccurrenceIds"]) == 4
    assert shots[2]["dialogueOccurrenceIds"] == []
    assert shots[1]["sourceShotId"] == "6.B1.S1"
    assert shots[2]["sourceShotId"] == "6.B3.S1"
    assert "scene plate" in shots[0]["keyframeReferenceSlots"].values()
    assert set(shots[0]["openingCharactersInFrame"]).issubset(
        set(shots[0]["keyframeReferenceSlots"].values()))
    assert shots[0]["referenceSlots"]["@图1"] == "opening keyframe"
    assert shots[0]["referenceSlots"]["@Audio1"] == "voice track"
    assert shots[0]["openingCharactersInFrame"] == [
        "Aida", "Amie", "Howey", "Luna", "Misty", "Sunny"]
    assert "Fuzzby" not in shots[0]["keyframeReferenceSlots"].values()
    assert "Zenny" not in shots[0]["keyframeReferenceSlots"].values()
    assert "Fuzzby" in shots[0]["referenceSlots"].values()
    assert "Zenny" in shots[0]["referenceSlots"].values()
