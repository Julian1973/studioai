"""Exercise the actual HTTP intake boundary without touching production or providers."""
import json
from types import SimpleNamespace
from test_local_auth import studio, _request


def test_script_save_waits_for_budget_and_preserves_exact_text(studio, monkeypatch):
    server, port = studio
    saved = []
    script = 'INT. GARDEN - DAY\nBo: I can try.\n'
    def store(episode, text, title, **metadata):
        saved.append((episode, text, title))
        return {'displayFile': 'Ep3_Test.txt', 'scriptVersionId': 'sha256:fixture'}
    monkeypatch.setattr(server, 'SCRIPT_STORE', SimpleNamespace(store=store))
    monkeypatch.setattr(server, 'reindex_episodes', lambda: [{'number': 3, 'title': 'Test'}])
    import cb_intake, cb_episode_budget
    monkeypatch.setattr(cb_intake, 'intake_status', lambda ep: {'canonicalCurrent': False})
    monkeypatch.setattr(cb_episode_budget, 'require_allowance', lambda *args: {'approved': False})
    def forbidden(*args, **kwargs):
        raise AssertionError('Intake must not generate before the episode budget is approved')
    monkeypatch.setattr(server, '_start', forbidden)
    _, headers, _ = _request(port, 'GET', '/cb-studio/app.html')
    auth = {'Cookie': headers['Set-Cookie'].split(';', 1)[0], 'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json'}
    status, _, body = _request(port, 'POST', '/api/episode', auth, json.dumps({'number': 3, 'title': 'Test', 'script': script}))
    result = json.loads(body)
    assert status == 200
    assert saved == [('Ep3', script, 'Test')]
    assert result['directionPreparation'] == 'awaiting-episode-budget'
    assert result['directionPreparationJobId'] is None
