import hashlib
import json
import pathlib

import pytest

import cb_intake
import cb_lineage
from cb_scripts import ScriptStore
import paths as P  # T45: scratch worlds use the project layout

SCRIPT_ONE = "INT. CRYSTAL COVE - DAY 1\n\nKEEN\nHello.\n"
SCRIPT_TWO = "INT. CRYSTAL COVE - DAY 1\n\nKEEN\nHello again.\n"
CANON_DIGEST = "c" * 64


def _canon_status(episode="Ep1", cast=None, root=None):
    return {
        "current": True, "episodeReady": True,
        "manifestDigest": "m" * 64,
        "profileDigests": {"story": CANON_DIGEST, "storyboard": "d" * 64},
        "blockers": [], "episodeBlockers": [], "warnings": [],
    }


def _workspace(tmp_path, monkeypatch, text=SCRIPT_ONE):
    store = ScriptStore(
        tmp_path, script_root=tmp_path / "projects/crystal-bears/episodes/scripts")
    current = store.store("Ep1", text, "Pilot", activated_at="2026-01-01T00:00:00+00:00")
    episodes = tmp_path / P.EPISODES_INDEX_REL
    episodes.parent.mkdir(parents=True, exist_ok=True)
    episodes.write_text(json.dumps([{
        "number": 1,
        "title": "Pilot",
        "script": current["displayFile"],
        "scriptVersionId": current["scriptVersionId"],
    }]), encoding="utf-8")
    out = tmp_path / P.OUTPUT_REL
    creative = out / "creative"
    creative.mkdir(parents=True)
    monkeypatch.setattr(cb_intake, "ROOT", tmp_path)
    monkeypatch.setattr(cb_intake, "OUT", out)
    monkeypatch.setattr(cb_intake, "CREATIVE_OUT", creative)
    monkeypatch.setattr(cb_intake, "EPISODES_JSON", episodes)
    monkeypatch.setattr(cb_intake, "SCRIPTS", store.script_root)
    monkeypatch.setattr(cb_intake, "STUDIO_SCRIPTS", store.studio_root)
    monkeypatch.setattr(cb_intake, "SCRIPT_STORE", store)
    monkeypatch.setattr(cb_intake, "ARCHIVE_DIR", out / "archive" / "story_intake_rejected")
    monkeypatch.setattr(cb_intake.cb_canon, "status", _canon_status)
    monkeypatch.setattr(cb_intake.cb_canon, "require_locked", _canon_status)
    monkeypatch.setattr(cb_intake.cb_canon, "source_hashes",
                        lambda profile, root=None: {"showBible": "a" * 64})
    return store, current, episodes


def _candidate(current, text=SCRIPT_ONE):
    parsed = cb_intake.parse_script(text, log=lambda *_: None)
    cb_intake._annotate_source_events(parsed["events"], current["scriptVersionId"])
    cuts = cb_intake._build_cuts(parsed["events"], 0, len(parsed["events"]) - 1)
    signature = cb_lineage.source_beat_event_signature(
        current["scriptVersionId"], parsed["events"])
    records = signature["inputs"]["orderedEvents"]
    beat = {"sceneNumber": 1, "beatCode": "S01-B01",
            "sourceBeatId": cb_lineage.source_beat_id(signature),
            "sourceEventRange": {"firstEventIndex": 0,
                "lastEventIndex": len(records) - 1,
                "firstEventId": records[0]["sourceEventId"],
                "lastEventId": records[-1]["sourceEventId"],
                "eventCount": len(records)},
            "sourceEventIds": [record["sourceEventId"] for record in records],
            "dialogueOccurrenceIds": [record["dialogueOccurrenceId"] for record in records
                                        if record["sourceType"] == "dialogue"],
            "sourceEventSignature": signature, "cuts": cuts}
    candidate = {
        "episode": "Ep1",
        "title": "Pilot",
        "logline": "A beginning.",
        "leadBear": "Keen",
        "scriptVersionId": current["scriptVersionId"],
        "scriptMd5": hashlib.md5(text.encode()).hexdigest(),
        "episodeVision": {"theme": "belonging"},
        "beats": [beat],
        "approvalState": "awaiting-human-approval",
    }
    candidate["inputSignature"] = cb_lineage.dependency_signature(
        "story-intake", {"scriptVersionId": current["scriptVersionId"],
                         "canonProfileDigest": CANON_DIGEST})
    candidate["sourceContract"] = cb_lineage.beat_package_source_contract(
        current["scriptVersionId"], candidate["beats"])
    return candidate


