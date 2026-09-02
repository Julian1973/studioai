"""The reference-control writers must hand cb_db the REPOSITORY root, never the project root.

Found 2026-09-02 on The Box Monsters: cb_render's zero-spend control writers passed
MEDIA.parent.parent.parent, which was the repository root only while every project shared
engine/media/shots. Since T58 a project owns its own media, so those three parents land on
projects/<id>/ — and cb_db.state_db_path joins the project's own OUTPUT_REL onto it a second
time, opening a second, unread state database at

    projects/<id>/projects/<id>/episodes/output/state/studio.sqlite3

The control images and records themselves were written to their real absolute paths; only the
revision/digest bookkeeping went to the stray database, so those writes had no conflict
detection at all. These tests pin the root, and pin that no path doubles the project again.
"""
import pathlib

import cb_db
import cb_render
import paths as P


def test_state_root_is_the_repository_root_not_the_project_root():
    assert cb_render._state_root() == cb_render.HERE.parent
    assert (cb_render._state_root() / "engine").is_dir()
    # The project root is a strictly deeper thing; handing it to cb_db is the bug.
    assert cb_render._state_root() != pathlib.Path(P.PROJECT)


def test_state_database_lands_once_inside_the_active_project_output(monkeypatch):
    # conftest routes every test's database to its own scratch tree; this one is about the
    # path arithmetic itself, so it asks cb_db the same question production asks.
    monkeypatch.delenv("CB_STUDIO_STATE_DB", raising=False)
    db = cb_db.state_db_path(cb_render._state_root())
    assert db == pathlib.Path(P.OUTPUT).resolve() / "state" / "studio.sqlite3"
    # The project's own folder name appears exactly once — a doubled path is the whole failure.
    assert db.parts.count(pathlib.PurePath(P.OUTPUT_REL).parts[1]) == 1


def test_no_writer_derives_a_root_from_media_depth_again():
    source = pathlib.Path(cb_render.__file__).read_text(encoding="utf-8")
    assert "MEDIA.parent.parent.parent" not in source
