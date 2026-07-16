#!/usr/bin/env python3
"""test_cb_creative.py — creative-room PROCESS v2 tests. Fully mocked LLM; these prove the
WORKFLOW and the DATA SEPARATION (Julian's 2026-07-17 process-correction directive) — they
never declare a storyboard creatively successful.

    pytest test_cb_creative.py -q
"""
import json
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_creative as C
import cb_llm


# ── fixtures ───────────────────────────────────────────────────────────────────────────
def _treatment(name):
    f = {k: f"{name}:{k}" for k in ("audienceExperience", "emotionalPointOfView",
         "comicOrDramaticMechanism", "characterPerformanceStrategy", "visualGrammar",
         "cameraCharacterRelationship", "movementVersusStillness", "depthAndEnvironment",
         "rhythmAndEscalation", "cutPhilosophy", "openingImage", "closingImage",
         "cinematographerChallenge")}
    return C.SceneTreatment(name=name, **f)


def _beat():
    return C.Beat(beatId="1.B1", sceneId="S1", sourceScript="Fuzzby crashes into pride.",
                  exactDialogue=["FUZZBY: Nailed it."], participatingCharacters=["Fuzzby"],
                  whatChanges="a crash becomes a claimed triumph", whoDrives="Fuzzby",
                  audienceAnticipation="we see the leaf before he does",
                  actionOrChoice="he overshoots", consequence="the leaf springs him back",
                  emotionalOrComicHandover="his verdict hangs for Zenny to puncture")


def _card(shot_id="S1.SH1", transition="PLANNED_CUT"):
    return C.CreativeShotCard(
        shotId=shot_id, beatIds=["1.B1"], purpose="discover the corridor at Fuzzby's speed",
        audienceExperience="we ride with him, not ahead of him",
        openingImage="blur of stems resolving as he swerves",
        principalPerformance="Fuzzby outruns his own steering",
        cameraRelationship="pursues and loses him, rediscovering him at the leaf",
        physicalOrEmotionalChange="confidence outruns control",
        closingImage="the leaf mid-rebound, Fuzzby gone past frame",
        transitionType=transition,
        transitionReason="a cut here would break the experiential chase" if
                          transition == "CONTINUOUS" else
                          "continuing would dilute the impact; the new image re-scales the gag")


def _scene():
    return C.Scene(sceneId="S1", sourceScriptRange="1.B1-1.B5", location="flower corridor",
                   time="day", participatingCharacters=["Fuzzby"], purpose="open in play",
                   dramaticQuestion="can he keep performing mastery",
                   emotionalOwner="Zenny", connectionFromPreviousScene="episode opening",
                   handoverToNextScene="thunder turns the world")


def _selection():
    return C.TreatmentSelection(selectedTreatment="A", governingAudienceExperience="ride-along",
                                 rationale="strongest character truth", rejectionChecks="checked")


def _fake_llm(record, review_script=None):
    """A schema-dispatching fake for cb_llm.structured that RECORDS call order."""
    state = {"reviews": 0}

    def fake(system, user, schema, label="", **k):
        record.append((label, schema.__name__, user))
        if schema is C.EpisodeVision:
            return C.EpisodeVision(**{k: "x" for k in C.EpisodeVision.model_fields})
        if schema is C.CanonCompletionProposal:
            return C.CanonCompletionProposal(completions=[C.CharacterCompletion(
                character="Fuzzby", proposals=[C.FieldProposal(
                    field="useOfStillness", proposedText="PROPOSED-ONLY-TEXT",
                    groundedIn="bible.motionRule")])])
        if schema is C.TreatmentSet:
            return C.TreatmentSet(treatments=[_treatment(n) for n in ("A", "B", "C")])
        if schema is C.TreatmentSelection:
            return _selection()
        if schema is C.SceneDirection:
            return C.SceneDirection(scene=_scene(), beats=[_beat()])
        if schema is C.ShotConference:
            return C.ShotConference(shots=[_card()])
        if schema is C.PerformancePass:
            card = _card()
            card.physicalPerformance = "weight lands late, wings recover first"
            card.animationTiming = "fast in, held rebound"
            return C.PerformancePass(shots=[card])
        if schema is C.VoiceScript:
            return C.VoiceScript(performances=[])
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[C.ProductionDetail(
                shotId="S1.SH1", continuityIn="in", continuityOut="out",
                dialogueTiming="after rebound", referenceRoles="turnarounds+plate",
                requiresNewKeyframe=True)])
        if schema is C.ShowrunnerReview:
            state["reviews"] += 1
            if review_script:
                return review_script(state["reviews"])
            return C.ShowrunnerReview(judgement="delivers the treatment",
                                       treatmentComparison="experience intact", passes=True)
        raise AssertionError(schema)
    return fake