def test_intake_approval_refuses_candidate_from_previous_script(tmp_path, monkeypatch):
    store, first, episodes = _workspace(tmp_path, monkeypatch)
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(first)), encoding="utf-8")

    second = store.store("Ep1", SCRIPT_TWO, "Pilot",
                         activated_at="2026-01-02T00:00:00+00:00")
    registry = json.loads(episodes.read_text(encoding="utf-8"))
    registry[0].update({"script": second["displayFile"],
                        "scriptVersionId": second["scriptVersionId"]})
    episodes.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(cb_intake.Refused, match="run Story & Direction again"):
        cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)

    assert not list((tmp_path / P.OUTPUT_REL).glob("Ep1_*beat_package.json"))


def test_failed_replacement_keeps_the_previous_candidate(tmp_path, monkeypatch):
    store, first, episodes = _workspace(tmp_path, monkeypatch)
    candidate_path = cb_intake.candidate_path("Ep1")
    previous = _candidate(first)
    candidate_path.write_text(json.dumps(previous), encoding="utf-8")

    second = store.store("Ep1", SCRIPT_TWO, "Pilot",
                         activated_at="2026-01-02T00:00:00+00:00")
    registry = json.loads(episodes.read_text(encoding="utf-8"))
    registry[0].update({"script": second["displayFile"],
                        "scriptVersionId": second["scriptVersionId"]})
    episodes.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setattr(
        cb_intake.cb_canon, "story_context",
        lambda cast, episode, root=None: {"sourceHashes": {"showBible": "a" * 64}},
    )

    def fail_director(*_args, **_kwargs):
        raise RuntimeError("Director unavailable")

    monkeypatch.setattr(cb_intake.cb_departments, "prepare_story", fail_director)

    with pytest.raises(RuntimeError, match="Director unavailable"):
        cb_intake.prepare_intake("Ep1", log=lambda *_: None)

    assert json.loads(candidate_path.read_text(encoding="utf-8")) == previous
    superseded = tmp_path / P.OUTPUT_REL / "archive" / "story_intake_superseded"
    assert not superseded.exists()


def test_intake_approval_persists_script_and_package_signatures(tmp_path, monkeypatch):
    _, current, _ = _workspace(tmp_path, monkeypatch)
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(current)), encoding="utf-8")

    result = cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)
    pkg = json.loads((tmp_path / result["canonicalPackage"]).read_text(encoding="utf-8"))
    vision = json.loads((tmp_path / result["episodeVision"]).read_text(encoding="utf-8"))

    assert pkg["sourceScript"]["scriptVersionId"] == current["scriptVersionId"]
    assert pkg["contentSignature"] == cb_lineage.beat_package_signature(pkg)
    expected_inputs = cb_lineage.episode_vision_inputs(
        current["scriptVersionId"], pkg["contentSignature"], CANON_DIGEST)
    assert cb_lineage.signature_matches(
        vision["inputSignature"], "episode-vision", expected_inputs)
    assert vision["directionVersion"] == "accepted-episode-direction-v1"
    assert cb_lineage.signature_matches(
        vision["directionSignature"], "accepted-episode-direction",
        vision["directionSignature"]["inputs"])
    assert vision["productionLineage"] == [
        "Story Director", "Screenwriter", "Cinematic Shot Director",
        "Seedream Keyframes", "Seedance Production Director", "Editor",
    ]
    status = cb_intake.intake_status("Ep1")
    assert status["candidateCurrent"] is True
    assert status["canonicalCurrent"] is True
    assert status["candidate"]["approvalState"] == "approved"
    # pathlib, not rsplit("/"): the recorded path uses the platform separator, so on Windows
    # the forward-slash split returned the whole path and never the file name.
    assert status["candidate"]["approval"]["canonicalPackage"] == (
        pathlib.PurePath(result["canonicalPackage"]).name
    )


