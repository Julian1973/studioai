import json

import cb_lineage
from cb_scripts import ScriptStore, ScriptStoreError


def test_dependency_signature_is_stable_and_explainable():
    left = cb_lineage.dependency_signature("shot", {"b": [2, 3], "a": 1})
    right = cb_lineage.dependency_signature("shot", {"a": 1, "b": [2, 3]})

    assert left == right
    assert left["inputs"] == {"a": 1, "b": [2, 3]}
    assert cb_lineage.signature_matches(left, "shot", {"b": [2, 3], "a": 1})
    assert not cb_lineage.signature_matches(left, "shot", {"a": 2, "b": [2, 3]})


def test_script_store_preserves_old_versions_and_moves_only_pointer(tmp_path):
    store = ScriptStore(tmp_path)
    first = store.store("Ep1", "INT. ROOM 1\nFirst draft\n", "Pilot", activated_at="2026-01-01T00:00:00+00:00")
    second = store.store("Ep1", "INT. ROOM 1\nSecond draft\n", "Pilot", activated_at="2026-01-02T00:00:00+00:00")

    assert first["scriptVersionId"] != second["scriptVersionId"]
    assert (tmp_path / first["contentPath"]).read_text() == "INT. ROOM 1\nFirst draft\n"
    assert (tmp_path / second["contentPath"]).read_text() == "INT. ROOM 1\nSecond draft\n"
    assert store.current("Ep1")["scriptVersionId"] == second["scriptVersionId"]
    assert second["previousScriptVersionId"] == first["scriptVersionId"]
    assert len(list((store.events_root / "Ep1").glob("*.json"))) == 2


def test_script_store_deduplicates_identical_bytes_without_losing_history(tmp_path):
    store = ScriptStore(tmp_path)
    first = store.store("Ep2", "same bytes\n", "Old title", activated_at="2026-01-01T00:00:00+00:00")
    second = store.store("Ep2", "same bytes\n", "New title", activated_at="2026-01-02T00:00:00+00:00")

    assert first["scriptVersionId"] == second["scriptVersionId"]
    assert len(list((store.versions_root / "Ep2").glob("*.txt"))) == 1
    assert second["title"] == "New title"
    assert len(list((store.events_root / "Ep2").glob("*.json"))) == 2


def test_script_store_detects_content_tampering(tmp_path):
    store = ScriptStore(tmp_path)
    current = store.store("Ep3", "locked\n", "Locked", activated_at="2026-01-01T00:00:00+00:00")
    (tmp_path / current["contentPath"]).write_text("tampered\n")

    try:
        store.current("Ep3")
    except ScriptStoreError as exc:
        assert "failed SHA-256 verification" in str(exc)
    else:
        raise AssertionError("tampered immutable script was accepted")


def test_beat_package_signature_ignores_mutable_approval_metadata():
    base = {"title": "Pilot", "episode": 1, "logline": "x", "leadBear": "Keen",
            "format": "11-min", "unit": "beat", "beats": [{"beatCode": "B1"}]}
    with_approval = json.loads(json.dumps(base))
    with_approval["approval"] = {"reviewedBy": "Julian"}

    assert cb_lineage.beat_package_signature(base) == cb_lineage.beat_package_signature(with_approval)
