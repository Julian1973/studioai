#!/usr/bin/env python3
"""test_cb_handover.py — the mocked, ZERO-SPEND storyboard->production handover proof
(Julian's directives, 2026-07-17/18). Fixtures match the CURRENT creative-room-2.0 schema
(CreativeShotCard + separate ProductionDetail) — the earlier fixture shape (fields
directly on the shot) was found stale by the single-shot-handover audit and corrected here
in lockstep with cb_handover.py itself.

    pytest test_cb_handover.py -q
"""
import hashlib
import json
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_handover as H
import cb_engine
import cb_lineage
from cb_scripts import ScriptStore
import paths as P  # T45: scratch worlds use the project layout

# distinctive markers that must NEVER cross into production (req 4)
JUDGEMENT_MARKER = "ZZ-SHOWRUNNER-ANALYSIS-MARKER-ZZ"
REJECTED_MARKER = "ZZ-REJECTED-INTERPRETATION-MARKER-ZZ"
CANON_MARKER = "ZZ-TASTE-CANON-MARKER-ZZ"
TEST_CANON_MANIFEST = "f" * 64
TEST_CANON_DIGESTS = {
    profile: hashlib.sha256(f"fixture-canon:{profile}".encode()).hexdigest()
    for profile in ("story", "storyboard", "look", "cinematography", "voice",
                    "animation", "review", "post")
}


def _sb_shot(shot_id, beat_ids, transition, protections=None):
    return {"shotId": shot_id, "beatIds": beat_ids, "purpose": "Land the leaf gag cleanly.",
            "audienceExperience": "We ride with him, not ahead of him.",
            "openingImage": "Fuzzby canted forward, blur of stems resolving as he swerves.",
            "principalPerformance": "Fuzzby overshoots the flower, grazes the leaf and the "
                                     "leaf springs him backward in a pollen burst.",
            "cameraRelationship": "The camera pursues and loses him, rediscovering him at "
                                    "the leaf.",
            "physicalOrEmotionalChange": "Confidence outruns control.",
            "closingImage": "The leaf mid-rebound, Fuzzby low in frame but airborne.",
            "transitionType": transition,
            "transitionReason": "A cut here would break the experiential chase." if
                                 transition == "CONTINUOUS" else
                                 "Continuing would dilute the impact; the new image "
                                 "re-scales the gag.",
            "cinematographyContract": {
                "storyPointOfView": "ride with Fuzzby's confidence",
                "shotScale": "medium-wide retains Fuzzby and the leaf",
                "lensIntent": "moderate perspective keeps speed readable",
                "cameraHeight": "at Fuzzby's eye line inside the stems",
                "composition": "open travel space closes at the leaf",
                "depthStrategy": "foreground stems wipe across a readable contact plane",
                "cameraBehavior": "pursue, briefly lose, then settle on the rebound",
                "focusStrategy": "hold Fuzzby and leaf together through contact",
                "lightingFunction": "warm side light reveals leaf compression",
                "paletteFunction": "green corridor separates Fuzzby's silhouette",
                "providerInstruction": (
                    "Eye-level medium-wide pursuit through foreground stems; hold Fuzzby "
                    "and the leaf sharp together, then settle on the rebound.")},
            "physicalPerformance": "Weight lands late, wings recover first, the whole body "
                                     "reads the overcommitment before he does.",
            "animationTiming": "Fast in, held rebound, a small settle before the next beat.",
            "performanceContract": {
                "beatOwner": beat_ids[0],
                "playableIntention": "Make control look convincing until physics answers.",
                "phases": [
                    {"phase": "anticipation", "performer": "Fuzzby",
                     "observableAction": "leans past his stable hover"},
                    {"phase": "action", "performer": "Fuzzby",
                     "observableAction": "clips the leaf and folds at the waist"},
                    {"phase": "reaction", "performer": "Fuzzby",
                     "observableAction": "rebounds with wings recovering before his body"}],
                "physicalCauseAndEffect": "His late weight compresses the leaf and releases him backward",
                "visibleEmotionalTurn": "His confident chest closes into a private flinch",
                "requiredLanding": "Fuzzby hangs low but airborne beside the trembling leaf",
                "performanceFreedom": "Keep secondary wing beats and the size of the flinch natural",
                "characterTruths": [{
                    "character": "Fuzzby",
                    "canonTrait": "buoyant confidence survives mishaps",
                    "playableWant": "make the arrival look intentional",
                    "pressureResponse": "recovers his social pose before his balance",
                    "observableSignature": "wings reset first and grin returns one beat late",
                    "substitutionTest": "Zenny would acknowledge the evidence"}],
                "comedyStaging": None},
            "approvalState": "draft"}


def _character_state(name, closing=False):
    if name == "Fuzzby":
        pose = "low but airborne after recoil" if closing else "already at speed"
        expression = "private flinch" if closing else "bright confidence"
    else:
        pose = "still on her petal"
        expression = "composed"
    return {"characterId": name,
            "screenZone": "frame-left" if name == "Fuzzby" else "frame-right",
            "facing": "toward the leaf" if name == "Fuzzby" else "toward Fuzzby",
            "pose": pose, "expression": expression,
            "visibleMarks": [], "heldProps": []}


def _boundary(closing=False):
    return {"lighting": "warm corridor daylight",
            "cameraSide": "meadow side of the action line",
            "characters": [_character_state("Fuzzby", closing),
                           _character_state("Zenny", closing)]}


def _pd(shot_id, requires_kf, duration="5-7s", protections=None, names_speaker=True,
        occurrence_ids=None, continuity_in_state="default", continuity_out_state="default"):
    occurrence_ids = list(occurrence_ids or [])
    if continuity_in_state == "default":
        continuity_in_state = _boundary(False)
    if continuity_out_state == "default":
        continuity_out_state = _boundary(True)
    return {"shotId": shot_id,
            "continuityIn": "Warm corridor light, Fuzzby already at speed, Zenny on her petal.",
            "continuityOut": "Leaf still trembling, pollen drifting, Fuzzby low but airborne.",
            "dialogueTiming": ("FUZZBY: chant runs under the whole shot, the line lands "
                                "after the rebound.") if names_speaker else
                               "The corridor holds its geography as the leaf settles.",
            "continuityInState": continuity_in_state,
            "continuityOutState": continuity_out_state,
            "dialogueTimings": [
                {"dialogueOccurrenceId": occurrence_id,
                 "startSec": 0.5 + index, "endSec": 1.25 + index}
                for index, occurrence_id in enumerate(occurrence_ids)],
            "referenceRoles": "Fuzzby identity anchors scale and rhythm; Zenny identity "
                               "anchors stillness; corridor/leaf anchor bee-height geography.",
            "requiresNewKeyframe": requires_kf, "intendedDurationRange": duration,
            "dialogueOccurrenceIds": occurrence_ids,
            "essentialProviderProtections": protections if protections is not None
                                             else ["Zenny stays on her petal"]}


def _beat(beat_id="1.B1", dialogue=None):
    lines = dialogue if dialogue is not None else ["FUZZBY: Nailed it."]
    source_beat_id = f"source-beat:test:{beat_id}"
    occurrences = []
    for index, display in enumerate(lines):
        speaker, exact_text = display.split(":", 1)
        occurrences.append({
            "dialogueOccurrenceId": f"dialogue-occurrence:test:{beat_id}:{index}",
            "sourceEventId": f"source-event:test:{beat_id}:{index}",
            "sourceEventIndex": index,
            "beatId": beat_id,
            "sourceBeatId": source_beat_id,
            "speaker": speaker.strip(), "exactText": exact_text.strip(),
        })
    source_event_ids = [item["sourceEventId"] for item in occurrences] or [
        f"source-event:test:{beat_id}:action"]
    return {"beatId": beat_id, "sceneId": "S1", "sourceScript": "x",
            "exactDialogue": lines,
            "sourceBeatId": source_beat_id, "sourceEventIds": source_event_ids,
            "sourceEventRange": {"firstEventIndex": 0,
                "lastEventIndex": len(source_event_ids) - 1,
                "firstEventId": source_event_ids[0], "lastEventId": source_event_ids[-1],
                "eventCount": len(source_event_ids)},
            "sourceEventSignature": {"kind": "fixture", "digest": source_beat_id},
            "dialogueOccurrences": occurrences,
            "participatingCharacters": ["Fuzzby", "Zenny"],
            "whatChanges": "x", "whoDrives": "Fuzzby", "audienceAnticipation": "x",
            "actionOrChoice": "x", "consequence": "x", "emotionalOrComicHandover": "x",
            "emotionContract": {
                "owner": "Fuzzby", "entryState": "buoyant certainty",
                "pressure": "the leaf exposes his late steering",
                "choiceOrRealisation": "he preserves the performance",
                "exitState": "confidence covering a private flinch",
                "observableEvidence": "his grin returns after the rebound",
                "audienceAlignment": "ahead",
                "heldAfterBeat": "the trembling leaf remains visible"},
            "comedyContract": {
                "mode": "SMALL", "mechanism": "confidence outlives evidence",
                "comicOwner": "Fuzzby", "straightCharacter": "Zenny",
                "setup": "he enters at speed", "expectation": "he owns the route",
                "disruption": "the leaf rebounds him", "button": "his pose resets",
                "hold": "the leaf trembles", "physicalStaging": None},
            "powerMoment": None,
            "approvalState": "redesigned_for_review"}


