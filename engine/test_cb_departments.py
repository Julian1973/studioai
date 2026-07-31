"""Focused proofs for the live department workers (all zero-provider-call)."""
import pytest

import cb_departments as D


def _locked():
    return [{"speaker": "FUZZBY", "exactText": "Nailed it."}]


def test_every_studio_department_loads_a_real_runtime_skill_contract():
    people = D.roster()
    assert len(people) == 7
    assert all(p["loaded"] for p in people)
    assert {p["worker"] for p in people} >= {
        "Director", "Cinematographer / DP", "Voice Director",
        "Seedance Production Director", "Director Review / Continuity Supervisor",
        "Post Supervisor"}


def test_voice_director_may_act_but_not_rewrite_locked_words():
    valid = D.VoiceDirection(
        shotId="S1.SH1", sceneIntention="cover the wobble",
        lines=[D.VoiceLineDirection(
            speaker="FUZZBY", exactDialogue="Nailed it.",
            performedText="[nervous] NAILED... it.", dramaticIntention="sell control",
            subtext="the body disagrees", cadenceAndBreath="too bright",
            timingAndBody="after the rebound")])
    assert D.validate_voice_direction(valid, _locked()) is valid

    changed = valid.model_copy(deep=True)
    changed.lines[0].performedText = "[nervous] Totally nailed it."
    with pytest.raises(RuntimeError, match="added, dropped or changed words"):
        D.validate_voice_direction(changed, _locked())


def test_prepare_voice_loads_the_skill_and_stops_at_structured_candidate(monkeypatch):
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        return schema(
            shotId="S1.SH1", sceneIntention="cover the wobble",
            lines=[D.VoiceLineDirection(
                speaker="FUZZBY", exactDialogue="Nailed it.",
                performedText="[nervous] Nailed it.", dramaticIntention="sell control",
                subtext="the body disagrees", cadenceAndBreath="too bright",
                timingAndBody="after the rebound")])

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    out = D.prepare_voice({"shotId": "S1.SH1"}, _locked(), log=lambda *a, **k: None)
    assert out.lines[0].performedText == "[nervous] Nailed it."
    assert "Runtime worker contract — Voice Director" in seen["system"]


def test_seedance_director_returns_shot_plan_and_separate_reference_contract(monkeypatch):
    seen = {}

    def fake(system, user, schema, **kwargs):
        seen["system"] = system
        seen["user"] = user
        return schema(
            shotId="S1.SH1",
            dramaticBeat="Fuzzby performs confidence while the wobble exposes him.",
            audienceBefore="Amused anticipation.",
            audienceAfter="A laugh with affection.",
            beatOwner="Fuzzby",
            performanceFreedom="Seedance may discover the micro-reaction, overlap and recovery cadence.",
            performanceArc="Bright control tightens into a tiny private flinch.",
            physicalCauseAndEffect="His planted paw shifts the loose plank, causing the wobble.",
            cameraBehaviour="A restrained 40mm push reveals the instability.",
            timingAndRhythm="Hold, wobble, reaction, clean landing.",
            landingBreath="Let the recovered pose register before handing off.",
            directionDensity="guided",
            precisionReasons=[],
            shotPlan=[D.InternalShotDirection(
                shotNumber=1, purpose="Reveal the false confidence",
                framingLensAndCamera="Medium 40mm, slow motivated push",
                causalAction="His paw loads the plank and the deck kicks back",
                observablePerformance="His smile holds as his eyes flick down",
                compositionLightAndMaterials="Layered deck depth, warm rim on tactile fur",
                landingImage="He settles in a readable off-balance silhouette")],
            referenceContract=[D.ReferenceDirection(
                assetTag="@Image1", role="opening_frame",
                controls="Exact opening state and composition", scope="continuity")],
            continuityFinish="End on the approved handoff silhouette.",
            surgicalSafeguards=["Preserve relative scale"],
            providerPrompt=(
                "Begin on the exact approved opening frame. Medium 40mm, the camera makes "
                "a restrained push because Fuzzby's planted paw loads the loose plank, "
                "causing the deck to kick back. His smile holds while his eyes flick down. "
                "Warm rim light shapes tactile fur against layered deck depth. Preserve "
                "identity and relative scale from @Image1. Land on his readable off-balance "
                "silhouette as the final continuity handoff."))

    monkeypatch.setattr(D.cb_llm, "structured", fake)
    out = D.prepare_animation(
        {"shot": {"shotId": "S1.SH1"}, "referenceSlots": {"@Image1": "opening frame"}},
        ["opening.png"], log=lambda *a, **k: None)
    assert len(out.shotPlan) == 1
    assert out.referenceContract[0].assetTag == "@Image1"
    assert "Runtime worker contract — Seedance Production Director" in seen["system"]
    assert "Keep every spoken word out of providerPrompt" in seen["user"]
