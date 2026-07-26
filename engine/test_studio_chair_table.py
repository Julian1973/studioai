#!/usr/bin/env python3
"""test_studio_chair_table.py — THE STUDIO SHOWS THE REAL CHAIRS (2026-07-25).

Julian moved the chairs (the Director to delivery: she stages the opening frame, directs
cadence with the Voice Director, owns the animation prompt, sits in the review) and then
asked the obvious question — "the studio pipeline now has to reflect this and we need to
test that this is now running."

It did not. The engine's table changed and the Studio kept showing the old titles, because
app.html hardcodes them client-side rather than reading the server's own roster. Worse, the
engine itself had TWO independent chair tables (cb_render._DEPARTMENT_WORKERS and
cb_departments.SKILLS/DEPARTMENTS) — re-pointing one changed nothing at all.

So this file is the binding: the labels a human reads must equal the table the code obeys.
It is a static text check on purpose — no server, no browser, no network — so it runs in
the ordinary suite and fails the moment anyone edits one side alone.

    pytest test_studio_chair_table.py -q
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_departments as D
import cb_render as R

APP = HERE.parent / "cb-studio" / "app.html"

# Every label retired by the restructure. A rendered occurrence of any of these means the
# Studio is telling Julian a chair holder who no longer holds that chair.
RETIRED = ("Animation Director / Camera",
           "Director Review / Continuity Supervisor")


def _app():
    return APP.read_text(encoding="utf-8")


def test_the_two_engine_chair_tables_agree_with_each_other():
    """The bug that started this: two tables, only one of which decided anything. Whatever
    else is true, they must not disagree about who holds a chair or which craft contract
    loads."""
    roster = {d["id"]: d for d in D.DEPARTMENTS}
    # animation is the one genuine transfer — the Director owns the prompt outright.
    assert R._DEPARTMENT_WORKERS["animation"][1] == "Director"
    assert R._DEPARTMENT_WORKERS["animation"][2] == "director"
    assert roster["animation"]["worker"] == "Director"
    assert roster["animation"]["skill"] == "crystal-bears-director"
    assert D.SKILLS["animation"].parent.name == "crystal-bears-director"

    # ...and the specialists keep their own craft contracts. "She sits in the review" is
    # not "she is the only one in the review": a chair move that collapsed two chairs into
    # one would satisfy every label assertion above and still be wrong.
    assert R._DEPARTMENT_WORKERS["cinematography"][2] == "cinematographer"
    assert R._DEPARTMENT_WORKERS["voice"][2] == "voice-director"
    assert R._DEPARTMENT_WORKERS["review-keyframe"][2] == "continuity"
    assert R._DEPARTMENT_WORKERS["review-animation"][2] == "continuity"


def test_the_loaded_animation_skill_is_not_the_stale_camera_document():
    """The camera SKILL.md the Director's chair displaced carried five stale markers —
    10-12s beats (retired by the 15s Handle Doctrine) and the retired FRAME CHAIN
    mechanism. Loading it would feed contradictions straight into a live prompt."""
    text = D.SKILLS["animation"].read_text(encoding="utf-8")
    stale = re.findall(r"10-12s|FRAME CHAIN", text)
    assert not stale, f"the animation chair loads a document with stale doctrine: {stale}"


def test_the_studio_never_renders_a_retired_chair_title():
    app = _app()
    for label in RETIRED:
        assert label not in app, (
            f"cb-studio/app.html still shows the retired chair title {label!r} — the Studio "
            f"is naming a holder who no longer holds that chair")


def test_every_studio_chair_label_matches_the_engine_table():
    """The real binding. For each production stage, the worker title app.html renders must
    be the one cb_render._DEPARTMENT_WORKERS actually obeys — checked by looking the exact
    engine string up in the page, so editing either side alone fails here."""
    app = _app()
    for stage in ("cinematography", "voice", "animation"):
        worker = R._DEPARTMENT_WORKERS[stage][1]
        assert worker in app, (
            f"the Studio never shows {stage}'s real worker title {worker!r} — app.html's "
            f"hardcoded chair labels have drifted from the engine's own table")


def test_base_url_follows_the_page_origin():
    """Not a chair, but the same class of defect and it lands on the same screen: BASE was
    pinned to localhost while the studio was browsed at 127.0.0.1, so every fetch tripped
    CORS and the UI reported 'Can't reach the studio server' over a page that had loaded
    its data fine."""
    app = _app()
    assert 'const BASE="http://localhost:8765";' not in app, (
        "BASE is hardcoded to localhost again — browsing on 127.0.0.1 will break every call")
    assert "location.origin" in app


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