def _vp(speaker, text, occurrence=None):
    occurrence = occurrence or {
        "dialogueOccurrenceId": "dialogue-occurrence:test:standalone:0",
        "sourceEventId": "source-event:test:standalone:0", "sourceEventIndex": 0,
        "beatId": "1.B1", "sourceBeatId": "source-beat:test:1.B1"}
    return {"dialogueOccurrenceId": occurrence["dialogueOccurrenceId"],
            "sourceEventId": occurrence["sourceEventId"],
            "sourceEventIndex": occurrence.get("sourceEventIndex", 0),
            "beatId": occurrence.get("beatId", "1.B1"),
            "sourceBeatId": occurrence.get("sourceBeatId", "source-beat:test:1.B1"),
            "speaker": speaker, "exactDialogue": text, "voiceIdentity": "",
            "dramaticIntention": "Claim admiration before the crash is classified.",
            "subtext": "He needs Zenny to believe the recovery was deliberate.",
            "relationshipTarget": "Zenny", "emotionalEntry": "Bright confidence.",
            "emotionalExit": "Covered embarrassment.", "operativeWords": ["nailed"],
            "pace": "Quick and assured.", "rhythm": "A clean claim with a tiny catch.",
            "pauses": "No pause before the claim.", "breaths": "One small recovery breath.",
            "nonVerbalActions": "His chest lifts as his eyes check Zenny.",
            "elevenLabsV3Direction": "[proud, covering a wobble]",
            "physicalActionRelationship": "Enters only after the rebound settles.",
            "expectedTiming": "just after the rebound"}


def _refresh_dialogue_contract(storyboard):
    occurrences = [item for beat in storyboard.get("beats", [])
                   for item in beat.get("dialogueOccurrences", [])]
    inputs = {
        "orderedSourceBeatIds": [beat["sourceBeatId"] for beat in storyboard.get("beats", [])],
        "orderedDialogueOccurrenceIds": [item["dialogueOccurrenceId"] for item in occurrences],
        "voiceOccurrenceIds": [voice.get("dialogueOccurrenceId")
                               for voice in storyboard.get("voicePerformances", [])],
        "shotAssignments": {detail["shotId"]: list(detail.get("dialogueOccurrenceIds") or [])
                            for detail in storyboard.get("productionDetail", [])},
        "shotTimingWindows": {detail["shotId"]: list(detail.get("dialogueTimings") or [])
                              for detail in storyboard.get("productionDetail", [])},
    }
    storyboard["dialogueContract"] = {
        "schemaVersion": 2, **inputs,
        "inputSignature": cb_lineage.dependency_signature(
            "scene-dialogue-occurrences", inputs)}
    return storyboard


def _storyboard(state="approved"):
    beat = _beat("1.B1", ["FUZZBY: Nailed it."])
    occurrence = beat["dialogueOccurrences"][0]
    storyboard = {"episodeId": "Ep1", "sceneNumber": 1, "approvalState": state,
            "humanNote": "lovely — go",
            "scene": {"sceneId": "S1", "location": "Crystal Cove meadow",
                      "purpose": "turn confidence into connection", "emotionalOwner": "Fuzzby",
                      "handoverToNextScene": "the trembling leaf points toward the storm"},
            "vision": {"theme": CANON_MARKER,
                       "intendedFinalFeeling": "delight with a warm aftertaste"},
            "showrunnerJudgement": JUDGEMENT_MARKER,
            "internalRevisions": [{"note": JUDGEMENT_MARKER}],
            "escalation": None,
            "treatments": [{
                "name": "x", "cinematographerChallenge": REJECTED_MARKER,
                "emotionalPointOfView": "Fuzzby's confidence becomes briefly transparent",
                "comicOrDramaticMechanism": "confidence outlives physical evidence",
                "characterPerformanceStrategy": "body recovers before pride concedes",
                "visualGrammar": "pursuit compresses into a held two-character result",
                "cameraCharacterRelationship": "ride with, lose and rediscover Fuzzby",
                "movementVersusStillness": "Fuzzby moves; Zenny's stillness lands the truth",
                "depthAndEnvironment": "stems streak until the leaf becomes the contact plane",
                "rhythmAndEscalation": "fast approach, elastic impact, generous hold",
                "cutPhilosophy": "cut only when the audience needs a new relationship",
                "openingImage": "Fuzzby drives through a corridor of stems",
                "closingImage": "Fuzzby and the trembling leaf share the held frame"}],
            "treatmentSelection": {
                "selectedTreatment": "x",
                "governingAudienceExperience": "ride with Fuzzby, then catch his bluff",
                "rejectionChecks": REJECTED_MARKER},
            "beats": [beat],
            "shots": [_sb_shot("S1.SH1", ["1.B1"], "PLANNED_CUT"),
                       _sb_shot("S1.SH2", ["1.B1"], "CONTINUOUS")],
            # S1.SH1 is the scene's true first shot — THE SIMPLIFICATION (2026-07-17):
            # nothing genuinely inherits into it, so continuityIn is the schema's own
            # existing empty-string value (typed absence), matching cb_creative.
            # production_detail's real mechanical clear, never real prose here.
            "productionDetail": [{**_pd("S1.SH1", True,
                                           occurrence_ids=[occurrence["dialogueOccurrenceId"]]),
                                    "continuityIn": "", "continuityInState": None},
                                  _pd("S1.SH2", False, names_speaker=False)],
            "voicePerformances": [_vp("FUZZBY", "Nailed it.", occurrence)]}
    return _refresh_dialogue_contract(storyboard)


def _old_pkg():
    return {"episode": "Ep1", "sceneNumber": "1", "sceneName": "Crystal Cove meadow",
            "revision": 6,
            "shots": [{"shotId": "1.B1.S1", "durationSec": 6.0,
                        "seedancePrompt": "OLD REVISION SIX PROMPT",
                        "performanceAssignment": "OLD-CREATIVE-SOURCE-MARKER",
                        "referenceSlots": {"@图1": "opening keyframe"}}],
            "voidedTokens": ["db660b33"]}


def _tmp(sb_state="approved"):
    d = pathlib.Path(tempfile.mkdtemp())
    sb_p, pkg_p = d / "sb.json", d / "pkg.json"
    json.dump(_storyboard(sb_state), open(sb_p, "w"))
    json.dump(_old_pkg(), open(pkg_p, "w"))
    return sb_p, pkg_p


def _md5(p):
    return hashlib.md5(pathlib.Path(p).read_bytes()).hexdigest()


# ── req 1 + 6: approval is the only door; refusal never writes ─────────────────────────
def test_unapproved_storyboard_cannot_alter_production():
    sb_p, pkg_p = _tmp("awaiting-human-storyboard-approval")
    before = _md5(pkg_p)
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert _md5(pkg_p) == before                      # byte-identical — untouched


