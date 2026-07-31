import json

from tools.quarantine_test_evidence import quarantine


def test_quarantine_preserves_test_records_outside_live_library(tmp_path):
    library = tmp_path / "EVIDENCE_LIBRARY.json"
    library.write_text(json.dumps({
        "note": "IMMUTABLE evidence",
        "records": [
            {"evidenceId": "real", "capturedBy": "Julian", "outcome": "approved"},
            {"evidenceId": "test", "capturedBy": "TestReviewer", "outcome": "approved"},
        ],
    }))

    result = quarantine(library, tmp_path / "quarantine")
    cleaned = json.loads(library.read_text())
    archived = json.loads(next((tmp_path / "quarantine").glob("*.json")).read_text())

    assert result["removed"] == 1
    assert [record["evidenceId"] for record in cleaned["records"]] == ["real"]
    assert [record["evidenceId"] for record in archived["records"]] == ["test"]
    assert quarantine(library, tmp_path / "quarantine")["changed"] is False
