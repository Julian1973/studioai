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