def test_real_awaiting_storyboard_refused_against_package_copy():
    live = HERE.parent / P.OUTPUT_REL / "creative" / "Ep1_scene1_storyboard.json"
    archived = (HERE.parent / P.OUTPUT_REL / "creative" / "archive_process_v1"
                / "Ep1_scene1_storyboard.json")
    real_sb = live if live.exists() else archived
    if not real_sb.exists():
        pytest.skip("no live or archived Ep1 storyboard is present in this checkout")
    sb = json.load(open(real_sb))
    if sb.get("approvalState") == "approved":
        pytest.skip("real storyboard is approved this run — covered by other refusal tests")
    _, pkg_p = _tmp()
    before = _md5(pkg_p)
    with pytest.raises(H.HandoverRefused):
        H.promote(real_sb, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert _md5(pkg_p) == before


# ── req 2: the approved storyboard is the SOLE creative source ────────────────────────
def test_storyboard_is_sole_creative_source():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    sb = _storyboard()
    s1 = pkg["shots"][0]
    assert s1["performanceAssignment"] == cb_engine.compile_performance_contract(
        sb["shots"][0]["performanceContract"])
    assert s1["principalPerformanceApproved"] == sb["shots"][0]["principalPerformance"]  # retained, not dropped
    assert s1["physicalPerformanceApproved"] == sb["shots"][0]["physicalPerformance"]
    assert s1["camera"] == sb["shots"][0]["cinematographyContract"]["providerInstruction"]
    assert s1["openingPose"] == sb["shots"][0]["openingImage"]
    assert s1["visualPayoff"] == sb["shots"][0]["closingImage"]
    assert s1["continuityProseIn"] == sb["productionDetail"][0]["continuityIn"]    # retained
    assert s1["characterTruthsApproved"] == (
        sb["shots"][0]["performanceContract"]["characterTruths"])
    assert s1["cinematographyContractApproved"] == (
        sb["shots"][0]["cinematographyContract"])
    assert s1["comedyContractsApproved"] == [{
        "beatCode": sb["beats"][0]["beatId"],
        **sb["beats"][0]["comedyContract"],
    }]
    assert s1["emotionContractsApproved"] == [{
        "beatCode": sb["beats"][0]["beatId"],
        **sb["beats"][0]["emotionContract"],
    }]
    assert "OLD-CREATIVE-SOURCE-MARKER" not in json.dumps(pkg)   # nothing of rev 6 survives
    assert pkg["sourceStoryboard"]["md5"] == _md5(sb_p)          # provenance binds the source


def _physical_comedy_staging():
    return {
        "staysVisible": "Fuzzby, the leaf and Zenny remain readable throughout.",
        "contactAndWeight": "The leaf bends under contact and springs Fuzzby backward.",
        "payoffShape": "Overconfidence becomes impact, recoil and a late proud reset.",
        "prohibitedStaging": ["Do not hide the contact point."],
    }


def test_big_comedy_can_be_owned_by_a_later_beat_in_one_packed_unit():
    storyboard = _storyboard()
    big_beat = _beat("1.B2", [])
    staging = _physical_comedy_staging()
    big_beat["comedyContract"].update({
        "mode": "BIG",
        "physicalStaging": staging,
    })
    storyboard["beats"].append(big_beat)
    shot = storyboard["shots"][0]
    shot["beatIds"] = ["1.B1", "1.B2"]
    shot["performanceContract"]["beatOwner"] = "1.B2"
    shot["performanceContract"]["comedyStaging"] = staging

    H._validate_supervision_contracts(storyboard)


def test_big_comedy_in_a_packed_unit_refuses_the_wrong_typed_owner():
    storyboard = _storyboard()
    big_beat = _beat("1.B2", [])
    staging = _physical_comedy_staging()
    big_beat["comedyContract"].update({
        "mode": "BIG",
        "physicalStaging": staging,
    })
    storyboard["beats"].append(big_beat)
    shot = storyboard["shots"][0]
    shot["beatIds"] = ["1.B1", "1.B2"]
    shot["performanceContract"]["beatOwner"] = "1.B1"
    shot["performanceContract"]["comedyStaging"] = staging

    with pytest.raises(H.HandoverRefused, match="does not identify a BIG beat"):
        H._validate_supervision_contracts(storyboard)


def test_packed_unit_handover_keeps_all_beat_dialogue_and_big_gag_contracts():
    first = _beat("1.B1", ["FUZZBY: First."])
    second = _beat("1.B2", ["ZENNY: Second."])
    first_staging = _physical_comedy_staging()
    second_staging = {
        "staysVisible": "The pollen mark and blossom remain readable.",
        "contactAndWeight": "The blossom cups Fuzzby and arrests his forward motion.",
        "payoffShape": "The correction ends with Fuzzby held upside down.",
        "prohibitedStaging": ["Do not hide the blossom contact."],
    }
    for beat, staging in ((first, first_staging), (second, second_staging)):
        beat["comedyContract"].update({"mode": "BIG", "physicalStaging": staging})

    shot = _sb_shot("S1.SH1", ["1.B1", "1.B2"], "PLANNED_CUT")
    shot["performanceContract"]["beatOwner"] = "1.B2"
    shot["performanceContract"]["comedyStaging"] = second_staging
    occurrences = first["dialogueOccurrences"] + second["dialogueOccurrences"]
    detail = _pd(
        "S1.SH1", True, occurrence_ids=[item["dialogueOccurrenceId"] for item in occurrences],
        continuity_in_state=None)
    storyboard = _refresh_dialogue_contract({
        "beats": [first, second],
        "shots": [shot],
        "productionDetail": [detail],
        "voicePerformances": [
            _vp("FUZZBY", "First.", occurrences[0]),
            _vp("ZENNY", "Second.", occurrences[1]),
        ],
    })

    H._validate_storyboard_dialogue_contract(storyboard)
    H._validate_supervision_contracts(storyboard)
    distilled, _retained, _hash = H._scoped_shot(
        storyboard, "S1.SH1", {}, None)

    assert distilled.beatCodes == ["1.B1", "1.B2"]
    assert [line.exactText for line in distilled.dialogueLines] == ["First.", "Second."]
    assert [item.beatCode for item in distilled.physicalStagings] == ["1.B1", "1.B2"]
    assert distilled.physicalStaging is None


# ── THE 2026-07-17 LAW 6 SOURCE CORRECTION — GENERAL PROOF, EVERY SHOT ─────────────────
# Julian's directive: principalPerformance quotes locked dialogue verbatim on real approved
# shots (a genuine Law 6 violation cb_engine.compile_shot_contract's own _assert_no_spoken_
# words correctly refuses); physicalPerformance was verified — every shot in the real
# approved Ep1 Scene 1 storyboard, not just S1.SH1 — to carry the complete approved physical
# acting direction WITHOUT any locked dialogue. This is the GENERAL fixture-driven proof of
# that fact, deliberately shaped so it would fail on the OLD mapping and pass on the
# corrected one, for a spread of distinct shots with distinct dialogue — never hardcoded to
# one shot's own text.
_LEAKY_LINES = {
    "S1.LEAK1": ("FUZZBY", "BIZZY-BIZZY-BIZZY, BIZZY-BIZZY-BIZZY…"),
    "S1.LEAK2": ("FUZZBY", "Do I look official?"),
    "S1.LEAK3": ("ZENNY", "A Storm's coming."),
    "S1.LEAK4": ("FUZZBY", "Good thing I work well under pressure."),
}


def _leaky_shot(shot_id, speaker, line):
    """A synthetic shot whose approved principalPerformance quotes ITS OWN locked line
    verbatim (exactly the shape found on 6 of 7 real Scene-1 shots) while physicalPerformance
    stays strictly body-first and dialogue-free — the two fields' real, verified contract."""
    s = _sb_shot(shot_id, [f"beat-{shot_id}"], "PLANNED_CUT")
    s["principalPerformance"] = (f'{speaker.title()} commits to the line, delivering '
                                  f'"{line}" as the whole beat turns on it.')
    s["physicalPerformance"] = ("Weight shifts forward through the chest, wings hold a "
                                 "steady beat, the whole posture leans into the moment "
                                 "before it releases.")
    return s


def test_performance_assignment_compiles_typed_contract_never_review_prose():
    """A spread of dialogue-bearing shots proves that executable animation comes only from
    the typed performance contract. Principal, physical and timing prose remain review
    context and cannot silently become provider direction."""
    chars_cfg = {"Fuzzby": {"avoid": ""}, "Zenny": {"avoid": ""}}
    for shot_id, (speaker, line) in _LEAKY_LINES.items():
        sb_shot = _leaky_shot(shot_id, speaker, line)
        vp = _vp(speaker, line)
        pd = _pd(shot_id, True, names_speaker=True,
                 occurrence_ids=[vp["dialogueOccurrenceId"]])
        shot, retained = H.distil_shot(sb_shot, pd, ["Fuzzby", "Zenny"], [vp], None, chars_cfg)

        assert shot.performanceAssignment == cb_engine.compile_performance_contract(
            sb_shot["performanceContract"])
        assert shot.performanceAssignment != sb_shot["physicalPerformance"]
        assert shot.performanceAssignment != sb_shot["principalPerformance"]
        assert line not in shot.performanceAssignment
        assert retained["principalPerformanceApproved"] == sb_shot["principalPerformance"]
        assert retained["physicalPerformanceApproved"] == sb_shot["physicalPerformance"]
        assert retained["performanceContractApproved"] == sb_shot["performanceContract"]

        # the REAL compiler: compiles clean, zero Law 6 violation
        prompt, wc, slots = cb_engine.compile_shot_contract(
            shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
        assert line not in prompt
        assert wc == len(prompt.split())

        # The old mapping is still rejected as source architecture: dialogue-bearing review
        # prose must not replace the typed physical performance contract, even though the
        # render lane may now carry attributed locked dialogue.
        old_mapping_shot = shot.model_copy(update={"performanceAssignment": sb_shot["principalPerformance"]})
        old_prompt, _, _ = cb_engine.compile_shot_contract(
            old_mapping_shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
        assert line in old_prompt
        assert old_mapping_shot.performanceAssignment != shot.performanceAssignment


def test_distil_shot_refuses_when_typed_performance_contract_is_missing():
    sb_shot = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    sb_shot["performanceContract"] = None
    pd = _pd("S1.SH9", True)
    with pytest.raises(H.HandoverRefused, match="no typed Gate-5 performanceContract"):
        H.distil_shot(sb_shot, pd, ["Fuzzby", "Zenny"], [], None, {})


def test_distil_shot_refuses_missing_character_truth_or_cinematography():
    pd = _pd("S1.SH9", True)
    no_truth = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    no_truth["performanceContract"]["characterTruths"] = []
    with pytest.raises(H.HandoverRefused, match="missing character-specific truth"):
        H.distil_shot(no_truth, pd, ["Fuzzby", "Zenny"], [], None, {})

    no_camera = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    no_camera["cinematographyContract"] = None
    with pytest.raises(H.HandoverRefused, match="no complete typed cinematographyContract"):
        H.distil_shot(no_camera, pd, ["Fuzzby", "Zenny"], [], None, {})


# ── req 3: only the distilled categories, structure honoured ──────────────────────────
def test_distils_only_the_categories_and_shot_structure():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)       # dry run is enough here
    s1, s2 = pkg["shots"]
    assert s1["sourceType"] == "opener" and s1.get("keyframePrompt")
    assert s2["sourceType"] == "relay" and s2["sourceShotId"] == "S1.SH1"
    assert "keyframePrompt" not in s2 or not s2.get("keyframePrompt")
    assert s1["prohibited"] == ["Zenny stays on her petal"]      # <=3 essential protections
    assert s1["durationSec"] == 6.0                              # midpoint of "5-7s"
    for s in (s1, s2):                                           # Option D lean brief holds
        assert s["promptWords"] == len(s["seedancePrompt"].split())
        assert "Begin exactly on @图1" in s["seedancePrompt"]
    assert pkg["handover"]["integrationGaps"] == []
    assert pkg["creativeIntent"]["schemaVersion"] == 2
    assert pkg["creativeIntent"]["beatExperienceContracts"][0]["emotion"]["owner"] == "Fuzzby"
    assert pkg["directorStatement"]["audienceFeeling"] == (
        "ride with Fuzzby, then catch his bluff")


def test_protections_capped_at_three():
    sb_p, pkg_p = _tmp()
    sb = json.load(open(sb_p))
    sb["productionDetail"][0]["essentialProviderProtections"] = ["one", "two", "three", "four"]
    json.dump(sb, open(sb_p, "w"))
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    assert pkg["shots"][0]["prohibited"] == ["one", "two", "three"]


def test_no_production_detail_refuses():
    sb_p, pkg_p = _tmp()
    sb = json.load(open(sb_p))
    sb["productionDetail"] = []
    json.dump(sb, open(sb_p, "w"))
    with pytest.raises(H.HandoverRefused, match="no Production Detail"):
        H.promote(sb_p, pkg_p, log=lambda *a, **k: None)


# ── req 4: creative-room internals never reach production or the brief ────────────────
def test_internals_never_enter_package_or_brief():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    dump = json.dumps(pkg, ensure_ascii=False)
    for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER, "Hard constraints:",
                    "showrunnerJudgement", "internalRevisions", "treatments",
                    "treatmentSelection"):
        assert banned not in dump, banned
    for s in pkg["shots"]:
        for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER):
            assert banned not in s["seedancePrompt"]
            assert banned not in (s.get("keyframePrompt") or "")


