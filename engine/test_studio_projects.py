"""A new production can enter the canonical script pathway without source edits."""
import json

import pytest

import cb_scripts
import studio_profile
import studio_projects


def brief(name="Lantern House"):
    return {"name": name, "animationType": "Live action", "aspectRatio": "16:9",
            "showBible": "Two siblings return home to reconcile.",
            "characters": [{"name": "Morgan", "keyFeatures": "Older sibling"}],
            "premise": "A homecoming changes two lives."}


def no_image(value):
    raise ValueError("Invalid image")


def test_new_project_to_immutable_script_and_reopen(tmp_path):
    project = studio_projects.create_project(tmp_path, brief(), decode_image=no_image)
    pid = project["id"]
    loaded = studio_profile.load_show_profile(tmp_path, pid)
    assert loaded.profile.showId == "lantern-house"
    assert loaded.canon_paths["characters"].is_file()
    assert not project["capabilities"]["adapterReady"]
    assert not project["capabilities"]["productionReady"]
    script = "INT. LANTERN HOUSE - NIGHT\nMORGAN\nI kept the light on.\n"
    first = studio_projects.store_script(tmp_path, pid, "Ep1", script, "Home")
    second = studio_projects.store_script(tmp_path, pid, "Ep1", script + "Silence.\n", "Home")
    assert first["scriptVersionId"] != second["scriptVersionId"]
    store = cb_scripts.ScriptStore(tmp_path, show_id=pid)
    assert store.current("Ep1")["scriptVersionId"] == second["scriptVersionId"]
    assert len(list(store.versions_root.glob("Ep1/*.txt"))) == 2
    assert studio_projects.list_projects(tmp_path)[0]["episodeCount"] == 1
    assert not (tmp_path / "shows/crystal-bears").exists()


def test_duplicate_names_never_overwrite_a_production(tmp_path):
    first = studio_projects.create_project(tmp_path, brief(), decode_image=no_image)
    second = studio_projects.create_project(tmp_path, brief(), decode_image=no_image)
    assert first["id"] == "lantern-house"
    assert second["id"] == "lantern-house-2"
    assert len(studio_projects.list_projects(tmp_path)) == 2


def test_invalid_reference_is_rejected_before_writing(tmp_path):
    data = brief()
    data["characters"][0]["imageData"] = "broken"
    with pytest.raises(ValueError, match="Invalid image"):
        studio_projects.create_project(tmp_path, data, decode_image=no_image)
    assert not (tmp_path / "shows").exists()


def test_character_names_and_format_are_validated_before_writing(tmp_path):
    data = brief()
    data["characters"].append({"name": "morgan"})
    with pytest.raises(ValueError, match="unique"):
        studio_projects.create_project(tmp_path, data, decode_image=no_image)
    data = brief()
    data["aspectRatio"] = "unlimited"
    with pytest.raises(ValueError, match="aspect ratio"):
        studio_projects.create_project(tmp_path, data, decode_image=no_image)
    assert not (tmp_path / "shows").exists()


def test_legacy_archive_is_preserved_during_discovery(tmp_path):
    registry = tmp_path / "cb-studio/data/projects.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"projects": [{"id": "old-archive", "archived": True}]}))
    studio_projects.create_project(tmp_path, brief(), decode_image=no_image)
    assert {row["id"] for row in studio_projects.list_projects(tmp_path)} == {"old-archive", "lantern-house"}
    assert json.loads(registry.read_text())["projects"][0]["archived"] is True


def test_unpublished_directory_is_not_discovered(tmp_path):
    (tmp_path / "shows/incomplete/canon").mkdir(parents=True)
    assert studio_projects.list_projects(tmp_path) == []
