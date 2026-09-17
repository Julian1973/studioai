from hashlib import sha256

import pytest

from studio_seedance_execution import require_reference_bindings


def test_reference_bindings_use_explicit_root_not_process_cwd(tmp_path, monkeypatch):
    media = tmp_path / "projects" / "demo" / "media" / "plate.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"plate")
    binding = {"role": "scene plate", "path": "projects/demo/media/plate.png",
               "hash": sha256(b"plate").hexdigest()}
    monkeypatch.chdir("/")
    require_reference_bindings([binding], root=tmp_path)


def test_reference_binding_diagnostic_has_stable_identity(tmp_path):
    with pytest.raises(ValueError, match="WATCH_REFERENCE_MISSING: reference Sunny"):
        require_reference_bindings([{"name": "Sunny", "path": "missing.png",
                                     "hash": sha256(b"missing").hexdigest()}], root=tmp_path)