# ── req 5: new revision; every earlier authorisation stale ────────────────────────────
def test_promotion_bumps_revision_and_stales_prior_authorisations():
    sb_p, pkg_p = _tmp()
    old = json.load(open(pkg_p))
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert pkg["revision"] == old["revision"] + 1                # versioned, never in place
    assert pkg["voidedTokens"] == ["db660b33"]                   # void history carries forward
    import cb_render
    assert cb_render._shots_hash(pkg) != cb_render._shots_hash(old)
    assert pkg["shots"][0]["seedancePrompt"] != old["shots"][0]["seedancePrompt"]
    with pytest.raises(cb_render.Refused, match="VOID"):
        cb_render._verify_envelope({"token": "stale-pre-envelope"})


# ── req 7 + verbatim law: dry run writes nothing; dialogue survives exactly ───────────
def test_dry_run_writes_nothing_and_module_has_no_provider_access():
    d = pathlib.Path(tempfile.mkdtemp())
    sb_p = d / "sb.json"
    json.dump(_storyboard(), open(sb_p, "w"))
    pkg_p = d / "brand_new_pkg.json"                             # does not exist yet
    pkg = H.promote(sb_p, pkg_p, dry_run=True, log=lambda *a, **k: None)
    assert not pkg_p.exists()                                    # dry run stored NOTHING
    assert pkg["revision"] == 1
    src = (HERE / "cb_handover.py").read_text()
    # 2026-07-17 (Julian's layer-boundary correction, item 2): the invariant is RESTORED in
    # full — neither cb_gen (the provider-calling module) nor cb_render (the renderer entry
    # point) may be imported here, no exception. promote_to_canonical no longer needs to
    # import cb_render even narrowly for its package-path convention: that convention now
    # lives in cb_engine.canonical_package_path (cb_engine.py already owns the canonical
    # package CONTRACT), a pure path helper this module calls directly — it was never a
    # provider call, but routing it through cb_render's own module was still a real,
    # avoidable coupling across the promotion boundary. Fixed at the source, not narrowed
    # here at the test.
    assert "import cb_gen" not in src
    assert "import cb_render" not in src
    # no CALL syntax to any provider function — a docstring citing a confirmed provider
    # fact (e.g. "cb_gen.generate_video_seedance's own duration=8 default") is fine and
    # expected (Julian's audit directive); an actual call/attribute-invocation is not
    assert not any(pat in src for pat in
                   ("cb_gen.generate_video_seedance(", "cb_gen.generate_video(",
                    "cb_gen.eleven_", "_fal_upload(", "_fal_subscribe(",
                    "cb_gen.generate_image("))


def test_verbatim_dialogue_lands_on_the_correct_shot():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    s1, s2 = pkg["shots"]
    lines = s1["dialogueLines"] + s2["dialogueLines"]
    assert len(lines) == 1
    ln = lines[0]
    assert ln["exactText"] == "Nailed it."                       # verbatim, never reworded
    assert "Nailed it" not in ln["delivery"]                     # delivery carries no words
    for s in (s1, s2):
        assert "Nailed it" not in s["seedancePrompt"]            # Law 6 holds through handover


# ── THE HANDOVER-MAPPING CORRECTION (2026-07-17): VOICE MAPPING ────────────────────────
# The keyframe/motion-brief corrections were CONSOLIDATED to their actual source,
# cb_engine.compile_keyframe_prompt/compile_shot_contract (see test_cb_engine.py's own
# 'HANDOVER-MAPPING CORRECTION' section, 2026-07-17) — the two fixture-based tests that
# used to live here (keyframe-follows-approved-state, screen-side-conditional) exercised
# H._keyframe_brief/H._compile_motion_brief directly; both functions were DELETED in the
# consolidation, not relocated, so those tests moved with the logic rather than being kept
# as dead references to code that no longer exists here. cb_handover.py's real, permanent
# responsibility below (voice mapping) never touched cb_engine.py and is unaffected.
def test_voice_delivery_carries_v3_direction_not_abstract_dramatic_intention():
    """The voice-mapping correction: DialogueLine.delivery (which feeds
    cb_engine.compile_audio_brief, the ElevenLabs-facing text) must carry the approved,
    EXECUTABLE elevenLabsV3Direction verbatim — never the abstract dramaticIntention read
    that used to silently replace it."""
    vp = _vp("FUZZBY", "Nailed it.")
    vp["elevenLabsV3Direction"] = "[proud, breathless] land the line like the stunt already worked."
    lines = H._dialogue_lines([vp], [{
        "dialogueOccurrenceId": vp["dialogueOccurrenceId"],
        "startSec": 1.0, "endSec": 2.25}], 6.0)
    assert lines[0]["delivery"] == vp["elevenLabsV3Direction"]
    assert lines[0]["delivery"] != vp["dramaticIntention"]
    assert (lines[0]["startSec"], lines[0]["endSec"]) == (1.0, 2.25)


