#!/usr/bin/env python3
"""test_cb_creative.py — focused tests for the Creative Room (§11). Fully mocked LLM;
these prove canon loading, provenance, role order, schema validity, dialogue preservation,
revision caps, escalation and provider-brief separation — NEVER creative excellence.

    pytest test_cb_creative.py -q
"""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_creative as C
import cb_llm


def _beat_stub():
    return C.Beat(beatId="1.B1", sceneId="S1", sourceScript="Fuzzby crashes into pride.",
                  exactDialogue=["FUZZBY: Nailed it."], participatingCharacters=["Fuzzby"],
                  objectiveByCharacter="Fuzzby: impress Zenny", opposition="his own speed",
                  subtext="wants approval", beginningState="rocketing", pressure="momentum",
                  actionDiscoveryOrChoice="overshoots", reversalReleaseOrRecognition="leaf FWIP",
                  consequence="rebound", reaction="claims triumph", closingState="proud hover",
                  intendedAudienceResponse="laugh", comedyOrEmotionEngine="overcommitment",
                  energyCurve="rising", memorableImage="bee frozen mid-brag",
                  interpretations=[C.Interpretation(name=n, dramaticConstruction=n,
                                                     characterBehaviour=n, audienceExperience=n)
                                    for n in ("A", "B", "C")],
                  selectedDirectorialInterpretation="A", selectionReason="character truth")


def _shot_stub(shot_id="1.B1.S1", transition="PLANNED_CUT"):
    f = {k: "x" for k in ("purpose", "intendedDurationRange", "openingComposition",
         "openingCharacterState", "blocking", "principalPerformance", "secondaryPerformance",
         "animationAndPhysics", "gazeAndExpression", "audiencePointOfView", "shotSize",
         "cameraHeight", "cameraAngle", "lensFeeling", "depthAndParallax", "cameraBehaviour",
         "lightingAndAtmosphere", "dialoguePlacement", "soundRelationship",
         "closingComposition", "closingCharacterState", "cutMotivation", "continuityIn",
         "continuityOut")}
    return C.Shot(shotId=shot_id, beatId="1.B1", transitionType=transition,
                  requiresNewKeyframe=(transition == "PLANNED_CUT"), **f)


def test_canon_envelope_loads_versions_and_hashes(tmp_path):
    env = C.load_canon_envelope("Ep1", log=lambda *a, **k: None)
    assert env["sources"]["script"]["md5"] and env["sources"]["characters"]["md5"]
    assert "canonVersion" in env and isinstance(env["gaps"], list)


def test_locked_dialogue_extraction_is_verbatim():
    beats, _ = C._script_beats("Ep1", 1)
    lines = C._locked_dialogue(beats)
    assert any("Nailed it." == t for _, t in lines)
    assert all(t == t.strip() for _, t in lines)


def test_beat_requires_exactly_three_interpretations():
    with pytest.raises(Exception):
        C.Beat(**{**_beat_stub().model_dump(),
                  "interpretations": [C.Interpretation(name="only", dramaticConstruction="x",
                                                        characterBehaviour="x",
                                                        audienceExperience="x").model_dump()]})
    b = _beat_stub()
    assert b.rejectedApproachSummaries == ["B", "C"]


def test_voice_pass_refuses_dropped_or_reworded_lines(monkeypatch):
    vp = C.VoicePerformance(speaker="FUZZBY", exactDialogue="Totally nailed it.",
                             dramaticIntention="x", subtext="x", relationshipTarget="Zenny",
                             emotionalEntry="x", emotionalExit="x", operativeWords=["nailed"],
                             pace="x", rhythm="x", pauses="x", breaths="x",
                             nonVerbalActions="x", elevenLabsV3Direction="x",
                             physicalActionRelationship="x", expectedTiming="x")
    monkeypatch.setattr(cb_llm, "structured",
                        lambda *a, **k: C.VoiceScript(performances=[vp]))
    sd = C.SceneDirection(scene=_scene_stub(), beats=[_beat_stub()])
    with pytest.raises(RuntimeError, match="DROPPED/REWORDED"):
        C.voice_design("Ep1", 1, sd, [_shot_stub()], log=lambda *a, **k: None)


def _scene_stub():
    f = {k: "x" for k in ("sourceScriptRange", "location", "time", "purpose",
         "dramaticQuestion", "emotionalOwner", "characterObjectives", "opposition",
         "subtext", "emotionalEntry", "emotionalExit", "storyTurn", "visualIdentity",
         "lightingAtmosphere", "energyShape", "connectionFromPreviousScene",
         "handoverToNextScene")}
    return C.Scene(sceneId="S1", participatingCharacters=["Fuzzby"], **f)


