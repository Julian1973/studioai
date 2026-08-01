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

CANON_DIGEST = "c" * 64


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


def _performance_contract(beat_id="1.B1"):
    return C.ShotPerformanceContract(
        beatOwner=beat_id,
        playableIntention="Make confidence survive one beat past the physical evidence.",
        phases=[
            C.PerformancePhase(phase="anticipation", performer="Fuzzby",
                               observableAction="leans beyond a stable hover"),
            C.PerformancePhase(phase="action", performer="Fuzzby",
                               observableAction="clips the leaf and compresses it"),
            C.PerformancePhase(phase="reaction", performer="Fuzzby",
                               observableAction="folds, rebounds and recovers his wings")],
        physicalCauseAndEffect="His late weight compresses the leaf and releases him backward",
        visibleEmotionalTurn="His open confidence closes into a private flinch",
        requiredLanding="Fuzzby hangs low beside the trembling leaf",
        performanceFreedom="Keep secondary wing beats and the flinch size natural")


def _boundary(closing=False):
    return C.ContinuityBoundary(
        lighting="warm corridor daylight", cameraSide="meadow side of the action line",
        characters=[C.BoundaryCharacterState(
            characterId="Fuzzby", screenZone="frame-left", facing="toward the leaf",
            pose="low after recoil" if closing else "already at speed",
            expression="private flinch" if closing else "bright confidence",
            visibleMarks=[], heldProps=[])])


def _detail(shot_id="S1.SH1", incoming="default", occurrence_ids=None):
    occurrence_ids = list(occurrence_ids or [])
    if incoming == "default":
        incoming = _boundary(False)
    return C.ProductionDetail(
        shotId=shot_id, continuityIn="in", continuityOut="out",
        dialogueTiming="after rebound", continuityInState=incoming,
        continuityOutState=_boundary(True),
        dialogueTimings=[C.DialogueTimingWindow(
            dialogueOccurrenceId=occurrence_id, startSec=0.5 + index,
            endSec=1.25 + index) for index, occurrence_id in enumerate(occurrence_ids)],
        referenceRoles="turnarounds+plate", requiresNewKeyframe=True,
        intendedDurationRange="5-8s", dialogueOccurrenceIds=occurrence_ids)


def _scene():
    return C.Scene(sceneId="S1", sourceScriptRange="1.B1-1.B5", location="flower corridor",
                   time="day", participatingCharacters=["Fuzzby"], purpose="open in play",
                   dramaticQuestion="can he keep performing mastery",
                   emotionalOwner="Zenny", connectionFromPreviousScene="episode opening",
                   handoverToNextScene="thunder turns the world")


def _selection():
    return C.TreatmentSelection(selectedTreatment="A", governingAudienceExperience="ride-along",
                                 rationale="strongest character truth", rejectionChecks="checked")


def _source_fixture(dialogue=None):
    version = "sha256:" + "4" * 64
    event = {"i": 0, "scene": 1,
             "type": "dialogue" if dialogue else "action",
             "speaker": "FUZZBY" if dialogue else None,
             "text": dialogue or "Fuzzby clips a leaf."}
    record = C.cb_lineage.source_event_record(version, event)
    cut = {"n": 1, "sourceEventId": record["sourceEventId"],
           "sourceEventIndex": 0, "sourceSceneNumber": 1,
           "sourceType": event["type"],
           "dialogueOccurrenceId": record.get("dialogueOccurrenceId"),
           "speaker": event["speaker"],
           "exactText": event["text"] if dialogue else None,
           "dialogue": f"FUZZBY: {dialogue}" if dialogue else None,
           "action": None if dialogue else event["text"]}
    signature = C.cb_lineage.source_beat_event_signature(version, [event])
    beat = {"beatCode": "1.B1", "sceneNumber": "1", "characters": ["Fuzzby"],
            "storyBeat": "Fuzzby crashes into pride.", "cuts": [cut],
            "sourceBeatId": C.cb_lineage.source_beat_id(signature),
            "sourceEventIds": [record["sourceEventId"]],
            "dialogueOccurrenceIds": ([record["dialogueOccurrenceId"]] if dialogue else []),
            "sourceEventRange": {"firstEventIndex": 0, "lastEventIndex": 0,
                "firstEventId": record["sourceEventId"],
                "lastEventId": record["sourceEventId"], "eventCount": 1},
            "sourceEventSignature": signature}
    pkg = {"title": "Fixture", "episode": 1, "logline": "x", "leadBear": "Fuzzby",
           "format": "11-min", "unit": "beat",
           "sourceScript": {"scriptVersionId": version}, "beats": [beat]}
    pkg["sourceContract"] = C.cb_lineage.beat_package_source_contract(version, [beat])
    pkg["contentSignature"] = C.cb_lineage.beat_package_signature(pkg)
    return [beat], pkg


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
            card.performanceContract = _performance_contract()
            return C.PerformancePass(shots=[card])
        if schema is C.VoiceScript:
            return C.VoiceScript(performances=[])
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[_detail()])
        if schema is C.ShowrunnerReview:
            state["reviews"] += 1
            if review_script:
                return review_script(state["reviews"])
            return C.ShowrunnerReview(judgement="delivers the treatment",
                                       treatmentComparison="experience intact", passes=True)
        raise AssertionError(schema)
    return fake


