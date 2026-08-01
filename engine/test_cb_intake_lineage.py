import hashlib
import json

import pytest

import cb_intake
import cb_lineage
from cb_scripts import ScriptStore

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
        tmp_path, script_root=tmp_path / "shows/crystal-bears/episodes/scripts")
    current = store.store("Ep1", text, "Pilot", activated_at="2026-01-01T00:00:00+00:00")
    episodes = tmp_path / "cb-studio" / "data" / "episodes.json"
    episodes.parent.mkdir(parents=True, exist_ok=True)
    episodes.write_text(json.dumps([{
        "number": 1,
        "title": "Pilot",
        "script": current["displayFile"],
        "scriptVersionId": current["scriptVersionId"],
    }]))
    out = tmp_path / "cb-output"
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
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(first)))

    second = store.store("Ep1", SCRIPT_TWO, "Pilot",
                         activated_at="2026-01-02T00:00:00+00:00")
    registry = json.loads(episodes.read_text())
    registry[0].update({"script": second["displayFile"],
                        "scriptVersionId": second["scriptVersionId"]})
    episodes.write_text(json.dumps(registry))

    with pytest.raises(cb_intake.Refused, match="run Story & Direction again"):
        cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)

    assert not list((tmp_path / "cb-output").glob("Ep1_*beat_package.json"))


def test_intake_approval_persists_script_and_package_signatures(tmp_path, monkeypatch):
    _, current, _ = _workspace(tmp_path, monkeypatch)
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(current)))

    result = cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)
    pkg = json.loads((tmp_path / result["canonicalPackage"]).read_text())
    vision = json.loads((tmp_path / result["episodeVision"]).read_text())

    assert pkg["sourceScript"]["scriptVersionId"] == current["scriptVersionId"]
    assert pkg["contentSignature"] == cb_lineage.beat_package_signature(pkg)
    expected_inputs = cb_lineage.episode_vision_inputs(
        current["scriptVersionId"], pkg["contentSignature"], CANON_DIGEST)
    assert cb_lineage.signature_matches(
        vision["inputSignature"], "episode-vision", expected_inputs)


def test_new_script_approval_archives_previous_canonical_package(tmp_path, monkeypatch):
    store, first, episodes = _workspace(tmp_path, monkeypatch)
    old = tmp_path / "cb-output" / "Ep1_Old_beat_package.json"
    old.write_text(json.dumps({"episode": 1, "title": "Old", "beats": [],
                               "sourceScript": cb_intake._script_ref(first)}))

    second = store.store("Ep1", SCRIPT_TWO, "Pilot",
                         activated_at="2026-01-02T00:00:00+00:00")
    registry = json.loads(episodes.read_text())
    registry[0].update({"script": second["displayFile"],
                        "scriptVersionId": second["scriptVersionId"]})
    episodes.write_text(json.dumps(registry))
    cb_intake.candidate_path("Ep1").write_text(json.dumps(_candidate(second, SCRIPT_TWO)))

    cb_intake.decide_intake("Ep1", "approve", log=lambda *_: None)

    assert not old.exists()
    archived = list((tmp_path / "cb-output" / "archive" / "script_versions").glob("*.json"))
    assert len(archived) == 1
    assert json.loads(archived[0].read_text())["sourceScript"]["scriptVersionId"] == first["scriptVersionId"]


def test_scene_roster_ignores_a_stale_legacy_package(tmp_path, monkeypatch):
    _, current, _ = _workspace(tmp_path, monkeypatch)
    legacy = tmp_path / "cb-output" / "Ep1_Legacy_beat_package.json"
    legacy.write_text(json.dumps({
        "episode": 1,
        "title": "Legacy",
        "sourceScript": cb_intake._script_ref(current),
        "beats": [{"sceneNumber": 1, "beatCode": "1.B1", "cuts": []}],
    }))

    roster = cb_intake.scene_roster("Ep1")

    assert roster["hasPackage"] is False
    assert roster["scenes"] == []
    assert roster["reason"] == "canonical-beat-package-stale"


def test_legacy_lineage_cannot_manufacture_canon_provenance():
    with pytest.raises(cb_intake.Refused, match="cannot be retroactively signed"):
        cb_intake.migrate_legacy_lineage("Ep1", dry_run=True, log=lambda *_: None)
