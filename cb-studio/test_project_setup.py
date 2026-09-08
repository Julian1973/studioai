"""Project setup writes only isolated project assets and scripts; no provider work."""
import json
import pytest
from test_local_auth import studio, _request


@pytest.mark.parametrize('contents', ['{broken', '[]', '{"projects": {}}'])
def test_invalid_registry_is_not_reported_as_an_empty_workspace(studio, monkeypatch, tmp_path, contents):
    module, port = studio
    _, headers, _ = _request(port, 'GET', '/cb-studio/app.html')
    auth = {'Cookie': headers['Set-Cookie'].split(';', 1)[0]}
    registry = tmp_path/'cb-studio/data/projects.json'
    registry.parent.mkdir(parents=True)
    registry.write_text(contents)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    status, _, body = _request(port, 'GET', '/api/projects', auth)
    assert status == 503 and 'error' in json.loads(body)
    assert 'projects' not in json.loads(body)
    assert registry.read_text() == contents
    registry.write_text('{"projects": []}')
    status, _, body = _request(port, 'GET', '/api/projects', auth)
    assert status == 200 and json.loads(body)['projects'] == []


def test_two_projects_keep_bibles_assets_and_scripts_separate(studio, monkeypatch, tmp_path):
    module, port = studio
    _, headers, _ = _request(port, 'GET', '/cb-studio/app.html')
    auth = {'Cookie': headers['Set-Cookie'].split(';', 1)[0],
            'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'}
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    (tmp_path / 'cb-studio/data').mkdir(parents=True)
    monkeypatch.setattr(module, 'decode_image_upload', lambda raw: (raw.encode(), '.png'))
    def post(path, payload):
        status, _, body = _request(port, 'POST', path, auth, json.dumps(payload))
        return status, json.loads(body)
    ids = []
    for bible in ('First world', 'Second world'):
        status, result = post('/api/project', {'name': 'A Film', 'projectType': 'film',
            'showBible': bible, 'characters': [{'name': 'Hero', 'imageData': bible}],
            'locations': [{'name': 'Forest', 'notes': bible, 'imageData': bible}],
            'props': [{'name': 'Map', 'notes': bible}]})
        assert status == 200, result
        ids.append(result['id'])
        meta = result['project']
        assert meta['canonApproved'] is False
        assert meta['setupGaps'] == ['props: Map reference image']
        pdir = tmp_path / 'projects' / result['id']
        assert (pdir / 'show_bible.md').read_text() == bible
        chars = json.loads((pdir / 'characters.json').read_text())
        assert set(chars) == {'Hero'}
        assert chars['Hero']['anchor'].startswith(f"projects/{result['id']}/")
        assert json.loads((pdir / 'locations.json').read_text())[0]['notes'] == bible
        assert json.loads((pdir / 'episodes.json').read_text()) == []
    assert ids == ['a-film', 'a-film-2']
    status, result = post('/api/project-episode', {'projectId': ids[0], 'title': 'Opening', 'script': 'Only in first project'})
    assert status == 200, result
    assert len(json.loads((tmp_path / 'projects/a-film/episodes.json').read_text())) == 1
    assert json.loads((tmp_path / 'projects/a-film-2/episodes.json').read_text()) == []
    status, _ = post('/api/project-episode', {'projectId': '../crystal-bears', 'title': 'X', 'script': 'X'})
    assert status == 400
    status, _ = post('/api/project', {'name': 'Invalid', 'characters': [{'name': 'Hero'}, {'name': 'hero'}]})
    assert status == 400
    assert not (tmp_path / 'projects/invalid').exists()
