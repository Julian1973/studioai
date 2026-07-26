#!/usr/bin/env python3
"""test_scenelook_race.py — THE LOST PLATE (2026-07-26).

Julian picked a plate from the library and it did not appear. The pick had genuinely
worked — the file was copied and the job logged "SCENE LOOK SELECTED". Two seconds later
it was gone.

Real job timings, from the running studio:
    department:look             21:01:00 -> 21:01:13
    select-scenelook-library    21:01:11 -> 21:01:11

The Look department loads the scene-look record, makes an LLM call lasting seconds, then
writes the WHOLE in-memory copy back. Anything that touched the same file during that
window is erased by a write that never intended to touch it. No error, no warning — the
losing write succeeded and was simply undone.

This pins the fix: the department save owns exactly one key and must graft it onto a
fresh read, never overwrite keys it did not author.
"""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_render


def test_a_concurrent_plate_pick_survives_the_look_department_save(tmp_path, monkeypatch):
    rec_path = tmp_path / "Ep1_scenelook_scene99.json"
    monkeypatch.setattr(cb_render, "_scenelook_path", lambda s, e="Ep1": rec_path)

    # 1. the Look department opens the record and starts its (slow) LLM call
    work, save = cb_render._department_container({}, "99", None, "look", "Ep1")
    work["candidate"] = {"department": "Look Development", "preparedAt": "21:01:00"}

    # 2. MEANWHILE Julian picks a plate from the library — a separate process, its own
    #    load/save, complete in milliseconds
    mid = cb_render._load_scenelook_rec("99", "Ep1")
    mid["candidate"] = {"path": "Ep1_S99_plate_candidate_abc.png", "source": "library"}
    cb_render._save_scenelook_rec(mid, "99", "Ep1")

    # 3. the department's LLM call returns and it saves — the moment the plate used to die
    save()

    after = json.loads(rec_path.read_text())
    assert after.get("candidate"), (
        "the library plate pick was erased by the Look department's own save — this is the "
        "exact defect Julian hit: the pick succeeded, logged success, and vanished")
    assert after["candidate"]["source"] == "library"
    # and the department's own work must still be there — the fix must not trade one loss
    # for the other
    assert after["departmentWork"]["look"]["candidate"]["preparedAt"] == "21:01:00"


def test_the_save_only_ever_writes_its_own_key(tmp_path, monkeypatch):
    """Defence in depth: whatever else lands in the record — an approval, a rejection,
    history — a department save must leave it alone. Anything it does not author, it does
    not own."""
    rec_path = tmp_path / "Ep1_scenelook_scene98.json"
    monkeypatch.setattr(cb_render, "_scenelook_path", lambda s, e="Ep1": rec_path)

    work, save = cb_render._department_container({}, "98", None, "look", "Ep1")
    work["candidate"] = {"preparedAt": "t0"}

    mid = cb_render._load_scenelook_rec("98", "Ep1")
    mid["approved"] = {"path": "approved.png"}
    mid["history"] = [{"note": "an earlier decision"}]
    cb_render._save_scenelook_rec(mid, "98", "Ep1")

    save()
    after = json.loads(rec_path.read_text())
    assert after["approved"]["path"] == "approved.png"
    assert len(after["history"]) == 1
    assert after["departmentWork"]["look"]["candidate"]["preparedAt"] == "t0"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
