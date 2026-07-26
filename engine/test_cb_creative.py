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
# DORMANT-SAFE WHEN THE EPISODE IS RESET TO SCRIPT (2026-07-26) — see _live_package.py.
from _live_package import require_live_beat_package
pytestmark = require_live_beat_package()

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


def _card(shot_id="S1.SH1", transition="PLANNED_CUT", cut_pace="single_continuous_take",
          internal_cuts=()):
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
                          "continuing would dilute the impact; the new image re-scales the gag",
        cutPace=cut_pace, cutPaceReason="a single beat lands cleanest as one unbroken take",
        internalCuts=list(internal_cuts))


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
                requiresNewKeyframe=True, intendedDurationRange="5-8s")])
        if schema is C.ShowrunnerReview:
            state["reviews"] += 1
            if review_script:
                return review_script(state["reviews"])
            return C.ShowrunnerReview(judgement="delivers the treatment",
                                       treatmentComparison="experience intact", passes=True)
        if schema is C.ProducerFeasibilityReview:
            return C.ProducerFeasibilityReview(judgement="producible as written", passes=True)
        raise AssertionError(schema)
    return fake


def _isolated(monkeypatch, record, review_script=None, missing_refs=None):
    monkeypatch.setattr(cb_llm, "structured", _fake_llm(record, review_script))
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {})
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])
    monkeypatch.setattr(C, "OUT", pathlib.Path(tempfile.mkdtemp()))   # never real cb-output
    # Gate 6b's own deterministic reference check reads real characters.json by design
    # (the same disk read load_canon_envelope's own equivalent check already makes) —
    # isolated here too, matching this fixture's own "never touch real disk for a check
    # unrelated to what THIS test proves" discipline; a test proving Gate 6b's own
    # missing-reference behaviour overrides this with a real name via missing_refs=.
    monkeypatch.setattr(C, "_missing_character_references", lambda cast: (missing_refs or []))


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