def test_repeated_identical_dialogue_keeps_distinct_numeric_windows():
    first = _vp("FUZZBY", "Again.", {
        "dialogueOccurrenceId": "occurrence:first", "sourceEventId": "event:first",
        "beatId": "1.B1", "sourceBeatId": "source-beat:test:1.B1"})
    second = _vp("FUZZBY", "Again.", {
        "dialogueOccurrenceId": "occurrence:second", "sourceEventId": "event:second",
        "beatId": "1.B1", "sourceBeatId": "source-beat:test:1.B1"})
    windows = [
        {"dialogueOccurrenceId": "occurrence:first", "startSec": 0.4, "endSec": 1.1},
        {"dialogueOccurrenceId": "occurrence:second", "startSec": 2.0, "endSec": 2.7}]
    lines = H._dialogue_lines([first, second], windows, 4.0)
    assert [line["exactText"] for line in lines] == ["Again.", "Again."]
    assert [line["dialogueOccurrenceId"] for line in lines] == [
        "occurrence:first", "occurrence:second"]
    assert [(line["startSec"], line["endSec"]) for line in lines] == [
        (0.4, 1.1), (2.0, 2.7)]


def test_canon_offscreen_speaker_is_audible_and_never_added_to_visible_cast():
    sb_shot = _sb_shot("S1.SH1", ["1.B1"], "PLANNED_CUT")
    vp = _vp("Bo's Mum", "Time to go.")
    pd = _pd("S1.SH1", True, occurrence_ids=[vp["dialogueOccurrenceId"]])
    cfg = {
        "Fuzzby": {"avoid": ""},
        "Zenny": {"avoid": ""},
        "Bo's Mum": {"avoid": "", "offscreenOnly": True},
    }
    shot, _ = H.distil_shot(
        sb_shot, pd, ["Fuzzby", "Zenny", "Bo's Mum"], [vp], None, cfg)

    assert "Fuzzby" in shot.charactersInFrame
    assert "Bo's Mum" not in shot.charactersInFrame
    assert shot.offscreenSpeakers == ["Bo's Mum"]


def test_first_stage_drives_opening_cast_and_visible_canon_props_are_bound():
    sb_shot = _sb_shot("S4.SH1", ["4.B1", "4.B2"], "PLANNED_CUT")
    sb_shot["stagePlan"] = [{
        "beatIds": ["4.B1"], "primaryEvent": "Bo walks beside Keen",
        "emotionalOrComicTurn": "play begins", "observableEndState": "Bo keeps moving",
    }]
    sb_shot["closingImage"] = "Aida sits beside Bo while he grips the satchel"
    beats = {
        "4.B1": {"participatingCharacters": ["Bo", "Keen"]},
        "4.B2": {"participatingCharacters": ["Bo", "Keen", "Aida"]},
    }
    cfg = {
        "Bo": {"props": {"satchel": "cb-seed/assets/props/CB_Bo_satchel.png"}},
        "Keen": {}, "Aida": {},
    }
    assert H._opening_cast_for_shot(sb_shot, beats, cfg) == ["Bo", "Keen"]
    assert H._required_prop_references(
        sb_shot, _pd("S4.SH1", True), ["Bo", "Keen", "Aida"], cfg) == ["satchel"]


def test_offscreen_speaker_is_removed_from_visual_continuity_boundary():
    boundary = {
        "lighting": "warm hollow light",
        "cameraSide": "inside the doorway axis",
        "characters": [
            {"characterId": "Bo"},
            {"characterId": "Bo's Mum"},
        ],
    }
    visible = H._visible_continuity_boundary(
        boundary, {"Bo": {}, "Bo's Mum": {"offscreenOnly": True}})
    assert [item["characterId"] for item in visible["characters"]] == ["Bo"]
    assert len(boundary["characters"]) == 2


def test_typed_continuity_maps_each_field_without_prose_duplication():
    sb_shot = _sb_shot("S1.SH1", ["1.B1"], "PLANNED_CUT")
    pd = _pd("S1.SH1", True, continuity_in_state=None)
    state = pd["continuityOutState"]["characters"][0]
    state.update({"screenZone": "lower-left", "facing": "three-quarter right",
                  "pose": "one wing braced on the leaf", "expression": "caught pride",
                  "visibleMarks": ["pollen moustache"], "heldProps": ["blue ribbon"]})
    pd["continuityOutState"]["lighting"] = "cool skylight with a warm leaf bounce"
    pd["continuityOutState"]["cameraSide"] = "pond side of the action line"
    shot, _ = H.distil_shot(
        sb_shot, pd, ["Fuzzby", "Zenny"], [], None,
        {"Fuzzby": {"avoid": ""}, "Zenny": {"avoid": ""}})
    fuzzby = shot.continuityOut.characters[0]
    assert fuzzby.screenZone == "lower-left"
    assert fuzzby.facing == "three-quarter right"
    assert fuzzby.pose == "one wing braced on the leaf"
    assert fuzzby.expression == "caught pride"
    assert fuzzby.visibleMarks == ["pollen moustache"]
    assert fuzzby.heldProps == ["blue ribbon"]
    assert shot.continuityOut.lighting != shot.continuityOut.cameraSide
    assert pd["continuityOut"] not in fuzzby.model_dump().values()


def test_voice_director_brief_carries_all_four_approved_fields_discretely():
    """The production voice brief must carry exact locked dialogue, the approved
    elevenLabsV3Direction, the approved expectedTiming and the concise
    physicalActionRelationship — four discrete fields, never collapsed into one summary."""
    vp = _vp("FUZZBY", "Nailed it.")
    vp["elevenLabsV3Direction"] = "[proud] deliver it like the stunt already landed."
    vp["expectedTiming"] = "right after the wobble settles"
    vp["physicalActionRelationship"] = "the line contradicts the still-recovering hover"
    brief = H._voice_director_brief_lines([vp])
    assert len(brief) == 1
    b = brief[0]
    assert b["exactDialogue"] == "Nailed it."
    assert b["elevenLabsV3Direction"] == vp["elevenLabsV3Direction"]
    assert b["expectedTiming"] == vp["expectedTiming"]
    assert b["physicalActionRelationship"] == vp["physicalActionRelationship"]