def _isolated(monkeypatch, record, review_script=None):
    monkeypatch.setattr(cb_llm, "structured", _fake_llm(record, review_script))
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {})
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])
    monkeypatch.setattr(C, "OUT", pathlib.Path(tempfile.mkdtemp()))   # never real cb-output


# ── workflow order: treatments -> selection BEFORE any beat exists ─────────────────────
def test_treatment_selection_precedes_beat_architecture(monkeypatch):
    record = []
    _isolated(monkeypatch, record)
    C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    order = [schema for _, schema, _ in record]
    assert order.index("TreatmentSet") < order.index("TreatmentSelection") \
           < order.index("SceneDirection") < order.index("ShotConference")


def test_exactly_three_materially_distinct_treatments_required():
    with pytest.raises(Exception):
        C.TreatmentSet(treatments=[_treatment("only")])
    assert len(C.TreatmentSet(treatments=[_treatment(n) for n in "ABC"]).treatments) == 3


# ── the split contract: lean creative card, production detail separate ─────────────────
def test_creative_card_is_lean_and_production_detail_is_separate():
    creative_fields = set(C.CreativeShotCard.model_fields)
    for production_only in ("continuityIn", "continuityOut", "dialogueTiming",
                             "referenceRoles", "requiresNewKeyframe",
                             "essentialProviderProtections", "shotSize", "cameraHeight",
                             "cameraAngle", "lensFeeling", "depthAndParallax",
                             "lightingAndAtmosphere", "gazeAndExpression", "blocking",
                             "secondaryPerformance", "soundRelationship"):
        assert production_only not in creative_fields, production_only
    assert {"purpose", "audienceExperience", "openingImage", "principalPerformance",
            "cameraRelationship", "physicalOrEmotionalChange", "closingImage",
            "transitionType", "transitionReason"} <= creative_fields
    assert "essentialProviderProtections" in set(C.ProductionDetail.model_fields)


def test_every_transition_carries_its_justification():
    with pytest.raises(Exception):
        card = _card().model_dump()
        card.pop("transitionReason")
        C.CreativeShotCard(**card)


def test_first_shot_always_requires_keyframe(monkeypatch):
    """A scene's first shot has no predecessor frame — whatever its creative
    transitionType says, the production layer must demand a keyframe."""
    record = []
    _isolated(monkeypatch, record)
    monkeypatch.setattr(cb_llm, "structured", (lambda orig: lambda s, u, schema, label="", **k:
        C.ShotConference(shots=[_card("S1.SH1", "CONTINUOUS"), _card("S1.SH2", "CONTINUOUS")])
        if schema is C.ShotConference else _fake_llm(record)(s, u, schema, label, **k))(None))
    details = C.production_detail("Ep1", 1,
                                    C.SceneDirection(scene=_scene(), beats=[_beat()]),
                                    [_card("S1.SH1", "CONTINUOUS"),
                                     _card("S1.SH2", "CONTINUOUS")], [],
                                    log=lambda *a, **k: None)
    assert details[0].requiresNewKeyframe is True     # first shot: forced, structural
    assert details[1].requiresNewKeyframe is False    # a true continuation stays chained


def test_production_detail_added_only_after_pass(monkeypatch):
    record = []
    _isolated(monkeypatch, record)
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert pkg["productionDetail"] and pkg["escalation"] is None
    assert any(s == "ProductionPass" for _, s, _ in record)

    record2 = []
    fail = lambda n: C.ShowrunnerReview(judgement="lost the treatment",
                                          treatmentComparison="experience gone", passes=False,
                                          returnTo="gate4")
    _isolated(monkeypatch, record2, review_script=fail)
    pkg2 = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert pkg2["escalation"] and pkg2["productionDetail"] == []      # never on a failed scene
    assert not any(s == "ProductionPass" for _, s, _ in record2)


