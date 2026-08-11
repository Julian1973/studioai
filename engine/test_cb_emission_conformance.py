import pytest

import cb_emission_conformance as C


def test_aaa_registry_has_exactly_sixteen_unique_versioned_checks():
    assert C.AAA_PREFLIGHT_VERSION == "aaa-part-8-v2.1"
    assert [number for number, _ in C.AAA_PREFLIGHT_CHECKS] == list(range(1, 17))
    assert len({code for _, code in C.AAA_PREFLIGHT_CHECKS}) == 16
    assert set(C.AAA_CONFORMANCE) == set(range(1, 17))
    assert all(set(paths) == {"keyframe", "render", "voice"}
               for paths in C.AAA_CONFORMANCE.values())
    assert all(status in {"IMPLEMENTED+TESTED", "OPEN"}
               for paths in C.AAA_CONFORMANCE.values() for status in paths.values())


def test_time_tiles_cover_the_entire_route_without_gaps():
    tiles = C.time_tiles([
        {"stageNumber": 1}, {"stageNumber": 2}, {"stageNumber": 3},
    ], 9)
    assert [(item["startSec"], item["endSec"]) for item in tiles] == [
        (0.0, 3.0), (3.0, 6.0), (6.0, 9.0)]


def test_audio_cues_reject_regions_outside_the_route():
    with pytest.raises(C.EmissionConformanceError, match="outside the approved"):
        C.dialogue_cues([
            {"speaker": "Fuzzby", "startSec": 8.0, "endSec": 10.0},
        ], duration_sec=9)


def test_multi_character_instance_lock_is_exact_and_deduplicated():
    assert C.character_instance_lock(["Fuzzby", "Zenny", "fuzzby"]) == (
        "Exactly one Fuzzby and one Zenny throughout; no duplicates of either character.")
    assert C.character_instance_lock(["Fuzzby"]) == ""
    assert C.character_instance_lock(
        ["Fuzzby", "Zenny", "fuzzby"], medium="still") == (
        "Exactly one Fuzzby and one Zenny appear in this image.")
    with pytest.raises(ValueError, match="medium"):
        C.character_instance_lock(["Fuzzby", "Zenny"], medium="print")


def test_reference_slot_and_multi_angle_boilerplate_is_deterministic():
    assert C.reference_slot_stability_line([
        ("@图1", "opening frame"), ("@图2", "Zenny")]) == (
        "Project-stable slots: @图1=opening frame; @图2=Zenny. Never swap roles.")
    assert C.multi_angle_collapse_line("@图2", "Zenny") == (
        "@图2: all turnaround angles are one Zenny, not extra characters.")
    assert C.multi_angle_collapse_summary([
        ("@图1", "Zenny"), ("@图2", "Fuzzby")]) == (
        "Multi-angle collapse: @图1=one Zenny; @图2=one Fuzzby; views are angles, "
        "not extra characters.")


def test_dialogue_direction_requires_written_prose_and_hold_is_ruled():
    cue = {"speaker": "Performer", "exactText": "Now."}
    line = C.dialogue_placement_line(
        cue, direction="calm over covered fear", hold_after=False)
    assert line == "Dialogue placement: Performer, calm over covered fear: {Now.}"
    assert "hold" not in line.casefold()
    with pytest.raises(C.EmissionConformanceError, match="raw token"):
        C.dialogue_placement_line(cue, direction="exhales")
    with pytest.raises(C.EmissionConformanceError, match="raw token"):
        C.dialogue_placement_line(cue, direction="the approved")


def test_r17_drops_superseded_action_before_world_first_replacement():
    action = (
        "A performer reacts to thunder. Before either character reacts, the light cools "
        "and every flower closes.")
    contract = ["The environment changes completely before either character reacts."]
    assert C.drop_superseded_action_prefix(action, contract) == (
        "Before either character reacts, the light cools and every flower closes.")
    assert C.drop_superseded_action_prefix(action, []) == action


def test_instance_lock_equivalence_is_character_agnostic():
    assert C.is_instance_lock_equivalent(
        "Exactly one Alpha and one Beta throughout; no duplicates or blended identities.",
        ["Alpha", "Beta"])
    assert not C.is_instance_lock_equivalent(
        "Keep Alpha and Beta on the same route.", ["Alpha", "Beta"])