def test_real_s1sh1_maps_cleanly_into_the_canonical_engine_compiler():
    """Pinned to the REAL, approved 1.B1 data (2026-07-17): distil_shot's mapping of the
    real approved shot/production-detail, fed into cb_engine's OWN canonical
    compile_keyframe_prompt/compile_shot_contract (never a cb_handover-local compiler,
    consolidated away 2026-07-17) — confirms the mapping layer produces a Shot the real
    engine compiles cleanly, on real production content, not just a synthetic fixture.
    Skips gracefully if the real storyboard file is absent/unapproved so this suite never
    depends on production state to pass."""
    real_sb_path = pathlib.Path(__file__).resolve().parent.parent / P.OUTPUT_REL / "creative" / \
        "Ep1_scene1_storyboard.json"
    if not real_sb_path.exists():
        pytest.skip("real storyboard not present in this environment")
    sb = json.load(open(real_sb_path))
    if sb.get("approvalState") != H.APPROVED_STATE:
        pytest.skip("real storyboard not currently approved")
    s1 = next((s for s in sb["shots"] if s["shotId"] == "S1.SH1"), None)
    pd1 = next((p for p in sb.get("productionDetail", []) if p["shotId"] == "S1.SH1"), None)
    if not (s1 and pd1):
        pytest.skip("real S1.SH1 shot/production-detail not present")
    if (not s1.get("performanceContract") or "continuityOutState" not in pd1 or
            "dialogueTimings" not in pd1):
        pytest.skip("real storyboard predates the typed execution contract and must be regenerated")
    chars_cfg = json.load(open(H.CHARS)) if H.CHARS.exists() else {}
    voice_by_occurrence = {
        voice["dialogueOccurrenceId"]: voice
        for voice in sb.get("voicePerformances", [])
    }
    shot_voices = [
        voice_by_occurrence[occurrence_id]
        for occurrence_id in pd1.get("dialogueOccurrenceIds", [])
    ]
    shot, retained = H.distil_shot(
        s1, pd1, ["Fuzzby", "Zenny"], shot_voices, None, chars_cfg,
        H._owned_big_comedy_stagings(sb, s1),
        H._owned_beat_contracts(sb, s1, "comedyContract"),
        H._owned_beat_contracts(sb, s1, "emotionContract"))
    assert [item["beatCode"] for item in retained["comedyContractsApproved"]] == [
        "1.B1", "1.B2", "1.B3"]
    assert [item["mode"] for item in retained["comedyContractsApproved"]] == [
        "BIG", "SMALL", "BIG"]
    assert "environmental participation" in (
        retained["comedyContractsApproved"][0]["mechanism"])
    assert "deadpan observation" in retained["comedyContractsApproved"][1]["mechanism"]
    assert "concealment becoming revelation" in (
        retained["comedyContractsApproved"][2]["mechanism"])
    assert len(retained["emotionContractsApproved"]) == 3
    kf, kwc, kslots = cb_engine.compile_keyframe_prompt(
        shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
    assert "already" in kf.lower()                                # the real, approved opening state
    assert "anticipation instant" not in kf.lower()
    assert "action already happening" not in kf.lower()
    prompt, wc, slots = cb_engine.compile_shot_contract(
        shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
    assert "screen sides" not in prompt                           # no default lane lock


# ── THE SINGLE-SHOT ZERO-SPEND HANDOVER (2026-07-17/18 directive) ─────────────────────
def test_promote_shot_scoped_to_one_shot_only():
    sb_p, pkg_p = _tmp()
    pkg = H.promote_shot(sb_p, "S1.SH1", pkg_p, log=lambda *a, **k: None)
    assert len(pkg["shots"]) == 1 and pkg["shots"][0]["shotId"] == "S1.SH1"
    assert pkg["scope"] == "single-shot handover: S1.SH1"
    assert pkg["shots"][0]["sourceType"] == "opener"
    assert pkg["shots"][0]["durationSec"] == 6.0                 # midpoint of "5-7s"
    assert pkg["shots"][0]["dialogueLines"][0]["exactText"] == "Nailed it."


def test_promote_shot_write_preserves_existing_sibling_units():
    sb_p, pkg_p = _tmp()
    old = json.load(open(pkg_p))
    old["shots"].append({
        "shotId": "S1.SH2", "durationSec": 7.0,
        "seedancePrompt": "APPROVED SIBLING PROMPT",
    })
    old["continuityLedger"] = [{
        "shotId": "S1.SH2", "status": "approved",
        "approval": {"approved": True, "candidate": 1},
    }]
    json.dump(old, open(pkg_p, "w"))

    pkg = H.promote_shot(
        sb_p, "S1.SH1", pkg_p, dry_run=False, log=lambda *a, **k: None)

    shots = {item["shotId"]: item for item in pkg["shots"]}
    assert shots["S1.SH1"]["dialogueLines"][0]["exactText"] == "Nailed it."
    assert shots["S1.SH2"]["seedancePrompt"] == "APPROVED SIBLING PROMPT"
    assert pkg["continuityLedger"][0]["status"] == "approved"
    assert json.load(open(pkg_p)) == pkg


def test_place_voices_for_beat_splits_by_line_content_not_bare_speaker_name():
    """Pinned to the real bug found live against the actual Ep1 S1.SH1/S1.SH2 data
    (2026-07-17): a two-line beat where BOTH shots' dialogueTiming mention the same bare
    speaker name ('FUZZBY') by word-boundary, but only ONE shot's dialogueTiming actually
    quotes each specific line. Speaker-name-only matching sent both lines to the
    first-sorted shot; content-first matching must split them correctly."""
    sb = _storyboard()
    sb["beats"] = [_beat("1.B1", ["FUZZBY: BIZZY-BIZZY-BIZZY…", "FUZZBY: Nailed it."])]
    first, second = sb["beats"][0]["dialogueOccurrences"]
    sb["shots"] = [_sb_shot("S1.SH1", ["1.B1"], "CONTINUOUS"),
                    _sb_shot("S1.SH2", ["1.B1"], "PLANNED_CUT")]
    sb["productionDetail"] = [
        {**_pd("S1.SH1", True), "dialogueTiming":
            "FUZZBY chant is already underway at frame one: “BIZZY-BIZZY-BIZZY…” "
            "in brisk pulse, carrying into the snap-away.",
            "dialogueOccurrenceIds": [first["dialogueOccurrenceId"]]},
        {**_pd("S1.SH2", False), "dialogueTiming":
            "FUZZBY: cut in after the messy recovery; hold the pose, then place "
            "“Nailed it.” before the hover steadies.",
            "dialogueOccurrenceIds": [second["dialogueOccurrenceId"]]}]
    sb["voicePerformances"] = [_vp("FUZZBY", "BIZZY-BIZZY-BIZZY…", first),
                               _vp("FUZZBY", "Nailed it.", second)]
    placement = H.place_voices_for_beat(
        "1.B1", ["S1.SH1", "S1.SH2"], sb["voicePerformances"],
        sb["beats"][0]["dialogueOccurrences"],
        {p["shotId"]: p for p in sb["productionDetail"]})
    assert [vp["exactDialogue"] for vp in placement["S1.SH1"]] == ["BIZZY-BIZZY-BIZZY…"]
    assert [vp["exactDialogue"] for vp in placement["S1.SH2"]] == ["Nailed it."]


def test_promote_shot_refuses_missing_shot_or_production_detail():
    sb_p, pkg_p = _tmp()
    with pytest.raises(H.HandoverRefused, match="not found"):
        H.promote_shot(sb_p, "S1.SH9", pkg_p, log=lambda *a, **k: None)
    sb = json.load(open(sb_p))
    sb["productionDetail"] = [p for p in sb["productionDetail"] if p["shotId"] != "S1.SH1"]
    json.dump(sb, open(sb_p, "w"))
    with pytest.raises(H.HandoverRefused, match="no Production Detail"):
        H.promote_shot(sb_p, "S1.SH1", pkg_p, log=lambda *a, **k: None)


def test_promote_shot_refuses_when_not_approved():
    sb_p, pkg_p = _tmp("awaiting-human-storyboard-approval")
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote_shot(sb_p, "S1.SH1", pkg_p, dry_run=False, log=lambda *a, **k: None)


def test_promote_shot_never_leaks_internals_and_dry_run_writes_nothing():
    sb_p, pkg_p = _tmp()
    before_exists = pkg_p.exists()
    pkg = H.promote_shot(sb_p, "S1.SH1", pkg_p, dry_run=True, log=lambda *a, **k: None)
    dump = json.dumps(pkg, ensure_ascii=False)
    for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER):
        assert banned not in dump
    assert not pkg_p.exists() if not before_exists else True     # nothing new written


def test_duration_normalized_to_midpoint_for_fixed_provider_duration():
    assert H.normalize_duration_for_provider("5-7s") == 6.0
    assert H.normalize_duration_for_provider("4-8s") == 6.0
    assert H.normalize_duration_for_provider("5-6s") == 6.0       # rounds .5 up
    assert H.normalize_duration_for_provider("6-7s") == 7.0       # no banker rounding
    assert H.normalize_duration_for_provider("24-30s") == 27.0    # full 2.5 unit window
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("not a range")
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("9-3s")                 # inverted, non-credible
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("28-31s")               # never silently truncates
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("1-3s")                 # never silently pads


# ── THE SOURCE-LEVEL HANDOVER: creative-room storyboard -> canonical package (2026-07-17) ──
def test_internal_leak_check_exempts_only_internalConstraints_field():
    """2026-07-17 correction: internalConstraints legitimately starts with 'Hard
    constraints:' (cb_engine.hard_constraints' own real text) — must not false-positive.
    Every other field, and every other banned term, is still checked exactly as before."""
    clean = [{"shotId": "S1.SH1", "internalConstraints": "Hard constraints: no crystals on bees."}]
    H._assert_no_internal_leak(clean)          # must not raise
    leaky_elsewhere = [{"shotId": "S1.SH1", "seedancePrompt": "Hard constraints: leaked here too"}]
    with pytest.raises(H.HandoverRefused, match="Hard constraints"):
        H._assert_no_internal_leak(leaky_elsewhere)
    real_leak = [{"shotId": "S1.SH1", "internalConstraints": "Hard constraints: fine",
                   "notes": "showrunnerJudgement leaked here"}]
    with pytest.raises(H.HandoverRefused, match="showrunnerJudgement"):
        H._assert_no_internal_leak(real_leak)


def _canonical_env(tmp_path, monkeypatch, sb_state="approved"):
    """Redirects cb_engine.canonical_package_path to a scratch dir so promote_to_canonical's
    real archive/write behaviour can be proven without touching production files.
    2026-07-17 correction (Julian's layer-boundary directive, item 2): promote_to_canonical
    no longer resolves the canonical path via cb_render._pkg_path (removed, along with the
    cb_render import itself) — it calls cb_engine.canonical_package_path directly, the SAME
    function cb_render._pkg_path itself now delegates to. Patching it here at its actual
    source correctly redirects BOTH cb_handover's own call and any test helper that still
    reads back through cb_render._pkg_path (it delegates, so it sees the same patch)."""
    import cb_engine
    store = ScriptStore(
        tmp_path, script_root=tmp_path / "projects/crystal-bears/episodes/scripts")
    current = store.store("Ep1", "fixture script\n", "Fixture",
                          activated_at="2026-01-01T00:00:00+00:00")
    event = {"i": 0, "scene": 1, "type": "dialogue",
             "speaker": "FUZZBY", "text": "Nailed it."}
    source_record = cb_lineage.source_event_record(current["scriptVersionId"], event)
    source_signature = cb_lineage.source_beat_event_signature(
        current["scriptVersionId"], [event])
    source_beat = {
        "sceneNumber": 1, "beatCode": "1.B1", "storyBeat": "x",
        "sourceBeatId": cb_lineage.source_beat_id(source_signature),
        "sourceEventIds": [source_record["sourceEventId"]],
        "dialogueOccurrenceIds": [source_record["dialogueOccurrenceId"]],
        "sourceEventRange": {"firstEventIndex": 0, "lastEventIndex": 0,
            "firstEventId": source_record["sourceEventId"],
            "lastEventId": source_record["sourceEventId"], "eventCount": 1},
        "sourceEventSignature": source_signature,
        "cuts": [{"n": 1, "sourceEventId": source_record["sourceEventId"],
                  "sourceEventIndex": 0, "sourceSceneNumber": 1,
                  "sourceType": "dialogue",
                  "dialogueOccurrenceId": source_record["dialogueOccurrenceId"],
                  "speaker": "FUZZBY", "exactText": "Nailed it.",
                  "dialogue": "FUZZBY: Nailed it.", "action": None}],
    }
    source_ref = {key: current[key] for key in
                  ("episodeId", "scriptVersionId", "sha256", "byteLength", "contentPath")}
    beat_pkg = {"title": "Fixture", "episode": 1, "logline": "x", "leadBear": "Keen",
                "format": "11-min", "unit": "beat", "sourceScript": source_ref,
                "beats": [source_beat]}
    beat_pkg["sourceContract"] = cb_lineage.beat_package_source_contract(
        current["scriptVersionId"], beat_pkg["beats"])
    beat_pkg["inputSignature"] = cb_lineage.dependency_signature(
        "beat-package-input", {
            "scriptVersionId": current["scriptVersionId"],
            "canonProfileDigest": TEST_CANON_DIGESTS["story"],
        })
    beat_pkg["contentSignature"] = cb_lineage.beat_package_signature(beat_pkg)
    beat_path = tmp_path / "source" / "Ep1_Fixture_beat_package.json"
    beat_path.parent.mkdir(parents=True)
    json.dump(beat_pkg, open(beat_path, "w"))
    sb = _storyboard(sb_state)
    sb["sourceScript"] = source_ref
    directed_beat = sb["beats"][0]
    directed_beat.update({key: source_beat[key] for key in
                          ("sourceBeatId", "sourceEventIds", "sourceEventRange",
                           "sourceEventSignature")})
    occurrence = {"dialogueOccurrenceId": source_record["dialogueOccurrenceId"],
                  "sourceEventId": source_record["sourceEventId"], "sourceEventIndex": 0,
                  "beatId": "1.B1", "sourceBeatId": source_beat["sourceBeatId"],
                  "speaker": "FUZZBY", "exactText": "Nailed it."}
    directed_beat["dialogueOccurrences"] = [occurrence]
    directed_beat["exactDialogue"] = ["FUZZBY: Nailed it."]
    sb["voicePerformances"] = [_vp("FUZZBY", "Nailed it.", occurrence)]
    sb["productionDetail"][0]["dialogueOccurrenceIds"] = [
        occurrence["dialogueOccurrenceId"]]
    sb["productionDetail"][0]["dialogueTimings"] = [{
        "dialogueOccurrenceId": occurrence["dialogueOccurrenceId"],
        "startSec": 0.5, "endSec": 1.25}]
    sb["productionDetail"][1]["dialogueOccurrenceIds"] = []
    sb["productionDetail"][1]["dialogueTimings"] = []
    _refresh_dialogue_contract(sb)
    sb["sourceBeatPackage"] = {
        "path": str(beat_path.relative_to(tmp_path)),
        "contentSignature": beat_pkg["contentSignature"],
    }
    storyboard_inputs = {"scriptVersionId": current["scriptVersionId"],
                         "beatPackageDigest": beat_pkg["contentSignature"]["digest"],
                         "episodeVisionDigest": "fixture", "sceneNumber": "1",
                         "ambitionBrief": None, "canonSources": {},
                         "canonProfileDigest": TEST_CANON_DIGESTS["storyboard"]}
    sb["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard", storyboard_inputs)
    sb["canonLock"] = {
        "manifestDigest": TEST_CANON_MANIFEST,
        "profile": "storyboard",
        "profileDigest": TEST_CANON_DIGESTS["storyboard"],
    }
    sb_p = tmp_path / "sb.json"
    json.dump(sb, open(sb_p, "w"))
    pkg_dir = tmp_path / P.OUTPUT_REL
    pkg_dir.mkdir()
    monkeypatch.setattr(H, "ROOT", tmp_path)
    monkeypatch.setattr(H, "SCRIPT_STORE", store)
    monkeypatch.setattr(H.cb_canon, "require_locked", lambda *args, **kwargs: {
        "manifestDigest": TEST_CANON_MANIFEST,
        "profileDigests": dict(TEST_CANON_DIGESTS),
    })
    monkeypatch.setattr(cb_engine, "canonical_package_path",
                        lambda scene, episode="Ep1": pkg_dir / f"{episode}_scene{scene}_production_package.json")
    return sb_p, pkg_dir


def _convert_to_snapshot_storyboard(sb_p):
    sb = json.load(open(sb_p))
    source_beat_ids = [beat.get("sourceBeatId") for beat in sb.get("beats", [])]
    shot_ids = [shot.get("shotId") for shot in sb.get("shots", [])]
    inputs = {
        "scriptVersionId": sb["sourceScript"]["scriptVersionId"],
        "beatPackageDigest": sb["sourceBeatPackage"]["contentSignature"]["digest"],
        "sceneNumber": str(sb.get("sceneNumber")),
        "sourceBeatIds": source_beat_ids,
        "shotIds": shot_ids,
    }
    sb["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard-snapshot", inputs)
    sb.pop("canonLock", None)
    json.dump(sb, open(sb_p, "w"))
    return sb


def test_promote_to_canonical_dry_run_writes_nothing_and_reports_honest_validation(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    new_pkg, archived = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=True, log=lambda *a, **k: None)
    assert new_pkg["shots"][0]["shotId"] == "S1.SH1"
    assert isinstance(new_pkg["validation"]["passed"], bool)      # a REAL computed verdict,
    #                                                                never a hardcoded True
    assert list((pkg_dir).iterdir()) == []                        # nothing written
    assert archived is None                                       # no prior package to archive


def test_promote_to_canonical_accepts_current_storyboard_snapshot_signature(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    _convert_to_snapshot_storyboard(sb_p)

    new_pkg, archived = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=True, log=lambda *a, **k: None)

    assert new_pkg["shots"][0]["shotId"] == "S1.SH1"
    assert archived is None
    assert list(pkg_dir.iterdir()) == []


def test_promote_to_canonical_refuses_stale_storyboard_snapshot_signature(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    sb = _convert_to_snapshot_storyboard(sb_p)
    sb["inputSignature"]["inputs"]["shotIds"] = ["S1.STALE"]
    json.dump(sb, open(sb_p, "w"))

    with pytest.raises(H.HandoverRefused, match="storyboard dependency signature is missing or stale"):
        H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                               dry_run=True, log=lambda *a, **k: None)

    assert list(pkg_dir.iterdir()) == []


def test_promote_to_canonical_writes_canonical_shape_and_archives_the_old_package(tmp_path, monkeypatch):
    import cb_render as R
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old_path = R._pkg_path("1", "Ep1")
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6,
           "shots": [{"shotId": "1.B1.S1", "performanceAssignment": "OLD-MARKER"}],
           "continuityLedger": [], "validation": {"passed": True}}
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    new_pkg, archived = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=False, log=lambda *a, **k: None)
    assert archived.exists() and _md5(archived) == old_md5        # byte-identical, preserved
    assert new_pkg["revision"] == 7
    # the canonical shape cb_render.py actually reads — every key it touches, present
    for key in ("episode", "sceneNumber", "shots", "continuityLedger", "validation", "revision"):
        assert key in new_pkg
    written = json.load(open(old_path))                           # same path, new content
    assert written["revision"] == 7
    assert [s["shotId"] for s in written["shots"]] == ["S1.SH1"]   # sole creative source
    assert "1.B1.S1" not in json.dumps(written["shots"])           # legacy shot gone, not merged
    ledger_ids = [e["shotId"] for e in written["continuityLedger"]]
    assert ledger_ids == ["S1.SH1"]


