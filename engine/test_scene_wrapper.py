import json
from pathlib import Path

import cb_engine
import paths as P  # T45: scratch worlds use the project layout


ROOT = Path(__file__).resolve().parents[1]


def _scene10_shot():
    # Use the tracked production-package schema as a deterministic wrapper fixture;
    # the wrapper contract is independent of a particular scene-10 generated output.
    pkg = json.loads((ROOT / f"{P.OUTPUT_REL}/Ep1_scene1_production_package.json").read_text())
    raw = dict(pkg["shots"][0])
    raw["shotId"] = "10.B1.S1"
    return pkg, raw


def test_establish_prompt_contains_wrapper_hold_and_ambient_rules():
    pkg, raw = _scene10_shot()
    raw = {**raw, "shotRole": "establish", "establishJob": "location",
           "frameSource": "chain_cut", "durationSec": 4.0, "dialogueLines": []}
    shot = cb_engine.Shot(**{k: v for k, v in raw.items()
                             if k in cb_engine.Shot.model_fields})
    prompt, _, _ = cb_engine.compile_shot_contract(
        shot, {}, json.load((ROOT / "engine/config/characters.json").open()))
    assert "[ESTABLISH — job: location]" in prompt
    assert "Ambient sound only, no dialogue" in prompt
    assert "held completely stable for the final full second" in prompt


def test_establish_validation_allows_ten_second_location_discovery():
    pkg, raw = _scene10_shot()
    raw = {**raw, "shotRole": "establish", "establishJob": "location",
           "frameSource": "chain_cut", "durationSec": 10.0, "dialogueLines": []}
    shot = cb_engine.Shot(**{k: v for k, v in raw.items()
                             if k in cb_engine.Shot.model_fields})
    design = cb_engine.SceneShotList(
        statement=cb_engine.DirectorStatement(**pkg["directorStatement"]), shots=[shot])
    report = cb_engine.validate_scene_design(
        design, [], json.load((ROOT / "engine/config/characters.json").open()))
    codes = {issue["code"] for issue in report["issues"]}
    assert "ESTABLISH_DURATION" not in codes


def test_fresh_establish_can_use_scene_plate_without_chain_source():
    pkg, raw = _scene10_shot()
    raw = {**raw, "shotRole": "establish", "establishJob": "emotion",
           "frameSource": "scene_plate", "durationSec": 4.0, "dialogueLines": []}
    shot = cb_engine.Shot(**{k: v for k, v in raw.items()
                             if k in cb_engine.Shot.model_fields})
    design = cb_engine.SceneShotList(
        statement=cb_engine.DirectorStatement(**pkg["directorStatement"]), shots=[shot])
    report = cb_engine.validate_scene_design(
        design, [], json.load((ROOT / "engine/config/characters.json").open()))
    codes = {issue["code"] for issue in report["issues"]}
    assert "WRAPPER_FRAME_SOURCE_MISSING" not in codes


def test_scene_may_open_and_close_on_coverage_when_story_demands_it():
    pkg, raw = _scene10_shot()
    raw = {**raw, "shotRole": "coverage", "establishJob": None,
           "buttonChange": None, "frameSource": None, "sourceType": "opener",
           "sourceShotId": None, "dialogueLines": []}
    shot = cb_engine.Shot(**{k: v for k, v in raw.items()
                             if k in cb_engine.Shot.model_fields})
    design = cb_engine.SceneShotList(
        statement=cb_engine.DirectorStatement(**pkg["directorStatement"]), shots=[shot])
    report = cb_engine.validate_scene_design(
        design, [], json.load((ROOT / "engine/config/characters.json").open()))
    codes = {issue["code"] for issue in report["issues"]}
    assert "WRAPPER_FRAME_SOURCE_MISSING" not in codes


def test_wrapper_validation_rejects_dialogue_on_button():
    pkg, raw = _scene10_shot()
    raw = {**raw, "shotRole": "button", "buttonChange": "the group leaves together",
           "frameSource": "chain_continue", "durationSec": 4.0}
    shot = cb_engine.Shot(**{k: v for k, v in raw.items()
                             if k in cb_engine.Shot.model_fields})
    design = cb_engine.SceneShotList(
        statement=cb_engine.DirectorStatement(**pkg["directorStatement"]), shots=[shot])
    report = cb_engine.validate_scene_design(
        design, [], json.load((ROOT / "engine/config/characters.json").open()))
    codes = {issue["code"] for issue in report["issues"]}
    assert "WRAPPER_DIALOGUE_FORBIDDEN" in codes