def test_episode_two_production_script_has_eight_scenes_and_59_exact_dialogue_lines():
    script_path = cb_intake.ROOT / "cb-studio/data/scripts/Ep2_Bos_Big_Day_V2.txt"
    parsed = cb_intake.parse_script(
        script_path.read_text(encoding="utf-8"), cb_intake._load_roster(),
        log=lambda *_: None)
    dialogue = [event for event in parsed["events"] if event["type"] == "dialogue"]
    assert len(parsed["scenes"]) == 8
    assert len(dialogue) == 59
    mum_lines = [event for event in dialogue if event["speaker"] == "Bo's Mum"]
    assert [event["text"] for event in mum_lines] == [
        "BO, it’s time for you to go to the Learning Circle? Don’t forget your lunch."
    ]
    assert all(event["text"] for event in dialogue)


def test_parser_keeps_shared_cue_and_following_action_out_of_dialogue():
    script = """EXT. FOREST PATH - DAY 4

BO/KEEN
3, 2, 1 …

POOF! The tail does The Thing again.

BO
3,2,1 …
POOF! The tail does The Thing again. Bo giggles.

AIDA
Every single time.
BEAT.
"""
    parsed = cb_intake.parse_script(
        script, roster=["Bo", "Keen", "Aida"], log=lambda *_: None)
    dialogue = [event for event in parsed["events"] if event["type"] == "dialogue"]
    action = [event["text"] for event in parsed["events"] if event["type"] == "action"]

    assert dialogue == [
        {"i": 0, "scene": 4, "type": "dialogue", "speaker": "Bo/Keen",
         "text": "3, 2, 1 …", "voiceTreatment": "group_chorus",
         "chorusMembers": ["Bo", "Keen"]},
        {"i": 2, "scene": 4, "type": "dialogue", "speaker": "Bo",
         "text": "3,2,1 …"},
        {"i": 4, "scene": 4, "type": "dialogue", "speaker": "Aida",
         "text": "Every single time."},
    ]
    assert action == [
        "POOF! The tail does The Thing again.",
        "POOF! The tail does The Thing again. Bo giggles.",
        "BEAT.",
    ]


def test_outcome_compression_plan_groups_beats_by_scene():
    beats = [
        {"sceneNumber": 1, "beatCode": "1.B1", "storyBeat": "Keen meets Fuzzby.",
         "sourceEventIds": ["a"]},
        {"sceneNumber": 1, "beatCode": "1.B2", "storyBeat": "The joke lands.",
         "sourceEventIds": ["b"]},
        {"sceneNumber": 2, "beatCode": "2.B1", "storyBeat": "A new location.",
         "sourceEventIds": ["c"]},
    ]

    plan = cb_intake.build_outcome_compression_plan(beats)

    assert [item["productionShotId"] for item in plan] == ["1.S1", "2.S1"]
    assert plan[0]["sourceBeatCodes"] == ["1.B1", "1.B2"]
    assert plan[0]["targetDurationSec"] == 30
    assert plan[1]["targetDurationSec"] == 24
    assert plan[0]["seeStageContract"]["blockWatchIf"]


