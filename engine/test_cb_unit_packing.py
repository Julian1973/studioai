#!/usr/bin/env python3
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_unit_packing as P


def _unit(shot_id, seconds, reason, beat_ids=None, stages=3, internal_shots=3):
    return {
        "shotId": shot_id,
        "beatIds": beat_ids or [shot_id + ".B"],
        "targetDurationSec": seconds,
        "stagePlan": [{"stageNumber": i + 1} for i in range(stages)],
        "internalShotPlan": [{"shotNumber": i + 1} for i in range(internal_shots)],
        "providerBoundaryReason": reason,
        "providerBoundaryExplanation": f"Observable production reason for {reason}.",
    }


def test_full_thirty_second_scene_is_reported_without_padding_claims():
    audit = P.audit_units([_unit("S1.SH1", 30, "scene_end", ["1.B1", "1.B2"])])
    assert audit["ready"] is True
    assert audit["fullThirtySecondUnitIds"] == ["S1.SH1"]
    assert audit["multiBeatUnitCount"] == 1
    assert audit["beatReduction"] == 1


def test_duration_limit_cannot_hide_an_avoidable_provider_join():
    audit = P.audit_units([
        _unit("S1.SH1", 12, "duration_limit"),
        _unit("S1.SH2", 14, "scene_end"),
    ])
    assert audit["ready"] is False
    assert audit["blockingIssues"][0]["code"] == "FALSE_DURATION_SPLIT"


def test_duration_limit_is_valid_when_combined_performance_exceeds_thirty_seconds():
    audit = P.audit_units([
        _unit("S1.SH1", 18, "duration_limit"),
        _unit("S1.SH2", 18, "scene_end"),
    ])
    assert audit["ready"] is True
    assert audit["protectedSplits"][0]["combinedDurationSec"] == 36
    assert not audit["mergeReviewRequired"]


def test_short_dramatic_split_is_visible_for_showrunner_merge_review():
    audit = P.audit_units([
        _unit("S1.SH1", 13, "dramatic_editorial_break"),
        _unit("S1.SH2", 14, "scene_end"),
    ])
    assert audit["ready"] is True
    assert audit["needsHumanMergeReview"] is True
    assert audit["mergeReviewRequired"][0]["combinedDurationSec"] == 27


def test_emotional_continuity_split_under_thirty_seconds_blocks_without_real_loss():
    first = _unit("S1.SH1", 16, "dramatic_editorial_break", ["1.B1"])
    first["purpose"] = "A quiet leaving home goodbye: child packs while Mum hides worry."
    first["providerBoundaryExplanation"] = "Cut here because this is the next paragraph."
    second = _unit("S1.SH2", 9, "scene_end", ["1.B2"])
    second["purpose"] = "The child swallows, borrows courage and tries to be brave."

    audit = P.audit_units([first, second])

    assert audit["ready"] is False
    assert audit["blockingIssues"][0]["code"] == "AVOIDABLE_EMOTIONAL_SPLIT"
    assert "emotional-continuity" in audit["blockingIssues"][0]["message"]


def test_emotional_continuity_split_is_allowed_for_specific_object_handoff():
    first = _unit("S1.SH1", 16, "dramatic_editorial_break", ["1.B1"])
    first["purpose"] = "A quiet leaving home goodbye: child packs while Mum hides worry."
    first["providerBoundaryExplanation"] = (
        "The next unit introduces a new wristband object handoff and needs a new reference.")
    second = _unit("S1.SH2", 9, "scene_end", ["1.B2"])
    second["purpose"] = "The child swallows, borrows courage and tries to be brave."

    audit = P.audit_units([first, second])

    assert audit["ready"] is True
    assert audit["needsHumanMergeReview"] is True
    assert audit["mergeReviewRequired"][0]["combinedDurationSec"] == 25


def test_reference_change_protects_a_short_boundary():
    audit = P.audit_units([
        _unit("S1.SH1", 11, "reference_regime_change"),
        _unit("S1.SH2", 12, "scene_end"),
    ])
    assert audit["ready"] is True
    assert not audit["mergeReviewRequired"]
    assert audit["protectedSplits"][0]["reason"] == "reference_regime_change"


def test_only_last_unit_can_close_the_scene():
    audit = P.audit_units([
        _unit("S1.SH1", 20, "scene_end"),
        _unit("S1.SH2", 20, "scene_end"),
    ])
    assert audit["ready"] is False
    assert audit["blockingIssues"][0]["code"] == "EARLY_SCENE_END"


def test_thirty_seconds_does_not_excuse_an_overpacked_unit():
    audit = P.audit_units([
        _unit("S1.SH1", 28, "scene_end", ["1.B1", "1.B2", "1.B3"],
              stages=4, internal_shots=6),
    ])
    assert audit["ready"] is False
    assert audit["blockingIssues"][0]["code"] == "UNIT_COMPLEXITY_EXCEEDED"
    assert audit["unitComplexity"] == [{
        "shotId": "S1.SH1", "stageCount": 4, "internalShotCount": 6,
        "complexitySignals": [],
        "withinStandard": False,
    }]


def test_long_unit_is_valid_when_its_story_grammar_stays_compact():
    audit = P.audit_units([
        _unit("S1.SH1", 30, "scene_end", ["1.B1", "1.B2", "1.B3"],
              stages=3, internal_shots=3),
    ])
    assert audit["ready"] is True
    assert audit["maxStagesPerUnit"] == 3
    assert audit["maxInternalShotsPerUnit"] == 3


def test_long_physical_reveal_unit_gets_showrunner_complexity_review():
    unit = _unit("S1.SH1", 29, "scene_end", ["1.B1", "1.B2", "1.B3"])
    unit["purpose"] = (
        "Fast chase, crash, flower moustache reveal and physical comedy tumble.")
    unit["visualPayoff"] = "Fuzzby lands with a flower-caused moustache."
    audit = P.audit_units([unit])
    assert audit["ready"] is True
    assert audit["needsHumanMergeReview"] is True
    assert audit["mergeReviewRequired"][0]["reason"] == "complexity_review"
    assert "moustache" in audit["unitComplexity"][0]["complexitySignals"]
    assert "handoff frame" in audit["executionPolicy"]["continuity"]
    assert "ElevenLabs scene-level music cue after stitch" in audit["executionPolicy"]["music"]
