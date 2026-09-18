import hashlib

import pytest
from PIL import Image

from studio_storyboard_sheet import compile_sheet


def _status(path, scope):
    image_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'scope': scope,
        'authoredActionHash': 'action-hash',
        'panels': [{
            'id': 'S3.SH1:opening', 'atSec': 0, 'viewId': 'S3-V01',
            'checkpointType': 'OPENING_STATE', 'inputHash': 'input-hash',
            'media': {'path': str(path), 'sha256': image_hash, 'current': True},
            'status': 'current', 'reviewStatus': 'approved',
            'review': {'decision': 'approved'},
            'actionHash': 'panel-action', 'storyboardRevision': 1,
            'directorCardRevision': 1, 'fidelity': 'OPENING_KEYFRAME',
        }],
    }


def test_compile_sheet_accepts_data_root_media_from_any_cwd(tmp_path, monkeypatch):
    source = tmp_path / 'release'
    data = tmp_path / 'production-data'
    cwd = tmp_path / 'cwd'
    media = data / 'engine' / 'media' / 'shots'
    source.mkdir()
    cwd.mkdir()
    media.mkdir(parents=True)
    asset = media / 'S3.SH1.png'
    Image.new('RGB', (320, 180), 'navy').save(asset)
    monkeypatch.setenv('STUDIO_DATA_ROOT', str(data))
    monkeypatch.chdir(cwd)

    result = compile_sheet(source, 'crystal-bears/Ep4/3/S3.SH1',
                           _status(asset, {'projectId': 'crystal-bears'}))

    assert result['providerCalls'] == 0
    assert result['media']['path'] == (
        'engine/media/see-storyboards/crystal-bears/Ep4/3/S3.SH1/'
        + result['sourceBinding'] + '.png')


@pytest.mark.parametrize('asset_kind', ['external', 'traversal', 'symlink'])
def test_compile_sheet_rejects_media_escape(tmp_path, monkeypatch, asset_kind):
    source = tmp_path / 'release'
    data = tmp_path / 'production-data'
    media = data / 'engine' / 'media'
    source.mkdir()
    media.mkdir(parents=True)
    outside = tmp_path / 'outside.png'
    Image.new('RGB', (320, 180), 'red').save(outside)
    monkeypatch.setenv('STUDIO_DATA_ROOT', str(data))

    if asset_kind == 'external':
        asset = outside
    elif asset_kind == 'traversal':
        asset = media / '..' / '..' / '..' / 'outside.png'
    else:
        asset = media / 'escape.png'
        asset.symlink_to(outside)

    with pytest.raises(ValueError, match='outside the trusted Studio media library'):
        compile_sheet(source, 'crystal-bears/Ep4/3/S3.SH1',
                      _status(asset, {'projectId': 'crystal-bears'}))
