#!/usr/bin/env python3
"""test_cb_intent.py — THE INTENT ENGINE.

Pinned against the real failure that created it (2026-07-25): a prompt written to pass all
nine recorded failure-checks, which delivered half the Director's stated beat. The engine
must catch that, and must never let a purely mechanical prompt score clean.
"""
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_intent as I

def _shot(sid="S1.SH2"):
    pkg = json.loads((HERE.parent / "shows" / "crystal-bears" / "episodes" / "output" /
                      "Ep1_scene1_production_package.json").read_text())
    return next(s for s in pkg["shots"] if s["shotId"] == sid)


def test_catches_the_prompt_that_passed_every_failure_check():
    """THE ORIGINATING FAILURE. SH2's card names the comedy hinge as 'the grin held too
    long'. A prompt was written that passed no-geometry, no-body-in-flower, identity,
    physics-chain, stasis — nine for nine — and contained no grin at all."""
    shot = _shot()
    p = (HERE.parent / "shows" / "crystal-bears" / "creative" / "fixtures" /
         "engine_ab" / "SH2_spine_build.txt").read_text()
    s = I.score(p, shot)
    assert s["total"] >= 8, "intent did not decompose into enough checkable clauses"
    assert s["coverage"] < 0.8, f"engine failed to catch the known gap (got {s['coverage']})"
    missed = " ".join(r["clause"].lower() for r in s["missed"])
    assert "grin-held-too-long" in missed, "the comedy hinge omission was not reported"
    assert any("gleeful" in r["missing"] or "playful" in r["missing"] for r in s["missed"]), \
        "the tempo/feel omissions were not reported"


def test_a_prompt_that_names_the_intent_scores_higher():
    """Directional sanity: adding the missing beats must raise coverage. Guards against a
    check that reports failure unconditionally, which would be just as useless as one that
    always passes."""
    shot = _shot()
    base = (HERE.parent / "shows" / "crystal-bears" / "creative" / "fixtures" /
            "engine_ab" / "SH2_spine_build.txt").read_text()
    better = base + ("\nHis flight is fast and gleeful, his joy driving the speed. He holds "
                     "a delighted grin far too long as the flower fills the frame — the "
                     "comedy hinge before one sharp impact. The recoil slows into the "
                     "discovery and stays playful and alive; the preen is its own beat, and "
                     "his showmanship physically betrays him.")
    assert I.score(better, shot)["coverage"] > I.score(base, shot)["coverage"]


def test_the_charge_leads_with_purpose_not_law():
    """The ordering IS the fix. Every prior charge opened with laws and buried purpose in a
    data field; the writer optimised for the laws."""
    c = I.charge(_shot())
    assert c.lstrip().startswith("===== WHAT THIS BEAT IS FOR")
    assert "This is the specification" in c
    assert "MUST BE VISIBLE ON SCREEN" in c
    head = c[:c.index("MUST BE VISIBLE")]
    assert "grin-held-too-long" in head or "comedy hinge" in head, \
        "the Director's own tempo words never reach the writer"


def test_a_shot_with_no_stated_intent_is_reported_not_faked():
    assert I.charge({"shotId": "X"}) is None
    assert I.score("some prompt", {"shotId": "X"})["total"] == 0
    assert "nothing to deliver against" in I.report("p", {"shotId": "X"})


if __name__ == "__main__":
    for fn in (test_catches_the_prompt_that_passed_every_failure_check,
               test_a_prompt_that_names_the_intent_scores_higher,
               test_the_charge_leads_with_purpose_not_law,
               test_a_shot_with_no_stated_intent_is_reported_not_faked):
        fn(); print("  ok ", fn.__name__)
    print("INTENT ENGINE PASSED")


def test_the_director_stops_the_shot():
    """THE DIRECTOR'S STOP. Not an advisory — a refusal. A prompt that omits what the
    Director wrote down does not reach the provider, exactly as a director on a stage pulls
    a take when the direction was not performed."""
    import cb_render as R, pathlib
    shot = _shot()
    bad = (HERE.parent / "shows" / "crystal-bears" / "creative" / "fixtures" /
           "engine_ab" / "SH2_spine_build.txt").read_text()
    try:
        R.check_formula_structure(bad, ["x"], shot=shot)
        raise AssertionError("the gate has no teeth — a half-delivered prompt was allowed")
    except R.Refused as e:
        assert "DIRECTOR'S DIRECTION IS NOT IN THE PROMPT" in str(e)
        # The refusal names the Director's own words. It used to pin the comedy-hinge
        # clause specifically; since the gate was calibrated to visualPayoff + feltIntent
        # (2026-07-25, against four prompts with real verdicts) the FIRST clause reported
        # is a different, equally real feltIntent miss. Pin the substance — that a named,
        # quoted clause of hers is reported missing — not which one sorts first.
        assert "she asked for" in str(e)
        assert any(w in str(e) for w in ("feltIntent", "visualPayoff"))


def test_the_gate_opens_when_the_direction_is_delivered():
    """A wall that never opens is not a gate. The corrected prompt — same shot, same laws,
    with the Director's five missing clauses written in — must pass."""
    import cb_render as R
    shot = _shot()
    good = (HERE.parent / "shows" / "crystal-bears" / "creative" / "fixtures" /
            "engine_ab" / "SH2_intent_delivered.txt").read_text()
    assert I.score(good, shot)["coverage"] == 1.0
    R.check_formula_structure(good, ["x"], shot=shot)      # must not raise


def test_a_missing_intent_engine_never_invents_a_refusal():
    """If cb_intent is absent the gate degrades silently — it never fabricates a stop."""
    import cb_render as R
    R.check_formula_structure("ENGLISH DIALOGUE ONLY, spoken in English. Use @Audio1 as the "
                              "sole source of dialogue, wording, voice, performance and "
                              "timing.", [], shot=None)


def test_both_prompts_are_engineered_from_the_direction():
    """JULIAN'S RULING, 2026-07-25: "the keyframe gives the stage which allows the
    performance to deliver and breathe — but BOTH those prompts are engineered FROM the
    director, not the other way around."

    So the stage (prepare_cinematography) and the performance (prepare_animation) must
    BOTH read the Director's stated intent, and must read it from the SAME place. Two
    readers would drift apart the first time one was edited — which is exactly how the
    animation chair ended up with the intent while the keyframe chair never saw it."""
    import cb_departments as D
    import inspect
    stage = inspect.getsource(D.prepare_cinematography)
    perf = inspect.getsource(D.prepare_animation)
    assert "_intent_charge" in stage, "the STAGE is not engineered from the direction"
    assert "_intent_charge" in perf, "the PERFORMANCE is not engineered from the direction"
    # the stage's charge must say what a stage is FOR, not merely be pretty
    assert "AFFORDS" in stage, "the stage's charge never asks it to afford the performance"

    # and the shared reader really returns the Director's own words on a real shot
    charge = D._intent_charge({"shot": _shot()})
    assert "WHAT THIS BEAT IS FOR" in charge
    assert "MUST BE VISIBLE ON SCREEN" in charge
    # silence when a shot states nothing — an invented purpose is worse than none
    assert D._intent_charge({"shot": {}}) == ""
    assert D._intent_charge({}) == ""
