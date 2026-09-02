import json
from pathlib import Path

import cb_departments
import cb_emission_standard
import cb_render
import paths as P  # T45: scratch worlds use the project layout


ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / P.OUTPUT_REL / "creative" / "director-records" / "scene1-v1"
PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene1_production_package.json"
CASES = {
    "S1.SH1B": "reveal-and-deadpan-verdict",
    "S1.SH1C": "escalation-into-verdict",
    "S1.SH2": "environment-turn",
}


def _shot_block(prompt, number):
    import re
    match = re.search(
        rf"Shot {number}:\s*(.*?)(?=\nShot \d+:|\nWitness staging:|\n\[|\Z)",
        prompt, re.S)
    assert match, f"Shot {number} block missing"
    return match.group(1)


def test_scene1_director_records_recompile_deterministically_and_pass():
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    shots = {item["shotId"]: item for item in package["shots"]}
    for shot_id, archetype in CASES.items():
        direction = cb_departments.AnimationDirection.model_validate(
            json.loads((RECORDS / f"{shot_id}.json").read_text(encoding="utf-8")))
        creative_shot = cb_render._shot_creative_contract_view(
            package, shots[shot_id], 1, "Ep1")
        compiled = cb_departments.compile_animation_provider_prompt(
            creative_shot, direction)
        # The record remains the approved source direction; the current compiler is
        # authoritative for provider emission and is tested for deterministic replay.
        assert compiled == cb_departments.compile_animation_provider_prompt(
            creative_shot, direction)
        direction.providerPrompt = compiled
        assert cb_emission_standard.preflight(
            compiled, duration_sec=direction.durationSec,
            timing_beats=[item.model_dump() for item in direction.timingBeats]
        )["score"] >= 9.0
        assert cb_emission_standard.manifest_checks(archetype, compiled)["ready"]
        assert cb_render._animation_prompt_contract_report(
            creative_shot, direction)["ready"]
        assert cb_render._engine_rule_report(
            package, creative_shot, direction, cinematography={})["ready"]


def test_s1s4_corrected_emission_fixture_and_regressions():
    direction = cb_departments.AnimationDirection.model_validate(
        json.loads((RECORDS / "S1.SH2.json").read_text(encoding="utf-8")))
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    shot = next(item for item in package["shots"] if item["shotId"] == "S1.SH2")
    prompt = cb_departments.compile_animation_provider_prompt(
        cb_render._shot_creative_contract_view(package, shot, 1, "Ep1"), direction)
    golden = (ROOT / "engine" / "grammar" / "golden-fixtures" /
              "scene1-v1" / "beat_4_storm.txt").read_text(encoding="utf-8").rstrip("\n")
    target = (RECORDS / "S1.SH2_user_prompt_target_20260811.txt").read_text(encoding="utf-8").rstrip("\n")

    assert golden == target
    assert "A distant thunder rumble interrupts the pollen aftermath; Fuzzby pauses" not in prompt
    assert "Fuzzby answers the warning, accelerates as if proving it" not in prompt
    assert "@图1 is the first frame and the previous shot's approved final frame." in prompt
    assert "Fuzzby is frame-left, coated in golden pollen" in prompt
    assert "with exhales delivery" not in prompt
    assert "with quietly delivery" not in prompt
    assert "with the approved delivery" not in prompt
    assert "Spoken action: Fuzzby, performed calm over covered fear:" in prompt
    assert "Spoken action: Zenny, quiet and unhurried, without drama:" in prompt
    assert "Spoken action: Fuzzby, at full volume, before the launch:" in prompt
    assert "pose holds a full beat after the line ends" not in _shot_block(prompt, 3)
    assert prompt.count("Exactly one Fuzzby and one Zenny throughout") == 1
    assert "No watermark." in prompt
