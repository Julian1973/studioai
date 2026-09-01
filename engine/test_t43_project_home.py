#!/usr/bin/env python3
"""T43 — one home per project: every Crystal Bears file lives under projects/crystal-bears/
and every old path is an alias (a link), never a second physical copy."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_links  # noqa: E402


def test_every_compatibility_link_resolves():
    assert check_links.broken_links(ROOT) == []


def test_links_point_where_the_spec_says():
    for rel, target in check_links.COMPATIBILITY_LINKS:
        assert (ROOT / rel).readlink().as_posix() == target, rel


def test_no_second_physical_copy_of_project_data_outside_the_project():
    # git must not track any real file at the old locations — only the links themselves.
    tracked = subprocess.run(["git", "ls-files", "shows", "cb-output", "engine/config",
                              "cb-studio/data/scripts"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    assert sorted(tracked) == sorted(["shows", "cb-output", "engine/config",
                                      "cb-studio/data/scripts"]), tracked


def test_profile_output_path_exists_now():
    import studio_profile
    loaded = studio_profile.load_show_profile(ROOT)
    assert loaded.output_path.is_dir(), "profile.json's episodes.output was a phantom before T43"
    assert loaded.scripts_path.is_dir()