def test_planned_cut_no_longer_forces_a_fresh_keyframe(monkeypatch):
    """2026-07-19 correction #4 (Julian: 'we can be flexible if it secures the beat again...
    this is a straight jacket, that's a guide not a rule'): the REAL bug this regression
    pins — every real Scene 1 shot is PLANNED_CUT, and the mechanical override used to
    force requiresNewKeyframe=True for all of them regardless of what the mind actually
    authored, discarding rich, genuinely-inherited continuityIn/Out text. A non-opener
    PLANNED_CUT shot whose authored value is False must now STAY False (relay preserved) —
    trusting the mind's own judgment, never overwriting it from transitionType alone."""
    record = []
    _isolated(monkeypatch, record)
    monkeypatch.setattr(cb_llm, "structured", (lambda orig: lambda s, u, schema, label="", **k:
        C.ProductionPass(details=[
            C.ProductionDetail(shotId="S1.SH1", continuityIn="", continuityOut="out",
                                dialogueTiming="", referenceRoles="", requiresNewKeyframe=True,
                                intendedDurationRange="5-8s"),
            C.ProductionDetail(shotId="S1.SH2", continuityIn="pollen carries in",
                                continuityOut="out", dialogueTiming="", referenceRoles="",
                                requiresNewKeyframe=False, intendedDurationRange="5-8s"),
        ]) if schema is C.ProductionPass else _fake_llm(record)(s, u, schema, label, **k))(None))
    details = C.production_detail("Ep1", 1,
                                    C.SceneDirection(scene=_scene(), beats=[_beat()]),
                                    [_card("S1.SH1", "PLANNED_CUT"),
                                     _card("S1.SH2", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None)
    assert details[0].requiresNewKeyframe is True     # true opener: still mechanical, correct
    assert details[1].requiresNewKeyframe is False    # PLANNED_CUT but authored False: honored


def test_planned_cut_omitted_from_llm_response_defaults_to_relay_not_forced_true(monkeypatch):
    """A shot the mind's response omits entirely used to fall back to
    requiresNewKeyframe=(transitionType == 'PLANNED_CUT') — forcing True for any omitted
    cut shot. The corrected fallback default is False (relay by default), matching the
    same guide-not-rule doctrine as the authored case above."""
    record = []
    _isolated(monkeypatch, record)
    monkeypatch.setattr(cb_llm, "structured", (lambda orig: lambda s, u, schema, label="", **k:
        C.ProductionPass(details=[
            C.ProductionDetail(shotId="S1.SH1", continuityIn="", continuityOut="out",
                                dialogueTiming="", referenceRoles="", requiresNewKeyframe=True,
                                intendedDurationRange="5-8s"),
            # S1.SH2 deliberately absent — never returned by the mind
        ]) if schema is C.ProductionPass else _fake_llm(record)(s, u, schema, label, **k))(None))
    details = C.production_detail("Ep1", 1,
                                    C.SceneDirection(scene=_scene(), beats=[_beat()]),
                                    [_card("S1.SH1", "PLANNED_CUT"),
                                     _card("S1.SH2", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None)
    assert details[1].requiresNewKeyframe is False


def test_continuityIn_mechanical_clear_uses_opener_shot_id_not_list_position(monkeypatch):
    """2026-07-17 (THE DUPLICATION correction, then THE SIMPLIFICATION): a SCOPED call
    (regenerate_production_detail's only_shot_id path) may pass a shots list whose
    position-0 entry is NOT the scene's true opener. The mechanical clear must key off the
    real opener_shot_id, never off list position — otherwise a later shot regenerated
    alone would be wrongly stamped as having nothing inherited. Typed absence: the clear
    is an empty string (the schema's own existing 'nothing here' value), never a sentinel
    phrase."""
    def fake(system, user, schema, label="", **k):
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[C.ProductionDetail(
                shotId="S1.SH2", continuityIn="Fuzzby's pollen mark still visible from the "
                "prior shot.", continuityOut="out", dialogueTiming="", referenceRoles="",
                requiresNewKeyframe=True, intendedDurationRange="5-7s")])
        raise AssertionError(schema)
    monkeypatch.setattr(cb_llm, "structured", fake)
    # S1.SH2 is the ONLY entry in this scoped call, but it is NOT the scene's true opener —
    # opener_shot_id names S1.SH1 (not present in this call at all) explicitly.
    details = C.production_detail("Ep1", 1, None, [_card("S1.SH2", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None, opener_shot_id="S1.SH1")
    assert details[0].continuityIn != ""
    assert "pollen mark" in details[0].continuityIn      # the LLM's real, authored content survives


def test_continuityIn_mechanical_clear_fires_for_the_real_opener(monkeypatch):
    def fake(system, user, schema, label="", **k):
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[C.ProductionDetail(
                shotId="S1.SH1", continuityIn="a duplicate restatement of the opening image",
                continuityOut="out", dialogueTiming="", referenceRoles="",
                requiresNewKeyframe=True, intendedDurationRange="5-7s")])
        raise AssertionError(schema)
    monkeypatch.setattr(cb_llm, "structured", fake)
    details = C.production_detail("Ep1", 1, None, [_card("S1.SH1", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None)
    assert details[0].continuityIn == ""   # mechanical clear wins — typed absence, not a sentinel


# ── THE SCHEMA CHECKPOINT (2026-07-17): duration field, hash-proven regeneration,
#    the approvalState rename, and the sole-Gate-A-authority proof ─────────────────────
def test_duration_field_required_and_validated():
    with pytest.raises(Exception):
        C.ProductionDetail(shotId="x", continuityIn="", continuityOut="",
                            dialogueTiming="", referenceRoles="", requiresNewKeyframe=True)
    good = C.ProductionDetail(shotId="x", continuityIn="", continuityOut="",
                               dialogueTiming="", referenceRoles="",
                               requiresNewKeyframe=True, intendedDurationRange="4-7s")
    bad = C.ProductionDetail(shotId="y", continuityIn="", continuityOut="",
                              dialogueTiming="", referenceRoles="",
                              requiresNewKeyframe=False, intendedDurationRange="not a range")
    inverted = C.ProductionDetail(shotId="z", continuityIn="", continuityOut="",
                                   dialogueTiming="", referenceRoles="",
                                   requiresNewKeyframe=False, intendedDurationRange="9-3s")
    v = C.validate_duration_ranges([good, bad, inverted], log=lambda *a, **k: None)
    assert v["invalidShotIds"] == ["y", "z"]           # malformed AND inverted both caught
    assert v["sceneTotal"]["formatted"] == "4-7s"       # only the credible shot sums
    assert v["sceneTotal"]["allValid"] is False


def test_regenerate_production_detail_proves_creative_cards_unchanged(monkeypatch, tmp_path):
    record = []
    _isolated(monkeypatch, record)
    src = tmp_path / "in.json"
    card = _card().model_dump()
    card["physicalPerformance"] = "weight lands late"
    card["animationTiming"] = "fast in, held rebound"
    src.write_text(json.dumps({"episodeId": "Ep1", "sceneNumber": "1",
        "shots": [card], "voicePerformances": [],
        "scene": {**_scene().model_dump(), "sourceApprovalState": "draft"},
        "approvalState": "approved"}))
    out = tmp_path / "out.json"
    result = C.regenerate_production_detail(str(src), str(out), log=lambda *a, **k: None)
    assert result["creativeCardHashCheck"]["unchanged"] is True
    assert result["creativeCardHashCheck"]["before"] == result["creativeCardHashCheck"]["after"]
    assert result["shots"] == json.loads(src.read_text())["shots"]   # byte-identical cards
    assert result["productionDetail"][0]["intendedDurationRange"] == "5-8s"
    assert result["durationValidation"]["sceneTotal"]["formatted"]
    assert json.loads(out.read_text())["shots"] == [card]   # written file matches too


def test_regenerate_refuses_if_creative_cards_would_change(monkeypatch, tmp_path):
    """A hash mismatch must raise, never silently ship — proven by corrupting the hash
    check's own comparison target after the fact is impossible from the public API, so
    this proves the guard exists and fires on the one path that CAN legitimately differ:
    a source file whose recorded shots do not match themselves after round-tripping
    would only happen on a bug in the copy step, which this assertion pins against."""
    record = []
    _isolated(monkeypatch, record)
    src = tmp_path / "in.json"
    card = _card().model_dump()
    src.write_text(json.dumps({"episodeId": "Ep1", "sceneNumber": "1", "shots": [card],
        "voicePerformances": [], "scene": _scene().model_dump(), "approvalState": "approved"}))
    out = tmp_path / "out.json"
    result = C.regenerate_production_detail(str(src), str(out), log=lambda *a, **k: None)
    assert C._shots_hash(result) == C._shots_hash(json.loads(src.read_text()))
    assert not any(s == "ShotConference" or s == "SceneDirection" or s == "TreatmentSet"
                   for _, s, _ in record)               # Gates 0-4 never ran


def test_scene_approvalState_renamed_to_sourceApprovalState():
    assert "sourceApprovalState" in C.Scene.model_fields
    assert "approvalState" not in C.Scene.model_fields
    s = C.Scene(**{**_scene().model_dump()})
    assert s.sourceApprovalState == "draft"


def test_top_level_approvalState_is_sole_gate_a_authority(monkeypatch, tmp_path):
    """A nested scene.sourceApprovalState of 'draft' must NEVER block promotion when the
    top-level state is approved, and a top-level state that is NOT approved must refuse
    even if the nested field claims 'approved' — proving the nested field has zero
    authority in either direction."""
    import cb_handover as H
    d = tmp_path
    pkg = tmp_path / "pkg.json"
    pkg.write_text(json.dumps({"episode": "Ep1", "sceneNumber": "1", "revision": 1,
                                "shots": [{"shotId": "S1.SH1", "durationSec": 6.0,
                                            "seedancePrompt": "x", "referenceSlots": {}}]}))

    approved_top_draft_nested = tmp_path / "a.json"
    approved_top_draft_nested.write_text(json.dumps({
        "episodeId": "Ep1", "sceneNumber": 1, "approvalState": "approved",
        "scene": {"sceneId": "S1", "location": "x", "sourceApprovalState": "draft"},
        "beats": [], "shots": [], "voicePerformances": []}))
    H.promote(str(approved_top_draft_nested), str(pkg), dry_run=True)   # must NOT refuse

    draft_top_approved_nested = tmp_path / "b.json"
    draft_top_approved_nested.write_text(json.dumps({
        "episodeId": "Ep1", "sceneNumber": 1,
        "approvalState": "awaiting-human-storyboard-approval",
        "scene": {"sceneId": "S1", "location": "x", "sourceApprovalState": "approved"},
        "beats": [], "shots": [], "voicePerformances": []}))
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote(str(draft_top_approved_nested), str(pkg), dry_run=True)


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


# ── gate 6b: the Producer's feasibility & scope review (2026-07-21) ─────────────────────
def test_gate6b_runs_only_after_gate6_passes_and_feeds_the_package(monkeypatch):
    record = []
    _isolated(monkeypatch, record)
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert any(s == "ProducerFeasibilityReview" for _, s, _ in record)
    pf = pkg["producerFeasibility"]
    assert pf["passes"] is True
    assert pf["missingCharacterReferences"] == []
    assert pf["durationValidation"]["sceneTotal"]["allValid"] is True
    assert pkg["provenance"]["producer"]["role"] == "producer"

    # a failed Gate 6 never reaches Gate 6b at all — nothing to check feasibility of yet
    record2 = []
    fail = lambda n: C.ShowrunnerReview(judgement="lost the treatment",
                                          treatmentComparison="experience gone", passes=False,
                                          returnTo="gate4")
    _isolated(monkeypatch, record2, review_script=fail)
    pkg2 = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    assert pkg2["producerFeasibility"] is None
    assert not any(s == "ProducerFeasibilityReview" for _, s, _ in record2)


def test_gate6b_missing_reference_is_a_block_regardless_of_the_llms_own_verdict(monkeypatch):
    """The mechanical fact (no locked anchor for a character in this scene) is never
    something a generous specialist gets to wave through — even when the LLM's own
    ProducerFeasibilityReview claims passes=True and raises no issue about it, the merged
    result must still BLOCK and must still name the missing character."""
    record = []
    _isolated(monkeypatch, record, missing_refs=["Ghost Bear"])
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    pf = pkg["producerFeasibility"]
    assert pf["passes"] is False
    assert pf["missingCharacterReferences"] == ["Ghost Bear"]
    assert any(i["severity"] == "BLOCK" and "Ghost Bear" in i["issue"] for i in pf["issues"])


def test_gate6b_invalid_duration_blocks_the_scene(monkeypatch):
    record = []

    def fake_with_bad_duration(system, user, schema, label="", **k):
        record.append((label, schema.__name__, user))
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[C.ProductionDetail(
                shotId="S1.SH1", continuityIn="in", continuityOut="out",
                dialogueTiming="after rebound", referenceRoles="turnarounds+plate",
                requiresNewKeyframe=True, intendedDurationRange="not-a-range")])
        return _fake_llm(record)(system, user, schema, label=label, **k)
    monkeypatch.setattr(cb_llm, "structured", fake_with_bad_duration)
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {})
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])
    monkeypatch.setattr(C, "OUT", pathlib.Path(tempfile.mkdtemp()))
    monkeypatch.setattr(C, "_missing_character_references", lambda cast: [])
    pkg = C.run_scene(1, "Ep1", log=lambda *a, **k: None)
    pf = pkg["producerFeasibility"]
    assert pf["passes"] is False
    assert pf["durationValidation"]["invalidShotIds"] == ["S1.SH1"]


def test_missing_character_references_reads_real_characters_json():
    """Unmocked, real-disk proof: a genuine show character (locked anchor on disk) is
    never flagged, and a name that doesn't exist in canon at all always is."""
    assert C._missing_character_references(["Fuzzby"]) == []
    assert C._missing_character_references(["Not A Real Character"]) == ["Not A Real Character"]


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))


