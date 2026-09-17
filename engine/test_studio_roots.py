from pathlib import Path

import pytest

from studio_roots import is_trusted, trusted_path


def test_source_local_path_is_trusted(tmp_path):
    path = tmp_path / "source" / "shows" / "canon.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    assert trusted_path(path, tmp_path / "source") == path.resolve()


def test_explicit_external_data_root_is_trusted(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production-data"
    data.mkdir()
    target = data / "canon.json"
    target.write_text("{}")
    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    assert trusted_path(target, source) == target.resolve()


def test_release_symlink_into_trusted_data_root_is_trusted(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production-data"
    data.mkdir()
    link = source / "shows" / "crystal-bears" / "canon.json"
    link.parent.mkdir(parents=True)
    target = data / "canon.json"
    target.write_text("{}")
    link.symlink_to(target)
    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    assert trusted_path(link, source) == target.resolve()


def test_untrusted_tmp_symlink_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production-data"
    data.mkdir()
    target = tmp_path / "untrusted" / "canon.json"
    target.parent.mkdir()
    target.write_text("{}")
    link = source / "canon.json"
    source.mkdir()
    link.symlink_to(target)
    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    with pytest.raises(ValueError):
        trusted_path(link, source)


def test_parent_escape_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production-data"
    source.mkdir(); data.mkdir()
    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    assert not is_trusted(source / ".." / "outside.json", source)


def test_missing_data_root_is_clear(tmp_path, monkeypatch):
    source = tmp_path / "release"
    source.mkdir()
    missing = tmp_path / "missing-data"
    monkeypatch.setenv("STUDIO_DATA_ROOT", str(missing))
    with pytest.raises(ValueError):
        trusted_path(missing / "canon.json", source)
