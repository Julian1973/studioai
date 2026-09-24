import json

import pytest

import cb_studio_director as director


def _fixture(tmp_path, *, board_shots=None, package_shots=None, approval="approved"):
    board_shots = board_shots if board_shots is not None else ["S3.SH1"]
    package_shots = package_shots if package_shots is not None else ["S3.SH1"]
    path = tmp_path / "EpT_scene3_storyboard.json"
    path.write_text(json.dumps({
        "approvalState": approval,
        "shots": [{"shotId": shot} for shot in board_shots],
    }), encoding="utf-8")
    package = {"shots": [{"shotId": shot, "dialogueLines": []}
                          for shot in package_shots]}
    return path, package


def test_watch_source_integrity_accepts_matching_approved_pack(monkeypatch, tmp_path):
    path, package = _fixture(tmp_path)
    monkeypatch.setattr("cb_render._declared_storyboard_path", lambda *args: path)
    monkeypatch.setattr("cb_departments.provider_dialogue_lines", lambda shot: [])

    report = director._require_watch_source_integrity(package, "3", "S3.SH1", "EpT")

    assert report["current"] is True
    assert report["zeroSpend"] is True


@pytest.mark.parametrize("kwargs,expected", [
    ({"board_shots": ["S3.SH1", "S3.SH2"]}, "different shot rosters"),
    ({"approval": "generated-pending-human-review"}, "not currently approved"),
    ({"package_shots": ["S3.SH2"]}, "not present in the production package"),
])
def test_watch_source_integrity_reports_one_actionable_graph_error(
        monkeypatch, tmp_path, kwargs, expected):
    path, package = _fixture(tmp_path, **kwargs)
    monkeypatch.setattr("cb_render._declared_storyboard_path", lambda *args: path)
    monkeypatch.setattr("cb_departments.provider_dialogue_lines", lambda shot: [])

    with pytest.raises(Exception, match="WATCH_SOURCE_PACKAGE_MISMATCH") as exc:
        director._require_watch_source_integrity(package, "3", "S3.SH1", "EpT")

    assert expected in str(exc.value)


def test_watch_source_integrity_normalises_segmentation_failure(monkeypatch, tmp_path):
    path, package = _fixture(tmp_path)
    monkeypatch.setattr("cb_render._declared_storyboard_path", lambda *args: path)
    monkeypatch.setattr(
        "cb_departments.provider_dialogue_lines",
        lambda shot: (_ for _ in ()).throw(
            ValueError("SOURCE_DIALOGUE_SEGMENTATION_UNRESOLVED: source payload changed")),
    )

    with pytest.raises(Exception, match="approved dialogue provenance"):
        director._require_watch_source_integrity(package, "3", "S3.SH1", "EpT")
