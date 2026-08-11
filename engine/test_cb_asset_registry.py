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
