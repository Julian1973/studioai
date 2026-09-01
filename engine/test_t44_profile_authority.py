#!/usr/bin/env python3
"""T44 — the project profile is the only path authority.

Three things must stay true from here on:
  1. `paths` exposes every declared project location and each one resolves inside the project name-space
     (links out of it are fine — the project owns the NAME, the bytes may live elsewhere).
  2. No live module builds a project path by hand — the literal "projects/crystal-bears" / the bare id
     string appear only where this file's allowlist says (each entry is a later ticket's job).
  3. The default project is decided by the registry (projects/*/profile.json), never by a constant.
"""
import os
import pathlib
import re
import subprocess

import pytest

import paths as P
import project_profile

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Files (repo-relative) that may still name the first project by id — each is owned by a ticket.
ALLOW_PROJECT_ID = {
    "tools/check_links.py",                        # T61 deletes the links and this list
    "engine/project_profile.py",                   # SUPPORTED_ENGINE_ADAPTERS — T55 (capabilities)
    "engine/cb_render.py",                         # adapter check + skills/crystal-bears-* — T53/T55
    "engine/cb_departments.py",                    # skills/crystal-bears-* — T53
    "engine/cb_intake.py",                         # "skill": "crystal-bears-director" — T53
    "tools/sync_canon.py",                         # skills/crystal-bears-* glob — T54
    "cb-studio/data/projects.json",                # the registry itself
}
CODE_GLOBS = ("engine/*.py", "engine/tools/*.py", "cb-studio/*.py", "cb-studio/*.js",
              "cb-studio/*.html", "tools/*.py", "dailies/*.py", "dailies/*.json")


def _live_code_files():
    for pat in CODE_GLOBS:
        for f in ROOT.glob(pat):
            rel = f.relative_to(ROOT).as_posix()
            if "/test_" in "/" + rel or rel.endswith("FULL_AUDIT_2026-07-11_findings.json"):
                continue
            yield rel, f


def test_every_declared_path_sits_inside_the_project_namespace():
    project = pathlib.Path(P.PROJECT)
    for name in ("CANON", "CHARS", "LOCATIONS", "CONTINUITY", "CONFIG", "STYLE_LAW", "CREATIVE",
                 "SCRIPTS", "OUTPUT", "EPISODES_INDEX", "ASSETS", "VOICE_CARDS", "BEAT_COSTS",
                 "LOCK_POLICY", "CANON_LOCK", "SFX_LIBRARY", "SFX_DIR", "SHOW_BIBLE"):
        value = getattr(P, name)
        assert value, f"paths.{name} is undeclared for {P.PROJECT_ID}"
        assert pathlib.Path(value).is_relative_to(project), f"paths.{name} = {value} is outside the project"


def test_assets_may_be_a_link_out_of_the_project():
    # The name is the project's; the bytes may live behind a link (cb-seed/assets for one release).
    assert os.path.exists(P.ASSETS), P.ASSETS
    assert os.path.isdir(os.path.realpath(P.ASSETS))


def test_no_live_module_names_the_first_project_by_hand():
    offenders = []
    needle = re.compile(r'projects/crystal-bears|"projects" ?/ ?"crystal-bears"|"projects", ?"crystal-bears"'
                        r'|(?<![\w-])["\']crystal-bears["\']')
    for rel, f in _live_code_files():
        if rel in ALLOW_PROJECT_ID:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not offenders, "hand-built project paths/ids in live code:\n" + "\n".join(offenders)


ALLOW_OLD_OUTPUT_NAME = {
    "cb-studio/serve.py",      # the "/cb-output/" URL root — served through the compatibility link, T61
    "tools/check_links.py",
}


def test_no_live_module_builds_the_output_path_by_hand():
    """T45: packages/evidence live at paths.OUTPUT — never ROOT/"cb-output" spelled by hand."""
    needle = re.compile(r'/ "cb-output"|"cb-output/|\'cb-output/|"\.\./cb-output')
    offenders = []
    for rel, f in _live_code_files():
        if rel in ALLOW_OLD_OUTPUT_NAME:
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if needle.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not offenders, "hand-built output paths in live code:\n" + "\n".join(offenders)


def test_default_project_comes_from_the_registry(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_PROJECT", raising=False)
    monkeypatch.delenv("STUDIO_SHOW", raising=False)
    (tmp_path / "projects").mkdir()
    with pytest.raises(project_profile.ShowProfileError, match="no projects"):
        project_profile.default_project_id(tmp_path)
    a = tmp_path / "projects" / "aaa"; a.mkdir(); (a / "profile.json").write_text('{"showId":"aaa"}')
    assert project_profile.default_project_id(tmp_path) == "aaa"          # the only project
    b = tmp_path / "projects" / "bbb"; b.mkdir(); (b / "profile.json").write_text('{"showId":"bbb"}')
    with pytest.raises(project_profile.ShowProfileError, match="none declares"):
        project_profile.default_project_id(tmp_path)                          # two, no default
    (b / "profile.json").write_text('{"showId":"bbb","default":true}')
    assert project_profile.default_project_id(tmp_path) == "bbb"          # the declared default
    monkeypatch.setenv("STUDIO_PROJECT", "aaa")
    assert project_profile.default_project_id(tmp_path) == "aaa"          # env wins
    monkeypatch.delenv("STUDIO_PROJECT")
    monkeypatch.setenv("STUDIO_SHOW", "aaa")
    assert project_profile.default_project_id(tmp_path) == "aaa"          # legacy alias still honoured


def test_studio_profile_shim_is_the_same_objects():
    import studio_profile
    assert studio_profile.load_show_profile is project_profile.load_show_profile
    assert studio_profile.ShowProfileError is project_profile.ShowProfileError
    assert studio_profile.DEFAULT_SHOW_ID == P.PROJECT_ID


def test_extended_profile_declares_the_files_the_engine_reads():
    prof = P.PROFILE.profile
    assert prof.canon.voiceCards and prof.canon.beatCosts and prof.canon.lockPolicy
    assert prof.creative and prof.creative.learning and prof.creative.voicePlaybook
    assert prof.assets and prof.assets.root
    assert prof.episodes.index