def test_new_script_approval_archives_previous_canonical_package(tmp_path, monkeypatch):
    store, first, episodes = _workspace(tmp_path, monkeypatch)
    old = tmp_path / P.OUTPUT_REL / "Ep1_Old_beat_package.json"
    old.write_text(json.dumps({"episode": 1, "title": "Old", "beats": [],
                               "sourceScript": cb_intake._script_ref(first)}), encoding="utf-8")

    second = store.store("Ep1", SCRIPT_TWO, "Pilot",
                         activated_at="2026-01-02T00:00:00+00:00")
    registry = json.loads(episodes.read_text(encoding="utf-8"))
    registry[0].update({"script": second["displayFile"],
                        "scriptVersionId": second["scriptVersionId"]})
    episodes.write_text(json.dumps(registry), encoding="utf-8")
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(second, SCRIPT_TWO)), encoding="utf-8")

    cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)

    assert not old.exists()
    archived = list((tmp_path / P.OUTPUT_REL / "archive" / "script_versions").glob("*.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text(encoding="utf-8"))["sourceScript"]["scriptVersionId"] == first["scriptVersionId"]


def test_canon_rebase_preserves_approved_creative_content(tmp_path, monkeypatch):
    _, current, _ = _workspace(tmp_path, monkeypatch)
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(current)), encoding="utf-8")
    approved = cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)
    package_path = tmp_path / approved["canonicalPackage"]
    before = json.loads(package_path.read_text(encoding="utf-8"))

    new_digest = "n" * 64
    monkeypatch.setattr(cb_intake.cb_canon, "status", lambda *args, **kwargs: {
        **_canon_status(), "profileDigests": {"story": new_digest, "storyboard": "d" * 64}})
    monkeypatch.setattr(cb_intake.cb_canon, "require_locked", lambda *args, **kwargs: {
        **_canon_status(), "profileDigests": {"story": new_digest, "storyboard": "d" * 64}})
    monkeypatch.setattr(cb_intake.cb_canon, "source_hashes",
                        lambda profile, root=None: {"showBible": "b" * 64})

    result = cb_intake.rebase_canon_lock("Ep1", reviewed_by="Julian", log=lambda *_: None)
    after = json.loads(package_path.read_text(encoding="utf-8"))

    assert result["outcome"] == "rebased"
    assert after["beats"] == before["beats"]
    assert after["contentSignature"] == before["contentSignature"]
    assert after["canonLock"]["profileDigest"] == new_digest
    assert cb_intake.intake_status("Ep1")["canonicalCurrent"] is True
    assert len(list((tmp_path / P.OUTPUT_REL / "archive/canon_rebases").glob("*.json"))) == 1


def test_scene_roster_ignores_a_stale_legacy_package(tmp_path, monkeypatch):
    _, current, _ = _workspace(tmp_path, monkeypatch)
    legacy = tmp_path / P.OUTPUT_REL / "Ep1_Legacy_beat_package.json"
    legacy.write_text(json.dumps({
        "episode": 1,
        "title": "Legacy",
        "sourceScript": cb_intake._script_ref(current),
        "beats": [{"sceneNumber": 1, "beatCode": "1.B1", "cuts": []}],
    }), encoding="utf-8")

    roster = cb_intake.scene_roster("Ep1")

    assert roster["hasPackage"] is False
    assert roster["scenes"] == []
    assert roster["reason"] == "canonical-beat-package-stale"


def test_scene_source_digest_changes_only_the_edited_scene():
    before = (
        "INT. CRYSTAL COVE - DAY 1\n\nKEEN\nHello.\n\n"
        "EXT. HOLLOW OAK - DAY 2\n\nBO\nReady.\n")
    after = before.replace("Ready.", "Really ready.")

    old = cb_intake.scene_source_digests(before, roster=["Keen", "Bo"])
    new = cb_intake.scene_source_digests(after, roster=["Keen", "Bo"])

    assert old["1"] == new["1"]
    assert old["2"] != new["2"]


def test_package_scene_roster_keeps_scenes_without_production_packages():
    package = {"beats": [
        {"sceneNumber": 1, "beatCode": "1.B1", "location": "COVE", "time": "DAY"},
        {"sceneNumber": 2, "beatCode": "2.B1", "location": "OAK", "time": "DAY"},
    ]}

    roster = cb_intake._package_scene_roster(package, [{
        "sceneNumber": "1", "shotCount": 3, "package": "scene1.json"}])

    assert [scene["sceneNumber"] for scene in roster] == ["1", "2"]
    assert roster[0]["shotCount"] == 3
    assert roster[1]["shotCount"] == 0
    assert roster[1]["reason"] == "last-approved-story-direction"


def test_legacy_lineage_cannot_manufacture_canon_provenance():
    with pytest.raises(cb_intake.Refused, match="cannot be retroactively signed"):
        cb_intake.migrate_legacy_lineage("Ep1", dry_run=True, log=lambda *_: None)
