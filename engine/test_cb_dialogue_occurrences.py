#!/usr/bin/env python3
"""Zero-spend proofs for repeated, byte-identical dialogue occurrences."""
import copy
import sys

import pytest

HERE = __import__("pathlib").Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cb_creative as C
import cb_engine as E
import cb_handover as H
import cb_intake as I
import cb_lineage as L
import cb_llm


VERSION = "sha256:" + "7" * 64


def _source_fixture():
    events = [
        {"i": 0, "scene": 1, "type": "dialogue", "speaker": "FUZZBY", "text": "Again."},
        {"i": 1, "scene": 1, "type": "dialogue", "speaker": "FUZZBY", "text": "Again."},
    ]
    I._annotate_source_events(events, VERSION)
    cuts = I._build_cuts(events, 0, 1)
    signature = L.source_beat_event_signature(VERSION, events)
    records = signature["inputs"]["orderedEvents"]
    beat = {
        "sceneNumber": 1, "beatCode": "1.B1", "storyBeat": "The insistence repeats.",
        "characters": ["Fuzzby"], "cuts": cuts,
        "sourceBeatId": L.source_beat_id(signature),
        "sourceEventIds": [record["sourceEventId"] for record in records],
        "dialogueOccurrenceIds": [record["dialogueOccurrenceId"] for record in records],
        "sourceEventRange": {"firstEventIndex": 0, "lastEventIndex": 1,
            "firstEventId": records[0]["sourceEventId"],
            "lastEventId": records[-1]["sourceEventId"], "eventCount": 2},
        "sourceEventSignature": signature,
    }
    package = {"title": "Fixture", "episode": 1, "logline": "x", "leadBear": "Fuzzby",
               "format": "11-min", "unit": "beat",
               "sourceScript": {"scriptVersionId": VERSION}, "beats": [beat]}
    package["sourceContract"] = L.beat_package_source_contract(VERSION, [beat])
    package["contentSignature"] = L.beat_package_signature(package)
    return events, beat, package


def _voice(occurrence, **changes):
    if hasattr(occurrence, "model_dump"):
        occurrence = occurrence.model_dump()
    values = {
        "dialogueOccurrenceId": occurrence["dialogueOccurrenceId"],
        "sourceEventId": occurrence["sourceEventId"],
        "sourceEventIndex": occurrence["sourceEventIndex"],
        "beatId": occurrence["beatId"], "sourceBeatId": occurrence["sourceBeatId"],
        "speaker": occurrence["speaker"], "exactDialogue": occurrence["exactText"],
        "dramaticIntention": "insist", "subtext": "again", "relationshipTarget": "Zenny",
        "emotionalEntry": "hopeful", "emotionalExit": "more hopeful",
        "operativeWords": ["Again"], "pace": "quick", "rhythm": "even",
        "pauses": "none", "breaths": "short", "nonVerbalActions": "leans in",
        "elevenLabsV3Direction": "bright, distinct repetition",
        "physicalActionRelationship": "lands after a lean", "expectedTiming": "mid-shot",
    }
    values.update(changes)
    return C.VoicePerformance(**values)


def _creative_occurrences(beat):
    return [C.DialogueOccurrence(
        dialogueOccurrenceId=cut["dialogueOccurrenceId"],
        sourceEventId=cut["sourceEventId"], sourceEventIndex=cut["sourceEventIndex"],
        beatId=beat["beatCode"], sourceBeatId=beat["sourceBeatId"],
        speaker=cut["speaker"], exactText=cut["exactText"])
        for cut in beat["cuts"]]


def test_identical_lines_receive_distinct_ids_and_complete_source_partition():
    events, beat, package = _source_fixture()
    assert events[0]["dialogueOccurrenceId"] != events[1]["dialogueOccurrenceId"]
    assert beat["sourceEventIds"][0] != beat["sourceEventIds"][1]
    assert I.dialogue_coverage_report(events, [beat])["ok"] is True
    assert I.source_event_coverage_report(events, [beat])["ok"] is True
    assert L.validate_beat_package_source_contract(package)["ok"] is True

    swapped = copy.deepcopy(package)
    swapped["beats"][0]["cuts"].reverse()
    assert L.validate_beat_package_source_contract(swapped)["ok"] is False


def test_voice_pass_requires_identical_words_to_keep_distinct_occurrence_order(monkeypatch):
    _, beat, package = _source_fixture()
    occurrences = _creative_occurrences(beat)
    voices = [_voice(occurrence) for occurrence in occurrences]
    monkeypatch.setattr(C, "_script_beats", lambda *a, **k: ([beat], package))
    monkeypatch.setattr(cb_llm, "structured",
                        lambda *a, **k: C.VoiceScript(performances=voices))
    result = C.gate5_voice("Ep1", 1, None, [], log=lambda *_: None)
    assert [voice.dialogueOccurrenceId for voice in result] == [
        occurrence.dialogueOccurrenceId for occurrence in occurrences]

    reversed_ids = [_voice(occurrences[0],
                           dialogueOccurrenceId=occurrences[1].dialogueOccurrenceId),
                    _voice(occurrences[1],
                           dialogueOccurrenceId=occurrences[0].dialogueOccurrenceId)]
    monkeypatch.setattr(cb_llm, "structured",
                        lambda *a, **k: C.VoiceScript(performances=reversed_ids))
    with pytest.raises(RuntimeError, match="CHANGED/REORDERED"):
        C.gate5_voice("Ep1", 1, None, [], log=lambda *_: None)