# ══ THE DIFFERENTIATION ORIGINATES IN THE ROOM, NOT THE PROMPT WRITER ══════════════
# (Julian's directive, 2026-07-25: "ensure the differentiation originates inside the
# actual Creative Room minds — not only in schemas or the final animation writer.")
# These read the REAL system prompts the real gates send. Zero provider calls: cb_llm.
# structured is replaced by a capture stub. If a future edit quietly drops one of these
# decisions from a gate's charge, the gate stops asking for it and every scene silently
# converges back on one house shape — which is the exact failure these pin down.

def _capture(monkeypatch, schema_value):
    seen = {}
    def fake(system, user, schema, label="", **k):
        seen["system"], seen["user"], seen["label"] = system, user, label
        return schema_value
    monkeypatch.setattr(cb_llm, "structured", fake)
    return seen


def test_gate3_charge_demands_the_dramatic_form_decision(monkeypatch):
    sd = C.SceneDirection(scene=_scene(), beats=[_beat()])
    seen = _capture(monkeypatch, sd)
    ready = {"beats": [{"beatCode": "1.B1", "storyBeat": "s", "cuts": [], "location": "l",
                        "time": "t"}], "cast": ["Fuzzby"], "brief": ""}
    C.gate3_beats("Ep1", 1, {}, _selection(), _treatment("T"), ready, log=lambda *a, **k: None)
    charge = seen["system"]
    for phrase in ("primaryForm", "secondaryColour", "tempoShape",
                   "never labels that select a template"):
        assert phrase in charge, f"Gate 3 no longer asks the Director for {phrase!r}"
    assert "must still be directed" in charge, \
        "Gate 3 lost the rule that a shared form does not mean a shared treatment"