def test_cinematographer_cannot_rewrite_director_performance(monkeypatch):
    director_shot = _shot_stub()
    director_shot.principalPerformance = "Fuzzby overshoots and sinks, still singing."
    rewritten = _shot_stub()
    rewritten.principalPerformance = "Fuzzby does something else entirely."
    monkeypatch.setattr(cb_llm, "structured", lambda *a, **k: C.ShotList(shots=[rewritten]))
    out = C.cinematic_design("Ep1", 1, C.SceneDirection(scene=_scene_stub(),
                                                         beats=[_beat_stub()]),
                              [director_shot], log=lambda *a, **k: None)
    assert out[0].principalPerformance == director_shot.principalPerformance


def test_transition_contract_planned_cut_vs_continuous():
    assert _shot_stub(transition="PLANNED_CUT").requiresNewKeyframe
    s = _shot_stub("1.B1.S2", transition="CONTINUOUS")
    assert not s.requiresNewKeyframe
    with pytest.raises(Exception):
        _shot_stub(transition="JUMP")           # only the two named transitions exist


def test_review_loop_caps_at_two_revisions_then_escalates(monkeypatch):
    calls = {"review": 0, "cine": 0}

    def fake_structured(system, user, schema, label="", **k):
        if schema is C.EpisodeVision:
            return C.EpisodeVision(**{k: "x" for k in C.EpisodeVision.model_fields})
        if schema is C.SceneDirection:
            return C.SceneDirection(scene=_scene_stub(), beats=[_beat_stub()])
        if schema is C.ShotList:
            calls["cine"] += 1
            return C.ShotList(shots=[_shot_stub()])
        if schema is C.VoiceScript:
            return C.VoiceScript(performances=[])
        if schema is C.ShowrunnerReview:
            calls["review"] += 1
            return C.ShowrunnerReview(judgement="still weak", passes=False,
                                       issues=[C.ReviewIssue(role="cinematographer",
                                                              target="1.B1.S1",
                                                              issue="camera adds no meaning")])
        raise AssertionError(schema)
    monkeypatch.setattr(cb_llm, "structured", fake_structured)
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {})
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])   # scene fixture is silent
    monkeypatch.setattr(C, "OUT", __import__("pathlib").Path(
        __import__("tempfile").mkdtemp()))                         # never the real cb-output
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert calls["review"] == C.MAX_INTERNAL_REVISIONS + 1      # never endless rewriting
    assert pkg["escalation"] and "presented to the user" in pkg["escalation"]
    assert len(pkg["internalRevisions"]) == C.MAX_INTERNAL_REVISIONS
    assert pkg["approvalState"] == "awaiting-human-storyboard-approval"


def test_provenance_and_no_provider_fields_in_storyboard(monkeypatch):
    def fake_structured(system, user, schema, label="", **k):
        return {C.EpisodeVision: C.EpisodeVision(**{k: "x" for k in C.EpisodeVision.model_fields}),
                C.SceneDirection: C.SceneDirection(scene=_scene_stub(), beats=[_beat_stub()]),
                C.ShotList: C.ShotList(shots=[_shot_stub()]),
                C.VoiceScript: C.VoiceScript(performances=[]),
                C.ShowrunnerReview: C.ShowrunnerReview(judgement="sings", passes=True)}[schema]
    monkeypatch.setattr(cb_llm, "structured", fake_structured)
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {})
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])   # scene fixture is silent
    monkeypatch.setattr(C, "OUT", __import__("pathlib").Path(
        __import__("tempfile").mkdtemp()))                         # never the real cb-output
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert all(r in pkg["provenance"] for r in ("showrunner", "director",
                                                  "cinematographer", "voice"))
    dump = json.dumps(pkg)
    for banned in ("seedancePrompt", "Negative:", "Pixar-caliber", "0–5s",
                    "squash-and-stretch"):
        assert banned not in dump          # planning never leaks toward the provider
    assert len(pkg["shots"][0]["essentialProviderProtections"]) <= 3


def test_creative_room_makes_no_provider_calls(monkeypatch):
    import cb_gen
    src = (HERE / "cb_creative.py").read_text()
    assert "import cb_gen" not in src and "import cb_render" not in src   # no provider path
    assert "generate_video" not in src and "_fal_" not in src


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
