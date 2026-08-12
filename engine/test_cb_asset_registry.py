import json
import pathlib

import pytest

import cb_asset_registry as A


def _tmp_registry(monkeypatch, tmp_path):
    media = tmp_path / "media"
    assets = tmp_path / "assets"
    media.mkdir()
    assets.mkdir()
    monkeypatch.setattr(A, "MEDIA", media.resolve())
    monkeypatch.setattr(A, "ASSET_ROOT", assets.resolve())
    monkeypatch.setattr(A, "PROJECTS_ROOT", (tmp_path / "projects").resolve())
    monkeypatch.setattr(A, "DISPLAY_ROOTS", (
        (media.resolve(), "/engine/media/"),
        (assets.resolve(), "/cb-seed/assets/"),
    ))
    monkeypatch.setattr(A, "REGISTRY_DIR", tmp_path / "registry")
    monkeypatch.setattr(A, "REGISTRY_PATH", tmp_path / "registry" / "assets.json")
    monkeypatch.setattr(A, "MANAGED_DIR", media / "asset-registry")
    return media, assets


def test_registration_fails_loudly_when_asset_cannot_display(monkeypatch, tmp_path):
    _tmp_registry(monkeypatch, tmp_path)
    external = tmp_path / "external.png"
    external.write_bytes(b"fake")

    with pytest.raises(A.AssetBindingError, match="not displayable"):
        A.register_asset(
            episode="Ep1",
            scene="3",
            shot_id="3.B1.S1",
            kind="opening_plate",
            role="scene_opening_plate",
            path=external,
        )


def test_scene_library_returns_opening_plate_without_package(monkeypatch, tmp_path):
    media, _ = _tmp_registry(monkeypatch, tmp_path)
    plate = media / "scene3_pier.png"
    plate.write_bytes(b"fake")
    rec = A.register_asset(
        episode="Ep1",
        scene="3",
        kind="opening_plate",
        role="scene_opening_plate",
        path=plate,
        label="Scene 3 pier opening plate",
    )

    items = A.library_for_scene("Ep1", "3")

    assert [item["assetId"] for item in items] == [rec["assetId"]]
    assert items[0]["url"] == "/engine/media/scene3_pier.png"
    stored = json.loads((tmp_path / "registry" / "assets.json").read_text())
    assert stored["assets"][0]["bindingKey"] == "Ep1|3||opening_plate|scene_opening_plate"


def test_remove_asset_unbinds_registry_record_without_deleting_file(monkeypatch, tmp_path):
    media, _ = _tmp_registry(monkeypatch, tmp_path)
    plate = media / "uploaded_prop.png"
    plate.write_bytes(b"fake")
    rec = A.register_asset(
        episode="Ep1",
        scene="3",
        kind="reference_image",
        role="uploaded_props_wristband",
        path=plate,
        label="Keen wristbands vacant no crystals",
        source="studio-upload",
        metadata={"libraryGroup": "props"},
    )

    result = A.remove_asset(rec["assetId"])

    assert result["assetCount"] == 0
    assert plate.exists()
    stored = json.loads((tmp_path / "registry" / "assets.json").read_text())
    assert stored["assets"] == []
    assert stored["deletedBindingKeys"] == ["Ep1|3||reference_image|uploaded_props_wristband"]


def test_deleted_binding_key_blocks_auto_recreation(monkeypatch, tmp_path):
    media, _ = _tmp_registry(monkeypatch, tmp_path)
    plate = media / "scene_plate.png"
    plate.write_bytes(b"fake")
    rec = A.register_asset(
        episode="Ep1",
        scene="3",
        kind="scene_plate",
        role="scene_plate_approved",
        path=plate,
        label="Scene 3 plate",
    )

    A.remove_asset(rec["assetId"])

    with pytest.raises(A.AssetBindingError, match="was deleted"):
        A.register_asset(
            episode="Ep1",
            scene="3",
            kind="scene_plate",
            role="scene_plate_approved",
            path=plate,
            label="Scene 3 plate",
        )


def test_update_asset_rebinds_image_and_metadata(monkeypatch, tmp_path):
    media, _ = _tmp_registry(monkeypatch, tmp_path)
    old = media / "old.png"
    new = media / "new.png"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    rec = A.register_asset(
        episode="Ep1",
        scene="3",
        kind="scene_plate",
        role="scene_plate_approved",
        path=old,
        label="Old plate",
    )

    updated = A.update_asset(
        rec["assetId"],
        label="New plate",
        scene="4",
        role="scene_plate_replacement",
        path=new,
        metadata={"libraryGroup": "scenes", "assetUse": "scene_plate"},
    )

    assert updated["assetId"] != rec["assetId"]
    assert updated["label"] == "New plate"
    assert updated["scene"] == "4"
    assert updated["url"] == "/engine/media/new.png"
    assert updated["metadata"]["assetUse"] == "scene_plate"
