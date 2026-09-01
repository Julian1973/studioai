import json
import pathlib

import pytest

import cb_scripts
import project_profile as studio_profile


def _profile(root, show_id="moon-lanterns", *, adapter="moon-lanterns-v1",
             characters="canon/characters.json"):
    show = root / "projects" / show_id
    show.mkdir(parents=True)
    payload = {
        "showId": show_id,
        "name": "Moon Lanterns",
        "animationType": "Stylized 3D CGI",
        "aspectRatio": "16:9",
        "engineAdapter": adapter,
        "canon": {
            "lockedCanon": "canon/LOCKED_CANON.md",
            "characters": characters,
            "locations": "canon/locations.json",
            "continuity": "canon/continuity.json",
            "identityPacks": "canon/identity_packs.json",
        },
        "laws": {"style": "laws/style.txt"},
        "episodes": {
            "scripts": "episodes/scripts",
            "output": "episodes/output",
        },
        "creativeRoot": "creative",
    }
    (show / "profile.json").write_text(json.dumps(payload))
    return show


def test_profile_resolves_only_inside_selected_tenant(tmp_path):
    show = _profile(tmp_path)
    loaded = studio_profile.load_show_profile(tmp_path, "moon-lanterns")

    assert loaded.profile.showId == "moon-lanterns"
    assert loaded.scripts_path == show / "episodes" / "scripts"
    assert loaded.canon_paths["characters"] == show / "canon" / "characters.json"
    assert loaded.canon_paths["identityPacks"] == show / "canon" / "identity_packs.json"
    report = studio_profile.capability_report(loaded)
    # T55: no adapter gate — production is blocked only by missing content, each file named by path
    assert report["adapterReady"] is True
    assert report["productionReady"] is False
    assert any(item.startswith("lockedCanon: projects/moon-lanterns/canon/LOCKED_CANON.md")
               for item in report["missingRequiredPaths"])
    assert report["capabilities"]["animation"] is True


def test_profile_loads_without_an_engine_adapter(tmp_path):
    show = _profile(tmp_path)
    payload = json.loads((show / "profile.json").read_text())
    del payload["engineAdapter"]
    payload["capabilities"] = {"music": False}
    (show / "profile.json").write_text(json.dumps(payload))
    loaded = studio_profile.load_show_profile(tmp_path, "moon-lanterns")
    report = studio_profile.capability_report(loaded)
    assert loaded.profile.engineAdapter is None
    assert report["capabilities"]["music"] is False and report["capabilities"]["voice"] is True


def test_selected_show_never_falls_back_to_crystal_bears(tmp_path):
    _profile(tmp_path, "crystal-bears", adapter="crystal-bears-v1")
    with pytest.raises(studio_profile.ShowProfileError, match="missing or invalid"):
        studio_profile.load_show_profile(tmp_path, "moon-lanterns")


def test_profile_rejects_path_escape_and_invalid_show_id(tmp_path):
    _profile(tmp_path, characters="../../outside.json")
    with pytest.raises(studio_profile.ShowProfileError, match="escapes"):
        studio_profile.load_show_profile(tmp_path, "moon-lanterns")
    with pytest.raises(studio_profile.ShowProfileError, match="lowercase"):
        studio_profile.load_show_profile(tmp_path, "../moon-lanterns")


def test_script_store_isolates_a_second_show(tmp_path):
    _profile(tmp_path)
    store = cb_scripts.ScriptStore(tmp_path, show_id="moon-lanterns")
    current = store.store("Ep1", "INT. MOON ROOM - NIGHT\nA lantern wakes.", "Awake")

    content = tmp_path / current["contentPath"]
    assert content.is_relative_to(tmp_path / "projects/moon-lanterns/episodes/scripts")
    assert not (tmp_path / "projects/crystal-bears/episodes/scripts").exists()
    # T43: one script store per project — the display file lives in the project, and the
    # studio keeps NO second copy anywhere under cb-studio/.
    assert (tmp_path / "projects/moon-lanterns/episodes/scripts/Ep1_Awake.txt").exists()
    assert not (tmp_path / "cb-studio/data/shows").exists()
    assert not (tmp_path / "cb-studio/data/scripts").exists()


def test_script_pointer_cannot_escape_the_active_show(tmp_path):
    script_root = tmp_path / "projects/crystal-bears/episodes/scripts"
    store = cb_scripts.ScriptStore(tmp_path, script_root=script_root)
    current = store.store("Ep1", "A safe script.", "Safe")
    pointer = script_root / "_current" / "Ep1.json"
    record = json.loads(pointer.read_text())
    outside = tmp_path / "outside.txt"
    outside.write_text("tampered")
    record["contentPath"] = str(outside.relative_to(tmp_path))
    pointer.write_text(json.dumps(record))

    with pytest.raises(cb_scripts.ScriptStoreError, match="escapes"):
        store.current("Ep1")
