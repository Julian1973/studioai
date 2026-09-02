"""T71 (2026-09-02): the project format and the writer's shot plan — the fast path's facts."""
import types

import cb_format
import project_profile


def _beat(scene, code, first, last, actions):
    return {"sceneNumber": scene, "beatCode": code,
            "sourceEventRange": {"firstEventIndex": first, "lastEventIndex": last},
            "storyBeat": f"story of {code}", "want": "w", "need": "n", "kidRead": "kid",
            "adultRead": "adult", "emotionalIntent": "intent", "location": "CLASSROOM",
            "cuts": [{"n": i + 1, "sourceEventIndex": first + i, "action": a, "sourceType": "action"}
                     for i, a in enumerate(actions)]}


PKG = {"beats": [
    _beat(1, "S01B01", 0, 4, ["Runtime: 1 minute", "Shot 01: Reading Goes Wrong",
                              "Jenny stands.", "Final Frame: Jenny frozen.", "x"]),
    _beat(1, "S01B02", 5, 7, ["Shot 02: The Feeling Stays", "Jenny sits.", "Final Frame: bag."]),
    _beat(1, "S01B03", 8, 9, ["She breathes.", "The bell goes."]),          # no heading: Shot 02's tail
    _beat(2, "S02B01", 10, 13, ["Shot 03: The Shoebox", "Jenny kneels.",
                                "Shot 04: The Box Calls", "Final Frame: light."]),  # straddles
    _beat(3, "S03B01", 14, 15, ["INT. COVE - DAY", "A screenplay scene."]),
]}


def test_writer_shot_plan_assigns_beats_to_headings_in_order():
    plan = cb_format.writer_shot_plan(PKG, 1)
    assert [(p["shotNumber"], p["title"], p["beatIds"]) for p in plan] == [
        (1, "Reading Goes Wrong", ["S01B01"]),
        (2, "The Feeling Stays", ["S01B02", "S01B03"]),
    ]
    assert all(not p["notes"] for p in plan)


def test_a_straddling_beat_stays_whole_and_is_reported():
    plan = cb_format.writer_shot_plan(PKG, 2)
    assert [(p["shotNumber"], p["beatIds"]) for p in plan] == [(3, ["S02B01"])]
    assert "Shot 03, Shot 04" in plan[0]["notes"][0]


def test_a_screenplay_scene_has_no_plan_and_keeps_the_creative_room():
    assert cb_format.writer_shot_plan(PKG, 3) is None
    assert cb_format.writer_shot_plan(PKG, 9) is None


def test_default_project_declares_no_format():
    # Crystal Bears never declared one: natural packing, full Creative Room, byte-identical
    assert cb_format.shot_seconds() is None or isinstance(cb_format.shot_seconds(), int)


def test_format_profile_parses_and_rejects_nonsense():
    fmt = project_profile.FormatProfile.model_validate(
        {"_note": "x", "shotSeconds": 30, "scriptStyle": "treatment", "fps": 24})
    assert fmt.shotSeconds == 30 and fmt.scriptStyle == "treatment"
    try:
        project_profile.FormatProfile.model_validate({"shotSeconds": 45})
    except Exception:
        pass
    else:
        raise AssertionError("a unit longer than the provider's 30s must be refused")


class _Shot(types.SimpleNamespace):
    pass


def test_enforce_units_sets_the_format_fields_and_reports_beat_disagreement():
    plan = cb_format.writer_shot_plan(PKG, 1)
    shots = [_Shot(shotId="S1.SH1", beatIds=["S01B01"], targetDurationSec=12,
                   transitionType="CONTINUOUS", providerBoundaryReason="complexity_protection",
                   providerBoundaryExplanation="", performanceBudget=None),
             _Shot(shotId="S1.SH2", beatIds=["S01B02", "S01B03"], targetDurationSec=18,
                   transitionType="CONTINUOUS", providerBoundaryReason="duration_limit",
                   providerBoundaryExplanation="x", performanceBudget=None)]
    shots, problems = cb_format.enforce_units(shots, 1, plan, 30)
    assert problems == []
    assert [s.shotId for s in shots] == ["S1.SH01", "S1.SH02"]
    assert all(s.targetDurationSec == 30 and s.transitionType == "PLANNED_CUT" for s in shots)
    assert shots[0].providerBoundaryReason == "duration_limit"
    assert shots[1].providerBoundaryReason == "scene_end"
    assert shots[0].providerBoundaryExplanation

    bad = [_Shot(shotId="a", beatIds=["S01B01", "S01B02"], targetDurationSec=30,
                 transitionType="PLANNED_CUT", providerBoundaryReason="scene_end",
                 providerBoundaryExplanation="x", performanceBudget=None)]
    _, problems = cb_format.enforce_units(bad, 1, plan, 30)
    assert problems and "exactly 2 unit(s)" in problems[0]


def test_writer_treatment_is_built_only_from_approved_material():
    plan = cb_format.writer_shot_plan(PKG, 1)
    t = cb_format.writer_treatment(PKG, 1, plan, 30)
    assert t["name"].endswith("CLASSROOM")
    assert "Reading Goes Wrong -> The Feeling Stays" == t["rhythmAndEscalation"]
    assert t["closingImage"] == "bag."
    sel = cb_format.writer_selection(t, plan)
    assert sel["selectedTreatment"] == t["name"] and sel["governingAudienceExperience"]
