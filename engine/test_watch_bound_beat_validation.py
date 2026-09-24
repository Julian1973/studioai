import copy
import hashlib
import json

import pytest

import cb_intake
import cb_lineage
import cb_render


def test_watch_uses_signed_scene_beats_across_proven_format_cleanup(tmp_path, monkeypatch):
    old_version = "sha256:" + hashlib.sha256(b"old script").hexdigest()
    new_version = "sha256:" + hashlib.sha256(b"new layout").hexdigest()
    old_events = [dict(i=0, scene=1, type="dialogue", speaker="Hero",
                       text="Hello. The door opens.")]
    cb_intake._annotate_source_events(old_events, old_version)
    beats = cb_intake._backfill_source_occurrences([
        dict(sceneNumber=1, beatCode="S1.B1",
             cuts=[dict(dialogue="Hero: Hello. The door opens.", action=None)])
    ], old_events, old_version)
    source_script = dict(scriptVersionId=old_version, sha256=old_version[7:])
    source = dict(sourceScript=source_script, beats=beats,
                  sourceContract=cb_lineage.beat_package_source_contract(old_version, beats))
    source["contentSignature"] = cb_lineage.beat_package_signature(source)
    path = tmp_path / "cb-output" / "EpT_test_beat_package.json"
    path.parent.mkdir()
    path.write_text(json.dumps(source))
    current_path = tmp_path / "scripts" / "new.txt"
    current_path.parent.mkdir()
    current_path.write_text("Hero: Hello.\n\nThe door opens.")
    current = dict(scriptVersionId=new_version, contentPath="scripts/new.txt",
                   changeScope={"kind": "dialogue-format-cleanup"})
    new_events = [dict(i=0, scene=1, type="dialogue", speaker="Hero", text="Hello."),
                  dict(i=1, scene=1, type="action", text="The door opens.")]
    monkeypatch.setattr(cb_render, "_source_base", lambda: tmp_path)
    monkeypatch.setattr(cb_render.SCRIPT_STORE, "current", lambda *args, **kwargs: current)
    monkeypatch.setattr(cb_intake, "_load_roster", lambda: {})
    monkeypatch.setattr(cb_intake, "parse_script", lambda *args, **kwargs: {"events": copy.deepcopy(new_events)})
    scene = dict(sourceScript=source_script,
                 sourceBeatPackage={"path": "cb-output/EpT_test_beat_package.json",
                                    "contentSignature": source["contentSignature"]},
                 inputSignature={"inputs": {"beatPackageDigest": source["contentSignature"]["digest"]}})

    assert cb_render._validation_beat_package(scene, "EpT")["beats"] == beats

    new_events[0]["text"] = "Goodbye."
    with pytest.raises(cb_render.Refused, match="cleanup changed source words"):
        cb_render._validation_beat_package(scene, "EpT")
    new_events[0]["text"] = "Hello."
    scene["sourceBeatPackage"]["contentSignature"] = {"digest": "tampered"}
    with pytest.raises(cb_render.Refused, match="changed after scene approval"):
        cb_render._validation_beat_package(scene, "EpT")