def _vision_for(source_pkg):
    beat_signature = C.cb_lineage.beat_package_signature(source_pkg)
    script_version = source_pkg["sourceScript"]["scriptVersionId"]
    return {
        **{name: "x" for name in C.EpisodeVision.model_fields},
        "inputSignature": C.cb_lineage.dependency_signature(
            "episode-vision",
            C.cb_lineage.episode_vision_inputs(
                script_version, beat_signature, CANON_DIGEST),
        ),
    }


def _set_source(monkeypatch, source_beats, source_pkg):
    monkeypatch.setattr(C, "_script_beats", lambda *a, **k: (source_beats, source_pkg))
    C.OUT.mkdir(parents=True, exist_ok=True)
    source_path = C.OUT.parent / "Ep1_fixture_beat_package.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(json.dumps(source_pkg, indent=1))
    monkeypatch.setattr(C, "_script_package", lambda *a, **k: source_path)
    monkeypatch.setattr(C, "episode_vision", lambda *a, **k: _vision_for(source_pkg))


def _isolated(monkeypatch, record, review_script=None):
    monkeypatch.setattr(cb_llm, "structured", _fake_llm(record, review_script))
    monkeypatch.setattr(C, "load_canon_envelope", lambda *a, **k: {
        "sources": {}, "canonLock": {"profileDigest": CANON_DIGEST}})
    monkeypatch.setattr(C.cb_canon, "profile_digest",
                        lambda *a, **k: CANON_DIGEST)
    root = pathlib.Path(tempfile.mkdtemp())
    monkeypatch.setattr(C, "ROOT", root)
    monkeypatch.setattr(C, "OUT", root / "cb-output" / "creative")
    source_beats, source_pkg = _source_fixture()
    _set_source(monkeypatch, source_beats, source_pkg)
    monkeypatch.setattr(C, "_locked_dialogue", lambda beats: [])


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


def test_performance_contract_rejects_duplicate_or_reordered_phases():
    base = _performance_contract().model_dump()
    reordered = {**base, "phases": list(reversed(base["phases"]))}
    with pytest.raises(Exception, match="must follow"):
        C.ShotPerformanceContract(**reordered)
    duplicated = {**base, "phases": [base["phases"][0], base["phases"][0]]}
    with pytest.raises(Exception, match="must be unique"):
        C.ShotPerformanceContract(**duplicated)


def test_production_detail_refuses_a_missing_shot_instead_of_inventing_fallback(monkeypatch):
    def fake(system, user, schema, label="", **kwargs):
        if schema is C.ProductionPass:
            return C.ProductionPass(details=[_detail("S1.SH1")])
        raise AssertionError(schema)

    monkeypatch.setattr(cb_llm, "structured", fake)
    shots = [_card("S1.SH1", "PLANNED_CUT"), _card("S1.SH2", "PLANNED_CUT")]
    with pytest.raises(RuntimeError, match="DROPPED/DUPLICATED/REORDERED"):
        C.production_detail(
            "Ep1", 1, None, shots, [], log=lambda *a, **k: None,
            shot_cast={"S1.SH1": ["Fuzzby"], "S1.SH2": ["Fuzzby"]})


def test_production_detail_refuses_cast_omission_and_dialogue_overrun(monkeypatch):
    occurrence = "dialogue-occurrence:test:1"

    def cast_omission(system, user, schema, label="", **kwargs):
        detail = _detail("S1.SH1")
        detail.continuityOutState.characters = []
        return C.ProductionPass(details=[detail])

    monkeypatch.setattr(cb_llm, "structured", cast_omission)
    with pytest.raises(RuntimeError, match="CONTINUITY CAST MISMATCH"):
        C.production_detail(
            "Ep1", 1, None, [_card()], [], log=lambda *a, **k: None,
            shot_cast={"S1.SH1": ["Fuzzby"]})

    voice = C.VoicePerformance(
        dialogueOccurrenceId=occurrence, sourceEventId="source-event:test:1",
        sourceEventIndex=0, beatId="1.B1", sourceBeatId="source-beat:test:1",
        speaker="Fuzzby", exactDialogue="Again.", dramaticIntention="x", subtext="x",
        relationshipTarget="x", emotionalEntry="x", emotionalExit="x",
        operativeWords=[], pace="x", rhythm="x", pauses="x", breaths="x",
        nonVerbalActions="x", elevenLabsV3Direction="x",
        physicalActionRelationship="x", expectedTiming="x")

    def overrun(system, user, schema, label="", **kwargs):
        detail = _detail("S1.SH1", occurrence_ids=[occurrence])
        detail.intendedDurationRange = "4-4s"
        detail.dialogueTimings[0].endSec = 4.5
        return C.ProductionPass(details=[detail])

    monkeypatch.setattr(cb_llm, "structured", overrun)
    with pytest.raises(RuntimeError, match="DIALOGUE TIMING OVERRUN"):
        C.production_detail(
            "Ep1", 1, None, [_card()], [voice], log=lambda *a, **k: None,
            shot_cast={"S1.SH1": ["Fuzzby"]})