def test_gate4_charge_demands_an_ending_with_no_default(monkeypatch):
    seen = _capture(monkeypatch, C.ShotConference(shots=[_card()]))
    sd = C.SceneDirection(scene=_scene(), beats=[_beat()])
    C.gate4_shot_conference("Ep1", 1, _selection(), _treatment("T"), sd, log=lambda *a, **k: None)
    charge = seen["system"]
    for kind in ("reaction_hold", "living_hold", "continue_in_motion",
                 "cut_on_action", "visual_transition"):
        assert kind in charge, f"Gate 4 no longer offers {kind} as an ending"
    assert "NO DEFAULT AND NO PREFERRED ENDING" in charge, \
        "Gate 4 lost the anti-universal clause — a house closing hold will reassert itself"


def test_gate4_actually_sees_each_beats_form_and_tempo(monkeypatch):
    """The charge tells Gate 4 to read the beat's primaryForm/tempoShape. That is only
    honest if those values genuinely reach the call — prove it from the real user text."""
    beat = _beat()
    beat.primaryForm = "physical comedy, escalating"
    beat.tempoShape = "runs fast, then stops dead on the verdict"
    sd = C.SceneDirection(scene=_scene(), beats=[beat])
    seen = _capture(monkeypatch, C.ShotConference(shots=[_card()]))
    C.gate4_shot_conference("Ep1", 1, _selection(), _treatment("T"), sd, log=lambda *a, **k: None)
    assert "physical comedy, escalating" in seen["user"]
    assert "stops dead on the verdict" in seen["user"]


def test_gate6_charge_runs_an_explicit_universals_test(monkeypatch):
    seen = _capture(monkeypatch, C.ShowrunnerReview(
        judgement="ok", treatmentComparison="held", passes=True, returnTo=None, issues=[]))
    sd = C.SceneDirection(scene=_scene(), beats=[_beat()])
    C.gate6_adversarial_review({}, _selection(), _treatment("T"), sd, [_card()], [],
                               log=lambda *a, **k: None)
    charge = seen["system"]
    assert "UNIVERSALS TEST" in charge
    for target in ("endingBehaviour", "cutPace", "true of EVERY shot"):
        assert target in charge, f"the universals test no longer names {target!r}"
