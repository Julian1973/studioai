import hashlib
import json
from pathlib import Path

import cb_emission_standard as standard
import cb_render


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
        assert flight["score"] >= standard.EMISSION_FIRING_FLOOR, (name, flight)
        assert flight["verdict"] == "PASS", (name, flight)
        assert manifest["ready"], (name, manifest)


def test_emission_firing_floor_is_nine_point_five():
    prompt = "Shot 1: Camera holds on the open flower. End state: The flower is open."
    flight = standard.preflight(prompt)
    assert standard.EMISSION_FIRING_FLOOR == 9.5
    assert flight["score"] == 9.25
    assert flight["firingFloor"] == 9.5
    assert flight["verdict"] == "BLOCK"


def test_duplicate_story_lock_is_a_mechanical_regression():
    prompt = (FIXTURES / "beat_1_chase.txt").read_text() + "\nStory lock: repeat it."
    flight = standard.preflight(prompt)
    assert any(item["rule"] == "R18" for item in flight["findings"])


def test_specialist_missing_hold_is_polish_until_typed_emitter_runs():
    prompt = (FIXTURES / "beat_1_chase.txt").read_text().replace(
        "The pose holds for a full beat after the line ends.", "")
    flight = standard.preflight(prompt)
    hold = [item for item in flight["findings"] if item["rule"] == "button-hold"]
    assert hold and hold[0]["severity"] == "POLISH"
    assert flight["score"] >= standard.EMISSION_FIRING_FLOOR


def test_separate_shot_ordinals_do_not_invent_repeated_contacts():
    prompt = """Shot 1: First companion appears. End state: Keen sees him.
Shot 2: A dolphin completes one water-to-air-to-water arc. End state: He re-enters.
Shot 3: Third view reveals home receding. End state: The boat sails onward.
No music."""

    flight = standard.preflight(prompt)

    assert not any(item["rule"] == "R10" for item in flight["findings"])


def test_true_repeated_contacts_still_require_escalation():
    prompt = """Shot 1: Fuzzby makes three readable impacts. End state: He settles.
No music."""

    flight = standard.preflight(prompt)

    assert any(item["rule"] == "R10" for item in flight["findings"])


def test_accepted_chase_prompt_and_local_render_match_recorded_provenance():
    provenance = json.loads((FIXTURES / "ACCEPTED_RENDER_PROVENANCE.json").read_text())
    prompt = FIXTURES / provenance["fixture"]
    assert hashlib.sha256(prompt.read_bytes()).hexdigest() == provenance["prompt"]["sha256"]

    render = Path(__file__).parent.parent / provenance["render"]["canonicalLocalPath"]
    if render.exists():
        assert hashlib.sha256(render.read_bytes()).hexdigest() == provenance["render"]["sha256"]


def test_render_path_uses_the_same_checker_and_timing_inputs():
    prompt = (FIXTURES / "beat_1_chase.txt").read_text()
    shot = {"durationSec": 16}
    specialist = {"timingBeats": [{"type": "travel", "count": 1}]}
    assert cb_render._emission_conformance_report(shot, specialist, prompt) == (
        standard.preflight(
            prompt,
            duration_sec=shot["durationSec"],
            timing_beats=specialist["timingBeats"],
        )
    )