def test_scoped_canonical_promotion_preserves_unselected_sibling_and_approval(
        tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    first, _ = H.promote_to_canonical(
        sb_p, "1", ["S1.SH1", "S1.SH2"], episode="Ep1",
        dry_run=False, log=lambda *a, **k: None)
    package_path = pkg_dir / "Ep1_scene1_production_package.json"
    sibling = next(item for item in first["shots"] if item["shotId"] == "S1.SH2")
    sibling_ledger = next(
        item for item in first["continuityLedger"] if item["shotId"] == "S1.SH2")
    sibling_ledger["status"] = "approved"
    sibling_ledger["approval"] = {
        "approved": True, "candidate": 2, "path": "/kept/sibling.mp4"}
    json.dump(first, open(package_path, "w"))

    promoted, _ = H.promote_to_canonical(
        sb_p, "1", ["S1.SH1"], episode="Ep1",
        dry_run=False, log=lambda *a, **k: None)

    shots = {item["shotId"]: item for item in promoted["shots"]}
    ledgers = {item["shotId"]: item for item in promoted["continuityLedger"]}
    assert shots["S1.SH2"] == sibling
    assert ledgers["S1.SH2"] == sibling_ledger
    assert "S1.SH2" in promoted["handover"]["carriedForwardUnchangedShots"]
    assert "S1.SH2" not in promoted["handover"]["resetChangedShots"]


def test_unchanged_selected_shot_preserves_approval_but_refreshes_ledger_structure(
        tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    first, _ = H.promote_to_canonical(
        sb_p, "1", ["S1.SH1", "S1.SH2"], episode="Ep1",
        dry_run=False, log=lambda *a, **k: None)
    package_path = pkg_dir / "Ep1_scene1_production_package.json"
    ledger = next(
        item for item in first["continuityLedger"] if item["shotId"] == "S1.SH1")
    ledger.update({
        "status": "approved",
        "approvedTake": "/kept/selected.mp4",
        "approval": {"approved": True, "candidate": 2},
        "sourceType": "relay",
        "sourceShotId": "S1.SH1",
    })
    json.dump(first, open(package_path, "w"))

    promoted, _ = H.promote_to_canonical(
        sb_p, "1", ["S1.SH1"], episode="Ep1",
        dry_run=False, log=lambda *a, **k: None)

    current = next(
        item for item in promoted["continuityLedger"] if item["shotId"] == "S1.SH1")
    assert current["status"] == "approved"
    assert current["approvedTake"] == "/kept/selected.mp4"
    assert current["approval"] == {"approved": True, "candidate": 2}
    assert current["sourceType"] == "opener"
    assert current["sourceShotId"] is None


def test_promote_to_canonical_refuses_missing_typed_continuity_before_candidate(tmp_path, monkeypatch):
    """A malformed typed boundary cannot be degraded into an invalid candidate package."""
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old_path = pkg_dir / "Ep1_scene1_production_package.json"
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6,
           "shots": [{"shotId": "1.B1.S1", "performanceAssignment": "STILL-THE-VALID-ONE"}],
           "continuityLedger": [], "validation": {"passed": True}}
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    sb = json.load(open(sb_p))
    sb["productionDetail"][0]["continuityOutState"]["characters"] = []
    json.dump(sb, open(sb_p, "w"))

    with pytest.raises(H.HandoverRefused, match="cast must be exactly"):
        H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                               dry_run=False, log=lambda *a, **k: None)
    assert _md5(old_path) == old_md5
    assert json.load(open(old_path))["shots"][0]["performanceAssignment"] == "STILL-THE-VALID-ONE"
    assert not list(pkg_dir.rglob("*REJECTED*"))


