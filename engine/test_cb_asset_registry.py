import json
import pathlib
from concurrent.futures import ThreadPoolExecutor

import pytest

import cb_asset_registry as A

registry = A


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


def test_reregistering_existing_binding_preserves_registry_order(monkeypatch, tmp_path):
    media, _ = _tmp_registry(monkeypatch, tmp_path)
    first = media / "first.png"
    second = media / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    A.register_asset(
        episode="Ep1", scene="1", kind="scene_plate", role="first", path=first)
    A.register_asset(
        episode="Ep1", scene="2", kind="scene_plate", role="second", path=second)

    A.register_asset(
        episode="Ep1", scene="1", kind="scene_plate", role="first", path=first,
        label="First refreshed")

    stored = json.loads((tmp_path / "registry" / "assets.json").read_text())
    assert [item["role"] for item in stored["assets"]] == ["first", "second"]
    assert stored["assets"][0]["label"] == "First refreshed"


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


def test_concurrent_registrations_are_atomic_and_preserve_both_assets(monkeypatch, tmp_path):
    registry_dir = tmp_path / "asset-registry"
    monkeypatch.setattr(registry, "REGISTRY_DIR", registry_dir)
    monkeypatch.setattr(registry, "REGISTRY_PATH", registry_dir / "assets.json")
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    def register(item):
        role, path = item
        return registry.register_asset(
            episode="Ep1", scene="4", kind="reference_image", role=role,
            path=path, require_displayable=False)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(register, (("first", first), ("second", second))))

    data = registry._read()
    assert {item["role"] for item in data["assets"]} == {"first", "second"}
    assert not list(registry_dir.glob("*.tmp"))


def test_shot_media_deduplicates_transport_aliases(monkeypatch, tmp_path):
    c1 = tmp_path / "c1.mp4"
    c2 = tmp_path / "c2.mp4"
    c1.write_bytes(b"one")
    c2.write_bytes(b"two")
    assets = [
        {"assetId": "c1", "episode": "Ep1", "scene": "3", "shotId": "3.B1.S1",
         "kind": "candidate_take", "role": "candidate_1", "status": "candidate",
         "path": str(c1), "url": "/media/c1.mp4"},
        {"assetId": "tc1", "episode": "Ep1", "scene": "3", "shotId": "3.B1.S1",
         "kind": "candidate_take", "role": "transport_candidate_1", "status": "candidate",
         "path": str(c1), "url": "/media/c1.mp4"},
        {"assetId": "c2", "episode": "Ep1", "scene": "3", "shotId": "3.B1.S1",
         "kind": "candidate_take", "role": "candidate_2", "status": "candidate",
         "path": str(c2), "url": "/media/c2.mp4"},
        {"assetId": "tc2", "episode": "Ep1", "scene": "3", "shotId": "3.B1.S1",
         "kind": "candidate_take", "role": "transport_candidate_2", "status": "candidate",
         "path": str(c2), "url": "/media/c2.mp4"},
    ]
    monkeypatch.setattr(registry, "migrate_existing", lambda episode: None)
    monkeypatch.setattr(registry, "resolve_assets", lambda *args, **kwargs: assets)

    media = registry.shot_media_from_registry(
        {"shots": [{"shotId": "3.B1.S1"}]}, "3", "Ep1")

    assert media["3.B1.S1"]["candidates"] == [
        {"n": 1, "url": "/media/c1.mp4"},
        {"n": 2, "url": "/media/c2.mp4"},
    ]