# ── gate 6: adversarial, treatment-compared, capped, escalates ──────────────────────────
def test_review_caps_at_two_complete_revisions_then_escalates(monkeypatch):
    record = []
    fail = lambda n: C.ShowrunnerReview(judgement="still safe coverage",
                                          treatmentComparison="drifted", passes=False,
                                          returnTo="gate3")
    _isolated(monkeypatch, record, review_script=fail)
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    reviews = [1 for _, s, _ in record if s == "ShowrunnerReview"]
    assert len(reviews) == C.MAX_INTERNAL_REVISIONS + 1
    assert len(pkg["internalRevisions"]) == C.MAX_INTERNAL_REVISIONS
    assert all(r["returnTo"] == "gate3" for r in pkg["internalRevisions"])
    # a gate3 return re-architects: SceneDirection called again, never a wording patch
    assert sum(1 for _, s, _ in record if s == "SceneDirection") == 3
    assert "escalated for human direction" in pkg["escalation"]
    assert pkg["approvalState"] == "awaiting-human-storyboard-approval"


# ── gate 0: canon proposal is visible, unapproved, and never fed into directing ────────
def test_canon_completion_is_proposed_never_used(monkeypatch):
    record = []
    _isolated(monkeypatch, record)
    monkeypatch.setattr(C, "_unresolved_fields_for",
                        lambda names: {"Fuzzby": ["useOfStillness"]})
    out = C.OUT
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    prop_files = list(out.glob("*canon_completion_PROPOSED.json"))
    assert prop_files, "proposal file must exist for human approval"
    doc = json.load(open(prop_files[0]))
    assert doc["approvalState"] == "proposed-awaiting-human-approval"
    assert pkg["directedOnEstablishedCanonOnly"] is True
    # the proposal text never reaches any directing prompt — psychology is never invisible
    for label, schema, user in record:
        if schema != "CanonCompletionProposal":
            assert "PROPOSED-ONLY-TEXT" not in user, (label, schema)


# ── dialogue: deterministic verbatim snap + voice lock (kept from v1) ───────────────────
def test_verbatim_dialogue_snap_and_voice_lock(monkeypatch):
    record = []
    _isolated(monkeypatch, record)
    monkeypatch.setattr(C, "_script_beats", lambda ep, sn=None: (
        [{"beatCode": "1.B1", "sceneNumber": "1", "characters": ["Fuzzby"],
          "storyBeat": "x", "cuts": [{"dialogue": 'FUZZBY: Nailed it.'}]}], {}))
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert pkg["beats"][0]["exactDialogue"] == ["FUZZBY: Nailed it."]   # snapped, verbatim

    vp = C.VoicePerformance(speaker="FUZZBY", exactDialogue="Totally nailed it.",
                             dramaticIntention="x", subtext="x", relationshipTarget="Zenny",
                             emotionalEntry="x", emotionalExit="x", operativeWords=["nailed"],
                             pace="x", rhythm="x", pauses="x", breaths="x",
                             nonVerbalActions="x", elevenLabsV3Direction="x",
                             physicalActionRelationship="x", expectedTiming="x")
    monkeypatch.setattr(cb_llm, "structured", lambda *a, **k: C.VoiceScript(performances=[vp]))
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [("FUZZBY", "Nailed it.")])
    with pytest.raises(RuntimeError, match="DROPPED/REWORDED"):
        C.gate5_voice("Ep1", 1, C.SceneDirection(scene=_scene(), beats=[_beat()]),
                       [_card()], log=lambda *a, **k: None)


# ── the rejected exemplar feeds the room; no provider access ────────────────────────────
def test_rejected_exemplar_reaches_role_minds_and_no_provider_access():
    mind = C._mind("DIRECTOR", ["directorTaste"], "charge")
    assert "EX-005" in mind and "REJECTED" in mind          # the process-v1 verdict is live
    assert "do not reverse-engineer a 'desired shot'" in mind
    src = (HERE / "cb_creative.py").read_text()
    assert "import cb_gen" not in src and "import cb_render" not in src
    assert "generate_video" not in src and "_fal_" not in src


def test_no_fixed_lane_or_mandatory_coverage_language_in_contract():
    """Data separation guard: the creative contract itself must not reintroduce lanes or
    coverage boxes."""
    for model in (C.CreativeShotCard, C.Beat, C.SceneTreatment):
        for f in model.model_fields:
            assert "screenSide" not in f and "lane" not in f.lower()


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
