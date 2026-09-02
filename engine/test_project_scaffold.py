#!/usr/bin/env python3
"""T56 — a new project is created from studio/templates/project/, engine-valid on arrival."""
import json
import os
import pathlib

import pytest

import project_profile
import project_scaffold as S

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def scratch(tmp_path):
    (tmp_path / "projects").mkdir()
    return tmp_path


def test_template_is_a_complete_project_skeleton():
    template = S.TEMPLATE
    for rel in ("profile.json", "canon/LOCKED_CANON.md", "canon/characters.json", "canon/locations.json",
                "canon/continuity.json", "laws/style.txt", "laws/cast_vocabulary.json",
                "laws/forbidden_elements.json", "laws/continuity_rules.json", "laws/emission_checks.json",
                "chairs/room.json", "creative/design_roster.json", "episodes/episodes.json",
                "SHOW_BIBLE.md"):
        assert (template / rel).exists(), rel
    text = "\n".join(p.read_text(encoding="utf-8") for p in template.rglob("*") if p.is_file() and p.suffix in (".json", ".md", ".txt"))
    assert "crystal" not in text.lower() and "Fuzzby" not in text     # the template names no show


def test_scaffold_creates_a_valid_project_with_its_cast(scratch):
    out = S.scaffold_project("Box Monsters", root=scratch,
                             facts={"premise": "Monsters who live in boxes", "audience": "Kids 4-8",
                                    "showrunner": "Julian", "animationType": "Stylized 3D CGI"},
                             characters=[{"name": "Crumple", "keyFeatures": "a crumpled cardboard monster",
                                          "species": "box monster"},
                                         {"name": "Tape", "keyFeatures": "sticky"}])
    assert out["id"] == "box-monsters"
    prof = out["profile"]
    assert prof.profile.name == "Box Monsters" and prof.profile.showrunner == "Julian"
    assert prof.profile.engineAdapter is None                    # T55: no adapter
    report = project_profile.capability_report(prof)
    assert report["productionReady"] is True and report["missingRequiredContent"] == []
    chars = json.loads((out["root"] / "canon" / "characters.json").read_text(encoding="utf-8"))
    assert chars["Crumple"]["species"] == "box monster" and chars["Tape"]["sizeRank"] == 2
    vocab = json.loads((out["root"] / "laws" / "cast_vocabulary.json").read_text(encoding="utf-8"))
    assert vocab["names"] == ["Crumple", "Tape"] and vocab["species"] == {"Crumple": "box monster"}
    roster = json.loads((out["root"] / "creative" / "design_roster.json").read_text(encoding="utf-8"))
    assert [c["name"] for c in roster["characters"]] == ["Crumple", "Tape"]
    style = (out["root"] / "laws" / "style.txt").read_text(encoding="utf-8")
    assert style.startswith("Stylized 3D CGI, Kids 4-8:") and "{{" not in style
    bible = (out["root"] / "SHOW_BIBLE.md").read_text(encoding="utf-8")
    assert "Monsters who live in boxes" in bible and "{{" not in bible
    # the project is registered by its own profile — the engine lists it
    assert "box-monsters" in project_profile.list_project_ids(scratch)


def test_scaffold_never_overwrites_and_ids_are_unique(scratch):
    S.scaffold_project("Box Monsters", root=scratch)
    with pytest.raises(S.ScaffoldError, match="already exists"):
        S.scaffold_project("Box Monsters", root=scratch, project_id="box-monsters")
    assert S.project_id_for("Box Monsters", scratch) == "box-monsters-2"
    assert S.project_id_for("  Ünnamed!! ", scratch) == "nnamed"


def test_fresh_project_is_isolated_from_the_first_project(scratch, monkeypatch):
    """With the fresh project active, no path the engine resolves points at another project."""
    S.scaffold_project("Moon Lanterns", root=scratch)
    loaded = project_profile.load_show_profile(scratch, "moon-lanterns")
    for name, path in {**loaded.canon_paths, **loaded.laws_paths,
                       "scripts": loaded.scripts_path, "output": loaded.output_path,
                       "index": loaded.episodes_index_path}.items():
        assert str(path).startswith(str(scratch / "projects" / "moon-lanterns")), name