def test_promote_to_canonical_dry_run_refusal_writes_absolutely_nothing(tmp_path, monkeypatch):
    """A failing dry run must not even write the rejected-evidence file — dry_run=True
    means nothing touches disk, full stop, matching this module's own standing contract."""
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6, "shots": [],
           "continuityLedger": [], "validation": {"passed": True}}
    old_path = pkg_dir / "Ep1_scene1_production_package.json"
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    sb = json.load(open(sb_p))
    sb["productionDetail"][0]["continuityOutState"]["characters"] = []
    json.dump(sb, open(sb_p, "w"))

    with pytest.raises(H.HandoverRefused, match="cast must be exactly"):
        H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                               dry_run=True, log=lambda *a, **k: None)
    assert _md5(old_path) == old_md5                              # completely untouched
    assert set(p.name for p in pkg_dir.rglob("*")) == {"Ep1_scene1_production_package.json"}
    #                                                    ^ no archive/ dir, no rejected file


def test_promote_to_canonical_promotes_only_named_shots_never_a_sweep(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    new_pkg, _ = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                          dry_run=True, log=lambda *a, **k: None)
    ids = [s["shotId"] for s in new_pkg["shots"]]
    assert ids == ["S1.SH1"]
    assert "S1.SH2" not in ids                                    # the sibling is real in the
    #                                                                storyboard but never named


def test_promote_to_canonical_refuses_when_not_approved(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch, sb_state="awaiting-human-storyboard-approval")
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                dry_run=True, log=lambda *a, **k: None)
    assert list(pkg_dir.iterdir()) == []


def test_current_packing_contract_is_recomputed_before_handover():
    shots = [{
        "shotId": "S1.SH1", "beatIds": ["1.B1", "1.B2"],
        "targetDurationSec": 30, "providerBoundaryReason": "scene_end",
        "providerBoundaryExplanation": "The causal scene arc lands here.",
    }]
    storyboard = {
        "unitPackingContractVersion": 1,
        "shots": shots,
        "packingPasses": True,
        "unitPackingAudit": H.cb_unit_packing.audit_units(shots),
    }
    H._validate_unit_packing_contract(storyboard)

    storyboard["shots"][0]["targetDurationSec"] = 29
    with pytest.raises(H.HandoverRefused, match="missing or stale"):
        H._validate_unit_packing_contract(storyboard)


def test_current_packing_contract_requires_showrunner_acceptance():
    shots = [{
        "shotId": "S1.SH1", "beatIds": ["1.B1"],
        "targetDurationSec": 30, "providerBoundaryReason": "scene_end",
        "providerBoundaryExplanation": "The scene ends on the approved landing image.",
    }]
    storyboard = {
        "unitPackingContractVersion": 1,
        "shots": shots,
        "packingPasses": False,
        "unitPackingAudit": H.cb_unit_packing.audit_units(shots),
    }
    with pytest.raises(H.HandoverRefused, match="Showrunner did not approve"):
        H._validate_unit_packing_contract(storyboard)

    storyboard["automaticPreparation"] = {
        "mode": "script-to-scene-direction",
        "humanGates": ["see", "hear", "watch"],
    }
    H._validate_unit_packing_contract(storyboard)


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))


def test_a_shared_phase_names_every_performer_and_still_needs_each_truth():
    """2026-09-02 (The Box Monsters S3.SH05): when two characters act in the same phase the
    folded contract Gate 5 produces reads "Fuzzby and Zenny". The handover checked the whole
    string as one name and refused the scene; every part is a cast name, checked separately."""
    shared = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    contract = shared["performanceContract"]
    contract["phases"][1]["performer"] = "Fuzzby and Zenny"
    contract["characterTruths"] = contract["characterTruths"] + [{
        "character": "Zenny",
        "canonTrait": "measured grace reads the room before it moves",
        "playableWant": "let the evidence speak without saying so",
        "pressureResponse": "holds still one beat longer than expected",
        "observableSignature": "a slow blink lands before any word",
        "substitutionTest": "Fuzzby would perform past the moment"}]
    pd = _pd("S1.SH9", True)
    assert H.distil_shot(shared, pd, ["Fuzzby", "Zenny"], [], None, {})

    # a shared phase whose second performer has no truth is still refused
    missing = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    missing["performanceContract"]["phases"][1]["performer"] = "Fuzzby and Zenny"
    with pytest.raises(H.HandoverRefused, match="missing character-specific truth"):
        H.distil_shot(missing, pd, ["Fuzzby", "Zenny"], [], None, {})

    # a name that is not in the shot's cast at all is still refused
    stranger = _sb_shot("S1.SH9", ["1.B1"], "PLANNED_CUT")
    stranger["performanceContract"]["phases"][1]["performer"] = "Fuzzby and Briggle"
    with pytest.raises(H.HandoverRefused, match="unknown performer or field"):
        H.distil_shot(stranger, pd, ["Fuzzby", "Zenny"], [], None, {})
