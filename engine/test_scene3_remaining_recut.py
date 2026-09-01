import json
from pathlib import Path

import cb_engine_rules
import cb_state
import paths as P  # T45: scratch worlds use the project layout


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene3_production_package.json"


def _package():
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def _shot(package, shot_id):
    return next(shot for shot in package["shots"] if shot["shotId"] == shot_id)


def test_scene3_finishes_as_two_active_generation_units():
    package = _package()
    b5 = _shot(package, "3.B5.S1")
    b6 = _shot(package, "3.B6.S1")
    b7 = _shot(package, "3.B7.S1")
    b8 = _shot(package, "3.B8.S1")

    assert b5["beatCodes"] == ["3.B5", "3.B6"]
    assert b5["durationSec"] == 30
    assert [line["text"] for line in b5["dialogueLines"]][-1] == "Still got it!"
    assert b6["status"] == "superseded"
    assert b6["supersededBy"] == "3.B5.S1"

    assert b7["beatCodes"] == ["3.B7", "3.B8"]
    assert b7["durationSec"] == 24
    assert b7["sourceShotId"] == "3.B5.S1"
    assert "Squeaky" in b7["charactersInFrame"]
    assert b8["status"] == "superseded"
    assert b8["supersededBy"] == "3.B7.S1"


def test_combined_units_preserve_wristband_and_scene_continuity():
    package = _package()
    for shot_id in ("3.B5.S1", "3.B7.S1"):
        shot = _shot(package, shot_id)
        constraints = json.dumps(shot["continuityConstraints"], ensure_ascii=False).lower()
        assert "blank settings" in constraints
        assert "no crystals" in constraints
        assert "pier" in constraints
        assert "cargo" in constraints

    assert "do not repeat or restage the fitting" in _shot(package, "3.B5.S1")["action"]


def test_combined_departure_carries_visible_r9_traversal_evidence():
    action = _shot(_package(), "3.B5.S1")["action"].lower()

    assert "three parallax speeds" in action
    assert "vanishes behind" in action
    assert "smaller as it moves away" in action
    assert "drift off-centre" in action
    assert "wipes across the lens" in action


def test_combined_departure_obeys_wind_powered_sailing_causality():
    shot = _shot(_package(), "3.B5.S1")
    clause = cb_engine_rules.sailing_departure_boilerplate(shot, {})

    assert "mooring line is visibly released" in clause
    assert "controls the sheet or boom" in clause
    assert "Wind visibly fills and tensions the sail" in clause
    assert "only after that load does the hull heel slightly" in clause


def test_superseded_units_are_excluded_from_live_production_state():
    package = _package()

    assert [shot["shotId"] for shot in cb_state._active_package_shots(package)] == [
        "3.B1.S1",
        "3.B3.S1",
        "3.B5.S1",
        "3.B7.S1",
    ]
