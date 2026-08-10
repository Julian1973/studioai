import json
from pathlib import Path

import cb_departments
import cb_emission_standard
import cb_render


ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "cb-output" / "creative" / "director-records" / "scene1-v1"
PACKAGE = ROOT / "cb-output" / "Ep1_scene1_production_package.json"
CASES = {
    "S1.SH1B": "reveal-and-deadpan-verdict",
    "S1.SH1C": "escalation-into-verdict",
    "S1.SH2": "environment-turn",
}


def test_scene1_director_records_recompile_deterministically_and_pass():
    package = json.loads(PACKAGE.read_text())
    shots = {item["shotId"]: item for item in package["shots"]}
    for shot_id, archetype in CASES.items():
        direction = cb_departments.AnimationDirection.model_validate(
            json.loads((RECORDS / f"{shot_id}.json").read_text()))
        creative_shot = cb_render._shot_creative_contract_view(
            package, shots[shot_id], 1, "Ep1")
        compiled = cb_departments.compile_animation_provider_prompt(
            creative_shot, direction)
        assert compiled == direction.providerPrompt
        assert compiled == (RECORDS / f"{shot_id}.prompt.txt").read_text().rstrip("\n")
        assert cb_emission_standard.preflight(
            compiled, duration_sec=direction.durationSec,
            timing_beats=[item.model_dump() for item in direction.timingBeats]
        )["score"] >= 9.0
        assert cb_emission_standard.manifest_checks(archetype, compiled)["ready"]
        assert cb_render._animation_prompt_contract_report(
            creative_shot, direction)["ready"]
        assert cb_render._engine_rule_report(
            package, creative_shot, direction, cinematography={})["ready"]