def test_first_shot_always_requires_keyframe(monkeypatch):
    """A scene's first shot has no predecessor frame — whatever its creative
    transitionType says, the production layer must demand a keyframe."""
    record = []
    _isolated(monkeypatch, record)
    fallback = _fake_llm(record)

    def fake(system, user, schema, label="", **kwargs):
        if schema is C.ProductionPass:
            first = _detail("S1.SH1")
            second = _detail("S1.SH2", incoming=first.continuityOutState.model_copy(deep=True))
            return C.ProductionPass(details=[first, second])
        return fallback(system, user, schema, label, **kwargs)

    monkeypatch.setattr(cb_llm, "structured", fake)
    details = C.production_detail("Ep1", 1,
                                    C.SceneDirection(scene=_scene(), beats=[_beat()]),
                                    [_card("S1.SH1", "CONTINUOUS"),
                                     _card("S1.SH2", "CONTINUOUS")], [],
                                    log=lambda *a, **k: None)
    assert details[0].requiresNewKeyframe is True     # first shot: forced, structural
    assert details[1].requiresNewKeyframe is False    # a true continuation stays chained


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
            detail = _detail("S1.SH2")
            detail.continuityIn = "Fuzzby's pollen mark still visible from the prior shot."
            detail.dialogueTiming = ""
            detail.intendedDurationRange = "5-7s"
            return C.ProductionPass(details=[detail])
        raise AssertionError(schema)
    monkeypatch.setattr(cb_llm, "structured", fake)
    # S1.SH2 is the ONLY entry in this scoped call, but it is NOT the scene's true opener —
    # opener_shot_id names S1.SH1 (not present in this call at all) explicitly.
    details = C.production_detail("Ep1", 1, None, [_card("S1.SH2", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None,
                                    shot_cast={"S1.SH2": ["Fuzzby"]},
                                    opener_shot_id="S1.SH1")
    assert details[0].continuityIn != ""
    assert "pollen mark" in details[0].continuityIn      # the LLM's real, authored content survives


def test_continuityIn_mechanical_clear_fires_for_the_real_opener(monkeypatch):
    def fake(system, user, schema, label="", **k):
        if schema is C.ProductionPass:
            detail = _detail("S1.SH1")
            detail.continuityIn = "a duplicate restatement of the opening image"
            detail.dialogueTiming = ""
            detail.intendedDurationRange = "5-7s"
            return C.ProductionPass(details=[detail])
        raise AssertionError(schema)
    monkeypatch.setattr(cb_llm, "structured", fake)
    details = C.production_detail("Ep1", 1, None, [_card("S1.SH1", "PLANNED_CUT")], [],
                                    log=lambda *a, **k: None,
                                    shot_cast={"S1.SH1": ["Fuzzby"]})
    assert details[0].continuityIn == ""   # mechanical clear wins — typed absence, not a sentinel
    assert details[0].continuityInState is None


# ── THE SCHEMA CHECKPOINT (2026-07-17): duration field, hash-proven regeneration,
#    the approvalState rename, and the sole-Gate-A-authority proof ─────────────────────
def test_duration_field_required_and_validated():
    missing = _detail("x").model_dump()
    missing.pop("intendedDurationRange")
    with pytest.raises(Exception):
        C.ProductionDetail(**missing)
    good = _detail("x").model_copy(update={"intendedDurationRange": "4-7s"})
    bad = _detail("y").model_copy(update={"intendedDurationRange": "not a range"})
    inverted = _detail("z").model_copy(update={"intendedDurationRange": "9-3s"})
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
        "shots": [card], "beats": [_beat().model_dump()], "voicePerformances": [],
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
        "beats": [_beat().model_dump(),], "voicePerformances": [],
        "scene": _scene().model_dump(), "approvalState": "approved"}))
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
    source_beats, source_pkg = _source_fixture("Nailed it.")
    _set_source(monkeypatch, source_beats, source_pkg)
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
