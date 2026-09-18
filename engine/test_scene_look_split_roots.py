import json
from pathlib import Path

import cb_render as render
import cb_canon


def test_scene_plate_reuse_reads_and_writes_trusted_data_root(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production"
    cwd = tmp_path / "cwd"
    (source / "engine").mkdir(parents=True)
    (data / "shows" / "crystal-bears" / "canon").mkdir(parents=True)
    (data / "shows" / "crystal-bears" / "laws").mkdir(parents=True)
    (data / "engine" / "media").mkdir(parents=True)
    (data / "cb-output").mkdir()
    cwd.mkdir()

    json.dump({"Ep4": {"3": {"look": "A clearing", "lighting": "Late light"}}},
              (data / "shows" / "crystal-bears" / "canon" / "locations.json").open("w"))
    (data / "shows" / "crystal-bears" / "laws" / "style.txt").write_text("Crystal Bears style")
    approved = data / "engine" / "media" / "Ep4_S3_plate.png"
    approved.write_bytes(b"approved scene plate")

    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    monkeypatch.setattr(render, "HERE", source / "engine")
    monkeypatch.setattr(render, "load_pkg", lambda *args: (
        {"validation": {"passed": True}, "revision": "fixture"}, source / "package.json"))
    monkeypatch.setattr(render, "_require_show_adapter", lambda: None)
    monkeypatch.setattr(render, "_require_valid", lambda package: None)
    monkeypatch.setattr(render, "_require_current_lineage", lambda *args: None)
    render._save_scenelook_rec({
        "approved": {"path": str(approved), "hash": render._sha256_file(approved),
                      "inputSignature": {"briefHash": "approved-brief"},
                      "packageRevision": 7},
        "candidate": None, "history": []}, "3", "Ep4")
    monkeypatch.setattr(cb_canon, "require_locked", lambda *args, **kwargs: {})
    monkeypatch.chdir(cwd)

    candidate = render.select_scenelook_source(
        "3", "library", "Ep4", library_path=str(approved), log=lambda *args: None)

    assert Path(candidate).is_relative_to(data / "engine" / "media")
    assert not Path(candidate).is_relative_to(source)
    assert render._scenelook_path("3", "Ep4").is_relative_to(data / "cb-output")
    record = json.loads(render._scenelook_path("3", "Ep4").read_text())
    assert record["candidate"]["path"] == candidate
    assert record["candidate"]["inputSignature"] == {"briefHash": "approved-brief"}
