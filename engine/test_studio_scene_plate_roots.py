import hashlib

import pytest

from studio_scene_plate import authority_file, reference


def test_scene_plate_authority_accepts_data_root_from_any_cwd(tmp_path, monkeypatch):
    source = tmp_path / 'release'
    data = tmp_path / 'production-data'
    cwd = tmp_path / 'cwd'
    source.mkdir()
    cwd.mkdir()
    canon = data / 'shows' / 'crystal-bears' / 'canon' / 'LOCKED_CANON.md'
    canon.parent.mkdir(parents=True)
    canon.write_text('# locked canon\n')
    monkeypatch.setenv('STUDIO_DATA_ROOT', str(data))
    monkeypatch.chdir(cwd)

    result = authority_file(source, canon)

    assert source != data and cwd != source and cwd != data
    assert result['source'] == 'shows/crystal-bears/canon/LOCKED_CANON.md'
    assert result['revision'] == hashlib.sha256(canon.read_bytes()).hexdigest()


@pytest.mark.parametrize('kind', ['external', 'traversal', 'symlink'])
def test_scene_plate_reference_rejects_untrusted_media(tmp_path, monkeypatch, kind):
    source = tmp_path / 'release'
    data = tmp_path / 'production-data'
    source.mkdir()
    media = data / 'engine' / 'media'
    media.mkdir(parents=True)
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'outside')
    if kind == 'external':
        path = outside
    elif kind == 'traversal':
        path = media / '..' / '..' / '..' / 'outside.png'
    else:
        path = media / 'escape.png'
        path.symlink_to(outside)
    monkeypatch.setenv('STUDIO_DATA_ROOT', str(data))

    with pytest.raises(ValueError):
        reference(source, {'path': str(path), 'approvalStatus': 'approved'},
                  'LOCATION_REFERENCE', 'test')
