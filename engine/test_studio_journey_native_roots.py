import hashlib

import pytest

from studio_journey_native import file_record


def test_file_record_accepts_configured_data_media_only(tmp_path, monkeypatch):
    source = tmp_path / "release"
    data = tmp_path / "production-data"
    cwd = tmp_path / "cwd"
    source.mkdir()
    cwd.mkdir()
    media = data / "engine" / "media" / "shots"
    media.mkdir(parents=True)
    asset = media / "S3.SH1.png"
    asset.write_bytes(b"approved S3.SH1")
    external = tmp_path / "external.png"
    external.write_bytes(b"outside")
    escape = media / "escape.png"
    escape.symlink_to(external)

    monkeypatch.setenv("STUDIO_DATA_ROOT", str(data))
    monkeypatch.chdir(cwd)
    assert source != data and cwd != source and cwd != data

    record = file_record(source, asset)
    assert record == {
        "path": str(asset.resolve()),
        "url": "/engine/media/shots/S3.SH1.png",
        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
    }

    with pytest.raises(ValueError, match="outside the Studio media library"):
        file_record(source, external)
    with pytest.raises(ValueError, match="outside the Studio media library"):
        file_record(source, source / ".." / "external.png")
    with pytest.raises(ValueError, match="outside the Studio media library"):
        file_record(source, escape)