def _state():
    return E.ContinuityState(lighting="day", cameraSide="centre", characters=[
        E.CharacterState(character="FUZZBY", screenZone="centre", facing="forward",
                         pose="hovering", expression="intent", visibleMarks=[], heldProps=[])
    ])


def _shot(shot_id, occurrence, source_type, source_shot_id=None):
    state = _state()
    return E.Shot(
        shotId=shot_id, beatCode="1.B1", durationSec=4,
        purpose="land one distinct repetition", performanceAssignment="Fuzzby leans in.",
        camera="still at eye level", openingPose="Fuzzby hovering",
        sourceType=source_type, sourceShotId=source_shot_id,
        cutInMotivation="matched lean" if source_shot_id else None,
        dialogueBinding="Fuzzby speaks with renewed insistence",
        dialogueLines=[E.DialogueLine(
            dialogueOccurrenceId=occurrence.dialogueOccurrenceId,
            sourceEventId=occurrence.sourceEventId, speaker=occurrence.speaker,
            exactText=occurrence.exactText, delivery="bright insistence",
            startSec=0.5, endSec=2.0)],
        visualPayoff="The lean settles", prohibited=[], charactersInFrame=["FUZZBY"],
        continuityIn=None if source_type == "opener" else state,
        continuityOut=state)


def test_shot_handover_and_engine_validator_preserve_duplicate_occurrences():
    _, beat, _ = _source_fixture()
    occurrences = _creative_occurrences(beat)
    voices = [_voice(occurrence).model_dump() for occurrence in occurrences]
    details = {
        "S1.SH1": {"dialogueOccurrenceIds": [occurrences[0].dialogueOccurrenceId]},
        "S1.SH2": {"dialogueOccurrenceIds": [occurrences[1].dialogueOccurrenceId]},
    }
    placement = H.place_voices_for_beat(
        "1.B1", ["S1.SH1", "S1.SH2"], voices,
        [occurrence.model_dump() for occurrence in occurrences], details)
    assert [item["dialogueOccurrenceId"] for item in placement["S1.SH1"]] == [
        occurrences[0].dialogueOccurrenceId]
    assert [item["dialogueOccurrenceId"] for item in placement["S1.SH2"]] == [
        occurrences[1].dialogueOccurrenceId]

    shots = [_shot("S1.SH1", occurrences[0], "opener"),
             _shot("S1.SH2", occurrences[1], "relay", "S1.SH1")]
    statement = E.DirectorStatement(**{key: "x" for key in E.DirectorStatement.model_fields})
    design = E.SceneShotList(statement=statement, shots=shots)
    report = E.validate_scene_design(design, [beat], {})
    assert report["passed"] is True, report["issues"]

    shots[1].dialogueLines[0].dialogueOccurrenceId = occurrences[0].dialogueOccurrenceId
    broken = E.validate_scene_design(design, [beat], {})
    codes = {issue["code"] for issue in broken["issues"]}
    assert "DIALOGUE_OCCURRENCE_DUPLICATED" in codes
    assert "DIALOGUE_OCCURRENCE_ORDER_CHANGED" in codes


def test_packed_shot_owns_dialogue_from_every_declared_beat():
    """A longer provider unit can combine adjacent script beats without making the
    later beat's locked dialogue look invented. Ownership must remain explicit."""
    _, first, _ = _source_fixture()
    second = copy.deepcopy(first)
    second["beatCode"] = "1.B2"
    second["sourceBeatId"] = "source-beat:packed-second"
    for cut in second["cuts"]:
        cut["dialogueOccurrenceId"] += ":second"
        cut["sourceEventId"] += ":second"

    first_occurrences = _creative_occurrences(first)
    second_occurrences = _creative_occurrences(second)
    state = _state()
    shot = E.Shot(
        shotId="S1.SH1", beatCode="1.B1", beatCodes=["1.B1", "1.B2"],
        durationSec=8, purpose="land both repetitions",
        performanceAssignment="Fuzzby repeats the insistence twice.",
        camera="still at eye level", openingPose="Fuzzby hovering",
        sourceType="opener", sourceShotId=None, cutInMotivation=None,
        dialogueBinding="Fuzzby owns all four locked repetitions",
        dialogueLines=[
            E.DialogueLine(
                dialogueOccurrenceId=occ.dialogueOccurrenceId,
                sourceEventId=occ.sourceEventId, speaker=occ.speaker,
                exactText=occ.exactText, delivery="bright insistence",
                startSec=index * 1.5, endSec=index * 1.5 + 1.0)
            for index, occ in enumerate(first_occurrences + second_occurrences)
        ],
        visualPayoff="Both repetitions settle", prohibited=[],
        charactersInFrame=["FUZZBY"], continuityIn=None, continuityOut=state)
    statement = E.DirectorStatement(**{
        key: "x" for key in E.DirectorStatement.model_fields})
    report = E.validate_scene_design(
        E.SceneShotList(statement=statement, shots=[shot]), [first, second], {})
    assert report["passed"] is True, report["issues"]
