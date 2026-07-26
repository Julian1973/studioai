#!/usr/bin/env python3
"""test_story_room.py — GUARDS ON THE ROOM ITSELF, NOT ON A PRODUCTION ARTEFACT.

These tests assert who is in the room and what context they hold. They need NO episode, NO
beat package and NO production data — which is exactly why they live here rather than in
test_cb_creative.py, whose module-level require_live_beat_package mark would silence them at
clean zero. That is the second time a blanket module mark has hidden tests that matter most
when the project is empty (the first was test_no_legacy_fingerprints.py, corrected the same
day). A guard that switches itself off when the pipeline is about to run for real is not a
guard.

    pytest test_story_room.py -q
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def test_step_one_convenes_the_whole_room():
    """THE MOST CONSEQUENTIAL PASS GETS THE MOST CONTEXT (2026-07-26).

    Julian: "step 1 has to be done properly... I knew when we were working further down the
    line the beats weren't landing and now we know why."

    cb_departments.prepare_story decides where EVERY beat begins and ends and authors
    want/need/kidRead/adultRead/emotionalIntent for the whole episode — the emotional
    architecture every later chair can only refine INSIDE. It used to run on the Director's
    runtime contract and the job text alone: no show bible, no taste canons, no exemplars, no
    Showrunner. Then the ten-gate creative room convened to design shots inside a shape it had
    no voice in choosing. The room got stronger as the decisions got smaller.

    It now routes through cb_creative._mind — the same room builder the creative gates use —
    so there is ONE room for the whole pipeline rather than two that drift. This test is the
    guard: it asserts the CONTEXT arrives, not the wording, so the charge can be rewritten
    freely without breaking it.

    Deliberately NOT guarded by require_live_beat_package: this needs no production data, and
    it matters most when the project is at clean zero and about to run a script for real."""
    import cb_departments as D
    import cb_llm

    captured = {}

    def _capture(system, user, schema, **kw):
        captured["system"] = system
        raise SystemExit("captured — no provider call")

    real = cb_llm.structured
    D.cb_llm.structured = _capture
    try:
        D.prepare_story([{"index": 0, "scene": 1, "type": "action", "text": "x"}],
                        {1: ["Fuzzby"]}, log=lambda *a, **k: None)
    except SystemExit:
        pass
    finally:
        D.cb_llm.structured = real

    m = captured.get("system", "")
    assert m, "prepare_story never reached the LLM boundary"
    for needed, what in (
            ("Crystal Bears Director", "the Director's runtime SKILL contract"),
            ("Crystal Bears Showrunner", "the Showrunner's contract — series truth in the room"),
            ("SHOW CANON", "the show bible"),
            ("TASTE CANON", "the taste canons"),
            ("APPROVED CANONICAL EXEMPLAR", "the approved exemplars"),
            ("verbatim-locked", "the dialogue lock")):
        assert needed in m, (
            f"step 1 lost {what}. This pass sets the episode's emotional architecture; a beat "
            f"boundary or an adultRead authored without it cannot be recovered downstream.")
    assert len(m) > 20000, (
        f"step 1's charge collapsed to {len(m)} chars — it was ~2,000 when it ran on the "
        f"Director alone and ~36,000 with the room. Something stopped assembling.")
