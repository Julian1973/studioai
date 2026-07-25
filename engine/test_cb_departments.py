"""Focused proofs for the live department workers (all zero-provider-call)."""
import pytest

import cb_departments as D


def _locked():
    return [{"speaker": "FUZZBY", "exactText": "Nailed it.",
             "delivery": "[exhales] the crash converted into triumph mid-breath"}]


def test_every_studio_department_loads_a_real_runtime_skill_contract():
    people = D.roster()
    assert len(people) == 7
    assert all(p["loaded"] for p in people)
    assert {p["worker"] for p in people} >= {
        "Director", "Cinematographer / DP", "Voice Director",
        # the Director holds the animation chair too as of 2026-07-25 — she stages the
        # shot and directs the performance in it; "Animation Director / Camera" is gone.
        "Director Review / Continuity Supervisor",
        "Post Supervisor"}


def test_voice_director_may_act_but_not_rewrite_locked_words():
    valid = D.VoiceDirection(
        shotId="S1.SH1", doesItLand="the exhale sells the crash-into-triumph turn",
        lines=[D.VoiceLineDirection(
            speaker="FUZZBY", exactDialogue="Nailed it.",
            performedText="[exhales] NAILED it.")])
    assert D.validate_voice_direction(valid, _locked()) is valid

    changed = valid.model_copy(deep=True)
    changed.lines[0].performedText = "[exhales] Totally nailed it."
    with pytest.raises(RuntimeError, match="added, dropped or changed words"):
        D.validate_voice_direction(changed, _locked())


def test_prepare_voice_compiles_the_approved_direction_not_a_fresh_read(monkeypatch):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21): each line's own `delivery` — the
    Voice Performance role's already-directed V3 performance, following the show's Voice
    Performance Canon — must reach the prompt labelled as the definitive source, never
    buried unread inside a generic context dump."""
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        seen["user"] = user
        return schema(
            shotId="S1.SH1", doesItLand="the exhale sells the crash-into-triumph turn",
            lines=[D.VoiceLineDirection(
                speaker="FUZZBY", exactDialogue="Nailed it.",
                performedText="[exhales] NAILED it.")])

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    out = D.prepare_voice({"shotId": "S1.SH1"}, _locked(), log=lambda *a, **k: None)
    assert out.lines[0].performedText == "[exhales] NAILED it."
    assert out.doesItLand
    assert "Runtime worker contract — Voice Director" in seen["system"]
    assert "already made" in seen["system"]
    assert "APPROVED DIRECTION: [exhales] the crash converted into triumph mid-breath" in seen["user"]


def test_prepare_voice_degrades_gracefully_with_no_direction_authored_yet(monkeypatch):
    """A line with no delivery authored yet (an early-pipeline shot) must not crash —
    it's labelled explicitly rather than silently omitted."""
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["user"] = user
        return schema(shotId="S1.SH1", doesItLand="t",
                      lines=[D.VoiceLineDirection(speaker="FUZZBY", exactDialogue="Nailed it.",
                                                   performedText="Nailed it.")])

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    D.prepare_voice({"shotId": "S1.SH1"}, [{"speaker": "FUZZBY", "exactText": "Nailed it."}],
                     log=lambda *a, **k: None)
    assert "APPROVED DIRECTION: (none authored yet)" in seen["user"]
