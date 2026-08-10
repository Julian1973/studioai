import hashlib
import json
from pathlib import Path

import cb_emission_standard as standard


FIXTURES = Path(__file__).parent / "grammar" / "golden-fixtures" / "scene1-v1"
CASES = {
    "beat_1_chase.txt": "false-triumph-chase",
    "beat_2_moustache.txt": "reveal-and-deadpan-verdict",
    "beat_3_crash.txt": "escalation-into-verdict",
    "beat_4_storm.txt": "environment-turn",
}


def test_golden_fixtures_score_at_least_nine_and_pass_manifests():
    for name, archetype in CASES.items():
        prompt = (FIXTURES / name).read_text()
        flight = standard.preflight(prompt)
        manifest = standard.manifest_checks(archetype, prompt)
        assert flight["score"] >= 9.0, (name, flight)
        assert manifest["ready"], (name, manifest)


def test_duplicate_story_lock_is_a_mechanical_regression():
    prompt = (FIXTURES / "beat_1_chase.txt").read_text() + "\nStory lock: repeat it."
    flight = standard.preflight(prompt)
    assert any(item["rule"] == "R18" for item in flight["findings"])


def test_accepted_chase_prompt_and_local_render_match_recorded_provenance():
    provenance = json.loads((FIXTURES / "ACCEPTED_RENDER_PROVENANCE.json").read_text())
    prompt = FIXTURES / provenance["fixture"]
    assert hashlib.sha256(prompt.read_bytes()).hexdigest() == provenance["prompt"]["sha256"]

    render = Path(__file__).parent.parent / provenance["render"]["canonicalLocalPath"]
    if render.exists():
        assert hashlib.sha256(render.read_bytes()).hexdigest() == provenance["render"]["sha256"]
