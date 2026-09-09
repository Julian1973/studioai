import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import export_episode_post_inputs as exporter


def test_export_uses_approved_ledger_entries_only(tmp_path, monkeypatch):
    root = tmp_path / "project"
    packages = root / "cb-output"
    media = root / "engine" / "media" / "post95"
    packages.mkdir(parents=True)
    source = tmp_path / "source"
    source.mkdir()
    approved_render = source / "approved.mp4"
    approved_frame = source / "approved.png"
    approved_voice = source / "approved.wav"
    for path in (approved_render, approved_frame, approved_voice):
        path.write_bytes(path.name.encode())

    package = {
        "episode": "EpT",
        "shots": [{"shotId": "S1.SH1", "dialogueLines": []}],
        "continuityLedger": [
            {
                "shotId": "S1.SH1",
                "status": "approved",
                "approvedTake": str(approved_render),
                "harvestFrame": str(approved_frame),
                "voiceApproval": {"path": str(approved_voice)},
            },
            {"shotId": "S1.SH2", "status": "superseded", "approvedTake": None},
        ],
    }
    (packages / "EpT_scene1_production_package.json").write_text(
        json.dumps(package), encoding="utf-8"
    )
    monkeypatch.setattr(exporter, "ROOT", root)
    monkeypatch.setattr(exporter, "PACKAGE_DIR", packages)
    monkeypatch.setattr(exporter, "MEDIA_DIR", root / "engine" / "media")

    manifest_path = exporter.export_episode("EpT")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [shot["id"] for shot in manifest["shots"]] == ["S1.SH1"]
    assert (manifest_path.parent / "renders" / "S1_SH1.mp4").read_bytes() == b"approved.mp4"
    assert (manifest_path.parent / "voice" / "S1_SH1.wav").exists()
    assert manifest['title']=='Crystal Bears EpT'
    assert manifest['shots'][0]['directionContext']==package['shots'][0]
    assert 'not proof' in manifest['shots'][0]['directionEvidence']
    assert manifest['shots'][0]['sourcePackageSha256']==exporter.sha256(packages/'EpT_scene1_production_package.json')


def test_approved_hash_and_numeric_shot_order(tmp_path,monkeypatch):
    import pytest
    monkeypatch.setattr(exporter,'PACKAGE_DIR',tmp_path)
    take=tmp_path/'render.mp4';take.write_bytes(b'approved')
    ledgers=[dict(shotId=sid,status='approved',approvedTake=str(take),approval={'contentHash':exporter.sha256(take)})
             for sid in ('S1.SH10','S1.SH2','S1.SH1')]
    package=tmp_path/'EpT_scene1_production_package.json'
    package.write_text(json.dumps({'shots':[],'continuityLedger':ledgers}))
    assert [s['shotId'] for s in exporter._approved_shots('EpT',[1])]==['S1.SH1','S1.SH2','S1.SH10']
    take.write_bytes(b'changed')
    with pytest.raises(exporter.ExportError,match='changed after approval'):
        exporter._approved_shots('EpT',[1])
